"""
可视化 turnover_5_20_60 回测结果

输入：
  report/backtest/turnover_5_20_60_trades.csv
  report/backtest/turnover_5_20_60_daily_summary.csv
  report/backtest/turnover_5_20_60_summary.json

输出：
  report/backtest/charts/*.png
"""

from __future__ import annotations

import json
from pathlib import Path
from matplotlib import font_manager

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path("report/backtest")
TRADES_FILE = BASE_DIR / "turnover_5_20_60_trades.csv"
DAILY_FILE = BASE_DIR / "turnover_5_20_60_daily_summary.csv"
SUMMARY_FILE = BASE_DIR / "turnover_5_20_60_summary.json"
OUT_DIR = BASE_DIR / "charts"

def _setup_chinese_font() -> None:
    candidates = [
        "PingFang SC",
        "Hiragino Sans GB",
        "Heiti SC",
        "STHeiti",
        "Arial Unicode MS",
        "Noto Sans CJK SC",
        "SimHei",
    ]
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _load_data():
    trades = pd.read_csv(TRADES_FILE)
    daily = pd.read_csv(DAILY_FILE)
    summary = json.loads(SUMMARY_FILE.read_text(encoding="utf-8"))

    trades["trade_date"] = pd.to_datetime(trades["trade_date"], format="%Y%m%d", errors="coerce")
    daily["trade_date"] = pd.to_datetime(daily["trade_date"], format="%Y%m%d", errors="coerce")
    trades = trades.dropna(subset=["trade_date"]).sort_values("trade_date")
    daily = daily.dropna(subset=["trade_date"]).sort_values("trade_date")
    return trades, daily, summary


