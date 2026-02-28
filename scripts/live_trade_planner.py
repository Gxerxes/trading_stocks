"""
实盘执行辅助脚本（不直连券商，仅生成操作清单）

功能：
1) 基于 turnover_5_20_60 信号生成“次日买入清单”
2) 基于持仓和当日收盘价生成“当日卖出清单”
3) 固定每只 100 股（可配置）

输出目录：
report/live_ops/
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd


BASE_DIR = Path("report/live_ops")
SIGNAL_DIR = Path("report/strategy_signals")
DAILY_DIR = Path("ai_stock_agent/data/daily_history")

POSITIONS_FILE = BASE_DIR / "positions.csv"
BUY_PLAN_FILE_TMPL = "buy_plan_{date}.csv"
SELL_PLAN_FILE_TMPL = "sell_plan_{date}.csv"
CHECKLIST_FILE_TMPL = "checklist_{date}.md"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="生成实盘交易清单")
    p.add_argument("--signal-date", required=True, help="信号日期 YYYYMMDD")
    p.add_argument("--top-n", type=int, default=10, help="信号候选上限")
    p.add_argument("--max-new", type=int, default=5, help="单日最多新开仓数量")
    p.add_argument("--max-holdings", type=int, default=10, help="总持仓上限")
    p.add_argument("--shares", type=int, default=100, help="每只股票下单股数")
    p.add_argument("--rr-min", type=float, default=1.5, help="最小风险收益比阈值")
    p.add_argument("--max-hold-days", type=int, default=5, help="最长持有天数（超过触发时间止盈/止损以外卖出）")
    return p.parse_args()


def load_positions() -> pd.DataFrame:
    if not POSITIONS_FILE.exists():
        cols = ["ts_code", "name", "buy_date", "buy_price", "shares", "entry", "stop_loss", "tp1", "status"]
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(POSITIONS_FILE, dtype={"ts_code": str, "buy_date": str})
    if "status" not in df.columns:
        df["status"] = "open"
    return df


def next_trade_date(signal_date: str) -> Optional[str]:
    dates = sorted([p.stem.split("_")[-1] for p in DAILY_DIR.glob("daily_*.csv")])
    future = [d for d in dates if d > signal_date]
    return future[0] if future else None


def current_close_map(signal_date: str) -> pd.DataFrame:
    f = DAILY_DIR / f"daily_{signal_date}.csv"
    if not f.exists():
        raise FileNotFoundError(f"缺少行情快照: {f}")
    df = pd.read_csv(f, usecols=["ts_code", "close"], dtype={"ts_code": str})
    return df


def build_buy_plan(args: argparse.Namespace, positions: pd.DataFrame) -> pd.DataFrame:
    signal_file = SIGNAL_DIR / f"turnover_5_20_60_{args.signal_date}.csv"
    if not signal_file.exists():
        raise FileNotFoundError(f"缺少信号文件: {signal_file}")
    sig = pd.read_csv(signal_file, dtype={"ts_code": str})

    open_pos = positions[positions["status"] == "open"]["ts_code"].astype(str).unique().tolist()
    slots = max(0, args.max_holdings - len(open_pos))
    cap = min(args.max_new, slots)
    if cap <= 0:
        return pd.DataFrame(columns=["order_date", "ts_code", "name", "entry", "stop_loss", "tp1", "rr_tp1", "shares", "reason"])

    candidates = sig.copy()
    candidates["rr_tp1"] = pd.to_numeric(candidates.get("rr_tp1"), errors="coerce")
    candidates = candidates[candidates["rr_tp1"] >= args.rr_min]
    candidates = candidates[~candidates["ts_code"].isin(open_pos)]
    candidates = candidates.sort_values("score", ascending=False).head(min(args.top_n, cap))

    order_date = next_trade_date(args.signal_date) or "NEXT_TRADE_DAY_UNKNOWN"
    buy_plan = pd.DataFrame({
        "order_date": order_date,
        "ts_code": candidates["ts_code"],
        "name": candidates.get("name", ""),
        "entry": candidates["entry"],
        "stop_loss": candidates["stop_loss"],
        "tp1": candidates["tp1"],
        "rr_tp1": candidates["rr_tp1"],
        "shares": args.shares,
        "reason": "turnover_5_20_60 signal",
    })
    return buy_plan


def build_sell_plan(args: argparse.Namespace, positions: pd.DataFrame) -> pd.DataFrame:
    open_pos = positions[positions["status"] == "open"].copy()
    if open_pos.empty:
        return pd.DataFrame(columns=["order_date", "ts_code", "name", "action", "shares", "trigger", "close", "stop_loss", "tp1"])

    close_df = current_close_map(args.signal_date)
    m = open_pos.merge(close_df, on="ts_code", how="left")
    m["buy_date_dt"] = pd.to_datetime(m["buy_date"], format="%Y%m%d", errors="coerce")
    m["signal_date_dt"] = pd.to_datetime(args.signal_date, format="%Y%m%d", errors="coerce")
    m["hold_days"] = (m["signal_date_dt"] - m["buy_date_dt"]).dt.days

    stop_hit = (m["close"] <= m["stop_loss"]) & (m["hold_days"] >= 1)
    tp1_hit = (m["close"] >= m["tp1"]) & (m["hold_days"] >= 1)
    time_exit = m["hold_days"] >= args.max_hold_days

    action = pd.Series([""] * len(m))
    action[stop_hit] = "SELL_STOP"
    action[~stop_hit & tp1_hit] = "SELL_TP1"
    action[(action == "") & time_exit] = "SELL_TIME"

    sell = m[action != ""].copy()
    sell["action"] = action[action != ""].values
    sell["trigger"] = sell["action"]
    sell["order_date"] = args.signal_date
    sell_plan = sell[["order_date", "ts_code", "name", "action", "shares", "trigger", "close", "stop_loss", "tp1"]]
    return sell_plan


def write_checklist(signal_date: str, buy_plan: pd.DataFrame, sell_plan: pd.DataFrame) -> Path:
    checklist = BASE_DIR / CHECKLIST_FILE_TMPL.format(date=signal_date)
    lines = [
        f"# 实盘执行清单 {signal_date}",
        "",
        "## 1. 盘前",
        "- 检查账户可用资金与持仓",
        "- 检查是否有停牌/一字板风险",
        "",
        "## 2. 今日卖出（先卖后买）",
        f"- 待卖数量: {len(sell_plan)}",
        "",
        "## 3. 次日买入计划",
        f"- 待买数量: {len(buy_plan)}（每只100股）",
        "",
        "## 4. 风控",
        "- 单票固定100股",
        "- 达到止损/止盈规则立即执行",
        "- 超过持有天数执行时间退出",
    ]
    checklist.write_text("\n".join(lines), encoding="utf-8")
    return checklist


def main() -> None:
    args = parse_args()
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    positions = load_positions()
    buy_plan = build_buy_plan(args, positions)
    sell_plan = build_sell_plan(args, positions)

    buy_file = BASE_DIR / BUY_PLAN_FILE_TMPL.format(date=args.signal_date)
    sell_file = BASE_DIR / SELL_PLAN_FILE_TMPL.format(date=args.signal_date)
    buy_plan.to_csv(buy_file, index=False, encoding="utf-8-sig")
    sell_plan.to_csv(sell_file, index=False, encoding="utf-8-sig")
    checklist_file = write_checklist(args.signal_date, buy_plan, sell_plan)

    print(f"buy_plan={buy_file}")
    print(f"sell_plan={sell_file}")
    print(f"checklist={checklist_file}")
    print(f"buy_count={len(buy_plan)}")
    print(f"sell_count={len(sell_plan)}")


if __name__ == "__main__":
    main()
