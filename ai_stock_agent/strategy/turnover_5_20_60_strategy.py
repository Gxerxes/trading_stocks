"""
短线换手率策略（5+20+60）
"""

from pathlib import Path
from typing import List

import pandas as pd

from config.settings import (
    DAILY_BASIC_HISTORY_DIR,
    DAILY_HISTORY_DIR,
    DATA_DIR,
    STRATEGY_SIGNAL_DIR,
)


class Turnover5260Strategy:
    """5+20+60 短线策略（偏埋伏，不追高）"""

    def __init__(self, top_n: int = 20):
        self.top_n = top_n

    @staticmethod
    def _available_dates(prefix: str, folder: Path) -> List[str]:
        files = sorted(folder.glob(f"{prefix}_*.csv"))
        return [f.stem.split("_")[-1] for f in files]

    @staticmethod
    def _load_history(folder: Path, prefix: str, end_date: str, lookback_days: int = 80) -> pd.DataFrame:
        dates = [d for d in Turnover5260Strategy._available_dates(prefix, folder) if d <= end_date]
        dates = dates[-lookback_days:]
        if not dates:
            return pd.DataFrame()
        frames = []
        for d in dates:
            frames.append(pd.read_csv(folder / f"{prefix}_{d}.csv"))
        return pd.concat(frames, ignore_index=True)

    def calculate(self, as_of_date: str) -> pd.DataFrame:
        price_hist = self._load_history(DAILY_HISTORY_DIR, "daily", as_of_date, lookback_days=90)
        basic_hist = self._load_history(DAILY_BASIC_HISTORY_DIR, "daily_basic", as_of_date, lookback_days=90)
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
        price_hist["ret20"] = g["close"].transform(lambda s: s / s.shift(20) - 1)
        price_hist["ret60"] = g["close"].transform(lambda s: s / s.shift(60) - 1)

        bg = basic_hist.groupby("ts_code", group_keys=False)
        basic_hist["to5"] = bg["turnover_rate"].transform(lambda s: s.rolling(5, min_periods=5).mean())
        basic_hist["to20"] = bg["turnover_rate"].transform(lambda s: s.rolling(20, min_periods=20).mean())
        basic_hist["to5_prev"] = bg["to5"].shift(5)

        dt = pd.to_datetime(as_of_date, format="%Y%m%d")
        pl = price_hist[price_hist["trade_date"] == dt].copy()
        bl = basic_hist[basic_hist["trade_date"] == dt].copy()
        if pl.empty or bl.empty:
            return pd.DataFrame()

        x = pl.merge(
            bl[["ts_code", "turnover_rate", "volume_ratio", "to5", "to20", "to5_prev"]],
            on="ts_code",
            how="inner",
        ).merge(industry_df, on="ts_code", how="left")

        x["ret20"] = pd.to_numeric(x["ret20"], errors="coerce")
        x["ret60"] = pd.to_numeric(x["ret60"], errors="coerce")
        x["ma20"] = pd.to_numeric(x["ma20"], errors="coerce")
        x["close"] = pd.to_numeric(x["close"], errors="coerce")

        ind_strength = x.groupby("industry")["ret20"].mean().rename("ind_ret20").reset_index()
        x = x.merge(ind_strength, on="industry", how="left")

        ext = x["close"] / x["ma20"] - 1
        x["f_5"] = (x["to5"] > x["to20"] * 1.15) & (x["to5"] > x["to5_prev"]) & (x["turnover_rate"] > 2)
        x["f_20"] = (x["close"] > x["ma20"]) & ext.between(0.00, 0.05)
        x["f_60"] = (x["ret60"] > 0.05) & (x["ind_ret20"] > x["ind_ret20"].quantile(0.6))
        x["risk_ok"] = (x["ret20"] > -0.03) & (x["turnover_rate"] < 20)

        cand = x[x["f_5"] & x["f_20"] & x["f_60"] & x["risk_ok"]].copy()
        if cand.empty:
            return cand

        cand["score"] = (
            35 * (cand["to5"] / cand["to20"]).clip(0, 3) / 3
            + 25 * (cand["ret20"].clip(-0.1, 0.3) + 0.1) / 0.4
            + 20 * (cand["ret60"].clip(-0.1, 0.5) + 0.1) / 0.6
            + 20 * (cand["ind_ret20"].clip(-0.1, 0.3) + 0.1) / 0.4
        )
        cand = cand.sort_values("score", ascending=False).head(self.top_n).copy()

        cand["entry"] = (cand["ma20"] * 1.005).round(2)
        cand["stop_loss"] = (cand["ma20"] * 0.97).round(2)
        cand["tp1"] = (cand["entry"] * 1.06).round(2)
        cand["tp2"] = (cand["entry"] * 1.10).round(2)
        cand["rr_tp1"] = ((cand["tp1"] - cand["entry"]) / (cand["entry"] - cand["stop_loss"])).round(2)

        cols = [
            "ts_code",
            "name",
            "industry",
            "close",
            "turnover_rate",
            "to5",
            "to20",
            "ret20",
            "ret60",
            "entry",
            "stop_loss",
            "tp1",
            "tp2",
            "rr_tp1",
            "score",
        ]
        cand = cand[cols]
        cand = cand.rename(columns={"ret20": "ret20_pct", "ret60": "ret60_pct"})
        cand["ret20_pct"] = (cand["ret20_pct"] * 100).round(2)
        cand["ret60_pct"] = (cand["ret60_pct"] * 100).round(2)
        cand["as_of_date"] = as_of_date
        return cand

    def save(self, as_of_date: str, output_dir: Path = STRATEGY_SIGNAL_DIR) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        result = self.calculate(as_of_date)
        out_file = output_dir / f"turnover_5_20_60_{as_of_date}.csv"
        result.to_csv(out_file, index=False, encoding="utf-8-sig")
        return out_file
