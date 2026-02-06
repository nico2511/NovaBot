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
        """Load history using StorageService if available"""
        try:
            from backend.services.storage import storage_service
            if storage_service:
                return storage_service.load_sentiment_history()
        except:
            pass
        return []

    def _save_history(self, entry):
        """Save history using StorageService if available"""
        # Keep last 100 entries
        self.history.append(entry)
        if len(self.history) > 100:
            self.history = self.history[-100:]
            
        try:
            from backend.services.storage import storage_service
            if storage_service:
                storage_service.save_sentiment_history(self.history)
                return
        except:
            pass
        
        # Fallback to local file if service not initialized (Bot standalone mode)
        try:
            HISTORY_FILE = "data/analysis/sentiment_history.json"
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(self.history, f)
        except:
            pass

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
                # Attach symbol metadata to df for OI/Funding fetch
                df.symbol = symbol
                results[tf] = self.calculate_sentiment(df)
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

    def calculate_sentiment(self, df: pd.DataFrame) -> dict:
        """Calculate sentiment for a single timeframe (Public helper)"""
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
            
            # Volume Influence
            if vol_trend == "HIGH":
                # Confirm movement strength
                if score > 0: score += 10
                elif score < 0: score -= 10
            elif vol_trend == "LOW":
                # Reduce conviction if volume is low
                score = int(score * 0.7)

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

    def analyze_position(self, position: dict, market_sentiment: dict, trading_timeframe: str = "15m") -> dict:
        """
        Generate advice for a specific position based on market sentiment.
        Dynamically selects the most relevant timeframe based on trading_timeframe.
        
        Args:
            position: Position data (side, size, returnOnEquity)
            market_sentiment: Multi-timeframe sentiment analysis
            trading_timeframe: Active trading timeframe (e.g., "15m", "1h", "4h")
        """
        advice = "HOLD"
        color = "blue"
        reason = "Monitoring position"
        
        try:
            side = position.get("side", "BUY") 
            size = float(position.get("size", 0))
            if size == 0: return {}
            
            real_side = side.upper()
            pnl_roe = float(position.get("returnOnEquity", 0)) * 100
            
            # DYNAMIC TIMEFRAME SELECTION (Prevent false alarms from slow timeframes)
            # For fast strategies (15m), use 5m for advice to avoid 4H/1H lag
            # For slower strategies (1h+), use 1h
            if trading_timeframe in ["1m", "5m", "15m"]:
                advice_tf = "5m"  # Use fastest timeframe for scalping/short-term
            elif trading_timeframe in ["1h", "4h"]:
                advice_tf = "1h"  # Use mid-term for swing trades
            else:
                advice_tf = "1h"  # Default fallback
            
            mid_term = market_sentiment.get(advice_tf, market_sentiment.get("1h", {}))
            mid_trend = mid_term.get("trend", "NEUTRAL")
            mid_rsi = mid_term.get("rsi", 50)
            mid_macd = mid_term.get("macd", {}).get("crossover", "NEUTRAL")
            
            # Advice Logic
            # Advice Logic Refined
            pnl_text = f"Profit ({pnl_roe:+.1f}%)" if pnl_roe > 0 else f"Loss ({pnl_roe:+.1f}%)"
            
            if real_side == "BUY":
                # --- SCENARIO 1: WINNING POSITION ---
                if pnl_roe > 0:
                    if mid_rsi > 75:  # Slightly lowered from 80
                        advice = "TAKE PROFIT"
                        color = "green"
                        reason = f"RSI High ({mid_rsi:.1f}). Consider securing gains."
                    elif mid_trend == "BEARISH":
                        advice = "PROTECT GAINS"
                        color = "orange"
                        reason = "Trend flipping Bearish. Tighten stops."
                    elif pnl_roe > 5 and mid_macd == "BULLISH":
                        advice = "LET IT RIDE"
                        color = "green"
                        reason = f"Strong momentum + Profit. Hold."
                    else:
                        advice = "HOLD"
                        reason = f"Trend valid ({mid_term.get('sentiment')}). Monitor."

                # --- SCENARIO 2: LOSING POSITION ---
                else:
                    if mid_trend == "BEARISH" and mid_macd == "BEARISH":
                        advice = "CUT LOSS"
                        color = "red"
                        reason = "Trend confirmed Bearish against position."
                    elif mid_rsi < 30:
                        advice = "WATCH BOUNCE" # Changed from DANGER
                        color = "orange"
                        reason = f"Oversold ({mid_rsi:.1f}). Wait for reaction to exit."
                    else:
                        advice = "HOLD"
                        reason = "Calculating recovery..."
                      
            else: # SELL
                # --- SCENARIO 1: WINNING POSITION ---
                if pnl_roe > 0:
                     if mid_rsi < 25: # Slightly raised from 20
                        advice = "TAKE PROFIT"
                        color = "green"
                        reason = f"RSI Low ({mid_rsi:.1f}). Consider securing gains."
                     elif mid_trend == "BULLISH":
                        advice = "PROTECT GAINS"
                        color = "orange"
                        reason = f"Trend changing to Bullish ({pnl_text}). Tighten stops."
                     elif pnl_roe > 5 and mid_macd == "BEARISH":
                        advice = "LET IT RIDE"
                        color = "green"
                        reason = f"Strong bearish momentum + Profit. Hold."
                     else:
                        advice = "HOLD"
                        reason = f"Trend still valid. Market is {mid_term.get('sentiment')} ({pnl_text})."

                # --- SCENARIO 2: LOSING POSITION ---
                else: 
                     if mid_trend == "BULLISH" and mid_macd == "BULLISH":
                        advice = "CUT LOSS"
                        color = "red"
                        reason = f"Trend confirmed Bullish against position ({pnl_text})."
                     elif mid_rsi > 70:
                        advice = "WATCH BOUNCE"
                        color = "orange"
                        reason = f"Overbought ({mid_rsi:.1f}). Wait for pullback to exit."
                     else:
                         advice = "HOLD"
                         reason = f"Trade valid. Market is {mid_term.get('sentiment')} ({pnl_text})."

            return {
                "advice": advice,
                "color": color,
                "reason": reason,
                "score": 85 if advice == "GOOD" else (40 if advice in ["CAUTION", "DANGER"] else 60)
            }
            
        except Exception as e:
             return {"advice": "ERROR", "reason": str(e)}

analyst_service = AnalystService()
