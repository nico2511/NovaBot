---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments:
  - c:\Users\User\Desktop\novabot\_bmad-output\analysis\brainstorming-session-2026-01-13.md
  - c:\Users\User\Desktop\novabot\project-context.md
  - c:\Users\User\Desktop\novabot\_bmad-output\project_knowledge\index.md
date: 2026-01-13
author: Nicolas
---

# Product Brief: novabot

<!-- Content will be appended sequentially through collaborative workflow steps -->

## Executive Summary

NovaBot est un système de trading automatisé personnel conçu pour générer un revenu passif sur les marchés crypto (Hyperliquid). Il se distingue par son approche "intelligente" qui fusionne l'analyse technique traditionnelle avec une validation par Intelligence Artificielle (LLM), permettant une prise de position sélective et qualitative. L'objectif final est la fiabilité absolue et l'autonomie, transformant la volatilité du marché en croissance constante du capital sans intervention humaine quotidienne.

---

## Core Vision

### Problem Statement
Pour un investisseur individuel, le trading manuel est chronophage, émotionnellement épuisant et sujet à l'erreur humaine. La plupart des solutions automatisées (bots simples) manquent de nuances, exécutant aveuglément des signaux techniques même dans de mauvaises conditions de marché, ce qui rend la génération de revenus instable et stressante.

### Problem Impact
- **Charge Mentale** : Nécessité de surveiller le bot, annulant le bénéfice "passif".
- **Performance Irrégulière** : Gains effacés par des pertes stupides dues à un manque de contexte.
- **Occasions Manquées** : Incapacité à agir 24/7 avec la même précision.

### Why Existing Solutions Fall Short
- **Manque de Discernement** : Les bots standards suivent des règles rigides (If RSI > 70 then Sell) sans "comprendre" le marché.
- **Complexité de Gestion** : Souvent fragiles, nécessitant des redémarrages ou des ajustements fréquents.

### Proposed Solution
Un moteur de trading consolidé et autonome (Python/FastAPI) qui agit comme un trader expert virtuel :
1.  **Positions Intelligentes** : Filtre les signaux techniques par une analyse IA du contexte global.
2.  **Robustesse** : Architecture simplifiée et fiabilisée pour tourner sans surveillance.
3.  **Transparence** : Rapports clairs sur pourquoi un trade a été pris ou refusé.

### Key Differentiators
- **Cerveau Hybride** : La vitesse du code technique + le jugement du LLM.
- **Focus Personnel** : Optimisé pour votre capital et votre tolérance au risque, pas pour vendre des abonnements.

## Target Users

### Primary Users: "L'Investisseur Serein"
Propriétaire du projet, il cherche à faire fructifier son capital crypto existant sans que cela ne devienne un second travail. Il a une compréhension technique et financière, mais son temps est précieux.

- **Motivation** : Liberté financière et optimisation du temps.
- **Frustration Actuelle** : Devoir surveiller les courbes, l'incertitude des bots "boite noire", la peur de la liquidation pendant la nuit.
- **Vision du Succès** : Une simple notification ou un coup d'œil rapide le matin confirmant que "tout fonctionne" et que le capital a cru pendant son sommeil.

### Secondary Users
*N/A - Projet personnel à usage unique.*

### User Journey: "La Routine Café"
1.  **Réveil (07:30)** : Notification silencieuse reçue pendant la nuit : *"Daily Target Reached (+1.5%)"*.
2.  **Le Check (08:00)** : Ouverture du Dashboard sur mobile en buvant le café.
3.  **Validation** : Coup d'œil sur la courbe d'équité (verte), vérification rapide qu'aucune erreur rouge n'est présente.
4.  **Déconnexion (08:05)** : Fermeture de l'app. Journée normale qui commence, l'esprit libre.

## Success Metrics

### User Success: "La Sérénité par la Qualité"
Le succès n'est pas vu comme un casino, mais comme une machine de précision.
- **Indicateur de Confiance** : L'utilisateur ne ressent pas le besoin de vérifier le bot quand le marché crash.
- **Zéro "Bad Trades"** : Aucun trade pris "par erreur" ou "contre la tendance" (les pertes font partie du jeu, mais elles doivent être logiques).
- **Rationnel** : Chaque position doit être justifiable par l'IA (le "Pourquoi" est clair).

### Business Objectives
- **Capital Preservation** : Priorité absolue. Ne jamais mettre le capital en danger de ruine.
- **Croissance Régulière** : Viser une accumulation lente mais constante (Compounding).
- **Autonomie** : Tendre vers 0 intervention humaine sur la mécanique (Maintenance-free).

### Key Performance Indicators (KPIs)
1.  **Winrate > 65%** : On vise la majorité de trades gagnants pour le confort psychologique.
2.  **Profit Factor > 1.5** : Pour chaque dollar perdu, on en gagne au moins 1.5.
3.  **Drawdown < 10%** : On accepte une volatilité négative minimale.
4.  **Trades "IA-Validated" : 100%** : Aucune position sans 'green light' du LLM.

## MVP Scope

### Core Features (V1 Launch)
Le focus est sur la **consolidation** et l'**interface de contrôle**.
- **Trading Engine (Hyperliquid)** : Exécution des stratégies existantes (SmartTrend, Bollinger, etc.).
- **AI Validation Layer** : Filtrage de chaque signal par le LLM avant exécution.
- **Mobile Dashboard (Web App)** :
    - Vue "Morning Check" : PnL journalier/total, Equity Curve.
    - Contrôle d'Urgence : Bouton "Panic Sell" / "Stop Bot".
    - État du système : Indicateurs "Running/Stopped", Logs simplifiés.
- **Système de Notification** : Alertes Discord/Telegram en temps réel (Prises de position, PnL daily).
- **Gamification Basique** : XP et Niveaux basés sur la performance (déjà implémenté).

### Out of Scope for MVP
Tout ce qui n'est pas essentiel à la "Routine Café" est repoussé.
- **Backtesting GUI** : L'optimisation se fera via scripts/config, pas via une UI complexe.
- **Multi-Exchange** : Focus 100% Hyperliquid pour l'instant.
- **Social Features** : Pas de leaderboard public ou de copy-trading.
- **Gestion de Portefeuille Complexe** : Pas de gestion multi-wallet.

### MVP Success Criteria
- **Dashboard Fonctionnel** : Accessible depuis un mobile, temps de chargement < 2s.
- **Feedback Loop** : Chaque action du bot génère une notif claire.
- **Stabilité** : Le bot tourne 7j/7 sans crash nécessitant un SSH.

### Future Vision (V2+)
Une fois la confiance établie, évolution vers une "Flotte" de stratégies autonomes et une interface de "Mission Control" plus poussée permettant le fine-tuning des hyper-paramètres depuis le canapé.
