#!/usr/bin/env python3
"""
完整的项目验证脚本 - 一键检查所有文件是否完整
"""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent


def check_files():
    """检查所有必要文件是否存在"""
    
    required_files = {
        "Python 代码": [
            "ai_stock_agent/__init__.py",
            "ai_stock_agent/main.py",
            "ai_stock_agent/config/__init__.py",
            "ai_stock_agent/config/settings.py",
            "ai_stock_agent/data/stock_pool.json",
            "ai_stock_agent/tushare_api/__init__.py",
            "ai_stock_agent/tushare_api/downloader.py",
            "ai_stock_agent/indicators/__init__.py",
            "ai_stock_agent/indicators/technical.py",
            "ai_stock_agent/strategy/__init__.py",
            "ai_stock_agent/strategy/feature_builder.py",
            "ai_stock_agent/agent/__init__.py",
            "ai_stock_agent/agent/llm_agent.py",
            "ai_stock_agent/agent/local_analyzer.py",
            "ai_stock_agent/report/__init__.py",
            "ai_stock_agent/report/report_generator.py",
        ],
        "配置文件": [
            "requirements.txt",
            ".env.example",
            ".gitignore",
        ],
        "文档": [
            "README.md",
            "docs/QUICKSTART.md",
            "docs/PROJECT_SUMMARY.md",
        ],
        "脚本": [
            "scripts/run.sh",
            "scripts/run.bat",
            "setup.py",
            "examples/check_config.py",
            "examples/test_features.py",
            "examples/example_usage.py",
            "verify_project.py",
        ],
        "目录": [
            "logs",
            "ai_stock_agent/report",
            "examples",
            "docs",
            "scripts",
        ]
    }
    
    print("\n" + "="*70)
    print("🔍 AI 股票分析系统 - 完整性检查")
    print("="*70)
    
    all_ok = True
    
    for category, files in required_files.items():
        print(f"\n📋 {category}:")
        print("-" * 70)
        
        category_ok = True
        for file_path in files:
            full_path = PROJECT_ROOT / file_path
            exists = full_path.exists()
            status = "✅" if exists else "❌"
            
            # 获取文件大小
            if exists:
                try:
                    size = full_path.stat().st_size
                    size_str = f" ({size:,} bytes)"
                except:
                    size_str = ""
            else:
                size_str = " (缺失)"
            
            print(f"{status} {file_path}{size_str}")
            
            if not exists:
                category_ok = False
                all_ok = False
        
        if category_ok:
            print(f"✅ {category} - 全部完整")
        else:
            print(f"❌ {category} - 存在缺失")
    
    return all_ok


def check_file_sizes():
    """检查关键文件的大小"""
    print("\n" + "="*70)
    print("📊 关键代码文件大小统计")
    print("="*70 + "\n")
    
    py_files = list((PROJECT_ROOT / "ai_stock_agent").rglob("*.py"))
    
    total_size = 0
    total_lines = 0
    
    print(f"{'文件':<50} {'大小':>15} {'行数':>10}")
    print("-" * 75)
    
    for py_file in sorted(py_files):
        try:
            size = py_file.stat().st_size
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = len(f.readlines())
            
            size_kb = size / 1024
            rel_path = py_file.relative_to(PROJECT_ROOT)
            
            print(f"{str(rel_path):<50} {size_kb:>14.1f}KB {lines:>10}")
            
            total_size += size
            total_lines += lines
        except:
            pass
    
    print("-" * 75)
    print(f"{'总计':<50} {total_size/1024:>14.1f}KB {total_lines:>10}")


def check_dependencies():
    """检查是否有 requirements.txt"""
    req_file = PROJECT_ROOT / "requirements.txt"
    
    print("\n" + "="*70)
    print("📦 依赖包配置")
    print("="*70 + "\n")
    
    if req_file.exists():
        print(f"✅ requirements.txt 存在")
        print("\n内容预览:")
        print("-" * 70)
        
        with open(req_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    print(f"  • {line}")
    else:
        print(f"❌ requirements.txt 不存在")


def show_installation_guide():
    """显示安装指南"""
    print("\n" + "="*70)
    print("快速安装指南")
    print("="*70 + "\n")
    
    print("""
1. 安装依赖
   pip install -r requirements.txt

2. 配置 API Keys
   cp .env.example .env
   # 编辑 .env，填入你的 API Keys

3. 验证配置
   python examples/check_config.py
4. 运行系统
   python ai_stock_agent/main.py

更多详情: 查看 docs/QUICKSTART.md
""")


def main():
    """主函数"""
    
    # 检查文件
    all_ok = check_files()
    
    # 检查大小
    check_file_sizes()
    
    # 检查依赖
    check_dependencies()
    
    # 显示安装指南
    show_installation_guide()
    
    # 最终结论
    print("="*70)
    if all_ok:
        print("✅ 项目结构完整！可以开始使用了")
        print("\n📖 建议按以下顺序操作:")
        print("   1. 阅读 docs/QUICKSTART.md")
        print("   2. 修改 .env，添加 API Keys")
        print("   3. 运行 python examples/check_config.py")
        print("   4. 运行 python examples/example_usage.py")
    else:
        print("❌ 项目结构不完整，请重新检查")
    print("="*70 + "\n")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
