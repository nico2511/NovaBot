---
stepsCompleted: ['step-01-init', 'step-02-discovery', 'step-03-success', 'step-04-journeys', 'step-05-domain', 'step-06-innovation']
classification:
  projectType: 'web_app'
  domain: 'fintech'
  complexity: 'high'
  projectContext: 'brownfield'
inputDocuments:
  - c:\Users\User\Desktop\novabot\_bmad-output\planning-artifacts\product-brief-novabot-2026-01-13.md
  - c:\Users\User\Desktop\novabot\project-context.md
workflowType: 'prd'
---

# Product Requirements Document - Novabot

**Author:** Nicolas
**Date:** 2026-01-16

## Success Criteria

### User Success
- **The "Morning Coffee" Standard:** You wake up, check the dashboard in < 2s, see green, and start your day.
- **Trust:** You never feel the need to "double-check" the bot during a market crash.
- **Rationale:** 100% of trades have a clear "Why" explained by AI.

### Business Success
- **Yield:** 5-10% monthly growth.
- **Risk:** Drawdown < 10%.
- **Performance:** Winrate > 65%, Profit Factor > 1.5.
- **Goal:** Capital preservation + Compounding.

### Technical Success
- **Stability:** Runs 7/7 without manual SSH intervention.
- **Performance:** Dashboard loads per "Morning Check" requirements (< 2s).
- **Reliability:** Atomic Position Tracking recovers state after any crash.

### Measurable Outcomes
- **Winrate:** > 65%
- **Profit Factor:** > 1.5
- **Drawdown:** < 10%
- **Uptime:** 99.9% (implied by 7/7 stability)
- **AI Validation:** 100% of trades

## Product Scope

### MVP - Minimum Viable Product
- **Trading Engine:** Hyperliquid execution (Strategies: SmartTrend, Bollinger, etc.).
- **AI Layer:** DeepSeek v3.2 validation for *every* signal.
- **Mobile Dashboard:** "Morning Check" view (PnL, Equity), Panic Button, Logs.
- **Notifications:** Discord/Telegram for trades and Daily PnL.

### Growth Features (Post-MVP)
- **Backtesting GUI:** Optimization via scripts initially, UI later.
- **Multi-Exchange:** Focus 100% Hyperliquid for now.
- **Social Features:** Leaderboards or copy-trading.

### Vision (Future)
- **Fleet Management:** Multiple autonomous strategies.

## Parcours Utilisateurs (User Journeys)

### 👤 Persona Principal : "L'Investisseur Serein"
*Nicolas, propriétaire, veut de la rentabilité sans travail.*

#### Parcours 1 : La Routine "Café du Matin" (Scénario Idéal)
*   **Scène :** 07h30, au réveil. Notification sur le téléphone : *"Daily Target Reached (+1.5%)"*.
*   **Action :** Ouvre le dashboard en faisant couler le café.
*   **Expérience :** Le dashboard charge instantanément (<2s). Un gros chiffre vert confirme le PnL. Aucun badge rouge d'avertissement.
*   **Résolution :** Ferme l'app satisfait. Charge mentale : 0%. Confiance : 100%.

#### Parcours 2 : La Panique "Crash du Marché" (Cas Limite)
*   **Scène :** 14h00, Flash crash du Bitcoin de -10%. Twitter est en panique.
*   **Action :** Se précipite sur le dashboard pour vérifier l'exposition au risque.
*   **Expérience :** Le dashboard affiche "Positions Sécurisées. Bot en Pause (Haute Volatilité)." Le log IA explique : *"Changement de régime de marché détecté (ADX > 50). Tous les longs ont été fermés."*
*   **Résolution :** Grand soulagement. Le système a protégé le capital mieux qu'un humain n'aurait pu le faire.

### 🛠 Persona Secondaire : "L'Opérateur"
*Nicolas, ingénieur, a besoin de vérifier la santé du système.*

#### Parcours 3 : L'Audit du Week-end (Admin/Maintenance)
*   **Scène :** Dimanche après-midi, vérification de la performance hebdomadaire.
*   **Action :** Se connecte au dashboard, active les "Stats Détaillées".
*   **Expérience :** Examine les logs du "Pourquoi" pour un trade perdant. L'explication de l'IA est logique ("Invalidation du renversement de tendance"). Vérifie les logs de restauration d'état atomique — le système a auto-récupéré d'un redémarrage mardi.
*   **Résolution :** Confirme que la logique de la stratégie tient la route. Pas de changement de code nécessaire.

### Résumé des Exigences Révélées
*   **Interface Mobile-First :** Critique pour la Routine du Matin & la Vérification Panique.
*   **Notifications Push :** Déclencheur essentiel pour le parcours.
*   **Explicabilité IA :** Les logs du "Pourquoi" sont la clé de la Confiance dans le Parcours 3.
*   **Safety Switch (Interrupteur de Sécurité) :** Mécanisme de pause automatique vérifié dans le Parcours 2.

## Exigences du Domaine (Spécifique : Trading Algo Personnel)

### 🏛 Compliance & Régulation
*   **Contexte :** Projet strictement personnel. Aucune gestion de fonds tiers.
*   **Fiscalité :** Le système doit permettre une traçabilité simple pour le reporting fiscal (Flat Tax).

### 🔒 Contraintes Techniques
*   **Sécurité :** Clés API stockées en `.env` local uniquement. Pas de hardcoding.
*   **Continuité :** Protection contre les boucles d'ordres infinis (Safety Switch).
*   **Dépendances :** Surveillance de l'état de l'API Hyperliquid et OpenRouter.

### 🔗 Intégrations
*   **Hyperliquid :** Trading & Données de marché.
*   **OpenRouter :** Décisions IA.
*   **Discord/Telegram :** Notifications personnelles.

### ⚠️ Risques & Mitigations
*   **Bug Critique :** Perte de capital. -> Prévention : Hard Stop-Loss dans le code + Limites de position.
*   **Panne Réseau :** Perte de connexion. -> Prévention : Hébergement stable (VPS ou Local sécurisé).

## Innovation & Modèles Nouveaux

### Domaines d'Innovation Détectés
*   **Filtrage Hybride (Technique + Sémantique) :**
    *   *Concept :* L'analyse technique (RSI/Bollinger) propose, l'IA (DeepSeek) dispose.
    *   *Nouveauté :* Utilisation d'un LLM comme "Gatekeeper" de risque en temps réel, et non comme générateur de signaux. L'IA a un droit de Veto, pas un droit d'Initiative.
*   **Résilience "Stateless" (Atomic Tracking) :**
    *   *Concept :* Le bot n'a aucune "mémoire" critique locale. Il reconstruit sa réalité à chaque cycle en interrogeant l'exchange.
    *   *Avantage :* Immunité totale contre la corruption de base de données locale. Crash-proof.

### Mitigation des Risques (Spécifique Innovation)
*   **Hallucination IA :** Risque que l'IA valide un mauvais contexte.
    *   *Sécurité :* Le "Hard Veto" technique prévaut toujours (ex: Si RSI > 80, interdiction d'acheter, quel que soit l'avis de l'IA).
*   **Coût/Latence :** Appel API à chaque signal.
    *   *Optimisation :* Appel IA uniquement si le signal technique est déjà valide (Entonnoir).
