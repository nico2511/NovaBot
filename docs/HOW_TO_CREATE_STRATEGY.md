# 🏗️ Guide de Création de Stratégie (Standard 2026)

Ce guide explique comment ajouter une nouvelle stratégie au NovaBot en respectant l'architecture "Entonnoir" (Funnel) et les standards de code actuels.

## 📐 Philosophie : L'Entonnoir (The Funnel)

Chaque stratégie doit valider 3 étapes successives pour générer un signal. Si une étape échoue, on arrête tout immédiatement (`return None`).

1.  **Régime de Marché (The Gatekeeper)** :
    *   Le marché est-il favorable à ma stratégie ?
    *   *Exemple Trend* : `ADX > 25`
    *   *Exemple Range* : `ADX < 25` et `Hauteur Range > 0.5%`
2.  **Le Setup (The Pattern)** :
    *   La configuration technique est-elle présente ?
    *   *Exemple* : Prix touche la Bollinger Basse, ou RSI en survente.
3.  **Le Trigger (The Trigger)** :
    *   L'événement précis qui déclenche l'entrée.
    *   *Exemple* : Bougie verte de rejet, croisement EMA, cassure de niveau.

---

## 1. Créer le fichier Python

Créez un fichier dans `strategies/` (ex: `strategies/ma_strategie.py`).
Utilisez ce modèle basé sur `bollinger_bounce.py`.

```python
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from strategies.base import BaseStrategy
from app.services.indicators import ta

class MaStrategie(BaseStrategy):
    """
    Description courte de la stratégie.
    """
    
    # ==========================================
    # 🧠 PERSONA IA : L'ÂME DE LA STRATÉGIE
    # ==========================================
    # Ce texte est envoyé à l'IA pour qu'elle "incarne" la stratégie lors de l'analyse.
    AI_PERSONA = """
    CODENAME: "NOM DE CODE (Ex: SNIPER)"
    
    ROLE:
    Décris ici le rôle de la stratégie. Es-tu prudent ? Agressif ? Contre-tendance ?
    
    PRIME DIRECTIVE:
    Ta règle absolue. Ex: "Je ne trade que si le volume confirme le mouvement."
    
    RULES OF ENGAGEMENT:
    1. Règle 1 (Ex: ADX doit être faible)
    2. Règle 2 (Ex: Rejet net sur support)
    3. Règle 3
    
    RESPONSE STYLE:
    Ton ton. Ex: "Froid, précis, militaire." ou "Sarcastique et prudent."
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        # Charger les paramètres depuis strategies.json (avec valeurs par défaut)
        self.mon_parametre = self.params.get("mon_parametre", 14)
        self.stop_loss_atr = self.params.get("stop_loss_atr", 1.5)
        self.min_rr = self.params.get("min_rr", 1.5)
    
    def generate_signal(self, df: pd.DataFrame, extra_data=None) -> Optional[Dict]:
        """
        La logique de trading (L'Entonnoir).
        """
        if df is None or df.empty or len(df) < 50:
            return None
        
        try:
            # === ÉTAPE 1 : RÉGIME (Gatekeeper) ===
            adx_series = ta.adx(df['high'], df['low'], df['close'], length=14)
            current_adx = adx_series['ADX'].iloc[-2] # Toujours utiliser bougie clôturée (-2) ou (-1 selon logique)
            
            # Exemple : On veut du Trend
            if current_adx < 25:
                # Régime invalide, on arrête.
                return None
            
            # === ÉTAPE 2 : SETUP & INDICATEURS ===
            # Calculer les indicateurs nécessaires
            rsi = ta.rsi(df['close'], length=14).iloc[-1]
            atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            close = df['close'].iloc[-1]
            
            # === ÉTAPE 3 : TRIGGER ===
            signal = None
            
            # Logique d'achat
            if rsi < 30: # Condition simple pour l'exemple
                
                # Calcul SL / TP
                sl = close - (atr * self.stop_loss_atr)
                tp = close + (atr * self.stop_loss_atr * self.min_rr)
                
                return {
                    "signal": "BUY",
                    "sl": sl,
                    "tp": tp,
                    "comment": f"RSI Oversold ({rsi:.1f})"
                }
                
            return None
            
        except Exception as e:
            print(f"Erreur dans MaStrategie: {e}")
            return None

    # --- MÉTHODES POUR L'INTERFACE GRAPHIQUE (DASHBOARD) ---

    def calculate_progress(self, df: pd.DataFrame, extra_data=None) -> int:
        """Barre de progression (0-100%) pour l'UI"""
        # Logique pour montrer à quel point on est proche d'un trade
        return 0 

    def check_conditions(self, df: pd.DataFrame, extra_data=None) -> List[Dict]:
        """Retourne l'état des conditions pour la Diagnostic Card"""
        conditions = []
        # Exemple : 
        # conditions.append({"name": "ADX Trend", "status": True, "value": "35.2"})
        return conditions
        
    def get_threshold_comparisons(self, df: pd.DataFrame, extra_data=None) -> Dict:
        """Retourne les valeurs précises pour l'onglet Paramètres"""
        # Exemple :
        # return {"RSI": f"{current_rsi:.1f} (Seuil: 30)"}
        return {}
```

