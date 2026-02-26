## 📦 完整项目结构树

```
trading_stocks/
│
├── 📄 README.md                          ⭐ 项目详细文档
├── 📄 QUICKSTART.md                      ⭐ 快速启动指南（从这里开始）
├── 📄 requirements.txt                   ⭐ Python依赖列表
├── 📄 .env.example                       ⭐ 环境变量示例
├── 📄 .gitignore                        安全配置
│
├── 🚀 run.sh                            启动脚本 (macOS/Linux)
├── 🚀 run.bat                           启动脚本 (Windows)
├── 🚀 setup.py                          初始化脚本
│
├── 🧪 test_features.py                  功能测试工具
├── 🧪 check_config.py                   配置检查工具
├── 💡 example_usage.py                  使用示例
│
├── 📁 logs/                             日志目录（自动生成）
│   └── stock_agent.log
│
└── 📁 ai_stock_agent/                   ⭐ 主项目目录
    │
    ├── 📄 main.py                       主程序入口
    ├── 📄 __init__.py                   包标记
    │
    ├── 📁 config/                       配置模块
    │   ├── settings.py                  所有配置项
    │   └── __init__.py
    │
    ├── 📁 data/                         数据目录
    │   ├── stock_pool.json              股票池配置（易于修改）
    │   └── (下载的CSV数据，可选)
    │
    ├── 📁 tushare_api/                  数据获取模块
    │   ├── downloader.py                Tushare API 调用
    │   └── __init__.py
    │
    ├── 📁 indicators/                   技术指标模块
    │   ├── technical.py                 指标计算（MA, MACD等）
    │   └── __init__.py
    │
    ├── 📁 strategy/                     策略模块
    │   ├── feature_builder.py           特征工程
    │   └── __init__.py
    │
    ├── 📁 agent/                        AI代理模块
    │   ├── llm_agent.py                 OpenAI API 调用
    │   └── __init__.py
    │
    └── 📁 report/                       报告生成模块
        ├── report_generator.py          生成CSV报告
        ├── __init__.py
        └── (生成的CSV报告)
```

## 🎯 各文件功能速览

### 核心业务代码

| 文件 | 行数 | 功能说明 |
|------|------|--------|
| `tushare_api/downloader.py` | ~180 | Tushare API 数据下载，支持单个/批量 |
| `indicators/technical.py` | ~250 | 计算技术指标（MA, VOL, etc） |
| `strategy/feature_builder.py` | ~200 | 构建 AI 分析所需的特征向量 |
| `agent/llm_agent.py` | ~250 | 调用 OpenAI API 生成交易信号 |
| `report/report_generator.py` | ~200 | 生成 CSV 报告，支持详细模式 |
| `config/settings.py` | ~50 | 所有配置项管理 |
| `main.py` | ~150 | 主程序协调流程 |

### 工具脚本

| 文件 | 功能 |
|------|------|
| `check_config.py` | 检查配置是否正确 ✅ |
| `test_features.py` | 测试单个功能模块 🧪 |
| `example_usage.py` | 交互式使用示例 💡 |
| `setup.py` | 初始化项目（创建目录） 🔧 |
| `run.sh` / `run.bat` | 一键启动脚本 🚀 |

## 🔄 数据处理流程

```
┌─────────────────────────────────────────────────────────────┐
│  1️⃣  加载股票池                                              │
│      stock_pool.json → ["000001.SZ", "600000.SH", ...]       │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  2️⃣  下载 Tushare 日线数据                                    │
│      TushareDownloader.get_multiple_stocks()                 │
│      输出: DataFrame(trade_date, open, high, low, close, vol) │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  3️⃣  计算技术指标                                            │
│      TechnicalIndicator.calculate_all_indicators()           │
│      计算: MA5, MA10, MA20, VOL_MA, VOLUME_RATIO, etc        │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  4️⃣  构建特征向量                                            │
│      FeatureBuilder.build_features()                         │
│      输出: {price, MA, volume, trend, history_stats}         │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  5️⃣  LLM 智能分析                                            │
│      LLMAgent.analyze_stock()                                │
│      输入: 特征向量                                           │
│      输出: {signal, score, entry_price, stop_loss, reason}  │
└────────────────────┬────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────┐
│  6️⃣  生成报告                                                │
│      ReportGenerator.generate_report()                       │
│      输出: stock_signals_YYYYMMDD_HHMMSS.csv                 │
└─────────────────────────────────────────────────────────────┘
```

## 🔑 配置关键项目

### 必填配置（.env）
```
TUSHARE_TOKEN=<从 tushare.pro 获取>
OPENAI_API_KEY=<从 platform.openai.com 获取>
```

