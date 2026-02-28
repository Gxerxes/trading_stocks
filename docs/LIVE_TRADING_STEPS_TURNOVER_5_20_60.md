# 实盘步骤（turnover_5_20_60）

## 目标
- 使用 `turnover_5_20_60` 信号做 T+1 短线
- 每只固定买入 `100` 股

## 固定流程
1. 收盘后生成信号（T日）
   - `python scripts/run_daily_update_and_signal.py --trade-date YYYYMMDD`
2. 生成实盘执行清单
   - `python scripts/live_trade_planner.py --signal-date YYYYMMDD`
3. 盘后回写成交并更新持仓
   - `python scripts/update_live_positions.py --trade-date YYYYMMDD`
3. 次日开盘执行（T+1）
   - 先执行 `sell_plan_YYYYMMDD.csv` 卖出
   - 再执行 `buy_plan_YYYYMMDD.csv` 买入（每只100股）

## 买入规则
- 从信号中按 `score` 排序取前 N（默认 10）
- 过滤 `rr_tp1 >= 1.5`
- 已持仓股票不重复买
- 总持仓上限默认 10 只；单日新开仓上限默认 5 只

## 卖出规则
- `SELL_STOP`：收盘价 <= `stop_loss`
- `SELL_TP1`：收盘价 >= `tp1`
- `SELL_TIME`：持有天数 >= 5（默认）
- 当日买入股票最早次日才能卖（A股 T+1）

## 输出文件
- `report/live_ops/buy_plan_YYYYMMDD.csv`
- `report/live_ops/sell_plan_YYYYMMDD.csv`
- `report/live_ops/checklist_YYYYMMDD.md`
- `report/live_ops/buy_fills_YYYYMMDD.csv`（成交回写模板）
- `report/live_ops/sell_fills_YYYYMMDD.csv`（成交回写模板）
- `report/live_ops/positions.csv`（自动更新）
- `report/live_ops/trade_log.csv`（自动更新）

## 注意
- 本流程是执行辅助，不直接下券商单
- `update_live_positions.py` 会自动生成成交模板；你只需填 `filled/fill_price/fill_time`
- 回写后自动更新持仓与交易日志，不需要手工改 `positions.csv`