def _plot_equity_curve(trades: pd.DataFrame) -> Path:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    eq = (
        filled.groupby("trade_date")["next_ret_pct"]
        .mean()
        .reset_index()
        .rename(columns={"next_ret_pct": "avg_ret"})
    )
    eq["cum_ret"] = (1 + eq["avg_ret"] / 100.0).cumprod() - 1

    plt.figure(figsize=(12, 5))
    plt.plot(eq["trade_date"], eq["cum_ret"] * 100, linewidth=1.5, color="#0a7")
    plt.title("Turnover 5-20-60 Backtest - Cumulative Return (Filled Trades)")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Return (%)")
    plt.grid(alpha=0.25)
    plt.tight_layout()
    out = OUT_DIR / "equity_curve.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def _plot_daily_stats(daily: pd.DataFrame) -> Path:
    d = daily.copy()
    d["win_rate_pct"] = d["win_rate_filled"] * 100
    d["fill_rate_pct"] = d["fill_rate"] * 100

    fig, ax1 = plt.subplots(figsize=(13, 5))
    ax1.plot(d["trade_date"], d["win_rate_pct"], label="Win Rate", color="#1f77b4", linewidth=1.2)
    ax1.plot(d["trade_date"], d["fill_rate_pct"], label="Fill Rate", color="#ff7f0e", linewidth=1.2)
    ax1.set_ylabel("Rate (%)")
    ax1.set_ylim(0, 100)
    ax1.grid(alpha=0.25)

    ax2 = ax1.twinx()
    ax2.bar(d["trade_date"], d["avg_next_ret_pct"], alpha=0.18, width=2.5, color="#2ca02c", label="Avg Next Ret")
    ax2.set_ylabel("Avg Next Return (%)")

    ax1.set_title("Daily Win/Fill Rate + Avg Next Return")
    ax1.set_xlabel("Date")
    ax1.legend(loc="upper left")
    plt.tight_layout()
    out = OUT_DIR / "daily_stats.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def _plot_monthly_heatmap(trades: pd.DataFrame) -> Path:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    filled["month"] = filled["trade_date"].dt.to_period("M").astype(str)
    m = (
        filled.groupby("month")
        .agg(
            avg_ret_pct=("next_ret_pct", "mean"),
            win_rate=("win_close", "mean"),
            count=("ts_code", "count"),
        )
        .reset_index()
    )
    m["win_rate_pct"] = m["win_rate"] * 100

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].bar(m["month"], m["avg_ret_pct"], color="#2ca02c", alpha=0.75)
    axes[0].set_ylabel("Avg Next Ret (%)")
    axes[0].set_title("Monthly Average Next-Day Return")
    axes[0].grid(axis="y", alpha=0.25)

    axes[1].bar(m["month"], m["win_rate_pct"], color="#1f77b4", alpha=0.75)
    axes[1].set_ylabel("Win Rate (%)")
    axes[1].set_title("Monthly Win Rate (Filled Trades)")
    axes[1].set_ylim(0, 100)
    axes[1].grid(axis="y", alpha=0.25)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = OUT_DIR / "monthly_performance.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def _plot_return_distribution(trades: pd.DataFrame) -> Path:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    r = filled["next_ret_pct"].dropna()

    plt.figure(figsize=(10, 5))
    plt.hist(r, bins=60, color="#9467bd", alpha=0.8)
    plt.axvline(r.mean(), color="red", linestyle="--", linewidth=1.2, label=f"Mean {r.mean():.2f}%")
    plt.axvline(0, color="black", linestyle="-", linewidth=0.8)
    plt.title("Distribution of Next-Day Return (Filled Trades)")
    plt.xlabel("Next-Day Return (%)")
    plt.ylabel("Frequency")
    plt.legend()
    plt.grid(alpha=0.2)
    plt.tight_layout()
    out = OUT_DIR / "return_distribution.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def _plot_top_symbols(trades: pd.DataFrame) -> Path:
    filled = trades[trades["filled"] == True].copy()  # noqa: E712
    s = (
        filled.groupby(["ts_code", "name"])
        .agg(
            picks=("ts_code", "count"),
            win_rate=("win_close", "mean"),
            avg_ret=("next_ret_pct", "mean"),
        )
        .reset_index()
    )
    s = s[s["picks"] >= 8].copy()
    s["score"] = s["win_rate"] * 0.6 + (s["avg_ret"] / 10.0) * 0.4
    s = s.sort_values("score", ascending=False).head(15)

    labels = [f"{r.ts_code}\n{r.name}" for r in s.itertuples()]
    plt.figure(figsize=(12, 6))
    plt.bar(labels, s["avg_ret"], color="#17becf", alpha=0.8)
    plt.title("Top Symbols by Avg Next-Day Return (min picks=8)")
    plt.ylabel("Avg Next Return (%)")
    plt.xticks(rotation=45, ha="right")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    out = OUT_DIR / "top_symbols_avg_return.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def _plot_summary_card(summary: dict) -> Path:
    lines = [
        "Turnover 5-20-60 Backtest Summary",
        f"Range: {summary['start_date']} ~ {summary['end_date']}",
        f"Top N: {summary['top_n']}",
        f"Trade Days: {summary['trade_days']}",
        f"Recommendations: {summary['total_recommendations']}",
        f"Filled: {summary['total_filled']} (Fill {summary['fill_rate'] * 100:.2f}%)",
        f"Win Rate (filled): {summary['win_rate_on_filled'] * 100:.2f}%",
        f"TP1 Hit Rate (filled): {summary['tp1_hit_rate_on_filled'] * 100:.2f}%",
        f"Stop Hit Rate (filled): {summary['stop_hit_rate_on_filled'] * 100:.2f}%",
        f"Avg Next Ret (filled): {summary['avg_next_ret_pct_on_filled']:.2f}%",
    ]

    plt.figure(figsize=(10, 5.5))
    plt.axis("off")
    plt.text(
        0.02,
        0.98,
        "\n".join(lines),
        va="top",
        ha="left",
        fontsize=12,
        family="monospace",
    )
    plt.tight_layout()
    out = OUT_DIR / "summary_card.png"
    plt.savefig(out, dpi=160)
    plt.close()
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _setup_chinese_font()
    trades, daily, summary = _load_data()

    outs = [
        _plot_equity_curve(trades),
        _plot_daily_stats(daily),
        _plot_monthly_heatmap(trades),
        _plot_return_distribution(trades),
        _plot_top_symbols(trades),
        _plot_summary_card(summary),
    ]

    for p in outs:
        print(p)


if __name__ == "__main__":
    main()
