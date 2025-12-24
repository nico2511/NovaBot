import google.generativeai as genai
from app.core.config import config
import threading

class GeminiService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if self.api_key:
            self.models_to_try = [
                'gemini-2.0-flash-lite-preview-02-05',
                'gemini-2.0-flash', 
                'gemini-flash-latest',
                'gemini-pro'
            ]
        else:
            self.models_to_try = []

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
            return {"raw_output": "{\"summary\": \"⚠️ Limite d'IA atteinte (Quota Free). Réessayez plus tard.\", \"risk_level\": \"UNKNOWN\"}"}
            
        return {"raw_output": f"{{\"error\": \"{last_error}\"}}"}

gemini_service = GeminiService()
