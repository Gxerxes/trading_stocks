from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys
import time
from typing import Optional

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--trade-date", type=str, default="20260302")
    p.add_argument("--all-stocks-file", type=str, default=str(Path(__file__).resolve().parents[1] / "ai_stock_agent" / "data" / "all_stocks_active.csv"))
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "daily_qfq"))
    p.add_argument("--sleep-seconds", type=float, default=0.15)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--resume", action="store_true")
    return p.parse_args()


def prepare_token() -> None:
    validate_config()
    if TUSHARE_TOKEN:
        import os

        os.environ["TUSHARE_TOKEN"] = TUSHARE_TOKEN


def fetch_qfq(ts_code: str, trade_date: str) -> Optional[pd.DataFrame]:
    df = ts.pro_bar(
        ts_code=ts_code,
        adj="qfq",
        start_date=trade_date,
        end_date=trade_date,
        freq="D",
        asset="E",
    )
    if df is None or df.empty:
        return None
    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str)
    return df


def main() -> None:
    args = parse_args()
    prepare_token()

    trade_date = args.trade_date
    all_stocks = pd.read_csv(args.all_stocks_file, dtype={"ts_code": str})
    ts_codes = all_stocks["ts_code"].dropna().astype(str).tolist()
    if args.limit:
        ts_codes = ts_codes[: int(args.limit)]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"daily_qfq_{trade_date}.csv"
    err_path = out_dir / f"daily_qfq_{trade_date}_errors.csv"

    header_written = out_path.exists()
    completed = set()
    if args.resume and out_path.exists():
        try:
            done_df = pd.read_csv(out_path, usecols=["ts_code"], dtype={"ts_code": str})
            completed = set(done_df["ts_code"].dropna().astype(str).tolist())
        except Exception:
            completed = set()
    err_rows = []

    for i, ts_code in enumerate(ts_codes, start=1):
        if completed and ts_code in completed:
            continue
        try:
            df = fetch_qfq(ts_code, trade_date)
            if df is None or df.empty:
                continue
            df = df.reset_index(drop=True)
            df.to_csv(out_path, mode="a", index=False, header=not header_written, encoding="utf-8-sig")
            header_written = True
        except Exception as e:
            err_rows.append({"ts_code": ts_code, "error": str(e)})

        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

        if i % 200 == 0:
            print(f"processed={i} total={len(ts_codes)}")

    if err_rows:
        pd.DataFrame(err_rows).to_csv(err_path, index=False, encoding="utf-8-sig")

    print(f"trade_date={trade_date}")
    print(f"out_file={out_path}")
    if err_rows:
        print(f"errors_file={err_path}")


if __name__ == "__main__":
    main()
