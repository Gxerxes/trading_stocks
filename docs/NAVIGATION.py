"""
文件导航地图 - 快速定位你需要的文件

使用这个指南快速找到项目中的各个文件及其功能
"""

print("""
================================================================================
📍 AI 股票分析系统 - 文件导航地图
================================================================================

1️⃣  我要快速开始
   └─ 📖 START_HERE.md         ← 开始这里！
   └─ 📖 QUICKSTART.md          快速启动指南（5分钟）
   └─ 🚀 python example_usage.py 交互式示例

2️⃣  我要了解项目
   └─ 📖 README.md              完整的项目文档和说明
   └─ 📖 PROJECT_SUMMARY.md     项目详细总结
   └─ 📖 QUICKSTART.md          快速启动指南

3️⃣  我要配置系统
   
   环境配置:
   ├─ 📄 .env.example           API Keys 配置模板
   │  └─ [复制] → .env          (你需要修改这个文件)
   │
   股票配置:
   └─ 📄 ai_stock_agent/data/stock_pool.json
      └─ 编辑以添加/移除股票

4️⃣  我要运行程序
   
   简单方式（推荐）:
   ├─ 📜 run.sh                 启动脚本 (macOS/Linux)
   └─ 📜 run.bat                启动脚本 (Windows)
   
   直接运行:
   └─ 🐍 python ai_stock_agent/main.py
   
   示例运行:
   └─ 💡 python example_usage.py (交互式菜单)

5️⃣  我要检查配置和排查问题
   
   验证工具:
   ├─ 🔍 python verify_project.py   检查项目完整性
   ├─ 🛠️  python check_config.py    检查配置是否正确
   └─ 🧪 python test_features.py    测试各个模块
   
   查看日志:
   └─ 📋 logs/stock_agent.log      程序运行日志

6️⃣  我要理解核心代码（按执行顺序）
   
   配置管理:
   ├─ 📄 config/settings.py        所有配置参数
   │                                  • API Keys
   │                                  • 技术指标参数
   │                                  • 超时和重试配置
   │
   数据获取:
   ├─ 📄 tushare_api/downloader.py 从 Tushare 下载数据
   │                                  • get_daily_data()
   │                                  • get_multiple_stocks()
   │
   技术分析:
   ├─ 📄 indicators/technical.py    计算各种技术指标
   │                                  • calculate_ma()
   │                                  • calculate_all_indicators()
   │                                  • get_latest_indicators()
   │
   特征工程:
   ├─ 📄 strategy/feature_builder.py 构建 AI 分析所需的特征
   │                                  • build_features()
   │                                  • build_features_batch()
   │
   AI 分析:
   ├─ 📄 agent/llm_agent.py         调用 OpenAI API
   │                                  • analyze_stock()
   │                                  • analyze_batch()
   │
   报告生成:
   ├─ 📄 report/report_generator.py 生成 CSV 报告
   │                                  • generate_report()
   │                                  • print_report_summary()
   │
   主程序:
   └─ 📄 main.py                   协调所有模块的执行流程

7️⃣  我要看实际的数据输出
   
   生成的报告:
   └─ 📁 ai_stock_agent/report/
      ├─ stock_signals_YYYYMMDD_HHMMSS.csv      标准报告
      └─ stock_signals_detailed_YYYYMMDD_HHMMSS.csv 详细报告

8️⃣  我要修改或扩展功能
   
   添加新股票:
   └─ 编辑 → ai_stock_agent/data/stock_pool.json
   
   修改技术指标:
   └─ 编辑 → ai_stock_agent/indicators/technical.py
   
   自定义分析提示词:
   └─ 编辑 → ai_stock_agent/agent/llm_agent.py (_build_prompt)
   
   修改报告格式:
   └─ 编辑 → ai_stock_agent/report/report_generator.py
   
   调整配置参数:
   └─ 编辑 → ai_stock_agent/config/settings.py

9️⃣  我要设置自动运行（定时任务）
   
   macOS/Linux (Cron):
   └─ 编辑 crontab
      30 15 * * 1-5 /path/to/run.sh >> /path/to/logs/cron.log
   
   Windows (任务计划):
   └─ Windows 任务计划程序
      └─ 每天 15:30 运行 run.bat

🔟  项目文件结构（完整版）
   
┌─ 📁 trading_stocks/
│
├─ 📄 START_HERE.md                  ← 从这里开始！
├─ 📄 README.md                      项目文档
├─ 📄 QUICKSTART.md                  快速启动
├─ 📄 PROJECT_SUMMARY.md             项目总结
├─ 📄 .env.example                   API 配置模板
├─ 📄 .gitignore                     Git 配置
├─ 📄 requirements.txt               Python 依赖
│
├─ 🚀 run.sh                         启动脚本 (Unix)
├─ 🚀 run.bat                        启动脚本 (Windows)
├─ 🚀 setup.py                       项目初始化
│
├─ 🔧 verify_project.py              项目完整性检查
├─ 🔧 check_config.py                配置检查工具
├─ 🔧 test_features.py               功能测试工具
├─ 💡 example_usage.py               使用示例
│
├─ 📁 logs/                          日志目录
│  └─ stock_agent.log                运行日志
│
└─ 📁 ai_stock_agent/                主项目目录
   │
   ├─ 🐍 main.py                     主程序入口
   │
   ├─ 📁 config/
   │  └─ settings.py                 配置管理
   │
   ├─ 📁 data/
   │  └─ stock_pool.json             股票池配置
   │
   ├─ 📁 tushare_api/
   │  └─ downloader.py               数据下载模块
   │
   ├─ 📁 indicators/
   │  └─ technical.py                技术指标计算
   │
   ├─ 📁 strategy/
   │  └─ feature_builder.py          特征工程
   │
   ├─ 📁 agent/
   │  └─ llm_agent.py                AI 分析模块
   │
   └─ 📁 report/
      ├─ report_generator.py         报告生成
      └─ (generated CSV files)       输出报告

================================================================================
🎯 按场景快速导航
================================================================================

我是初学者，想快速体验:
   1. 阅读: START_HERE.md
   2. 运行: python example_usage.py
   3. 查看: ai_stock_agent/report/*.csv

我想理解工作流程:
   1. 阅读: QUICKSTART.md
   2. 查看: ai_stock_agent/main.py
   3. 运行: python test_features.py

我想生产级使用:
   1. 阅读: README.md
   2. 配置: .env 文件
   3. 运行: bash run.sh 或 python ai_stock_agent/main.py

我想集成到自己的系统:
   1. 理解: PROJECT_SUMMARY.md
   2. 研究: 各模块源代码
   3. 修改: config/settings.py 和各模块

我想添加自己的股票:
   1. 编辑: ai_stock_agent/data/stock_pool.json
   2. 添加: "YOUR_STOCK_CODE.SZ" 或 ".SH"
   3. 运行: python ai_stock_agent/main.py

我遇到了问题:
   1. 运行: python verify_project.py
   2. 查看: logs/stock_agent.log
   3. 运行: python check_config.py
   4. 运行: python test_features.py

我想修改分析逻辑:
   1. 查看: ai_stock_agent/agent/llm_agent.py (_build_prompt)
   2. 修改: 分析提示词内容
   3. 测试: python test_features.py

我想优化成本:
   1. 编辑: .env 中的 OPENAI_MODEL
   2. 改为: OPENAI_MODEL=gpt-3.5-turbo
   3. 运行: python ai_stock_agent/main.py

================================================================================
📊 数据流和模块依赖关系
================================================================================

输入数据流:
  stock_pool.json → TushareDownloader → DataFrame → 技术指标 → 特征向量

分析流程:
  特征向量 → LLMAgent → 交易信号

输出数据流:
  交易信号 → ReportGenerator → CSV 报告

模块依赖:
  main.py
    ├── config/settings.py
    ├── tushare_api/downloader.py
    ├── indicators/technical.py
    ├── strategy/feature_builder.py
    ├── agent/llm_agent.py
    └── report/report_generator.py

================================================================================
⌨️  快捷命令参考
================================================================================

初始化:
  $ python setup.py

检查:
  $ python verify_project.py     # 检查项目完整性
  $ python check_config.py       # 检查配置
  $ python test_features.py      # 测试功能

运行:
  $ python ai_stock_agent/main.py     # 直接运行
  $ bash run.sh                       # 使用脚本 (Unix)
  $ run.bat                           # 使用脚本 (Windows)
  $ python example_usage.py           # 示例程序

查看日志:
  $ tail -f logs/stock_agent.log

安装依赖:
  $ pip install -r requirements.txt

================================================================================

💡 提示: 大多数人应该从 START_HERE.md 或 QUICKSTART.md 开始！

祝你使用愉快！🚀

================================================================================
""")
