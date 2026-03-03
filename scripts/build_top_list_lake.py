from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--start-date", type=str, default="20050101")
    p.add_argument("--end-date", type=str, default=None)
    p.add_argument("--sleep-seconds", type=float, default=0.2)
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "top_list"))
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def get_open_trade_dates(pro: ts.pro_api, start_date: str, end_date: str) -> list[str]:
    cal = pro.trade_cal(
        exchange="SSE",
        start_date=start_date,
        end_date=end_date,
        fields="cal_date,is_open",
    )
    if cal is None or cal.empty:
        return []
    opens = cal[cal["is_open"] == 1]["cal_date"].astype(str).tolist()
    return opens


def save_top_list(df: pd.DataFrame, out_dir: Path, trade_date: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"top_list_{trade_date}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out


def main() -> None:
    args = parse_args()
    end_date = args.end_date or datetime.now().strftime("%Y%m%d")
    pro = build_pro()
    out_dir = Path(args.out_dir) / "top_list"
    dates = get_open_trade_dates(pro, args.start_date, end_date)
    if not dates:
        raise RuntimeError("未获取到交易日列表")

    ok = 0
    skipped = 0
    failed = 0
    for trade_date in dates:
        out_file = out_dir / f"top_list_{trade_date}.csv"
        if out_file.exists() and not args.force:
            skipped += 1
            continue
        try:
            df = pro.top_list(trade_date=trade_date)
            if df is None or df.empty:
                failed += 1
                print(f"{trade_date}: empty")
            else:
                save_top_list(df, out_dir, trade_date)
                ok += 1
                print(f"{trade_date}: ok rows={len(df)}")
        except Exception as e:
            failed += 1
            print(f"{trade_date}: failed error={e}")
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    print(
        f"summary start={args.start_date} end={end_date} "
        f"ok={ok} skipped={skipped} failed={failed} total={len(dates)}"
    )


if __name__ == "__main__":
    main()
