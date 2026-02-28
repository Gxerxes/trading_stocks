"""
资金扩散突破高胜率版回测（持仓3-5天）
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
    p = argparse.ArgumentParser(description="回测资金扩散突破高胜率版（3-5天）")
    p.add_argument("--start-date", type=str, default="20250101")
    p.add_argument("--end-date", type=str, default="20260227")
    p.add_argument("--top-n", type=int, default=10)
    return p.parse_args()


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
        ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "pct_chg", "amount"],
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
    price["ma20_slope5"] = g["ma20"].transform(lambda s: s - s.shift(5))
    price["vol_ma5"] = g["vol"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    price["ret5"] = g["close"].transform(lambda s: s / s.shift(5) - 1)
    price["ret20"] = g["close"].transform(lambda s: s / s.shift(20) - 1)
    price["pre_close_proxy"] = price["close"] / (1 + price["pct_chg"] / 100.0)
    price["amplitude_pct"] = ((price["high"] - price["low"]) / price["pre_close_proxy"]) * 100
    price["avg_price_proxy"] = (price["open"] + price["high"] + price["low"] + price["close"]) / 4

    data = price.merge(basic, on=["ts_code", "trade_date"], how="inner").merge(industry, on="ts_code", how="left")

    # 按日期计算市场广度、行业强度阈值
    data["breadth"] = data.groupby("trade_date").apply(lambda x: (x["close"] > x["ma20"]).mean()).reindex(data["trade_date"]).values
    ind = data.groupby(["trade_date", "industry"]).agg(ind_ret5=("ret5", "mean"), ind_ret20=("ret20", "mean")).reset_index()
    data = data.merge(ind, on=["trade_date", "industry"], how="left")
    data["q5"] = data.groupby("trade_date")["ind_ret5"].transform(lambda s: s.quantile(0.7))
    data["q20"] = data.groupby("trade_date")["ind_ret20"].transform(lambda s: s.quantile(0.7))

    cond = (
        (data["breadth"] >= 0.55)
        & (data["close"] > data["ma20"])
        & (data["ma20_slope5"] > 0)
        & (data["pct_chg"].between(2.5, 5.5))
        & (data["vol"] > data["vol_ma5"] * 1.8)
        & (data["turnover_rate"].between(6, 15))
        & (data["amplitude_pct"] <= 8)
        & (data["amount"] >= 200000)
        & (data["ind_ret5"] >= data["q5"])
        & (data["ind_ret20"] >= data["q20"])
    )
    sig = data[cond].copy()
    if sig.empty:
        raise RuntimeError("无信号，无法回测")

    sig["vol_boost"] = (sig["vol"] / sig["vol_ma5"]).clip(1.0, 4.0)
    sig["turnover_mid"] = 1 - ((sig["turnover_rate"] - 10).abs() / 10).clip(0, 1)
    sig["amp_score"] = (1 - (sig["amplitude_pct"] / 8).clip(0, 1)).fillna(0)
    sig["score"] = (
        35 * (sig["vol_boost"] - 1) / 3
        + 25 * (sig["pct_chg"].clip(2.5, 5.5) - 2.5) / 3
        + 20 * sig["turnover_mid"]
        + 20 * sig["amp_score"]
    )
    sig = sig.sort_values(["trade_date", "score"], ascending=[True, False])
    sig["rank"] = sig.groupby("trade_date").cumcount() + 1
    sig = sig[sig["rank"] <= args.top_n].copy()

    dates = sorted(data["trade_date"].unique())
    idx = {d: i for i, d in enumerate(dates)}

    px_map = {}
    for _, r in price.iterrows():
        px_map[(r["ts_code"], r["trade_date"])] = {
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "vol": r["vol"],
        }

    trades = []
    for _, r in sig.iterrows():
        ts = r["ts_code"]
        d0 = r["trade_date"]
        if d0 not in idx or idx[d0] + 1 >= len(dates):
            continue
        d1 = dates[idx[d0] + 1]
        d1_px = px_map.get((ts, d1))
        if d1_px is None:
            continue

        # 次日入场条件
        if not (d1_px["open"] <= r["close"] * 1.03 and d1_px["low"] >= r["avg_price_proxy"]):
            continue

        entry = float(d1_px["open"])
        stop = entry * 0.97  # 高胜率版更紧止损
        exit_price = None
        exit_date = None
        exit_reason = None
        hold_days = 0
        prev_vol = d1_px["vol"]

        for h in range(0, 5):
            if idx[d1] + h >= len(dates):
                break
            d = dates[idx[d1] + h]
            px = px_map.get((ts, d))
            if px is None:
                continue
            hold_days = h + 1

            if px["low"] <= stop:
                exit_price = stop
                exit_date = d
                exit_reason = "STOP_LOSS"
                break

            if h >= 1 and px["vol"] < prev_vol * 0.8:
                exit_price = float(px["close"])
                exit_date = d
                exit_reason = "MOMENTUM_DECAY"
                break

            if hold_days == 3:
                exit_price = float(px["close"])
                exit_date = d
                exit_reason = "TIME_EXIT_D3"
                break

            prev_vol = px["vol"]

        if exit_price is None:
            continue

        ret = (exit_price - entry) / entry
        trades.append(
            {
                "signal_date": d0,
                "entry_date": d1,
                "exit_date": exit_date,
                "ts_code": ts,
                "name": r.get("name", ""),
                "industry": r.get("industry", ""),
                "rank": int(r["rank"]),
                "score": float(r["score"]),
                "entry_price": round(entry, 4),
                "exit_price": round(exit_price, 4),
                "return_pct": round(ret * 100, 4),
                "hold_days": int(hold_days),
                "exit_reason": exit_reason,
                "win": ret > 0,
            }
        )

    trades_df = pd.DataFrame(trades).sort_values(["signal_date", "rank"])
    if trades_df.empty:
        raise RuntimeError("回测无成交记录")

    daily = trades_df.groupby("signal_date").agg(
        picks=("ts_code", "count"),
        wins=("win", "sum"),
        avg_ret_pct=("return_pct", "mean"),
        avg_hold_days=("hold_days", "mean"),
    ).reset_index()
    daily["win_rate"] = daily["wins"] / daily["picks"]

    summary = {
        "strategy": "capital_diffusion_3_5d_high_win",
        "start_date": args.start_date,
        "end_date": args.end_date,
        "top_n": args.top_n,
        "trades": int(len(trades_df)),
        "win_rate": round(float(trades_df["win"].mean()), 4),
        "avg_return_pct": round(float(trades_df["return_pct"].mean()), 4),
        "median_return_pct": round(float(trades_df["return_pct"].median()), 4),
        "avg_hold_days": round(float(trades_df["hold_days"].mean()), 4),
        "profit_factor_proxy": round(
            float(
                trades_df.loc[trades_df["return_pct"] > 0, "return_pct"].sum()
                / abs(trades_df.loc[trades_df["return_pct"] < 0, "return_pct"].sum())
            ),
            4,
        ) if (trades_df["return_pct"] < 0).any() else None,
    }

    trades_path = out_dir / "capital_diffusion_3_5d_high_win_trades.csv"
    daily_path = out_dir / "capital_diffusion_3_5d_high_win_daily_summary.csv"
    summary_path = out_dir / "capital_diffusion_3_5d_high_win_summary.json"
    trades_df.to_csv(trades_path, index=False, encoding="utf-8-sig")
    daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"trades_file={trades_path}")
    print(f"daily_file={daily_path}")
    print(f"summary_file={summary_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
