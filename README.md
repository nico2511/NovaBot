# NovaBot

> 🤖 **Bot de Trading Algorithmique Hybride (Python/Hyperliquid)**

## 📌 Vue d'ensemble
NovaBot est un bot de trading conçu pour générer un revenu passif via des stratégies court-terme sur Hyperliquid. Il combine une exécution algorithmique rigoureuse avec une validation par IA (LLM).

Pour une vision détaillée du projet, voir [project-context.md](./project-context.md).
Pour la documentation technique historique, voir [docs/CONTEXT.md](./docs/CONTEXT.md).

## 📂 Structure du Projet
- **`/app`** : Cœur logique (Engine, Services).
- **`/backend`** : Serveur API (FastAPI) pour l'interface de gestion.
- **`/strategies`** : Implémentation des stratégies de trading.
- **`/utils`** : Fonctions utilitaires partagées.
- **`/data`** : Données locales.
- **`/docs`** : Documentation du projet.

## 🚀 Démarrage Rapide
```bash
# Lancer le bot (Backend + Engine)
./start_integrated.sh
```

## 🛠 Commandes Utiles
*   **Lancer les tests** : `pytest ./tests` (à configurer)
*   **Vérifier les logs** : `pm2 logs`
