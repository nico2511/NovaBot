"""
AI Service for Trading Bot - Production Ready
Handles all AI-powered market analysis and signal validation using OpenRouter API
"""
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
import json
import logging
import re

from app.core.config import config
from app.core.prompts import get_system_prompt, SIGNAL_VALIDATION_JSON_SCHEMA

logger = logging.getLogger(__name__)


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
                logger.info("AI Service (OpenRouter) initialized with model: %s", self.model)
            except ImportError:
                logger.warning("OpenAI module not found. AI Service disabled.")
                self.client = None
            except Exception as e:
                logger.warning("Failed to init AI Service: %s", e)
                self.client = None
        else:
            logger.info("OpenRouter Key not found. AI Service disabled.")
    
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
        Uses brace matching so nested objects are not truncated.
        """
        if not text:
            return ""
        try:
            stripped = text.strip()
            fence = re.search(r"```(?:json)?\s*", stripped, re.IGNORECASE)
            if fence:
                start = fence.end()
                end = stripped.find("```", start)
                if end != -1:
                    stripped = stripped[start:end].strip()

            start = stripped.find("{")
            if start == -1:
                return stripped

            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(stripped)):
                ch = stripped[i]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                elif ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return stripped[start : i + 1]

            match = re.search(r"(\{.*\})", stripped, re.DOTALL)
            return match.group(1) if match else stripped
        except Exception:
            return text.strip()

    @staticmethod
    def repair_json(text: str) -> str:
        """
        Fix common LLM JSON mistakes (template placeholders, trailing commas, etc.).
        """
        if not text:
            return text

        repaired = text
        repaired = re.sub(r"//.*?$", "", repaired, flags=re.MULTILINE)
        repaired = re.sub(r"/\*.*?\*/", "", repaired, flags=re.DOTALL)
        repaired = re.sub(r"\btrue\s*\|\s*false\b", "false", repaired, flags=re.IGNORECASE)
        repaired = re.sub(
            r'"confidence"\s*:\s*<[^>]*>',
            '"confidence": 50',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r'"risk_score"\s*:\s*<[^>]*>',
            '"risk_score": 5',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(r":\s*<price or null>", ": null", repaired, flags=re.IGNORECASE)
        repaired = re.sub(
            r'"rejection_reason_category"\s*:\s*"See System Prompt ENUM"\s*\|\s*null',
            '"rejection_reason_category": null',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(r":\s*<[^>]+>", ": null", repaired)
        repaired = re.sub(r":\s*boolean\b", ": false", repaired, flags=re.IGNORECASE)
        repaired = re.sub(r":\s*integer\b", ": 0", repaired, flags=re.IGNORECASE)
        repaired = re.sub(r":\s*number\b", ": 0", repaired, flags=re.IGNORECASE)
        repaired = re.sub(r":\s*string\b", ': ""', repaired, flags=re.IGNORECASE)
        repaired = re.sub(r":\s*array<string>", ": []", repaired, flags=re.IGNORECASE)
        repaired = re.sub(
            r'"confidence"\s*:\s*0\s*-\s*100\b',
            '"confidence": 50',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r'"confidence"\s*:\s*(\d+(?:\.\d+)?)\s*%',
            r'"confidence": \1',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r':\s*(?:number|string)\s*\|\s*null',
            ": null",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r':\s*\d+(?:\.\d+)?\s*\|\s*null',
            ": null",
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r'"risk_level"\s*:\s*([A-Z][A-Z_]*(?:\|[A-Z][A-Z_]*)+)',
            '"risk_level": "MEDIUM"',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r'"rejection_reason_category"\s*:\s*([A-Z][A-Z_]*(?:\|[A-Z][A-Z_]*)+)',
            '"rejection_reason_category": null',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(
            r'"risk_level"\s*:\s*([A-Z]+)\b(?!\s*[\|,"])',
            r'"risk_level": "\1"',
            repaired,
            flags=re.IGNORECASE,
        )
        repaired = re.sub(r",\s*}", "}", repaired)
        repaired = re.sub(r",\s*]", "]", repaired)
        return repaired

    @staticmethod
    def _fallback_extract_validation_fields(text: str) -> Optional[Dict[str, Any]]:
        """Best-effort regex recovery when JSON is still invalid after repair."""
        if not text:
            return None

        approved_match = re.search(r'"approved"\s*:\s*(true|false)', text, re.IGNORECASE)
        confidence_match = re.search(r'"confidence"\s*:\s*(\d+(?:\.\d+)?)', text, re.IGNORECASE)
        reasoning_match = re.search(r'"reasoning"\s*:\s*"((?:\\.|[^"\\])*)"', text, re.IGNORECASE | re.DOTALL)
        risk_level_match = re.search(
            r'"risk_level"\s*:\s*(?:"([^"]+)"|([A-Z]+))',
            text,
            re.IGNORECASE,
        )

        if not approved_match and not confidence_match:
            return None

        risk_level = "MEDIUM"
        if risk_level_match:
            risk_level = (risk_level_match.group(1) or risk_level_match.group(2) or "MEDIUM").upper()
            if "|" in risk_level:
                risk_level = "MEDIUM"

        return {
            "approved": approved_match.group(1).lower() == "true" if approved_match else False,
            "confidence": int(float(confidence_match.group(1))) if confidence_match else 0,
            "reasoning": (
                reasoning_match.group(1).replace('\\"', '"')
                if reasoning_match
                else "Recovered from partial AI JSON response"
            ),
            "risk_level": risk_level,
            "risk_score": 5,
            "decisive_factors": [],
            "rejection_reason_category": None,
            "suggested_adjustments": {"sl": None, "tp": None},
            "_recovered_from_partial_json": True,
        }

    def parse_json_response(self, text: str) -> Dict[str, Any]:
        """Extract, repair if needed, and parse JSON from an LLM response."""
        extracted = self.extract_json(text)
        if not extracted:
            raise json.JSONDecodeError("Empty JSON payload", text or "", 0)

        candidates = [extracted]
        repaired = self.repair_json(extracted)
        if repaired != extracted:
            candidates.append(repaired)

        last_error: Optional[json.JSONDecodeError] = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if not isinstance(parsed, dict):
                    raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
                return parsed
            except json.JSONDecodeError as exc:
                last_error = exc

        fallback = self._fallback_extract_validation_fields(extracted)
        if fallback:
            logger.warning(
                "AI validation JSON recovered via regex fallback | snippet=%s",
                str(extracted)[:400],
            )
            return fallback

        if last_error is not None:
            raise last_error
        raise json.JSONDecodeError("Invalid JSON payload", extracted, 0)
    
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
            
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"},
            }
            try:
                completion = self.client.chat.completions.create(**request_kwargs)
            except Exception as format_err:
                if "response_format" in str(format_err).lower() or "json" in str(format_err).lower():
                    logger.warning("Model rejected JSON response_format, retrying without it: %s", format_err)
                    request_kwargs.pop("response_format", None)
                    completion = self.client.chat.completions.create(**request_kwargs)
                else:
                    raise
            raw_content = completion.choices[0].message.content or ""
            return {"raw_output": raw_content.strip(), "model": f"openrouter:{self.model}"}
        except Exception as e:
            raise Exception(f"OpenRouter failed: {e}")
    
    def _parse_validation_payload(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw_output JSON into the result dict used for logging and constraints."""
        if not result:
            return {}
        raw = result.get("raw_output")
        if not raw:
            return {
                **result,
                "approved": False,
                "confidence": 0,
                "reasoning": "Empty AI response (no raw_output)",
                "rejection_reason_category": "AI_PARSE_ERROR",
            }
        try:
            parsed = self.parse_json_response(raw)
            if parsed.get("error"):
                return {
                    **result,
                    **parsed,
                    "approved": False,
                    "confidence": 0,
                    "reasoning": parsed.get("details") or parsed.get("error", "AI call failed"),
                    "rejection_reason_category": "AI_UNAVAILABLE",
                    "raw_output": raw,
                }
            merged = {**result, **parsed}
            merged["raw_output"] = raw
            return merged
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("AI validation JSON parse failed: %s | snippet=%s", e, str(raw)[:400])
            return {
                **result,
                "approved": False,
                "confidence": 0,
                "reasoning": f"Invalid AI JSON: {e}",
                "rejection_reason_category": "AI_PARSE_ERROR",
                "raw_output": raw,
            }

    def _call_ai_generic(self, prompt: str) -> Dict[str, Any]:
        """
        Generic AI call dispatcher with Circuit Breaker logic.
        Injects the Dynamic System Prompt automatically.
        """
        # Check Circuit Breaker
        if self.circuit_breaker_until:
            if datetime.now() < self.circuit_breaker_until:
                remaining = int((self.circuit_breaker_until - datetime.now()).total_seconds() / 60)
                logger.warning("AI Circuit Breaker active (%s min left). Using rule-based fallback.", remaining)
                return self._rule_based_fallback(prompt)
            self.circuit_breaker_until = None
            logger.info("AI Circuit Breaker RESET - Resuming AI calls")

        try:
            system_prompt = self.get_dynamic_system_prompt()
            return self._call_openrouter_api(prompt, system_prompt=system_prompt)
        except Exception as e:
            error_str = str(e).lower()
            logger.warning("AI Call failed: %s", e)

            # Trigger Circuit Breaker on quota errors
            if "quota" in error_str or "429" in error_str:
                self.circuit_breaker_until = datetime.now() + timedelta(minutes=10)
                logger.error("AI CIRCUIT BREAKER TRIGGERED: Pausing AI for 10 minutes")
            
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
- summary: A 2-sentence analysis in ENGLISH
- reasoning: A list of 3 key factors (in ENGLISH)

