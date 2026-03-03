from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd


class MarketRegime(str, Enum):
    BEAR = "Bear"
    RANGE = "Range"
    TREND = "Trend"
    MOMENTUM = "Momentum"


@dataclass(frozen=True)
class RegimeScoreConfig:
    ma_fast: int = 20
    ma_slow: int = 60
    slope_window: int = 20
    vol_fast: int = 20
    vol_slow: int = 120
    mom_window: int = 20
    w_trend: float = 0.4
    w_structure: float = 0.3
    w_vol: float = 0.2
    w_mom: float = 0.1
    thr_bear: float = -0.5
    thr_range: float = 0.5
    thr_trend: float = 1.2


class RegimeDetectionEngine:
    def __init__(self, config: RegimeScoreConfig | None = None):
        self.config = config or RegimeScoreConfig()

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        if "close" not in df.columns:
            raise ValueError("missing close")

        out = df.copy()
        if "trade_date" in out.columns:
            out["trade_date"] = pd.to_datetime(out["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
            out = out.sort_values("trade_date")

        c = out["close"].astype(float)
        cfg = self.config

        ma_fast = c.rolling(cfg.ma_fast, min_periods=cfg.ma_fast).mean()
        ma_slow = c.rolling(cfg.ma_slow, min_periods=cfg.ma_slow).mean()

        out[f"ma{cfg.ma_fast}"] = ma_fast
        out[f"ma{cfg.ma_slow}"] = ma_slow

        trend_factor = self._rolling_slope(ma_slow, cfg.slope_window)
        denom = ma_slow.replace(0, np.nan)
        trend_factor = trend_factor / denom

        ma_structure = (ma_fast - ma_slow) / denom

        ret1 = c.pct_change()
        vol_fast = ret1.rolling(cfg.vol_fast, min_periods=cfg.vol_fast).std()
        vol_slow = ret1.rolling(cfg.vol_slow, min_periods=cfg.vol_slow).std()
        volatility_factor = vol_fast / vol_slow.replace(0, np.nan)

        momentum = c / c.shift(cfg.mom_window) - 1.0

        score = (
            cfg.w_trend * trend_factor
            + cfg.w_structure * ma_structure
            + cfg.w_vol * volatility_factor
            + cfg.w_mom * momentum
        )

        out["trend_factor"] = trend_factor
        out["ma_structure"] = ma_structure
        out["volatility_factor"] = volatility_factor
        out["momentum"] = momentum
        out["market_score"] = score
        out["regime"] = out["market_score"].apply(self.classify)
        return out

    def classify(self, score: float) -> str:
        if score is None or (isinstance(score, float) and np.isnan(score)):
            return MarketRegime.RANGE.value
        cfg = self.config
        if score < cfg.thr_bear:
            return MarketRegime.BEAR.value
        if cfg.thr_bear <= score <= cfg.thr_range:
            return MarketRegime.RANGE.value
        if cfg.thr_range < score <= cfg.thr_trend:
            return MarketRegime.TREND.value
        return MarketRegime.MOMENTUM.value

    @staticmethod
    def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
        x = np.arange(window, dtype=float)
        x_mean = x.mean()
        x_demean = x - x_mean
        denom = (x_demean**2).sum()

        def _slope(y: np.ndarray) -> float:
            if np.any(np.isnan(y)):
                return np.nan
            y = y.astype(float)
            y_mean = y.mean()
            num = (x_demean * (y - y_mean)).sum()
            return float(num / denom)

        return series.rolling(window, min_periods=window).apply(lambda s: _slope(s.values), raw=False)

