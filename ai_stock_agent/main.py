"""
主程序入口 - AI股票分析系统
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime

# 添加上层目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import (
    validate_config,
    STOCK_POOL_FILE,
    LOG_FILE,
    LOG_LEVEL,
    ANALYSIS_MODE,
    DAILY_DATA_DIR,
)
from tushare_api.downloader import TushareDownloader
from indicators.technical import TechnicalIndicator
from strategy.feature_builder import FeatureBuilder
from agent.llm_agent import LLMAgent
from agent.local_analyzer import LocalAnalyzer
from report.report_generator import ReportGenerator

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def load_stock_pool(stock_pool_file: Path) -> list:
    """
    加载股票池配置
    
    Args:
        stock_pool_file: stock_pool.json 文件路径
        
    Returns:
        股票代码列表
    """
    try:
        with open(stock_pool_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            stocks = config.get('stocks', [])
            logger.info(f"加载了 {len(stocks)} 个股票: {stocks[:5]}...")
            return stocks
    except Exception as e:
        logger.error(f"加载股票池失败: {e}")
        raise


def main():
    """主程序流程"""
    
    logger.info("="*60)
    logger.info("🚀 AI 股票分析系统启动")
    logger.info("="*60)
    
    try:
        # 验证配置
        logger.info("📋 验证配置...")
        validate_config()
        
        # 加载股票池
        logger.info("📥 加载股票池...")
        stocks = load_stock_pool(STOCK_POOL_FILE)
        
        if not stocks:
            logger.error("股票池为空，程序退出")
            return
        
        # 第一步: 下载数据
        logger.info("📥 下载Tushare全历史日线数据...")
        downloader = TushareDownloader()
        data_dict = downloader.get_multiple_stocks(stocks, days=None)

        if not data_dict:
            logger.error("未能下载任何股票数据")
            return

        # 保存每只股票的原始日线数据为CSV
        logger.info("💾 保存日线数据到CSV...")
        saved_files = downloader.save_to_csv_batch(data_dict, DAILY_DATA_DIR)
        logger.info(f"已保存 {len(saved_files)} 个CSV文件到: {DAILY_DATA_DIR}")

        # 第二步: 计算技术指标
        logger.info("📊 计算技术指标...")
        for ts_code, df in data_dict.items():
            data_dict[ts_code] = TechnicalIndicator.calculate_all_indicators(df)
        
        # 第三步: 构建特征
        logger.info("🔧 构建特征...")
        features_dict = FeatureBuilder.build_features_batch(data_dict)
        
        if not features_dict:
            logger.error("未能构建任何特征")
            return
        
        logger.info(f"成功构建 {len(features_dict)} 个特征")
        
        # 第四步: 进行智能分析
        logger.info(f"🤖 使用 {ANALYSIS_MODE} 模式进行分析...")
        
        if ANALYSIS_MODE.lower() == "api":
            # 使用 OpenAI API 分析
            llm_agent = LLMAgent()
            signals = llm_agent.analyze_batch(features_dict)
        else:
            # 使用本地规则分析（默认）
            local_analyzer = LocalAnalyzer()
            signals = local_analyzer.analyze_batch(features_dict)
        
        if not signals:
            logger.error("未能生成任何信号")
            return
        
        logger.info(f"生成了 {len(signals)} 个交易信号")
        
        # 第五步: 生成报告
        logger.info("📄 生成交易报告...")
        report_path = ReportGenerator.generate_report(signals)
        ReportGenerator.generate_detailed_report(signals, features_dict)
        
        # 打印摘要
        ReportGenerator.print_report_summary(signals)
        
        logger.info("")
        logger.info(f"✅ 分析完成！报告保存至: {report_path}")
        logger.info("="*60)
        
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常: {e}")
        logger.exception(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
