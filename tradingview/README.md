# 📊 TradingView Pine Scripts - Backtesting des Stratégies Chartistes

Ce dossier contient les scripts Pine Script (v5) pour backtester les stratégies chartistes sur TradingView.

## 📁 Scripts Disponibles

### Stratégies Chartistes

### 1. `double_top_bottom.pine`
**Stratégie** : Double Top/Bottom avec divergence RSI

**Paramètres ajustables** :
- `Price Tolerance (%)` : Tolérance pour niveaux similaires (défaut: 2%)
- `Min Candles Between Peaks` : Distance minimum entre pics (défaut: 10)
- `RSI Length` : Période RSI (défaut: 14)
- `Require RSI Divergence` : Exiger divergence (défaut: true)

**Signaux** :
- 🟢 Triangle vert = Double Bottom (LONG)
- 🔴 Triangle rouge = Double Top (SHORT)

---

### 2. `triangle_breakout.pine`
**Stratégie** : Triangle Breakout (Ascendant/Descendant)

**Paramètres ajustables** :
- `Lookback Period` : Période d'analyse (défaut: 30)
- `Volatility Compression` : Seuil compression ATR (défaut: 0.8)
- `Volume Spike Multiplier` : Multiplicateur volume (défaut: 1.5x)
- `Flatness Threshold (%)` : Seuil de platitude (défaut: 2%)

**Signaux** :
- 🟢 Triangle vert = Ascending Triangle (LONG)
- 🔴 Triangle rouge = Descending Triangle (SHORT)

**Visualisation** :
- Ligne rouge = Résistance
- Ligne verte = Support
- Fond jaune = Compression de volatilité

---

### 3. `head_shoulders.pine`
**Stratégie** : Head & Shoulders (Classique et Inversé)

**Paramètres ajustables** :
- `Shoulder Tolerance (%)` : Tolérance épaules (défaut: 5%)
- `Min Formation Candles` : Formation minimum (défaut: 60)
- `Require Volume Confirmation` : Volume décroissant (défaut: true)

**Signaux** :
- 🔴 Label "H&S" = Head & Shoulders (SHORT)
- 🟢 Label "IH&S" = Inverse H&S (LONG)

---

### Stratégies du Bot

### 4. `rsi_reversal.pine`
**Stratégie** : RSI Reversal (Zones extrêmes)

**Paramètres** :
- RSI Length: 14
- Oversold: 30 / Overbought: 70
- SL: 1.5% / TP: 3.0%

---

### 5. `golden_cross.pine`
**Stratégie** : Golden Cross (SMA 50/200)

**Paramètres** :
- Fast SMA: 50
- Slow SMA: 200
- Exit on SMA cross

---

### 6. `scalp_ema.pine`
**Stratégie** : Scalp EMA (9/21/200)

**Paramètres** :
- EMA 9, 21, 200
- RSI filter: 50
- SL: 2% / TP: 4%

---

### 7. `bollinger_breakout.pine`
**Stratégie** : Bollinger Breakout

**Paramètres** :
- BB Length: 20
- Std Dev: 2.0
- Min Body Ratio: 1.0

---

## 🚀 Comment Utiliser

