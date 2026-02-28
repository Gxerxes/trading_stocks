"""
使用 BaoStock 下载沪深300成分股（hs300Stock）。

接口文档：
http://www.baostock.com/mainContent?file=hs300Stock.md

默认行为：
- 下载当前最新沪深300成分股快照

可选行为：
- 通过 start/end 区间按交易日下载历史快照，并合并保存

示例：
python scripts/download_hs300_stocks_baostock.py
python scripts/download_hs300_stocks_baostock.py --date 2026-02-27
python scripts/download_hs300_stocks_baostock.py --start-date 2026-02-01 --end-date 2026-02-28
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import baostock as bs
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载沪深300成分股（BaoStock）")
    parser.add_argument("--date", type=str, default=None, help="单日日期 YYYY-MM-DD")
    parser.add_argument("--start-date", type=str, default=None, help="区间开始 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="区间结束 YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ai_stock_agent/data/hs300",
        help="输出目录",
    )
    return parser.parse_args()


def fetch_hs300_for_date(date: str | None) -> pd.DataFrame:
    rs = bs.query_hs300_stocks(date=date or "")
    if rs.error_code != "0":
        raise RuntimeError(f"query_hs300_stocks failed: {rs.error_code} {rs.error_msg}")

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())

    df = pd.DataFrame(rows, columns=rs.fields)
    query_date = date or datetime.now().strftime("%Y-%m-%d")
    df["query_date"] = query_date
    return df


def fetch_trade_dates(start_date: str, end_date: str) -> list[str]:
    rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
    if rs.error_code != "0":
        raise RuntimeError(f"query_trade_dates failed: {rs.error_code} {rs.error_msg}")

    trade_dates: list[str] = []
    while rs.next():
        row = rs.get_row_data()
        # row: [calendar_date, is_trading_day]
        if len(row) >= 2 and row[1] == "1":
            trade_dates.append(row[0])
    return trade_dates


def main() -> None:
    args = parse_args()
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.date and (args.start_date or args.end_date):
        raise ValueError("--date 与 --start-date/--end-date 不能同时使用")

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")

    try:
        if args.start_date or args.end_date:
            if not (args.start_date and args.end_date):
                raise ValueError("区间下载必须同时提供 --start-date 和 --end-date")

            trade_dates = fetch_trade_dates(args.start_date, args.end_date)
            if not trade_dates:
                raise RuntimeError(f"区间内无交易日: {args.start_date}~{args.end_date}")

            all_df = []
            for d in trade_dates:
                day_df = fetch_hs300_for_date(d)
                if not day_df.empty:
                    all_df.append(day_df)

            if not all_df:
                raise RuntimeError(f"未获取到沪深300成分股数据: {args.start_date}~{args.end_date}")

            df = pd.concat(all_df, ignore_index=True)
            df = df.drop_duplicates(subset=["query_date", "code"]).reset_index(drop=True)
            out_file = out_dir / f"hs300_stocks_{args.start_date}_{args.end_date}.csv"
        else:
            df = fetch_hs300_for_date(args.date)
            if df.empty:
                target_date = args.date or "latest"
                raise RuntimeError(f"未获取到沪深300成分股数据: {target_date}")

            suffix = (args.date or "latest").replace("-", "")
            out_file = out_dir / f"hs300_stocks_{suffix}.csv"
    finally:
        bs.logout()

    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"fields={','.join(df.columns)}")
    if "query_date" in df.columns:
        print(f"query_date_range={df['query_date'].min()}~{df['query_date'].max()}")


if __name__ == "__main__":
    main()
