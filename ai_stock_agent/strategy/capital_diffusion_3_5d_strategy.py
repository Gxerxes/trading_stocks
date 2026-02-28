"""
资金扩散突破策略（持仓3-5天）

核心规则：
1) 趋势过滤：close > MA20 且 MA20上行
2) 资金启动：当日涨幅 3%~7%，vol > VOL_MA5 * 1.8
3) 换手率：5%~20%
4) 次日执行条件（由执行/回测阶段判断）：
   - 次日开盘涨幅不超过3%
   - 次日最低价不破前一日均价代理值((O+H+L+C)/4)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pandas as pd

from config.settings import (
    DAILY_BASIC_HISTORY_DIR,
    DAILY_HISTORY_DIR,
    DATA_DIR,
    STRATEGY_SIGNAL_DIR,
)


class CapitalDiffusion35DStrategy:
    """资金扩散突破策略（偏3-5日持有）"""

    def __init__(self, top_n: int = 20):
        self.top_n = top_n

    @staticmethod
    def _available_dates(prefix: str, folder: Path) -> List[str]:
        files = sorted(folder.glob(f"{prefix}_*.csv"))
        return [f.stem.split("_")[-1] for f in files]

    @staticmethod
    def _load_history(folder: Path, prefix: str, end_date: str, lookback_days: int = 120) -> pd.DataFrame:
        dates = [d for d in CapitalDiffusion35DStrategy._available_dates(prefix, folder) if d <= end_date]
        dates = dates[-lookback_days:]
        if not dates:
            return pd.DataFrame()
        frames = [pd.read_csv(folder / f"{prefix}_{d}.csv") for d in dates]
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _next_trade_date(as_of_date: str) -> Optional[str]:
        dates = sorted(CapitalDiffusion35DStrategy._available_dates("daily", DAILY_HISTORY_DIR))
        future = [d for d in dates if d > as_of_date]
        return future[0] if future else None

    def calculate(self, as_of_date: str) -> pd.DataFrame:
        price_hist = self._load_history(DAILY_HISTORY_DIR, "daily", as_of_date, lookback_days=160)
        basic_hist = self._load_history(DAILY_BASIC_HISTORY_DIR, "daily_basic", as_of_date, lookback_days=160)
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
        # 使用 daily 的 pct_chg，若不存在则回退 close 变化率
        if "pct_chg" not in price_hist.columns:
            price_hist["pct_chg"] = g["close"].pct_change() * 100
        price_hist["avg_price_proxy"] = (
            price_hist["open"] + price_hist["high"] + price_hist["low"] + price_hist["close"]
        ) / 4.0

        dt = pd.to_datetime(as_of_date, format="%Y%m%d")
        pl = price_hist[price_hist["trade_date"] == dt].copy()
        bl = basic_hist[basic_hist["trade_date"] == dt].copy()
        if pl.empty or bl.empty:
            return pd.DataFrame()

        x = pl.merge(
            bl[["ts_code", "turnover_rate", "volume_ratio"]],
            on="ts_code",
            how="inner",
        ).merge(industry_df, on="ts_code", how="left")

        for c in ["close", "ma20", "ma20_slope5", "vol", "vol_ma5", "pct_chg", "turnover_rate", "volume_ratio"]:
            x[c] = pd.to_numeric(x[c], errors="coerce")

        # 三大过滤条件
        trend_ok = (x["close"] > x["ma20"]) & (x["ma20_slope5"] > 0)
        start_ok = (x["pct_chg"].between(3, 7)) & (x["vol"] > x["vol_ma5"] * 1.8)
        turnover_ok = x["turnover_rate"].between(5, 20)
        x = x[trend_ok & start_ok & turnover_ok].copy()
        if x.empty:
            return x

        # 评分：倾向于“强启动但不过热”
        x["vol_boost"] = (x["vol"] / x["vol_ma5"]).clip(1.0, 4.0)
        x["turnover_mid"] = 1 - ((x["turnover_rate"] - 10).abs() / 10).clip(0, 1)
        x["score"] = (
            45 * (x["vol_boost"] - 1) / 3
            + 35 * (x["pct_chg"].clip(3, 7) - 3) / 4
            + 20 * x["turnover_mid"]
        )
        x = x.sort_values("score", ascending=False).head(self.top_n).copy()

        next_day = self._next_trade_date(as_of_date) or "NEXT_TRADE_DAY_UNKNOWN"
        x["signal_date"] = as_of_date
        x["entry_date"] = next_day
        x["entry_rule"] = "next_open<=prev_close*1.03 AND next_low>=prev_avg_price_proxy"
        x["entry_price_ref"] = x["close"].round(2)
        x["stop_loss_pct"] = -4.0
        x["max_hold_days"] = 5
        x["time_exit_day"] = 4
        x["momentum_exit_rule"] = "daily_vol < prev_day_vol*0.7"

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
            "vol_boost",
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
        out_file = output_dir / f"capital_diffusion_3_5d_{as_of_date}.csv"
        self.calculate(as_of_date).to_csv(out_file, index=False, encoding="utf-8-sig")
        return out_file
