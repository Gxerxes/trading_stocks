"""
特征构建模块 - 将原始数据转换为结构化特征
"""

import logging
import pandas as pd
from typing import Dict, Any, Optional
from indicators.technical import TechnicalIndicator

logger = logging.getLogger(__name__)


class FeatureBuilder:
    """特征构建器，用于生成AI分析所需的特征"""
    
    @staticmethod
    def build_features(df: pd.DataFrame, ts_code: str) -> Optional[Dict[str, Any]]:
        """
        为单个股票构建特征字典
        
        Args:
            df: 包含技术指标的DataFrame
            ts_code: 股票代码
            
        Returns:
            包含特征的字典，格式用于LLM分析
        """
        try:
            if df is None or len(df) < 5:
                logger.warning(f"{ts_code} 数据不足，无法构建特征")
                return None
            
            # 确保指标已计算
            if 'MA5' not in df.columns:
                df = TechnicalIndicator.calculate_all_indicators(df)
            
            # 获取最新指标
            latest = TechnicalIndicator.get_latest_indicators(df)
            
            # 获取历史统计
            hist_5day = TechnicalIndicator.get_historical_summary(df, period=5)
            hist_10day = TechnicalIndicator.get_historical_summary(df, period=10)
            
            # 生成趋势判断特征
            trend_features = FeatureBuilder._calculate_trend_features(df)
            
            # 生成量价特征
            price_volume_features = FeatureBuilder._calculate_price_volume_features(df)
            
            # 构建完整特征字典
            features = {
                'symbol': ts_code,
                'trade_date': str(latest.get('trade_date')),
                
                # 价格特征
                'price': {
                    'close': latest['close'],
                    'open': latest['open'],
                    'high': latest['high'],
                    'low': latest['low'],
                    'pct_change': latest['PCT_CHANGE'],
                },
                
                # 移动平均线
                'moving_averages': {
                    'MA5': latest['MA5'],
                    'MA10': latest['MA10'],
                    'MA20': latest['MA20'],
                    'close_vs_ma5': latest['close'] - latest['MA5'],
                    'close_vs_ma20': latest['close'] - latest['MA20'],
                },
                
                # 成交量特征
                'volume': {
                    'current_vol': latest['vol'],
                    'vol_ma5': latest['VOL_MA5'],
                    'volume_ratio': latest['VOLUME_RATIO'],
                },
                
                # 高低点特征
                'price_range': {
                    'high_5d': latest['HIGH_5D'],
                    'low_5d': latest['LOW_5D'],
                    'current_price_position': (latest['close'] - latest['LOW_5D']) / (latest['HIGH_5D'] - latest['LOW_5D']) if latest['HIGH_5D'] != latest['LOW_5D'] else 0.5,
                },
                
                # 历史统计
                'history_5day': hist_5day,
                'history_10day': hist_10day,
                
                # 趋势特征
                'trend': trend_features,
                
                # 量价特征
                'price_volume': price_volume_features,
            }
            
            logger.info(f"成功为 {ts_code} 构建特征")
            return features
            
        except Exception as e:
            logger.error(f"为 {ts_code} 构建特征失败: {e}")
            return None
    
    @staticmethod
    def _calculate_trend_features(df: pd.DataFrame) -> Dict[str, Any]:
        """计算趋势特征"""
        if len(df) < 10:
            return {'status': 'insufficient_data'}
        
        recent_5 = df.tail(5)
        recent_10 = df.tail(10)
        
        # 5日趋势
        pct_change_5d = (df.iloc[-1]['close'] - df.iloc[-5]['close']) / df.iloc[-5]['close'] * 100
        
        # 10日趋势
        pct_change_10d = (df.iloc[-1]['close'] - df.iloc[-10]['close']) / df.iloc[-10]['close'] * 100
        
        # 判断上升/下降趋势
        close_above_ma20 = df.iloc[-1]['close'] > df.iloc[-1]['MA20']
        close_above_ma5 = df.iloc[-1]['close'] > df.iloc[-1]['MA5']
        
        return {
            'pct_change_5d': pct_change_5d,
            'pct_change_10d': pct_change_10d,
            'close_above_ma5': close_above_ma5,
            'close_above_ma20': close_above_ma20,
            'ma5_above_ma20': df.iloc[-1]['MA5'] > df.iloc[-1]['MA20'],
        }
    
    @staticmethod
    def _calculate_price_volume_features(df: pd.DataFrame) -> Dict[str, Any]:
        """计算量价关联特征"""
        if len(df) < 5:
            return {}
        
        recent_5 = df.tail(5)
        
        # 成交量增长率
        vol_change = (df.iloc[-1]['vol'] - df.iloc[-2]['vol']) / df.iloc[-2]['vol'] * 100 if df.iloc[-2]['vol'] > 0 else 0
        
        # 价格上升时成交量是否放大
        price_up = df.iloc[-1]['close'] > df.iloc[-2]['close']
        vol_up = df.iloc[-1]['vol'] > df.iloc[-2]['vol']
        vol_price_sync = price_up and vol_up
        
        return {
            'vol_change_pct': vol_change,
            'vol_price_synchronized': vol_price_sync,
            'avg_volume_5d': float(recent_5['vol'].mean()),
        }
    
    @staticmethod
    def build_features_batch(
        data_dict: Dict[str, pd.DataFrame]
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        批量构建多个股票的特征
        
        Args:
            data_dict: 字典，key为ts_code，value为DataFrame
            
        Returns:
            字典，key为ts_code，value为特征字典
        """
        features_dict = {}
        
        for ts_code, df in data_dict.items():
            features = FeatureBuilder.build_features(df, ts_code)
            if features:
                features_dict[ts_code] = features
        
        logger.info(f"完成 {len(features_dict)} 个股票的特征构建")
        return features_dict
