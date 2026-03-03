from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import REPORT_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--trade-date", type=str, default=None)
    p.add_argument("--all-stocks-file", type=str, default=str(Path(__file__).resolve().parents[1] / "ai_stock_agent" / "data" / "all_stocks_active.csv"))
    p.add_argument("--snapshot-dir", type=str, default=str(Path(__file__).resolve().parents[1] / "ai_stock_agent" / "data" / "lake" / "bars" / "snapshot"))
    p.add_argument("--out-dir", type=str, default=str(REPORT_DIR / "market_scan"))
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def latest_open_trade_date(pro: ts.pro_api) -> str:
    today = datetime.now().strftime("%Y%m%d")
    cal = pro.trade_cal(exchange="SSE", start_date="19900101", end_date=today, fields="cal_date,is_open")
    cal = cal[cal["is_open"] == 1].copy()
    if cal.empty:
        raise ValueError("未获取到交易日历")
    cal["cal_date"] = cal["cal_date"].astype(str)
    cal = cal.sort_values("cal_date")
    return cal["cal_date"].iloc[-1]


def normalize_limit_pct(ts_code: str) -> float:
    if ts_code.startswith(("300", "301", "688")):
        return 0.20
    return 0.10


def load_stock_day(snapshot_path: Path, trade_date: str) -> Optional[pd.DataFrame]:
    df = pd.read_csv(
        snapshot_path,
        encoding="utf-8-sig",
        usecols=["trade_date", "open", "high", "low", "close", "volume", "amount", "adjust_type"],
    )
    df["trade_date"] = df["trade_date"].astype(str)
    if trade_date not in set(df["trade_date"]):
        return None
    return df.sort_values("trade_date")


def infer_latest_trade_date(snapshot_dir: Path, ts_codes: list[str], sample_size: int = 50) -> Optional[str]:
    dates = []
    for ts_code in ts_codes[:sample_size]:
        snapshot_path = snapshot_dir / f"{ts_code}_bars_snapshot.csv"
        if not snapshot_path.exists():
            continue
        df = pd.read_csv(snapshot_path, encoding="utf-8-sig", usecols=["trade_date"])
        if df.empty:
            continue
        dates.append(str(df["trade_date"].iloc[-1]))
    return max(dates) if dates else None


def calc_limit_streak(df: pd.DataFrame, trade_date: str, limit_pct: float) -> int:
    df = df.sort_values("trade_date")
    df["trade_date"] = df["trade_date"].astype(str)
    idx = df.index[df["trade_date"] == trade_date]
    if len(idx) == 0:
        return 0
    i = idx[0]
    if i == df.index.min():
        return 0
    close = df["close"].astype(float)
    prev = close.shift(1)
    pct = close / prev.replace(0, np.nan) - 1.0
    limit_up = pct >= (limit_pct - 0.002)
    streak = 0
    pos = df.index.get_loc(i)
    while pos >= 0 and limit_up.iloc[pos]:
        streak += 1
        pos -= 1
    return streak


