"""
将多源行情（BaoStock分钟线 + Tushare日/周线）统一成一套 bars 数据结构并落地为 Parquet。

示例（中信证券）:
python scripts/build_unified_bars_lake.py \
  --ts-code 600030.SH \
  --minute-csv ai_stock_agent/data/minute_baostock/sh_600030_2026-02-27_2026-02-27_5m_adj2.csv \
  --daily-csv ai_stock_agent/data/stock_daily/600030.SH_20030106_20260226.csv \
  --weekly-csv ai_stock_agent/data/weekly_data/600030.SH_qfq_w_20030110_20260226.csv
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd


STANDARD_COLS = [
    "ts_code",
    "freq",
    "trade_time",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "adjust_type",
    "source",
    "updated_at",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="构建统一 bars 数据层（Parquet）")
    p.add_argument("--ts-code", type=str, required=True, help="统一TS代码，如 600030.SH")
    p.add_argument("--minute-csv", type=str, default=None, help="BaoStock 分钟线 CSV（可选）")
    p.add_argument("--daily-csv", type=str, default=None, help="Tushare 日线 CSV（可选）")
    p.add_argument("--weekly-csv", type=str, default=None, help="Tushare 周线 CSV（可选）")
    p.add_argument("--daily-adjust-type", type=str, default="qfq", help="日线复权类型，默认 qfq")
    p.add_argument("--weekly-adjust-type", type=str, default="qfq", help="周线复权类型，默认 qfq")
    p.add_argument(
        "--enforce-qfq",
        action="store_true",
        default=True,
        help="强制所有输入数据为前复权（默认开启）",
    )
    p.add_argument("--out-dir", type=str, default="ai_stock_agent/data/lake/bars", help="输出根目录（Parquet）")
    return p.parse_args()


def normalize_ts_code_from_baostock(code: str) -> str:
    c = str(code).strip().lower()
    if c.startswith("sh."):
        return c.replace("sh.", "").upper() + ".SH"
    if c.startswith("sz."):
        return c.replace("sz.", "").upper() + ".SZ"
    return c.upper()


def parse_baostock_time(raw: str) -> str:
    s = str(raw).strip()
    # 20260227093500000 -> 2026-02-27 09:35:00
    s14 = s[:14]
    return datetime.strptime(s14, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")


def infer_adjust_type_from_adjustflag(adjustflag: str) -> str:
    mapping = {"1": "hfq", "2": "qfq", "3": "none"}
    return mapping.get(str(adjustflag), "unknown")


def detect_adjust_type_from_filename(path: Path, fallback: str) -> str:
    stem = path.stem.lower()
    for x in ["qfq", "hfq", "none"]:
        if f"_{x}_" in stem or stem.endswith(f"_{x}") or f"{x}_" in stem:
            return x
    return fallback


def normalize_minute(minute_csv: Path, ts_code: str) -> pd.DataFrame:
    df = pd.read_csv(minute_csv, encoding="utf-8-sig")
    need = {"date", "time", "code", "open", "high", "low", "close", "volume", "amount", "adjustflag"}
    if not need.issubset(df.columns):
        raise ValueError(f"分钟线文件缺少字段: {sorted(need - set(df.columns))}")

    out = pd.DataFrame(index=df.index)
    out["ts_code"] = ts_code
    out["freq"] = "5m" if "5m" in minute_csv.stem else "min"
    out["trade_time"] = df["time"].map(parse_baostock_time)
    out["trade_date"] = pd.to_datetime(df["date"]).dt.strftime("%Y%m%d")
    for c in ["open", "high", "low", "close", "volume", "amount"]:
        out[c] = pd.to_numeric(df[c], errors="coerce")
    out["adjust_type"] = df["adjustflag"].map(infer_adjust_type_from_adjustflag)
    out["source"] = "baostock"
    out["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return out[STANDARD_COLS]


def normalize_tushare_ohlcv(csv_path: Path, ts_code: str, freq: str, adjust_type: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    need = {"ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"}
    if not need.issubset(df.columns):
        raise ValueError(f"{freq} 文件缺少字段: {sorted(need - set(df.columns))}")

    out = pd.DataFrame(index=df.index)
    out["ts_code"] = ts_code
    out["freq"] = freq
    out["trade_date"] = df["trade_date"].astype(str)
    out["trade_time"] = pd.to_datetime(out["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d 15:00:00")
    out["open"] = pd.to_numeric(df["open"], errors="coerce")
    out["high"] = pd.to_numeric(df["high"], errors="coerce")
    out["low"] = pd.to_numeric(df["low"], errors="coerce")
    out["close"] = pd.to_numeric(df["close"], errors="coerce")
    out["volume"] = pd.to_numeric(df["vol"], errors="coerce")
    out["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    out["adjust_type"] = adjust_type
    out["source"] = "tushare"
    out["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return out[STANDARD_COLS]


def write_partitioned_parquet(df: pd.DataFrame, out_root: Path) -> list[Path]:
    outputs: list[Path] = []
    for (freq, ts_code), g in df.groupby(["freq", "ts_code"], sort=True):
        p = out_root / f"freq={freq}" / f"ts_code={ts_code}"
        p.mkdir(parents=True, exist_ok=True)
        fname = f"{ts_code}_{freq}_{g['trade_date'].min()}_{g['trade_date'].max()}.parquet"
        out_file = p / fname
        g.sort_values("trade_time").to_parquet(out_file, index=False)
        outputs.append(out_file)
    return outputs


def main() -> None:
    args = parse_args()
    ts_code = args.ts_code.strip().upper()
    out_root = Path(args.out_dir)

    frames: list[pd.DataFrame] = []
    if args.minute_csv:
        minute_path = Path(args.minute_csv)
        m = normalize_minute(minute_path, ts_code=ts_code)
        # 自动修正频率（从文件名里识别 5m/15m/30m/60m）
        stem = minute_path.stem.lower()
        for f in ["5m", "15m", "30m", "60m"]:
            if f in stem:
                m["freq"] = f
                break
        if args.enforce_qfq and not m.empty:
            adjust_set = set(m["adjust_type"].astype(str).str.lower().unique().tolist())
            if adjust_set != {"qfq"}:
                raise ValueError(f"分钟线必须为前复权(qfq)，当前 detect={sorted(adjust_set)}，文件={minute_path}")
        frames.append(m)

    if args.daily_csv:
        daily_path = Path(args.daily_csv)
        daily_adjust = detect_adjust_type_from_filename(daily_path, args.daily_adjust_type)
        if args.enforce_qfq and daily_adjust.lower() != "qfq":
            raise ValueError(f"日线必须为前复权(qfq)，当前 detect={daily_adjust}，文件={daily_path}")
        frames.append(normalize_tushare_ohlcv(daily_path, ts_code=ts_code, freq="1d", adjust_type=daily_adjust))

    if args.weekly_csv:
        weekly_path = Path(args.weekly_csv)
        weekly_adjust = detect_adjust_type_from_filename(weekly_path, args.weekly_adjust_type)
        if args.enforce_qfq and weekly_adjust.lower() != "qfq":
            raise ValueError(f"周线必须为前复权(qfq)，当前 detect={weekly_adjust}，文件={weekly_path}")
        frames.append(normalize_tushare_ohlcv(weekly_path, ts_code=ts_code, freq="1w", adjust_type=weekly_adjust))

    if not frames:
        raise ValueError("至少提供一个输入文件: --minute-csv / --daily-csv / --weekly-csv")

    bars = pd.concat(frames, ignore_index=True)
    bars["freq"] = bars["freq"].astype(str).replace({"": "unknown", "nan": "unknown"})
    bars = bars.dropna(subset=["trade_time", "open", "high", "low", "close"]).copy()
    bars = bars.sort_values(["freq", "trade_time"]).reset_index(drop=True)

    out_files = write_partitioned_parquet(bars, out_root=out_root)

    # 额外保存一份统一快照，便于手工检查
    snapshot_dir = out_root / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = snapshot_dir / f"{ts_code}_bars_snapshot.csv"
    bars.to_csv(snapshot_file, index=False, encoding="utf-8-sig")

    print(f"snapshot={snapshot_file}")
    print(f"rows={len(bars)} freqs={sorted(set(bars['freq'].tolist()))}")
    for f in out_files:
        print(f"parquet={f}")


if __name__ == "__main__":
    main()
