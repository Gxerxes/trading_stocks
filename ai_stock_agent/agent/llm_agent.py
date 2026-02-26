"""
LLM 代理模块 - 调用OpenAI API进行股票分析（仅限 API 模式）
"""

import logging
import json
from typing import Dict, Any, Optional
from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from config.settings import (
    OPENAI_API_KEY, 
    OPENAI_API_BASE, 
    OPENAI_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS
)

logger = logging.getLogger(__name__)


class LLMAgent:
    """OpenAI API 分析代理（仅限 API 模式）"""
    
    def __init__(self):
        """初始化OpenAI客户端"""
        if not OPENAI_API_KEY:
            logger.warning("LLM Agent 初始化：未设置 OPENAI_API_KEY")
            self.client = None
            return
        
        try:
            if OPENAI_API_BASE:
                self.client = OpenAI(
                    api_key=OPENAI_API_KEY,
                    base_url=OPENAI_API_BASE
                )
            else:
                self.client = OpenAI(api_key=OPENAI_API_KEY)
            logger.info("LLM Agent 初始化成功，使用 OpenAI API")
        except Exception as e:
            logger.error(f"LLM Agent 初始化失败: {e}")
            self.client = None
    
    def analyze_stock(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        对单个股票进行分析
        
        Args:
            features: 特征字典
            
        Returns:
            包含交易信号的字典
        """
        if self.client is None:
            logger.error("OpenAI 客户端未初始化，无法进行 API 分析")
            return self._create_default_signal(features['symbol'])
        
        try:
            # 构建分析提示
            prompt = self._build_prompt(features)
            
            # 调用OpenAI API
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "你是一位资深的股票技术分析师。分析给定的股票数据，提供专业的交易建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            
            # 提取响应内容
            response_text = response.choices[0].message.content
            
            # 解析JSON
            signal = json.loads(response_text)
            
            # 验证和补充信号
            signal = self._validate_signal(signal, features['symbol'])
            
            logger.info(f"成功分析 {features['symbol']}: {signal.get('signal')}")
            return signal
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {e}")
            return self._create_default_signal(features['symbol'])
        except (APIError, APIConnectionError, RateLimitError) as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            return self._create_default_signal(features['symbol'])
        except Exception as e:
            logger.error(f"分析 {features['symbol']} 异常: {e}")
            return self._create_default_signal(features['symbol'])
    
    def _build_prompt(self, features: Dict[str, Any]) -> str:
        """构建分析提示"""
        price_info = features['price']
        ma_info = features['moving_averages']
        trend_info = features['trend']
        volume_info = features['volume']
        history_5d = features['history_5day']
        
        prompt = f"""
分析以下股票数据并提供交易信号：

股票代码: {features['symbol']}
交易日期: {features['trade_date']}

【价格数据】
- 最新收盘价: {price_info['close']:.2f}
- 今日涨幅: {price_info['pct_change']:.2f}%
- 开盘价: {price_info['open']:.2f}
- 今日最高: {price_info['high']:.2f}
- 今日最低: {price_info['low']:.2f}

【移动平均线】
- MA5: {ma_info['MA5']:.2f}
- MA10: {ma_info['MA10']:.2f}
- MA20: {ma_info['MA20']:.2f}
- 收盘价 vs MA5: {ma_info['close_vs_ma5']:.2f}
- 收盘价 vs MA20: {ma_info['close_vs_ma20']:.2f}

【成交量】
- 当前成交量: {volume_info['current_vol']:.0f}
- 成交量MA5: {volume_info['vol_ma5']:.0f}
- 成交量比率: {volume_info['volume_ratio']:.2f}

【趋势指标】
- 5日涨幅: {trend_info.get('pct_change_5d', 0):.2f}%
- 10日涨幅: {trend_info.get('pct_change_10d', 0):.2f}%
- 价格在MA5上方: {trend_info.get('close_above_ma5', False)}
- 价格在MA20上方: {trend_info.get('close_above_ma20', False)}

【历史统计（5日）】
- 平均收盘价: {history_5d['avg_close']:.2f}
- 平均成交量: {history_5d['avg_vol']:.0f}
- 平均涨幅: {history_5d['avg_pct_change']:.2f}%

请根据上述数据分析，返回以下JSON格式的交易信号：

{{
    "symbol": "股票代码",
    "trend": "上升趋势/中性/下降趋势",
    "score": 0-100的评分,
    "signal": "BUY/WATCH/SELL",
    "entry_price": 建议入场价格,
    "stop_loss": 止损价格,
    "target_price": 目标价格,
    "confidence": 0-100的信心指数,
    "reason": "简明的分析理由，最多100字"
}}

分析要点：
1. 关注价格与移动平均线的位置关系
2. 成交量是否配合价格运动
3. 短期趋势（5日）和中期趋势（10日）
4. 信号强度：BUY（强烈看好）、WATCH（持续观察）、SELL（建议卖出）
5. 评分和信心指数应该相互呼应
"""
        return prompt
    
    def _validate_signal(self, signal: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """验证并补充信号完整性"""
        required_keys = ['symbol', 'trend', 'score', 'signal', 'entry_price', 'stop_loss', 'target_price', 'confidence', 'reason']
        
        # 补充缺失的字段
        for key in required_keys:
            if key not in signal:
                if key == 'symbol':
                    signal[key] = symbol
                elif key == 'score':
                    signal[key] = 50
                elif key == 'signal':
                    signal[key] = 'WATCH'
                elif key == 'confidence':
                    signal[key] = 50
                elif key == 'reason':
                    signal[key] = '数据不足'
                else:
                    signal[key] = 0.0
        
        # 数据类型转换和验证
        signal['score'] = max(0, min(100, float(signal.get('score', 50))))
        signal['confidence'] = max(0, min(100, float(signal.get('confidence', 50))))
        signal['entry_price'] = float(signal.get('entry_price', 0))
        signal['stop_loss'] = float(signal.get('stop_loss', 0))
        signal['target_price'] = float(signal.get('target_price', 0))
        
        # 验证signal值
        if signal['signal'] not in ['BUY', 'WATCH', 'SELL']:
            signal['signal'] = 'WATCH'
        
        # 限制reason长度
        signal['reason'] = str(signal.get('reason', ''))[:200]
        
        return signal
    
    def _create_default_signal(self, symbol: str) -> Dict[str, Any]:
        """创建默认信号（当API调用失败时）"""
        return {
            'symbol': symbol,
            'trend': '未知',
            'score': 50,
            'signal': 'WATCH',
            'entry_price': 0.0,
            'stop_loss': 0.0,
            'target_price': 0.0,
            'confidence': 0,
            'reason': 'LLM分析失败，请稍后重试'
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
            logger.info(f"分析 {ts_code}...")
            signal = self.analyze_stock(features)
            if signal:
                signals[ts_code] = signal
        
        logger.info(f"完成 {len(signals)} 个股票的分析")
        return signals
