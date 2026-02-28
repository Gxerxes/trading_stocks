"""
Wyckoff AI Engine

将主观维科夫分析规则化为可训练数据管线：
- Trading Range 识别
- Phase A-E 判定
- Spring / SOS 检测
- 吸筹概率评分（0-100）
- 训练标签（未来收益）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class WyckoffResult:
    daily_features: pd.DataFrame
    phase_signals: pd.DataFrame
    latest_assessment: Dict[str, object]
    minute_entry: Dict[str, object]


class WyckoffAIEngine:
    def __init__(self, lake_root: Path):
        self.lake_root = lake_root

    def load_bars(self, ts_code: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        daily_file = self._find_latest_parquet("1d", ts_code)
        weekly_file = self._find_latest_parquet("1w", ts_code)
        minute_file = self._find_latest_parquet("5m", ts_code)

        if daily_file is None or weekly_file is None:
            raise FileNotFoundError(f"{ts_code} 缺少日线或周线 parquet 数据")

        daily = pd.read_parquet(daily_file)
        weekly = pd.read_parquet(weekly_file)
        minute = pd.read_parquet(minute_file) if minute_file else pd.DataFrame()

        daily = self._prep_bars(daily)
        weekly = self._prep_bars(weekly)
        if not minute.empty:
            minute = self._prep_bars(minute)

        return daily, weekly, minute

    def run(self, ts_code: str) -> WyckoffResult:
        daily, weekly, minute = self.load_bars(ts_code)
        daily_feat = self._build_daily_features(daily, weekly)
        phase_df = self._build_phase_signals(daily_feat)
        minute_entry = self._build_minute_entry_signal(minute)
        latest = self._build_latest_assessment(phase_df, minute_entry)
        return WyckoffResult(
            daily_features=daily_feat,
            phase_signals=phase_df,
            latest_assessment=latest,
            minute_entry=minute_entry,
        )

    def _find_latest_parquet(self, freq: str, ts_code: str) -> Path | None:
        p = self.lake_root / f"freq={freq}" / f"ts_code={ts_code}"
        if not p.exists():
            return None
        files = sorted(p.glob("*.parquet"))
        return files[-1] if files else None

    @staticmethod
    def _prep_bars(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out["trade_date"] = out["trade_date"].astype(str)
        out["trade_time"] = pd.to_datetime(out["trade_time"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume", "amount"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
        out = out.sort_values("trade_time").reset_index(drop=True)
        return out

    @staticmethod
    def _atr(df: pd.DataFrame, n: int = 20) -> pd.Series:
        prev_close = df["close"].shift(1)
        tr = pd.concat(
            [
                (df["high"] - df["low"]).abs(),
                (df["high"] - prev_close).abs(),
                (df["low"] - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        return tr.rolling(n, min_periods=max(5, n // 2)).mean()

    @staticmethod
    def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
        # 用窗口首尾变化率近似斜率，避免引入额外库
        return (series / series.shift(window) - 1.0).replace([np.inf, -np.inf], np.nan)

    def _build_daily_features(self, daily: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
        d = daily.copy()
        d["trade_dt"] = pd.to_datetime(d["trade_date"], format="%Y%m%d", errors="coerce")
        d["ma20"] = d["close"].rolling(20, min_periods=10).mean()
        d["ma60"] = d["close"].rolling(60, min_periods=30).mean()
        d["vol_ma20"] = d["volume"].rolling(20, min_periods=10).mean()
        d["vol_ma120"] = d["volume"].rolling(120, min_periods=30).mean()
        d["atr20"] = self._atr(d, 20)
        d["atr20_norm"] = d["atr20"] / d["close"]
        d["atr20_change_20"] = d["atr20_norm"] / d["atr20_norm"].shift(20) - 1.0

        d["range_low_120"] = d["low"].rolling(120, min_periods=40).min()
        d["range_high_120"] = d["high"].rolling(120, min_periods=40).max()
        d["range_width_120"] = d["range_high_120"] - d["range_low_120"]
        d["range_width_ratio_120"] = d["range_width_120"] / d["close"]
        d["range_position_120"] = (d["close"] - d["range_low_120"]) / d["range_width_120"].replace(0, np.nan)

        d["trend_slope_20"] = self._rolling_slope(d["close"], 20)
        d["trend_slope_60"] = self._rolling_slope(d["close"], 60)
        d["volume_trend_20"] = self._rolling_slope(d["vol_ma20"], 20)
        d["vol_dry_up_ratio"] = 1.0 - (d["vol_ma20"] / d["vol_ma120"])
        d["vol_spike"] = (d["volume"] > d["vol_ma20"] * 1.5).astype(int)

        # 支撑测试次数：近60日内 low 接近 rolling support 的次数
        support_raw = d["low"].rolling(120, min_periods=40).min()
        support_touch = (d["low"] <= support_raw * 1.02).astype(int)
        d["support_test_count_60"] = support_touch.rolling(60, min_periods=20).sum()

        # Trading Range 标记
        d["trading_range_flag"] = (
            (d["range_width_ratio_120"] < 0.30)
            & (d["atr20_change_20"] < 0)
            & (d["trend_slope_60"].abs() < 0.18)
        ).astype(int)

        # 周线特征（phase用）：merge_asof 到日线
        w = weekly.copy()
        w["trade_dt"] = pd.to_datetime(w["trade_date"], format="%Y%m%d", errors="coerce")
        w["weekly_trend_26"] = self._rolling_slope(w["close"], 26)
        w["weekly_range_low_26"] = w["low"].rolling(26, min_periods=10).min()
        w["weekly_range_high_26"] = w["high"].rolling(26, min_periods=10).max()
        w["weekly_range_pos_26"] = (w["close"] - w["weekly_range_low_26"]) / (
            w["weekly_range_high_26"] - w["weekly_range_low_26"]
        ).replace(0, np.nan)
        w = w[["trade_dt", "weekly_trend_26", "weekly_range_pos_26"]].sort_values("trade_dt")

        d = d.sort_values("trade_dt")
        d = pd.merge_asof(d, w, on="trade_dt", direction="backward")
        d = d.replace([np.inf, -np.inf], np.nan)
        return d

    def _build_phase_signals(self, d: pd.DataFrame) -> pd.DataFrame:
        df = d.copy()

        support_prev = df["range_low_120"].shift(1)
        resistance_prev = df["range_high_120"].shift(1)

        # Spring
        df["spring"] = (
            (df["low"] < support_prev * 0.98)
            & (df["close"] > support_prev)
            & (df["volume"] > df["vol_ma20"] * 1.5)
        ).astype(int)

        # SOS
        df["sos_breakout"] = (
            (df["close"] > resistance_prev * 1.01) & (df["volume"] > df["vol_ma20"] * 2.0)
        ).astype(int)
        # 回踩不破（向后验证，训练与复盘用）
        pullback_floor = df["low"].rolling(5, min_periods=2).min().shift(-4)
        df["sos_pullback_hold"] = (pullback_floor > resistance_prev * 0.99).astype(int)
        df["sos"] = ((df["sos_breakout"] == 1) & (df["sos_pullback_hold"] == 1)).astype(int)

        # Phase A-E 规则
        phase = np.array(["UNKNOWN"] * len(df), dtype=object)

        phase_a = (
            (df["trend_slope_60"] < -0.20)
            & (df["vol_spike"] == 1)
            & (self._rolling_slope(df["close"], 5) > -0.03)
        )
        phase_b = (
            (df["trading_range_flag"] == 1)
            & (df["volume_trend_20"] < 0)
            & (df["support_test_count_60"] >= 3)
        )
        phase_c = df["spring"] == 1
        phase_d = (
            (df["close"] > df["range_high_120"].shift(1) * 1.01)
            & (df["volume"] > df["vol_ma20"] * 1.8)
            & (df["low"] > df["low"].shift(10))
        )
        phase_e = (
            (df["high"] >= df["high"].rolling(20, min_periods=10).max())
            & (df["trend_slope_20"] > df["trend_slope_60"])
            & (df["close"] > df["ma20"])
        )

        # 优先级：E > D > C > B > A
        phase[phase_a.fillna(False).values] = "A"
        phase[phase_b.fillna(False).values] = "B"
        phase[phase_c.fillna(False).values] = "C"
        phase[phase_d.fillna(False).values] = "D"
        phase[phase_e.fillna(False).values] = "E"

        # 二级兜底分类：减少 UNKNOWN，提升可训练标签密度
        unknown_mask = phase == "UNKNOWN"
        fallback_a = unknown_mask & (df["trend_slope_60"] < -0.12).fillna(False)
        phase[fallback_a.values] = "A"

        unknown_mask = phase == "UNKNOWN"
        fallback_e = unknown_mask & (df["trend_slope_60"] > 0.12).fillna(False)
        phase[fallback_e.values] = "E"

        unknown_mask = phase == "UNKNOWN"
        fallback_b = unknown_mask & (df["trading_range_flag"] == 1).fillna(False)
        phase[fallback_b.values] = "B"

        # 仍无法判定的剩余部分，归为 B（中性区间），避免训练标签过 sparse
        phase[phase == "UNKNOWN"] = "B"
        df["phase"] = phase

        # 吸筹评分 0-100
        range_duration = (df["trading_range_flag"].rolling(120, min_periods=20).sum() / 120.0).clip(0, 1)
        volatility_contraction = (-df["atr20_change_20"] / 0.30).clip(0, 1)
        volume_dry_up = df["vol_dry_up_ratio"].clip(0, 1)
        spring_quality = (
            df["spring"]
            * ((df["close"] - support_prev) / (support_prev * 0.03)).clip(0, 1)
            * (df["volume"] / (df["vol_ma20"] * 1.5)).clip(0, 1)
        ).fillna(0)
        support_strength = (df["support_test_count_60"] / 10.0).clip(0, 1)

        score = (
            0.25 * range_duration
            + 0.20 * volatility_contraction
            + 0.20 * volume_dry_up
            + 0.20 * spring_quality
            + 0.15 * support_strength
        ) * 100.0
        df["accumulation_score"] = score.round(2).clip(0, 100)

        # 训练标签
        df["future_return_5d"] = df["close"].shift(-5) / df["close"] - 1.0
        df["future_return_10d"] = df["close"].shift(-10) / df["close"] - 1.0
        df["future_return_20d"] = df["close"].shift(-20) / df["close"] - 1.0
        df["spring_success_10d"] = (
            (df["spring"] == 1) & (df["future_return_10d"] > 0.05)
        ).astype(int)

        keep_cols = [
            "ts_code",
            "trade_date",
            "trade_dt",
            "close",
            "volume",
            "range_low_120",
            "range_high_120",
            "trading_range_flag",
            "trend_slope_60",
            "volume_trend_20",
            "weekly_trend_26",
            "phase",
            "spring",
            "sos",
            "accumulation_score",
            "future_return_5d",
            "future_return_10d",
            "future_return_20d",
            "spring_success_10d",
        ]
        return df[keep_cols].copy()

    @staticmethod
    def _build_minute_entry_signal(minute: pd.DataFrame) -> Dict[str, object]:
        if minute is None or minute.empty:
            return {
                "available": False,
                "entry_ready": False,
                "reason": "minute data missing",
            }

        m = minute.copy().sort_values("trade_time")
        last_day = m["trade_date"].astype(str).max()
        day = m[m["trade_date"].astype(str) == str(last_day)].copy()
        if day.empty:
            return {"available": False, "entry_ready": False, "reason": "latest day missing"}

        # 5分钟入场逻辑：突破开盘30分钟高点 + 量能确认
        first_6 = day.head(6)  # 30分钟
        first_30m_high = float(first_6["high"].max())
        last_close = float(day["close"].iloc[-1])
        vol_ma20 = day["volume"].rolling(20, min_periods=5).mean()
        vol_last3 = float(day["volume"].tail(3).mean())
        vol_ref = float(vol_ma20.iloc[-1]) if not pd.isna(vol_ma20.iloc[-1]) else np.nan

        entry_ready = (last_close > first_30m_high) and (not np.isnan(vol_ref)) and (vol_last3 > vol_ref * 1.2)
        reason = "break_30m_high_and_volume_expand" if entry_ready else "no_confirmed_intraday_entry"
        return {
            "available": True,
            "trade_date": str(last_day),
            "first_30m_high": round(first_30m_high, 4),
            "last_close": round(last_close, 4),
            "vol_last3": round(vol_last3, 2),
            "vol_ref20": round(vol_ref, 2) if not np.isnan(vol_ref) else None,
            "entry_ready": bool(entry_ready),
            "reason": reason,
        }

    @staticmethod
    def _build_latest_assessment(phase_df: pd.DataFrame, minute_entry: Dict[str, object]) -> Dict[str, object]:
        latest = phase_df.iloc[-1]
        score = float(latest["accumulation_score"])
        if score >= 80:
            score_level = "strong_accumulation"
        elif score >= 60:
            score_level = "suspected_accumulation"
        elif score >= 40:
            score_level = "neutral_range"
        else:
            score_level = "no_accumulation"

        return {
            "ts_code": str(latest["ts_code"]),
            "trade_date": str(latest["trade_date"]),
            "phase": str(latest["phase"]),
            "spring": bool(int(latest["spring"])),
            "sos": bool(int(latest["sos"])),
            "accumulation_score": round(score, 2),
            "score_level": score_level,
            "minute_entry": minute_entry,
        }
