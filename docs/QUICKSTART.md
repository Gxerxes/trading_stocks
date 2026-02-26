# AI 股票分析系统 - 快速启动指南

## 🎯 项目概览

这是一个生产级的 AI 股票分析系统，使用：
- **Tushare Pro API** 获取 A 股日线数据
- **OpenAI GPT-4** 进行智能技术分析
- **Python 3.10+** 和 pandas 数据处理
- **模块化架构**，易于扩展和维护

## ⚡ 快速开始（5分钟）

### 步骤 1: 选择分析模式

**本地模式**（推荐快速开始）
- 无需 OpenAI API Key
- 完全免费
- 立即可用

**API 模式**
- 需要 OpenAI API Key
- 更高精度
- 需要付费

### 步骤 2: 获取必要的 API Keys

**Tushare Pro**（两种模式都需要）
- 访问 https://tushare.pro
- 注册账号（免费）
- 获取 API Token

**OpenAI**（仅 API 模式需要）
- 访问 https://platform.openai.com
- 创建 API Key（需要支付方式）

### 步骤 3: 安装环境

```bash
# macOS/Linux
cd ai_stock_agent
python -m venv venv
source venv/bin/activate

# Windows
cd ai_stock_agent
python -m venv venv
venv\Scripts\activate
```

### 步骤 4: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 5: 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑 .env 文件
vim .env
```

**本地模式配置**（推荐）：
```
TUSHARE_TOKEN=your_token_here
ANALYSIS_MODE=local          # 关键：使用本地分析
```

**API 模式配置**：
```
TUSHARE_TOKEN=your_token_here
ANALYSIS_MODE=api            # 关键：使用 API 分析
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4
```

### 步骤 6: 运行系统

```bash
# 方法 1: 直接运行（推荐）
python ai_stock_agent/main.py

# 方法 2: 使用启动脚本
bash run.sh              # macOS/Linux
run.bat                  # Windows

# 方法 3: 运行示例代码
python example_usage.py
```

## 📋 文件结构详解

```
ai_stock_agent/
│
├── config/settings.py
│  └── 所有配置管理，包括 API 密钥、路径、参数
│
├── data/stock_pool.json
│  └── 股票池配置（易于添加/移除股票）
│
├── tushare_api/downloader.py
│  └── Tushare 数据下载，支持单个和批量下载
│
├── indicators/technical.py
│  └── 技术指标计算（MA, VOL, 等）
│
├── strategy/feature_builder.py
│  └── 特征处理，将原始数据转换为 AI 所需的格式
│
├── agent/llm_agent.py
│  └── OpenAI API 调用，生成交易信号
│
├── report/report_generator.py
│  └── 生成 CSV 报告，按评分排序
│
└── main.py
   └── 主程序，协调所有模块

.env.example              # 环境变量示例
requirements.txt          # 依赖列表
run.sh / run.bat         # 启动脚本
check_config.py          # 配置检查工具
test_features.py         # 功能测试脚本
example_usage.py         # 使用示例
```

## 🔧 核心功能说明

### 1. 数据下载 (downloader.py)

```python
from tushare_api.downloader import TushareDownloader

downloader = TushareDownloader()

# 下载单个股票
df = downloader.get_daily_data("000001.SZ", days=30)

# 批量下载
data = downloader.get_multiple_stocks(["000001.SZ", "600000.SH"])
```

### 2. 计算指标 (technical.py)

```python
from indicators.technical import TechnicalIndicator

# 计算所有指标
df = TechnicalIndicator.calculate_all_indicators(df)

# 获取最新指标
latest = TechnicalIndicator.get_latest_indicators(df)
```

计算的指标：
- MA5, MA10, MA20（移动平均线）
- VOL_MA5（成交量MA）
- VOLUME_RATIO（成交量比率）
- HIGH_5D, LOW_5D（5日最高/最低）
- PCT_CHANGE（日涨跌幅）

### 3. 构建特征 (feature_builder.py)

```python
from strategy.feature_builder import FeatureBuilder

