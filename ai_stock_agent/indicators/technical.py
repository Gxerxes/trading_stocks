"""
技术指标计算模块
"""

import logging
import pandas as pd
import numpy as np
from typing import Dict, Any
from config.settings import MA_PERIODS, VOLUME_MA_PERIOD

logger = logging.getLogger(__name__)


class TechnicalIndicator:
    """技术指标计算类"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
        """
        计算移动平均线
        
        Args:
            df: DataFrame，必须包含 'close' 列
            periods: MA周期列表，默认 [5, 10, 20]
            
        Returns:
            添加了MA列的DataFrame
        """
        if periods is None:
            periods = MA_PERIODS
        
        for period in periods:
            col_name = f'MA{period}'
            df[col_name] = df['close'].rolling(window=period, min_periods=1).mean()
        
        return df
    
    @staticmethod
    def calculate_volume_ma(df: pd.DataFrame, period: int = VOLUME_MA_PERIOD) -> pd.DataFrame:
        """
        计算成交量移动平均
        
        Args:
            df: DataFrame，必须包含 'vol' 列
            period: MA周期
            
        Returns:
            添加了 VOL_MA 列的DataFrame
        """
        col_name = f'VOL_MA{period}'
        df[col_name] = df['vol'].rolling(window=period, min_periods=1).mean()
        return df
    
    @staticmethod
    def calculate_volume_ratio(df: pd.DataFrame, period: int = VOLUME_MA_PERIOD) -> pd.DataFrame:
        """
        计算成交量比率 (当前成交量 / MA成交量)
        
        Args:
            df: DataFrame
            period: MA周期
            
        Returns:
            添加了 VOLUME_RATIO 列的DataFrame
        """
        vol_ma_col = f'VOL_MA{period}'
        if vol_ma_col not in df.columns:
            df = TechnicalIndicator.calculate_volume_ma(df, period)
        
        df['VOLUME_RATIO'] = df['vol'] / df[vol_ma_col]
        df['VOLUME_RATIO'] = df['VOLUME_RATIO'].fillna(1.0)
        
        return df
    
    @staticmethod
    def calculate_high_low(df: pd.DataFrame, period: int = 5) -> pd.DataFrame:
        """
        计算过去N天的最高价和最低价
        
        Args:
            df: DataFrame
            period: 周期
            
        Returns:
            添加了 HIGH_N 和 LOW_N 列的DataFrame
        """
        df[f'HIGH_{period}D'] = df['high'].rolling(window=period, min_periods=1).max()
        df[f'LOW_{period}D'] = df['low'].rolling(window=period, min_periods=1).min()
        
        return df
    
    @staticmethod
    def calculate_pct_change(df: pd.DataFrame) -> pd.DataFrame:
        """
        计算日涨跌幅
        
        Args:
            df: DataFrame
            
        Returns:
            添加了 PCT_CHANGE 列的DataFrame
        """
        df['PCT_CHANGE'] = df['close'].pct_change() * 100
        df['PCT_CHANGE'] = df['PCT_CHANGE'].fillna(0)
        
        return df
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        一次性计算所有技术指标
        
        Args:
            df: DataFrame
            
        Returns:
            包含所有指标的DataFrame
        """
        try:
            # 确保必要的列存在
            required_cols = ['close', 'vol', 'high', 'low']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"DataFrame 缺少必要列: {required_cols}")
                return df
            
            # 计算各类指标
            df = TechnicalIndicator.calculate_ma(df)
            df = TechnicalIndicator.calculate_volume_ma(df)
            df = TechnicalIndicator.calculate_volume_ratio(df)
            df = TechnicalIndicator.calculate_high_low(df, period=5)
            df = TechnicalIndicator.calculate_pct_change(df)
            
            logger.info(f"成功计算 {len(df)} 行数据的技术指标")
            return df
            
        except Exception as e:
            logger.error(f"计算技术指标异常: {e}")
            return df
    
    @staticmethod
    def get_latest_indicators(df: pd.DataFrame) -> Dict[str, Any]:
        """
        获取最新一行的所有指标
        
        Args:
            df: DataFrame
            
        Returns:
            包含最新指标的字典
        """
        if df.empty:
            logger.warning("DataFrame 为空，无法获取最新指标")
            return {}
        
        latest = df.iloc[-1]
        
        indicators = {
            'trade_date': latest.get('trade_date'),
            'close': float(latest.get('close', 0)),
            'open': float(latest.get('open', 0)),
            'high': float(latest.get('high', 0)),
            'low': float(latest.get('low', 0)),
            'vol': float(latest.get('vol', 0)),
            'MA5': float(latest.get('MA5', 0)),
            'MA10': float(latest.get('MA10', 0)),
            'MA20': float(latest.get('MA20', 0)),
            'VOL_MA5': float(latest.get('VOL_MA5', 0)),
            'VOLUME_RATIO': float(latest.get('VOLUME_RATIO', 1.0)),
            'HIGH_5D': float(latest.get('HIGH_5D', 0)),
            'LOW_5D': float(latest.get('LOW_5D', 0)),
            'PCT_CHANGE': float(latest.get('PCT_CHANGE', 0))
        }
        
        return indicators
    
    @staticmethod
    def get_historical_summary(df: pd.DataFrame, period: int = 5) -> Dict[str, Any]:
        """
        获取过去N天的统计摘要
        
        Args:
            df: DataFrame
            period: 统计周期
            
        Returns:
            包含统计信息的字典
        """
        if len(df) < period:
            period = len(df)
        
        recent = df.tail(period)
        
        summary = {
            'avg_close': float(recent['close'].mean()),
            'avg_vol': float(recent['vol'].mean()),
            'avg_pct_change': float(recent['PCT_CHANGE'].mean()),
            'total_pct_change': float(recent['PCT_CHANGE'].sum()),
            'max_high': float(recent['high'].max()),
            'min_low': float(recent['low'].min()),
        }
        
        return summary
