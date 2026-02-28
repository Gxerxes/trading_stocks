"""
下载融资融券交易明细（Tushare: margin_detail, doc_id=59）

输出字段：
- trade_date
- ts_code
- name
- rzye
- rqye
- rzmre
- rqyl
- rzche
- rqchl
- rqmcl
- rzrqye

输出目录：
ai_stock_agent/data/margin_detail/
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


MARGIN_DETAIL_FIELDS = [
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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="下载融资融券交易明细")
    p.add_argument("--ts-code", type=str, default=None, help="指定TS代码，如 512880.SH")
    p.add_argument("--start-date", type=str, default=None, help="开始日期 YYYYMMDD")
    p.add_argument("--end-date", type=str, default=None, help="结束日期 YYYYMMDD")
    p.add_argument("--trade-date", type=str, default=None, help="单日下载 YYYYMMDD（优先于区间）")
    p.add_argument("--split-by-date", action="store_true", help="是否额外按交易日拆分保存")
    return p.parse_args()


def fetch_margin_detail(
    pro,
    ts_code: str | None,
    trade_date: str | None,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    last_err = None
    for _ in range(RETRY_ATTEMPTS):
        try:
            if trade_date:
                df = pro.margin_detail(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    fields=",".join(MARGIN_DETAIL_FIELDS),
                )
            else:
                df = pro.margin_detail(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    fields=",".join(MARGIN_DETAIL_FIELDS),
                )
            if df is None:
                return pd.DataFrame(columns=MARGIN_DETAIL_FIELDS)
            for c in MARGIN_DETAIL_FIELDS:
                if c not in df.columns:
                    df[c] = None
            return df[MARGIN_DETAIL_FIELDS].sort_values(["trade_date", "ts_code"]).reset_index(drop=True)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"获取融资融券明细失败: {last_err}")


def main() -> None:
    args = parse_args()
    validate_config()

    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    if args.trade_date:
        trade_date = args.trade_date
        start_date = None
        end_date = None
    else:
        trade_date = None
        end_date = args.end_date or datetime.now().strftime("%Y%m%d")
        # 默认全历史区间
        start_date = args.start_date or "19900101"

    df = fetch_margin_detail(pro, args.ts_code, trade_date, start_date, end_date)
    if df.empty:
        raise RuntimeError("未获取到融资融券明细数据")

    out_dir = DATA_DIR / "margin_detail"
    out_dir.mkdir(parents=True, exist_ok=True)

    code_tag = f"_{args.ts_code}" if args.ts_code else ""
    if trade_date:
        out_file = out_dir / f"margin_detail{code_tag}_{trade_date}.csv"
    else:
        out_file = out_dir / f"margin_detail{code_tag}_{start_date}_{end_date}.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")

    if args.split_by_date:
        for d, g in df.groupby("trade_date"):
            g.to_csv(out_dir / f"margin_detail{code_tag}_{d}.csv", index=False, encoding="utf-8-sig")

    print(f"output={out_file}")
    print(f"rows={len(df)}")
    print(f"dates={df['trade_date'].min()}~{df['trade_date'].max()}")


if __name__ == "__main__":
    main()
