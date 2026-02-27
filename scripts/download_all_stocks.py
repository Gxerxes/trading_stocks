"""
下载全市场股票基础信息并保存CSV
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import validate_config, DATA_DIR  # noqa: E402
from tushare_api.downloader import TushareDownloader  # noqa: E402


def main() -> None:
    validate_config()
    downloader = TushareDownloader()
    df = downloader.get_all_stock_basic()
    if df is None or df.empty:
        raise RuntimeError("未获取到股票基础信息")

    output_file = DATA_DIR / "all_stocks.csv"
    saved = downloader.save_stock_basic_csv(df, output_file)
    print(saved)


if __name__ == "__main__":
    main()
