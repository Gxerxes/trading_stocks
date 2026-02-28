"""
可视化指数成分股变化（基于 index_weight 格式化明细）。

输入示例：
ai_stock_agent/data/index_weight/399975.SZ_components_by_date_20160831_20260227.csv

输出：
- top_weight_timeseries.png     Top成分股权重时序
- constituent_turnover.png      每次调仓新增/剔除数量
- constituent_turnover.csv      每次调仓变更明细
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="绘制指数成分变化图")
    parser.add_argument(
        "--input-csv",
        type=str,
        default="ai_stock_agent/data/index_weight/399975.SZ_components_by_date_20160831_20260227.csv",
        help="格式化后的指数成分明细CSV",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=12,
        help="按平均权重选取前N个成分股用于权重时序图",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="report/index_weight_analysis",
        help="输出目录",
    )
    return parser.parse_args()


def configure_matplotlib_fonts() -> None:
    # 中文显示优先级：macOS -> Windows -> Linux 常见字体
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


def build_turnover(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["trade_date"] = work["trade_date"].astype(str)
    work["con_code"] = work["con_code"].astype(str)
    dates = sorted(work["trade_date"].unique().tolist())
    rows: list[dict] = []

    prev_set: set[str] | None = None
    for d in dates:
        cur_set = set(work.loc[work["trade_date"] == d, "con_code"].tolist())
        if prev_set is None:
            rows.append(
                {
                    "trade_date": d,
                    "component_count": len(cur_set),
                    "added_count": 0,
                    "removed_count": 0,
                }
            )
        else:
            added = cur_set - prev_set
            removed = prev_set - cur_set
            rows.append(
                {
                    "trade_date": d,
                    "component_count": len(cur_set),
                    "added_count": len(added),
                    "removed_count": len(removed),
                }
            )
        prev_set = cur_set

    return pd.DataFrame(rows)


def plot_top_weight_timeseries(df: pd.DataFrame, top_n: int, out_file: Path) -> None:
    work = df.copy()
    work["trade_date_dt"] = pd.to_datetime(work["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    work["weight"] = pd.to_numeric(work["weight"], errors="coerce")

    avg_weight = work.groupby("con_code", as_index=False)["weight"].mean().sort_values("weight", ascending=False)
    top_codes = avg_weight.head(top_n)["con_code"].tolist()
    top_df = work[work["con_code"].isin(top_codes)].copy()

    # 图例优先使用股票名称，缺失时回退为代码
    if "name" in work.columns:
        name_map = (
            work[["con_code", "name"]]
            .dropna(subset=["con_code"])
            .drop_duplicates(subset=["con_code"], keep="last")
            .set_index("con_code")["name"]
            .to_dict()
        )
    else:
        name_map = {}

    pivot = (
        top_df.pivot_table(index="trade_date_dt", columns="con_code", values="weight", aggfunc="last")
        .sort_index()
    )

    plt.figure(figsize=(14, 7))
    for code in pivot.columns:
        raw_name = name_map.get(code, "")
        label = str(raw_name).strip() if pd.notna(raw_name) else ""
        if not label:
            label = code
        plt.plot(pivot.index, pivot[code], linewidth=1.5, label=label)

    plt.title(f"Index Components Weight Trend (Top {len(pivot.columns)} by Avg Weight)")
    plt.xlabel("Trade Date")
    plt.ylabel("Weight")
    plt.grid(alpha=0.25)
    plt.legend(ncol=3, fontsize=8, loc="upper left")
    plt.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=140)
    plt.close()


def plot_turnover(turnover_df: pd.DataFrame, out_file: Path) -> None:
    work = turnover_df.copy()
    work["trade_date_dt"] = pd.to_datetime(work["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    work = work.sort_values("trade_date_dt")

    plt.figure(figsize=(14, 6))
    plt.bar(work["trade_date_dt"], work["added_count"], width=20, label="Added", alpha=0.75)
    plt.bar(work["trade_date_dt"], -work["removed_count"], width=20, label="Removed", alpha=0.75)
    plt.axhline(0, color="black", linewidth=1)
    plt.title("Component Turnover per Rebalance Date")
    plt.xlabel("Trade Date")
    plt.ylabel("Count (+Added / -Removed)")
    plt.legend()
    plt.grid(alpha=0.25)
    plt.tight_layout()
    out_file.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_file, dpi=140)
    plt.close()


def main() -> None:
    args = parse_args()
    configure_matplotlib_fonts()

    input_csv = Path(args.input_csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv, encoding="utf-8-sig")
    needed = {"trade_date", "index_code", "con_code", "weight"}
    if not needed.issubset(df.columns):
        raise ValueError(f"输入文件缺少字段，至少需要: {sorted(needed)}")

    turnover_df = build_turnover(df)
    turnover_csv = out_dir / "constituent_turnover.csv"
    turnover_df.to_csv(turnover_csv, index=False, encoding="utf-8-sig")

    top_png = out_dir / "top_weight_timeseries.png"
    turnover_png = out_dir / "constituent_turnover.png"

    plot_top_weight_timeseries(df, args.top_n, top_png)
    plot_turnover(turnover_df, turnover_png)

    print(f"input={input_csv}")
    print(f"top_weight_chart={top_png}")
    print(f"turnover_chart={turnover_png}")
    print(f"turnover_csv={turnover_csv}")
    print(f"dates={df['trade_date'].nunique()} components={df['con_code'].nunique()} rows={len(df)}")


if __name__ == "__main__":
    main()
