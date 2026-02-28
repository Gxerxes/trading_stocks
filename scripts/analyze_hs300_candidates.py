"""
分析 HS300 最新成分股，剔除银行/保险/证券，并筛选可加入 stock_pool 的候选。

输入：
- ai_stock_agent/data/hs300/hs300_stocks_latest.csv
- ai_stock_agent/data/all_stocks_active_no_st.csv
- ai_stock_agent/data/stock_pool.json
- ai_stock_agent/data/daily_history/daily_*.csv（可选，用于补充成交额和涨跌幅）
- ai_stock_agent/data/daily_basic_history/daily_basic_*.csv（可选，用于补充换手率）

输出：
- ai_stock_agent/data/hs300/hs300_no_financial.csv
- ai_stock_agent/data/hs300/hs300_candidates_for_pool.csv
- ai_stock_agent/data/hs300/hs300_candidates_focus.csv
- ai_stock_agent/data/hs300/hs300_candidates_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "ai_stock_agent" / "data"


def normalize_ts_code(code: str) -> str:
    c = str(code).strip().lower()
    if c.startswith("sh."):
        return f"{c[3:].upper()}.SH"
    if c.startswith("sz."):
        return f"{c[3:].upper()}.SZ"
    return c.upper()


def find_latest_file(folder: Path, prefix: str) -> Path | None:
    files = sorted(folder.glob(f"{prefix}_*.csv"))
    if not files:
        return None
    return files[-1]


def load_stock_pool_codes(path: Path) -> set[str]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    stocks = obj.get("stocks", [])
    return {str(x).strip().upper() for x in stocks}


def main() -> None:
    hs300_path = DATA_DIR / "hs300" / "hs300_stocks_latest.csv"
    stock_info_path = DATA_DIR / "all_stocks_active_no_st.csv"
    stock_pool_path = DATA_DIR / "stock_pool.json"

    out_dir = DATA_DIR / "hs300"
    out_dir.mkdir(parents=True, exist_ok=True)

    hs = pd.read_csv(hs300_path)
    base = pd.read_csv(stock_info_path)

    hs["ts_code"] = hs["code"].map(normalize_ts_code)

    merged = hs.merge(
        base[["ts_code", "name", "industry", "area", "market"]],
        on="ts_code",
        how="left",
        suffixes=("", "_base"),
    )
    merged["name"] = merged["name"].fillna(merged.get("code_name"))

    # 剔除行业：银行 / 保险 / 证券（包含匹配）
    industry = merged["industry"].fillna("")
    exclude_mask = (
        industry.str.contains("银行")
        | industry.str.contains("保险")
        | industry.str.contains("证券")
    )
    merged["is_financial_excluded"] = exclude_mask

    no_financial = merged[~exclude_mask].copy()

    # 补充最新日线快照（可选）
    daily_file = find_latest_file(DATA_DIR / "daily_history", "daily")
    if daily_file is not None:
        daily = pd.read_csv(daily_file, usecols=["ts_code", "pct_chg", "amount", "vol"])
        no_financial = no_financial.merge(daily, on="ts_code", how="left")

    # 补充最新 daily_basic 快照（可选）
    basic_file = find_latest_file(DATA_DIR / "daily_basic_history", "daily_basic")
    if basic_file is not None:
        basic = pd.read_csv(
            basic_file,
            usecols=["ts_code", "turnover_rate", "turnover_rate_f", "pe_ttm", "pb", "total_mv"],
        )
        no_financial = no_financial.merge(basic, on="ts_code", how="left")

    stock_pool_codes = load_stock_pool_codes(stock_pool_path)
    no_financial["in_stock_pool"] = no_financial["ts_code"].isin(stock_pool_codes)

    # 候选：剔除已在池中，按成交额和换手率优先（数据缺失自动靠后）
    candidates = no_financial[~no_financial["in_stock_pool"]].copy()
    for col in ["amount", "turnover_rate_f", "pct_chg"]:
        if col not in candidates.columns:
            candidates[col] = pd.NA
    candidates = candidates.sort_values(
        by=["amount", "turnover_rate_f", "pct_chg"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    no_financial_out = out_dir / "hs300_no_financial.csv"
    candidates_out = out_dir / "hs300_candidates_for_pool.csv"
    focus_out = out_dir / "hs300_candidates_focus.csv"
    summary_out = out_dir / "hs300_candidates_summary.json"

    no_financial.to_csv(no_financial_out, index=False, encoding="utf-8-sig")
    candidates.to_csv(candidates_out, index=False, encoding="utf-8-sig")

    # 更适合短线埋伏的精简候选：
    # - 避免极端涨跌日
    # - 要有一定换手与流动性
    focus = candidates.copy()
    if "pct_chg" in focus.columns:
        focus = focus[focus["pct_chg"].between(-3.0, 4.0, inclusive="both")]
    if "turnover_rate_f" in focus.columns:
        focus = focus[focus["turnover_rate_f"].between(1.0, 12.0, inclusive="both")]
    if "amount" in focus.columns:
        focus = focus.sort_values("amount", ascending=False, na_position="last")
    focus = focus.head(50).reset_index(drop=True)
    focus.to_csv(focus_out, index=False, encoding="utf-8-sig")

    summary = {
        "source_hs300_file": str(hs300_path),
        "latest_daily_file": str(daily_file) if daily_file else None,
        "latest_daily_basic_file": str(basic_file) if basic_file else None,
        "total_hs300": int(len(merged)),
        "excluded_financial_count": int(exclude_mask.sum()),
        "remaining_after_exclusion": int(len(no_financial)),
        "already_in_stock_pool_count": int(no_financial["in_stock_pool"].sum()),
        "new_candidates_count": int(len(candidates)),
        "focus_candidates_count": int(len(focus)),
        "output_no_financial": str(no_financial_out),
        "output_candidates": str(candidates_out),
        "output_focus_candidates": str(focus_out),
    }
    summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
