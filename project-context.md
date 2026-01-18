# Contexte du Projet NovaBot
**Mise à jour Architecture :** 2026-01-17 (Post-Review)

## 🎯 Vision & Principes
*   **Objectif :** Bot de trading passif (5-10% retour mensuel) via stratégies court-terme.
*   **Philosophie :** "Consolider, Pérenniser, Automatiser".
*   **Règle d'Or (Code) :** "Silence is Golden" - Gestion des erreurs robuste, pas de crash pour des détails.
*   **Règle d'Or (Architecture) :** **IMMUTABLE BACKEND**. On ne touche pas au moteur Python qui fonctionne.

## 🛑 Directives d'Implémentation (CRITIQUE)
Tous les agents IA doivent respecter ces contraintes absolues :

1.  **Back-end Immuable :**
    *   Les dossiers `app/`, `backend/`, `strategies/` sont considérés **READ-ONLY**.
    *   Interdiction de refactorer le code Python existant pour "faire propre".
    *   Seule exception : Ajout d'endpoints API dans `backend/` si strictement nécessaire pour exposer une donnée existante.

2.  **Frontend "Sidecar" :**
    *   Tout le développement UI se fait dans `frontend-v3/` (Next.js 14).
    *   Le Frontend considère le Backend comme une API externe (Black Box).
    *   Pas de "Business Logic" complexe dans le Frontend (juste de la visualisation et des commandes).

3.  **Intégration "Loosely Coupled" :**
    *   Communication via **API REST Polling** (1s) sur `localhost:8001`.
    *   Pas d'Authentification requise (Contexte Localhost/VPN).
    *   Le Frontend ne possède PAS l'état. Il reflète l'état du Backend (`bot_state.json`).

## 🏗 Architecture Technique
*   **Stack Hybride :**
    *   **Backend (Legacy) :** Python 3.10+, FastAPI, StateManager (Atomic JSON).
    *   **Frontend (New) :** Next.js 14, Tailwind CSS, Shadcn/UI.
    *   **Orchestration :** PM2 (`ecosystem.config.js` gère les 2 processus).

*   **Flux de Données :**
    *   `Bot` (Python) -> écrit -> `bot_state.json`.
    *   `API` (FastAPI) -> lit -> `bot_state.json`.
    *   `Frontend` (Next.js) -> poll -> `GET /api/status`.

## 🧩 Protocoles Clés
*   **Zero Repainting :** `iloc[-2]` uniquement.
*   **Atomic Position Tracking :** Le bot doit pouvoir redémarrer à tout moment et retrouver ses positions via Hyperliquid API + `bot_state.json`.
*   **Hard Veto IA :** DeepSeek v3.2 valide *tous* les signaux avant exécution.

## 📁 Structure du Projet
```
novabot/
├── app/               # 🔒 [IMMUTABLE] Core Logic Python
├── backend/           # 🔒 [IMMUTABLE] API Server
├── strategies/        # 🔒 [IMMUTABLE] Trading Strategies
├── frontend-v3/       # ⭐ [DEV ZONE] Next.js PWA
│   ├── app/           # Pages & Routes
│   ├── components/    # UI (Shadcn) & Widgets
│   └── lib/api/       # Clients API (Typescript interfaces mirroring Python)
└── ecosystem.config.js # Config de lancement unifié
```

## 🛠 Commandes Utiles
*   **Lancer tout :** `pm2 start ecosystem.config.js`
*   **Dev Frontend :** `cd frontend-v3 && npm run dev`
*   **Logs Backend :** `pm2 logs bot-engine`
