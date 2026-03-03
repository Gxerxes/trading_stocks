from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
from typing import Callable, Optional

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--ts-code", type=str, default="600030.SH")
    p.add_argument("--start-date", type=str, default=None)
    p.add_argument("--end-date", type=str, default=None)
    p.add_argument("--trade-date", type=str, default=None)
    p.add_argument("--hsgt-start-date", type=str, default=None)
    p.add_argument("--hsgt-end-date", type=str, default=None)
    p.add_argument("--hsgt-trade-date", type=str, default=None)
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "moneyflow"))
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def normalize_range(start_date: Optional[str], end_date: Optional[str], days: int = 30) -> tuple[str, str]:
    if start_date and end_date:
        return start_date, end_date
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    return start, end


def save_df(df: pd.DataFrame, out_dir: Path, api_name: str, file_tag: str) -> Optional[Path]:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    out = out_dir / f"{file_tag}_{api_name}_{date_tag}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    for old in out_dir.glob(f"{file_tag}_{api_name}_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def fetch_one(
    pro: ts.pro_api,
    api_name: str,
    out_dir: Path,
    params: dict[str, str | None],
    file_tag: str,
    filter_ts_code: Optional[str],
) -> tuple[str, Optional[Path], Optional[str]]:
    fn: Optional[Callable[..., pd.DataFrame]] = getattr(pro, api_name, None)
    if fn is None:
        return api_name, None, f"接口不存在: {api_name}"
    try:
        df = fn(**params)
        if filter_ts_code and df is not None and not df.empty and "ts_code" in df.columns:
            df = df[df["ts_code"].astype(str).str.upper() == filter_ts_code.upper()]
        path = save_df(df, out_dir / api_name, api_name, file_tag)
        if path is None:
            return api_name, None, "无数据"
        return api_name, path, None
    except Exception as e:
        return api_name, None, str(e)


def main() -> None:
    args = parse_args()
    pro = build_pro()
    out_dir = Path(args.out_dir)

    mf_params: dict[str, str | None] = {}
    if args.trade_date:
        mf_params["trade_date"] = args.trade_date
    else:
        start, end = normalize_range(args.start_date, args.end_date)
        mf_params["start_date"] = start
        mf_params["end_date"] = end
    if args.ts_code:
        mf_params["ts_code"] = args.ts_code

    hsgt_params: dict[str, str | None] = {}
    if args.hsgt_trade_date:
        hsgt_params["trade_date"] = args.hsgt_trade_date
        hsgt_tag = args.hsgt_trade_date
    else:
        start, end = normalize_range(args.hsgt_start_date, args.hsgt_end_date)
        hsgt_params["start_date"] = start
        hsgt_params["end_date"] = end
        hsgt_tag = f"{start}_{end}"

    results: list[tuple[str, Optional[Path], Optional[str]]] = []
    results.append(
        fetch_one(
            pro,
            "moneyflow",
            out_dir,
            mf_params,
            args.ts_code.replace(".", "_"),
            args.ts_code,
        )
    )
    results.append(
        fetch_one(
            pro,
            "moneyflow_hsgt",
            out_dir,
            hsgt_params,
            f"hsgt_{hsgt_tag}",
            None,
        )
    )

    ok = 0
    for api_name, path, err in results:
        if err:
            print(f"{api_name}: failed error={err}")
        else:
            ok += 1
            print(f"{api_name}: ok file={path}")
    print(f"ts_code={args.ts_code} ok={ok} total={len(results)}")


if __name__ == "__main__":
    main()
