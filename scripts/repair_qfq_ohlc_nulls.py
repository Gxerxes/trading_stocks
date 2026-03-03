"""
修复 stock_daily_qfq 中早期 OHLC 为空的历史文件。

原因：
- Tushare pro_bar 在长区间 qfq 请求下，部分股票早期 OHLC 可能返回空值。
- 该脚本改用分段下载并重建：
  1) stock_daily_qfq
  2) weekly_data_qfq
  3) lake/bars/snapshot（日/周；保留原有5分钟段）

示例：
python scripts/repair_qfq_ohlc_nulls.py
python scripts/repair_qfq_ohlc_nulls.py --ts-code 000021.SZ
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import tushare as ts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DATA = PROJECT_ROOT / "ai_stock_agent" / "data"
DAILY_QFQ_DIR = APP_DATA / "stock_daily_qfq"
WEEKLY_QFQ_DIR = APP_DATA / "weekly_data_qfq"
SNAP_DIR = APP_DATA / "lake" / "bars" / "snapshot"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="修复 qfq 日线 OHLC 空值")
    p.add_argument("--ts-code", type=str, default=None, help="仅修复单只股票，如 000021.SZ")
    return p.parse_args()


def load_token() -> str:
    env_file = PROJECT_ROOT / ".env"
    token = None
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TUSHARE_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN")
    return token


def chunked_qfq_download(pro, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    s = datetime.strptime(start_date, "%Y%m%d")
    e = datetime.strptime(end_date, "%Y%m%d")
    if s > e:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    cursor = s
    chunk_days = 730
    while cursor <= e:
        ce = min(cursor + timedelta(days=chunk_days - 1), e)
        cs_str = cursor.strftime("%Y%m%d")
        ce_str = ce.strftime("%Y%m%d")
        part = ts.pro_bar(
            ts_code=ts_code,
            adj="qfq",
            start_date=cs_str,
            end_date=ce_str,
            asset="E",
            adjfactor=False,
            api=pro,
        )
        if part is not None and not part.empty:
            frames.append(part)
        cursor = ce + timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["trade_date"] = out["trade_date"].astype(str)
    out = out.drop_duplicates(subset=["trade_date"], keep="last")
    out = out.sort_values("trade_date").reset_index(drop=True)
    return out


def normalize_daily(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    out = df[cols].copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    out = out.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    for c in ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def build_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    w = (
        daily_df.groupby(daily_df["trade_date"].dt.to_period("W-FRI"), as_index=False)
        .agg(
            ts_code=("ts_code", "first"),
            trade_date=("trade_date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            vol=("vol", "sum"),
            amount=("amount", "sum"),
        )
        .sort_values("trade_date")
        .reset_index(drop=True)
    )
    w["pre_close"] = w["close"].shift(1)
    w["change"] = w["close"] - w["pre_close"]
    w["pct_chg"] = (w["change"] / w["pre_close"]) * 100
    return w[["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]]


def save_daily(ts_code: str, daily_df: pd.DataFrame) -> Path:
    start = daily_df["trade_date"].min().strftime("%Y%m%d")
    end = daily_df["trade_date"].max().strftime("%Y%m%d")
    out = DAILY_QFQ_DIR / f"{ts_code}_qfq_{start}_{end}.csv"
    tmp = daily_df.copy()
    tmp["trade_date"] = tmp["trade_date"].dt.strftime("%Y%m%d")
    tmp.to_csv(out, index=False, encoding="utf-8-sig")
    for f in DAILY_QFQ_DIR.glob(f"{ts_code}_qfq_*.csv"):
        if f != out:
            f.unlink(missing_ok=True)
    return out


def save_weekly(ts_code: str, weekly_df: pd.DataFrame) -> Path:
    start = weekly_df["trade_date"].min().strftime("%Y%m%d")
    end = weekly_df["trade_date"].max().strftime("%Y%m%d")
    out = WEEKLY_QFQ_DIR / f"{ts_code}_qfq_w_{start}_{end}.csv"
    tmp = weekly_df.copy()
    tmp["trade_date"] = tmp["trade_date"].dt.strftime("%Y%m%d")
    tmp.to_csv(out, index=False, encoding="utf-8-sig")
    for f in WEEKLY_QFQ_DIR.glob(f"{ts_code}_qfq_w_*.csv"):
        if f != out:
            f.unlink(missing_ok=True)
    return out


def rewrite_snapshot(ts_code: str, daily_df: pd.DataFrame, weekly_df: pd.DataFrame) -> Path:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    d = pd.DataFrame(
        {
            "ts_code": ts_code,
            "freq": "1d",
            "trade_date": daily_df["trade_date"].dt.strftime("%Y%m%d"),
            "trade_time": daily_df["trade_date"].dt.strftime("%Y-%m-%d 15:00:00"),
            "open": daily_df["open"],
            "high": daily_df["high"],
            "low": daily_df["low"],
            "close": daily_df["close"],
            "volume": daily_df["vol"],
            "amount": daily_df["amount"],
            "adjust_type": "qfq",
            "source": "tushare",
            "updated_at": now,
        }
    )
    w = pd.DataFrame(
        {
            "ts_code": ts_code,
            "freq": "1w",
            "trade_date": weekly_df["trade_date"].dt.strftime("%Y%m%d"),
            "trade_time": weekly_df["trade_date"].dt.strftime("%Y-%m-%d 15:00:00"),
            "open": weekly_df["open"],
            "high": weekly_df["high"],
            "low": weekly_df["low"],
            "close": weekly_df["close"],
            "volume": weekly_df["vol"],
            "amount": weekly_df["amount"],
            "adjust_type": "qfq",
            "source": "tushare",
            "updated_at": now,
        }
    )
    frames = [d, w]
    snap_file = SNAP_DIR / f"{ts_code}_bars_snapshot.csv"
    if snap_file.exists():
        old = pd.read_csv(snap_file, encoding="utf-8-sig")
        m = old[old["freq"] == "5m"].copy()
        if not m.empty:
            m["updated_at"] = now
            frames.append(m)
    new_snap = pd.concat(frames, ignore_index=True)
    new_snap.to_csv(snap_file, index=False, encoding="utf-8-sig")
    return snap_file


def find_affected_files(target_code: str | None) -> list[Path]:
    files = sorted(DAILY_QFQ_DIR.glob("*_qfq_*.csv"))
    out: list[Path] = []
    for f in files:
        if target_code and not f.name.startswith(f"{target_code}_qfq_"):
            continue
        df = pd.read_csv(f, usecols=["close"])
        if int(df["close"].isna().sum()) > 0:
            out.append(f)
    return out


def parse_start_end_from_name(path: Path) -> tuple[str, str]:
    m = re.search(r"_qfq_(\d{8})_(\d{8})\.csv$", path.name)
    if not m:
        return "19900101", datetime.now().strftime("%Y%m%d")
    return m.group(1), m.group(2)


def main() -> None:
    args = parse_args()
    token = load_token()
    pro = ts.pro_api(token)

    affected = find_affected_files(args.ts_code)
    print(f"affected={len(affected)}")
    if not affected:
        return

    ok = 0
    fail = 0
    for i, f in enumerate(affected, start=1):
        ts_code = f.name.split("_qfq_")[0]
        start, _ = parse_start_end_from_name(f)
        try:
            # 用最新交易日快照确定截止日期
            latest_daily = sorted((APP_DATA / "daily_history").glob("daily_*.csv"))
            end = latest_daily[-1].stem.split("_")[-1] if latest_daily else datetime.now().strftime("%Y%m%d")

            raw = chunked_qfq_download(pro, ts_code, start, end)
            daily_df = normalize_daily(raw)
            weekly_df = build_weekly(daily_df)

            save_daily(ts_code, daily_df)
            save_weekly(ts_code, weekly_df)
            rewrite_snapshot(ts_code, daily_df, weekly_df)

            nulls = int(daily_df["close"].isna().sum())
            print(f"[{i}/{len(affected)}] {ts_code}: ok, null_close={nulls}, rows={len(daily_df)}")
            ok += 1
        except Exception as e:
            print(f"[{i}/{len(affected)}] {ts_code}: failed: {e}")
            fail += 1

    print(f"done ok={ok} failed={fail}")


if __name__ == "__main__":
    main()
