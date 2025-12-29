# Backtesting Guide

## 📊 Scripts Disponibles

### 1. `backtest_rsi_reversal.py`
Backtest de la stratégie RSI Reversal uniquement.

### 2. `backtest_all_strategies.py`
Backtest automatique de toutes les stratégies avec tableau comparatif.

## 🚀 Installation

```bash
# Activer l'environnement virtuel
source .venv/bin/activate

# Installer les dépendances
pip install backtesting pandas pandas-ta ccxt tabulate
```

## 📝 Utilisation

### Backtest Simple (RSI Reversal)
```bash
python3 backtest_rsi_reversal.py
```

### Backtest Complet (Toutes les Stratégies)
```bash
python3 backtest_all_strategies.py
```

## ⚙️ Configuration

Les paramètres peuvent être modifiés dans les scripts :

```python
SYMBOL = 'BTC/USDT'      # Paire à tester
TIMEFRAME = '15m'         # Timeframe
MONTHS = 6                # Période (mois)
INITIAL_CASH = 10000      # Capital initial
COMMISSION = 0.0006       # Frais (0.06%)
```

## 📈 Stratégies Testées

1. **Golden Cross** - SMA 50/200 crossover (Trend Following)
2. **RSI Reversal** - Sortie de zones extrêmes 30/70 (Intraday)
3. **Bollinger Breakout** - Breakout avec bougies impulsives
4. **Scalp EMA** - EMA 9/21/200 avec filtre RSI

## ⚠️ Notes Importantes

### Problème de Marge
Si vous voyez des erreurs "insufficient margin", c'est que :
- Le capital initial est trop faible
- Les SL/TP sont trop larges
- La stratégie utilise trop de levier

**Solutions** :
1. Augmenter `INITIAL_CASH` (ex: 50000 ou 100000)
2. Réduire les SL/TP dans les stratégies
3. Utiliser `size=0.1` dans les ordres (10% du capital)

### Période de Test
- 6 mois peuvent ne pas contenir assez de signaux
- Certaines stratégies (Golden Cross) sont rares
- Essayez 12 mois ou plus pour plus de trades

### Optimisation
Pour optimiser les paramètres :
```python
# Dans le script, ajouter :
stats = bt.optimize(
    rsi_period=range(10, 20, 2),
    rsi_oversold=range(20, 35, 5),
    maximize='Return [%]'
)
```

## 🎨 Visualisation

Le script ouvre automatiquement un graphique interactif dans le navigateur avec :
- Courbe d'équité
- Positions (entrées/sorties)
- Indicateurs
- Drawdown

## 📊 Métriques Affichées

- **Return %** : Rendement total
- **Win Rate %** : Taux de réussite
- **Sharpe Ratio** : Ratio rendement/risque
- **Max Drawdown** : Perte maximale
- **# Trades** : Nombre de trades
- **Avg Trade %** : Gain moyen par trade

## 🔧 Développement

### Ajouter une Nouvelle Stratégie

1. Créer la classe dans `backtest_all_strategies.py` :
```python
class MaStrategieStrategy(Strategy):
    def init(self):
        # Calculer les indicateurs
        pass
    
    def next(self):
        # Logique de trading
        pass
```

2. L'ajouter à la liste :
```python
strategies = [
    # ...
    (MaStrategieStrategy, "Ma Stratégie"),
]
```

## ⚠️ Avertissement

**Le backtesting ne garantit PAS les performances futures !**

- Les résultats passés ne préjugent pas des résultats futurs
- Le marché change constamment
- Toujours tester en paper trading avant le réel
- Utilisez une gestion de risque stricte

## 📚 Ressources

- [Documentation backtesting.py](https://kernc.github.io/backtesting.py/)
- [pandas-ta Documentation](https://github.com/twopirllc/pandas-ta)
- [CCXT Documentation](https://docs.ccxt.com/)

---

**Note** : Ces scripts sont destinés à un usage local uniquement, pas de déploiement en production.
