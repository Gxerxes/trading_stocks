from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys
import time
from typing import Callable, Optional

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--index-code", type=str, default="399975")
    p.add_argument("--start-date", type=str, default="19900101")
    p.add_argument("--end-date", type=str, default=None)
    p.add_argument("--sleep-seconds", type=float, default=0.08)
    p.add_argument("--out-dir", type=str, default=str(DATA_DIR / "index"))
    p.add_argument("--force", action="store_true")
    return p.parse_args()


def build_pro() -> ts.pro_api:
    validate_config()
    return ts.pro_api(TUSHARE_TOKEN)


def normalize_index_code(raw: str) -> str:
    code = raw.strip().upper()
    if not code:
        return code
    if "." in code:
        return code
    if code.startswith("399"):
        return f"{code}.SZ"
    if code.startswith(("0", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def save_latest(df: pd.DataFrame, out_dir: Path, file_prefix: str, tag: str) -> Optional[Path]:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    out = out_dir / f"{file_prefix}_{tag}_{date_tag}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    for old in out_dir.glob(f"{file_prefix}_{tag}_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    return out


def save_snapshot(df: pd.DataFrame, out_dir: Path, file_prefix: str, tag: str) -> Optional[Path]:
    if df is None or df.empty:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = out_dir / f"{file_prefix}_{tag}_{ts_tag}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return out


def fetch_in_windows(
    fn: Callable[..., pd.DataFrame],
    params_base: dict[str, str],
    start_date: str,
    end_date: str,
    window_days: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    frames: list[pd.DataFrame] = []
    cur = start
    while cur <= end:
        nxt = min(end, cur + timedelta(days=window_days - 1))
        params = dict(params_base)
        params["start_date"] = cur.strftime("%Y%m%d")
        params["end_date"] = nxt.strftime("%Y%m%d")
        df = fn(**params)
        if df is not None and not df.empty:
            frames.append(df)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        cur = nxt + timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def month_range(start_date: str, end_date: str) -> list[tuple[str, str, str]]:
    start = datetime.strptime(start_date, "%Y%m%d").replace(day=1)
    end = datetime.strptime(end_date, "%Y%m%d")
    cur = start
    out: list[tuple[str, str, str]] = []
    while cur <= end:
        month_start = cur.strftime("%Y%m%d")
        next_month = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end_dt = next_month - timedelta(days=1)
        month_end = min(month_end_dt, end).strftime("%Y%m%d")
        yyyymm = cur.strftime("%Y%m")
        out.append((month_start, month_end, yyyymm))
        cur = next_month
    return out


def year_range(start_date: str, end_date: str, step_years: int) -> list[tuple[str, str, str]]:
    start = datetime.strptime(start_date, "%Y%m%d").replace(month=1, day=1)
    end = datetime.strptime(end_date, "%Y%m%d")
    cur = start
    out: list[tuple[str, str, str]] = []
    while cur <= end:
        nxt = cur.replace(year=cur.year + step_years) - timedelta(days=1)
        rng_end = min(nxt, end)
        s = cur.strftime("%Y%m%d")
        e = rng_end.strftime("%Y%m%d")
        tag = f"{cur.year:04d}_{rng_end.year:04d}"
        out.append((s, e, tag))
        cur = rng_end + timedelta(days=1)
    return out


def main() -> None:
    args = parse_args()
    pro = build_pro()

    end_date = args.end_date or datetime.now().strftime("%Y%m%d")
    index_code = normalize_index_code(args.index_code)
    safe_code = index_code.replace(".", "_")
    out_root = Path(args.out_dir) / safe_code

    results: list[tuple[str, Optional[Path], Optional[str]]] = []

    try:
        df_rt = pro.rt_idx_k(ts_code=index_code)
        p = save_snapshot(df_rt, out_root / "rt_idx_k", "rt_idx_k", safe_code)
        results.append(("rt_idx_k", p, None if p else "无数据"))
    except Exception as e:
        results.append(("rt_idx_k", None, str(e)))

    try:
        df_weekly = fetch_in_windows(
            pro.index_weekly,
            {"ts_code": index_code},
            args.start_date,
            end_date,
            window_days=365 * 5,
            sleep_seconds=args.sleep_seconds,
        )
        if not df_weekly.empty and "trade_date" in df_weekly.columns:
            df_weekly = df_weekly.drop_duplicates(subset=["ts_code", "trade_date"]).sort_values(["trade_date"])
        p = save_latest(df_weekly, out_root / "index_weekly", "index_weekly", safe_code)
        results.append(("index_weekly", p, None if p else "无数据"))
    except Exception as e:
        results.append(("index_weekly", None, str(e)))

    try:
        df_daily = fetch_in_windows(
            pro.index_daily,
            {"ts_code": index_code},
            args.start_date,
            end_date,
            window_days=365 * 3,
            sleep_seconds=args.sleep_seconds,
        )
        if not df_daily.empty and "trade_date" in df_daily.columns:
            df_daily = df_daily.drop_duplicates(subset=["ts_code", "trade_date"]).sort_values(["trade_date"])
        p = save_latest(df_daily, out_root / "index_daily", "index_daily", safe_code)
        results.append(("index_daily", p, None if p else "无数据"))
    except Exception as e:
        results.append(("index_daily", None, str(e)))

    try:
        df_monthly = fetch_in_windows(
            pro.index_monthly,
            {"ts_code": index_code},
            args.start_date,
            end_date,
            window_days=365 * 8,
            sleep_seconds=args.sleep_seconds,
        )
        if not df_monthly.empty and "trade_date" in df_monthly.columns:
            df_monthly = df_monthly.drop_duplicates(subset=["ts_code", "trade_date"]).sort_values(["trade_date"])
        p = save_latest(df_monthly, out_root / "index_monthly", "index_monthly", safe_code)
        results.append(("index_monthly", p, None if p else "无数据"))
    except Exception as e:
        results.append(("index_monthly", None, str(e)))

    try:
        weight_dir = out_root / "index_weight"
        ranges = year_range(args.start_date, end_date, step_years=5)
        frames: list[pd.DataFrame] = []
        for start_d, end_d, tag in ranges:
            out_file = weight_dir / f"index_weight_{safe_code}_{tag}.csv"
            if out_file.exists() and not args.force:
                df_w = pd.read_csv(out_file, encoding="utf-8-sig")
                if df_w is not None and not df_w.empty:
                    frames.append(df_w)
                continue
            df_w = pro.index_weight(index_code=index_code, start_date=start_d, end_date=end_d)
            if df_w is None or df_w.empty:
                continue
            weight_dir.mkdir(parents=True, exist_ok=True)
            df_w.to_csv(out_file, index=False, encoding="utf-8-sig")
            frames.append(df_w)
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)
        merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not merged.empty and "trade_date" in merged.columns:
            merged = merged.drop_duplicates(subset=["index_code", "con_code", "trade_date"]).sort_values(
                ["trade_date", "con_code"]
            )
        p = save_latest(merged, weight_dir, "index_weight", safe_code)
        results.append(("index_weight", p, None if p else "无数据"))
    except Exception as e:
        results.append(("index_weight", None, str(e)))

    ok = 0
    for name, path, err in results:
        if err:
            print(f"{name}: failed error={err}")
        else:
            ok += 1
            print(f"{name}: ok out={path}")
    print(f"index_code={index_code} ok={ok} total={len(results)} out_root={out_root}")


if __name__ == "__main__":
    main()
