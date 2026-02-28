"""
分析 512880(证券ETF) 价格与融资融券行为，并输出因子/信号/图表。

输入：
- ETF 价格CSV（支持 Investing 下载格式）
- 融资融券明细CSV（margin_detail_512880.SH_*.csv）

输出：
- 标准化价格数据: ai_stock_agent/data/etf/512880_formatted.csv
- 因子明细: report/etf_margin_analysis/512880_margin_factors.csv
- 最新信号: report/etf_margin_analysis/512880_latest_signal.json
- 图表: report/etf_margin_analysis/512880_margin_analysis.png
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析512880价格与融资融券行为")
    parser.add_argument(
        "--price-csv",
        type=str,
        default="ai_stock_agent/data/etf/512880 ETF Stock Price History.csv",
        help="ETF价格CSV路径（Investing格式或标准格式）",
    )
    parser.add_argument(
        "--margin-csv",
        type=str,
        default="ai_stock_agent/data/margin_detail/margin_detail_512880.SH_19900101_20260228.csv",
        help="融资融券明细CSV路径",
    )
    parser.add_argument(
        "--formatted-price-out",
        type=str,
        default="ai_stock_agent/data/etf/512880_formatted.csv",
        help="标准化价格CSV输出路径",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="report/etf_margin_analysis",
        help="分析输出目录",
    )
    return parser.parse_args()


def _parse_volume_text(v: object) -> float:
    if pd.isna(v):
        return np.nan
    s = str(v).strip().replace(",", "")
    if not s or s == "-":
        return np.nan
    unit = s[-1].upper()
    try:
        if unit == "B":
            return float(s[:-1]) * 1_000_000_000
        if unit == "M":
            return float(s[:-1]) * 1_000_000
        if unit == "K":
            return float(s[:-1]) * 1_000
        return float(s)
    except ValueError:
        return np.nan


def load_and_format_price(price_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(price_csv, encoding="utf-8-sig")
    df.columns = [c.strip().replace('"', "") for c in df.columns]

    # Investing风格: Date, Price, Open, High, Low, Vol., Change %
    if "Date" in df.columns:
        rename_map = {
            "Date": "trade_date",
            "Price": "close",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Vol.": "volume_text",
            "Change %": "change_pct_text",
        }
        df = df.rename(columns=rename_map)
        for c in ["close", "open", "high", "low"]:
            df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", ""), errors="coerce")
        df["volume"] = df["volume_text"].apply(_parse_volume_text)
        df["pct_chg"] = pd.to_numeric(
            df["change_pct_text"].astype(str).str.replace("%", ""),
            errors="coerce",
        )
        # 日期格式 MM/DD/YYYY
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%m/%d/%Y", errors="coerce")
    else:
        # 已标准化格式兜底
        if "trade_date" not in df.columns:
            raise ValueError("ETF价格CSV缺少日期列(Date 或 trade_date)")
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume", "pct_chg"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["trade_date", "close"]).copy()
    df["trade_date"] = df["trade_date"].dt.strftime("%Y%m%d")
    df = df.sort_values("trade_date").drop_duplicates("trade_date", keep="last").reset_index(drop=True)

    # 近似成交额（元）：收盘价 * 成交量
    if "volume" in df.columns:
        df["amount_est"] = df["close"] * df["volume"]

    keep_cols = [c for c in ["trade_date", "open", "high", "low", "close", "pct_chg", "volume", "amount_est"] if c in df.columns]
    return df[keep_cols]


def load_margin_detail(margin_csv: Path) -> pd.DataFrame:
    need_cols = [
        "trade_date",
        "ts_code",
        "name",
        "rzye",
        "rqye",
        "rzmre",
        "rqyl",
        "rzche",
        "rqchl",
        "rqmcl",
        "rzrqye",
    ]
    df = pd.read_csv(margin_csv, encoding="utf-8-sig")
    for c in need_cols:
        if c not in df.columns:
            df[c] = np.nan
    df = df[need_cols].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce").dt.strftime("%Y%m%d")
    num_cols = [c for c in need_cols if c not in ["trade_date", "ts_code", "name"]]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    return df.reset_index(drop=True)


def build_factors(price_df: pd.DataFrame, margin_df: pd.DataFrame) -> pd.DataFrame:
    df = pd.merge(price_df, margin_df, on="trade_date", how="inner")
    df = df.sort_values("trade_date").reset_index(drop=True)

    # 核心融资行为因子
    df["financing_net"] = df["rzmre"] - df["rzche"]
    df["financing_net_ma5"] = df["financing_net"].rolling(5).mean()
    df["rzye_slope_5d"] = df["rzye"].diff(5)
    df["rzye_ma10"] = df["rzye"].rolling(10).mean()
    df["rzye_acceleration"] = df["rzye"] - df["rzye_ma10"]

    # 杠杆拥挤度: 融资余额 / 当日成交额(近似)
    df["leverage_ratio"] = df["rzye"] / df["amount_est"].replace(0, np.nan)
    lr_mean20 = df["leverage_ratio"].rolling(20).mean()
    lr_std20 = df["leverage_ratio"].rolling(20).std(ddof=0)
    df["leverage_ratio_z20"] = (df["leverage_ratio"] - lr_mean20) / lr_std20.replace(0, np.nan)

    # 融资余额Z-score
    rz_mean20 = df["rzye"].rolling(20).mean()
    rz_std20 = df["rzye"].rolling(20).std(ddof=0)
    df["rzye_z20"] = (df["rzye"] - rz_mean20) / rz_std20.replace(0, np.nan)

    # 价格与趋势
    df["close_ma5"] = df["close"].rolling(5).mean()
    df["close_ma20"] = df["close"].rolling(20).mean()

    # 买点：融资净买入连续3天>0 + 站上MA5 + 融资余额创新20日新高
    net3_pos = df["financing_net"].rolling(3).apply(lambda x: 1.0 if np.all(x > 0) else 0.0, raw=True)
    df["net_buy_3d_pos"] = net3_pos.fillna(0).astype(int)
    df["rzye_new_high_20d"] = (df["rzye"] >= df["rzye"].rolling(20).max()).astype(int)
    df["buy_signal"] = (
        (df["net_buy_3d_pos"] == 1)
        & (df["close"] > df["close_ma5"])
        & (df["rzye_new_high_20d"] == 1)
    ).astype(int)

    # 卖点：价格创新20日新高，但融资余额低于前一日（融资背离）
    df["price_new_high_20d"] = (df["close"] >= df["close"].rolling(20).max()).astype(int)
    df["sell_signal"] = ((df["price_new_high_20d"] == 1) & (df["rzye"] < df["rzye"].shift(1))).astype(int)

    # 未来收益，用于后续建模评估
    df["future_return_3d"] = df["close"].shift(-3) / df["close"] - 1
    df["future_return_5d"] = df["close"].shift(-5) / df["close"] - 1

    return df


def generate_latest_signal(df: pd.DataFrame) -> dict:
    latest = df.iloc[-1]

    stage = "neutral"
    if latest.get("buy_signal", 0) == 1:
        stage = "accumulation_breakout"
    elif latest.get("sell_signal", 0) == 1:
        stage = "distribution_risk"
    elif pd.notna(latest.get("financing_net_ma5")) and latest["financing_net_ma5"] > 0 and latest.get("close", 0) > latest.get("close_ma20", np.inf):
        stage = "uptrend_with_leverage_support"
    elif pd.notna(latest.get("financing_net_ma5")) and latest["financing_net_ma5"] < 0:
        stage = "deleveraging"

    action = "HOLD"
    reason = []
    if latest.get("buy_signal", 0) == 1:
        action = "BUY_PULLBACK"
        reason.append("融资净买入连续3天为正")
        reason.append("价格站上MA5")
        reason.append("融资余额创新20日高")
    elif latest.get("sell_signal", 0) == 1:
        action = "REDUCE_OR_EXIT"
        reason.append("价格创新高但融资余额回落（融资背离）")
    else:
        if pd.notna(latest.get("financing_net_ma5")):
            if latest["financing_net_ma5"] > 0:
                reason.append("融资净买入5日均值为正")
            else:
                reason.append("融资净买入5日均值为负")

    return {
        "ts_code": str(latest.get("ts_code", "512880.SH")),
        "trade_date": str(latest.get("trade_date")),
        "stage": stage,
        "action": action,
        "close": float(latest.get("close", np.nan)),
        "financing_net": float(latest.get("financing_net", np.nan)),
        "financing_net_ma5": float(latest.get("financing_net_ma5", np.nan)),
        "rzye": float(latest.get("rzye", np.nan)),
        "rzye_slope_5d": float(latest.get("rzye_slope_5d", np.nan)),
        "leverage_ratio": float(latest.get("leverage_ratio", np.nan)) if pd.notna(latest.get("leverage_ratio", np.nan)) else None,
        "leverage_ratio_z20": float(latest.get("leverage_ratio_z20", np.nan)) if pd.notna(latest.get("leverage_ratio_z20", np.nan)) else None,
        "rzye_acceleration": float(latest.get("rzye_acceleration", np.nan)) if pd.notna(latest.get("rzye_acceleration", np.nan)) else None,
        "reason": reason,
    }


def plot_analysis(df: pd.DataFrame, out_png: Path) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # Panel 1: 价格 + 均线 + 信号
    ax1 = axes[0]
    x = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    ax1.plot(x, df["close"], label="Close", color="#1f77b4", linewidth=1.6)
    ax1.plot(x, df["close_ma5"], label="MA5", color="#ff7f0e", linewidth=1.2)
    ax1.plot(x, df["close_ma20"], label="MA20", color="#2ca02c", linewidth=1.2)

    buy_pts = df[df["buy_signal"] == 1]
    sell_pts = df[df["sell_signal"] == 1]
    ax1.scatter(pd.to_datetime(buy_pts["trade_date"], format="%Y%m%d"), buy_pts["close"], marker="^", color="red", s=50, label="Buy Signal")
    ax1.scatter(pd.to_datetime(sell_pts["trade_date"], format="%Y%m%d"), sell_pts["close"], marker="v", color="black", s=40, label="Sell Signal")
    ax1.set_title("512880 Price & Signals")
    ax1.legend(loc="upper left")
    ax1.grid(alpha=0.25)

    # Panel 2: 融资余额 + 融资净买入
    ax2 = axes[1]
    ax2.plot(x, df["rzye"] / 1e8, label="RZYE (100m CNY)", color="#9467bd", linewidth=1.4)
    ax2_t = ax2.twinx()
    ax2_t.bar(x, df["financing_net"] / 1e8, label="Financing Net (100m CNY)", color="#17becf", alpha=0.35)
    ax2.set_title("Margin Financing Behavior")
    ax2.grid(alpha=0.25)

    # Panel 3: 拥挤度与Z-score
    ax3 = axes[2]
    ax3.plot(x, df["leverage_ratio_z20"], label="Leverage Ratio Z20", color="#d62728", linewidth=1.3)
    ax3.plot(x, df["rzye_z20"], label="RZYE Z20", color="#8c564b", linewidth=1.3)
    ax3.axhline(2.0, color="gray", linestyle="--", linewidth=1)
    ax3.axhline(-2.0, color="gray", linestyle="--", linewidth=1)
    ax3.set_title("Crowding / Extremes")
    ax3.legend(loc="upper left")
    ax3.grid(alpha=0.25)

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=140)
    plt.close(fig)


def main() -> None:
    args = parse_args()

    price_csv = Path(args.price_csv)
    margin_csv = Path(args.margin_csv)
    formatted_price_out = Path(args.formatted_price_out)
    out_dir = Path(args.out_dir)

    price_df = load_and_format_price(price_csv)
    margin_df = load_margin_detail(margin_csv)
    factor_df = build_factors(price_df, margin_df)

    formatted_price_out.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    price_df.to_csv(formatted_price_out, index=False, encoding="utf-8-sig")

    factor_out = out_dir / "512880_margin_factors.csv"
    factor_df.to_csv(factor_out, index=False, encoding="utf-8-sig")

    signal = generate_latest_signal(factor_df)
    signal_out = out_dir / "512880_latest_signal.json"
    with open(signal_out, "w", encoding="utf-8") as f:
        json.dump(signal, f, ensure_ascii=False, indent=2)

    png_out = out_dir / "512880_margin_analysis.png"
    plot_analysis(factor_df, png_out)

    print(f"formatted_price={formatted_price_out}")
    print(f"factor_file={factor_out}")
    print(f"signal_file={signal_out}")
    print(f"chart_file={png_out}")
    print(f"rows={len(factor_df)}")
    print("latest_signal=")
    print(json.dumps(signal, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
