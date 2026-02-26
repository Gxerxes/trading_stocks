"""
独立的特征测试脚本 - 用于调试和验证
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_stock_agent"))

import logging
from config.settings import TUSHARE_TOKEN
from tushare_api.downloader import TushareDownloader
from indicators.technical import TechnicalIndicator
from strategy.feature_builder import FeatureBuilder

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_data_download():
    """测试数据下载功能"""
    print("\n" + "="*60)
    print("🧪 测试数据下载")
    print("="*60)
    
    try:
        downloader = TushareDownloader()
        
        # 测试单个股票
        print("\n📥 下载 000001.SZ 数据...")
        df = downloader.get_daily_data("000001.SZ", days=30)
        
        if df is not None:
            print(f"✅ 成功获取 {len(df)} 行数据")
            print("\n最后 3 行数据:")
            print(df.tail(3))
            return df
        else:
            print("❌ 下载失败")
            return None
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def test_indicators(df):
    """测试技术指标计算"""
    print("\n" + "="*60)
    print("🧪 测试技术指标计算")
    print("="*60)
    
    if df is None or len(df) == 0:
        print("❌ 数据为空")
        return None
    
    try:
        # 计算所有指标
        df_with_indicators = TechnicalIndicator.calculate_all_indicators(df)
        
        print(f"✅ 成功计算指标")
        print(f"\n最新一行数据的指标：")
        
        latest = TechnicalIndicator.get_latest_indicators(df_with_indicators)
        for key, value in latest.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        
        return df_with_indicators
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def test_feature_building(df):
    """测试特征构建"""
    print("\n" + "="*60)
    print("🧪 测试特征构建")
    print("="*60)
    
    if df is None or len(df) == 0:
        print("❌ 数据为空")
        return None
    
    try:
        # 先计算指标
        if 'MA5' not in df.columns:
            df = TechnicalIndicator.calculate_all_indicators(df)
        
        features = FeatureBuilder.build_features(df, "000001.SZ")
        
        if features:
            print("✅ 成功构建特征")
            print(f"\n特征结构：")
            for key, value in features.items():
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for k, v in value.items():
                        print(f"    {k}: {v}")
                else:
                    print(f"  {key}: {value}")
            return features
        else:
            print("❌ 特征构建失败")
            return None
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None


def main():
    """运行所有测试"""
    print("\n" + "🔧 "*10)
    print("AI 股票分析系统 - 功能测试")
    print("🔧 "*10)
    
    # 检查 Tushare Token
    if not TUSHARE_TOKEN:
        print("\n❌ TUSHARE_TOKEN 未配置")
        print("请在 .env 文件中设置: TUSHARE_TOKEN=<your-token>")
        return
    
    print("✅ TUSHARE_TOKEN 已配置")
    
    # 测试数据下载
    df = test_data_download()
    
    if df is None:
        return
    
    # 测试指标计算
    df_with_indicators = test_indicators(df)
    
    if df_with_indicators is None:
        return
    
    # 测试特征构建
    test_feature_building(df_with_indicators)
    
    print("\n" + "="*60)
    print("✅ 所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    main()
