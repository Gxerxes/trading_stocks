"""
快速开始示例 - 展示如何使用各个模块
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_stock_agent"))

import logging
from config.settings import TUSHARE_TOKEN, ANALYSIS_MODE, OPENAI_API_KEY
from tushare_api.downloader import TushareDownloader
from indicators.technical import TechnicalIndicator
from strategy.feature_builder import FeatureBuilder
from agent.llm_agent import LLMAgent
from agent.local_analyzer import LocalAnalyzer
from report.report_generator import ReportGenerator

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_single_stock():
    """示例: 分析单个股票"""
    print("\n" + "="*60)
    print("示例: 分析单个股票")
    print("="*60)
    
    # 1. 下载数据
    logger.info("下载 000001.SZ（平安银行）的数据...")
    downloader = TushareDownloader()
    df = downloader.get_daily_data("000001.SZ", days=30)
    
    if df is None:
        logger.error("数据下载失败")
        return
    
    logger.info(f"成功获取 {len(df)} 条数据")
    
    # 2. 计算指标
    logger.info("计算技术指标...")
    df = TechnicalIndicator.calculate_all_indicators(df)
    
    # 3. 构建特征
    logger.info("构建特征...")
    features = FeatureBuilder.build_features(df, "000001.SZ")
    
    if features is None:
        logger.error("特征构建失败")
        return
    
    # 4. 调用分析器（根据配置选择）
    logger.info(f"使用 {ANALYSIS_MODE} 模式进行分析...")
    if ANALYSIS_MODE.lower() == "api":
        analyzer = LLMAgent()
    else:
        analyzer = LocalAnalyzer()
    
    signal = analyzer.analyze_stock(features)
    
    # 5. 打印结果
    print("\n🎯 分析结果:")
    print("-" * 60)
    print(f"分析模式: {ANALYSIS_MODE.upper()}")
    print(f"股票代码: {signal['symbol']}")
    print(f"交易日期: {features['trade_date']}")
    print(f"最新价格: {features['price']['close']:.2f}")
    print(f"涨跌幅: {features['price']['pct_change']:.2f}%")
    print("")
    print(f"信号: {signal['signal']}")
    print(f"评分: {signal['score']}/100")
    print(f"信心: {signal['confidence']}%")
    print("")
    print(f"建议入场: {signal['entry_price']:.2f}")
    print(f"止损价格: {signal['stop_loss']:.2f}")
    print(f"目标价格: {signal['target_price']:.2f}")
    print("")
    print(f"分析理由: {signal['reason']}")
    print("-" * 60)


def example_multiple_stocks():
    """示例: 分析多个股票"""
    print("\n" + "="*60)
    print("示例: 分析多个股票")
    print("="*60)
    
    stocks = ["000001.SZ", "600000.SH", "600519.SH"]
    
    # 1. 批量下载数据
    logger.info(f"下载 {len(stocks)} 个股票的数据...")
    downloader = TushareDownloader()
    data_dict = downloader.get_multiple_stocks(stocks, days=30)
    
    if not data_dict:
        logger.error("数据下载失败")
        return
    
    # 2. 批量计算指标
    logger.info("计算技术指标...")
    for ts_code, df in data_dict.items():
        data_dict[ts_code] = TechnicalIndicator.calculate_all_indicators(df)
    
    # 3. 批量构建特征
    logger.info("构建特征...")
    features_dict = FeatureBuilder.build_features_batch(data_dict)
    
    # 4. 批量分析（根据配置选择）
    logger.info(f"使用 {ANALYSIS_MODE} 模式进行分析...")
    if ANALYSIS_MODE.lower() == "api":
        analyzer = LLMAgent()
    else:
        analyzer = LocalAnalyzer()
    
    signals = analyzer.analyze_batch(features_dict)
    
    # 5. 生成报告
    logger.info("生成报告...")
    report_path = ReportGenerator.generate_report(signals)
    ReportGenerator.generate_detailed_report(signals, features_dict)
    
    # 6. 打印摘要
    print("\n📊 分析摘要:")
    print("-" * 60)
    print(f"分析模式: {ANALYSIS_MODE.upper()}")
    ReportGenerator.print_report_summary(signals)
    print(f"\n✅ 报告已保存: {report_path}")


def main():
    """运行示例"""
    print("\n" + "💡 "*20)
    print(" AI 股票分析系统 - 使用示例")
    print("💡 "*20)
    
    # 检查必要的配置
    if not TUSHARE_TOKEN:
        print("\n❌ Tushare Token 未配置")
        print("请在 .env 文件中设置: TUSHARE_TOKEN=<your-token>")
        return
    
    # 根据分析模式检查 API Key
    if ANALYSIS_MODE.lower() == "api" and not OPENAI_API_KEY:
        print("\n❌ OpenAI API Key 未配置（API 模式需要）")
        print("请在 .env 文件中设置: OPENAI_API_KEY=<your-key>")
        print("或者切换到本地模式: ANALYSIS_MODE=local")
        return
    
    # 显示当前配置
    print(f"\n✓ 分析模式: {ANALYSIS_MODE.upper()}")
    if ANALYSIS_MODE.lower() == "api":
        print("✓ Tushare Token: 已配置")
        print("✓ OpenAI API Key: 已配置")
    else:
        print("✓ Tushare Token: 已配置")
        print("✓ OpenAI API: 不需要（本地分析）")
    
    # 选择运行示例
    print("\n请选择运行的示例:")
    print("1. 分析单个股票（000001.SZ）")
    print("2. 分析多个股票（推荐）")
    print("q. 退出")
    
    choice = input("\n请输入选项 [1/2/q]: ").strip().lower()
    
    if choice == "1":
        example_single_stock()
    elif choice == "2":
        example_multiple_stocks()
    elif choice == "q":
        print("退出程序")
        return
    else:
        print("无效的选项")
        return
    
    print("\n✅ 示例完成")


if __name__ == "__main__":
    main()
