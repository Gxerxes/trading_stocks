"""
生成资金扩散突破高胜率版策略信号
"""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from strategy.capital_diffusion_3_5d_high_win_strategy import CapitalDiffusion35DHighWinStrategy  # noqa: E402


def parse_args():
    p = argparse.ArgumentParser(description="运行资金扩散突破高胜率版策略信号")
    p.add_argument("--as-of-date", required=True, help="信号日期 YYYYMMDD")
    p.add_argument("--top-n", type=int, default=20, help="输出前N只")
    return p.parse_args()


def main():
    args = parse_args()
    strategy = CapitalDiffusion35DHighWinStrategy(top_n=args.top_n)
    out = strategy.save(args.as_of_date)
    print(out)


if __name__ == "__main__":
    main()
