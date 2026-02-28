"""
下载指数成分与权重（Tushare: index_weight, doc_id=96）

输出字段：
- index_code
- con_code
- trade_date
- weight

示例：
python scripts/download_index_weight.py --index-code 399975
python scripts/download_index_weight.py --index-code 399975.SZ --start-date 20200101 --end-date 20260228
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


INDEX_WEIGHT_FIELDS = ["index_code", "con_code", "trade_date", "weight"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="下载指数成分与权重")
    p.add_argument("--index-code", type=str, default="399975", help="指数代码，如 399975 或 399975.SZ")
    p.add_argument("--start-date", type=str, default="19900101", help="开始日期 YYYYMMDD")
    p.add_argument("--end-date", type=str, default=None, help="结束日期 YYYYMMDD，默认今天")
    return p.parse_args()


def normalize_index_code(raw: str) -> str:
    code = raw.strip().upper()
    if "." in code:
        return code
    if code.startswith(("399", "980")):
        return f"{code}.SZ"
    return f"{code}.SH"


def fetch_index_weight(pro, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    last_err = None
    for _ in range(RETRY_ATTEMPTS):
        try:
            df = pro.index_weight(index_code=index_code, start_date=start_date, end_date=end_date)
            if df is None:
                return pd.DataFrame(columns=INDEX_WEIGHT_FIELDS)

            for c in INDEX_WEIGHT_FIELDS:
                if c not in df.columns:
                    df[c] = None

            result = df[INDEX_WEIGHT_FIELDS].copy()
            result["trade_date"] = result["trade_date"].astype(str)
            result = result.sort_values(["trade_date", "index_code", "con_code"]).reset_index(drop=True)
            return result
        except Exception as e:
            last_err = e

    raise RuntimeError(f"获取指数成分权重失败: {last_err}")


def main() -> None:
    args = parse_args()
    validate_config()

    index_code = normalize_index_code(args.index_code)
    end_date = args.end_date or datetime.now().strftime("%Y%m%d")

    # 直接传 token，避免写 ~/tk.csv
    pro = ts.pro_api(TUSHARE_TOKEN)

    df = fetch_index_weight(pro, index_code=index_code, start_date=args.start_date, end_date=end_date)
    if df.empty:
        raise RuntimeError(f"未获取到数据: {index_code} {args.start_date}~{end_date}")

    out_dir = DATA_DIR / "index_weight"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{index_code}_{args.start_date}_{end_date}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"date_range={df['trade_date'].min()}~{df['trade_date'].max()}")


if __name__ == "__main__":
    main()
