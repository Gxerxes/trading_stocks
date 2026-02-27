"""
报告生成模块 - 生成交易报告并导出为CSV
"""

import logging
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from config.settings import REPORT_DIR

logger = logging.getLogger(__name__)


class ReportGenerator:
    """交易报告生成器"""
    
    @staticmethod
    def generate_report(
        signals: Dict[str, Dict[str, Any]],
        report_name: str = None
    ) -> Path:
        """
        生成交易报告并保存为CSV文件
        
        Args:
            signals: 信号字典，key为ts_code，value为信号字典
            report_name: 报告文件名（可选，默认使用时间戳）
            
        Returns:
            报告文件路径
        """
        try:
            # 生成文件名
            if report_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_name = f"stock_signals_{timestamp}.csv"
            
            report_path = REPORT_DIR / report_name
            
            # 按评分降序排序信号
            sorted_signals = sorted(
                signals.items(),
                key=lambda x: x[1].get('score', 0),
                reverse=True
            )
            
            # 写入CSV文件
            with open(report_path, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'symbol',
                    'signal',
                    'score',
                    'confidence',
                    'trend',
                    'stage',
                    'entry_price',
                    'stop_loss',
                    'target_price',
                    'reason'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # 写入表头
                writer.writeheader()
                
                # 写入数据行
                for ts_code, signal in sorted_signals:
                    row = {
                        'symbol': signal.get('symbol', ts_code),
                        'signal': signal.get('signal', 'WATCH'),
                        'score': signal.get('score', 0),
                        'confidence': signal.get('confidence', 0),
                        'trend': signal.get('trend', '未知'),
                        'stage': signal.get('stage', '未知'),
                        'entry_price': f"{signal.get('entry_price', 0):.2f}",
                        'stop_loss': f"{signal.get('stop_loss', 0):.2f}",
                        'target_price': f"{signal.get('target_price', 0):.2f}",
                        'reason': signal.get('reason', '')
                    }
                    writer.writerow(row)
            
            logger.info(f"报告已生成: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"生成报告异常: {e}")
            raise
    
    @staticmethod
    def print_report_summary(signals: Dict[str, Dict[str, Any]]) -> None:
        """
        打印报告摘要到日志
        
        Args:
            signals: 信号字典
        """
        if not signals:
            logger.info("没有生成任何信号")
            return
        
        # 统计各类信号
        buy_signals = [s for s in signals.values() if s.get('signal') == 'BUY']
        watch_signals = [s for s in signals.values() if s.get('signal') == 'WATCH']
        sell_signals = [s for s in signals.values() if s.get('signal') == 'SELL']
        
        logger.info("="*60)
        logger.info("📊 交易信号报告摘要")
        logger.info("="*60)
        logger.info(f"总分析股票数: {len(signals)}")
        logger.info(f"  ✅ BUY信号: {len(buy_signals)}")
        logger.info(f"  ⏳ WATCH信号: {len(watch_signals)}")
        logger.info(f"  ❌ SELL信号: {len(sell_signals)}")
        logger.info("")
        
        # 打印TOP 5
        sorted_signals = sorted(
            signals.items(),
            key=lambda x: x[1].get('score', 0),
            reverse=True
        )
        
        logger.info("📈 排名前5的股票：")
        for rank, (ts_code, signal) in enumerate(sorted_signals[:5], 1):
            logger.info(f"{rank}. {signal['symbol']} - "
                       f"信号:{signal['signal']} | "
                       f"评分:{signal['score']} | "
                       f"信心:{signal['confidence']}%")
        
        logger.info("="*60)
    
    @staticmethod
    def generate_detailed_report(
        signals: Dict[str, Dict[str, Any]],
        features_dict: Dict[str, Dict[str, Any]],
        report_name: str = None
    ) -> Path:
        """
        生成详细报告（包含技术指标）
        
        Args:
            signals: 信号字典
            features_dict: 特征字典
            report_name: 报告文件名
            
        Returns:
            报告文件路径
        """
        try:
            # 生成文件名
            if report_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_name = f"stock_signals_detailed_{timestamp}.csv"
            
            report_path = REPORT_DIR / report_name
            
            # 合并信号和特征
            merged_data = []
            for ts_code, signal in signals.items():
                features = features_dict.get(ts_code, {})
                merged = {
                    'symbol': signal.get('symbol', ts_code),
                    'signal': signal.get('signal', 'WATCH'),
                    'score': signal.get('score', 0),
                    'confidence': signal.get('confidence', 0),
                    'trend': signal.get('trend', '未知'),
                    'stage': signal.get('stage', '未知'),
                    'entry_price': f"{signal.get('entry_price', 0):.2f}",
                    'stop_loss': f"{signal.get('stop_loss', 0):.2f}",
                    'target_price': f"{signal.get('target_price', 0):.2f}",
                    'reason': signal.get('reason', ''),
                    'close_price': f"{features.get('price', {}).get('close', 0):.2f}",
                    'pct_change': f"{features.get('price', {}).get('pct_change', 0):.2f}%",
                    'MA5': f"{features.get('moving_averages', {}).get('MA5', 0):.2f}",
                    'MA20': f"{features.get('moving_averages', {}).get('MA20', 0):.2f}",
                    'volume_ratio': f"{features.get('volume', {}).get('volume_ratio', 0):.2f}",
                    'trade_date': features.get('trade_date', '')
                }
                merged_data.append(merged)
            
            # 按评分降序排序
            merged_data.sort(key=lambda x: float(x['score']), reverse=True)
            
            # 写入CSV文件
            with open(report_path, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'symbol', 'trade_date', 'close_price', 'pct_change',
                    'MA5', 'MA20', 'volume_ratio',
                    'signal', 'score', 'confidence', 'trend', 'stage',
                    'entry_price', 'stop_loss', 'target_price',
                    'reason'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(merged_data)
            
            logger.info(f"详细报告已生成: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"生成详细报告异常: {e}")
            raise
