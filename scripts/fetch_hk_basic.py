from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import tushare as ts


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR_DEFAULT = PROJECT_ROOT / "ai_stock_agent" / "data" / "hk_basic"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="获取并保存港股列表 hk_basic")
    p.add_argument("--list-status", type=str, default="L", choices=["L", "D", "P", "ALL"], help="上市状态")
    p.add_argument("--out-dir", type=str, default=str(OUT_DIR_DEFAULT), help="输出目录")
    p.add_argument("--file-prefix", type=str, default="hk_basic", help="输出文件前缀")
    return p.parse_args()


def load_token() -> str:
    env_file = PROJECT_ROOT / ".env"
    token = None
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("TUSHARE_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        import os

        token = os.getenv("TUSHARE_TOKEN")
    if not token:
        raise ValueError("未找到 TUSHARE_TOKEN，请检查 .env 或环境变量")
    return token


def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "ts_code",
        "name",
        "fullname",
        "enname",
        "cn_spell",
        "market",
        "list_status",
        "list_date",
        "delist_date",
        "trade_unit",
        "isin",
        "curr_type",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = pd.Series([None] * len(df))
    return df[cols]


def fetch_hk_basic(status: str) -> pd.DataFrame:
    token = load_token()
    pro = ts.pro_api(token)
    if status == "ALL":
        frames: list[pd.DataFrame] = []
        for s in ["L", "D", "P"]:
            d = pro.hk_basic(list_status=s)
            if d is not None and not d.empty:
                d["list_status"] = s
                frames.append(d)
        df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if not df.empty:
            df = df.drop_duplicates(subset=["ts_code", "list_status"])
        return ensure_columns(df)
    d = pro.hk_basic(list_status=status)
    if d is None or d.empty:
        return pd.DataFrame(columns=["ts_code"])
    d["list_status"] = status
    return ensure_columns(d)


def save_dataframe(df: pd.DataFrame, out_dir: Path, prefix: str, status: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y%m%d")
    tag = status.lower()
    out = out_dir / f"{prefix}_{tag}_{date}.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    for old in out_dir.glob(f"{prefix}_{tag}_*.csv"):
        if old != out:
            old.unlink(missing_ok=True)
    alias = out_dir / f"{prefix}_{tag}.csv"
    try:
        if alias.exists():
            alias.unlink()
        alias.symlink_to(out.name)
    except Exception:
        pass
    return out


def main() -> None:
    args = parse_args()
    status = args.list_status.upper()
    df = fetch_hk_basic(status)
    out_dir = Path(args.out_dir)
    path = save_dataframe(df, out_dir, args.file_prefix, status if status != "ALL" else "all")
    print(f"rows={len(df)}")
    print(f"out_file={path}")


if __name__ == "__main__":
    main()

