# Contexte du Projet NovaBot

## 🎯 Vision
**Objectif :** Bot de trading passif générant 5-10% de rendement mensuel via des stratégies court-terme (5-15min).
**Utilisation :** Personnelle & Open Source.
**Philosophie :** "Consolider, Pérenniser, Automatiser". Éviter le "code spaghetti".

## 🏗 Architecture Technique (Hybride)
*   **Backend :** Python (FastAPI, Port 8001).
*   **Frontend :** Next.js 14 + Tailwind CSS (Port 8000 expected).
*   **Orchestration :** PM2 (`ecosystem.config.js`).
*   **IA :** OpenRouter (Llama 3.1 8B) pour validation des signaux.
*   **Plateforme :** Hyperliquid (DEX).

## 🧩 Protocoles & Features Clés
*   **Zero Repainting :** Décisions basées sur `iloc[-2]` (bougie clôturée).
*   **Funnel Strategy :** Filtre Régime (ADX) -> Setup -> Trigger.
*   **Atomic Position Tracking :** Récupération automatique des positions après crash.
*   **Internal Scanner :** Scanne les tokens, check Trend/Volume, note > 75 déclenche une opportunité.
*   **Mode Hybride :** Le bot gère le TP/SL des positions manuelles prises sur Hyperliquid.

## 🧠 Stratégies & Personas
Chaque stratégie possède un "Persona" IA dédié pour la validation.
*   `smart_trend.py` (Suivi de tendance)
*   `bollinger_bounce.py` (Rebond volatilité)
*   `elastic_reversion.py`
*   `institutional_scalp.py`
*   `scalp_ema_rsi.py`
*   `smart_mean_reversion.py`

## 📂 Structure Cible (à restaurer)
*   `/app` : Core Logic (Python package).
*   `/backend` : Serveur API.
*   `/strategies` : Implémentation des stratégies.
*   `/utils` : Helpers.
*   `/docs` : Documentation (Reference: `CONTEXT.md`).
*   *(Frontend introuvable pour l'instant)*

## 🛠 Tâches Prioritaires
1.  **Restructuration :** Sortir le code de `_legacy_backup`.
2.  **Frontend :** Localiser et reconnecter le Dashboard.
3.  **Fiabilisation :** Sécuriser la boucle d'exécution et les appels IA.
