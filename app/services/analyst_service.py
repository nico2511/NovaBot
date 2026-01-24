"""
Analyst Service
Provides real-time multi-timeframe analysis for the Frontend "Co-pilot".
Extension to the core bot (Sidecar pattern).
"""

import asyncio
import pandas as pd
import json
import os
import time
from backend.market_data import get_hyperliquid_candles
from app.services.indicators import Indicators

HISTORY_FILE = "data/sentiment_history.json"

class AnalystService:
    def __init__(self):
        self.timeframes = ["5m", "1h", "4h"]
        self.history = self._load_history()
    
    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []

    def _save_history(self, entry):
        # Keep last 100 entries
        self.history.append(entry)
        if len(self.history) > 100:
            self.history = self.history[-100:]
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f)

    async def analyze_market_sentiment(self, symbol: str) -> dict:
        """
        Analyze market sentiment across 3 timeframes.
        Returns a dictionary with sentiment for each timeframe.
        """
        results = {}
        
        # Parallel fetch of candles
        tasks = [get_hyperliquid_candles(symbol, tf, limit=100) for tf in self.timeframes]
        candles_list = await asyncio.gather(*tasks, return_exceptions=True)
        
        for tf, df in zip(self.timeframes, candles_list):
            if isinstance(df, pd.DataFrame) and not df.empty:
                results[tf] = self._calculate_sentiment(df)
            else:
                results[tf] = {"sentiment": "UNKNOWN", "score": 0, "reason": "No Data"}
        
        # Historical Tracking (Track 1h sentiment changes)
        current_1h = results.get("1h", {})
        if current_1h.get("sentiment") != "UNKNOWN":
            last_entry = self.history[-1] if self.history else None
            
            # Save if list is empty, or if sentiment changed, or if last entry is > 1 hour old
            should_save = False
            now = time.time()
            
            if not last_entry:
                should_save = True
            elif last_entry.get("sentiment") != current_1h.get("sentiment"):
                should_save = True
            elif (now - last_entry.get("timestamp", 0)) > 3600:
                should_save = True
                
            if should_save:
                entry = {
                    "timestamp": now,
                    "symbol": symbol,
                    "sentiment": current_1h.get("sentiment"),
                    "score": current_1h.get("score"),
                    "details": current_1h.get("details")
                }
                self._save_history(entry)

        results["history"] = self.history
        return results

    def _calculate_sentiment(self, df: pd.DataFrame) -> dict:
        """Calculate sentiment for a single timeframe"""
        try:
            close = df['close'].iloc[-1]
            
            # Indicators
            rsi = Indicators.rsi(df['close'], 14).iloc[-1]
            ema20 = Indicators.ema(df['close'], 20).iloc[-1]
            ema50 = Indicators.ema(df['close'], 50).iloc[-1]
            
            # MACD
            macd_df = Indicators.macd(df['close'])
            macd_val = macd_df['MACD'].iloc[-1]
            macd_signal = macd_df['MACDs'].iloc[-1]
            macd_hist = macd_df['MACDh'].iloc[-1]
            
            # Volume
            vol_sma = Indicators.sma(df['volume'], 20).iloc[-1]
            curr_vol = df['volume'].iloc[-1]
            vol_trend = "HIGH" if curr_vol > 1.5 * vol_sma else "LOW" if curr_vol < 0.5 * vol_sma else "NORMAL"
            
            # Determine Trend
            trend = "BULLISH" if ema20 > ema50 else "BEARISH"
            
            # Determine RSI Status
            rsi_status = "NEUTRAL"
            if rsi > 70: rsi_status = "OVERBOUGHT"
            elif rsi < 30: rsi_status = "OVERSOLD"
            
            # Scoring (-100 to +100)
            score = 0
            if trend == "BULLISH": score += 40
            else: score -= 40
            
            # MACD Contribution
            if macd_val > macd_signal: score += 15
            else: score -= 15
            
            if rsi_status == "OVERBOUGHT": score -= 20 # Pullback risk
            if rsi_status == "OVERSOLD": score += 20   # Bounce chance
            
            # Final Sentiment Label
            label = "NEUTRAL"
            if score >= 30: label = "BULLISH"
            elif score <= -30: label = "BEARISH"
            
            return {
                "sentiment": label,
                "score": score,
                "rsi": round(rsi, 1),
                "trend": trend,
                "macd": {
                    "value": round(macd_val, 4),
                    "signal": round(macd_signal, 4),
                    "hist": round(macd_hist, 4),
                    "crossover": "BULLISH" if macd_val > macd_signal else "BEARISH"
                },
                "volume": {
                    "status": vol_trend,
                    "value": round(curr_vol, 2)
                },
                "details": f"RSI {round(rsi,1)} | MACD {('Bull' if macd_val > macd_signal else 'Bear')}"
            }
        except Exception as e:
            return {"sentiment": "ERROR", "score": 0, "reason": str(e)}

    def analyze_position(self, position: dict, market_sentiment: dict) -> dict:
        """
        Generate advice for a specific position based on market sentiment.
        """
        advice = "HOLD"
        color = "blue"
        reason = "Monitoring position"
        
        try:
            side = position.get("side", "BUY") 
            size = float(position.get("size", 0))
            if size == 0: return {}
            
            real_side = "BUY" if size > 0 else "SELL"
            pnl_roe = float(position.get("returnOnEquity", 0)) * 100
            
            # Use 1h timeframe for main advice
            mid_term = market_sentiment.get("1h", {})
            mid_trend = mid_term.get("trend", "NEUTRAL")
            mid_rsi = mid_term.get("rsi", 50)
            mid_macd = mid_term.get("macd", {}).get("crossover", "NEUTRAL")
            
            # Advice Logic
            if real_side == "BUY":
                if mid_trend == "BEARISH":
                    advice = "CAUTION"
                    color = "orange"
                    reason = "Trend is changing to Bearish"
                    if mid_macd == "BEARISH":
                        reason += " + MACD Bear Cross"
                        
                    if mid_rsi < 30:
                        advice = "DANGER"
                        color = "red"
                        reason = "Bearish Trend + Oversold (Crash risk)"
                elif mid_rsi > 80:
                     advice = "TAKE PROFIT"
                     color = "green"
                     reason = "RSI Extremely High (>80)"
                elif pnl_roe > 10 and mid_macd == "BULLISH":
                     advice = "GOOD"
                     color = "green"
                     reason = "Profitable & Trend Match"
                     
            else: # SELL
                if mid_trend == "BULLISH":
                    advice = "CAUTION"
                    color = "orange"
                    reason = "Trend is changing to Bullish"
                    if mid_macd == "BULLISH":
                        reason += " + MACD Bull Cross"

                    if mid_rsi > 70:
                        advice = "DANGER"
                        color = "red"
                        reason = "Bullish Trend + Overbought"
                elif mid_rsi < 20:
                     advice = "TAKE PROFIT"
                     color = "green"
                     reason = "RSI Extremely Low (<20)"

            return {
                "advice": advice,
                "color": color,
                "reason": reason,
                "score": 85 if advice == "GOOD" else 50
            }
            
        except Exception as e:
             return {"advice": "ERROR", "reason": str(e)}

analyst_service = AnalystService()
