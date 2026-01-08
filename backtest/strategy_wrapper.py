"""
Strategy Wrapper pour Backtest
Gère correctement les indicateurs ta qui retournent des DataFrames
"""

import pandas as pd
from app.services.indicators import ta


class StrategyWrapper:
    """Wrapper qui corrige les indicateurs pour backtesting"""
    
    def __init__(self, strategy_instance):
        self.strategy = strategy_instance
    
    def add_indicators_safe(self, df):
        """
        Ajoute les indicateurs en gérant les retours multi-colonnes de ta
        """
        # Sauvegarder la méthode originale
        original_add_indicators = self.strategy.add_indicators
        
        # Appeler la méthode originale
        result = original_add_indicators(df)
        
        # Corriger les colonnes ADX si nécessaire
        if 'ADX_14' in df.columns and isinstance(df['ADX_14'].iloc[0], pd.Series):
            # ta.adx() retourne un DataFrame, extraire seulement la colonne ADX
            adx_result = ta.adx(df['high'], df['low'], df['close'], length=14)
            if isinstance(adx_result, pd.DataFrame) and 'ADX' in adx_result.columns:
                df['ADX_14'] = adx_result['ADX']
        
        # Corriger autres indicateurs multi-colonnes si nécessaire
        for col in df.columns:
            if isinstance(df[col].iloc[0] if len(df) > 0 else None, (pd.Series, pd.DataFrame)):
                # Supprimer colonne problématique
                df.drop(columns=[col], inplace=True, errors='ignore')
        
        return result
    
    def generate_signal(self, df):
        """Wrapper pour generate_signal"""
        return self.strategy.generate_signal(df)
