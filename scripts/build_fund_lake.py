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
    p.add_argument("--fund-ts-code", type=str, default="512850.SH")
    p.add_argument("--fund-basic-market", type=str, default="E", choices=["E", "O"])
    p.add_argument("--fund-basic-status", type=str, default=None)
    p.add_argument("--fund-manager-limit", type=int, default=5000)
    p.add_argument("--fund-manager-offset", type=int, default=0)
    p.add_argument("--share-start-date", type=str, default=None)
    p.add_argument("--share-end-date", type=str, default=None)
    p.add_argument("--share-trade-date", type=str, default=None)
    p.add_argument("--share-market", type=str, default=None)
    p.add_argument("--nav-start-date", type=str, default=None)
    p.add_argument("--nav-end-date", type=str, default=None)
    p.add_argument("--nav-date", type=str, default=None)
    p.add_argument("--nav-market", type=str, default=None)
    p.add_argument("--div-ann-date", type=str, default=None)
    p.add_argument("--div-ex-date", type=str, default=None)
    p.add_argument("--div-pay-date", type=str, default=None)
    p.add_argument("--all-dates", action="store_true")
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "fund"))
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


def normalize_fund_code(raw: str) -> str:
    code = raw.strip().upper()
    if not code:
        return code
    if "." in code:
        return code
    if code.startswith(("5", "6")):
        return f"{code}.SH"
    if code.startswith(("0", "1", "3")):
        return f"{code}.SZ"
    return f"{code}.OF"


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
    params: dict[str, str | int | None],
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

    fund_code = normalize_fund_code(args.fund_ts_code)
    fund_tag = fund_code.replace(".", "_")

    fund_basic_params: dict[str, str | int | None] = {"market": args.fund_basic_market}
    if args.fund_basic_status:
        fund_basic_params["status"] = args.fund_basic_status

    manager_params: dict[str, str | int | None] = {
        "ts_code": fund_code,
        "limit": args.fund_manager_limit,
        "offset": args.fund_manager_offset,
    }

    share_params: dict[str, str | int | None] = {}
    if args.share_trade_date:
        share_params["trade_date"] = args.share_trade_date
    elif not args.all_dates:
        start, end = normalize_range(args.share_start_date, args.share_end_date)
        share_params["start_date"] = start
        share_params["end_date"] = end
    if fund_code:
        share_params["ts_code"] = fund_code
    if args.share_market:
        share_params["market"] = args.share_market

    nav_params: dict[str, str | int | None] = {}
    if args.nav_date:
        nav_params["nav_date"] = args.nav_date
    elif not args.all_dates:
        start, end = normalize_range(args.nav_start_date, args.nav_end_date)
        nav_params["start_date"] = start
        nav_params["end_date"] = end
    if fund_code:
        nav_params["ts_code"] = fund_code
    if args.nav_market:
        nav_params["market"] = args.nav_market

    div_params: dict[str, str | int | None] = {}
    if args.div_ann_date:
        div_params["ann_date"] = args.div_ann_date
    if args.div_ex_date:
        div_params["ex_date"] = args.div_ex_date
    if args.div_pay_date:
        div_params["pay_date"] = args.div_pay_date
    if not div_params and fund_code:
        div_params["ts_code"] = fund_code

    results: list[tuple[str, Optional[Path], Optional[str]]] = []
    results.append(
        fetch_one(
            pro,
            "fund_basic",
            out_dir,
            fund_basic_params,
            f"market_{args.fund_basic_market.lower()}",
            None,
        )
    )
    results.append(fetch_one(pro, "fund_company", out_dir, {}, "fund_company", None))
    results.append(fetch_one(pro, "fund_manager", out_dir, manager_params, fund_tag, fund_code))
    results.append(fetch_one(pro, "fund_share", out_dir, share_params, fund_tag, fund_code))
    results.append(fetch_one(pro, "fund_nav", out_dir, nav_params, fund_tag, fund_code))
    results.append(fetch_one(pro, "fund_div", out_dir, div_params, fund_tag, fund_code))

    ok = 0
    for api_name, path, err in results:
        if err:
            print(f"{api_name}: failed error={err}")
        else:
            ok += 1
            print(f"{api_name}: ok file={path}")
    print(f"fund_ts_code={fund_code} ok={ok} total={len(results)}")


if __name__ == "__main__":
    main()
