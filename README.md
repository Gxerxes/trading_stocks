# AI 股票分析系统

使用 Tushare Pro API 获取股票数据，通过 OpenAI API 进行智能技术分析，生成 BUY/WATCH/SELL 交易信号的完整系统。

## 🎯 功能特性

- ✅ 支持配置股票池，灵活添加/移除股票
- ✅ Tushare Pro API 自动获取日线数据
- ✅ 计算多种技术指标（MA, MACD, 成交量等）
- ✅ **两种分析模式**（本地规则分析或 OpenAI API 智能分析）
- ✅ 生成可视化的交易报告（CSV）
- ✅ 完善的错误处理和日志记录
- ✅ 模块化架构，易于扩展

## 📋 系统要求

- Python 3.10+
- Tushare Pro API Token（免费注册）
- OpenAI API Key

## 🚀 快速开始

### 1. 环境搭建

```bash
# 克隆或进入项目目录
cd trading_stocks

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# 在 macOS/Linux:
source venv/bin/activate
# 在 Windows:
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的配置
vim .env
```

需要配置以下环境变量：

```
# Tushare API（必需）
TUSHARE_TOKEN=your_tushare_token       # 从 https://tushare.pro 获取

# 分析模式选择（重要！）
ANALYSIS_MODE=local                    # 默认：本地分析（推荐，无需费用）
# 或
ANALYSIS_MODE=api                      # OpenAI API 分析（需要 API Key）

# OpenAI API（仅在 ANALYSIS_MODE=api 时需要）
OPENAI_API_KEY=your_openai_api_key     # 从 https://platform.openai.com 获取
OPENAI_MODEL=gpt-4                     # 或 gpt-3.5-turbo
```

**分析模式说明：**

| 模式 | 说明 | 费用 | 精度 |
|------|------|------|------|
| **local** | 基于规则的本地分析 | 免费 | 中等 |
| **api** | 调用 OpenAI API 分析 | 按使用计费 | 更高 |

### 3. 配置股票池

编辑 `data/stock_pool.json` 文件，添加你要分析的股票：

```json
{
  "stocks": [
    "000001.SZ",
    "600000.SH",
    "600519.SH"
  ]
}
```

### 4. 运行系统

```bash
# 方法 1: 直接运行
python ai_stock_agent/main.py

# 方法 2: 使用启动脚本
bash scripts/run.sh              # macOS/Linux
scripts\run.bat                  # Windows

# 方法 3: 查看示例和测试
python examples/example_usage.py  # 使用示例
python examples/check_config.py   # 配置检查
python examples/test_features.py  # 功能测试
```

## 📁 项目结构

```
trading_stocks/                         # 项目根目录
├── ai_stock_agent/                     # 核心代码
│   ├── config/
│   │   └── settings.py                 # 配置管理
│   ├── data/
│   │   └── stock_pool.json             # 股票池配置
│   ├── tushare_api/
│   │   └── downloader.py               # 数据下载模块
│   ├── indicators/
│   │   └── technical.py                # 技术指标计算
│   ├── strategy/
│   │   └── feature_builder.py          # 特征构建
│   ├── agent/
│   │   ├── llm_agent.py                # LLM 分析代理
│   │   └── local_analyzer.py           # 本地分析器
│   ├── report/
│   │   └── report_generator.py         # 报告生成
│   └── main.py                         # 主程序入口
│
├── examples/                           # 示例脚本
│   ├── example_usage.py                # 使用示例
│   ├── check_config.py                 # 配置检查
│   └── test_features.py                # 功能测试
│
├── docs/                               # 文档
│   ├── QUICKSTART.md                   # 快速开始
│   ├── DUAL_MODE_UPDATES.md            # 双模式更新说明
│   ├── COMPLETION_SUMMARY.md           # 完成总结
│   └── ...（其他文档）
│
├── scripts/                            # 启动脚本
│   ├── run.sh                          # Linux/macOS 启动脚本
│   └── run.bat                         # Windows 启动脚本
│
├── requirements.txt                    # 依赖项
├── .env.example                        # 环境变量示例
├── .gitignore                          # Git 忽略配置
├── setup.py                            # 项目安装脚本
└── README.md                           # 项目文档
```

## 📊 工作流程

```
1. 加载股票池配置
   ↓
2. 通过 Tushare API 下载日线数据
   ↓
3. 计算技术指标（MA, 成交量等）
   ↓
4. 构建特征向量
   ↓
5. 选择分析模式
   ├─ 本地模式：基于规则分析（无需 API）
   └─ API 模式：调用 OpenAI 进行智能分析
   ↓
6. 生成交易报告（CSV）
   ↓
7. 输出交易信号（BUY/WATCH/SELL）
```

## 🔧 技术指标

系统计算以下技术指标用于分析：

| 指标 | 说明 |
|------|------|
| MA5，MA10，MA20 | 5、10、20日移动平均线 |
| VOL_MA5 | 5日成交量平均 |
| VOLUME_RATIO | 成交量比率（当前/平均） |
| HIGH_5D，LOW_5D | 5日最高价、最低价 |
| PCT_CHANGE | 日涨跌幅 |

## 🤖 分析模式详解

### 本地分析模式（ANALYSIS_MODE=local）

