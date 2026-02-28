# 每日更新流水线（qfq）

脚本：

- `scripts/daily_update_pipeline.py`

目标：

- 分钟线：BaoStock（`adjustflag=2`，前复权）
- 日线/周线：Tushare（`pro_bar adj='qfq'`）
- 同步写入统一数据层 `ai_stock_agent/data/lake/bars`

## 1. 日常执行

```bash
python scripts/daily_update_pipeline.py
```

行为：

- 自动识别“运行日之前最近一个交易日”
- 更新股票池每只股票 `qfq` 日线
- 基于日线重建 `qfq` 周线
- 下载当日分钟线（默认 5 分钟）
- 写入 lake（`1d/1w/5m` 分区 Parquet）
- 输出状态文件：`ai_stock_agent/data/pipeline_state/daily_update_state.json`

## 2. 常用参数

```bash
python scripts/daily_update_pipeline.py \
  --run-date 20260228 \
  --minute-frequency 5 \
  --max-stocks 5
```

- `--run-date`：指定运行日期（`YYYYMMDD`）
- `--minute-frequency`：`5/15/30/60`
- `--skip-minute`：只更新日线和周线
- `--skip-lake`：只下载不入 lake
- `--max-stocks`：调试用，限制处理数量
- `--initial-start-date`：首次无本地数据时起始日（默认 `19900101`）

## 3. 目录说明

- qfq日线：`ai_stock_agent/data/stock_daily_qfq/`
- qfq周线：`ai_stock_agent/data/weekly_data_qfq/`
- 分钟线：`ai_stock_agent/data/minute_baostock/`
- 统一数据层：`ai_stock_agent/data/lake/bars/`
- 运行状态：`ai_stock_agent/data/pipeline_state/daily_update_state.json`

## 4. 定时任务建议

- 交易日 `15:30` 跑一次（主任务）
- `21:00` 补跑一次（网络/接口波动容错）

可先用 `--max-stocks 3` 做烟雾测试，再全量执行。
