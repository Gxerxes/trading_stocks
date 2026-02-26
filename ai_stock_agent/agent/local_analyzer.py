"""
本地分析器模块 - 基于规则的本地分析，不需要调用 API
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class LocalAnalyzer:
    """基于规则的本地分析器"""
    
    def analyze_stock(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        基于规则进行本地分析
        
        Args:
            features: 特征字典
            
        Returns:
            包含交易信号的字典
        """
        try:
            symbol = features.get('symbol', '')
            price = features.get('price', {})
            ma = features.get('moving_averages', {})
            trend = features.get('trend', {})
            volume = features.get('volume', {})
            
            # === 分析逻辑 ===
            
            # 1. 评估趋势强度
            trend_score = self._evaluate_trend(ma, price, trend)
            
            # 2. 评估量价配合
            volume_score = self._evaluate_volume(volume, price)
            
            # 3. 评估技术面
            technical_score = self._evaluate_technical(ma, price, trend)
            
            # 4. 综合评分
            total_score = (trend_score * 0.4 + volume_score * 0.3 + technical_score * 0.3)
            
            # 5. 生成信号
            signal = self._generate_signal(total_score, trend, ma, price)
            
            # 6. 确定入场、止损、目标价
            entry_price = self._calculate_entry_price(price, ma)
            stop_loss = self._calculate_stop_loss(price, features)
            target_price = self._calculate_target_price(price, ma, trend)
            
            # 7. 生成分析理由
            reason = self._generate_reason(signal, trend, ma, volume)
            
            result = {
                'symbol': symbol,
                'trend': trend.get('pct_change_10d', 0) > 0 and '上升趋势' or '下降趋势',
                'score': int(total_score),
                'signal': signal,
                'entry_price': float(entry_price),
                'stop_loss': float(stop_loss),
                'target_price': float(target_price),
                'confidence': int(min(100, abs(total_score) * 1.3)),
                'reason': reason,
            }
            
            logger.info(f"本地分析 {symbol} 完成: {signal} (评分: {int(total_score)})")
            return result
            
        except Exception as e:
            logger.error(f"本地分析异常: {e}")
            return self._create_default_signal(features.get('symbol', 'UNKNOWN'))
    
    def _evaluate_trend(self, ma: Dict[str, Any], price: Dict[str, Any], trend: Dict[str, Any]) -> float:
        """评估趋势强度（0-100）"""
        score = 50  # 基础分
        
        close = price.get('close', 0)
        ma5 = ma.get('MA5', 0)
        ma20 = ma.get('MA20', 0)
        
        # 价格在 MA5 和 MA20 上方 → 加分
        if close > ma5 and close > ma20:
            score += 20
        elif close > ma5:
            score += 10
        elif close < ma5 and close < ma20:
            score -= 20
        elif close < ma5:
            score -= 10
        
        # 短期涨幅
        pct_5d = trend.get('pct_change_5d', 0)
        if pct_5d > 5:
            score += 15
        elif pct_5d > 0:
            score += 5
        elif pct_5d < -5:
            score -= 15
        elif pct_5d < 0:
            score -= 5
        
        # MA 排列
        if ma5 > ma20:
            score += 10
        else:
            score -= 10
        
        return max(0, min(100, score))
    
    def _evaluate_volume(self, volume: Dict[str, Any], price: Dict[str, Any]) -> float:
        """评估量价配合（0-100）"""
        score = 50
        
        volume_ratio = volume.get('volume_ratio', 1.0)
        pct_change = price.get('pct_change', 0)
        
        # 价格上升且成交量放大
        if pct_change > 0 and volume_ratio > 1.2:
            score += 30
        elif pct_change > 0 and volume_ratio > 1.0:
            score += 15
        elif pct_change < 0 and volume_ratio > 1.2:
            score -= 20
        elif pct_change < 0 and volume_ratio > 1.0:
            score -= 10
        
        # 成交量极度异常
        if volume_ratio > 3:
            score += 10
        elif volume_ratio < 0.3:
            score -= 15
        
        return max(0, min(100, score))
    
    def _evaluate_technical(self, ma: Dict[str, Any], price: Dict[str, Any], trend: Dict[str, Any]) -> float:
        """评估技术面（0-100）"""
        score = 50
        
        close = price.get('close', 0)
        ma5 = ma.get('MA5', 0)
        ma10 = ma.get('MA10', 0)
        ma20 = ma.get('MA20', 0)
        
        # 价格位置得分
        if ma20 > 0:
            price_position = (close - ma20) / ma20 * 100
            if 0 < price_position <= 5:
                score += 10
            elif 5 < price_position <= 15:
                score += 15
            elif price_position < -10:
                score -= 20
        
        # MA 间距
        if ma5 > 0 and ma20 > 0:
            ma_diff = (ma5 - ma20) / ma20 * 100
            if 0 < ma_diff <= 5:
                score += 10
            elif ma_diff > 5:
                score += 15
            elif ma_diff < -5:
                score -= 10
        
        return max(0, min(100, score))
    
    def _generate_signal(self, score: float, trend: Dict[str, Any], ma: Dict[str, Any], price: Dict[str, Any]) -> str:
        """根据评分生成信号"""
        if score >= 70:
            return "BUY"
        elif score >= 40:
            return "WATCH"
        else:
            return "SELL"
    
    def _calculate_entry_price(self, price: Dict[str, Any], ma: Dict[str, Any]) -> float:
        """计算建议入场价"""
        close = price.get('close', 0)
        ma5 = ma.get('MA5', 0)
        ma10 = ma.get('MA10', 0)
        
        # 入场价是最近的支撑位
        entry = min(close, ma5, ma10)
        
        # 确保有有效价格
        if entry <= 0:
            entry = close
        
        return round(entry, 2)
    
    def _calculate_stop_loss(self, price: Dict[str, Any], features: Dict[str, Any]) -> float:
        """计算止损价"""
        low_5d = features.get('price_range', {}).get('low_5d', price.get('low', 0))
        
        # 止损为 5 日低点下方 2%
        stop_loss = low_5d * 0.98
        
        if stop_loss <= 0:
            stop_loss = price.get('close', 0) * 0.95
        
        return round(stop_loss, 2)
    
    def _calculate_target_price(self, price: Dict[str, Any], ma: Dict[str, Any], trend: Dict[str, Any]) -> float:
        """计算目标价"""
        close = price.get('close', 0)
        ma20 = ma.get('MA20', 0)
        
        # 目标价 = 当前价 + 5 日平均涨幅 * 10
        avg_pct = trend.get('pct_change_5d', 0)
        
        # 保守估计，目标价格为当前价上方 5-10%
        if avg_pct > 0:
            target = close * 1.10
        else:
            target = close * 1.05
        
        if target <= 0:
            target = close * 1.05
        
        return round(target, 2)
    
    def _generate_reason(self, signal: str, trend: Dict[str, Any], ma: Dict[str, Any], volume: Dict[str, Any]) -> str:
        """生成分析理由"""
        reasons = []
        
        pct_5d = trend.get('pct_change_5d', 0)
        pct_10d = trend.get('pct_change_10d', 0)
        vol_ratio = volume.get('volume_ratio', 1.0)
        
        if signal == "BUY":
            if pct_5d > 2:
                reasons.append("短期上升明显")
            if vol_ratio > 1.2:
                reasons.append("成交量放大")
            if trend.get('close_above_ma20'):
                reasons.append("价格站上MA20")
            if trend.get('ma5_above_ma20'):
                reasons.append("MA5站上MA20")
            
            reason = "；".join(reasons) if reasons else "技术面看好"
        
        elif signal == "SELL":
            if pct_5d < -2:
                reasons.append("短期下跌明显")
            if not trend.get('close_above_ma20'):
                reasons.append("价格打破MA20")
            if not trend.get('close_above_ma5'):
                reasons.append("价格打破MA5")
            if pct_10d < -5:
                reasons.append("中期下跌")
            
            reason = "；".join(reasons) if reasons else "技术面走弱"
        
        else:  # WATCH
            if 0 < pct_5d <= 2:
                reasons.append("上升动能不足")
            elif -2 <= pct_5d < 0:
                reasons.append("下跌幅度有限")
            
            if 0.8 < vol_ratio < 1.2:
                reasons.append("成交量平稳")
            
            reason = "；".join(reasons) if reasons else "观望"
        
        # 限制长度
        return reason[:100]
    
    def _create_default_signal(self, symbol: str) -> Dict[str, Any]:
        """创建默认信号"""
        return {
            'symbol': symbol,
            'trend': '未知',
            'score': 50,
            'signal': 'WATCH',
            'entry_price': 0.0,
            'stop_loss': 0.0,
            'target_price': 0.0,
            'confidence': 50,
            'reason': '数据不足',
        }
    
    def analyze_batch(self, features_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        批量分析多个股票
        
        Args:
            features_dict: 字典，key为ts_code，value为特征字典
            
        Returns:
            字典，key为ts_code，value为信号字典
        """
        signals = {}
        
        for ts_code, features in features_dict.items():
            logger.info(f"本地分析 {ts_code}...")
            signal = self.analyze_stock(features)
            if signal:
                signals[ts_code] = signal
        
        logger.info(f"完成 {len(signals)} 个股票的本地分析")
        return signals
