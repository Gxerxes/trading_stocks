#!/bin/bash

# AI 股票分析系统 - 快速启动脚本

# 切换到项目根目录
cd "$(dirname "$0")/.."

echo "🚀 AI 股票分析系统启动脚本"
echo "================================"

# 检查 Python 版本
echo "📌 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✅ 检测到 Python $PYTHON_VERSION"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔄 激活虚拟环境..."
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖包..."
pip install -r requirements.txt -q

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "✏️  正在创建 .env 文件（基于 .env.example）..."
    cp .env.example .env
    echo "❌ 请编辑 .env 文件，填入必要的配置"
    echo "   vim .env"
    exit 1
fi

# 检查 Tushare Token
if grep -q "your_tushare_token_here" .env; then
    echo "❌ TUSHARE_TOKEN 未配置，请编辑 .env 文件"
    exit 1
fi

# 检查分析模式
ANALYSIS_MODE=$(grep "^ANALYSIS_MODE" .env | cut -d'=' -f2 | tr -d ' ')

# 如果使用 API 模式，检查 OpenAI API Key
if [ "$ANALYSIS_MODE" = "api" ] || [ -z "$ANALYSIS_MODE" ]; then
    if grep -q "your_openai_api_key_here" .env; then
        echo "❌ ANALYSIS_MODE=api 但 OPENAI_API_KEY 未配置"
        echo "   请在 .env 文件中填入 OPENAI_API_KEY，或改用本地模式 ANALYSIS_MODE=local"
        exit 1
    fi
    echo "✓ 分析模式: API（需要 OpenAI）"
else
    echo "✓ 分析模式: 本地分析（无需 OpenAI）"
fi

echo ""
echo "✅ 所有检查通过！"
echo ""
echo "▶️  启动分析系统..."
echo "================================"

# 运行主程序
python3 ai_stock_agent/main.py

echo ""
echo "✅ 程序执行完成"
echo "📊 报告已保存到 report/ 目录"
