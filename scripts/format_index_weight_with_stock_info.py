"""
将指数成分权重与股票主数据合并，生成按日期纵向排列的标准化明细表。

输入：
- all_stocks.csv
- index_weight CSV（如 399975.SZ_19900101_20260228.csv）

输出列（默认）：
- trade_date
- index_code
- con_code
- symbol
- name
- weight
- area
- industry
- market
- list_status
- list_date
- delist_date
- is_hs
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="格式化指数成分权重并关联股票信息")
    p.add_argument(
        "--all-stocks-csv",
        type=str,
        default="ai_stock_agent/data/all_stocks.csv",
        help="all_stocks.csv 路径",
    )
    p.add_argument(
        "--index-weight-csv",
        type=str,
        default="ai_stock_agent/data/index_weight/399975.SZ_19900101_20260228.csv",
        help="指数成分权重 CSV 路径",
    )
    p.add_argument(
        "--output-csv",
        type=str,
        default=None,
        help="输出 CSV 路径（可选）",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    all_stocks_path = Path(args.all_stocks_csv)
    index_weight_path = Path(args.index_weight_csv)

    stocks_df = pd.read_csv(all_stocks_path, encoding="utf-8-sig")
    weight_df = pd.read_csv(index_weight_path, encoding="utf-8-sig")

    required_weight_cols = ["index_code", "con_code", "trade_date", "weight"]
    missing_weight = [c for c in required_weight_cols if c not in weight_df.columns]
    if missing_weight:
        raise ValueError(f"指数权重文件缺少字段: {missing_weight}")

    required_stock_cols = [
        "ts_code",
        "symbol",
        "name",
        "area",
        "industry",
        "market",
        "list_status",
        "list_date",
        "delist_date",
        "is_hs",
    ]
    missing_stock = [c for c in required_stock_cols if c not in stocks_df.columns]
    if missing_stock:
        raise ValueError(f"all_stocks 文件缺少字段: {missing_stock}")

    stock_info = stocks_df[required_stock_cols].drop_duplicates(subset=["ts_code"], keep="last").copy()

    merged = weight_df.merge(stock_info, left_on="con_code", right_on="ts_code", how="left")
    merged = merged.drop(columns=["ts_code"])

    merged["trade_date"] = merged["trade_date"].astype(str)
    merged["weight"] = pd.to_numeric(merged["weight"], errors="coerce")
    merged = merged.sort_values(["trade_date", "index_code", "weight", "con_code"], ascending=[True, True, False, True])

    output_cols = [
        "trade_date",
        "index_code",
        "con_code",
        "symbol",
        "name",
        "weight",
        "area",
        "industry",
        "market",
        "list_status",
        "list_date",
        "delist_date",
        "is_hs",
    ]
    result = merged[output_cols].reset_index(drop=True)

    if args.output_csv:
        out_path = Path(args.output_csv)
    else:
        index_code = str(result["index_code"].iloc[0]) if not result.empty else "index"
        date_min = str(result["trade_date"].min()) if not result.empty else "NA"
        date_max = str(result["trade_date"].max()) if not result.empty else "NA"
        out_path = index_weight_path.parent / f"{index_code}_components_by_date_{date_min}_{date_max}.csv"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"output={out_path}")
    print(f"rows={len(result)}")
    if not result.empty:
        print(f"date_range={result['trade_date'].min()}~{result['trade_date'].max()}")
        print(f"columns={','.join(output_cols)}")


if __name__ == "__main__":
    main()
