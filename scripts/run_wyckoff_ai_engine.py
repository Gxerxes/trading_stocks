"""
运行 Wyckoff AI Engine，并导出训练与信号文件。

示例：
python scripts/run_wyckoff_ai_engine.py --ts-code 600030.SH
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from strategy.wyckoff_ai_engine import WyckoffAIEngine  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="运行 Wyckoff AI Engine")
    p.add_argument("--ts-code", type=str, default="600030.SH", help="股票代码")
    p.add_argument("--lake-root", type=str, default="ai_stock_agent/data/lake/bars", help="统一数据层根目录")
    p.add_argument("--out-dir", type=str, default="report/wyckoff_ai", help="输出目录")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    ts_code = args.ts_code.strip().upper()
    lake_root = Path(args.lake_root)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    engine = WyckoffAIEngine(lake_root=lake_root)
    result = engine.run(ts_code=ts_code)

    features_file = out_dir / f"{ts_code}_wyckoff_features.csv"
    phase_file = out_dir / f"{ts_code}_wyckoff_phase_signals.csv"
    latest_file = out_dir / f"{ts_code}_wyckoff_latest.json"
    train_file = out_dir / f"{ts_code}_wyckoff_train_dataset.csv"

    result.daily_features.to_csv(features_file, index=False, encoding="utf-8-sig")
    result.phase_signals.to_csv(phase_file, index=False, encoding="utf-8-sig")

    # 训练数据：去除标签缺失尾部区间
    train_df = result.phase_signals.dropna(subset=["future_return_10d"]).copy()
    train_df.to_csv(train_file, index=False, encoding="utf-8-sig")

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(result.latest_assessment, f, ensure_ascii=False, indent=2)

    print(f"features={features_file}")
    print(f"phase_signals={phase_file}")
    print(f"train_dataset={train_file}")
    print(f"latest={latest_file}")
    print("latest_assessment=")
    print(json.dumps(result.latest_assessment, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
