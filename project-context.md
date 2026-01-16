# Contexte du Projet NovaBot

## 🎯 Vision
**Objectif :** Bot de trading passif générant 5-10% de rendement mensuel via des stratégies court-terme (5-15min).
**Utilisation :** Personnelle & Open Source.
**Philosophie :** "Consolider, Pérenniser, Automatiser". Éviter le "code spaghetti".

## 🏗 Architecture Technique (Hybride)
*   **Backend :** Python (FastAPI, Port 8001).
*   **Frontend :** Next.js 14 + Tailwind CSS (Port 8000 expected).
*   **Orchestration :** PM2 (`ecosystem.config.js`).
*   **IA :** OpenRouter (DeepSeek v3.2) pour validation des signaux.
*   **Plateforme :** Hyperliquid (DEX).

## 🧩 Protocoles & Features Clés
*   **Zero Repainting :** Décisions basées sur `iloc[-2]` (bougie clôturée).
*   **Funnel Strategy :** Filtre Régime (ADX) -> Setup -> Trigger.
*   **Atomic Position Tracking :** Récupération automatique des positions après crash.
*   **Internal Scanner :** Scanne les tokens, check Trend/Volume, note > 75 déclenche une opportunité.
*   **Mode Hybride :** Le bot gère le TP/SL des positions manuelles prises sur Hyperliquid.
*   **Symbol Resolver :** Résolution automatique des symboles (ex: `PEPE` -> `kPEPE`). Case-insensitive.
*   **Strategy-Level Trade Management :** Hook `manage_trade()` dans `BaseStrategy` pour trailing SL personnalisé.

## 🧠 Stratégies & Personas
Chaque stratégie possède un "Persona" IA dédié pour la validation.
*   `smart_trend.py` (Suivi de tendance)
*   `bollinger_bounce.py` (Rebond volatilité)
*   `elastic_reversion.py`
*   `institutional_scalp.py`
*   `scalp_ema_rsi.py`
*   `smart_mean_reversion.py`
*   `elastic_nibbler.py` (**NEW** - Reversion Scalp BTC avec trailing SL custom)

## 🛠 API Endpoints Clés
*   `POST /api/engine/start` - Démarrer le bot
*   `POST /api/engine/stop` - Arrêter le bot
*   `POST /api/engine/restart` - Redémarrer le bot (Stop + Start)
*   `POST /api/trading/enable` - Activer le trading live
*   `POST /api/trading/disable` - Désactiver le trading live
*   `POST /api/switch_symbol` - Changer le symbole actif

## � Structure Cible
*   `/app` : Core Logic (Python package).
*   `/backend` : Serveur API.
*   `/strategies` : Implémentation des stratégies.
*   `/frontend-v3` : Dashboard Next.js.
*   `/docs` : Documentation (Reference: `CONTEXT.md`).

