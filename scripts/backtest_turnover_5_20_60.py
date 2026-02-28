"""
回测 turnover_5_20_60_strategy

输出：
1) report/backtest/turnover_5_20_60_trades.csv
2) report/backtest/turnover_5_20_60_daily_summary.csv
3) report/backtest/turnover_5_20_60_summary.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DAILY_BASIC_HISTORY_DIR, DAILY_HISTORY_DIR, DATA_DIR, REPORT_DIR  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="回测 turnover_5_20_60 策略")
    parser.add_argument("--start-date", type=str, default="20250101", help="开始日期 YYYYMMDD")
    parser.add_argument("--end-date", type=str, default="20260227", help="结束日期 YYYYMMDD")
    parser.add_argument("--top-n", type=int, default=20, help="每日推荐数量")
    return parser.parse_args()


def load_history(folder: Path, prefix: str, start_date: str, end_date: str, cols: list[str]) -> pd.DataFrame:
    files = sorted(folder.glob(f"{prefix}_*.csv"))
    selected = []
    for f in files:
        d = f.stem.split("_")[-1]
        if start_date <= d <= end_date:
            selected.append(f)
    frames = [pd.read_csv(f, usecols=cols) for f in selected]
    if not frames:
        return pd.DataFrame(columns=cols)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    args = parse_args()
    out_dir = REPORT_DIR / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)

    price = load_history(
        DAILY_HISTORY_DIR,
        "daily",
        args.start_date,
        args.end_date,
        ["ts_code", "trade_date", "open", "high", "low", "close", "vol"],
    )
    basic = load_history(
        DAILY_BASIC_HISTORY_DIR,
        "daily_basic",
        args.start_date,
        args.end_date,
        ["ts_code", "trade_date", "turnover_rate", "volume_ratio"],
    )
    industry = pd.read_csv(DATA_DIR / "all_stocks_active_no_st_by_industry.csv", dtype={"ts_code": str})[
        ["ts_code", "name", "industry"]
    ].drop_duplicates("ts_code")

    if price.empty or basic.empty:
        raise RuntimeError("历史数据为空，无法回测")

    price["trade_date"] = price["trade_date"].astype(str)
    basic["trade_date"] = basic["trade_date"].astype(str)
    price = price.sort_values(["ts_code", "trade_date"])
    basic = basic.sort_values(["ts_code", "trade_date"])

    g = price.groupby("ts_code", group_keys=False)
    price["ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    price["ret20"] = g["close"].transform(lambda s: s / s.shift(20) - 1)
    price["ret60"] = g["close"].transform(lambda s: s / s.shift(60) - 1)

    bg = basic.groupby("ts_code", group_keys=False)
    basic["to5"] = bg["turnover_rate"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    basic["to20"] = bg["turnover_rate"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    basic["to5_prev"] = bg["to5"].shift(5)

    data = price.merge(
        basic[["ts_code", "trade_date", "turnover_rate", "volume_ratio", "to5", "to20", "to5_prev"]],
        on=["ts_code", "trade_date"],
        how="inner",
    ).merge(industry, on="ts_code", how="left")

    data["ind_ret20"] = data.groupby(["trade_date", "industry"])["ret20"].transform("mean")
    data["ind_quantile60"] = data.groupby("trade_date")["ind_ret20"].transform(lambda x: x.quantile(0.6))
    ext = data["close"] / data["ma20"] - 1

    data["f_5"] = (data["to5"] > data["to20"] * 1.15) & (data["to5"] > data["to5_prev"]) & (data["turnover_rate"] > 2)
    data["f_20"] = (data["close"] > data["ma20"]) & ext.between(0.00, 0.05)
    data["f_60"] = (data["ret60"] > 0.05) & (data["ind_ret20"] > data["ind_quantile60"])
    data["risk_ok"] = (data["ret20"] > -0.03) & (data["turnover_rate"] < 20)

    data["score"] = (
        35 * (data["to5"] / data["to20"]).clip(0, 3) / 3
        + 25 * (data["ret20"].clip(-0.1, 0.3) + 0.1) / 0.4
        + 20 * (data["ret60"].clip(-0.1, 0.5) + 0.1) / 0.6
        + 20 * (data["ind_ret20"].clip(-0.1, 0.3) + 0.1) / 0.4
    )

    candidates = data[data["f_5"] & data["f_20"] & data["f_60"] & data["risk_ok"]].copy()
    candidates["entry"] = (candidates["ma20"] * 1.005).round(2)
    candidates["stop_loss"] = (candidates["ma20"] * 0.97).round(2)
    candidates["tp1"] = (candidates["entry"] * 1.06).round(2)
    candidates["tp2"] = (candidates["entry"] * 1.10).round(2)

    candidates = candidates.sort_values(["trade_date", "score"], ascending=[True, False])
    candidates["rank"] = candidates.groupby("trade_date").cumcount() + 1
    picks = candidates[candidates["rank"] <= args.top_n].copy()

    trade_dates = sorted(data["trade_date"].unique())
    next_map = {trade_dates[i]: trade_dates[i + 1] for i in range(len(trade_dates) - 1)}
    picks["next_trade_date"] = picks["trade_date"].map(next_map)
    picks = picks.dropna(subset=["next_trade_date"])

    next_px = price[["ts_code", "trade_date", "open", "high", "low", "close"]].rename(
        columns={
            "trade_date": "next_trade_date",
            "open": "next_open",
            "high": "next_high",
            "low": "next_low",
            "close": "next_close",
        }
    )
    trades = picks.merge(next_px, on=["ts_code", "next_trade_date"], how="left")
    trades = trades.dropna(subset=["next_close"])

    trades["filled"] = trades["next_high"] >= trades["entry"]
    trades["win_close"] = trades["filled"] & (trades["next_close"] > trades["entry"])
    trades["tp1_hit"] = trades["filled"] & (trades["next_high"] >= trades["tp1"])
    trades["stop_hit"] = trades["filled"] & (trades["next_low"] <= trades["stop_loss"])
    trades["next_ret_pct"] = ((trades["next_close"] - trades["entry"]) / trades["entry"] * 100).round(2)

    keep_cols = [
        "trade_date",
        "next_trade_date",
        "ts_code",
        "name",
        "industry",
        "score",
        "rank",
        "entry",
        "stop_loss",
        "tp1",
        "tp2",
        "next_open",
        "next_high",
        "next_low",
        "next_close",
        "filled",
        "win_close",
        "tp1_hit",
        "stop_hit",
        "next_ret_pct",
    ]
    trades = trades[keep_cols].sort_values(["trade_date", "rank"])

    daily = trades.groupby("trade_date").agg(
        picks=("ts_code", "count"),
        filled=("filled", "sum"),
        wins=("win_close", "sum"),
        tp1_hits=("tp1_hit", "sum"),
        stop_hits=("stop_hit", "sum"),
        avg_next_ret_pct=("next_ret_pct", "mean"),
    ).reset_index()
    daily["win_rate_filled"] = (daily["wins"] / daily["filled"]).fillna(0)
    daily["fill_rate"] = (daily["filled"] / daily["picks"]).fillna(0)

    total_picks = int(len(trades))
    total_filled = int(trades["filled"].sum())
    total_wins = int(trades["win_close"].sum())
    total_tp1 = int(trades["tp1_hit"].sum())
    total_stop = int(trades["stop_hit"].sum())

    summary = {
        "strategy": "turnover_5_20_60",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "top_n": args.top_n,
        "trade_days": int(daily["trade_date"].nunique()),
        "total_recommendations": total_picks,
        "total_filled": total_filled,
        "fill_rate": round(total_filled / total_picks, 4) if total_picks else 0,
        "wins_on_filled": total_wins,
        "win_rate_on_filled": round(total_wins / total_filled, 4) if total_filled else 0,
        "tp1_hit_rate_on_filled": round(total_tp1 / total_filled, 4) if total_filled else 0,
        "stop_hit_rate_on_filled": round(total_stop / total_filled, 4) if total_filled else 0,
        "avg_next_ret_pct_on_filled": round(
            float(trades.loc[trades["filled"], "next_ret_pct"].mean()) if total_filled else 0, 4
        ),
    }

    trades_path = out_dir / "turnover_5_20_60_trades.csv"
    daily_path = out_dir / "turnover_5_20_60_daily_summary.csv"
    summary_path = out_dir / "turnover_5_20_60_summary.json"
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")
    daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"trades_file={trades_path}")
    print(f"daily_file={daily_path}")
    print(f"summary_file={summary_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