---

## 2. Ajouter la configuration JSON

Ouvrez `strategies.json` et ajoutez votre bloc dans l'objet `"strategies"`.
Le nom de la clé (ex: `ma_strategie`) doit être unique.

```json
"ma_strategie": {
    "enabled": true,
    "type": "trend", 
    "description": "Expliquez ce que ça fait ici.",
    "active_timeframes": ["15m"],
    "display_conditions": [
        "Régime ADX (>25)",
        "RSI Oversold (<30)"
    ],
    "params": {
        "execution_type": "auto",
        "allow_longs": true,
        "allow_shorts": true,
        "mon_parametre": 14,
        "stop_loss_atr": 1.5,
        "min_rr": 2.0
    }
}
```

*   **type**: `trend`, `range`, `reversion` (utilisé par le bot pour filtrer selon le régime global).
*   **display_conditions**: Liste de textes affichés dans l'UI.

---

## 3. Enregistrer dans le moteur

Dernière étape indispensable : dire au bot que ce fichier existe.
Allez dans `strategies/engine.py`.

1.  **Import** :
    ```python
    from strategies.ma_strategie import MaStrategie
    ```

2.  **Instanciation** (dans `__init__`) :
    ```python
    self.strategies = {
        # ... autres stratégies
        "ma_strategie": MaStrategie(strats_config.get("ma_strategie")),
    }
    ```

C'est tout ! Au prochain redémarrage (`pm2 restart all`), votre stratégie sera chargée, visible dans le dashboard, et active.

---

## 🤖 Prompt pour générer une stratégie par IA

Copiez-collez le prompt ci-dessous dans votre assistant IA (ChatGPT, Claude, etc.) pour qu'il génère une stratégie conforme à ce guide.

> **Prompt :**
>
> "Agis en tant qu'expert Python en trading algorithmique. Lis attentivement le fichier `docs/HOW_TO_CREATE_STRATEGY.md` ci-dessus (ou utilise les règles suivantes : Architecture Entonnoir, Classe `BaseStrategy`, Persona IA, Config JSON).
>
> Je veux que tu crées une nouvelle stratégie nommée **[NOM_DE_LA_STRATEGIE]**.
>
> **Logique de la stratégie :**
> 1.  **Régime (Gatekeeper)** : [Ex: Tendance Hausière définie par EMA20 > EMA50 et ADX > 25]
> 2.  **Setup (Pattern)** : [Ex: Pullback sur la EMA20 avec RSI < 40]
> 3.  **Trigger (Entrée)** : [Ex: Clôture de bougie verte englobante]
>
> **Tâche :**
> 1.  Écris le code Python complet pour le fichier `strategies/[nom_fichier].py`. N'oublie pas la classe `AI_PERSONA` et les imports.
> 2.  Fournis le bloc de configuration JSON à ajouter dans `strategies.json`.
> 3.  Indique la ligne d'import à ajouter dans `strategies/engine.py`.
>
> Sois rigoureux sur le typage et la gestion des erreurs (`try/except`)."
