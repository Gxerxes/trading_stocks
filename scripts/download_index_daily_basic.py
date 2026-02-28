"""
下载大盘指数每日指标（Tushare: index_dailybasic, doc_id=128），默认上证指数 000001.SH。

输出字段：
- ts_code
- trade_date
- total_mv
- float_mv
- total_share
- float_share
- free_share
- turnover_rate
- turnover_rate_f
- pe
- pe_ttm
- pb

示例：
python scripts/download_index_daily_basic.py
python scripts/download_index_daily_basic.py --ts-code 000001.SH --start-date 20000101 --end-date 20260228
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, RETRY_ATTEMPTS, TUSHARE_TOKEN, validate_config  # noqa: E402


FIELDS = [
    "ts_code",
    "trade_date",
    "total_mv",
    "float_mv",
    "total_share",
    "float_share",
    "free_share",
    "turnover_rate",
    "turnover_rate_f",
    "pe",
    "pe_ttm",
    "pb",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="下载大盘指数每日指标（默认上证指数）")
    p.add_argument("--ts-code", type=str, default="000001.SH", help="指数代码，默认 000001.SH（上证指数）")
    p.add_argument("--start-date", type=str, default="19900101", help="开始日期 YYYYMMDD")
    p.add_argument("--end-date", type=str, default=None, help="结束日期 YYYYMMDD，默认今天")
    return p.parse_args()


def fetch_index_daily_basic(pro, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    last_err = None
    for _ in range(RETRY_ATTEMPTS):
        try:
            df = pro.index_dailybasic(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=",".join(FIELDS),
            )
            if df is None:
                return pd.DataFrame(columns=FIELDS)

            for c in FIELDS:
                if c not in df.columns:
                    df[c] = None
            out = df[FIELDS].copy().sort_values("trade_date").reset_index(drop=True)
            return out
        except Exception as e:
            last_err = e
    raise RuntimeError(f"获取指数每日指标失败: {last_err}")


def main() -> None:
    args = parse_args()
    validate_config()

    end_date = args.end_date or datetime.now().strftime("%Y%m%d")
    ts_code = args.ts_code.strip().upper()

    # 直接传 token，避免写 ~/tk.csv
    pro = ts.pro_api(TUSHARE_TOKEN)
    df = fetch_index_daily_basic(pro, ts_code=ts_code, start_date=args.start_date, end_date=end_date)
    if df.empty:
        raise RuntimeError(f"未获取到数据: {ts_code} {args.start_date}~{end_date}")

    out_dir = DATA_DIR / "index_daily_basic"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{ts_code}_{args.start_date}_{end_date}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"date_range={df['trade_date'].min()}~{df['trade_date'].max()}")


if __name__ == "__main__":
    main()
