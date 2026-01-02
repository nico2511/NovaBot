# 🧪 Backtest Engine - Guide d'Utilisation

## 📋 Vue d'Ensemble

Le Backtest Engine permet de **tester vos stratégies sur des données historiques** sans risquer d'argent réel. Il utilise le **code exact du bot** (StrategyEngine, RiskManager) dans un environnement isolé.

### Architecture

```
backtest/
├── mock_exchange.py       # Faux Hyperliquid (pas d'API réelle)
├── backtest_engine.py     # Moteur de simulation temporelle
└── __init__.py

backtest_launcher.py       # Script principal
scripts/
└── download_historical_data.py  # Téléchargement de données

data/
└── historical/
    └── BTC_15m.csv        # Données historiques
```

---

## 🚀 Utilisation Rapide

### Étape 1: Télécharger les Données

```bash
# Télécharger 90 jours de BTC 15m
python scripts/download_historical_data.py --symbol BTC --interval 15m --days 90

# Autres exemples
python scripts/download_historical_data.py --symbol ETH --interval 1h --days 60
python scripts/download_historical_data.py --symbol SOL --interval 15m --days 30
```

### Étape 2: Lancer le Backtest

```bash
python backtest_launcher.py
```

### Résultat Attendu

```
====================================================================
🧪 BACKTEST LAUNCHER - Strategy Validation
====================================================================
📂 Loading data from data/historical/BTC_15m.csv...
📊 Backtest: 8640 candles loaded
📅 Period: 2025-10-01 00:00:00 → 2026-01-01 00:00:00
💰 Initial Balance: $1000.00
====================================================================
[2025-10-05 14:30:00] 🚀 BUY 0.0021 BTC @ $47850.00
[2025-10-06 08:15:00] ✅ TP HIT - Closed @ $48200.00
[2025-10-12 16:45:00] 🚀 SELL 0.0019 BTC @ $46500.00
...
====================================================================
📈 BACKTEST RESULTS
====================================================================
Initial Balance: $1000.00
Final Balance:   $1245.30
Total PnL:       $245.30
Total Fees:      $12.50
ROI:             +24.53%
--------------------------------------------------------------------
Total Trades:    45
Winning:         28 (62.2%)
Losing:          17
Avg Win:         $15.20
Avg Loss:        -$8.50
Profit Factor:   2.14
====================================================================
✅ STRATEGY PROFITABLE
```

---

## 🔧 Fonctionnalités

### 1. MockExchange (Le Leurre)

Simule Hyperliquid **sans appeler l'API réelle**:

```python
from backtest.mock_exchange import MockExchange

exchange = MockExchange(initial_balance=1000.0)

# Compatible avec hyperliquid_service
balance = exchange.get_account_balance()
# → {"status": "success", "equity": 1000.0}

exchange.execute_order(
    symbol="BTC",
    is_buy=True,
    size=0.01,
    sl_price=45000,
    tp_price=50000
)
```

**Méthodes Disponibles:**
- `get_account_balance()` - Solde virtuel
- `get_positions()` - Positions ouvertes
- `execute_order()` - Exécuter un ordre
- `close_position()` - Fermer une position
- `check_stops()` - Vérifier SL/TP
- `get_stats()` - Statistiques du backtest

### 2. BacktestEngine (La Machine à Remonter le Temps)

Simule le passage du temps **bougie par bougie**:

```python
from backtest.backtest_engine import BacktestEngine

engine = BacktestEngine(initial_balance=1000.0)

stats = engine.run(
    data_csv_path="data/historical/BTC_15m.csv",
    strategy_func=my_strategy,
    symbol="BTC",
    warmup_candles=50  # Bougies nécessaires pour indicateurs
)
```

**Protection Anti-Lookahead:**
- À chaque itération `i`, la stratégie ne voit QUE `df[0:i]`
- Impossible de "voir le futur"
- SL/TP vérifiés avec `high`/`low` de la bougie

### 3. Strategy Wrapper

Utilise le **vrai code du bot**:

