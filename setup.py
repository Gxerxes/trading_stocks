"""
快速安装和首次运行脚本
"""

import os
import sys
import json
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
AI_STOCK_AGENT = PROJECT_ROOT / "ai_stock_agent"


def create_logs_dir():
    """创建日志目录"""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    # 创建 .gitkeep 文件，保留目录
    gitkeep = logs_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    
    print(f"✅ 日志目录已创建: {logs_dir}")
    return logs_dir


def create_report_dir():
    """创建报告目录"""
    report_dir = PROJECT_ROOT / "ai_stock_agent" / "report"
    report_dir.mkdir(exist_ok=True)
    
    # 创建 .gitkeep 文件，保留目录
    gitkeep = report_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    
    print(f"✅ 报告目录已创建: {report_dir}")
    return report_dir


def create_env_file():
    """创建 .env 文件"""
    env_file = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"
    
    if env_file.exists():
        print(f"⚠️  .env 文件已存在，跳过创建")
        return env_file
    
    if env_example.exists():
        with open(env_example, 'r') as f:
            content = f.read()
        with open(env_file, 'w') as f:
            f.write(content)
        print(f"✅ .env 文件已创建（基于 .env.example）")
        print(f"⚠️  请编辑 {env_file}，填入你的 API Keys")
    else:
        print(f"❌ .env.example 文件不存在")
    
    return env_file


def check_project_structure():
    """检查项目结构"""
    print("\n📁 项目结构检查")
    print("-" * 50)
    
    required_dirs = [
        "config",
        "data",
        "tushare_api",
        "indicators",
        "strategy",
        "agent",
        "report",
    ]
    
    all_ok = True
    for dir_name in required_dirs:
        dir_path = AI_STOCK_AGENT / dir_name
        if dir_path.exists():
            print(f"✅ {dir_name}")
        else:
            print(f"❌ {dir_name}")
            all_ok = False
    
    return all_ok


def main():
    """主安装流程"""
    print("\n" + "🚀 "*20)
    print(" AI 股票分析系统 - 初始化安装")
    print("🚀 "*20 + "\n")
    
    try:
        print("📋 开始初始化...")
        print("-" * 50)
        
        # 创建必要的目录
        create_logs_dir()
        create_report_dir()
        
        # 检查项目结构
        if not check_project_structure():
            print("\n❌ 项目结构不完整！")
            return False
        
        # 创建 .env 文件
        print("\n🔐 环境配置")
        print("-" * 50)
        create_env_file()
        
        print("\n" + "="*50)
        print("✅ 初始化完成！")
        print("="*50)
        print("\n📝 后续步骤:")
        print("1. 编辑 .env 文件，设置 API Keys:")
        print(f"   TUSHARE_TOKEN=<your-token>")
        print(f"   OPENAI_API_KEY=<your-key>")
        print("")
        print("2. 根据需要编辑 data/stock_pool.json")
        print("")
        print("3. 运行配置检查:")
        print("   python check_config.py")
        print("")
        print("4. 运行主程序:")
        print("   python ai_stock_agent/main.py")
        print("")
        print("或使用启动脚本:")
        print("   bash run.sh       # macOS/Linux")
        print("   run.bat          # Windows")
        print("="*50 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
