"""
配置管理模块 - 读取环境变量和系统配置
"""

import os
from pathlib import Path
from typing import Optional, List

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "ai_stock_agent"

# 自动加载项目根目录 .env（若 python-dotenv 可用）
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except Exception:
    # 未安装 python-dotenv 或加载失败时，回退系统环境变量
    pass

# API 配置
TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "f8a677295862ba0cee74b5c6909d8704c04485c27f6a93257480526a")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE: Optional[str] = os.getenv("OPENAI_API_BASE", None)
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")

# 分析模式配置
ANALYSIS_MODE: str = os.getenv("ANALYSIS_MODE", "local")  # "local" 或 "api"
# local - 使用本地规则分析（免费，无需 API）
# api   - 调用 OpenAI API（需要 API Key）

# 策略名称映射：兼容旧名称，统一到规范名称
STRATEGY_NAME_MAP = {
    "local": "trend_momentum_volume",
    "trend_momentum_volume": "trend_momentum_volume",
    "tmv": "trend_momentum_volume",
    "api": "api",
    "wyckoff": "wyckoff",
}


def _parse_strategies() -> List[str]:
    """
    解析策略配置，支持单选或多选（逗号分隔）。
    兼容老配置：未设置 STRATEGIES 时，回退到 ANALYSIS_MODE。
    """
    strategies_raw = os.getenv("STRATEGIES", "").strip()
    if strategies_raw:
        raw_list = [s.strip().lower() for s in strategies_raw.split(",") if s.strip()]
    else:
        # 兼容旧逻辑
        mode = ANALYSIS_MODE.lower()
        raw_list = [mode if mode in {"local", "api"} else "local"]

    strategies = [STRATEGY_NAME_MAP.get(s, s) for s in raw_list]

    # 去重并保持顺序
    deduped = []
    for strategy in strategies:
        if strategy not in deduped:
            deduped.append(strategy)
    return deduped


STRATEGIES: List[str] = _parse_strategies()

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
DAILY_HISTORY_DIR = DATA_DIR / "daily_history"
DAILY_BASIC_HISTORY_DIR = DATA_DIR / "daily_basic_history"
STRATEGY_SIGNAL_DIR = REPORT_DIR / "strategy_signals"
STOCK_POOL_FILE = Path(
    os.getenv("STOCK_POOL_FILE", str(DATA_DIR / "stock_pool.json"))
)

# 创建必要的目录
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)
DAILY_DATA_DIR.mkdir(parents=True, exist_ok=True)
DAILY_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
DAILY_BASIC_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
STRATEGY_SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

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

    valid_strategies = {"trend_momentum_volume", "api", "wyckoff"}
    invalid_strategies = [s for s in STRATEGIES if s not in valid_strategies]
    if invalid_strategies:
        raise ValueError(
            f"STRATEGIES 包含无效策略: {invalid_strategies}，"
            f"可选值: {sorted(valid_strategies)}"
        )
    
    # API 模式需要 API Key，本地模式不需要
    if "api" in STRATEGIES and not OPENAI_API_KEY:
        raise ValueError("STRATEGIES 包含 api 时需要设置 OPENAI_API_KEY 环境变量")
    
    return True
