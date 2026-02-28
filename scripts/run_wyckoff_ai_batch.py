"""
批量运行 Wyckoff AI Engine（stock_pool 全部股票）。

输出：
- stock_pool_latest_summary.csv
- stock_pool_topn_accumulation.csv
- stock_pool_spring_candidates.csv
- stock_pool_batch_overview.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from strategy.wyckoff_ai_engine import WyckoffAIEngine  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="批量运行 Wyckoff AI Engine")
    p.add_argument("--stock-pool", type=str, default="ai_stock_agent/data/stock_pool.json", help="股票池文件")
    p.add_argument("--lake-root", type=str, default="ai_stock_agent/data/lake/bars", help="lake 根目录")
    p.add_argument("--out-dir", type=str, default="report/wyckoff_ai", help="输出目录")
    p.add_argument("--top-n", type=int, default=10, help="TopN 输出数量")
    p.add_argument("--spring-lookback", type=int, default=20, help="Spring 候选池回看天数")
    p.add_argument("--relaxed-score-threshold", type=float, default=35.0, help="宽松候选池吸筹评分阈值")
    p.add_argument(
        "--relaxed-phases",
        type=str,
        default="B,C",
        help="宽松候选池允许阶段，逗号分隔，如 B,C",
    )
    p.add_argument(
        "--relaxed-require-minute-entry",
        action="store_true",
        help="宽松候选池是否要求 minute_entry_ready=1",
    )
    return p.parse_args()


def load_stock_pool(path: Path) -> tuple[list[str], dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    stocks = [str(x).strip().upper() for x in data.get("stocks", []) if str(x).strip()]
    name_map: dict[str, str] = {}
    for item in data.get("stocks_detail", []):
        if not isinstance(item, dict):
            continue
        code = str(item.get("ts_code", "")).strip().upper()
        if not code:
            continue
        name_map[code] = str(item.get("name", "")).strip()
    return stocks, name_map


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stocks, name_map = load_stock_pool(Path(args.stock_pool))
    if not stocks:
        raise RuntimeError("股票池为空，无法批跑")

    engine = WyckoffAIEngine(lake_root=Path(args.lake_root))

    latest_rows: list[dict] = []
    spring_rows: list[dict] = []
    relaxed_rows: list[dict] = []
    failed_rows: list[dict] = []

    for idx, ts_code in enumerate(stocks, start=1):
        try:
            result = engine.run(ts_code=ts_code)
            latest = result.latest_assessment
            phase_df = result.phase_signals.copy()

            trade_date = str(latest.get("trade_date", ""))
            phase = str(latest.get("phase", ""))
            score = float(latest.get("accumulation_score", 0))
            spring = bool(latest.get("spring", False))
            sos = bool(latest.get("sos", False))
            score_level = str(latest.get("score_level", ""))
            minute_entry = latest.get("minute_entry", {}) if isinstance(latest.get("minute_entry", {}), dict) else {}

            latest_rows.append(
                {
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code, ""),
                    "trade_date": trade_date,
                    "phase": phase,
                    "accumulation_score": round(score, 2),
                    "score_level": score_level,
                    "spring": int(spring),
                    "sos": int(sos),
                    "minute_entry_ready": int(bool(minute_entry.get("entry_ready", False))),
                    "minute_reason": str(minute_entry.get("reason", "")),
                    "status": "ok",
                }
            )

            # Spring 候选池：最近 N 个交易日出现过 spring
            recent = phase_df.tail(args.spring_lookback).copy()
            spring_recent = recent[recent["spring"] == 1]
            if not spring_recent.empty:
                last_spring = str(spring_recent["trade_date"].max())
                spring_rows.append(
                    {
                        "ts_code": ts_code,
                        "name": name_map.get(ts_code, ""),
                        "latest_trade_date": trade_date,
                        "latest_phase": phase,
                        "latest_accumulation_score": round(score, 2),
                        "spring_count_recent": int(len(spring_recent)),
                        "last_spring_date": last_spring,
                        "sos_latest": int(sos),
                    }
                )

            # 宽松候选池：吸筹评分 + 阶段 +（可选）分钟入场确认
            relaxed_phase_set = {x.strip().upper() for x in args.relaxed_phases.split(",") if x.strip()}
            minute_ok = bool(minute_entry.get("entry_ready", False))
            relaxed_ok = (
                (score >= float(args.relaxed_score_threshold))
                and (phase.upper() in relaxed_phase_set)
                and ((not args.relaxed_require_minute_entry) or minute_ok)
            )
            if relaxed_ok:
                relaxed_rows.append(
                    {
                        "ts_code": ts_code,
                        "name": name_map.get(ts_code, ""),
                        "latest_trade_date": trade_date,
                        "latest_phase": phase,
                        "latest_accumulation_score": round(score, 2),
                        "spring_latest": int(spring),
                        "sos_latest": int(sos),
                        "minute_entry_ready": int(minute_ok),
                        "minute_reason": str(minute_entry.get("reason", "")),
                    }
                )

            print(f"[{idx}/{len(stocks)}] {ts_code}: ok")
        except Exception as e:
            failed_rows.append({"ts_code": ts_code, "name": name_map.get(ts_code, ""), "error": str(e)})
            latest_rows.append(
                {
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code, ""),
                    "trade_date": "",
                    "phase": "",
                    "accumulation_score": None,
                    "score_level": "",
                    "spring": 0,
                    "sos": 0,
                    "minute_entry_ready": 0,
                    "minute_reason": "",
                    "status": "failed",
                }
            )
            print(f"[{idx}/{len(stocks)}] {ts_code}: failed")

    latest_df = pd.DataFrame(latest_rows)
    latest_df = latest_df.sort_values(["status", "accumulation_score"], ascending=[True, False], na_position="last").reset_index(drop=True)

    topn_df = (
        latest_df[latest_df["status"] == "ok"]
        .sort_values("accumulation_score", ascending=False)
        .head(args.top_n)
        .reset_index(drop=True)
    )

    spring_df = pd.DataFrame(spring_rows)
    if not spring_df.empty:
        spring_df = spring_df.sort_values(
            ["spring_count_recent", "latest_accumulation_score"],
            ascending=[False, False],
        ).reset_index(drop=True)

    latest_file = out_dir / "stock_pool_latest_summary.csv"
    topn_file = out_dir / "stock_pool_topn_accumulation.csv"
    spring_file = out_dir / "stock_pool_spring_candidates.csv"
    relaxed_file = out_dir / "stock_pool_relaxed_candidates.csv"
    overview_file = out_dir / "stock_pool_batch_overview.json"

    latest_df.to_csv(latest_file, index=False, encoding="utf-8-sig")
    topn_df.to_csv(topn_file, index=False, encoding="utf-8-sig")
    if spring_df.empty:
        pd.DataFrame(
            columns=[
                "ts_code",
                "name",
                "latest_trade_date",
                "latest_phase",
                "latest_accumulation_score",
                "spring_count_recent",
                "last_spring_date",
                "sos_latest",
            ]
        ).to_csv(spring_file, index=False, encoding="utf-8-sig")
    else:
        spring_df.to_csv(spring_file, index=False, encoding="utf-8-sig")

    relaxed_df = pd.DataFrame(relaxed_rows)
    if relaxed_df.empty:
        pd.DataFrame(
            columns=[
                "ts_code",
                "name",
                "latest_trade_date",
                "latest_phase",
                "latest_accumulation_score",
                "spring_latest",
                "sos_latest",
                "minute_entry_ready",
                "minute_reason",
            ]
        ).to_csv(relaxed_file, index=False, encoding="utf-8-sig")
    else:
        relaxed_df = relaxed_df.sort_values(
            ["latest_accumulation_score", "minute_entry_ready", "sos_latest"],
            ascending=[False, False, False],
        ).reset_index(drop=True)
        relaxed_df.to_csv(relaxed_file, index=False, encoding="utf-8-sig")

    overview = {
        "total_stocks": len(stocks),
        "ok": int((latest_df["status"] == "ok").sum()),
        "failed": int((latest_df["status"] == "failed").sum()),
        "top_n": args.top_n,
        "spring_lookback": args.spring_lookback,
        "files": {
            "latest_summary": str(latest_file),
            "topn_accumulation": str(topn_file),
            "spring_candidates": str(spring_file),
            "relaxed_candidates": str(relaxed_file),
        },
        "relaxed_rules": {
            "score_threshold": args.relaxed_score_threshold,
            "phases": sorted({x.strip().upper() for x in args.relaxed_phases.split(",") if x.strip()}),
            "require_minute_entry": bool(args.relaxed_require_minute_entry),
        },
        "failed_detail": failed_rows,
    }
    with open(overview_file, "w", encoding="utf-8") as f:
        json.dump(overview, f, ensure_ascii=False, indent=2)

    print(f"latest_summary={latest_file}")
    print(f"topn={topn_file}")
    print(f"spring_candidates={spring_file}")
    print(f"relaxed_candidates={relaxed_file}")
    print(f"overview={overview_file}")
    print(f"ok={overview['ok']} failed={overview['failed']}")


if __name__ == "__main__":
    main()