def main() -> None:
    args = parse_args()
    pro = build_pro()

    all_stocks = pd.read_csv(args.all_stocks_file, dtype={"ts_code": str})
    ts_codes = all_stocks["ts_code"].dropna().astype(str).tolist()

    snapshot_dir = Path(args.snapshot_dir)
    if args.trade_date:
        trade_date = args.trade_date
    else:
        trade_date = infer_latest_trade_date(snapshot_dir, ts_codes) or latest_open_trade_date(pro)
    rows = []

    for ts_code in ts_codes:
        snapshot_path = snapshot_dir / f"{ts_code}_bars_snapshot.csv"
        if not snapshot_path.exists():
            continue
        df = load_stock_day(snapshot_path, trade_date)
        if df is None or df.empty:
            continue
        day_row = df[df["trade_date"] == trade_date].iloc[-1]
        idx = df.index[df["trade_date"] == trade_date][0]
        if idx == df.index.min():
            prev_close = np.nan
        else:
            prev_close = df.loc[df.index[df.index.get_loc(idx) - 1], "close"]
        close = float(day_row["close"])
        high = float(day_row["high"])
        amount = float(day_row["amount"]) if not pd.isna(day_row["amount"]) else 0.0
        limit_pct = normalize_limit_pct(ts_code)
        if pd.isna(prev_close) or prev_close == 0:
            pct_chg = np.nan
        else:
            pct_chg = close / prev_close - 1.0
        limit_price = prev_close * (1.0 + limit_pct) if not pd.isna(prev_close) else np.nan
        is_limit_up = False if pd.isna(pct_chg) else pct_chg >= (limit_pct - 0.002)
        is_limit_down = False if pd.isna(pct_chg) else pct_chg <= (-limit_pct + 0.002)
        is_break = False
        if not pd.isna(limit_price):
            is_break = high >= limit_price * 0.999 and close < limit_price * 0.999 and close > prev_close
        streak = calc_limit_streak(df[["trade_date", "close"]].copy(), trade_date, limit_pct) if is_limit_up else 0
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": trade_date,
                "close": close,
                "prev_close": prev_close,
                "pct_chg": pct_chg,
                "amount": amount,
                "is_limit_up": int(is_limit_up),
                "is_limit_down": int(is_limit_down),
                "is_break": int(is_break),
                "limit_streak": streak,
            }
        )

    price_df = pd.DataFrame(rows)
    if price_df.empty:
        raise ValueError("未获取到行情数据")

    try:
        daily_basic = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,trade_date,turnover_rate,turnover_rate_f,volume_ratio,total_mv,circ_mv",
        )
    except Exception:
        daily_basic = None
    if daily_basic is None or daily_basic.empty:
        daily_basic = pd.DataFrame(columns=["ts_code", "trade_date"])

    merged = price_df.merge(daily_basic, on=["ts_code", "trade_date"], how="left")

    up_count = int((merged["pct_chg"] > 0).sum())
    down_count = int((merged["pct_chg"] < 0).sum())
    limit_up_count = int(merged["is_limit_up"].sum())
    limit_down_count = int(merged["is_limit_down"].sum())
    break_count = int(merged["is_break"].sum())
    max_streak = int(merged["limit_streak"].max()) if not merged["limit_streak"].empty else 0
    total_amount = float(merged["amount"].sum())

    denom = limit_up_count + break_count
    break_rate = float(break_count / denom) if denom > 0 else 0.0

    avg_turnover = float(merged["turnover_rate"].mean()) if "turnover_rate" in merged else np.nan
    avg_volume_ratio = float(merged["volume_ratio"].mean()) if "volume_ratio" in merged else np.nan
    total_mv = float(merged["total_mv"].sum()) if "total_mv" in merged else np.nan
    circ_mv = float(merged["circ_mv"].sum()) if "circ_mv" in merged else np.nan

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"market_scan_{trade_date}.csv"
    merged.to_csv(csv_path, index=False, encoding="utf-8-sig")

    md_path = out_dir / f"market_scan_{trade_date}.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write(f"# 市场温度扫描 {trade_date}\n\n")
        f.write("## 核心统计\n")
        f.write(f"- 上涨家数: {up_count}\n")
        f.write(f"- 下跌家数: {down_count}\n")
        f.write(f"- 涨停数量: {limit_up_count}\n")
        f.write(f"- 跌停数量: {limit_down_count}\n")
        f.write(f"- 炸板率: {break_rate:.2%}\n")
        f.write(f"- 连板高度: {max_streak}\n")
        f.write(f"- 成交额合计: {total_amount:.2f}\n")
        if not np.isnan(avg_turnover):
            f.write(f"- 平均换手率: {avg_turnover:.4f}\n")
        if not np.isnan(avg_volume_ratio):
            f.write(f"- 平均量比: {avg_volume_ratio:.4f}\n")
        if not np.isnan(total_mv):
            f.write(f"- 总市值合计(万元): {total_mv:.2f}\n")
        if not np.isnan(circ_mv):
            f.write(f"- 流通市值合计(万元): {circ_mv:.2f}\n")

    print(f"trade_date={trade_date}")
    print(f"csv_file={csv_path}")
    print(f"md_file={md_path}")


if __name__ == "__main__":
    main()
