"""
配置管理模块 - 读取环境变量和系统配置
"""

import os
from pathlib import Path
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "ai_stock_agent"

# API 配置
TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "f8a677295862ba0cee74b5c6909d8704c04485c27f6a93257480526a")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE", None)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")

# 分析模式配置
ANALYSIS_MODE: str = os.getenv("ANALYSIS_MODE", "local")  # "local" 或 "api"
# local - 使用本地规则分析（免费，无需 API）
# api   - 调用 OpenAI API（需要 API Key）

# 数据配置
ROOT_DATA_DIR = PROJECT_ROOT / "data"
APP_DATA_DIR = APP_ROOT / "data"

if (ROOT_DATA_DIR / "stock_pool.json").exists():
    DATA_DIR = ROOT_DATA_DIR
elif (APP_DATA_DIR / "stock_pool.json").exists():
    DATA_DIR = APP_DATA_DIR
else:
    # 默认使用项目根目录 data，首次运行时会自动创建
    DATA_DIR = ROOT_DATA_DIR

REPORT_DIR = PROJECT_ROOT / "report"
DAILY_DATA_DIR = DATA_DIR / "daily"
STOCK_POOL_FILE = Path(
    os.getenv("STOCK_POOL_FILE", str(DATA_DIR / "stock_pool.json"))
)

# 创建必要的目录
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
DAILY_DATA_DIR.mkdir(parents=True, exist_ok=True)

# 技术指标参数
MA_PERIODS = [5, 10, 20]
VOLUME_MA_PERIOD = 5
LOOKBACK_DAYS = 30  # 获取过去多少天的数据用于指标计算

# 日志配置
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = PROJECT_ROOT / "logs" / "stock_agent.log"
LOG_FILE.parent.mkdir(exist_ok=True)

# LLM 配置
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1000"))

# 超时配置（秒）
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))

def validate_config() -> bool:
    """验证必要的配置项"""
    if not TUSHARE_TOKEN:
        raise ValueError("TUSHARE_TOKEN 环境变量未设置")
    
    # API 模式需要 API Key，本地模式不需要
    if ANALYSIS_MODE == "api" and not OPENAI_API_KEY:
        raise ValueError("ANALYSIS_MODE=api 时需要设置 OPENAI_API_KEY 环境变量")
    
    return True
