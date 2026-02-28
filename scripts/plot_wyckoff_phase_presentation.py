"""
Wyckoff 演示增强图（中文汇报版）

特点：
- 阶段背景色 + 阶段切换箭头标注
- Spring / SOS 事件标注
- 量价关系面板
- 吸筹评分阈值（60/80）
- 右上角最新结论信息框
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="绘制 Wyckoff 演示增强图")
    p.add_argument("--ts-code", type=str, default="600030.SH", help="股票代码")
    p.add_argument("--phase-csv", type=str, default=None, help="phase信号CSV")
    p.add_argument("--latest-json", type=str, default=None, help="最新评估JSON")
    p.add_argument("--lookback-days", type=int, default=700, help="展示最近N日")
    p.add_argument("--output", type=str, default=None, help="输出图片路径")
    return p.parse_args()


def setup_cn_font() -> None:
    mpl.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Heiti SC",
        "STHeiti",
        "Hiragino Sans GB",
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "WenQuanYi Zen Hei",
        "DejaVu Sans",
    ]
    mpl.rcParams["axes.unicode_minus"] = False


def phase_cn(phase: str) -> str:
    return {
        "A": "A 停跌",
        "B": "B 吸筹震荡",
        "C": "C Spring测试",
        "D": "D SOS确认",
        "E": "E 上涨阶段",
    }.get(str(phase), str(phase))


def phase_color(phase: str) -> str:
    return {
        "A": "#9e9e9e",
        "B": "#64b5f6",
        "C": "#ffb74d",
        "D": "#81c784",
        "E": "#ef5350",
    }.get(str(phase), "#cfd8dc")


def build_phase_legend_handles() -> list[Patch]:
    return [
        Patch(facecolor=phase_color("A"), edgecolor="none", alpha=0.35, label="A 停跌"),
        Patch(facecolor=phase_color("B"), edgecolor="none", alpha=0.35, label="B 吸筹震荡"),
        Patch(facecolor=phase_color("C"), edgecolor="none", alpha=0.35, label="C Spring测试"),
        Patch(facecolor=phase_color("D"), edgecolor="none", alpha=0.35, label="D SOS确认"),
        Patch(facecolor=phase_color("E"), edgecolor="none", alpha=0.35, label="E 上涨阶段"),
    ]


def phase_transition_points(df: pd.DataFrame) -> pd.DataFrame:
    s = df["phase"].astype(str)
    changed = s != s.shift(1)
    return df[changed].copy()


def load_latest(latest_file: Path) -> dict:
    if latest_file.exists():
        with open(latest_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def main() -> None:
    args = parse_args()
    setup_cn_font()

    ts_code = args.ts_code.strip().upper()
    phase_csv = Path(args.phase_csv) if args.phase_csv else Path(f"report/wyckoff_ai/{ts_code}_wyckoff_phase_signals.csv")
    latest_json = Path(args.latest_json) if args.latest_json else Path(f"report/wyckoff_ai/{ts_code}_wyckoff_latest.json")
    output = Path(args.output) if args.output else Path(f"report/wyckoff_ai/{ts_code}_wyckoff_presentation.png")

    df = pd.read_csv(phase_csv, encoding="utf-8-sig")
    if df.empty:
        raise RuntimeError(f"无数据: {phase_csv}")

    df["trade_dt"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    for c in ["close", "volume", "accumulation_score", "spring", "sos"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["phase"] = df["phase"].astype(str)
    df = df.dropna(subset=["trade_dt", "close"]).sort_values("trade_dt").reset_index(drop=True)
    df = df.tail(args.lookback_days).reset_index(drop=True)

    df["vol_ma20"] = df["volume"].rolling(20, min_periods=5).mean()
    df["price_ret_5"] = df["close"].pct_change(5)
    df["vol_ret_5"] = df["volume"].pct_change(5)

    latest = load_latest(latest_json)

    fig = plt.figure(figsize=(18, 11))
    gs = fig.add_gridspec(3, 1, height_ratios=[3.3, 1.3, 1.4], hspace=0.08)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)
    ax3 = fig.add_subplot(gs[2, 0], sharex=ax1)

    x = df["trade_dt"]

    # 阶段背景
    phases = df["phase"].tolist()
    start = 0
    for i in range(1, len(df) + 1):
        if i == len(df) or phases[i] != phases[start]:
            p = phases[start]
            ax1.axvspan(x.iloc[start], x.iloc[i - 1], color=phase_color(p), alpha=0.11, lw=0)
            start = i

    # 价格主图
    ax1.plot(x, df["close"], color="#0d47a1", lw=1.8, label="收盘价")
    ax1.set_title(f"{ts_code} Wyckoff 阶段结构演示图（量价+阶段+信号）", fontsize=15, pad=12)
    ax1.set_ylabel("价格")
    ax1.grid(alpha=0.2)

    # Spring / SOS
    sp = df[df["spring"] == 1]
    so = df[df["sos"] == 1]
    if not sp.empty:
        ax1.scatter(sp["trade_dt"], sp["close"], s=60, marker="v", color="#fb8c00", label="Spring", zorder=4)
    if not so.empty:
        ax1.scatter(so["trade_dt"], so["close"], s=60, marker="^", color="#2e7d32", label="SOS", zorder=4)

    # 阶段切换标注（最多最近12个，防止太密）
    trans = phase_transition_points(df).tail(12)
    ymax = float(df["close"].max())
    for _, row in trans.iterrows():
        label = phase_cn(row["phase"])
        ax1.annotate(
            label,
            xy=(row["trade_dt"], row["close"]),
            xytext=(0, 16),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="#263238",
            arrowprops=dict(arrowstyle="-|>", color="#607d8b", lw=0.8, alpha=0.8),
        )
    ax1.set_ylim(df["close"].min() * 0.92, ymax * 1.10)
    ax1.legend(loc="upper left")

    # Phase 背景色图例（颜色说明）
    phase_legend = ax1.legend(
        handles=build_phase_legend_handles(),
        title="Phase背景色",
        loc="upper center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=5,
        fontsize=9,
        title_fontsize=10,
        frameon=True,
    )
    ax1.add_artist(phase_legend)

    # 量能
    ax2.bar(x, df["volume"], color="#90a4ae", alpha=0.75, width=1.0, label="成交量")
    ax2.plot(x, df["vol_ma20"], color="#ef6c00", lw=1.2, label="20日均量")
    ax2.set_ylabel("成交量")
    ax2.grid(alpha=0.2)
    ax2.legend(loc="upper left")

    # 量价关系 + 吸筹分
    ax3.plot(x, df["price_ret_5"], color="#1e88e5", lw=1.2, label="5日价格变化率")
    ax3.plot(x, df["vol_ret_5"], color="#8e24aa", lw=1.2, label="5日成交量变化率")
    ax3.axhline(0, color="#616161", lw=1)
    ax3.set_ylabel("量价变化率")
    ax3.grid(alpha=0.2)

    ax3r = ax3.twinx()
    ax3r.plot(x, df["accumulation_score"], color="#d32f2f", lw=1.5, label="吸筹评分")
    ax3r.axhline(60, color="#f57c00", ls="--", lw=1, alpha=0.7)
    ax3r.axhline(80, color="#d32f2f", ls="--", lw=1, alpha=0.7)
    ax3r.set_ylabel("吸筹评分(0-100)")

    l1, lb1 = ax3.get_legend_handles_labels()
    l2, lb2 = ax3r.get_legend_handles_labels()
    ax3.legend(l1 + l2, lb1 + lb2, loc="upper left")

    # 最新结论框
    if latest:
        txt = (
            f"最新日期: {latest.get('trade_date', '-')}\n"
            f"阶段: {phase_cn(str(latest.get('phase', '-')))}\n"
            f"吸筹评分: {latest.get('accumulation_score', '-')}\n"
            f"Spring: {latest.get('spring', '-')}\n"
            f"SOS: {latest.get('sos', '-')}\n"
            f"分钟入场: {latest.get('minute_entry', {}).get('entry_ready', '-')}"
        )
        ax1.text(
            0.985,
            0.98,
            txt,
            transform=ax1.transAxes,
            va="top",
            ha="right",
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.45", fc="#ffffff", ec="#90a4ae", alpha=0.92),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"output={output}")
    print(f"rows={len(df)}")


if __name__ == "__main__":
    main()
