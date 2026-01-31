"""
AI Service for Trading Bot - Production Ready
Handles all AI-powered market analysis and signal validation using OpenRouter API
"""
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import json
import re

from app.core.config import config
from app.core.prompts import get_system_prompt


class IAService:
    """
    AI Service for market analysis and trading signal validation.
    Uses OpenRouter API with configurable LLM models.
    """
    
    def __init__(self):
        """Initialize AI Service with OpenRouter client"""
        self.openrouter_key: Optional[str] = config.OPENROUTER_API_KEY
        self.client: Optional[Any] = None
        self.model: str = config.AI_MODEL_NAME
        
        # Cache with LRU eviction (max 1000 entries)
        self.cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.MAX_CACHE_SIZE: int = 1000
        
        # Circuit Breaker
        self.circuit_breaker_until: Optional[datetime] = None
        
        # Initialize OpenRouter client
        if self.openrouter_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key,
                )
                print(f"✅ AI Service (OpenRouter) initialized with model: {self.model}")
            except ImportError:
                print("⚠️ OpenAI module not found. AI Service disabled.")
                self.client = None
            except Exception as e:
                print(f"⚠️ Failed to init AI Service: {e}")
                self.client = None
        else:
            print("ℹ️ OpenRouter Key not found. AI Service disabled.")
    
    def get_dynamic_system_prompt(self) -> str:
        """
        Get dynamic system prompt based on .env configuration.
        Uses BOT_PERSONA, RISK_PROFILE, and TRADING_TIMEFRAME from config.
        
        Returns:
            Formatted system prompt string
        """
        return get_system_prompt(
            persona=config.BOT_PERSONA,
            risk_profile=config.RISK_PROFILE,
            timeframe=config.TRADING_TIMEFRAME
        )
    
    
    @staticmethod
    def extract_json(text: str) -> str:
        """
        Robustly extract JSON from text, handling markdown code blocks.
        """
        try:
            # Try to find ```json ... ``` block
            match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                return match.group(1)
            
            # Try to find outer braces { ... }
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                return match.group(1)
            
            return text.strip()
        except Exception:
            return text.strip()
    
    def _clean_cache(self) -> None:
        """
        Clean expired cache entries and enforce size limit (LRU eviction).
        Called periodically to prevent memory leaks.
        """
        current_time = datetime.now()
        
        # Remove expired entries
        expired_keys = []
        for key, entry in self.cache.items():
            ttl_seconds = entry.get("ttl_minutes", 15) * 60
            if (current_time - entry["time"]).total_seconds() >= ttl_seconds:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        # Enforce max size (LRU: remove oldest entries)
        while len(self.cache) > self.MAX_CACHE_SIZE:
            self.cache.popitem(last=False)  # Remove oldest (FIFO)
    
    def _call_openrouter_api(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Call OpenRouter API with error handling.
        """
        if not self.client:
            raise Exception("AI Client not initialized (Missing Key)")
        
        try:
            messages = []
            
            # Add system prompt if provided
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add user prompt
            messages.append({"role": "user", "content": prompt})
            
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            raw_content = completion.choices[0].message.content
            clean_text = self.extract_json(raw_content)
            return {"raw_output": clean_text, "model": f"openrouter:{self.model}"}
        except Exception as e:
            raise Exception(f"OpenRouter failed: {e}")
    
    def _call_ai_generic(self, prompt: str) -> Dict[str, Any]:
        """
        Generic AI call dispatcher with Circuit Breaker logic.
        Injects the Dynamic System Prompt automatically.
        """
        # Check Circuit Breaker
        if self.circuit_breaker_until:
            if datetime.now() < self.circuit_breaker_until:
                remaining = int((self.circuit_breaker_until - datetime.now()).total_seconds() / 60)
                return {
                    "error": "AI Circuit Breaker Active",
                    "raw_output": json.dumps({
                        "explanation": f"IA en pause pour {remaining} min (Quota épuisé)"
                    })
                }
            else:
                self.circuit_breaker_until = None
                print("⚡ AI Circuit Breaker RESET - Resuming AI calls")
        
        try:
            # Inject dynamic system prompt here
            system_prompt = self.get_dynamic_system_prompt()
            return self._call_openrouter_api(prompt, system_prompt=system_prompt)
        except Exception as e:
            error_str = str(e).lower()
            print(f"⚠️ AI Call failed: {e}")
            
            # Trigger Circuit Breaker on quota errors
            if "quota" in error_str or "429" in error_str:
                self.circuit_breaker_until = datetime.now() + timedelta(minutes=10)
                print("❄️ AI CIRCUIT BREAKER TRIGGERED: Pausing AI for 10 minutes")
            
            return {
                "raw_output": json.dumps({
                    "error": "AI call failed",
                    "details": str(e)
                })
            }
    
    def _get_cache_key(self, type_: str, unique_id: str) -> str:
        return f"{type_}:{unique_id}"
    
    def _get_cached_response(self, key: str, ttl_minutes: int) -> Optional[Dict[str, Any]]:
        if key in self.cache:
            entry = self.cache[key]
            if (datetime.now() - entry["time"]).total_seconds() < (ttl_minutes * 60):
                # Move to end (LRU: mark as recently used)
                self.cache.move_to_end(key)
                return entry["data"]
        return None
    
    def _set_cache(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        self.cache[key] = {
            "time": datetime.now(),
            "data": data,
            "ttl_minutes": ttl_minutes
        }
        
        # Periodic cleanup (every 10 cache sets)
        if len(self.cache) % 10 == 0:
            self._clean_cache()
    
    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market conditions (cached 15 min).
        Refactored to rely on System Prompt for persona.
        """
        symbol = market_data.get('symbol', 'UNKNOWN')
        key = self._get_cache_key("market", symbol)
        
        cached = self._get_cached_response(key, 15)
        if cached:
            return cached
        
        # Prompt simplifié : On donne les données et le format attendu.
        # L'identité (Expert Trader) est gérée par le System Prompt.
        prompt = f"""Analyze the provided market data for {symbol} according to your active persona and risk profile.

Market Data:
{json.dumps(market_data, indent=2)}

Respond ONLY with valid JSON (no markdown) containing:
- risk_level: (LOW, MEDIUM, HIGH)
- trend: (BULLISH, BEARISH, NEUTRAL, RANGE)
- summary: A 2-sentence analysis in FRENCH
- reasoning: A list of 3 key factors (in FRENCH)

Example:
{{
  "risk_level": "MEDIUM",
  "trend": "BULLISH",
  "summary": "Le marché montre une tendance haussière avec un RSI équilibré. La volatilité reste modérée.",
  "reasoning": ["RSI à 55 indique un momentum sain", "Prix au-dessus de l'EMA20", "Volume en hausse de 20%"]
}}
"""
        result = self._call_ai_generic(prompt)
        
        if "error" not in result and "raw_output" in result and "Error" not in result["raw_output"]:
            self._set_cache(key, result, ttl_minutes=15)
        
        return result
    
    def validate_signal(
        self,
        signal_data: Dict[str, Any],
        market_context: Dict[str, Any],
        strategy_persona: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate a trading signal before execution (AI Gatekeeper).
        Refactored to rely on System Prompt for persona.
        """
        symbol = signal_data.get('symbol', 'UNKNOWN')
        key = self._get_cache_key("signal_validation", f"{symbol}_{signal_data.get('signal')}")
        
        cached = self._get_cached_response(key, 1)
        if cached:
            return cached
        
        ctx = market_context or {}
        
        # Prompt simplifié : Instruction directe de validation.
        prompt = f"""Validate the following trading signal based on the current market conditions and your configured Persona/Risk Profile.

=== SIGNAL TO VALIDATE ===
Symbol: {symbol}
Direction: {signal_data.get('signal', 'N/A')}
Strategy: {signal_data.get('strategy', 'N/A')}
Entry Price: ${signal_data.get('price', 'N/A')}
Proposed SL: ${signal_data.get('sl', 'N/A')}
Proposed TP: ${signal_data.get('tp', 'N/A')}

=== CURRENT MARKET CONDITIONS ===
Current Price: ${ctx.get('current_price', 'N/A')}
Market Regime: {ctx.get('regime', 'UNKNOWN')}
Market Bias: {ctx.get('market_bias', 'NEUTRAL')}

Technical Indicators (Dynamic):
- RSI(14): {ctx.get('rsi_val', 'N/A')} [{ctx.get('rsi_trend', '')}] (15m Change: {ctx.get('rsi_slope', 0):+.1f})
- Volume: {ctx.get('vol_current', 'N/A')} [{ctx.get('vol_trend', '')}] (15m Change: {ctx.get('vol_slope', 0):+.1f}%)
- ADX: {ctx.get('adx_val', 'N/A')} (Slope: {ctx.get('adx_slope', 0):+.1f})
- MACD (12,26,9): Line {ctx.get('macd_line', 'N/A')} | Signal {ctx.get('macd_signal', 'N/A')} | Hist {ctx.get('macd_hist', 'N/A')}
- Open Interest: ${int(ctx.get('open_interest', 0)):,}
- Price Action: {ctx.get('price_trend', '')} ({ctx.get('price_change_15m', 0):+.2f}%)

Bollinger Bands (20, 2.0):
- Upper: ${ctx.get('bb_upper', 'N/A')}
- Middle: ${ctx.get('bb_middle', 'N/A')}
- Lower: ${ctx.get('bb_lower', 'N/A')}
- Position: {ctx.get('bb_position', 'N/A')}
- Width: {ctx.get('bb_width', 'N/A')}%

EMA Trends:
- EMA 20 Slope: {ctx.get('ema_20_slope', 0):.6f}
- EMA 50 Slope: {ctx.get('ema_50_slope', 0):.6f} [{ctx.get('ema_50_slope_label', 'N/A')}]

Fibonacci Levels (from Swing):
- 78.6%: ${ctx.get('fib_786', 'N/A')}
- 61.8% (Golden): ${ctx.get('fib_618', 'N/A')}
- 50.0%: ${ctx.get('fib_50', 'N/A')}
- 38.2%: ${ctx.get('fib_382', 'N/A')}
- 23.6%: ${ctx.get('fib_236', 'N/A')}
- Current Zone: {ctx.get('fib_zone', 'N/A')}

Key Levels:
- Swing High: ${ctx.get('swing_high', 'N/A')}
- Swing High: ${ctx.get('swing_high', 'N/A')}
- Swing Low: ${ctx.get('swing_low', 'N/A')}

=== COPILOT SENTIMENT (MTF) ===
{ctx.get('mtf_sentiment', 'N/A')}

Volume:
- Current: {ctx.get('current_volume', 'N/A')}
- Ratio vs Avg: {ctx.get('volume_ratio', 'N/A')}%

=== VALIDATION CRITERIA ===
Approve the signal ONLY if:
1. Signal direction aligns with market bias and technical indicators
2. Entry price is at a logical technical level (support/resistance, EMA, etc.)
3. SL/TP placement is reasonable based on market structure
4. Volume supports the move
5. RSI is not in extreme territory against the signal direction
6. Overall risk/reward is favorable

Reject if any major red flags exist (e.g., buying into overbought RSI, selling at support, low volume, etc.)

=== REQUIRED OUTPUT ===
Respond ONLY with valid JSON. The 'reasoning' field must be in FRENCH:
{{
  "approved": true|false,
  "confidence": <0-100>,
  "reasoning": "brief 2-3 sentence explanation in FRENCH",
  "risk_level": "LOW|MEDIUM|HIGH",
  "suggested_adjustments": {{
    "sl": <price or null>,
    "tp": <price or null>
  }}
}}
"""
        if strategy_persona:
            # Use Strategy Persona directly as System Prompt (Override)
            # We append the "Output JSON" instruction to ensure format compliance
            system_prompt_override = strategy_persona + "\n\nIMPORTANT: REPOND TOUJOURS EN JSON VALIDE."
            result = self._call_openrouter_api(prompt, system_prompt=system_prompt_override)
        else:
            # Fallback to Generic Bot Persona
            result = self._call_ai_generic(prompt)
        
        if "error" not in result:
            self._set_cache(key, result, ttl_minutes=1)
        
        return result
    
    def analyze_active_position(
        self,
        position_data: Dict[str, Any],
        current_market: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze an active position for risk management (cached 5 min).
        Refactored to rely on System Prompt for persona.
        """
        symbol = position_data.get("symbol", "UNKNOWN")
        key = self._get_cache_key("position", symbol)
        
        cached = self._get_cached_response(key, 5)
        if cached:
            return cached
        
        ctx = current_market or {}
        
        # Extract position details
        side = position_data.get("side", "N/A")
        entry = position_data.get("entry", 0)
        current_price = ctx.get("current_price", 0)
        pnl = ((current_price - entry) / entry * 100) if entry > 0 else 0
        if side == "SELL":
            pnl = -pnl
        
        breakeven_status = "ACTIVE (SL at BreakEven)" if position_data.get("breakeven_active") else "NOT ACTIVE"
        
        # Prompt simplifié
        prompt = f"""Analyze the active position and recommend risk management actions based on your Persona.

=== ACTIVE POSITION ===
Symbol: {symbol}
Side: {side}
Entry Price: ${entry}
Current Price: ${current_price}
Current P&L: {pnl:.2f}%
BreakEven Status: {breakeven_status}

Current Protection:
- Stop Loss: ${position_data.get('sl', 'N/A')}
- Take Profit: ${position_data.get('tp', 'N/A')}

Position Age: {position_data.get('duration', 'N/A')}
Strategy: {position_data.get('strategy', 'N/A')}

=== CURRENT MARKET CONDITIONS ===
Market Regime: {ctx.get('regime', 'UNKNOWN')}
Market Bias: {ctx.get('market_bias', 'NEUTRAL')}

Technical Indicators:
- RSI(14): {ctx.get('rsi', 'N/A')} {self._get_rsi_label(ctx.get('rsi'))}
- ATR: {ctx.get('atr', 'N/A')}
- Price vs EMA20: {ctx.get('ema20_distance', 'N/A')}%
- Price vs EMA50: {ctx.get('ema50_distance', 'N/A')}%

Key Levels:
- Swing High: ${ctx.get('swing_high', 'N/A')}
- Swing Low: ${ctx.get('swing_low', 'N/A')}

Volume:
- Current: {ctx.get('current_volume', 'N/A')}
- Ratio vs Avg: {ctx.get('volume_ratio', 'N/A')}%

=== RISK ASSESSMENT TASK ===
Analyze the position and provide:
1. Should we move SL to break-even? (if in profit and conditions are right)
2. Should we tighten SL to lock in profits?
3. Should we adjust TP based on current momentum?
4. What is the current risk level?

NOTE: If BreakEven is already ACTIVE, do NOT recommend moving to BreakEven again.

=== REQUIRED OUTPUT ===
Respond ONLY with valid JSON. The 'reasoning' field must be in FRENCH:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "recommendation": "HOLD|TIGHTEN_SL|MOVE_TO_BREAKEVEN|TAKE_PROFIT|CLOSE_NOW",
  "reasoning": "2-3 sentence explanation in FRENCH",
  "suggested_sl": <price or null>,
  "suggested_tp": <price or null>,
  "confidence": <0-100>
}}
"""
        result = self._call_ai_generic(prompt)
        
        if "error" not in result:
            self._set_cache(key, result, ttl_minutes=5)
        
        return result
    
    def analyze_market_evolution(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market evolution/sentiment (simple version for UI).
        """
        key = self._get_cache_key("evolution", market_data.get('symbol', 'UNKNOWN'))
        cached = self._get_cached_response(key, 15)
        if cached:
            return cached

        prompt = f"""Analyze the market evolution for {market_data.get('symbol')} at price ${market_data.get('price')}.
        
        Respond ONLY with valid JSON (no markdown):
        {{
            "sentiment": "BULLISH|BEARISH|NEUTRAL",
            "summary": "Brief 1-sentence market summary in FRENCH",
            "key_levels": ["support level", "resistance level"]
        }}
        """
        
        result = self._call_ai_generic(prompt)
        
        if "error" not in result:
            self._set_cache(key, result, ttl_minutes=15)
            
        return result

    
    def analyze_position_risk(self, symbol: str, position_data: Dict[str, Any], market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper for analyze_active_position compatibility"""
        # Ensure symbol is in position_data
        if "symbol" not in position_data:
            position_data["symbol"] = symbol
        return self.analyze_active_position(position_data, market_data)

    def _get_rsi_label(self, rsi: Optional[float]) -> str:
        """Helper to label RSI values"""
        if rsi is None:
            return ""
        if rsi > 70:
            return "→ OVERBOUGHT"
        elif rsi < 30:
            return "→ OVERSOLD"
        else:
            return "→ NEUTRAL"


# Global singleton instance
ia_service = IAService()