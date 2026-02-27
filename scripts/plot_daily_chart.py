"""
统一样式绘制股票日线图

用法示例:
python scripts/plot_daily_chart.py --ts-code 600030.SH
python scripts/plot_daily_chart.py --csv ai_stock_agent/data/daily/600030.SH_qfq_20030106_20260226.csv
python scripts/plot_daily_chart.py --ts-code 600030.SH --output report/charts/600030_custom.png
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from report.chart_plotter import DailyChartPlotter  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="绘制日线走势图（统一样式）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ts-code", type=str, help="股票代码，如 600030.SH")
    group.add_argument("--csv", type=str, help="日线CSV路径")
    parser.add_argument("--output", type=str, default=None, help="输出图片路径（可选）")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output) if args.output else None

    if args.csv:
        chart_path = DailyChartPlotter.plot_from_csv(Path(args.csv), output_path=output_path)
    else:
        chart_path = DailyChartPlotter.plot_from_ts_code(args.ts_code, output_path=output_path)

    print(chart_path)


if __name__ == "__main__":
    main()
