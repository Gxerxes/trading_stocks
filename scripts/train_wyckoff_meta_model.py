"""
训练 Wyckoff Meta Model（无外部ML依赖版本）。

输入：
- run_wyckoff_ai_engine.py 生成的 phase_signals CSV

输出：
- 因子权重（IC导出）
- 当期打分与分层统计
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


FEATURE_COLS = [
    "accumulation_score",
    "trading_range_flag",
    "spring",
    "sos",
    "trend_slope_60",
    "volume_trend_20",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="训练 Wyckoff Meta Model（baseline）")
    p.add_argument(
        "--input-csv",
        type=str,
        default="report/wyckoff_ai/600030.SH_wyckoff_phase_signals.csv",
        help="phase signals CSV",
    )
    p.add_argument("--out-dir", type=str, default="report/wyckoff_ai", help="输出目录")
    p.add_argument("--target", type=str, default="future_return_10d", choices=["future_return_5d", "future_return_10d", "future_return_20d"], help="训练目标")
    return p.parse_args()


def robust_zscore(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    med = x.median()
    mad = (x - med).abs().median()
    if pd.isna(mad) or mad == 0:
        std = x.std(ddof=0)
        if pd.isna(std) or std == 0:
            return pd.Series(np.zeros(len(x)), index=x.index)
        return (x - x.mean()) / std
    return 0.6745 * (x - med) / mad


def main() -> None:
    args = parse_args()
    input_csv = Path(args.input_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    if args.target not in df.columns:
        raise ValueError(f"目标列不存在: {args.target}")

    work = df.copy()
    for c in FEATURE_COLS:
        if c not in work.columns:
            work[c] = np.nan
        work[c] = pd.to_numeric(work[c], errors="coerce")

    work = work.dropna(subset=[args.target]).copy()
    work[args.target] = pd.to_numeric(work[args.target], errors="coerce")
    work = work.dropna(subset=[args.target]).copy()

    if len(work) < 100:
        raise RuntimeError(f"有效训练样本不足: {len(work)}")

    # 1) 因子IC -> 权重（绝对值归一）
    ic = {}
    for c in FEATURE_COLS:
        x = work[c]
        valid = x.notna() & work[args.target].notna()
        if valid.sum() < 50:
            ic[c] = 0.0
            continue
        ic_val = x[valid].corr(work.loc[valid, args.target], method="pearson")
        ic[c] = 0.0 if pd.isna(ic_val) else float(ic_val)

    abs_sum = sum(abs(v) for v in ic.values()) or 1.0
    weights = {k: float(v / abs_sum) for k, v in ic.items()}

    # 2) 生成 meta_score
    score = pd.Series(0.0, index=work.index)
    for c in FEATURE_COLS:
        score += robust_zscore(work[c]).fillna(0.0) * weights[c]
    work["meta_score"] = score

    # 3) 分层统计（10分位）
    work["score_bucket"] = pd.qcut(work["meta_score"], 10, labels=False, duplicates="drop")
    bucket = (
        work.groupby("score_bucket", as_index=False)
        .agg(
            sample_count=(args.target, "count"),
            avg_return=(args.target, "mean"),
            win_rate=(args.target, lambda x: float((x > 0).mean())),
            spring_success_rate=("spring_success_10d", "mean") if "spring_success_10d" in work.columns else (args.target, lambda x: np.nan),
        )
        .sort_values("score_bucket")
    )

    # 4) 导出
    stem = input_csv.stem.replace("_wyckoff_phase_signals", "")
    score_file = out_dir / f"{stem}_wyckoff_meta_scored.csv"
    bucket_file = out_dir / f"{stem}_wyckoff_meta_bucket.csv"
    model_file = out_dir / f"{stem}_wyckoff_meta_model.json"

    work.to_csv(score_file, index=False, encoding="utf-8-sig")
    bucket.to_csv(bucket_file, index=False, encoding="utf-8-sig")
    with open(model_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "target": args.target,
                "n_samples": int(len(work)),
                "feature_ic": ic,
                "weights": weights,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"scored={score_file}")
    print(f"bucket={bucket_file}")
    print(f"model={model_file}")
    print("top_weights=")
    for k, v in sorted(weights.items(), key=lambda kv: abs(kv[1]), reverse=True):
        print(f"{k}: {v:.4f} (IC={ic[k]:.4f})")


if __name__ == "__main__":
    main()
