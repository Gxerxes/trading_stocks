from __future__ import annotations

import argparse
from datetime import datetime
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
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "finance"))
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def save_df(df: pd.DataFrame, out_dir: Path, api_name: str, ts_code: str) -> Optional[Path]:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    safe_code = ts_code.replace(".", "_")
    out = out_dir / f"{safe_code}_{api_name}_{date_tag}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    for old in out_dir.glob(f"{safe_code}_{api_name}_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def fetch_one(
    pro: ts.pro_api,
    api_name: str,
    ts_code: str,
    out_dir: Path,
    params: dict[str, str | None],
    filter_by_ts_code: bool,
) -> tuple[str, Optional[Path], Optional[str]]:
    fn: Optional[Callable[..., pd.DataFrame]] = getattr(pro, api_name, None)
    if fn is None:
        return api_name, None, f"接口不存在: {api_name}"
    try:
        df = fn(**params)
        if filter_by_ts_code and df is not None and not df.empty and "ts_code" in df.columns:
            df = df[df["ts_code"].astype(str).str.upper() == ts_code.upper()]
        path = save_df(df, out_dir / api_name, api_name, ts_code)
        if path is None:
            return api_name, None, "无数据"
        return api_name, path, None
    except Exception as e:
        return api_name, None, str(e)


def main() -> None:
    args = parse_args()
    pro = build_pro()
    api_list = [
        {"name": "income", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "balancesheet", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "cashflow", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "forecast", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "express", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "dividend", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "fina_indicator", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "fina_audit", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "fina_mainbz", "params": {"ts_code": args.ts_code}, "filter": False},
        {"name": "disclosure_date", "params": {"ts_code": args.ts_code}, "filter": False},
    ]
    results: list[tuple[str, Optional[Path], Optional[str]]] = []
    out_dir = Path(args.out_dir)
    for api in api_list:
        results.append(
            fetch_one(
                pro,
                api["name"],
                args.ts_code,
                out_dir,
                api["params"],
                api["filter"],
            )
        )
    ok = 0
    for api_name, path, err in results:
        if err:
            print(f"{api_name}: failed error={err}")
        else:
            ok += 1
            print(f"{api_name}: ok file={path}")
    print(f"ts_code={args.ts_code} ok={ok} total={len(api_list)}")


if __name__ == "__main__":
    main()
