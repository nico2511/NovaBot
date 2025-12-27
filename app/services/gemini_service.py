import google.generativeai as genai
from app.core.config import config
import threading
import json
from datetime import datetime

class GeminiService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.models_to_try = [
                'gemini-2.0-flash-lite-preview-02-05',
                'gemini-2.0-flash', 
                'gemini-flash-latest',
                'gemini-pro'
            ]
        else:
            self.models_to_try = []
        
        # Cache pour éviter trop d'appels API
        self.last_market_analysis = None
        self.last_market_analysis_time = None

    def _call_gemini(self, prompt: str) -> dict:
        """Méthode interne pour appeler Gemini avec gestion d'erreurs"""
        if not self.api_key:
            return {"error": "API Key missing"}
        
        last_error = ""
        
        for model_name in self.models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                # Cleanup potential markdown fencing
                clean_text = response.text.replace("```json", "").replace("```", "").strip()
                return {"raw_output": clean_text, "model": model_name}
            except Exception as e:
                error_msg = str(e)
                print(f"⚠️ Model {model_name} failed: {error_msg}")
                last_error = error_msg
                if "429" in error_msg:
                    continue
        
        if "429" in last_error or "quota" in last_error.lower():
            return {"raw_output": "{\"summary\": \"⚠️ Limite d'IA atteinte (Quota Free). Réessayez plus tard.\", \"error\": \"quota_exceeded\"}"}
            
        return {"raw_output": f"{{\"error\": \"{last_error}\"}}"}

    def analyze_market(self, market_data: dict) -> dict:
        """
        Sends market metrics to Gemini and asks for a structured analysis.
        Returns a dict with 'risk_level', 'trend', 'summary'.
        """
        if not self.api_key:
            return {"risk_level": "UNKNOWN", "trend": "UNKNOWN", "summary": "API Key missing"}

        prompt = f"""
        Agis comme un expert Quant Trader Crypto. Analyse les indicateurs suivants pour {market_data.get('symbol', 'Inconnu')}:
        
        Données:
        {market_data}
        
        Réponds UNIQUEMENT avec un objet JSON valide (sans markdown) contenant:
        - risk_level: (LOW, MEDIUM, HIGH)
        - trend: (BULLISH, BEARISH, NEUTRAL, RANGE)
        - summary: Une analyse de 2 phrases en FRANÇAIS sur la structure du marché.
        - reasoning: Une liste de 3 facteurs clés (en FRANÇAIS).
        """
        
        return self._call_gemini(prompt)
    
    def analyze_trade_signal(self, signal_data: dict, market_context: dict = None) -> dict:
        """
        Analyse un signal de trading et explique pourquoi il a été généré.
        
        Args:
            signal_data: Dict avec {signal, price, sl, tp, strategy, comment}
            market_context: Dict optionnel avec indicateurs du marché
            
        Returns:
            Dict avec {explanation, confidence, risks, recommendation}
        """
        if not self.api_key:
            return {"explanation": "IA non disponible", "confidence": "UNKNOWN"}
        
        context_str = f"\n\nContexte marché:\n{json.dumps(market_context, indent=2)}" if market_context else ""
        
        prompt = f"""
        Tu es un expert trader crypto. Analyse ce signal de trading et explique-le de manière claire.
        
        Signal:
        - Action: {signal_data.get('signal', 'UNKNOWN')}
        - Prix: {signal_data.get('price', 0)}
        - Stop Loss: {signal_data.get('sl', 0)}
        - Take Profit: {signal_data.get('tp', 0)}
        - Stratégie: {signal_data.get('strategy', 'Unknown')}
        - Commentaire: {signal_data.get('comment', 'N/A')}
        {context_str}
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        - explanation: Explication claire en 2-3 phrases en FRANÇAIS de pourquoi ce signal a été généré
        - confidence: Niveau de confiance (HIGH, MEDIUM, LOW)
        - risks: Liste de 2-3 risques potentiels
        - recommendation: Recommandation courte (ex: "Signal solide, respecter le SL")
        - risk_reward: Ratio risque/récompense calculé
        """
        
        return self._call_gemini(prompt)
    
    def analyze_market_evolution(self, current_data: dict, previous_data: dict = None) -> dict:
        """
        Compare l'état actuel du marché avec l'état précédent et détecte les changements.
        
        Args:
            current_data: Données actuelles du marché
            previous_data: Données précédentes (optionnel)
            
        Returns:
            Dict avec {changes, implications, alert_level}
        """
        if not self.api_key:
            return {"changes": "IA non disponible", "alert_level": "NONE"}
        
        prev_str = ""
        if previous_data:
            prev_str = f"\n\nÉtat précédent (il y a 15 min):\n{json.dumps(previous_data, indent=2)}"
        
        prompt = f"""
        Tu es un analyste de marché crypto. Compare l'état actuel du marché avec l'état précédent.
        
        État actuel:
        {json.dumps(current_data, indent=2)}
        {prev_str}
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        - changes: Liste de 2-3 changements importants détectés (en FRANÇAIS)
        - implications: Ce que ces changements signifient pour le trading
        - alert_level: Niveau d'alerte (CRITICAL, HIGH, MEDIUM, LOW, NONE)
        - trend_shift: true/false si changement de tendance détecté
        - summary: Résumé en 1 phrase
        """
        
        result = self._call_gemini(prompt)
        
        # Mettre en cache
        self.last_market_analysis = result
        self.last_market_analysis_time = datetime.now()
        
        return result
    
    def analyze_indicators(self, indicators_dict: dict) -> dict:
        """
        Analyse les indicateurs techniques et explique ce qu'ils signifient.
        
        Args:
            indicators_dict: Dict avec les indicateurs (RSI, ADX, EMA, etc.)
            
        Returns:
            Dict avec {interpretations, overall_signal, key_points}
        """
        if not self.api_key:
            return {"overall_signal": "NEUTRAL", "key_points": ["IA non disponible"]}
        
        prompt = f"""
        Tu es un expert en analyse technique crypto. Explique ces indicateurs en langage simple.
        
        Indicateurs:
        {json.dumps(indicators_dict, indent=2)}
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        - interpretations: Dict avec explication de chaque indicateur clé en FRANÇAIS
        - overall_signal: Signal global (BULLISH, BEARISH, NEUTRAL)
        - key_points: Liste de 3 points clés à retenir
        - divergences: Divergences détectées entre indicateurs (si applicable)
        """
        
        return self._call_gemini(prompt)
    
    def analyze_active_position(self, position_data: dict, current_market: dict) -> dict:
        """
        Analyse une position active et fournit des recommandations.
        
        Args:
            position_data: Dict avec {symbol, side, entry, sl, tp, strategy}
            current_market: État actuel du marché
            
        Returns:
            Dict avec {status, recommendations, risk_level, actions}
        """
        if not self.api_key:
            return {"status": "IA non disponible", "risk_level": "UNKNOWN"}
        
        # Calculer le PnL actuel
        current_price = current_market.get('price', position_data.get('entry', 0))
        entry = position_data.get('entry', 0)
        side = position_data.get('side', 'BUY')
        
        if side == 'BUY':
            pnl_pct = ((current_price - entry) / entry) * 100
        else:
            pnl_pct = ((entry - current_price) / entry) * 100
        
        prompt = f"""
        Tu es un gestionnaire de risque crypto. Analyse cette position active.
        
        Position:
        - Symbole: {position_data.get('symbol', 'Unknown')}
        - Côté: {side}
        - Prix d'entrée: {entry}
        - Stop Loss: {position_data.get('sl', 0)}
        - Take Profit: {position_data.get('tp', 0)}
        - Stratégie: {position_data.get('strategy', 'Unknown')}
        - PnL actuel: {pnl_pct:.2f}%
        
        Marché actuel:
        {json.dumps(current_market, indent=2)}
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        - status: Statut de la position (WINNING, LOSING, BREAK_EVEN, AT_RISK)
        - recommendations: Liste de 2-3 recommandations en FRANÇAIS
        - risk_level: Niveau de risque actuel (LOW, MEDIUM, HIGH, CRITICAL)
        - actions: Actions suggérées (HOLD, ADJUST_SL, TAKE_PARTIAL_PROFIT, CLOSE)
        - reasoning: Explication courte de l'analyse
        """
        
        return self._call_gemini(prompt)
    
    def generate_market_commentary(self, full_context: dict) -> dict:
        """
        Génère un commentaire complet et narratif du marché.
        
        Args:
            full_context: Dict complet avec marché, indicateurs, positions, etc.
            
        Returns:
            Dict avec {commentary, sentiment, outlook}
        """
        if not self.api_key:
            return {"commentary": "IA non disponible", "sentiment": "NEUTRAL"}
        
        prompt = f"""
        Tu es un analyste crypto professionnel. Rédige un commentaire de marché complet et engageant.
        
        Contexte complet:
        {json.dumps(full_context, indent=2)}
        
        Réponds UNIQUEMENT avec un JSON valide (sans markdown) contenant:
        - commentary: Commentaire narratif de 4-5 phrases en FRANÇAIS, style professionnel mais accessible
        - sentiment: Sentiment global (VERY_BULLISH, BULLISH, NEUTRAL, BEARISH, VERY_BEARISH)
        - outlook: Perspectives court terme (1 phrase)
        - key_levels: Niveaux de prix clés à surveiller
        - timeframe: Horizon temporel de l'analyse (SHORT_TERM, MEDIUM_TERM, LONG_TERM)
        """
        
        return self._call_gemini(prompt)

gemini_service = GeminiService()