# 为单个股票构建特征
features = FeatureBuilder.build_features(df, "000001.SZ")

# 批量构建
features_dict = FeatureBuilder.build_features_batch(data_dict)
```

特征包含：
- 价格特征（close, open, high, low, 涨幅）
- 移动平均线特征
- 成交量特征
- 趋势特征
- 历史统计

### 4. 分析模块（两种模式可选）

**本地分析 (local_analyzer.py)**

```python
from agent.local_analyzer import LocalAnalyzer

analyzer = LocalAnalyzer()

# 分析单个股票
signal = analyzer.analyze_stock(features)

# 批量分析
signals = analyzer.analyze_batch(features_dict)
```

**API 分析 (llm_agent.py)**

```python
from agent.llm_agent import LLMAgent

agent = LLMAgent()

# 分析单个股票
signal = agent.analyze_stock(features)

# 批量分析
signals = agent.analyze_batch(features_dict)
```

两种模式返回的信号格式相同：
```python
{
    "symbol": "000001.SZ",
    "signal": "BUY",              # BUY/WATCH/SELL
    "score": 75,                  # 0-100 评分
    "confidence": 85,             # 信心指数
    "entry_price": 10.50,         # 建议入场价
    "stop_loss": 9.80,            # 止损价格
    "target_price": 12.00,        # 目标价格
    "reason": "短期上升明显；成交量放大；价格站上MA20"
}
```

**模式对比**

| 特性 | 本地模式 | API 模式 |
|------|---------|---------|
| 成本 | 免费 💰 | 付费（¥2-30/天） |
| 速度 | 快速 ⚡ | 较慢（需要网络调用） |
| 精度 | 一般（规则优化） | 精准（AI驱动） |
| 依赖 | 无外部依赖 | 需要 OpenAI API |
| 自定义 | 易于调整规则权重 | 难以定制 |

**选择建议**：
- 💡 快速开始或成本敏感 → 本地模式
- 💡 追求最高精度 → API 模式
- 💡 对比测试 → 两种都试试

### 5. 生成报告 (report_generator.py)

```python
from report.report_generator import ReportGenerator

# 生成标准报告
path = ReportGenerator.generate_report(signals)

# 生成详细报告
path = ReportGenerator.generate_detailed_report(signals, features_dict)

# 打印摘要
ReportGenerator.print_report_summary(signals)
```

## 📊 使用场景

### 场景 1: 快速测试

```bash
# 检查配置是否正确
python check_config.py

# 测试数据下载和指标计算
python test_features.py
```

### 场景 2: 查看使用示例

```bash
# 交互式示例（推荐新手）
python example_usage.py
```

### 场景 3: 每日自动运行

使用 cron (macOS/Linux) 或任务计划 (Windows):

```bash
# 每天 15:30 运行（A 股收盘后）
30 15 * * 1-5 cd /path/to/ai_stock_agent && bash run.sh
```

### 场景 4: 自定义分析

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "ai_stock_agent"))

from tushare_api.downloader import TushareDownloader
from indicators.technical import TechnicalIndicator
from strategy.feature_builder import FeatureBuilder
from agent.llm_agent import LLMAgent

# 自定义编写分析流程
downloader = TushareDownloader()
df = downloader.get_daily_data("600519.SH", days=60)
df = TechnicalIndicator.calculate_all_indicators(df)
features = FeatureBuilder.build_features(df, "600519.SH")

agent = LLMAgent()
signal = agent.analyze_stock(features)

print(f"分析结果: {signal}")
```

## 🔐 安全最佳实践

1. **环境变量隔离**
   ```bash
   # 不要提交 .env 到版本控制
   git config core.excludesfile .gitignore
   ```

2. **定期轮换密钥**
   - 每月更换一次 OpenAI API Key
   - 每月更换一次 Tushare Token

