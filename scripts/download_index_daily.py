"""
下载指数日线行情（Tushare: index_daily, doc_id=95）

输出字段：
- ts_code
- trade_date
- close
- open
- high
- low
- pre_close
- change
- pct_chg
- vol
- amount

示例：
python scripts/download_index_daily.py --ts-code 399975
python scripts/download_index_daily.py --ts-code 399975.SZ --start-date 20100101 --end-date 20260228
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


INDEX_DAILY_FIELDS = [
    "ts_code",
    "trade_date",
    "close",
    "open",
    "high",
    "low",
    "pre_close",
    "change",
    "pct_chg",
    "vol",
    "amount",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="下载指数日线行情")
    p.add_argument("--ts-code", type=str, default="399975", help="指数代码，如 399975 或 399975.SZ")
    p.add_argument("--start-date", type=str, default="19900101", help="开始日期 YYYYMMDD")
    p.add_argument("--end-date", type=str, default=None, help="结束日期 YYYYMMDD，默认今天")
    return p.parse_args()


def normalize_ts_code(raw: str) -> str:
    code = raw.strip().upper()
    if "." in code:
        return code

    if code.startswith(("000", "399")):
        return f"{code}.SZ"
    if code.startswith(("000", "880", "930", "931", "932")):
        return f"{code}.SH"
    # 默认深市指数后缀
    return f"{code}.SZ"


def fetch_index_daily(pro, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    last_err = None
    for _ in range(RETRY_ATTEMPTS):
        try:
            df = pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields=",".join(INDEX_DAILY_FIELDS),
            )
            if df is None:
                return pd.DataFrame(columns=INDEX_DAILY_FIELDS)

            for c in INDEX_DAILY_FIELDS:
                if c not in df.columns:
                    df[c] = None

            df = df[INDEX_DAILY_FIELDS].copy()
            # 统一升序，便于后续分析
            df = df.sort_values("trade_date").reset_index(drop=True)
            return df
        except Exception as e:
            last_err = e

    raise RuntimeError(f"获取指数日线失败: {last_err}")


def main() -> None:
    args = parse_args()
    validate_config()

    ts_code = normalize_ts_code(args.ts_code)
    end_date = args.end_date or datetime.now().strftime("%Y%m%d")

    # 直接传 token，避免 ts.set_token 写入 ~/tk.csv（受沙箱权限限制）
    pro = ts.pro_api(TUSHARE_TOKEN)

    df = fetch_index_daily(pro, ts_code=ts_code, start_date=args.start_date, end_date=end_date)
    if df.empty:
        raise RuntimeError(f"未获取到数据: {ts_code} {args.start_date}~{end_date}")

    out_dir = DATA_DIR / "index_daily"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{ts_code}_{args.start_date}_{end_date}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"date_range={df['trade_date'].min()}~{df['trade_date'].max()}")


if __name__ == "__main__":
    main()
