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
    p.add_argument("--start-date", type=str, default="19900101")
    p.add_argument("--end-date", type=str, default=None)
    p.add_argument("--sleep-seconds", type=float, default=0.12)
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


def fetch_in_windows(
    fn: Callable[..., pd.DataFrame],
    params_base: dict[str, str],
    start_date: str,
    end_date: str,
    window_days: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    frames: list[pd.DataFrame] = []
    cur = start
    while cur <= end:
        nxt = min(end, cur + timedelta(days=window_days - 1))
        params = dict(params_base)
        params["start_date"] = cur.strftime("%Y%m%d")
        params["end_date"] = nxt.strftime("%Y%m%d")
        df = fn(**params)
        if df is not None and not df.empty:
            frames.append(df)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        cur = nxt + timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


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


def main() -> None:
    args = parse_args()
    pro = build_pro()

    end_date = args.end_date or datetime.now().strftime("%Y%m%d")
    ts_code = normalize_etf_code(args.ts_code)
    safe = ts_code.replace(".", "_")
    out_root = Path(args.out_dir) / safe

    out_dir = out_root / "fund_daily"
    out_file = out_dir / f"fund_daily_{safe}_{datetime.now().strftime('%Y%m%d')}.csv"
    if out_file.exists() and not args.force:
        print(f"fund_daily: skipped file={out_file}")
        print(f"ts_code={ts_code} ok=1 total=1 out_root={out_root}")
        return

    df = fetch_in_windows(
        pro.fund_daily,
        {"ts_code": ts_code},
        args.start_date,
        end_date,
        window_days=365 * 3,
        sleep_seconds=args.sleep_seconds,
    )
    if not df.empty and "trade_date" in df.columns:
        df = df.drop_duplicates(subset=["ts_code", "trade_date"]).sort_values(["trade_date"])
    saved = save_latest(df, out_dir, "fund_daily", safe)
    if saved is None:
        print("fund_daily: failed error=无数据")
        print(f"ts_code={ts_code} ok=0 total=1 out_root={out_root}")
        return
    print(f"fund_daily: ok file={saved}")
    print(f"ts_code={ts_code} ok=1 total=1 out_root={out_root}")


if __name__ == "__main__":
    main()