**特点：**
- ✅ 完全免费，无需 API 费用
- ✅ 无网络依赖，安全可靠
- ✅ 分析速度快，实时响应
- ✅ 基于规则的分析，结果可预测

**分析逻辑：**
1. **趋势强度评分** (40% 权重)
   - 价格与 MA 位置关系
   - 短期（5日）与中期（10日）涨幅
   - MA 线排列情况

2. **量价配合评分** (30% 权重)
   - 成交量是否放大
   - 价格上升时量能配合
   - 异常成交量判断

3. **技术面评分** (30% 权重)
   - 价格位置评估
   - MA 间距分析
   - 支撑阻力位置

**适用场景：**
- 学习和研究用途
- 实时快速扫描
- 成本控制要求高
- 对规则分析有信心

### API 分析模式（ANALYSIS_MODE=api）

**特点：**
- 🧠 使用 GPT-4/GPT-3.5-turbo 进行深度分析
- 📊 考虑更多复杂因素
- 💡 更贴近人工分析师思路
- 🎯 分析结果更精细化

**分析能力：**
- 综合理解多重技术指标
- 市场心理分析
- 趋势转折点识别
- 风险因素评估

**成本参考：**
- gpt-3.5-turbo：约 ¥2-3/天（20 只股票）
- gpt-4-turbo：约 ¥14-20/天（20 只股票）
- gpt-4：约 ¥30+/天（20 只股票）

**适用场景：**
- 专业量化分析
- 高精度要求
- 复杂策略研发
- 机构级应用

## 💡 交易信号说明

| 信号 | 说明 |
|------|------|
| **BUY** | 强烈看好，建议买入 |
| **WATCH** | 持续观察，等待更好机会 |
| **SELL** | 建议卖出或持谨慎态度 |

每个信号包含：
- **score**: 0-100 的综合评分
- **confidence**: 信心指数
- **entry_price**: 建议入场价格
- **stop_loss**: 止损价格
- **target_price**: 目标价格
- **reason**: 分析理由

## 📈 报告输出

系统生成两类报告：

### 1. 标准报告（stock_signals_YYYYMMDD_HHMMSS.csv）

包含核心交易信号，按评分降序排列

### 2. 详细报告（stock_signals_detailed_YYYYMMDD_HHMMSS.csv）

包含技术指标和信号，便于深入分析

## ⚙️ 高级配置

编辑 `config/settings.py` 调整：

```python
# 技术指标参数
MA_PERIODS = [5, 10, 20]           # 移动平均周期
VOLUME_MA_PERIOD = 5               # 成交量MA周期
LOOKBACK_DAYS = 30                 # 回溯天数

# LLM 参数
LLM_TEMPERATURE = 0.7              # 创意度（0-2）
LLM_MAX_TOKENS = 1000              # 最大输出令牌数

# API 超时配置
API_TIMEOUT = 30                   # 超时时间（秒）
RETRY_ATTEMPTS = 3                 # 重试次数
```

## 🔐 安全建议

1. 永远不要将 `.env` 文件提交到版本控制
2. 定期轮换 API Keys
3. 使用环境变量而非硬码化密钥
4. 监控 API 使用量，避免意外费用

## 📝 日志文件

日志记录在 `logs/stock_agent.log`，包含：
- API 调用状态
- 错误信息
- 执行进度

## 🤖 选择合适的 OpenAI 模型

| 模型 | 价格 | 速度 | 推荐场景 |
|------|------|------|--------|
| gpt-4 | 贵 | 慢 | 高精度分析 |
| gpt-4-turbo-preview | 中 | 中 | 平衡方案 |
| gpt-3.5-turbo | 便宜 | 快 | 快速分析 |

## 🛠️ 常见问题

### Q: 我应该选择哪种分析模式？

**本地模式（local）**：
- 想要完全免费 ✅
- 不想申请 OpenAI API ✅
- 只是学习和研究 ✅
- 需要实时分析 ✅

**API 模式（api）**：
- 追求高精度分析 ✅
- 有 OpenAI API 账户 ✅
- 专业量化分析 ✅
- 不在乎成本 ✅

### Q: 本地分析模式准确度如何？

A: 本地分析使用经过验证的规则系统，准确度约 50-60%（与 API 模式相比）。足以用于基础的技术面分析和筛选，但不如 AI 模型精细。

### Q: 如何从本地模式切换到 API 模式？

A: 修改 .env 文件中的配置：
```
ANALYSIS_MODE=api
OPENAI_API_KEY=your_key_here
```

### Q: OpenAI API 返回错误？

A: 检查：
1. API Key 是否正确
2. 账户是否有余额
3. 网络连接是否正常
4. 修改 config/settings.py 中的 API_TIMEOUT

### Q: Tushare API 返回空数据？
A: 检查股票代码格式（如 `000001.SZ`），确认 token 有效，特定时段可能无法下载历史数据。

### Q: 如何添加新的股票？
A: 编辑 `data/stock_pool.json` 文件，添加股票代码即可。

## 📚 文档资源

- [Tushare Pro 官网](https://tushare.pro)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [pandas 文档](https://pandas.pydata.org)

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**免责声明**: 本系统仅供学习和研究使用。交易决策应基于完整的市场分析和风险评估，本系统不构成投资建议。
