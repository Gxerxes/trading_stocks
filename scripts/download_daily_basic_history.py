"""
分步下载全市场历史 daily_basic 快照（按交易日）

示例：
python scripts/download_daily_basic_history.py --start-date 20260201 --end-date 20260228
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import validate_config, DAILY_BASIC_HISTORY_DIR  # noqa: E402
from tushare_api.downloader import TushareDownloader  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按交易日下载全市场 daily_basic 历史数据")
    parser.add_argument("--start-date", required=True, help="开始日期 YYYYMMDD")
    parser.add_argument("--end-date", required=True, help="结束日期 YYYYMMDD")
    parser.add_argument(
        "--output-dir",
        default=str(DAILY_BASIC_HISTORY_DIR),
        help="输出目录（默认 ai_stock_agent/data/daily_basic_history）",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.2,
        help="每个交易日请求间隔秒数，避免限流",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    validate_config()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_file = output_dir / "download_state.json"

    downloader = TushareDownloader()
    trade_dates = downloader.get_open_trade_dates(args.start_date, args.end_date)
    if not trade_dates:
        raise RuntimeError(f"区间内无交易日: {args.start_date}~{args.end_date}")

    done = []
    skipped = []
    failed = []
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for trade_date in trade_dates:
        output_file = output_dir / f"daily_basic_{trade_date}.csv"
        if output_file.exists():
            skipped.append(trade_date)
            continue

        try:
            df = downloader.get_daily_basic(trade_date)
            if df is None or df.empty:
                failed.append(trade_date)
                continue

            downloader.save_daily_basic_csv(df, output_file)
            done.append(trade_date)
            time.sleep(max(0.0, args.sleep_seconds))
        except Exception:
            failed.append(trade_date)

    state = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "started_at": started_at,
        "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_trade_dates": len(trade_dates),
        "downloaded": done,
        "skipped_existing": skipped,
        "failed": failed,
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output_dir={output_dir}")
    print(f"total_trade_dates={len(trade_dates)}")
    print(f"downloaded={len(done)}")
    print(f"skipped_existing={len(skipped)}")
    print(f"failed={len(failed)}")
    print(f"state_file={state_file}")


if __name__ == "__main__":
    main()