3. **监控成本**
   - 定期检查 OpenAI 使用费
   - 考虑使用 gpt-3.5-turbo 降低成本

4. **日志记录**
   - 检查 logs/stock_agent.log 了解执行情况
   - 定期备份重要日志

## 🚨 常见问题

### Q: 本地模式 vs API 模式，怎么选择？

**A:** 取决于你的需求：
- **本地模式**（推荐新手）：完全免费，无需 API Key，立即可用
- **API 模式**（追求精度）：更智能准确，但需要付费

在 .env 文件中设置 `ANALYSIS_MODE=local` 或 `ANALYSIS_MODE=api`

### Q: 如果设置了 ANALYSIS_MODE=local，需要 OpenAI API Key 吗？

**A:** 不需要！本地模式完全独立，只需要 Tushare Token

### Q: 连接 OpenAI 超时

**A:** 检查两点：
1. 网络连接是否正常
2. API Key 是否有效
3. 修改 config/settings.py 中的 API_TIMEOUT

### Q: Tushare 返回无数据

**A:** 可能的原因：
1. Token 无效或过期
2. 股票代码格式错误（应为 `000001.SZ`）
3. 周末或节假日无数据

### Q: 如何降低 OpenAI 成本？

**A:** 几个建议：
1. 改用 gpt-3.5-turbo 模型（速度快，价格低）
2. 减少 LLM_MAX_TOKENS（默认 1000）
3. 减少分析股票的数量
4. 优先使用本地模式（完全免费）

### Q: 能否随时切换分析模式？

**A:** 可以！直接修改 .env 中的 `ANALYSIS_MODE` 值，重新运行即可。两种模式返回相同的信号格式

### Q: 如何添加新股票？

**A:** 编辑 data/stock_pool.json：
```json
{
  "stocks": [
    "000001.SZ",    # 添加 ts_code
    "新股票代码.SZ"
  ]
}
```

### Q: 如何自定义技术指标？

**A:** 编辑 indicators/technical.py，添加新的计算方法

### Q: 能否支持其他数据源？

**A:** 可以！修改 downloader.py，替换数据源即可

### Q: 本地模式的分析逻辑是什么？

**A:** 基于得分制（0-100）：
- 趋势强度（40%）：MA 交叉、价格动量、形态识别
- 量价配合（30%）：成交量比、价量配合度
- 技术面（30%）：价格定位、MA 间距

信号判定：
- BUY：得分 ≥ 70
- WATCH：得分 40-70  
- SELL：得分 < 40

## 📈 性能优化建议

1. **缓存机制**
   ```python
   # 缓存已下载的数据，避免重复请求
   df_cache = {}
   ```

2. **批量处理**
   ```python
   # 一次性下载多个股票比逐个下载快
   data_dict = downloader.get_multiple_stocks(stocks)
   ```

3. **异步 API 调用**
   ```python
   # 可以使用 asyncio 并发调用 LLM
   import asyncio
   ```

4. **预计算指标**
   ```python
   # 提前计算好指标，重用结果
   indicators_cache = {}
   ```

## 📞 技术支持

遇到问题？按以下顺序排查：

1. ✅ 运行 `python check_config.py` 检查配置
2. ✅ 查看 `logs/stock_agent.log` 日志文件
3. ✅ 运行 `python test_features.py` 测试功能
4. ✅ 查看项目代码中的注释和文档

## 📚 相关资源

- [Tushare Pro 文档](https://tushare.pro/document/2)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [pandas 数据处理](https://pandas.pydata.org/docs/)
- [Python 虚拟环境](https://docs.python.org/3/tutorial/venv.html)

## 🎓 推荐阅读顺序

1. 本快速启动指南（5分钟）
2. readme.md（了解项目详情）
3. config/settings.py（理解配置项）
4. main.py（理解主逻辑）
5. 各模块代码（深入学习）

---

**版本**: 1.0.0  
**最后更新**: 2024年  
**维护者**: Quantitative Trading Team

祝你使用愉快！🚀
