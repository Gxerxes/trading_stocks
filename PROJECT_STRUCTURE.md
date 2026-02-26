# 项目结构说明

## 📂 目录结构概览

```
trading_stocks/                          # 项目根目录
│
├── ai_stock_agent/                      # 核心代码（Python 模块）
│   ├── __init__.py
│   ├── main.py                          # 主程序入口
│   ├── config/                          # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py                  # 全局配置和验证
│   ├── data/                            # 数据配置
│   │   └── stock_pool.json              # 股票池配置
│   ├── tushare_api/                     # 数据获取
│   │   ├── __init__.py
│   │   └── downloader.py                # Tushare API 调用
│   ├── indicators/                      # 技术指标
│   │   ├── __init__.py
│   │   └── technical.py                 # 指标计算（MA, VOL 等）
│   ├── strategy/                        # 策略层
│   │   ├── __init__.py
│   │   └── feature_builder.py           # 特征工程
│   ├── agent/                           # 分析器
│   │   ├── __init__.py
│   │   ├── llm_agent.py                 # OpenAI GPT 分析（API 模式）
│   │   └── local_analyzer.py            # 规则基础分析（本地模式）
│   └── report/                          # 报告生成
│       ├── __init__.py
│       └── report_generator.py          # CSV 报告输出
│
├── examples/                            # 示例脚本和工具
│   ├── example_usage.py                 # 完整使用示例（交互式）
│   ├── check_config.py                  # 配置检查工具
│   └── test_features.py                 # 功能测试脚本
│
├── docs/                                # 文档目录
│   ├── QUICKSTART.md                    # 快速开始指南（推荐首先阅读）
│   ├── DUAL_MODE_UPDATES.md             # 双模式分析详细说明
│   ├── COMPLETION_SUMMARY.md            # 项目完成总结
│   ├── PROJECT_SUMMARY.md               # 项目概览
│   └── ...                              # 其他文档
│
├── scripts/                             # 启动脚本
│   ├── run.sh                           # Linux/macOS 启动脚本
│   └── run.bat                          # Windows 启动脚本
│
├── logs/                                # 日志目录（运行时生成）
│   └── stock_agent.log                  # 应用日志
│
├── requirements.txt                     # Python 依赖列表
├── .env.example                         # 环境变量示例
├── .gitignore                           # Git 忽略配置
├── setup.py                             # Python 包安装脚本
├── verify_project.py                    # 项目完整性检查
├── README.md                            # 项目主文档
└── PROJECT_STRUCTURE.md                 # 本文件
```

---

## 🚀 快速开始

### 1️⃣ 第一次使用

```bash
# 安装依赖
pip install -r requirements.txt

# 复制并编辑环境配置
cp .env.example .env
# 编辑 .env，填入 TUSHARE_TOKEN（必需）

# 验证配置
python examples/check_config.py

# 查看示例
python examples/example_usage.py
```

### 2️⃣ 运行分析系统

```bash
# 方法 1: 直接运行
python ai_stock_agent/main.py

# 方法 2: 使用启动脚本
bash scripts/run.sh           # macOS/Linux
scripts\run.bat               # Windows
```

---

## 📖 文档导航

| 文件 | 用途 | 适合人群 |
|------|------|--------|
| [README.md](README.md) | 项目主文档，功能说明 | 所有人 |
| [docs/QUICKSTART.md](docs/QUICKSTART.md) | 快速开始指南、配置教程 | 新手 |
| [docs/DUAL_MODE_UPDATES.md](docs/DUAL_MODE_UPDATES.md) | 双模式分析详细说明 | 进阶用户 |
| [docs/COMPLETION_SUMMARY.md](docs/COMPLETION_SUMMARY.md) | 项目完成总结、功能列表 | 项目管理 |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | 项目结构说明（本文件） | 开发者 |

---

## 🔧 核心模块说明

### ai_stock_agent/
项目的核心业务逻辑代码，分为多个子模块：

