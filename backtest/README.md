# Backtest Framework - NovaBot Strategies

Framework de backtest pour **TOUTES les stratégies** du dossier `strategies/` sur BTC/USDT 15M.

## 📁 Structure

```
backtest/
├── .gitignore              # Ignore results, keep code
├── README.md               # Ce fichier
├── main.py                 # Backtest toutes les stratégies
├── config.py               # Configuration globale
├── requirements.txt        # Dépendances
├── results/                # Résultats (dans gitignore parent)
│   ├── equity/            # Courbes d'equity par stratégie
│   ├── trades/            # Trades par stratégie
│   ├── plots/             # Graphiques
│   └── comparison/        # Comparaison multi-stratégies
└── utils/                  # Utilitaires
    ├── data_loader.py     # Chargement données
    └── reporter.py        # Export résultats
```

## 🚀 Installation

```bash
# Depuis la racine du projet
cd backtest
pip install -r requirements.txt
```

## ▶️ Lancement

### Backtest TOUTES les Stratégies
```bash
python main.py
```

### Backtest Stratégie Spécifique
```bash
python main.py --strategy fibo_pullback
```

### Avec Optimisation
```bash
python main.py --strategy fibo_pullback --optimize
```

### Personnaliser Période
```bash
python main.py --start 2025-01-01 --end 2026-01-08
```

## 📊 Résultats

Les résultats sont sauvegardés dans `results/` :
- **comparison/** : Tableau comparatif de toutes les stratégies
- **equity/** : Courbes d'equity individuelles
- **trades/** : Listes des trades par stratégie
- **plots/** : Graphiques interactifs

## ⚙️ Configuration

Modifier `config.py` pour changer :
- Symbole (BTC, ETH, etc.)
- Période de backtest
- Frais et slippage
- Capital initial
- Stratégies à exclure

## 📈 Stratégies Testées

Le framework teste automatiquement toutes les stratégies dans `../strategies/` :
- ✅ fibo_pullback (V2 refactored)
- ✅ smart_trend
- ✅ smart_mean_reversion
- ✅ scalp_ema_rsi
- ✅ institutional_scalp
- ✅ bollinger_bounce
- ✅ elastic_reversion
- ✅ double_bottom
- ✅ bull_flag
- ✅ rsi_ping_pong
- ... et toutes les autres

## 🎯 Métriques Calculées

Pour chaque stratégie :
- Win Rate
- Profit Factor
- Sharpe Ratio
- Max Drawdown
- Total Return
- Nombre de trades
- R:R moyen

Comparaison globale :
- Classement par Sharpe Ratio
- Classement par Return
- Classement par Win Rate
- Meilleure stratégie globale
