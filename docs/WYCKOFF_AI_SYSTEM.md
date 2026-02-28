# Wyckoff AI 系统落地说明（600030.SH 测试版）

## 1. 系统链路

`Data Layer -> Feature Engine -> Wyckoff Detector -> Accumulation Score -> AI Dataset`

对应实现：

- Data Layer：`ai_stock_agent/data/lake/bars/freq=.../ts_code=.../*.parquet`
- Feature Engine：`ai_stock_agent/strategy/wyckoff_ai_engine.py`
- Detector（Phase / Spring / SOS）：`ai_stock_agent/strategy/wyckoff_ai_engine.py`
- 评分：`accumulation_score`（0-100）
- 训练集输出：`scripts/run_wyckoff_ai_engine.py`

## 2. 当前规则实现

- Trading Range：
  - `range_width_ratio_120 < 0.30`
  - `atr20_change_20 < 0`
  - `abs(trend_slope_60) < 0.18`
- Phase A-E：
  - A：下跌后放量止跌
  - B：区间震荡 + 缩量 + 支撑测试
  - C：Spring（假跌破收回 + 放量）
  - D：突破区间高点 + 放量 + 抬高低点
  - E：新高 + 趋势加速
- Spring：
  - `low < support*0.98`
  - `close > support`
  - `volume > vol_ma20*1.5`
- SOS：
  - `close > resistance*1.01`
  - `volume > vol_ma20*2`
  - 回踩 5 日不破（复盘验证）
- 吸筹评分（0-100）：
  - 区间时长 25%
  - 波动收敛 20%
  - 成交量干涸 20%
  - Spring 质量 20%
  - 支撑强度 15%

## 3. 输出文件

运行：

```bash
python scripts/run_wyckoff_ai_engine.py --ts-code 600030.SH
```

输出：

- `report/wyckoff_ai/600030.SH_wyckoff_features.csv`
- `report/wyckoff_ai/600030.SH_wyckoff_phase_signals.csv`
- `report/wyckoff_ai/600030.SH_wyckoff_train_dataset.csv`
- `report/wyckoff_ai/600030.SH_wyckoff_latest.json`

## 4. 训练建议

- 阶段分类：`phase` 作为分类标签（A/B/C/D/E/UNKNOWN）
- Spring 成功率：`spring_success_10d` 作为二分类标签
- 收益回归：`future_return_5d/10d/20d` 作为回归标签

## 5. 1分钟替换路径

当前分钟层使用 `5m`，未来替换 `1m` 时：

- Data Layer 增加 `freq=1m`
- 引擎中 `_build_minute_entry_signal` 从 `5m` 换 `1m`
- 其余日/周识别逻辑不变