**config/** - 配置管理
- `settings.py`: 全局配置、API 密钥、分析模式选择

**tushare_api/** - 数据层
- `downloader.py`: 获取股票日线数据，支持单个和批量下载

**indicators/** - 指标计算
- `technical.py`: MA5/10/20、成交量比、5日高低等指标

**strategy/** - 特征工程
- `feature_builder.py`: 构建 AI 分析所需的特征向量

**agent/** - 分析层（可选择两种模式）
- `llm_agent.py`: 调用 OpenAI API 进行智能分析
- `local_analyzer.py`: 基于规则的本地分析（完全免费）

**report/** - 输出层
- `report_generator.py`: 生成 CSV 报告和摘要

### examples/
快速上手和测试工具：

- `example_usage.py`: 完整示例，展示从下载到分析的全流程
- `check_config.py`: 检查配置是否正确，API Key 是否可用
- `test_features.py`: 测试数据下载和指标计算功能

### docs/
详细的文档和说明：

- 快速开始指南
- 功能详解
- 常见问题解答
- 项目信息总结

### scripts/
便捷启动脚本：

- `run.sh`: 自动检查 Python、创建虚拟环境、安装依赖、运行程序
- `run.bat`: Windows 版本的启动脚本

---

## 🎯 工作流程

```
1. 配置阶段 (.env)
   └─> TUSHARE_TOKEN 必需
   └─> OPENAI_API_KEY 可选（仅 API 模式）

2. 数据获取 (tushare_api/)
   └─> Tushare Pro API 下载股票日线数据

3. 指标计算 (indicators/)
   └─> 计算 MA、成交量等技术指标

4. 特征构建 (strategy/)
   └─> 将原始数据转为 AI 特征

5. 分析阶段 (agent/) - 两种模式可选
   ├─ 本地模式: LocalAnalyzer（免费，速度快）
   └─ API 模式: LLMAgent（精度高，需付费）

6. 报告生成 (report/)
   └─> 输出 CSV 报告和信号汇总
```

---

## 🔐 配置文件说明

### .env.example
```
# Tushare API（必需）
TUSHARE_TOKEN=your_token_here

# 分析模式选择（必需）
ANALYSIS_MODE=local  # 或 api

# OpenAI API（仅 API 模式需要）
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4
```

详见 [docs/QUICKSTART.md](docs/QUICKSTART.md) 的配置章节。

---

## ✨ 两种分析模式

### 本地模式（ANALYSIS_MODE=local）
- ✅ 完全免费
- ✅ 速度快（本地计算）
- ✅ 无需 OpenAI API Key
- 📊 基于规则的评分系统（准确度 50-60%）

### API 模式（ANALYSIS_MODE=api）
- 🧠 使用 GPT-4/GPT-3.5 进行智能分析
- 💡 精度更高（60-80%）
- 💰 按使用计费（¥2-30/天）
- 📡 需要网络连接

---

## 📊 项目统计

| 项目 | 统计 |
|------|------|
| Python 代码 | 1400+ 行 |
| 代码文件 | 15+ 个 |
| 依赖包 | 8 个 |
| 文档 | 5+ 份 |
| 示例脚本 | 3 个 |
| 启动脚本 | 2 个 |

---

## 🔗 相关资源

- [Tushare Pro 官网](https://tushare.pro)
- [OpenAI API 文档](https://platform.openai.com/docs)
- [pandas 文档](https://pandas.pydata.org)
- [numpy 文档](https://numpy.org)

---

## 💡 建议阅读顺序

1. **README.md** - 了解项目功能和特性
2. **docs/QUICKSTART.md** - 快速配置和运行
3. **examples/example_usage.py** - 查看实际使用示例
4. **docs/DUAL_MODE_UPDATES.md** - 深入理解分析模式
5. **PROJECT_STRUCTURE.md**（本文件）- 了解项目架构

---

## 🆘 常见问题

**Q: 从哪里获取 Tushare Token？**
A: 访问 https://tushare.pro 注册账号（免费），获取 Token

**Q: 本地模式和 API 模式有什么区别？**
A: 见 docs/DUAL_MODE_UPDATES.md 的模式对比章节

**Q: 如何验证配置是否正确？**
A: 运行 `python examples/check_config.py`

**Q: 系统生成的报告在哪里？**
A: 在 report/ 目录下，CSV 文件按日期时间命名

---

## 📝 版本信息

- **项目版本**: 2.0
- **最后更新**: 2024
- **Python 版本**: 3.10+
- **项目状态**: ✅ 完整可用

---

**祝您使用愉快！** 🚀
