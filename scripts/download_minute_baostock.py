"""
使用 BaoStock 下载股票分钟线数据。

字段：
date,time,code,open,high,low,close,volume,amount,adjustflag

示例（中信证券 2026-02-27 1分钟 前复权）：
python scripts/download_minute_baostock.py \
  --code 600030 \
  --start-date 2026-02-27 \
  --end-date 2026-02-27 \
  --frequency 1 \
  --adjustflag 2
"""

from __future__ import annotations

import argparse
from pathlib import Path

import baostock as bs
import pandas as pd


FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
VALID_MINUTE_FREQUENCIES = {"5", "15", "30", "60"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载 BaoStock 分钟线数据")
    parser.add_argument("--code", type=str, required=True, help="股票代码，如 600030 或 sh.600030")
    parser.add_argument("--start-date", type=str, required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--frequency",
        type=str,
        default="1",
        help="分钟频率，常用: 1/5/15/30/60",
    )
    parser.add_argument(
        "--adjustflag",
        type=str,
        default="2",
        help="复权类型: 1后复权 2前复权 3不复权",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="ai_stock_agent/data/minute_baostock",
        help="输出目录",
    )
    return parser.parse_args()


def normalize_code(code: str) -> str:
    c = code.strip().lower()
    if c.startswith(("sh.", "sz.")):
        return c
    if c.startswith(("6", "9")):
        return f"sh.{c}"
    return f"sz.{c}"


def fetch_minute_data(
    code: str,
    start_date: str,
    end_date: str,
    frequency: str,
    adjustflag: str,
) -> pd.DataFrame:
    rs = bs.query_history_k_data_plus(
        code=code,
        fields=FIELDS,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        adjustflag=adjustflag,
    )
    if rs.error_code != "0":
        raise RuntimeError(f"query_history_k_data_plus failed: {rs.error_code} {rs.error_msg}")

    rows: list[list[str]] = []
    while rs.next():
        rows.append(rs.get_row_data())

    return pd.DataFrame(rows, columns=rs.fields)


def main() -> None:
    args = parse_args()
    code = normalize_code(args.code)
    freq = str(args.frequency).strip()
    adjustflag = str(args.adjustflag).strip()
    if freq not in VALID_MINUTE_FREQUENCIES:
        raise ValueError(
            f"BaoStock 分钟线不支持 frequency={freq}。"
            f"可选值: {sorted(VALID_MINUTE_FREQUENCIES)}"
        )
    if adjustflag != "2":
        raise ValueError("股票分钟线统一要求前复权，adjustflag 必须为 2")

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")

    try:
        df = fetch_minute_data(
            code=code,
            start_date=args.start_date,
            end_date=args.end_date,
            frequency=freq,
            adjustflag=adjustflag,
        )
    finally:
        bs.logout()

    if df.empty:
        raise RuntimeError(
            f"未获取到数据: code={code}, date={args.start_date}~{args.end_date}, "
            f"frequency={args.frequency}, adjustflag={args.adjustflag}"
        )

    out_file = out_dir / (
        f"{code.replace('.', '_')}_{args.start_date}_{args.end_date}_"
        f"{freq}m_adj{adjustflag}.csv"
    )
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"date_range={df['date'].min()}~{df['date'].max()}")
    print(f"fields={','.join(df.columns)}")


if __name__ == "__main__":
    main()