```python
def strategy_wrapper(df_slice, exchange, symbol):
    # Utilise le VRAI StrategyEngine
    risk_manager = RiskManager()
    engine = StrategyEngine(risk_manager)
    
    # Analyse avec les vraies stratégies
    result = engine.analyze(df_slice)
    
    if result.get('signals'):
        signal = result['signals'][0]
        
        # Calcul de taille avec RiskManager
        size = risk_manager.calculate_position_size(
            price=signal['price'],
            sl_price=signal['sl'],
            equity=exchange.balance,
            method="risk_pct",
            risk_per_trade_pct=0.01
        )
        
        return {
            "symbol": symbol,
            "side": signal['signal'],
            "size": size,
            "sl": signal['sl'],
            "tp": signal['tp']
        }
    
    return None
```

---

## 📊 Métriques Calculées

Le backtest calcule automatiquement:

- **ROI (%)** - Retour sur investissement
- **Total PnL** - Profit/Perte total
- **Win Rate** - Taux de réussite
- **Avg Win/Loss** - Gain/Perte moyen
- **Profit Factor** - (Total Wins) / (Total Losses)
- **Total Fees** - Frais cumulés (0.05% par défaut)

---

## ⚙️ Configuration Avancée

### Modifier le Risque par Trade

Éditer `backtest_launcher.py`:

```python
size = risk_manager.calculate_position_size(
    price=signal['price'],
    sl_price=signal['sl'],
    equity=equity,
    method="risk_pct",
    risk_per_trade_pct=0.02  # 2% au lieu de 1%
)
```

### Tester une Stratégie Spécifique

```python
# Dans strategy_wrapper
result = engine.analyze(df_slice)

# Filtrer par stratégie
if result.get('signals'):
    for signal in result['signals']:
        if signal['strategy'] == 'ScalpEmaRsi':  # Tester seulement ScalpEmaRsi
            # ...
```

### Changer les Frais

```python
engine = BacktestEngine(initial_balance=1000.0)
engine.exchange.fees_pct = 0.001  # 0.1% au lieu de 0.05%
```

---

## 🐛 Troubleshooting

### Erreur: "Data file not found"

```bash
# Télécharger les données
python scripts/download_historical_data.py
```

### Erreur: "No candle set"

Le MockExchange n'a pas de bougie actuelle. Vérifier que `engine.run()` est appelé correctement.

### Stratégie ne génère aucun signal

- Vérifier que les stratégies sont **enabled** dans `strategies.json`
- Augmenter le nombre de jours d'historique
- Vérifier les conditions de marché (ADX, RSI, etc.)

---

## 📈 Exemples de Résultats

### Stratégie Rentable ✅

```
ROI: +35.2%
Win Rate: 65%
Profit Factor: 2.8
→ Stratégie validée, peut être utilisée en production
```

### Stratégie Marginale ⚠️

```
ROI: +5.1%
Win Rate: 52%
Profit Factor: 1.2
→ Stratégie fragile, optimiser les paramètres
```

### Stratégie Perdante ❌

```
ROI: -12.3%
Win Rate: 38%
Profit Factor: 0.7
→ Stratégie à revoir complètement
```

---

## 🎯 Prochaines Étapes

1. **Optimiser les paramètres** (SL/TP, RSI thresholds, etc.)
2. **Tester sur différentes périodes** (bull market, bear market, range)
3. **Comparer plusieurs stratégies** (ScalpEmaRsi vs SmartTrend)
4. **Walk-Forward Analysis** (tester sur période future non vue)

---

## ⚠️ Avertissements

- **Les performances passées ne garantissent pas les résultats futurs**
- **Le backtest ignore le slippage** (écart entre prix théorique et réel)
- **Le backtest ignore la liquidité** (assume que tous les ordres sont remplis)
- **Toujours tester en mode Phantom avant de passer en Auto**

---

## 📝 Logs et Debugging

Les logs du backtest sont affichés en temps réel:

```
[2025-10-05 14:30:00] 🚀 BUY 0.0021 BTC @ $47850.00
[2025-10-06 08:15:00] ✅ TP HIT - Closed @ $48200.00
```

Pour plus de détails, modifier `backtest_engine.py`:

```python
# Ajouter des prints dans la boucle
print(f"Candle {i}: Price={current_candle['close']}, RSI={result.get('rsi')}")
```

---

## 🤝 Contribution

Pour ajouter une nouvelle stratégie au backtest:

1. Créer la stratégie dans `strategies/`
2. L'ajouter au `StrategyEngine`
3. Lancer `python backtest_launcher.py`

Le backtest utilisera automatiquement la nouvelle stratégie !
