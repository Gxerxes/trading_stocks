"""
生成 Wyckoff 展示图（中文）：价格+成交量+量价关系+Phase 标注。

示例：
python scripts/plot_wyckoff_phase_showcase.py --ts-code 600030.SH
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="绘制 Wyckoff Phase 中文展示图")
    p.add_argument("--ts-code", type=str, default="600030.SH", help="股票代码")
    p.add_argument(
        "--phase-csv",
        type=str,
        default=None,
        help="phase 信号CSV路径，默认 report/wyckoff_ai/{ts_code}_wyckoff_phase_signals.csv",
    )
    p.add_argument("--lookback-days", type=int, default=500, help="展示最近N个交易日")
    p.add_argument(
        "--out-file",
        type=str,
        default=None,
        help="输出图片路径，默认 report/wyckoff_ai/{ts_code}_wyckoff_showcase.png",
    )
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
    mapping = {
        "A": "A 停跌",
        "B": "B 吸筹震荡",
        "C": "C Spring测试",
        "D": "D SOS确认",
        "E": "E 上涨阶段",
        "UNKNOWN": "未知",
    }
    return mapping.get(str(phase), str(phase))


def phase_color(phase: str) -> str:
    return {
        "A": "#9e9e9e",
        "B": "#64b5f6",
        "C": "#ffb74d",
        "D": "#81c784",
        "E": "#ef5350",
    }.get(str(phase), "#cfd8dc")


def main() -> None:
    args = parse_args()
    setup_cn_font()

    ts_code = args.ts_code.strip().upper()
    phase_csv = Path(args.phase_csv) if args.phase_csv else Path(f"report/wyckoff_ai/{ts_code}_wyckoff_phase_signals.csv")
    out_file = Path(args.out_file) if args.out_file else Path(f"report/wyckoff_ai/{ts_code}_wyckoff_showcase.png")

    df = pd.read_csv(phase_csv, encoding="utf-8-sig")
    if df.empty:
        raise RuntimeError(f"无数据: {phase_csv}")

    df["trade_dt"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["accumulation_score"] = pd.to_numeric(df["accumulation_score"], errors="coerce")
    df["spring"] = pd.to_numeric(df["spring"], errors="coerce").fillna(0).astype(int)
    df["sos"] = pd.to_numeric(df["sos"], errors="coerce").fillna(0).astype(int)
    df = df.dropna(subset=["trade_dt", "close"]).sort_values("trade_dt").reset_index(drop=True)
    df = df.tail(args.lookback_days).reset_index(drop=True)

    df["vol_ma20"] = df["volume"].rolling(20, min_periods=5).mean()
    df["price_ret_5"] = df["close"].pct_change(5)
    df["vol_ret_5"] = df["volume"].pct_change(5)

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 1, height_ratios=[3.2, 1.4, 1.2], hspace=0.08)

    ax_price = fig.add_subplot(gs[0, 0])
    ax_vol = fig.add_subplot(gs[1, 0], sharex=ax_price)
    ax_rel = fig.add_subplot(gs[2, 0], sharex=ax_price)

    x = df["trade_dt"]

    # 背景按 phase 着色（连续段）
    phase_series = df["phase"].fillna("UNKNOWN").astype(str).tolist()
    start = 0
    for i in range(1, len(df) + 1):
        if i == len(df) or phase_series[i] != phase_series[start]:
            p = phase_series[start]
            ax_price.axvspan(
                x.iloc[start],
                x.iloc[i - 1],
                color=phase_color(p),
                alpha=0.12,
                lw=0,
            )
            mid = (start + i - 1) // 2
            ax_price.text(
                x.iloc[mid],
                df["close"].max() * 1.01,
                phase_cn(p),
                fontsize=9,
                ha="center",
                va="bottom",
                color="#263238",
            )
            start = i

    ax_price.plot(x, df["close"], color="#1565c0", lw=1.8, label="收盘价")

    # Spring / SOS 标记
    spr = df[df["spring"] == 1]
    sos = df[df["sos"] == 1]
    if not spr.empty:
        ax_price.scatter(spr["trade_dt"], spr["close"], marker="v", s=60, color="#fb8c00", label="Spring", zorder=4)
    if not sos.empty:
        ax_price.scatter(sos["trade_dt"], sos["close"], marker="^", s=60, color="#2e7d32", label="SOS", zorder=4)

    ax_price.set_title(f"{ts_code} Wyckoff 量价结构展示（含阶段标注）", fontsize=14, pad=10)
    ax_price.set_ylabel("价格")
    ax_price.grid(alpha=0.22)
    ax_price.legend(loc="upper left")

    # 成交量
    ax_vol.bar(x, df["volume"], color="#90a4ae", width=1.0, alpha=0.75, label="成交量")
    ax_vol.plot(x, df["vol_ma20"], color="#ef6c00", lw=1.2, label="20日均量")
    ax_vol.set_ylabel("成交量")
    ax_vol.grid(alpha=0.2)
    ax_vol.legend(loc="upper left")

    # 量价关系 + 吸筹分
    ax_rel.plot(x, df["price_ret_5"], color="#1e88e5", lw=1.2, label="5日价格变化率")
    ax_rel.plot(x, df["vol_ret_5"], color="#8e24aa", lw=1.2, label="5日成交量变化率")
    ax_rel.axhline(0, color="#616161", lw=1)
    ax_rel.set_ylabel("量价变化率")
    ax_rel.grid(alpha=0.2)

    ax_score = ax_rel.twinx()
    ax_score.plot(x, df["accumulation_score"], color="#d32f2f", lw=1.4, alpha=0.9, label="吸筹评分")
    ax_score.axhline(80, color="#d32f2f", ls="--", lw=1, alpha=0.6)
    ax_score.axhline(60, color="#f57c00", ls="--", lw=1, alpha=0.6)
    ax_score.set_ylabel("吸筹评分(0-100)")

    # 合并图例
    lines1, labels1 = ax_rel.get_legend_handles_labels()
    lines2, labels2 = ax_score.get_legend_handles_labels()
    ax_rel.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_file, dpi=160)
    plt.close(fig)

    print(f"output={out_file}")
    print(f"rows={len(df)}")


if __name__ == "__main__":
    main()

