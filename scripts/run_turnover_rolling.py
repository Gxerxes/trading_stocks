"""
执行 5+20+60 换手率策略（单日或滚动区间）

示例：
python scripts/run_turnover_rolling.py --as-of-date 20260227
python scripts/run_turnover_rolling.py --start-date 20251201 --end-date 20260227
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import STRATEGY_SIGNAL_DIR, DAILY_HISTORY_DIR  # noqa: E402
from strategy.turnover_5_20_60_strategy import Turnover5260Strategy  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行5+20+60换手率策略")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--as-of-date", type=str, help="单日计算，格式YYYYMMDD")
    group.add_argument("--start-date", type=str, help="滚动开始日期，格式YYYYMMDD")
    parser.add_argument("--end-date", type=str, help="滚动结束日期，格式YYYYMMDD（配合--start-date）")
    parser.add_argument("--top-n", type=int, default=20, help="每个交易日保留前N只")
    parser.add_argument("--overwrite", action="store_true", help="是否覆盖已存在结果")
    return parser.parse_args()


def available_trade_dates() -> list[str]:
    files = sorted(DAILY_HISTORY_DIR.glob("daily_*.csv"))
    return [f.stem.split("_")[-1] for f in files]


def main() -> None:
    args = parse_args()
    strategy = Turnover5260Strategy(top_n=args.top_n)

    if args.as_of_date:
        dates = [args.as_of_date]
    else:
        if not args.end_date:
            raise ValueError("使用 --start-date 时必须提供 --end-date")
        dates = [d for d in available_trade_dates() if args.start_date <= d <= args.end_date]

    done, skipped, failed = [], [], []
    for d in dates:
        out_file = STRATEGY_SIGNAL_DIR / f"turnover_5_20_60_{d}.csv"
        if out_file.exists() and not args.overwrite:
            skipped.append(d)
            continue
        try:
            strategy.save(d, STRATEGY_SIGNAL_DIR)
            done.append(d)
        except Exception:
            failed.append(d)

    state = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dates_total": len(dates),
        "done": done,
        "skipped": skipped,
        "failed": failed,
        "top_n": args.top_n,
    }
    state_file = STRATEGY_SIGNAL_DIR / "turnover_5_20_60_state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"output_dir={STRATEGY_SIGNAL_DIR}")
    print(f"dates_total={len(dates)}")
    print(f"done={len(done)}")
    print(f"skipped={len(skipped)}")
    print(f"failed={len(failed)}")
    print(f"state_file={state_file}")


if __name__ == "__main__":
    main()
