@echo off
REM AI 股票分析系统 - Windows 启动脚本

echo 🚀 AI 股票分析系统启动脚本
echo ================================

REM 检查 Python 版本
echo 📌 检查 Python 版本...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

echo ✅ Python 已安装

REM 检查虚拟环境
if not exist "venv" (
    echo 📦 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
echo 🔄 激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo 📥 安装依赖包...
pip install -r requirements.txt -q

REM 检查 .env 文件
if not exist ".env" (
    echo ⚠️  未找到 .env 文件
    echo ✏️  正在创建 .env 文件（基于 .env.example）...
    copy .env.example .env
    echo ❌ 请编辑 .env 文件，填入你的 API Keys
    pause
    exit /b 1
)

REM 检查 API Keys
findstr /m "your_tushare_token_here" .env >nul
if %errorlevel% equ 0 (
    echo ❌ TUSHARE_TOKEN 未配置，请编辑 .env 文件
    pause
    exit /b 1
)

findstr /m "your_openai_api_key_here" .env >nul
if %errorlevel% equ 0 (
    echo ❌ OPENAI_API_KEY 未配置，请编辑 .env 文件
    pause
    exit /b 1
)

echo.
echo ✅ 所有检查通过！
echo.
echo ▶️  启动分析系统...
echo ================================

REM 运行主程序
python ai_stock_agent\main.py

echo.
echo ✅ 程序执行完成
echo 📊 报告已保存到 report\ 目录
pause