Example:
{{
  "risk_level": "MEDIUM",
  "trend": "BULLISH",
  "summary": "The market shows a bullish trend with balanced RSI. Volatility remains moderate.",
  "reasoning": ["RSI at 55 indicates healthy momentum", "Price above EMA20", "Volume up 20%"]
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
        strategy_persona: Optional[str] = None,
        strategy: Any = None,
    ) -> Dict[str, Any]:
        """
        Validate a trading signal before execution (AI Gatekeeper).
        Strategy owns persona / criteria / post-AI geometry; risk_profile is capital appetite.
        """
        symbol = signal_data.get('symbol', 'UNKNOWN')
        key = self._get_cache_key("signal_validation", f"{symbol}_{signal_data.get('signal')}")
        
        cached = self._get_cached_response(key, 1)
        if cached:
            return cached
        
        ctx = market_context or {}

        # Pre-compute R:R / SL width so the model doesn't invent geometry errors.
        rr_line = "N/A"
        sl_pct_line = "N/A"
        try:
            entry = float(signal_data.get("price") or 0)
            sl = float(signal_data.get("sl") or 0)
            tp = float(signal_data.get("tp") or 0)
            if entry > 0 and sl > 0 and tp > 0:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                if risk > 0:
                    rr_line = f"{(reward / risk):.2f}"
                sl_pct_line = f"{(risk / entry) * 100:.2f}%"
        except Exception:
            pass

        strat_criteria = None
        if strategy is not None and hasattr(strategy, "get_ai_validation_criteria"):
            try:
                strat_criteria = strategy.get_ai_validation_criteria()
            except Exception:
                strat_criteria = None
        if not strategy_persona and strategy is not None and hasattr(strategy, "get_ai_persona"):
            try:
                strategy_persona = strategy.get_ai_persona()
            except Exception:
                strategy_persona = None

        if strat_criteria:
            criteria = strat_criteria
        else:
            criteria = """=== VALIDATION CRITERIA ===
Approve when direction, structure, volume and R:R are coherent.
Reject on major red flags (counter-trend, dead volume < 50% avg, bad R:R, extreme chase).
Prefer execution when R:R is good and momentum exists — do not over-filter."""

        swing_high = ctx.get("swing_high", "N/A")
        swing_low = ctx.get("swing_low", "N/A")
        tp_structure_note = ""
        try:
            entry_f = float(signal_data.get("price") or 0)
            tp_f = float(signal_data.get("tp") or 0)
            sh_f = float(ctx.get("swing_high") or 0)
            slw_f = float(ctx.get("swing_low") or 0)
            side = str(signal_data.get("signal") or "").upper()
            if side == "BUY" and entry_f > 0 and tp_f > 0 and sh_f > 0:
                rel = ((tp_f - sh_f) / entry_f) * 100.0
                tp_structure_note = (
                    f"TP vs Swing High: {rel:+.2f}% of entry "
                    f"({'TRIM REQUIRED' if tp_f > sh_f else 'OK — at/below swing'})"
                )
            elif side == "SELL" and entry_f > 0 and tp_f > 0 and slw_f > 0:
                rel = ((slw_f - tp_f) / entry_f) * 100.0
                tp_structure_note = (
                    f"TP vs Swing Low: gap {rel:+.2f}% of entry "
                    f"({'TRIM REQUIRED' if tp_f < slw_f else 'OK — at/above swing'})"
                )
        except Exception:
            tp_structure_note = ""

        strat_tf = str(ctx.get("strategy_timeframe") or config.TRADING_TIMEFRAME or "15m")

        account_default = config.RISK_PROFILE or "Balanced Growth"
        if strategy is not None and hasattr(strategy, "get_risk_profile"):
            try:
                risk_profile = strategy.get_risk_profile(account_default)
            except Exception:
                risk_profile = account_default
        else:
            risk_profile = account_default

        # Prompt simplifié : Instruction directe de validation.
        prompt = f"""Validate the following trading signal based on the current market conditions and your configured Persona/Risk Profile.

=== SIGNAL TO VALIDATE ===
Symbol: {symbol}
Direction: {signal_data.get('signal', 'N/A')}
Strategy: {signal_data.get('strategy', 'N/A')}
Strategy Timeframe: {strat_tf}
Entry Price: ${signal_data.get('price', 'N/A')}
Proposed SL: ${signal_data.get('sl', 'N/A')}
Proposed TP: ${signal_data.get('tp', 'N/A')}
Computed R:R: {rr_line}
SL Distance: {sl_pct_line}
{tp_structure_note}

=== CURRENT MARKET CONDITIONS ({strat_tf}) ===
Current Price: ${ctx.get('current_price', 'N/A')}
Market Regime: {ctx.get('regime', 'UNKNOWN')}
Market Bias: {ctx.get('market_bias', 'NEUTRAL')}

Technical Indicators (Dynamic on {strat_tf}):
- RSI(14): {ctx.get('rsi_val', 'N/A')} [{ctx.get('rsi_trend', '')}] ({strat_tf} Change: {ctx.get('rsi_slope', 0):+.1f})
- Volume: {ctx.get('vol_current', 'N/A')} [{ctx.get('vol_trend', '')}] ({strat_tf} Change: {ctx.get('vol_slope', 0):+.1f}%)
- ADX: {ctx.get('adx_val', 'N/A')} (Slope: {ctx.get('adx_slope', 0):+.1f})
- MACD (12,26,9): Line {ctx.get('macd_line', 'N/A')} | Signal {ctx.get('macd_signal', 'N/A')} | Hist {ctx.get('macd_hist', 'N/A')}
- Open Interest: ${int(ctx.get('open_interest', 0)):,}
- Funding Rate: {ctx.get('funding_rate', 0):.4f}% ({"Longs pay Shorts" if ctx.get('funding_rate', 0) > 0 else "Shorts pay Longs" if ctx.get('funding_rate', 0) < 0 else "Neutral"})
- Price Action: {ctx.get('price_trend', '')} ({ctx.get('price_change_15m', 0):+.2f}% on {strat_tf})

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
- Swing High: ${swing_high}
- Swing Low: ${swing_low}

=== COPILOT SENTIMENT (MTF) ===
{ctx.get('mtf_sentiment', 'N/A')}

Volume:
- Current: {ctx.get('current_volume', 'N/A')}
- Ratio vs Avg: {ctx.get('volume_ratio', 'N/A')}%

{criteria}

=== REQUIRED OUTPUT ===
{SIGNAL_VALIDATION_JSON_SCHEMA}
"""
        # Always keep the full dynamic system prompt (risk profile = capital appetite).
        # Strategy persona is PRIMARY for trading vocabulary / geometry.
        # Primary timeframe follows the strategy plan (e.g. 1h for trend_lt), not global 15m.
        system_prompt = get_system_prompt(
            persona=config.BOT_PERSONA,
            risk_profile=risk_profile,
            timeframe=strat_tf,
        )
        if strategy_persona:
            system_prompt = (
                f"{system_prompt}\n\n"
                f"=== STRATEGY PERSONA (PRIMARY FOR THIS SIGNAL) ===\n"
                f"{strategy_persona}\n\n"
                f"If STRATEGY PERSONA conflicts with generic global prompt wording, "
                f"follow STRATEGY PERSONA. ATR/trend stops owned by the strategy are valid.\n\n"
                f"IMPORTANT: RESPOND ONLY WITH VALID JSON.\n"
                f"{SIGNAL_VALIDATION_JSON_SCHEMA}"
            )
        result = self._call_openrouter_api(prompt, system_prompt=system_prompt)

        result = self._parse_validation_payload(result or {})

        if result.get("raw_output") and result.get("rejection_reason_category") != "AI_PARSE_ERROR":
            # === CODE-LEVEL HARD CONSTRAINTS (Double-Check) ===
            result = self._enforce_hard_constraints(
                signal_data,
                result,
                risk_profile,
                market_context=ctx,
                strategy=strategy,
            )

            # --- LOGGING V2 IMPROVEMENTS ---
            is_approved = result.get("approved", False)
            conf = result.get("confidence", 0)
            reason = result.get("reasoning") or "No reasoning"
            factors = result.get("decisive_factors", [])
            reject_cat = result.get("rejection_reason_category")
            
            verdict = "APPROVED" if is_approved else "REJECTED"
            logger.info("AI VALIDATION %s: %s | Conf: %s%% | %s", verdict, symbol, conf, reason[:100])
            if factors:
                logger.info("  Key Factors: %s", ", ".join(factors[:3]))
            if not is_approved and reject_cat:
                logger.info("  Rejection Category: %s", reject_cat)

            self._set_cache(key, result, ttl_minutes=1)
        elif result.get("rejection_reason_category") == "AI_PARSE_ERROR":
            reason = result.get("reasoning", "AI_PARSE_ERROR")
            logger.info(
                "AI VALIDATION REJECTED: %s | Conf: 0%% | %s",
                symbol,
                str(reason)[:100],
            )

        return result

    def _enforce_hard_constraints(
        self,
        signal: Dict[str, Any],
        ai_result: Dict[str, Any],
        risk_profile: str,
        market_context: Optional[Dict[str, Any]] = None,
        strategy: Any = None,
    ) -> Dict[str, Any]:
        """
        Mechanically enforce capital R:R + strategy-owned geometry/volume.

        Strategy owns post_ai_adjust (e.g. swing trim) and optional volume floor.
        risk_profile supplies the account min_rr floor (+ strategy rr epsilon).
        """
        # Only check if AI approved the trade
        if not ai_result.get("approved"):
            return ai_result
            
        try:
            from app.core.prompts import RISK_PARAMS_MAP
            from app.core.veto_checker import LOW_VOLUME_RATIO_PCT
            
            ctx = market_context or {}

            # 0. Strategy-owned post-AI geometry (trim TP, etc.)
            if strategy is not None and hasattr(strategy, "post_ai_adjust"):
                try:
                    ai_result = strategy.post_ai_adjust(signal, ai_result, ctx) or ai_result
                except Exception as strat_err:
                    logger.debug("strategy.post_ai_adjust skipped: %s", strat_err)

            # 1. Check Risk:Reward (after any structural TP trim)
            entry = float(signal.get("price", 0))
            sl = float(ai_result.get("suggested_adjustments", {}).get("sl") or signal.get("sl", 0))
            tp = float(ai_result.get("suggested_adjustments", {}).get("tp") or signal.get("tp", 0))
            
            if entry > 0 and sl > 0 and tp > 0:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                
                if risk > 0:
                    rr_ratio = reward / risk
                    min_rr = RISK_PARAMS_MAP.get(risk_profile, {}).get("min_rr", 1.5)
                    rr_eps = 0.02
                    if strategy is not None and hasattr(strategy, "get_rr_epsilon"):
                        try:
                            rr_eps = float(strategy.get_rr_epsilon() or 0.02)
                        except (TypeError, ValueError):
                            rr_eps = 0.02
                    
                    if rr_ratio + rr_eps < float(min_rr):
                        logger.warning(
                            "[HARD CONSTRAINT] R:R Violation detected! Calculated: %.2f < Min: %s (eps=%.2f)",
                            rr_ratio, min_rr, rr_eps,
                        )
                        ai_result["approved"] = False
                        ai_result["rejection_reason_category"] = "BAD_RR"
                        ai_result["reasoning"] = (
                            f"CRITICAL: Calculated R:R ({rr_ratio:.2f}) is below minimum requirement "
                            f"({min_rr}) for {risk_profile}. Trade Rejected."
                        )
                        ai_result["risk_score"] = 9
                        return ai_result

            # 2. Weak volume — prefer strategy floor, else shared helper default
            vol_floor = float(LOW_VOLUME_RATIO_PCT)
            if strategy is not None and hasattr(strategy, "get_min_volume_ratio_pct"):
                try:
                    strat_floor = strategy.get_min_volume_ratio_pct()
                    if strat_floor is not None:
                        vol_floor = float(strat_floor)
                except (TypeError, ValueError):
                    pass

            vol_ratio = ctx.get("volume_ratio")
            if vol_ratio is None:
                cur = ctx.get("current_volume")
                avg = ctx.get("avg_volume")
                try:
                    if cur is not None and avg and float(avg) > 0:
                        vol_ratio = (float(cur) / float(avg)) * 100.0
                except (TypeError, ValueError):
                    vol_ratio = None
            try:
                if vol_ratio is not None and float(vol_ratio) < vol_floor:
                    logger.warning(
                        "[HARD CONSTRAINT] Weak volume %.1f%% < %.0f%%",
                        float(vol_ratio), vol_floor,
                    )
                    ai_result["approved"] = False
                    ai_result["rejection_reason_category"] = "WEAK_VOLUME"
                    ai_result["reasoning"] = (
                        f"CRITICAL: Volume ratio ({float(vol_ratio):.1f}% of average) is below "
                        f"minimum {vol_floor:.0f}%. Trade Rejected."
                    )
                    ai_result["risk_score"] = 8
            except (TypeError, ValueError):
                pass

        except Exception as e:
            logger.warning("Failed to verify hard constraints: %s", e)
            
        return ai_result
    
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
Respond ONLY with valid JSON. The 'reasoning' field must be in ENGLISH:
{{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "recommendation": "HOLD|TIGHTEN_SL|MOVE_TO_BREAKEVEN|TAKE_PROFIT|CLOSE_NOW",
  "reasoning": "2-3 sentence explanation in ENGLISH",
  "suggested_sl": null,
  "suggested_tp": null,
  "confidence": 75
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
            "summary": "Brief 1-sentence market summary in ENGLISH",
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

    def _rule_based_fallback(self, prompt: str) -> Dict[str, Any]:
        """
        Pure rule-based fallback when AI is unavailable (STORY-001).
        More intelligent conservative logic to avoid burning credits.
        """
        from app.core.prompts import RISK_PARAMS_MAP
        from app.core.config import config
        
        risk_profile = config.RISK_PROFILE or "Balanced Growth"
        params = RISK_PARAMS_MAP.get(risk_profile, RISK_PARAMS_MAP["Balanced Growth"])
        
        is_buy = any(word in prompt.upper() for word in ["BUY", "LONG"])
        is_sell = any(word in prompt.upper() for word in ["SELL", "SHORT"])
        
        # Default conservative fallback
        fallback = {
            "approved": False,
            "confidence": 35,
            "risk_score": 8,
            "reasoning": "Rule-based fallback (AI unavailable). Conservative mode enabled to protect capital.",
            "decisive_factors": ["AI offline", "Safety first"],
            "rejection_reason_category": "AI_UNAVAILABLE",
            "risk_level": "MEDIUM"
        }
        
        # Allow only high-quality setups during fallback
        if (is_buy or is_sell) and ("RSI" in prompt and "volume" in prompt.lower()) and ("strong" in prompt.lower() or "pullback" in prompt.lower()):
            fallback["approved"] = True
            fallback["confidence"] = 62
            fallback["risk_score"] = 4
            fallback["reasoning"] = "Rule-based APPROVAL: Clear trend + volume confirmation during AI outage."
            fallback["decisive_factors"] = ["Trend aligned", "Volume support", "Safe R:R assumed"]
            fallback["rejection_reason_category"] = None
            fallback["risk_level"] = "LOW"
        
        return {
            "raw_output": json.dumps(fallback),
            "model": "rule-based-fallback"
        }


# Global singleton instance
ia_service = IAService()
