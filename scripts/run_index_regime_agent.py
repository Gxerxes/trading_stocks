from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ai_stock_agent"))

from backtest.regime_backtest import BacktestConfig, run_backtest, save_report
from config.settings import DATA_DIR, REPORT_DIR, validate_config
from data_loader.index_loader import find_latest_index_daily_csv, load_index_daily
from regime.regime_engine import RegimeDetectionEngine, RegimeScoreConfig
from strategy.regime_strategies import GridConfig, MomentumConfig, RiskConfig, TrendConfig, apply_risk_control, build_target_position


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--index-code", type=str, default="399975.SZ")
    p.add_argument("--fee-rate", type=float, default=0.0002)
    p.add_argument("--k-atr", type=float, default=1.0)
    p.add_argument("--trail-stop", type=float, default=0.08)
    p.add_argument("--target-vol", type=float, default=0.15)
    p.add_argument("--out", type=str, default=None)
    return p.parse_args()


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


def main() -> None:
    validate_config()
    args = parse_args()
    index_code = normalize_index_code(args.index_code)
    safe = index_code.replace(".", "_")

    path = find_latest_index_daily_csv(DATA_DIR, safe)
    df = load_index_daily(path)

    engine = RegimeDetectionEngine(RegimeScoreConfig())
    feat = engine.compute(df)

    strat = build_target_position(
        feat,
        grid=GridConfig(k_atr=float(args.k_atr)),
        trend=TrendConfig(),
        momentum=MomentumConfig(trail_stop_pct=float(args.trail_stop)),
    )
    strat = apply_risk_control(strat, risk=RiskConfig(target_vol_annual=float(args.target_vol)))
    bt = run_backtest(strat, cfg=BacktestConfig(fee_rate=float(args.fee_rate)))

    cols = [
        "trade_date",
        "close",
        "market_score",
        "regime",
        "ma20",
        "ma60",
        "atr",
        "grid_lower",
        "grid_upper",
        "target_pos",
        "risk_scale",
        "position",
        "turnover",
        "cost",
        "strategy_ret",
        "benchmark_ret",
        "nav",
        "benchmark_nav",
        "excess_nav",
    ]
    out_df = bt.copy()
    if "trade_date" in out_df.columns:
        out_df["trade_date"] = pd.to_datetime(out_df["trade_date"]).dt.strftime("%Y%m%d")
    out_df = out_df[[c for c in cols if c in out_df.columns]]

    if args.out:
        out_path = Path(args.out)
    else:
        date = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = REPORT_DIR / "regime_agent" / f"{safe}_{date}.csv"
    save_report(out_df, out_path)
    print(f"data_file={path}")
    print(f"report_file={out_path}")
    print(f"rows={len(out_df)}")


if __name__ == "__main__":
    main()

