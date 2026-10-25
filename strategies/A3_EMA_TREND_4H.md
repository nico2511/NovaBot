# A3 — EMA-Trend 4H

Stratégie systématique **désactivée par défaut** (`enabled` / `active`: `false`), comme les autres plans après PR #33.

## Activer l’observation (Dry Run / paper)

1. Dans `data/config/strategies.json` (ou API stratégie) :
   - `"a3_ema_trend_4h": { "enabled": true, "active": true, ... }`
2. Laisser **`EXECUTION_MODE=Live`** ou **`Dry Run`** / **`paper`** dans `.env` :
   - **Dry Run / paper** : aucun ordre Hyperliquid (entrées bloquées dans `execute_entry_atomically`), même si `HL_PRIVATE_KEY` est définie.
   - **Live** : ordres réels via le moteur existant (activer seulement après validation papier).

3. Scanner : limiter la whitelist aux **18 coins** A3 (déjà listés dans `params.symbols` ; le hard veto bloque le reste).

4. Métriques papier : `GET /api/strategy/a3-ema-trend-4h/paper-metrics` (clé API si requise).

Critères d’arrêt (spec analyste) exposés dans la réponse :
- DD composé papier > 20 %
- PF < 1,0 après ≥ 150 trades clos journalisés
- Slippage moyen > 0,1 % par côté (si renseigné sur les closes)

## Passage live (micro)

1. Confirmer les métriques papier / dry-run sur ≥ 150 trades simulés ou journalisés.
2. `enabled` + `active` true, `EXECUTION_MODE=Live`, `trading_enabled` true.
3. **Ne pas** modifier les paramètres de risque global (`user_settings.json` / `risk_defaults`) — A3 utilise le profil **`Balanced Growth`** (3,5 % budget risque portfolio, levier max 5× selon résolution bot), découpé par `max_positions`.
4. Le stop **4×ATR** est large → le moteur `calculate_position_size(risk_pct)` produit des **tailles plus petites** qu’avec un stop serré ; les trades sous le minimum HL peuvent être **refusés** par `RiskManager` (pas d’agrandissement).

## Écarts vs spec backtest

| Spec backtest | NovaBot |
|---------------|---------|
| Risque fixe 0,25 % / trade | Profil capital + `max_positions` (ex. Balanced 3,5 % ÷ N) |
| Levier implicite ≤ 2,4× brut | Levier résolu par profil / compte |
| Pas de couche IA | `skip_ai_validation: true` (pas d’appel OpenRouter) |
| Sortie trailing + croisement inverse | `manage_trade` + `evaluate_trade_thesis` |
| Entrée open i+1 | Prix = open bougie 4H formante |
