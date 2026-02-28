"""
下载申万 2021 行业分类（L1/L2/L3）并保存到本地

输出目录:
ai_stock_agent/data/industry/
  - sw2021_l1.csv
  - sw2021_l2.csv
  - sw2021_l3.csv
  - sw2021_all_levels.csv
"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd
import tushare as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from config.settings import DATA_DIR, TUSHARE_TOKEN, validate_config  # noqa: E402


def fetch_level(pro, level: str, src: str = "SW2021") -> pd.DataFrame:
    df = pro.index_classify(level=level, src=src)
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    out["level"] = level
    out["src"] = src
    return out


def main() -> None:
    validate_config()
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()

    out_dir = DATA_DIR / "industry"
    out_dir.mkdir(parents=True, exist_ok=True)

    l1 = fetch_level(pro, "L1")
    l2 = fetch_level(pro, "L2")
    l3 = fetch_level(pro, "L3")

    l1_file = out_dir / "sw2021_l1.csv"
    l2_file = out_dir / "sw2021_l2.csv"
    l3_file = out_dir / "sw2021_l3.csv"
    all_file = out_dir / "sw2021_all_levels.csv"

    l1.to_csv(l1_file, index=False, encoding="utf-8-sig")
    l2.to_csv(l2_file, index=False, encoding="utf-8-sig")
    l3.to_csv(l3_file, index=False, encoding="utf-8-sig")

    all_df = pd.concat([l1, l2, l3], ignore_index=True)
    all_df.to_csv(all_file, index=False, encoding="utf-8-sig")

    print(f"l1_file={l1_file} rows={len(l1)}")
    print(f"l2_file={l2_file} rows={len(l2)}")
    print(f"l3_file={l3_file} rows={len(l3)}")
    print(f"all_file={all_file} rows={len(all_df)}")


if __name__ == "__main__":
    main()
