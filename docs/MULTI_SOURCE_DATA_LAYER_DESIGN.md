# 多源行情统一数据层设计（BaoStock 分钟 + Tushare 日/周）

## 1. 目标

统一不同来源、不同周期的数据口径，避免策略层反复适配：

- 分钟线：来自 BaoStock
- 日线/周线：来自 Tushare

统一后，策略与回测只读一套 `bars` 结构。

前复权规则：

- 本项目股票行情统一使用前复权（`qfq`）。
- 分钟线（BaoStock）固定 `adjustflag=2`。
- 日线/周线（Tushare）输入文件必须是 `qfq` 口径。

## 2. 统一表结构（bars）

字段定义：

- `ts_code`：统一股票代码（如 `600030.SH`）
- `freq`：周期（`5m/15m/30m/60m/1d/1w`）
- `trade_time`：K线结束时间（`YYYY-MM-DD HH:MM:SS`）
- `trade_date`：交易日（`YYYYMMDD`）
- `open, high, low, close`
- `volume`
- `amount`
- `adjust_type`：`qfq/hfq/none/unknown`
- `source`：`baostock/tushare`
- `updated_at`：入库时间

## 3. 目录与分区

建议落地到 Parquet（列式存储）：

`ai_stock_agent/data/lake/bars/freq={freq}/ts_code={ts_code}/xxx.parquet`

示例：

- `.../freq=5m/ts_code=600030.SH/600030.SH_5m_20260227_20260227.parquet`
- `.../freq=1d/ts_code=600030.SH/600030.SH_1d_20030106_20260226.parquet`
- `.../freq=1w/ts_code=600030.SH/600030.SH_1w_20030110_20260226.parquet`

## 4. 字段映射规则

### 4.1 BaoStock 分钟线 -> bars

源字段：
`date,time,code,open,high,low,close,volume,amount,adjustflag`

映射：

- `code`（如 `sh.600030`）-> `ts_code=600030.SH`
- `time`（如 `20260227093500000`）-> `trade_time=2026-02-27 09:35:00`
- `date` -> `trade_date=20260227`
- `adjustflag`: `1->hfq, 2->qfq, 3->none`
- `source=baostock`
- 生产规则：仅接受 `adjustflag=2 (qfq)`

### 4.2 Tushare 日/周线 -> bars

源字段：
`ts_code,trade_date,open,high,low,close,vol,amount,...`

映射：

- `trade_date` -> `trade_date`
- `trade_time` 统一设为 `15:00:00`
- `vol -> volume`
- `source=tushare`
- `adjust_type` 从文件名推断（含 `qfq/hfq`），否则 `unknown`
- 生产规则：仅接受 `qfq`

## 5. 可执行脚本

已新增脚本：

- `scripts/build_unified_bars_lake.py`

中信证券示例：

```bash
python scripts/build_unified_bars_lake.py \
  --ts-code 600030.SH \
  --minute-csv ai_stock_agent/data/minute_baostock/sh_600030_2026-02-27_2026-02-27_5m_adj2.csv \
  --daily-csv ai_stock_agent/data/stock_daily/600030.SH_20030106_20260226.csv \
  --weekly-csv ai_stock_agent/data/weekly_data/600030.SH_qfq_w_20030110_20260226.csv
```

输出：

- 分区 Parquet（按 `freq + ts_code`）
- 快照 CSV：`ai_stock_agent/data/lake/bars/snapshot/600030.SH_bars_snapshot.csv`

## 6. 使用建议

- 策略计算只依赖 `bars`，不直接读原始 CSV。
- 分钟/日/周特征分别在特征层计算，避免把指标写回原始行情表。
- 多股票批处理时，按 `ts_code + freq` 增量追加，避免整表重写。
