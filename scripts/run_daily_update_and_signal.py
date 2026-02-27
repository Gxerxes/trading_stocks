"""
日更一键脚本：
1) 下载当日（或最近交易日）daily快照
2) 下载当日（或最近交易日）daily_basic快照
3) 运行 5+20+60 策略并输出信号

示例：
python scripts/run_daily_update_and_signal.py
python scripts/run_daily_update_and_signal.py --trade-date 20260227
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import (  # noqa: E402
    DAILY_BASIC_HISTORY_DIR,
    DAILY_HISTORY_DIR,
    STRATEGY_SIGNAL_DIR,
    validate_config,
)
from strategy.turnover_5_20_60_strategy import Turnover5260Strategy  # noqa: E402
from tushare_api.downloader import TushareDownloader  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载当日数据并生成策略信号")
    parser.add_argument(
        "--trade-date",
        type=str,
        default=None,
        help="指定交易日 YYYYMMDD，不传则自动使用今天/最近交易日",
    )
    parser.add_argument("--top-n", type=int, default=20, help="策略输出前N只")
    return parser.parse_args()


def resolve_trade_date(downloader: TushareDownloader, trade_date: str | None) -> str:
    if trade_date:
        return trade_date

    today = datetime.now().strftime("%Y%m%d")
    open_days = downloader.get_open_trade_dates(today, today)
    if open_days:
        return today

    recent = downloader.get_open_trade_dates(
        (datetime.now().replace(day=1)).strftime("%Y%m%d"),
        today,
    )
    if not recent:
        raise RuntimeError("未获取到最近交易日")
    return recent[-1]


def main() -> None:
    args = parse_args()
    validate_config()

    downloader = TushareDownloader()
    trade_date = resolve_trade_date(downloader, args.trade_date)

    daily_df = downloader.get_daily_snapshot(trade_date)
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"未获取到 daily 数据: {trade_date}")
    daily_file = downloader.save_daily_snapshot_csv(
        daily_df,
        trade_date,
        output_dir=DAILY_HISTORY_DIR,
    )

    daily_basic_df = downloader.get_daily_basic(trade_date)
    if daily_basic_df is None or daily_basic_df.empty:
        raise RuntimeError(f"未获取到 daily_basic 数据: {trade_date}")
    daily_basic_file = downloader.save_daily_basic_csv(
        daily_basic_df,
        DAILY_BASIC_HISTORY_DIR / f"daily_basic_{trade_date}.csv",
    )

    strategy = Turnover5260Strategy(top_n=args.top_n)
    signal_file = strategy.save(trade_date, STRATEGY_SIGNAL_DIR)

    print(f"trade_date={trade_date}")
    print(f"daily_file={daily_file}")
    print(f"daily_basic_file={daily_basic_file}")
    print(f"signal_file={signal_file}")


if __name__ == "__main__":
    main()
