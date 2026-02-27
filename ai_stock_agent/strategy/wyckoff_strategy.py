"""
维科夫量价策略 - 基于日线量价关系识别阶段并给出买卖提示
"""

import logging
from typing import Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class WyckoffStrategy:
    """维科夫量价分析策略"""

    def analyze_stock(self, df: pd.DataFrame, ts_code: str) -> Optional[Dict[str, Any]]:
        """
        分析单只股票当前维科夫阶段并生成交易建议

        Args:
            df: 含 OHLCV 与指标列的日线数据
            ts_code: 股票代码

        Returns:
            交易信号字典（兼容现有报告字段）
        """
        try:
            if df is None or len(df) < 30:
                return self._default_signal(ts_code, "数据不足，无法识别维科夫阶段")

            data = df.copy().sort_values("trade_date").reset_index(drop=True)
            if "MA20" not in data.columns:
                data["MA20"] = data["close"].rolling(20, min_periods=1).mean()
            if "VOLUME_RATIO" not in data.columns:
                vol_ma20 = data["vol"].rolling(20, min_periods=1).mean()
                data["VOLUME_RATIO"] = (data["vol"] / vol_ma20).fillna(1.0)

            latest = data.iloc[-1]
            recent20 = data.tail(20)
            recent40 = data.tail(40)

            close = float(latest["close"])
            open_price = float(latest["open"])
            low = float(latest["low"])
            high = float(latest["high"])
            ma20 = float(latest["MA20"])
            vol_ratio = float(latest.get("VOLUME_RATIO", 1.0))

            low20 = float(recent20["low"].min())
            high20 = float(recent20["high"].max())
            range_pct_20 = (high20 - low20) / low20 if low20 > 0 else 0.0
            trend_40 = (float(recent40["close"].iloc[-1]) - float(recent40["close"].iloc[0])) / float(
                recent40["close"].iloc[0]
            ) if float(recent40["close"].iloc[0]) > 0 else 0.0

            avg_vol_5 = float(data.tail(5)["vol"].mean())
            avg_vol_20 = float(recent20["vol"].mean())
            volume_dryup = avg_vol_5 < avg_vol_20 * 0.8 if avg_vol_20 > 0 else False

            # 维科夫关键行为（简化）
            spring = (
                low <= low20 * 1.005
                and close > low20 * 1.01
                and close > open_price
                and vol_ratio >= 1.1
            )
            breakout = close > high20 * 1.005 and vol_ratio >= 1.3
            upthrust = high >= high20 * 0.998 and close < high20 * 0.99 and vol_ratio >= 1.1

            # 阶段识别（简化日线规则）
            stage = "震荡"
            trend_label = "中性"
            if close < ma20 and trend_40 < -0.12:
                stage = "下跌阶段（Markdown）"
                trend_label = "下降趋势"
            elif close > ma20 and trend_40 > 0.12 and range_pct_20 > 0.12:
                stage = "上涨阶段（Markup）"
                trend_label = "上升趋势"
            elif range_pct_20 <= 0.18 and trend_40 < -0.03:
                stage = "吸筹阶段（Accumulation）"
                trend_label = "筑底震荡"
            elif range_pct_20 <= 0.18 and trend_40 > 0.03:
                stage = "派发阶段（Distribution）"
                trend_label = "高位震荡"

            signal = "WATCH"
            score = 50
            reason_parts = [f"维科夫阶段: {stage}"]

            entry_price = close
            stop_loss = low20 * 0.98 if low20 > 0 else close * 0.95
            target_price = close * 1.08

            if "吸筹阶段" in stage:
                score = 62
                reason_parts.append("区间收敛，疑似底部构建")
                if volume_dryup:
                    reason_parts.append("下跌量能衰减")
                    score += 6
                if spring:
                    signal = "BUY"
                    score = max(score, 76)
                    reason_parts.append("出现Spring，给出试探买点")
                    entry_price = close
                    stop_loss = low20 * 0.985
                    target_price = high20 * 1.04
            elif "上涨阶段" in stage:
                score = 66
                reason_parts.append("趋势向上，优先回踩买入")
                pullback_to_ma20 = abs(close - ma20) / ma20 <= 0.02 if ma20 > 0 else False
                if pullback_to_ma20 and volume_dryup:
                    signal = "BUY"
                    score = 74
                    reason_parts.append("回踩MA20且缩量，给出低吸买点")
                    entry_price = min(close, ma20)
                    stop_loss = entry_price * 0.96
                    target_price = max(high20 * 1.03, close * 1.08)
                elif breakout:
                    reason_parts.append("放量突破，避免追高，等待回踩")
                    signal = "WATCH"
            elif "派发阶段" in stage:
                score = 38
                signal = "SELL" if upthrust else "WATCH"
                reason_parts.append("高位震荡，警惕主力派发")
                if upthrust:
                    reason_parts.append("出现Upthrust，给出减仓/卖点")
                target_price = close * 0.95
            elif "下跌阶段" in stage:
                score = 25
                signal = "SELL"
                reason_parts.append("空头主导，避免抄底")
                target_price = close * 0.92

            confidence = min(95, max(45, int(abs(score - 50) * 1.8 + 50)))
            reason = "；".join(reason_parts)[:180]

            return {
                "symbol": ts_code,
                "trend": trend_label,
                "score": int(max(0, min(100, score))),
                "signal": signal,
                "entry_price": round(float(entry_price), 2),
                "stop_loss": round(float(stop_loss), 2),
                "target_price": round(float(target_price), 2),
                "confidence": int(confidence),
                "reason": reason,
                "stage": stage,
                "strategy": "wyckoff",
            }
        except Exception as e:
            logger.error(f"维科夫分析异常 {ts_code}: {e}")
            return self._default_signal(ts_code, "维科夫分析失败")

    def analyze_batch(self, data_dict: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, Any]]:
        """批量分析"""
        signals: Dict[str, Dict[str, Any]] = {}
        for ts_code, df in data_dict.items():
            signal = self.analyze_stock(df, ts_code)
            if signal:
                signals[ts_code] = signal
        logger.info(f"完成 {len(signals)} 个股票的维科夫分析")
        return signals

    @staticmethod
    def _default_signal(ts_code: str, reason: str) -> Dict[str, Any]:
        return {
            "symbol": ts_code,
            "trend": "未知",
            "score": 50,
            "signal": "WATCH",
            "entry_price": 0.0,
            "stop_loss": 0.0,
            "target_price": 0.0,
            "confidence": 50,
            "reason": reason,
            "stage": "未知",
            "strategy": "wyckoff",
        }