### 可选配置
```
OPENAI_MODEL=gpt-4          # 或 gpt-3.5-turbo（更便宜）
LLM_TEMPERATURE=0.7         # 分析创意度，0-2
LOOKBACK_DAYS=30            # 回溯多少天的数据
API_TIMEOUT=30              # API 超时时间
```

### 股票池配置（data/stock_pool.json）
```json
{
  "stocks": [
    "000001.SZ",   # 平安银行
    "600519.SH",   # 贵州茅台
    "你的股票代码"
  ]
}
```

## 📊 交易信号说明

系统生成的信号及其含义：

```
┌──────────────┬──────────────────┬────────────────────────────────┐
│ 信号类型      │ 含义              │ 适用情况                        │
├──────────────┼──────────────────┼────────────────────────────────┤
│ BUY          │ 强烈看好，建议买入 │ score > 70 且趋势向好           │
│ WATCH        │ 持续观察，等待机会 │ score 40-70，信号不够明确      │
│ SELL         │ 建议卖出或观望     │ score < 40 或下跌趋势           │
└──────────────┴──────────────────┴────────────────────────────────┘

每个信号包含：
├── score (0-100)        → 综合评分
├── confidence (0-100)   → 信心指数
├── entry_price          → 建议入场价
├── stop_loss            → 止损价格
├── target_price         → 利润目标价
└── reason               → 详细分析理由
```

## 🚀 不同场景的使用方法

### 场景1️⃣: 第一次使用
```bash
1. python setup.py                    # 初始化（创建目录）
2. vim .env                           # 填入 API Keys
3. python check_config.py             # 验证配置
4. python example_usage.py            # 运行示例
```

### 场景2️⃣: 日常运行
```bash
bash run.sh                           # macOS/Linux
# 或
run.bat                               # Windows
```

### 场景3️⃣: 定时任务（cron）
```bash
# 每天 15:30 自动运行（A股收盘后）
30 15 * * 1-5 /path/to/run.sh >> /path/to/logs/cron.log 2>&1
```

### 场景4️⃣: 自定义分析
```python
# 修改 main.py 或创建新脚本，使用各个模块
from tushare_api.downloader import TushareDownloader
from indicators.technical import TechnicalIndicator
from agent.llm_agent import LLMAgent
# ... 自定义逻辑
```

## 📈 成本分析

### Tushare Pro
- 免费版: 基础数据 OK ✅
- 专业版: ¥58/月（推荐）

### OpenAI API
| 模型 | 输入价格 | 输出价格 | 推荐 |
|------|--------|--------|------|
| gpt-4 | $0.03/1K | $0.06/1K | 高精度 |
| gpt-4-turbo | $0.01/1K | $0.03/1K | ⭐ 推荐 |
| gpt-3.5-turbo | $0.0005/1K | $0.0015/1K | 经济 |

**成本估算**: 分析 20 个股票/天
- 使用 gpt-3.5-turbo: ~$0.30/天 = ¥2.20/天
- 使用 gpt-4-turbo: ~$2/天 = ¥14.6/天

## ✅ 快速检查清单

使用前确保：

- [ ] 克隆或创建了项目目录
- [ ] 申请了 Tushare Token
- [ ] 创建了 OpenAI API Key
- [ ] 复制并编辑了 .env.example → .env
- [ ] 运行 `python check_config.py` 通过检查
- [ ] 修改了 stock_pool.json（添加你的股票）
- [ ] 运行过 `python test_features.py` 测试功能
- [ ] 理解了数据处理流程
- [ ] 知道报告输出位置

## 🆘 故障排查

| 问题 | 解决方案 |
|------|--------|
| API Key 无效 | 重新生成 Key，更新 .env |
| 下载数据为空 | 检查股票代码格式（如 000001.SZ） |
| No module named ... | 运行 `pip install -r requirements.txt` |
| Connection timeout | 等待网络恢复，或更改 API_TIMEOUT |
| OpenAI rate limit | 实施请求限流，或升级账户 |

运行 `python check_config.py` 快速诊断！

## 📞 获取帮助

1. **查看日志**: `logs/stock_agent.log`
2. **运行测试**: `python test_features.py`
3. **检查配置**: `python check_config.py`
4. **查看文档**: README.md, QUICKSTART.md
5. **审查代码**: 注释详细，易于理解

## 🎓 学习资源

- [Tushare 文档](https://tushare.pro/document/)
- [OpenAI Cookbook](https://github.com/openai/openai-cookbook)
- [pandas 教程](https://pandas.pydata.org/docs/user_guide/)
- [Python 3.10+ 新特性](https://docs.python.org/3/whatsnew/)

---

**项目完成！** ✅

所有核心文件已生成，可以立即使用。

祝分析顺利！🎯📈
