import google.generativeai as genai
from app.core.config import config
import threading
import json
from datetime import datetime, timedelta

class IAService:
    def __init__(self):
        # 1. Init OpenRouter (Unified Provider)
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.client = None
        self.model = config.AI_MODEL_NAME  # Dynamic model from config

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

        # Cache
        self.last_market_analysis = None
        self.last_market_analysis_time = None
        self.cache = {}
        
        # Circuit Breaker
        self.circuit_breaker_until = None

    @staticmethod
    def extract_json(text: str) -> str:
        """Robustly extract JSON from text even if markdown wrapped"""
        import re
        try:
            # 1. Try to find JSON block ```json ... ```
            match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
            if match:
                return match.group(1)
            # 2. Try to find just outer braces { ... }
            # Match the first { to the last }
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                return match.group(1)
            return text.strip()
        except Exception:
            return text.strip()

    def _call_openrouter_api(self, prompt: str) -> dict:
        """Call OpenRouter API"""
        if not self.client:
            raise Exception("AI Client not initialized (Missing Key)")
            
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            raw_content = completion.choices[0].message.content
            clean_text = self.extract_json(raw_content)
            return {"raw_output": clean_text, "model": f"openrouter:{self.model}"}
        except Exception as e:
            raise Exception(f"OpenRouter failed: {e}")

    def _call_ai_generic(self, prompt: str) -> dict:
        """Dispatcher: Try provider"""
        
        # Check Circuit Breaker
        if self.circuit_breaker_until:
            if datetime.now() < self.circuit_breaker_until:
                remaining = int((self.circuit_breaker_until - datetime.now()).total_seconds() / 60)
                return {"error": "AI Circuit Breaker Active", "raw_output": json.dumps({"explanation": f"IA en pause pour {remaining} min (Quota épuisé)"})}
            else:
                self.circuit_breaker_until = None
                print("⚡ AI Circuit Breaker RESET - Resuming AI calls")

        try:
            return self._call_openrouter_api(prompt)
        except Exception as e:
            error_str = str(e).lower()
            print(f"⚠️ AI Call failed: {e}")
            
            if "quota" in error_str or "429" in error_str:
                self.circuit_breaker_until = datetime.now() + timedelta(minutes=10)
                print("❄️ AI CIRCUIT BREAKER TRIGGERED: Pausing AI for 10 minutes")
                
            return {"raw_output": json.dumps({"error": "AI call failed", "details": str(e)})}

    def _get_cache_key(self, type_: str, unique_id: str) -> str:
        return f"{type_}:{unique_id}"

    def _get_cached_response(self, key: str, ttl_minutes: int):
        if key in self.cache:
            entry = self.cache[key]
            if (datetime.now() - entry["time"]).total_seconds() < (ttl_minutes * 60):
                return entry["data"]
        return None

    def _set_cache(self, key: str, data: dict):
        self.cache[key] = {
            "time": datetime.now(),
            "data": data
        }

    def analyze_market(self, market_data: dict) -> dict:
        """Cached market analysis (15 min TTL)"""
        symbol = market_data.get('symbol', 'UNKNOWN')
        # Create a rough hash/key based on symbol and price (rounded) to avoid minor fluctuation triggering new analysis
        # Actually, simpler: just cache by symbol for 15 mins.
        key = self._get_cache_key("market", symbol)
        
        cached = self._get_cached_response(key, 15)
        if cached:
            return cached
            
        prompt = f"""
        Agis comme un expert Quant Trader Crypto. Analyse les indicateurs suivants pour {symbol}:
        
        Données:
        {market_data}
        
        Réponds UNIQUEMENT avec un objet JSON valide (sans markdown) contenant:
        - risk_level: (LOW, MEDIUM, HIGH)
        - trend: (BULLISH, BEARISH, NEUTRAL, RANGE)
        - summary: Une analyse de 2 phrases en FRANÇAIS.
        - reasoning: Une liste de 3 facteurs clés.
        """
        result = self._call_ai_generic(prompt)
        # Only cache if successful
        if "error" not in result and "raw_output" in result and "Error" not in result["raw_output"]:
             self._set_cache(key, result)
        return result
    
    def validate_signal(self, signal_data: dict, market_context: dict) -> dict:
        """Validate a trading signal with AI before execution"""
        # Cache for 1 min (signals are time-sensitive)
        symbol = signal_data.get('symbol', 'UNKNOWN')
        key = self._get_cache_key("signal_validation", f"{symbol}_{signal_data.get('signal')}")
        cached = self._get_cached_response(key, 1)
        if cached:
            return cached
        
        ctx = market_context or {}
        
        prompt = f"""You are a professional crypto trading signal validator. Your job is to approve or reject trade signals based on technical analysis and market conditions.

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

Technical Indicators:
- RSI(14): {ctx.get('rsi', 'N/A')} {self._get_rsi_label(ctx.get('rsi'))}
- ATR: {ctx.get('atr', 'N/A')} (Volatility: {ctx.get('volatility_percentile', 'N/A')}th percentile)
- Price vs EMA20: {ctx.get('ema20_distance', 'N/A')}%
- Price vs EMA50: {ctx.get('ema50_distance', 'N/A')}%

Key Levels:
- Swing High: ${ctx.get('swing_high', 'N/A')}
- Swing Low: ${ctx.get('swing_low', 'N/A')}

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
Respond ONLY with valid JSON:
{{
  "approved": true|false,
  "confidence": <0-100>,
  "reasoning": "brief 2-3 sentence explanation of decision",
  "risk_factors": ["factor1", "factor2"],
  "suggested_adjustments": {{
    "entry": <price_or_null>,
    "sl": <price_or_null>,
    "tp": <price_or_null>
  }}
}}"""
        
        result = self._call_ai_generic(prompt)
        if "error" not in result:
            self._set_cache(key, result)
        return result
    
    def analyze_trade_signal(self, signal_data: dict, market_context: dict = None) -> dict:
        """Cached signal analysis (5 min TTL for same signal/price)"""
        # Key includes symbol, signal logic, and Price bucket (to avoid re-analyzing same price level)
        # e.g. "BTC-BUY-ScalpEmaRsi-88000" (rounded price)
        price = signal_data.get("price", 0)
        strat = signal_data.get("strategy", "stat")
        side = signal_data.get("signal", "none")
        # Round price to nearest 100 to group similar signals
        price_bucket = round(price / 10.0) * 10
        
        key = self._get_cache_key("signal", f"{strat}-{side}-{price_bucket}")
        
        cached = self._get_cached_response(key, 10)
        if cached:
            return cached

        context_str = f"\nContexte: {json.dumps(market_context)}" if market_context else ""
        
        # Extract key data for better analysis
        entry_price = signal_data.get("price", 0)
        sl_price = signal_data.get("sl", 0)
        tp_price = signal_data.get("tp", 0)
        strategy = signal_data.get("strategy", "Unknown")
        signal_type = signal_data.get("signal", "UNKNOWN")
        
        # Calculate current R:R if SL/TP exist
        risk_reward = "N/A"
        if sl_price and tp_price and entry_price:
            risk = abs(entry_price - sl_price)
            reward = abs(tp_price - entry_price)
            if risk > 0:
                risk_reward = f"{reward/risk:.2f}"
        
        prompt = f"""
        ACT AS A SENIOR QUANT TRADER.
        Review this trade signal and data.
        
        SIGNAL:
        - Type: {signal_type}
        - Strategy: {strategy}
        - Enter: {entry_price}
        - SL: {sl_price}
        - TP: {tp_price}
        
        MARKET CONTEXT:
        {context_str}
        
        TASK:
        1. Analyze if this signal matches the current market regime.
        2. Check for contradictions (e.g. BUY signal but RSI is 80, or huge resistance overhead).
        3. Make a GO/NO-GO decision.
        
        CRITICAL RULES (DO NOT IGNORE):
        - IF SIGNAL == SELL AND MARKET BIAS == BEARISH -> YOU MUST APPROVE (unless specific reason not to).
        - IF SIGNAL == BUY AND MARKET BIAS == BULLISH -> YOU MUST APPROVE (unless specific reason not to).
        - Alignment with trend is POSITIVE. Do NOT reject a SELL signal because the market is BEARISH - that is the POINT.
        
        OUTPUT FORMAT (JSON ONLY, NO MARKDOWN):
        {{
            "decision": "APPROVE" | "REJECT",
            "confidence_score": (0-100),
            "reasoning": "Short explanation...",
            "risk_factors": ["risk1", "risk2"],
            "suggested_modifications": "None or e.g. lower leverage"
        }}
        """
        result = self._call_ai_generic(prompt)
        if "error" not in result:
            self._set_cache(key, result)
        return result
    
    def analyze_market_evolution(self, current_data: dict, previous_data: dict = None) -> dict:
        # Evolution is periodic by nature, usually called by main loop with its own timer
        # But we can cache it too just in case
        key = self._get_cache_key("evolution", current_data.get("symbol", "Unk"))
        cached = self._get_cached_response(key, 15)
        if cached:
            return cached

        prev_str = f"\nAvant: {json.dumps(previous_data)}" if previous_data else ""
        prompt = f"""
        Analyste Crypto. Compare l'état actuel et précédent:
        Actuel: {json.dumps(current_data)}
        {prev_str}
        
        Réponds UNIQUEMENT avec JSON:
        - changes: Liste changements (FR)
        - implications: Impact trading
        - alert_level: (CRITICAL, HIGH, MEDIUM, LOW, NONE)
        """
        result = self._call_ai_generic(prompt)
        if "error" not in result:
             self._set_cache(key, result)
        self.last_market_analysis = result
        self.last_market_analysis_time = datetime.now()
        return result

    def analyze_active_position(self, position_data: dict, current_market: dict) -> dict:
        # Cache for 5 mins
        key = self._get_cache_key("position", position_data.get("symbol", "Unk"))
        cached = self._get_cached_response(key, 5)
        if cached:
            return cached

        prompt = f"""
        Risk Manager Crypto. Analyse position:
        Position: {position_data}
        Marché: {current_market}
        
        Réponds UNIQUEMENT avec JSON:
        - status: (WINNING, LOSING, etc)
        - recommendations: Conseils (FR)
        - risk_level: (LOW...CRITICAL)
        - actions: (HOLD, CLOSE, etc)
        - reasoning: Pourquoi
        """
        result = self._call_ai_generic(prompt)
        if "error" not in result:
             self._set_cache(key, result)
        
        return result

    def analyze_indicators(self, indicators_dict: dict) -> dict:
        prompt = f"""
        Expert Tech Analysis. Explique indicateurs:
        {json.dumps(indicators_dict)}
        
        Réponds UNIQUEMENT avec JSON:
        - interpretations: Dict explications (FR)
        - overall_signal: (BULLISH, BEARISH...)
        - key_points: 3 points clés
        """
        return self._call_ai_generic(prompt)

    def generate_market_commentary(self, full_context: dict) -> dict:
        prompt = f"""
        Analyste Pro. Rédige commentaire marché:
        {json.dumps(full_context)}
        
        Réponds UNIQUEMENT avec JSON:
        - commentary: 4-5 phrases narratives (FR)
        - sentiment: (VERY_BULLISH...)
        - outlook: Perspective court terme
        """
        return self._call_ai_generic(prompt)
    
    def analyze_position_risk(self, symbol: str, position_data: dict = None, market_data: dict = None) -> dict:
        """Analyze risk for a position with comprehensive market context"""
        # Cache for 5 mins
        key = self._get_cache_key("position_risk", symbol)
        cached = self._get_cached_response(key, 5)
        if cached:
            return cached
        
        # Extract market context
        ctx = market_data or {}
        
        # Build professional prompt
        prompt = f"""You are a professional crypto trading risk analyst with expertise in technical analysis and position management.

=== POSITION ANALYSIS REQUEST ===

Symbol: {symbol}
Current Price: ${ctx.get('current_price', 'N/A')}
Market Regime: {ctx.get('regime', 'UNKNOWN')}
Market Bias: {ctx.get('market_bias', 'NEUTRAL')}

{f'''Position Details:
- Direction: {position_data.get('side', 'N/A')}
- Entry Price: ${position_data.get('entry_price', 'N/A')}
- Unrealized PnL: {ctx.get('pnl_percent', 0):.2f}%
- Time in Trade: {ctx.get('time_in_trade', 'N/A')}
- Current SL: ${position_data.get('sl', 'N/A')} ({ctx.get('sl_distance', 'N/A')}% from entry)
- Current TP: ${position_data.get('tp', 'N/A')} ({ctx.get('tp_distance', 'N/A')}% from entry)
- Risk/Reward Ratio: {ctx.get('rr_ratio', 'N/A')}
''' if position_data else 'Analyzing potential entry opportunity'}

=== TECHNICAL INDICATORS ===
- RSI(14): {ctx.get('rsi', 'N/A')} {self._get_rsi_label(ctx.get('rsi'))}
- ATR: {ctx.get('atr', 'N/A')} (Volatility: {ctx.get('volatility_percentile', 'N/A')}th percentile)
- Price vs EMA20: {ctx.get('ema20_distance', 'N/A')}%
- Price vs EMA50: {ctx.get('ema50_distance', 'N/A')}%

=== KEY PRICE LEVELS ===
- Recent Swing High: ${ctx.get('swing_high', 'N/A')}
- Recent Swing Low: ${ctx.get('swing_low', 'N/A')}
- EMA20: ${ctx.get('ema_20', 'N/A')}
- EMA50: ${ctx.get('ema_50', 'N/A')}
{f"- EMA200: ${ctx.get('ema_200', 'N/A')}" if ctx.get('ema_200') else ''}

=== VOLUME ANALYSIS ===
- Current Volume: {ctx.get('current_volume', 'N/A')}
- Average Volume (50): {ctx.get('avg_volume', 'N/A')}
- Volume Ratio: {ctx.get('volume_ratio', 'N/A')}% of average

=== REQUIRED OUTPUT ===
Provide a JSON response with:
1. Risk assessment (0-100 score, where 100 = extremely risky)
2. Risk level classification
3. Key risk factors identified
4. Actionable recommendations
5. Optimal SL/TP based on technical levels (not arbitrary percentages)

Respond ONLY with valid JSON in this exact format:
{{
  "risk_score": <0-100>,
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "risk_factors": ["factor1", "factor2", "factor3"],
  "market_bias": "BULLISH|BEARISH|NEUTRAL",
  "recommendations": ["action1", "action2"],
  "stop_loss_suggestion": <price_number>,
  "stop_loss_reasoning": "brief explanation based on technical level",
  "take_profit_suggestion": <price_number>,
  "take_profit_reasoning": "brief explanation based on technical level",
  "confidence": <0-100>,
  "reasoning": "2-3 sentence summary of analysis"
}}"""
        
        result = self._call_ai_generic(prompt)
        if "error" not in result:
            self._set_cache(key, result)
        return result
    
    def _get_rsi_label(self, rsi):
        """Helper to label RSI values"""
        if rsi is None:
            return ""
        if rsi > 70:
            return "→ OVERBOUGHT"
        elif rsi < 30:
            return "→ OVERSOLD"
        else:
            return "→ NEUTRAL"

ia_service = IAService()
