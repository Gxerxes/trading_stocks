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
    p.add_argument("--exchange", type=str, default="SSE", choices=["SSE", "SZSE", "BSE", "ALL"])
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "basic"))
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


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

    exchange = args.exchange.upper()
    if exchange == "ALL":
        exch_list = ["SSE", "SZSE", "BSE"]
    else:
        exch_list = [exchange]

    results: list[tuple[str, Optional[Path], Optional[str]]] = []

    for exch in exch_list:
        results.append(
            fetch_one(
                pro,
                "stock_company",
                out_dir,
                {"exchange": exch},
                f"{exch.lower()}",
                None,
            )
        )

    results.append(
        fetch_one(
            pro,
            "stk_managers",
            out_dir,
            {"ts_code": args.ts_code},
            args.ts_code.replace(".", "_"),
            args.ts_code,
        )
    )
    results.append(
        fetch_one(
            pro,
            "stk_rewards",
            out_dir,
            {"ts_code": args.ts_code},
            args.ts_code.replace(".", "_"),
            args.ts_code,
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
