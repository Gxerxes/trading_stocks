# 周线数据计算规则

本文档对应脚本：`scripts/build_weekly_from_daily.py`。
用于将日线 OHLCV 数据稳定转换为周线数据，供后续策略和回测复用。

## 1. 输入要求

输入 CSV 必须包含以下字段：

- `ts_code`
- `trade_date`（格式 `YYYYMMDD`）
- `open`
- `high`
- `low`
- `close`
- `vol`
- `amount`

说明：
- 若缺少任一字段，脚本会报错并跳过该文件。
- `trade_date` 会转换为日期类型；无法解析的行会被丢弃。

## 2. 周线聚合口径

按 `W-FRI` 周期分组（以周五为周结束锚点），但周线日期不强制写成周五，而是采用该周**最后一个真实交易日**。

每周字段计算规则：

- `ts_code`：该周第一条记录
- `trade_date`：该周最后一个真实交易日（max）
- `open`：该周第一个交易日开盘价（first）
- `high`：该周最高价（max）
- `low`：该周最低价（min）
- `close`：该周最后一个交易日收盘价（last）
- `vol`：该周成交量求和（sum）
- `amount`：该周成交额求和（sum）

## 3. 衍生字段计算

在周线 OHLCV 基础上计算：

- `pre_close`：上一周 `close`
- `change`：`close - pre_close`
- `pct_chg`：`(change / pre_close) * 100`

说明：
- 第一周无上一周收盘，因此 `pre_close/change/pct_chg` 为空。

## 4. 输出字段顺序

输出统一为：

1. `ts_code`
2. `trade_date`
3. `open`
4. `high`
5. `low`
6. `close`
7. `pre_close`
8. `change`
9. `pct_chg`
10. `vol`
11. `amount`

## 5. 输出文件命名

命名规则：

`{原始前缀}_w_{周线首日期}_{周线末日期}.csv`

示例：

- 输入：`600030.SH_qfq_20030106_20260226.csv`
- 输出：`600030.SH_qfq_w_20030110_20260226.csv`

## 6. 使用方式

单文件：

```bash
python scripts/build_weekly_from_daily.py \
  --input-csv ai_stock_agent/data/wyckoff_data/600030.SH_qfq_20030106_20260226.csv
```

批量目录：

```bash
python scripts/build_weekly_from_daily.py \
  --input-dir ai_stock_agent/data/wyckoff_data
```

自定义输出目录：

```bash
python scripts/build_weekly_from_daily.py \
  --input-dir ai_stock_agent/data/wyckoff_data \
  --output-dir ai_stock_agent/data/weekly_data
```

## 7. 稳定性约定（后续策略依赖）

- 周线日期永远是该周最后真实交易日，避免出现非交易日日期。
- 周线计算仅依赖日线数据，不做前复权/后复权二次变换。
- 后续策略应直接读取本规则产出的周线 CSV，避免重复实现聚合逻辑导致口径不一致。
