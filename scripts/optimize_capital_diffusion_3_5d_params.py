"""
为 capital_diffusion_3_5d 策略做参数网格搜索（以胜率优先）

输出：
- report/backtest/capital_diffusion_3_5d_param_search.csv
- report/backtest/capital_diffusion_3_5d_best_params.json
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DAILY_BASIC_HISTORY_DIR, DAILY_HISTORY_DIR, DATA_DIR, REPORT_DIR  # noqa: E402


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


def prepare_data(start_date: str, end_date: str):
    price = load_history(
        DAILY_HISTORY_DIR,
        "daily",
        start_date,
        end_date,
        ["ts_code", "trade_date", "open", "high", "low", "close", "vol", "pct_chg"],
    )
    basic = load_history(
        DAILY_BASIC_HISTORY_DIR,
        "daily_basic",
        start_date,
        end_date,
        ["ts_code", "trade_date", "turnover_rate", "volume_ratio"],
    )
    industry = pd.read_csv(DATA_DIR / "all_stocks_active_no_st_by_industry.csv", dtype={"ts_code": str})[
        ["ts_code", "name", "industry"]
    ].drop_duplicates("ts_code")

    price["trade_date"] = price["trade_date"].astype(str)
    basic["trade_date"] = basic["trade_date"].astype(str)
    price = price.sort_values(["ts_code", "trade_date"])
    basic = basic.sort_values(["ts_code", "trade_date"])

    g = price.groupby("ts_code", group_keys=False)
    price["ma20"] = g["close"].transform(lambda s: s.rolling(20, min_periods=20).mean())
    price["ma20_slope5"] = g["ma20"].transform(lambda s: s - s.shift(5))
    price["vol_ma5"] = g["vol"].transform(lambda s: s.rolling(5, min_periods=5).mean())
    price["avg_price_proxy"] = (price["open"] + price["high"] + price["low"] + price["close"]) / 4

    data = price.merge(basic, on=["ts_code", "trade_date"], how="inner").merge(industry, on="ts_code", how="left")
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
    return data, dates, idx, px_map


def run_backtest(data: pd.DataFrame, dates: list[str], idx: dict[str, int], px_map: dict, params: dict) -> dict:
    cond = (
        (data["close"] > data["ma20"])
        & (data["ma20_slope5"] > 0)
        & (data["pct_chg"].between(params["pct_low"], params["pct_high"]))
        & (data["vol"] > data["vol_ma5"] * params["vol_mult"])
        & (data["turnover_rate"].between(params["turnover_min"], params["turnover_max"]))
    )
    sig = data[cond].copy()
    if sig.empty:
        return {}

    sig["vol_boost"] = (sig["vol"] / sig["vol_ma5"]).clip(1.0, 4.0)
    sig["turnover_mid"] = 1 - ((sig["turnover_rate"] - 10).abs() / 10).clip(0, 1)
    sig["score"] = 45 * (sig["vol_boost"] - 1) / 3 + 35 * (sig["pct_chg"] - params["pct_low"]) / (params["pct_high"] - params["pct_low"]) + 20 * sig["turnover_mid"]
    sig = sig.sort_values(["trade_date", "score"], ascending=[True, False])
    sig["rank"] = sig.groupby("trade_date").cumcount() + 1
    sig = sig[sig["rank"] <= params["top_n"]].copy()

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

        if not (d1_px["open"] <= r["close"] * 1.03 and d1_px["low"] >= r["avg_price_proxy"]):
            continue

        entry = float(d1_px["open"])
        stop = entry * (1 - params["stop_loss"])
        exit_price = None
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
                break
            if h >= 1 and px["vol"] < prev_vol * params["momentum_decay"]:
                exit_price = float(px["close"])
                break
            if hold_days == params["time_exit_day"]:
                exit_price = float(px["close"])
                break
            prev_vol = px["vol"]

        if exit_price is None:
            continue
        ret = (exit_price - entry) / entry
        trades.append(ret)

    if not trades:
        return {}
    s = pd.Series(trades)
    wins = (s > 0).sum()
    losses = (s < 0).sum()
    pf = (s[s > 0].sum() / abs(s[s < 0].sum())) if losses > 0 else None

    return {
        **params,
        "trades": int(len(s)),
        "win_rate": float((s > 0).mean()),
        "avg_return_pct": float(s.mean() * 100),
        "median_return_pct": float(s.median() * 100),
        "profit_factor_proxy": float(pf) if pf is not None else None,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="参数搜索（胜率优先）")
    p.add_argument("--mode", choices=["quick", "full"], default="quick")
    return p.parse_args()


def main():
    args = parse_args()
    start_date = "20250101"
    end_date = "20260227"
    out_dir = REPORT_DIR / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)

    data, dates, idx, px_map = prepare_data(start_date, end_date)

    if args.mode == "quick":
        grid = {
            "pct_low": [2.5, 3.0],
            "pct_high": [5.5, 6.0],
            "vol_mult": [1.6, 1.8],
            "turnover_min": [4.0, 5.0],
            "turnover_max": [15.0, 20.0],
            "stop_loss": [0.03, 0.04],
            "momentum_decay": [0.7, 0.8],
            "time_exit_day": [3, 4],
            "top_n": [8, 10],
        }
    else:
        grid = {
            "pct_low": [2.0, 2.5, 3.0],
            "pct_high": [5.0, 5.5, 6.0],
            "vol_mult": [1.6, 1.8, 2.0],
            "turnover_min": [4.0, 5.0, 6.0],
            "turnover_max": [15.0, 20.0],
            "stop_loss": [0.03, 0.04],
            "momentum_decay": [0.7, 0.8],
            "time_exit_day": [3, 4],
            "top_n": [8, 10],
        }

    keys = list(grid.keys())
    results = []
    for vals in itertools.product(*(grid[k] for k in keys)):
        p = dict(zip(keys, vals))
        if p["pct_high"] <= p["pct_low"]:
            continue
        if p["turnover_max"] <= p["turnover_min"]:
            continue
        res = run_backtest(data, dates, idx, px_map, p)
        if not res:
            continue
        results.append(res)

    if not results:
        raise RuntimeError("参数搜索无有效结果")

    df = pd.DataFrame(results)
    # 过滤太少交易，避免胜率虚高
    df_valid = df[df["trades"] >= 300].copy()
    if df_valid.empty:
        df_valid = df.copy()

    df_valid = df_valid.sort_values(
        ["win_rate", "avg_return_pct", "profit_factor_proxy", "trades"],
        ascending=[False, False, False, False],
    )
    best = df_valid.iloc[0].to_dict()

    search_file = out_dir / "capital_diffusion_3_5d_param_search.csv"
    best_file = out_dir / "capital_diffusion_3_5d_best_params.json"
    df.sort_values("win_rate", ascending=False).to_csv(search_file, index=False, encoding="utf-8-sig")
    best_file.write_text(json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"search_file={search_file}")
    print(f"best_file={best_file}")
    print(json.dumps(best, ensure_ascii=False))


if __name__ == "__main__":
    main()
