# 资金扩散突破策略（3-5天）要点

## 策略定位
- 目标：捕捉“资金启动 -> 扩散”阶段
- 持仓周期：`3~5` 个交易日
- 市场：A股日线

## 核心逻辑
1. 趋势过滤（避免逆势）
   - `close > MA20`
   - `MA20` 近5日斜率为正（`MA20_slope5 > 0`）

2. 资金启动信号（避免无量）
   - 当日涨幅：`3% ~ 7%`
   - 当日成交量：`vol > VOL_MA5 * 1.8`

3. 换手率过滤（避免过冷/过热）
   - `5% <= turnover_rate <= 20%`

## 入场规则（T+1）
- 信号日为 `T`
- 执行日为 `T+1`
- 满足以下条件才买入：
  - `next_open <= close_T * 1.03`（不追高开）
  - `next_low >= avg_price_proxy_T`（不破前日均价代理）
  - 其中 `avg_price_proxy = (open+high+low+close)/4`

## 卖出规则（优先级）
1. 止损：`low <= entry * 0.96`（-4%）
2. 动量衰减：`vol_today < vol_prev * 0.7`（收盘退出）
3. 时间退出：持仓第4个交易日收盘退出
4. 最大持仓：5个交易日

## 评分机制（用于排序）
- `score = 45*vol_boost + 35*涨幅强度 + 20*换手率中枢贴合度`
- `vol_boost = clip(vol/vol_ma5, 1, 4)`
- 按 `score` 降序取 `TopN`

## 回测口径（当前实现）
- 脚本：`scripts/backtest_capital_diffusion_3_5d.py`
- 区间：`20250101 ~ 20260227`
- 参数：`top_n=10`
- 结果（最近一次）：
  - 交易数：`803`
  - 胜率：`55.92%`
  - 平均收益：`1.9727%`
  - 中位数收益：`0.7143%`
  - 平均持有天数：`2.8207`

## 相关代码
- 策略实现：`ai_stock_agent/strategy/capital_diffusion_3_5d_strategy.py`
- 信号生成：`scripts/run_capital_diffusion_signal.py`
- 回测脚本：`scripts/backtest_capital_diffusion_3_5d.py`

## 执行示例
```bash
python scripts/run_capital_diffusion_signal.py --as-of-date 20260227 --top-n 10
python scripts/backtest_capital_diffusion_3_5d.py --start-date 20250101 --end-date 20260227 --top-n 10
```