### Étape 1 : Ouvrir TradingView
1. Aller sur [TradingView](https://www.tradingview.com/)
2. Ouvrir un graphique (ex: BTC/USDT)
3. Cliquer sur "Pine Editor" en bas

### Étape 2 : Copier le Script
1. Ouvrir un des fichiers `.pine` de ce dossier
2. Copier tout le contenu
3. Coller dans l'éditeur Pine de TradingView

### Étape 3 : Ajouter au Graphique
1. Cliquer sur "Add to Chart" (ou Ctrl+S)
2. Le script apparaît sur le graphique

### Étape 4 : Lancer le Backtest
1. Cliquer sur l'onglet "Strategy Tester" en bas
2. Voir les résultats :
   - **Net Profit** : Profit total
   - **Percent Profitable** : Win rate
   - **Max Drawdown** : Perte maximale
   - **Sharpe Ratio** : Ratio rendement/risque

### Étape 5 : Ajuster les Paramètres
1. Cliquer sur l'icône ⚙️ du script
2. Modifier les paramètres
3. Observer l'impact sur les résultats

---

## 📊 Recommandations de Test

### Timeframes Recommandés

**Double Top/Bottom** :
- ✅ 15m (scalping)
- ✅ 1h (intraday)
- ⚠️ 4h (swing)

**Triangle Breakout** :
- ✅ 1h (intraday)
- ✅ 4h (swing)
- ✅ 1D (position)

**Head & Shoulders** :
- ⚠️ 1h (minimum)
- ✅ 4h (recommandé)
- ✅ 1D (idéal)

### Périodes de Test

**Minimum** : 3 mois
**Recommandé** : 6-12 mois
**Optimal** : 2-3 ans

### Paires à Tester

**Cryptos** :
- BTC/USDT (référence)
- ETH/USDT (volatilité)
- SOL/USDT (alt majeur)

**Forex** :
- EUR/USD (liquidité)
- GBP/USD (volatilité)

**Actions** :
- SPY (S&P 500)
- AAPL (tech)

---

## 🎯 Interprétation des Résultats

### Métriques Clés

**Net Profit** :
- ✅ > 20% sur 1 an = Excellent
- ⚠️ 5-20% = Bon
- ❌ < 5% = Faible

**Win Rate** :
- ✅ > 60% = Très bon
- ⚠️ 50-60% = Acceptable
- ❌ < 50% = Problématique

**Sharpe Ratio** :
- ✅ > 2.0 = Excellent
- ⚠️ 1.0-2.0 = Bon
- ❌ < 1.0 = Risqué

**Max Drawdown** :
- ✅ < 10% = Très bon
- ⚠️ 10-20% = Acceptable
- ❌ > 20% = Risqué

### Liste de Trades

Cliquer sur "List of Trades" pour voir :
- Tous les trades exécutés
- Entry/Exit prices
- Profit/Loss par trade
- Durée de chaque trade

---

## ⚙️ Optimisation

### Méthode 1 : Manuelle
1. Modifier un paramètre
2. Relancer le backtest
3. Comparer les résultats
4. Répéter

### Méthode 2 : Deep Backtesting (Premium)
1. Cliquer sur "Deep Backtesting"
2. Sélectionner les paramètres à optimiser
3. Lancer l'optimisation
4. TradingView teste toutes les combinaisons

---

## 🔍 Analyse Visuelle

### Vérifier Visuellement

**Signaux Valides** :
- ✅ Pattern bien formé
- ✅ Volume confirmé
- ✅ Breakout clair

**Faux Signaux** :
- ❌ Pattern incomplet
- ❌ Breakout faible
- ❌ Pas de volume

### Zoomer sur les Trades

1. Cliquer sur un trade dans la liste
2. Le graphique zoom sur ce trade
3. Analyser le pattern visuellement

---

## 📝 Export des Résultats

### Exporter les Trades
1. Onglet "List of Trades"
2. Cliquer sur "Export" (icône ⬇️)
3. Format CSV disponible

### Screenshot
1. Cliquer sur l'icône 📷
2. Sauvegarder l'image

---

## 🎨 Personnalisation

### Modifier les Couleurs
```pine
// Dans le script, modifier :
color.green → color.blue
color.red → color.orange
```

### Ajouter des Alertes
```pine
// Ajouter après les signaux :
if doubleBottom
    alert("Double Bottom détecté!", alert.freq_once_per_bar)
```

### Modifier SL/TP
```pine
// Modifier les ratios :
tp = close + (close - trough2) * 1.5  // 1.5x → 2.0x
sl = trough2 * 0.99  // 1% → 2%
```

---

## ⚠️ Limitations

### TradingView Gratuit
- Backtest sur 1 seul timeframe
- Pas d'optimisation automatique
- Historique limité

### TradingView Premium
- ✅ Multi-timeframe
- ✅ Deep backtesting
- ✅ Historique complet
- ✅ Alertes illimitées

---

## 🚀 Prochaines Étapes

1. **Tester chaque stratégie** sur BTC/USDT 1h
2. **Comparer les résultats** (Win Rate, Profit, Drawdown)
3. **Optimiser les paramètres** de la meilleure
4. **Tester sur d'autres paires** pour validation
5. **Implémenter dans le bot** si résultats satisfaisants

---

## 📚 Ressources

- [Pine Script Documentation](https://www.tradingview.com/pine-script-docs/)
- [Strategy Tester Guide](https://www.tradingview.com/support/solutions/43000481029/)
- [Backtesting Best Practices](https://www.tradingview.com/blog/en/backtesting-best-practices/)

---

## 💡 Conseils

1. **Ne pas sur-optimiser** : Des résultats trop parfaits = overfitting
2. **Tester sur différentes périodes** : Bull market vs Bear market
3. **Vérifier visuellement** : Les signaux doivent avoir du sens
4. **Comparer avec Buy & Hold** : La stratégie doit battre le marché
5. **Tenir compte des frais** : 0.06% par trade (réaliste)

**Bon backtesting !** 📊
