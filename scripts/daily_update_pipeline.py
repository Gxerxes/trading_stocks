"""
股票数据每日更新总控脚本（统一前复权 qfq）。

数据源约定：
- 分钟线：BaoStock（adjustflag=2, qfq）
- 日线/周线：Tushare（pro_bar, adj='qfq'）

输出：
- qfq日线：ai_stock_agent/data/stock_daily_qfq/
- qfq周线：ai_stock_agent/data/weekly_data_qfq/
- 分钟线：ai_stock_agent/data/minute_baostock/
- 全市场快照：daily_history / daily_basic_history（当日）
- 统一数据层：ai_stock_agent/data/lake/bars/
- 状态文件：ai_stock_agent/data/pipeline_state/daily_update_state.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import baostock as bs
import pandas as pd
import tushare as ts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DATA = PROJECT_ROOT / "ai_stock_agent" / "data"

STOCK_POOL_DEFAULT = APP_DATA / "stock_pool.json"
DAILY_QFQ_DIR = APP_DATA / "stock_daily_qfq"
WEEKLY_QFQ_DIR = APP_DATA / "weekly_data_qfq"
MINUTE_DIR = APP_DATA / "minute_baostock"
DAILY_HISTORY_DIR = APP_DATA / "daily_history"
DAILY_BASIC_HISTORY_DIR = APP_DATA / "daily_basic_history"
LAKE_BARS_DIR = APP_DATA / "lake" / "bars"
PIPELINE_STATE_DIR = APP_DATA / "pipeline_state"
PIPELINE_STATE_FILE = PIPELINE_STATE_DIR / "daily_update_state.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="每日更新 qfq 股票数据并入统一数据层")
    p.add_argument("--stock-pool", type=str, default=str(STOCK_POOL_DEFAULT), help="stock_pool.json 路径")
    p.add_argument("--run-date", type=str, default=None, help="运行日期 YYYYMMDD，默认今天")
    p.add_argument("--minute-frequency", type=str, default="5", choices=["5", "15", "30", "60"], help="分钟周期")
    p.add_argument("--skip-minute", action="store_true", help="跳过分钟线更新")
    p.add_argument("--skip-lake", action="store_true", help="跳过统一数据层写入")
    p.add_argument("--max-stocks", type=int, default=None, help="仅处理前N只股票（调试）")
    p.add_argument("--initial-start-date", type=str, default="19900101", help="首次无本地数据时起始日期")
    p.add_argument("--sleep-seconds", type=float, default=0.08, help="每只股票请求间隔秒数")
    return p.parse_args()


def load_token() -> str:
    env_file = PROJECT_ROOT / ".env"
    token = None
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("TUSHARE_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        import os

        token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN，请检查 .env 或环境变量")
    return token


def load_stock_pool(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stocks = data.get("stocks", [])
    if not isinstance(stocks, list) or not stocks:
        raise ValueError(f"股票池为空: {path}")
    return [str(x).strip().upper() for x in stocks if str(x).strip()]


def get_latest_open_trade_date(pro, run_date: str) -> str:
    start = (datetime.strptime(run_date, "%Y%m%d") - timedelta(days=20)).strftime("%Y%m%d")
    cal = pro.trade_cal(
        exchange="SSE",
        start_date=start,
        end_date=run_date,
        fields="cal_date,is_open",
    )
    if cal is None or cal.empty:
        raise RuntimeError(f"无法获取交易日历: {start}~{run_date}")
    opens = cal[cal["is_open"] == 1]["cal_date"].astype(str).sort_values().tolist()
    if not opens:
        raise RuntimeError(f"区间无开市日: {start}~{run_date}")
    return opens[-1]


def parse_trade_date_series(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.replace(".0", "", regex=False)
    parsed = pd.to_datetime(s, format="%Y%m%d", errors="coerce")
    miss = parsed.isna()
    if miss.any():
        parsed.loc[miss] = pd.to_datetime(s.loc[miss], errors="coerce")
    return parsed


def normalize_daily_qfq(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    out = df[cols].copy()
    out["trade_date"] = parse_trade_date_series(out["trade_date"])
    out = out.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    for c in ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def find_latest_qfq_file(ts_code: str, root: Path, kind: str) -> Optional[Path]:
    pat = f"{ts_code}_qfq_*.csv" if kind == "daily" else f"{ts_code}_qfq_w_*.csv"
    files = sorted(root.glob(pat))
    if not files:
        return None
    return files[-1]


def save_qfq_daily(ts_code: str, df: pd.DataFrame) -> Path:
    DAILY_QFQ_DIR.mkdir(parents=True, exist_ok=True)
    start = df["trade_date"].min().strftime("%Y%m%d")
    end = df["trade_date"].max().strftime("%Y%m%d")
    out = DAILY_QFQ_DIR / f"{ts_code}_qfq_{start}_{end}.csv"
    save = df.copy()
    save["trade_date"] = save["trade_date"].dt.strftime("%Y%m%d")
    save.to_csv(out, index=False, encoding="utf-8-sig")
    for old in DAILY_QFQ_DIR.glob(f"{ts_code}_qfq_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def build_weekly_from_daily_qfq(ts_code: str, daily_df: pd.DataFrame) -> pd.DataFrame:
    work = daily_df.copy().sort_values("trade_date").reset_index(drop=True)
    week = work["trade_date"].dt.to_period("W-FRI")
    w = (
        work.groupby(week, as_index=False)
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


def save_qfq_weekly(ts_code: str, weekly_df: pd.DataFrame) -> Path:
    WEEKLY_QFQ_DIR.mkdir(parents=True, exist_ok=True)
    start = weekly_df["trade_date"].min().strftime("%Y%m%d")
    end = weekly_df["trade_date"].max().strftime("%Y%m%d")
    out = WEEKLY_QFQ_DIR / f"{ts_code}_qfq_w_{start}_{end}.csv"
    save = weekly_df.copy()
    save["trade_date"] = save["trade_date"].dt.strftime("%Y%m%d")
    save.to_csv(out, index=False, encoding="utf-8-sig")
    for old in WEEKLY_QFQ_DIR.glob(f"{ts_code}_qfq_w_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def normalize_baostock_code(ts_code: str) -> str:
    code, market = ts_code.split(".")
    return ("sh." if market == "SH" else "sz.") + code


def download_minute_qfq_for_date(ts_code: str, trade_date: str, freq: str) -> Optional[Path]:
    MINUTE_DIR.mkdir(parents=True, exist_ok=True)
    bs_code = normalize_baostock_code(ts_code)
    date_dash = datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d")

    rs = bs.query_history_k_data_plus(
        code=bs_code,
        fields="date,time,code,open,high,low,close,volume,amount,adjustflag",
        start_date=date_dash,
        end_date=date_dash,
        frequency=freq,
        adjustflag="2",
    )
    if rs.error_code != "0":
        return None

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return None

    df = pd.DataFrame(rows, columns=rs.fields)
    out = MINUTE_DIR / f"{bs_code.replace('.', '_')}_{date_dash}_{date_dash}_{freq}m_adj2.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out


def write_lake(ts_code: str, minute_csv: Optional[Path], daily_df: pd.DataFrame, weekly_df: pd.DataFrame) -> list[Path]:
    out_files: list[Path] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def write_one(frame: pd.DataFrame, freq: str) -> Path:
        p = LAKE_BARS_DIR / f"freq={freq}" / f"ts_code={ts_code}"
        p.mkdir(parents=True, exist_ok=True)
        f = p / f"{ts_code}_{freq}_{frame['trade_date'].min()}_{frame['trade_date'].max()}.parquet"
        frame.to_parquet(f, index=False)
        # 只保留最新时间范围文件，避免旧分区文件累积
        for old in p.glob(f"{ts_code}_{freq}_*.parquet"):
            if old != f:
                old.unlink(missing_ok=True)
        return f

    d = pd.DataFrame(index=daily_df.index)
    d["ts_code"] = ts_code
    d["freq"] = "1d"
    d["trade_date"] = daily_df["trade_date"].dt.strftime("%Y%m%d")
    d["trade_time"] = daily_df["trade_date"].dt.strftime("%Y-%m-%d 15:00:00")
    d["open"] = daily_df["open"]
    d["high"] = daily_df["high"]
    d["low"] = daily_df["low"]
    d["close"] = daily_df["close"]
    d["volume"] = daily_df["vol"]
    d["amount"] = daily_df["amount"]
    d["adjust_type"] = "qfq"
    d["source"] = "tushare"
    d["updated_at"] = now
    out_files.append(write_one(d, "1d"))

    w = pd.DataFrame(index=weekly_df.index)
    w["ts_code"] = ts_code
    w["freq"] = "1w"
    w["trade_date"] = weekly_df["trade_date"].dt.strftime("%Y%m%d")
    w["trade_time"] = weekly_df["trade_date"].dt.strftime("%Y-%m-%d 15:00:00")
    w["open"] = weekly_df["open"]
    w["high"] = weekly_df["high"]
    w["low"] = weekly_df["low"]
    w["close"] = weekly_df["close"]
    w["volume"] = weekly_df["vol"]
    w["amount"] = weekly_df["amount"]
    w["adjust_type"] = "qfq"
    w["source"] = "tushare"
    w["updated_at"] = now
    out_files.append(write_one(w, "1w"))

    m = None
    if minute_csv and minute_csv.exists():
        mraw = pd.read_csv(minute_csv, encoding="utf-8-sig")
        if not mraw.empty:
            m = pd.DataFrame(index=mraw.index)
            m["ts_code"] = ts_code
            m["freq"] = "5m"
            m["trade_date"] = pd.to_datetime(mraw["date"]).dt.strftime("%Y%m%d")
            m["trade_time"] = pd.to_datetime(mraw["time"].astype(str).str[:14], format="%Y%m%d%H%M%S").dt.strftime("%Y-%m-%d %H:%M:%S")
            for c in ["open", "high", "low", "close", "volume", "amount"]:
                m[c] = pd.to_numeric(mraw[c], errors="coerce")
            m["adjust_type"] = "qfq"
            m["source"] = "baostock"
            m["updated_at"] = now
            out_files.append(write_one(m, "5m"))

    # 快照
    snap_dir = LAKE_BARS_DIR / "snapshot"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_frames = [d, w]
    if m is not None:
        snap_frames.append(m)
    snap = pd.concat(snap_frames, ignore_index=True)
    snap.to_csv(snap_dir / f"{ts_code}_bars_snapshot.csv", index=False, encoding="utf-8-sig")
    return out_files


def save_daily_snapshots(pro, trade_date: str) -> tuple[Optional[Path], Optional[Path]]:
    DAILY_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    DAILY_BASIC_HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    daily_file = DAILY_HISTORY_DIR / f"daily_{trade_date}.csv"
    basic_file = DAILY_BASIC_HISTORY_DIR / f"daily_basic_{trade_date}.csv"

    if not daily_file.exists():
        df = pro.daily(
            trade_date=trade_date,
            fields="ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
        )
        if df is not None and not df.empty:
            df.to_csv(daily_file, index=False, encoding="utf-8-sig")

    if not basic_file.exists():
        bf = pro.daily_basic(
            trade_date=trade_date,
            fields="ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv",
        )
        if bf is not None and not bf.empty:
            bf.to_csv(basic_file, index=False, encoding="utf-8-sig")

    return (daily_file if daily_file.exists() else None, basic_file if basic_file.exists() else None)


def main() -> None:
    args = parse_args()
    token = load_token()
    pro = ts.pro_api(token)

    run_date = args.run_date or datetime.now().strftime("%Y%m%d")
    latest_trade_date = get_latest_open_trade_date(pro, run_date)

    stocks = load_stock_pool(Path(args.stock_pool))
    if args.max_stocks:
        stocks = stocks[: args.max_stocks]

    PIPELINE_STATE_DIR.mkdir(parents=True, exist_ok=True)
    state: dict = {
        "run_date": run_date,
        "latest_trade_date": latest_trade_date,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_stocks": len(stocks),
        "stocks": [],
    }

    # 全市场当日快照
    daily_snap, basic_snap = save_daily_snapshots(pro, latest_trade_date)
    state["daily_snapshot"] = str(daily_snap) if daily_snap else None
    state["daily_basic_snapshot"] = str(basic_snap) if basic_snap else None

    # 分钟线登录一次
    bs_ok = False
    if not args.skip_minute:
        lg = bs.login()
        bs_ok = lg.error_code == "0"
        state["baostock_login"] = {"error_code": lg.error_code, "error_msg": lg.error_msg}

    try:
        for i, ts_code in enumerate(stocks, start=1):
            item = {"ts_code": ts_code, "status": "ok"}
            try:
                latest_file = find_latest_qfq_file(ts_code, DAILY_QFQ_DIR, kind="daily")
                if latest_file and latest_file.exists():
                    old_df = pd.read_csv(latest_file, encoding="utf-8-sig")
                    old_df = normalize_daily_qfq(old_df)
                    if old_df.empty:
                        start_date = args.initial_start_date
                    else:
                        start_date = (old_df["trade_date"].max() + timedelta(days=1)).strftime("%Y%m%d")
                else:
                    old_df = None
                    start_date = args.initial_start_date

                new_df = pro_bar_qfq(pro, ts_code, start_date, latest_trade_date)
                if new_df is None or new_df.empty:
                    merged = old_df if old_df is not None else pd.DataFrame(columns=["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"])
                else:
                    new_norm = normalize_daily_qfq(new_df)
                    if old_df is not None and not old_df.empty:
                        merged = pd.concat([old_df, new_norm], ignore_index=True)
                        merged = merged.drop_duplicates(subset=["trade_date"], keep="last").sort_values("trade_date").reset_index(drop=True)
                    else:
                        merged = new_norm

                if merged.empty:
                    item["status"] = "no_data"
                    state["stocks"].append(item)
                    continue

                daily_file = save_qfq_daily(ts_code, merged)
                weekly_df = build_weekly_from_daily_qfq(ts_code, merged)
                weekly_file = save_qfq_weekly(ts_code, weekly_df)
                item["daily_file"] = str(daily_file)
                item["weekly_file"] = str(weekly_file)

                minute_file = None
                if (not args.skip_minute) and bs_ok:
                    minute_file = download_minute_qfq_for_date(ts_code, latest_trade_date, args.minute_frequency)
                    item["minute_file"] = str(minute_file) if minute_file else None

                if not args.skip_lake:
                    lake_files = write_lake(ts_code, minute_file, merged, weekly_df)
                    item["lake_files"] = [str(x) for x in lake_files]

                if args.sleep_seconds > 0:
                    import time

                    time.sleep(args.sleep_seconds)
            except Exception as e:
                item["status"] = "failed"
                item["error"] = str(e)
            state["stocks"].append(item)
            print(f"[{i}/{len(stocks)}] {ts_code}: {item['status']}")
    finally:
        if not args.skip_minute and bs_ok:
            bs.logout()

    state["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok = sum(1 for x in state["stocks"] if x.get("status") == "ok")
    fail = sum(1 for x in state["stocks"] if x.get("status") == "failed")
    state["summary"] = {"ok": ok, "failed": fail}

    PIPELINE_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"latest_trade_date={latest_trade_date}")
    print(f"ok={ok} failed={fail}")
    print(f"state_file={PIPELINE_STATE_FILE}")


def pro_bar_qfq(pro, ts_code: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    分段下载 qfq 日线，规避长区间请求时早期 OHLC 为空的问题。
    """
    s = datetime.strptime(start_date, "%Y%m%d")
    e = datetime.strptime(end_date, "%Y%m%d")
    if s > e:
        return None

    frames: list[pd.DataFrame] = []
    cursor = s
    # 两年一个分段，降低单次查询过长导致的数据空洞风险
    chunk_days = 730
    last_err = None

    while cursor <= e:
        chunk_end = min(cursor + timedelta(days=chunk_days - 1), e)
        cs = cursor.strftime("%Y%m%d")
        ce = chunk_end.strftime("%Y%m%d")

        got = None
        for _ in range(3):
            try:
                got = ts.pro_bar(
                    ts_code=ts_code,
                    adj="qfq",
                    start_date=cs,
                    end_date=ce,
                    asset="E",
                    adjfactor=False,
                    api=pro,
                )
                break
            except Exception as e1:
                last_err = e1

        if got is not None and not got.empty:
            frames.append(got)

        cursor = chunk_end + timedelta(days=1)

    if not frames:
        if last_err:
            raise RuntimeError(f"pro_bar_qfq failed: {last_err}")
        return None

    out = pd.concat(frames, ignore_index=True)
    if "trade_date" in out.columns:
        out["trade_date"] = out["trade_date"].astype(str)
        out = out.drop_duplicates(subset=["trade_date"], keep="last")
    out = out.sort_values("trade_date").reset_index(drop=True)
    return out


if __name__ == "__main__":
    main()
