from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time
from typing import Callable, Optional

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--ts-code", type=str, default="512880")
    p.add_argument("--freq", type=str, default="5min", choices=["1min", "5min", "15min", "30min", "60min"])
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--start-date", type=str, default=None)
    p.add_argument("--end-date", type=str, default=None)
    p.add_argument("--sleep-seconds", type=float, default=35.0)
    p.add_argument("--rate-limit-sleep", type=float, default=60.0)
    p.add_argument("--max-retries", type=int, default=5)
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "index" / "etf"))
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def normalize_etf_code(raw: str) -> str:
    code = raw.strip().upper()
    if not code:
        return code
    if "." in code:
        return code
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    if code.startswith(("0", "1", "3")):
        return f"{code}.SZ"
    return f"{code}.OF"


def save_latest(df: pd.DataFrame, out_dir: Path, file_prefix: str, tag: str) -> Optional[Path]:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    out = out_dir / f"{file_prefix}_{tag}_{date_tag}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    for old in out_dir.glob(f"{file_prefix}_{tag}_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def fetch_segment(
    fn: Callable[..., pd.DataFrame],
    ts_code: str,
    freq: str,
    start_dt: datetime,
    end_dt: datetime,
    rate_limit_sleep: float,
    max_retries: int,
) -> pd.DataFrame:
    params = {
        "ts_code": ts_code,
        "freq": freq,
        "start_date": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
    }
    attempt = 0
    while attempt <= max_retries:
        try:
            df = fn(**params)
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            msg = str(e)
            attempt += 1
            if "每分钟最多访问" in msg or "每小时最多访问" in msg or "最多访问该接口" in msg:
                time.sleep(rate_limit_sleep)
                continue
            if attempt > max_retries:
                raise
            time.sleep(rate_limit_sleep)
    return pd.DataFrame()

def fetch_range(
    fn: Callable[..., pd.DataFrame],
    ts_code: str,
    freq: str,
    start_dt: datetime,
    end_dt: datetime,
    sleep_seconds: float,
    rate_limit_sleep: float,
    max_retries: int,
) -> pd.DataFrame:
    df = fetch_segment(fn, ts_code, freq, start_dt, end_dt, rate_limit_sleep, max_retries)
    if df is None or df.empty:
        return pd.DataFrame()
    if len(df) < 7990:
        return df
    if (end_dt - start_dt).days <= 0:
        return df

    mid = start_dt + (end_dt - start_dt) / 2
    mid = mid.replace(second=0, microsecond=0)
    left_end = mid
    right_start = mid + timedelta(seconds=1)

    time.sleep(sleep_seconds)
    left = fetch_range(fn, ts_code, freq, start_dt, left_end, sleep_seconds, rate_limit_sleep, max_retries)
    time.sleep(sleep_seconds)
    right = fetch_range(fn, ts_code, freq, right_start, end_dt, sleep_seconds, rate_limit_sleep, max_retries)

    out = pd.concat([left, right], ignore_index=True) if not left.empty or not right.empty else pd.DataFrame()
    if {"ts_code", "trade_time"}.issubset(out.columns):
        out = out.drop_duplicates(subset=["ts_code", "trade_time"])
    if "trade_time" in out.columns:
        out["trade_time"] = pd.to_datetime(out["trade_time"], errors="coerce")
        out = out.sort_values("trade_time")
        out["trade_time"] = out["trade_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return out

def main() -> None:
    args = parse_args()
    pro = build_pro()

    ts_code = normalize_etf_code(args.ts_code)
    safe = ts_code.replace(".", "_")

    if args.end_date:
        end_dt = datetime.strptime(args.end_date, "%Y%m%d").replace(hour=19, minute=0, second=0, microsecond=0)
    else:
        end_dt = datetime.now().replace(hour=19, minute=0, second=0, microsecond=0)
    if args.start_date:
        start_dt = datetime.strptime(args.start_date, "%Y%m%d").replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        start_dt = (end_dt - timedelta(days=int(args.days))).replace(hour=9, minute=0, second=0, microsecond=0)

    out_root = Path(args.out_dir) / safe / "stk_mins" / f"freq={args.freq}"
    tag = f"{safe}_{args.freq}_{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}"

    if list(out_root.glob(f"stk_mins_{tag}_*.csv")) and not args.force:
        latest = sorted(out_root.glob(f"stk_mins_{tag}_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)[0]
        print(f"stk_mins: skipped file={latest}")
        print(f"ts_code={ts_code} ok=1 total=1 out_root={out_root}")
        return

    df = fetch_range(
        pro.stk_mins,
        ts_code,
        args.freq,
        start_dt,
        end_dt,
        sleep_seconds=float(args.sleep_seconds),
        rate_limit_sleep=float(args.rate_limit_sleep),
        max_retries=int(args.max_retries),
    )
    saved = save_latest(df, out_root, "stk_mins", tag)
    if saved is None:
        print("stk_mins: failed error=无数据")
        print(f"ts_code={ts_code} ok=0 total=1 out_root={out_root}")
        return
    print(f"stk_mins: ok file={saved}")
    print(f"ts_code={ts_code} ok=1 total=1 out_root={out_root}")


if __name__ == "__main__":
    main()
