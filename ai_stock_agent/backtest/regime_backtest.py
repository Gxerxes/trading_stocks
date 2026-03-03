from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    fee_rate: float = 0.0002


def run_backtest(df: pd.DataFrame, cfg: Optional[BacktestConfig] = None) -> pd.DataFrame:
    cfg = cfg or BacktestConfig()
    out = df.copy()
    if "position" not in out.columns:
        raise ValueError("missing position")
    close = out["close"].astype(float)
    ret = close.pct_change().fillna(0.0)
    pos = out["position"].astype(float).clip(lower=0.0, upper=1.0)
    prev_pos = pos.shift(1).fillna(0.0)
    turnover = (pos - prev_pos).abs()
    cost = turnover * cfg.fee_rate
    strat_ret = prev_pos * ret - cost

    out["benchmark_ret"] = ret
    out["turnover"] = turnover
    out["cost"] = cost
    out["strategy_ret"] = strat_ret

    nav = (1.0 + strat_ret).cumprod()
    bnav = (1.0 + ret).cumprod()
    out["nav"] = nav
    out["benchmark_nav"] = bnav
    out["excess_nav"] = nav / bnav.replace(0, np.nan)
    return out


def save_report(df: pd.DataFrame, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    return out_path

