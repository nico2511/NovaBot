import google.generativeai as genai
from app.core.config import config
import threading
import json
from datetime import datetime, timedelta

class GeminiService:
    def __init__(self):
        # 1. Init Gemini - Using Gemini 2.0 Flash (free 1500 req/day)
        self.gemini_key = config.GEMINI_API_KEY
        self.gemini_models = []
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_models = [
                'gemini-2.0-flash-exp',
                'gemini-2.5-flash',
                'gemini-flash-latest',
            ]  # Prioritize confirmed available models (1.5 removed)
        
        # 2. Init OpenRouter (via OpenAI client) - OPTIONAL
        self.openrouter_key = config.OPENROUTER_API_KEY
        self.openrouter_client = None
        self.openrouter_model = "meta-llama/llama-3.3-70b-instruct:free"

        if self.openrouter_key:
            try:
                from openai import OpenAI
                self.openrouter_client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_key,
                )
            except ImportError:
                print("⚠️ OpenAI module not found. OpenRouter fallback disabled.")
                self.openrouter_client = None
            except Exception as e:
                print(f"⚠️ Failed to init OpenRouter: {e}")
                self.openrouter_client = None

        self.provider_order = ["gemini", "openrouter"]  # Gemini first, OpenRouter fallback

        # Cache
        self.last_market_analysis = None
        self.last_market_analysis_time = None
        self.cache = {}
        
        # Circuit Breaker
        self.circuit_breaker_until = None

    def _call_gemini_api(self, prompt: str) -> dict:
        """Call official Gemini API"""
        if not self.gemini_key:
             raise Exception("Gemini Key missing")
             
        for model_name in self.gemini_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                return {"raw_output": clean_text, "model": f"gemini-official:{model_name}"}
            except Exception as e:
                # If specific model fails, try next
                if "429" in str(e) or "quota" in str(e).lower():
                    continue 
                raise e # Other errors might be fatal
        raise Exception("All Gemini models exhausted (Quota or Error)")

    def _call_openrouter_api(self, prompt: str) -> dict:
        """Call OpenRouter API"""
        if not self.openrouter_client:
            raise Exception("OpenRouter Key missing")
            
        try:
            completion = self.openrouter_client.chat.completions.create(
                model=self.openrouter_model,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            raw_content = completion.choices[0].message.content
            clean_text = raw_content.replace("```json", "").replace("```", "").strip()
            return {"raw_output": clean_text, "model": f"openrouter:{self.openrouter_model}"}
        except Exception as e:
            raise Exception(f"OpenRouter failed: {e}")

    def _call_ai_generic(self, prompt: str) -> dict:
        """Dispatcher: Try providers in order"""
        
        # Check Circuit Breaker
        if self.circuit_breaker_until:
            if datetime.now() < self.circuit_breaker_until:
                remaining = int((self.circuit_breaker_until - datetime.now()).total_seconds() / 60)
                # Silent return to avoid spamming logs
                return {"error": "AI Circuit Breaker Active", "raw_output": json.dumps({"explanation": f"IA en pause pour {remaining} min (Quota épuisé)"})}
            else:
                # Reset breaker
                self.circuit_breaker_until = None
                print("⚡ AI Circuit Breaker RESET - Resuming AI calls")

        errors = []
        
        for provider in self.provider_order:
            try:
                if provider == "gemini":
                    return self._call_gemini_api(prompt)
                elif provider == "openrouter":
                    return self._call_openrouter_api(prompt)
            except Exception as e:
                error_str = str(e).lower()
                print(f"⚠️ AI Provider {provider} failed: {e}")
                errors.append(f"{provider}: {e}")
                
                # Check for Quota/Rate Limit errors to trigger Circuit Breaker
                if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                     # Only trigger if this is the LAST provider or if we want to be aggressive
                     pass 
                continue
        
        # If we get here, all failed
        # Check if it was a quota issue
        if any("quota" in e.lower() or "429" in e.lower() or "exhausted" in e.lower() for e in errors):
            self.circuit_breaker_until = datetime.now() + timedelta(minutes=10)
            print("❄️ AI CIRCUIT BREAKER TRIGGERED: Pausing AI for 10 minutes (Quota/Rate Limits)")
            
        return {"raw_output": json.dumps({"error": "All AI providers failed", "details": errors})}

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
        Tu es un Expert Trader Crypto spécialisé en Risk Management. Analyse ce signal de trading et fournis une évaluation COHÉRENTE.
        
        SIGNAL:
        - Type: {signal_type}
        - Stratégie: {strategy}
        - Prix d'entrée: {entry_price}
        - Stop Loss proposé: {sl_price}
        - Take Profit proposé: {tp_price}
        - Risk:Reward actuel: {risk_reward}
        
        CONTEXTE MARCHÉ:
        {context_str}
        
        INSTRUCTIONS:
        1. Analyse la COHÉRENCE du trade:
           - Le SL est-il trop serré ou trop large par rapport à la volatilité?
           - Le TP est-il réaliste par rapport au trend et à la stratégie?
           - Le R:R est-il adapté au type de trade (scalp vs swing)?
        
        2. Considère le CONTEXTE:
           - Volatilité actuelle (ATR, range récent)
           - Direction du trend (bullish/bearish/range)
           - Type de stratégie (scalp = R:R 1.5-2, swing = R:R 2-3)
        
        3. ADAPTE les niveaux si nécessaire:
           - Si SL trop serré → suggère niveau plus respirant
           - Si TP irréaliste → ajuste selon résistances/supports
           - Si R:R < 1.5 → recommande ajustement
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        {{
            "explanation": "Analyse courte du trade (2-3 phrases en FRANÇAIS)",
            "confidence": "HIGH|MEDIUM|LOW",
            "risks": ["risque1", "risque2"],
            "recommendation": "TAKE|SKIP|ADJUST",
            "suggested_sl": prix_sl_optimal (float, ou null si OK),
            "suggested_tp": prix_tp_optimal (float, ou null si OK),
            "reasoning": "Pourquoi ces ajustements (si ADJUST)"
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
        """Analyze risk for a position or potential position"""
        # Cache for 5 mins
        key = self._get_cache_key("position_risk", symbol)
        cached = self._get_cached_response(key, 5)
        if cached:
            return cached
        
        prompt = f"""
        Risk Analyst Crypto. Analyse risque position {symbol}:
        Position: {json.dumps(position_data) if position_data else 'Nouvelle position'}
        Marché: {json.dumps(market_data) if market_data else 'N/A'}
        
        Réponds UNIQUEMENT avec JSON:
        - risk_score: (0-100, 100 = très risqué)
        - risk_factors: Liste facteurs de risque (FR)
        - recommendations: Conseils gestion risque
        - stop_loss_suggestion: Prix SL suggéré (si applicable)
        - take_profit_suggestion: Prix TP suggéré (si applicable)
        """
        result = self._call_ai_generic(prompt)
        if "error" not in result:
            self._set_cache(key, result)
        return result

gemini_service = GeminiService()
