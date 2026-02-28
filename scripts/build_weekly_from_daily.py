"""
将日线CSV聚合为周线CSV（按每周最后一个交易日收盘）。

示例：
python scripts/build_weekly_from_daily.py \
  --input-csv ai_stock_agent/data/wyckoff_data/600030.SH_qfq_20030106_20260226.csv

批量：
python scripts/build_weekly_from_daily.py --input-dir ai_stock_agent/data/wyckoff_data
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="将日线CSV聚合为周线CSV")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--input-csv", type=str, help="单个日线CSV路径")
    group.add_argument("--input-dir", type=str, help="日线CSV目录（批量处理）")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ai_stock_agent/data/weekly_data",
        help="周线CSV输出目录",
    )
    return parser.parse_args()


def build_weekly_from_daily(df: pd.DataFrame) -> pd.DataFrame:
    required_cols = ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要字段: {missing}")

    work = df.copy()
    work["trade_date"] = pd.to_datetime(work["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)

    num_cols = ["open", "high", "low", "close", "vol", "amount"]
    for col in num_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    # 使用周周期分组，但 trade_date 取该周最后一个真实交易日，避免生成非交易日日期。
    week_period = work["trade_date"].dt.to_period("W-FRI")

    weekly = (
        work.groupby(week_period, as_index=False)
        .agg(
            ts_code=("ts_code", "first"),
            trade_date=("trade_date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            vol=("vol", "sum"),
            amount=("amount", "sum"),
        )
        .sort_values("trade_date")
        .reset_index(drop=True)
    )

    weekly["pre_close"] = weekly["close"].shift(1)
    weekly["change"] = weekly["close"] - weekly["pre_close"]
    weekly["pct_chg"] = (weekly["change"] / weekly["pre_close"]) * 100

    weekly["trade_date"] = weekly["trade_date"].dt.strftime("%Y%m%d")

    ordered_cols = [
        "ts_code",
        "trade_date",
        "open",
        "high",
        "low",
        "close",
        "pre_close",
        "change",
        "pct_chg",
        "vol",
        "amount",
    ]
    return weekly[ordered_cols]


def iter_input_files(input_csv: str | None, input_dir: str | None) -> Iterable[Path]:
    if input_csv:
        yield Path(input_csv)
        return

    p = Path(input_dir)
    for f in sorted(p.glob("*.csv")):
        if f.is_file():
            yield f


def output_filename(src: Path, weekly_df: pd.DataFrame) -> str:
    stem = src.stem
    # 例如: 600030.SH_qfq_20030106_20260226 -> 600030.SH_qfq_w_20030110_20260226
    first_date = str(weekly_df["trade_date"].iloc[0])
    last_date = str(weekly_df["trade_date"].iloc[-1])
    if "_" in stem:
        parts = stem.split("_")
        if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
            stem = "_".join(parts[:-2])
    return f"{stem}_w_{first_date}_{last_date}.csv"


def process_one_file(src: Path, out_dir: Path) -> Path:
    df = pd.read_csv(src, encoding="utf-8-sig")
    weekly_df = build_weekly_from_daily(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / output_filename(src, weekly_df)
    weekly_df.to_csv(out_file, index=False, encoding="utf-8-sig")
    return out_file


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)

    outputs: list[Path] = []
    for src in iter_input_files(args.input_csv, args.input_dir):
        try:
            out_file = process_one_file(src, out_dir)
            outputs.append(out_file)
            print(f"ok: {src} -> {out_file}")
        except Exception as e:
            print(f"failed: {src} ({e})")

    print(f"total_outputs={len(outputs)}")


if __name__ == "__main__":
    main()
