from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from regime.regime_engine import MarketRegime


@dataclass(frozen=True)
class GridConfig:
    ma_window: int = 20
    atr_window: int = 14
    k_atr: float = 1.0


@dataclass(frozen=True)
class TrendConfig:
    ma_window: int = 20


@dataclass(frozen=True)
class MomentumConfig:
    breakout_window: int = 20
    trail_stop_pct: float = 0.08


@dataclass(frozen=True)
class RiskConfig:
    vol_window: int = 20
    target_vol_annual: float = 0.15
    max_pos: float = 1.0
    min_pos: float = 0.0


def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window, min_periods=window).mean()


def compute_realized_vol_annual(close: pd.Series, window: int) -> pd.Series:
    r = close.astype(float).pct_change()
    v = r.rolling(window, min_periods=window).std()
    return v * np.sqrt(252.0)


def build_target_position(
    df: pd.DataFrame,
    grid: GridConfig | None = None,
    trend: TrendConfig | None = None,
    momentum: MomentumConfig | None = None,
) -> pd.DataFrame:
    grid = grid or GridConfig()
    trend = trend or TrendConfig()
    momentum = momentum or MomentumConfig()

    out = df.copy()
    close = out["close"].astype(float)

    ma20 = close.rolling(grid.ma_window, min_periods=grid.ma_window).mean()
    out["ma_grid"] = ma20

    if {"high", "low"}.issubset(out.columns):
        atr = compute_atr(out, window=grid.atr_window)
    else:
        atr = close.rolling(grid.atr_window, min_periods=grid.atr_window).std()
    out["atr"] = atr

    upper = ma20 + grid.k_atr * atr
    lower = ma20 - grid.k_atr * atr
    out["grid_upper"] = upper
    out["grid_lower"] = lower

    ma_trend = close.rolling(trend.ma_window, min_periods=trend.ma_window).mean()
    out["ma_trend"] = ma_trend

    roll_high = close.rolling(momentum.breakout_window, min_periods=momentum.breakout_window).max()
    out["breakout_high"] = roll_high

    regime = out.get("regime")
    if regime is None:
        raise ValueError("missing regime column")

    target = pd.Series(0.0, index=out.index, dtype=float)

    in_pos = False
    peak = np.nan

    for i in range(len(out)):
        mode = str(regime.iloc[i])
        px = float(close.iloc[i])

        if mode == MarketRegime.BEAR.value:
            in_pos = False
            peak = np.nan
            target.iloc[i] = 0.0
            continue

        if mode == MarketRegime.RANGE.value:
            lo = out["grid_lower"].iloc[i]
            hi = out["grid_upper"].iloc[i]
            prev = target.iloc[i - 1] if i > 0 else 0.0
            if not np.isnan(lo) and px < float(lo):
                target.iloc[i] = 1.0
            elif not np.isnan(hi) and px > float(hi):
                target.iloc[i] = 0.0
            else:
                target.iloc[i] = prev
            in_pos = target.iloc[i] > 0
            peak = px if in_pos else np.nan
            continue

        if mode == MarketRegime.TREND.value:
            m = out["ma_trend"].iloc[i]
            if not np.isnan(m) and px > float(m):
                target.iloc[i] = 1.0
                in_pos = True
                peak = px if np.isnan(peak) else max(peak, px)
            else:
                target.iloc[i] = 0.0
                in_pos = False
                peak = np.nan
            continue

        bh = out["breakout_high"].iloc[i]
        prev = target.iloc[i - 1] if i > 0 else 0.0
        if prev > 0:
            peak = px if np.isnan(peak) else max(peak, px)
            if not np.isnan(peak) and px < peak * (1.0 - momentum.trail_stop_pct):
                target.iloc[i] = 0.0
                in_pos = False
                peak = np.nan
            else:
                target.iloc[i] = 1.0
                in_pos = True
        else:
            if not np.isnan(bh) and px >= float(bh):
                target.iloc[i] = 1.0
                in_pos = True
                peak = px
            else:
                target.iloc[i] = 0.0
                in_pos = False
                peak = np.nan

    out["target_pos"] = target
    return out


def apply_risk_control(df: pd.DataFrame, risk: RiskConfig | None = None) -> pd.DataFrame:
    risk = risk or RiskConfig()
    out = df.copy()
    close = out["close"].astype(float)
    vol = compute_realized_vol_annual(close, window=risk.vol_window)
    out["realized_vol_annual"] = vol

    scale = risk.target_vol_annual / vol.replace(0, np.nan)
    scale = scale.clip(lower=0.0, upper=1.0).fillna(0.0)
    out["risk_scale"] = scale

    pos = out["target_pos"].astype(float) * out["risk_scale"]
    pos = pos.clip(lower=risk.min_pos, upper=risk.max_pos)
    out["position"] = pos
    return out

