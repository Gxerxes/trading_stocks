"""
配置验证脚本 - 检查所有必要配置是否正确
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "ai_stock_agent"))

from config.settings import (
    TUSHARE_TOKEN,
    ANALYSIS_MODE,
    OPENAI_API_KEY,
    OPENAI_API_BASE,
    OPENAI_MODEL,
    STOCK_POOL_FILE,
    PROJECT_ROOT
)
import json


def check_env_vars():
    """检查环境变量"""
    print("\n📋 环境变量检查")
    print("-" * 50)
    
    # 基础检查
    tushare_ok = bool(TUSHARE_TOKEN)
    print(f"{'✅' if tushare_ok else '❌'} TUSHARE_TOKEN: {'已设置' if tushare_ok else '未设置'}")
    
    # 显示分析模式
    mode = ANALYSIS_MODE.lower() if ANALYSIS_MODE else "local"
    print(f"✅ ANALYSIS_MODE: {mode.upper()}")
    
    # 根据分析模式检查 OpenAI API Key
    if mode == "api":
        openai_ok = bool(OPENAI_API_KEY)
        print(f"{'✅' if openai_ok else '❌'} OPENAI_API_KEY: {'已设置' if openai_ok else '未设置'}（API 模式需要）")
        print(f"✅ OPENAI_MODEL: {OPENAI_MODEL}")
        if OPENAI_API_BASE:
            print(f"✅ OPENAI_API_BASE: {OPENAI_API_BASE}")
        return tushare_ok and openai_ok
    else:
        print(f"✅ OPENAI_API_KEY: 不需要（本地分析模式）")
        return tushare_ok


def check_stock_pool():
    """检查股票池配置"""
    print("\n📊 股票池检查")
    print("-" * 50)
    
    try:
        with open(STOCK_POOL_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            stocks = config.get('stocks', [])
            
            print(f"✅ 股票池文件存在")
            print(f"✅ 共配置 {len(stocks)} 个股票")
            print(f"   示例: {stocks[:3]}")
            
            return len(stocks) > 0
    except FileNotFoundError:
        print(f"❌ 股票池文件不存在: {STOCK_POOL_FILE}")
        return False
    except Exception as e:
        print(f"❌ 股票池读取失败: {e}")
        return False


def check_directories():
    """检查必要的目录"""
    print("\n📁 目录检查")
    print("-" * 50)
    
    dirs = [
        PROJECT_ROOT,
        PROJECT_ROOT / "config",
        PROJECT_ROOT / "data",
        PROJECT_ROOT / "report",
    ]
    
    all_ok = True
    for dir_path in dirs:
        exists = dir_path.exists()
        status = "✅" if exists else "❌"
        print(f"{status} {dir_path.name}: {'存在' if exists else '不存在'}")
        all_ok = all_ok and exists
    
    return all_ok


def check_dependencies():
    """检查依赖包"""
    print("\n📦 依赖包检查")
    print("-" * 50)
    
    packages = [
        'pandas',
        'numpy',
        'tushare',
        'requests',
    ]
    
    # 如果使用 API 模式，检查 openai 包
    if (ANALYSIS_MODE.lower() if ANALYSIS_MODE else "local") == "api":
        packages.append('openai')
    
    missing = []
    for package in packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n💡 缺失包，请运行:")
        print(f"   pip install {' '.join(missing)}")
    
    return len(missing) == 0


def log_summary(results):
    """输出总结"""
    print("\n" + "="*50)
    print("📋 配置检查总结")
    print("="*50)
    
    checks_passed = sum(results.values())
    checks_total = len(results)
    
    items = [
        ("环境变量", results.get('env', False)),
        ("股票池配置", results.get('stock_pool', False)),
        ("目录结构", results.get('directories', False)),
        ("依赖包", results.get('dependencies', False)),
    ]
    
    for name, passed in items:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    print("\n" + "-"*50)
    if checks_passed == checks_total:
        print(f"✅ 所有检查通过！可以运行系统")
        print(f"\n运行命令: python ai_stock_agent/main.py")
    else:
        print(f"⚠️  有 {checks_total - checks_passed} 项检查未通过")
        print(f"   请根据上面的提示进行修复")
    print("="*50 + "\n")
    
    return checks_passed == checks_total


def main():
    """主函数"""
    print("\n🔍 "*15)
    print("AI 股票分析系统 - 配置检查")
    print("🔍 "*15)
    
    results = {
        'env': check_env_vars(),
        'stock_pool': check_stock_pool(),
        'directories': check_directories(),
        'dependencies': check_dependencies(),
    }
    
    all_ok = log_summary(results)
    
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
