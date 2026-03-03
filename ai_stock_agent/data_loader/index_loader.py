from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def find_latest_index_daily_csv(data_dir: Path, index_code: str) -> Path:
    matches = list(data_dir.glob(f"**/index_daily/*index_daily_{index_code}_*.csv"))
    if not matches:
        raise FileNotFoundError(f"no index_daily csv for {index_code} under {data_dir}")
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def load_index_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"ts_code": str, "trade_date": str})
    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str)
    return df


def find_index_root(data_dir: Path, index_code: str) -> Optional[Path]:
    p = data_dir / "index" / index_code
    return p if p.exists() else None

