"""
成交回写与持仓自动更新

流程：
1) 读取 report/live_ops/buy_fills_{date}.csv / sell_fills_{date}.csv
2) 更新 report/live_ops/positions.csv
3) 追加写入 report/live_ops/trade_log.csv

若 fills 文件不存在，会基于 buy_plan / sell_plan 自动生成模板文件。
"""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


BASE_DIR = Path("report/live_ops")
POSITIONS_FILE = BASE_DIR / "positions.csv"
TRADE_LOG_FILE = BASE_DIR / "trade_log.csv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="成交回写并更新持仓")
    p.add_argument("--trade-date", required=True, help="交易日 YYYYMMDD")
    p.add_argument("--buy-fills", default=None, help="买入成交文件路径")
    p.add_argument("--sell-fills", default=None, help="卖出成交文件路径")
    return p.parse_args()


def _init_positions() -> pd.DataFrame:
    cols = [
        "ts_code",
        "name",
        "buy_date",
        "buy_price",
        "shares",
        "entry",
        "stop_loss",
        "tp1",
        "status",
        "last_update",
    ]
    if POSITIONS_FILE.exists():
        df = pd.read_csv(POSITIONS_FILE, dtype={"ts_code": str, "buy_date": str, "last_update": str})
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]
    return pd.DataFrame(columns=cols)


def _init_trade_log() -> pd.DataFrame:
    cols = [
        "trade_date",
        "ts_code",
        "name",
        "side",
        "shares",
        "price",
        "reason",
        "note",
    ]
    if TRADE_LOG_FILE.exists():
        df = pd.read_csv(TRADE_LOG_FILE, dtype={"ts_code": str, "trade_date": str})
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        return df[cols]
    return pd.DataFrame(columns=cols)


def _to_bool(v) -> bool:
    s = str(v).strip().lower()
    return s in {"1", "true", "yes", "y", "成交", "filled"}


def _prepare_fill_templates(trade_date: str, buy_fills: Path, sell_fills: Path) -> None:
    buy_plan = BASE_DIR / f"buy_plan_{trade_date}.csv"
    sell_plan = BASE_DIR / f"sell_plan_{trade_date}.csv"

    if (not buy_fills.exists()) and buy_plan.exists():
        b = pd.read_csv(buy_plan, dtype={"ts_code": str})
        b["filled"] = 0
        b["fill_price"] = ""
        b["fill_time"] = ""
        b.to_csv(buy_fills, index=False, encoding="utf-8-sig")

    if (not sell_fills.exists()) and sell_plan.exists():
        s = pd.read_csv(sell_plan, dtype={"ts_code": str})
        s["filled"] = 0
        s["fill_price"] = ""
        s["fill_time"] = ""
        s.to_csv(sell_fills, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    buy_fills = Path(args.buy_fills) if args.buy_fills else BASE_DIR / f"buy_fills_{args.trade_date}.csv"
    sell_fills = Path(args.sell_fills) if args.sell_fills else BASE_DIR / f"sell_fills_{args.trade_date}.csv"

    _prepare_fill_templates(args.trade_date, buy_fills, sell_fills)

    positions = _init_positions()
    trade_log = _init_trade_log()
    open_pos = positions[positions["status"] == "open"].copy()

    # 1) 先处理卖出成交
    sell_count = 0
    if sell_fills.exists():
        sf = pd.read_csv(sell_fills, dtype={"ts_code": str})
        for _, r in sf.iterrows():
            if not _to_bool(r.get("filled", 0)):
                continue
            ts_code = str(r.get("ts_code", "")).strip()
            fill_price = float(r.get("fill_price", 0) or 0)
            shares = int(float(r.get("shares", 0) or 0))
            reason = str(r.get("action", r.get("reason", "SELL"))).strip()
            if not ts_code or shares <= 0 or fill_price <= 0:
                continue

            idx = open_pos.index[open_pos["ts_code"] == ts_code]
            if len(idx) == 0:
                continue
            i = idx[0]
            current_shares = int(float(open_pos.at[i, "shares"]))
            remain = current_shares - shares
            if remain <= 0:
                open_pos.at[i, "shares"] = 0
                open_pos.at[i, "status"] = "closed"
            else:
                open_pos.at[i, "shares"] = remain
                open_pos.at[i, "status"] = "open"
            open_pos.at[i, "last_update"] = args.trade_date
            sell_count += 1

            log_row = {
                "trade_date": args.trade_date,
                "ts_code": ts_code,
                "name": open_pos.at[i, "name"],
                "side": "SELL",
                "shares": shares,
                "price": fill_price,
                "reason": reason,
                "note": "",
            }
            trade_log = pd.concat([trade_log, pd.DataFrame([log_row])], ignore_index=True)

    # 2) 再处理买入成交
    buy_count = 0
    if buy_fills.exists():
        bf = pd.read_csv(buy_fills, dtype={"ts_code": str})
        for _, r in bf.iterrows():
            if not _to_bool(r.get("filled", 0)):
                continue
            ts_code = str(r.get("ts_code", "")).strip()
            name = str(r.get("name", "")).strip()
            fill_price = float(r.get("fill_price", 0) or 0)
            shares = int(float(r.get("shares", 0) or 0))
            entry = float(r.get("entry", 0) or 0)
            stop_loss = float(r.get("stop_loss", 0) or 0)
            tp1 = float(r.get("tp1", 0) or 0)
            if not ts_code or shares <= 0 or fill_price <= 0:
                continue

            # 若已有持仓则加仓合并
            idx = open_pos.index[(open_pos["ts_code"] == ts_code) & (open_pos["status"] == "open")]
            if len(idx) > 0:
                i = idx[0]
                old_shares = int(float(open_pos.at[i, "shares"]))
                old_price = float(open_pos.at[i, "buy_price"])
                new_shares = old_shares + shares
                new_price = (old_price * old_shares + fill_price * shares) / new_shares
                open_pos.at[i, "shares"] = new_shares
                open_pos.at[i, "buy_price"] = round(new_price, 4)
                open_pos.at[i, "last_update"] = args.trade_date
            else:
                row = {
                    "ts_code": ts_code,
                    "name": name,
                    "buy_date": args.trade_date,
                    "buy_price": fill_price,
                    "shares": shares,
                    "entry": entry,
                    "stop_loss": stop_loss,
                    "tp1": tp1,
                    "status": "open",
                    "last_update": args.trade_date,
                }
                open_pos = pd.concat([open_pos, pd.DataFrame([row])], ignore_index=True)
            buy_count += 1

            log_row = {
                "trade_date": args.trade_date,
                "ts_code": ts_code,
                "name": name,
                "side": "BUY",
                "shares": shares,
                "price": fill_price,
                "reason": "signal_buy",
                "note": "",
            }
            trade_log = pd.concat([trade_log, pd.DataFrame([log_row])], ignore_index=True)

    open_pos = open_pos.sort_values(["status", "ts_code"]).reset_index(drop=True)
    trade_log = trade_log.sort_values(["trade_date", "ts_code", "side"]).reset_index(drop=True)

    open_pos.to_csv(POSITIONS_FILE, index=False, encoding="utf-8-sig")
    trade_log.to_csv(TRADE_LOG_FILE, index=False, encoding="utf-8-sig")

    print(f"positions={POSITIONS_FILE}")
    print(f"trade_log={TRADE_LOG_FILE}")
    print(f"buy_fills={buy_fills}")
    print(f"sell_fills={sell_fills}")
    print(f"buy_filled_count={buy_count}")
    print(f"sell_filled_count={sell_count}")


if __name__ == "__main__":
    main()
