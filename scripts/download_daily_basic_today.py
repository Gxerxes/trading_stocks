"""
下载今日（或最近交易日）股票指标 daily_basic 并保存CSV
"""

from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import validate_config, DATA_DIR  # noqa: E402
from tushare_api.downloader import TushareDownloader  # noqa: E402


def main() -> None:
    validate_config()
    downloader = TushareDownloader()

    today = datetime.now().strftime("%Y%m%d")
    df = downloader.get_daily_basic(today)
    trade_date = today

    if df is None or df.empty:
        df, trade_date = downloader.get_latest_daily_basic(today)

    if df is None or df.empty or not trade_date:
        raise RuntimeError("未获取到今日或最近交易日 daily_basic 数据")

    out_file = DATA_DIR / f"daily_basic_{trade_date}.csv"
    saved = downloader.save_daily_basic_csv(df, out_file)
    print(saved)
    print(f"rows={len(df)}")
    print(f"trade_date={trade_date}")


if __name__ == "__main__":
    main()
