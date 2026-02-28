"""
资金扩散突破策略（高胜率改进版，3-5天）

改进点（相对原版）：
1) 市场广度过滤：当日 close>MA20 占比 >= 55%
2) 入选阈值收紧：
   - pct_chg: 2.5%~5.5%
   - turnover_rate: 6%~15%
   - amplitude_pct <= 8%
3) 行业动量过滤：行业 ret5、ret20 同时位于前30%
4) 流动性过滤：amount >= 200000（单位按Tushare daily）
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from config.settings import DAILY_BASIC_HISTORY_DIR, DAILY_HISTORY_DIR, DATA_DIR, STRATEGY_SIGNAL_DIR


class CapitalDiffusion35DHighWinStrategy:
    def __init__(self, top_n: int = 20):
        self.top_n = top_n

    @staticmethod
    def _available_dates(prefix: str, folder: Path) -> List[str]:
        files = sorted(folder.glob(f"{prefix}_*.csv"))
        return [f.stem.split("_")[-1] for f in files]

    @staticmethod
    def _load_history(folder: Path, prefix: str, end_date: str, lookback_days: int = 180) -> pd.DataFrame:
        dates = [d for d in CapitalDiffusion35DHighWinStrategy._available_dates(prefix, folder) if d <= end_date]
        dates = dates[-lookback_days:]
        if not dates:
            return pd.DataFrame()
        return pd.concat([pd.read_csv(folder / f"{prefix}_{d}.csv") for d in dates], ignore_index=True)

    @staticmethod
    def _next_trade_date(as_of_date: str) -> Optional[str]:
        dates = sorted(CapitalDiffusion35DHighWinStrategy._available_dates("daily", DAILY_HISTORY_DIR))
        future = [d for d in dates if d > as_of_date]
        return future[0] if future else None

    def calculate(self, as_of_date: str) -> pd.DataFrame:
        price_hist = self._load_history(DAILY_HISTORY_DIR, "daily", as_of_date, lookback_days=200)
        basic_hist = self._load_history(DAILY_BASIC_HISTORY_DIR, "daily_basic", as_of_date, lookback_days=200)
        if price_hist.empty or basic_hist.empty:
            return pd.DataFrame()

        industry_df = pd.read_csv(DATA_DIR / "all_stocks_active_no_st_by_industry.csv", dtype={"ts_code": str})
        industry_df = industry_df[["ts_code", "name", "industry"]].drop_duplicates("ts_code")

        price_hist["trade_date"] = pd.to_datetime(price_hist["trade_date"].astype(str), format="%Y%m%d")
        basic_hist["trade_date"] = pd.to_datetime(basic_hist["trade_date"].astype(str), format="%Y%m%d")
        price_hist = price_hist.sort_values(["ts_code", "trade_date"])
        basic_hist = basic_hist.sort_values(["ts_code", "trade_date"])

        g = price_hist.groupby("ts_code", group_keys=False)
        price_hist["ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
        price_hist["ma20_slope5"] = g["ma20"].transform(lambda s: s - s.shift(5))
        price_hist["vol_ma5"] = g["vol"].transform(lambda s: s.rolling(5, min_periods=5).mean())
        price_hist["ret5"] = g["close"].transform(lambda s: s / s.shift(5) - 1)
        price_hist["ret20"] = g["close"].transform(lambda s: s / s.shift(20) - 1)
        if "pct_chg" not in price_hist.columns:
            price_hist["pct_chg"] = g["close"].pct_change() * 100

        # 振幅代理：以 pre_close 推导（pre_close = close / (1+pct_chg)）
        price_hist["pre_close_proxy"] = price_hist["close"] / (1 + price_hist["pct_chg"] / 100.0)
        price_hist["amplitude_pct"] = ((price_hist["high"] - price_hist["low"]) / price_hist["pre_close_proxy"]) * 100
        price_hist["avg_price_proxy"] = (price_hist["open"] + price_hist["high"] + price_hist["low"] + price_hist["close"]) / 4.0

        dt = pd.to_datetime(as_of_date, format="%Y%m%d")
        pl = price_hist[price_hist["trade_date"] == dt].copy()
        bl = basic_hist[basic_hist["trade_date"] == dt].copy()
        if pl.empty or bl.empty:
            return pd.DataFrame()

        # 市场广度过滤
        breadth = float((pl["close"] > pl["ma20"]).mean()) if len(pl) else 0.0
        if breadth < 0.55:
            return pd.DataFrame()

        x = pl.merge(
            bl[["ts_code", "turnover_rate", "volume_ratio"]],
            on="ts_code",
            how="inner",
        ).merge(industry_df, on="ts_code", how="left")

        for c in [
            "close",
            "ma20",
            "ma20_slope5",
            "vol",
            "vol_ma5",
            "pct_chg",
            "turnover_rate",
            "volume_ratio",
            "amplitude_pct",
            "ret5",
            "ret20",
            "amount",
        ]:
            x[c] = pd.to_numeric(x[c], errors="coerce")

        ind = x.groupby("industry").agg(ind_ret5=("ret5", "mean"), ind_ret20=("ret20", "mean")).reset_index()
        x = x.merge(ind, on="industry", how="left")
        q5 = x["ind_ret5"].quantile(0.7)
        q20 = x["ind_ret20"].quantile(0.7)

        trend_ok = (x["close"] > x["ma20"]) & (x["ma20_slope5"] > 0)
        start_ok = x["pct_chg"].between(2.5, 5.5) & (x["vol"] > x["vol_ma5"] * 1.8)
        turnover_ok = x["turnover_rate"].between(6, 15)
        amp_ok = x["amplitude_pct"] <= 8
        liquid_ok = x["amount"] >= 200000
        ind_ok = (x["ind_ret5"] >= q5) & (x["ind_ret20"] >= q20)

        x = x[trend_ok & start_ok & turnover_ok & amp_ok & liquid_ok & ind_ok].copy()
        if x.empty:
            return x

        x["vol_boost"] = (x["vol"] / x["vol_ma5"]).clip(1.0, 4.0)
        x["turnover_mid"] = 1 - ((x["turnover_rate"] - 10).abs() / 10).clip(0, 1)
        x["amp_score"] = (1 - (x["amplitude_pct"] / 8).clip(0, 1)).fillna(0)
        x["score"] = (
            35 * (x["vol_boost"] - 1) / 3
            + 25 * (x["pct_chg"].clip(2.5, 5.5) - 2.5) / 3
            + 20 * x["turnover_mid"]
            + 20 * x["amp_score"]
        )
        x = x.sort_values("score", ascending=False).head(self.top_n).copy()

        next_day = self._next_trade_date(as_of_date) or "NEXT_TRADE_DAY_UNKNOWN"
        x["signal_date"] = as_of_date
        x["entry_date"] = next_day
        x["market_breadth"] = round(breadth, 4)
        x["entry_rule"] = "next_open<=prev_close*1.03 AND next_low>=prev_avg_price_proxy"
        x["entry_price_ref"] = x["close"].round(2)
        x["stop_loss_pct"] = -3.0
        x["max_hold_days"] = 5
        x["time_exit_day"] = 3
        x["momentum_exit_rule"] = "daily_vol < prev_day_vol*0.8"

        cols = [
            "ts_code",
            "name",
            "industry",
            "signal_date",
            "entry_date",
            "close",
            "pct_chg",
            "turnover_rate",
            "volume_ratio",
            "amplitude_pct",
            "vol_boost",
            "market_breadth",
            "score",
            "entry_rule",
            "entry_price_ref",
            "stop_loss_pct",
            "time_exit_day",
            "max_hold_days",
            "momentum_exit_rule",
        ]
        return x[cols]

    def save(self, as_of_date: str, output_dir: Path = STRATEGY_SIGNAL_DIR) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / f"capital_diffusion_3_5d_high_win_{as_of_date}.csv"
        self.calculate(as_of_date).to_csv(out_file, index=False, encoding="utf-8-sig")
        return out_file
