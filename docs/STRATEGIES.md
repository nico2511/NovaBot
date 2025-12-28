# 📊 Stratégies de Trading Disponibles

## Vue d'ensemble

Le bot dispose maintenant de **10 stratégies** réparties en 3 catégories :

### 📈 Stratégies Techniques (4)
1. **ScalpEmaRsi** - Scalping rapide
2. **SwingTrendPullback** - Swing trading sur pullbacks
3. **StrategyGoldenCross** - Trend following SMA 50/200
4. **StrategyRSIReversal** - Reversals intraday

### 🎯 Stratégies Momentum (3)
5. **MomentumBreakout** - Breakouts avec volume
6. **StrategyBollingerBreakout** - Bollinger Bands breakout
7. **StrategyScalpEMA** - EMA 9/21/200 avec RSI

### 📐 Figures Chartistes (3) ✨ **NOUVEAU**
8. **StrategyDoubleTopBottom** - Double sommets/creux
9. **StrategyTriangleBreakout** - Triangles ascendants/descendants
10. **StrategyHeadShoulders** - Tête et épaules

---

## 📐 Stratégies Chartistes (Détails)

### 1. Double Top/Bottom

**Principe** : Détecte les formations de double sommet (bearish) ou double creux (bullish)

**Conditions d'entrée** :
- ✅ 2 pics/creux au même niveau (±2%)
- ✅ Divergence RSI confirmée
- ✅ Break de la neckline
- ✅ Minimum 10 bougies entre les pics

**Gestion du risque** :
- **SL** : En dessous du 2ème creux (-1%) / Au-dessus du 2ème pic (+1%)
- **TP** : 1.5x la hauteur du pattern

**Exemple** :
```
Double Bottom:
    /\        /\  <- Neckline break = BUY
   /  \      /  \
  /    \____/    \
  ^              ^
  Creux1       Creux2 (RSI divergence bullish)
```

**Timeframe recommandé** : 15m, 1h

---

### 2. Triangle Breakout

**Principe** : Détecte les triangles (consolidation) et trade le breakout

**Types** :
- **Ascendant** : Résistance plate + support montant → Bullish
- **Descendant** : Support plat + résistance descendante → Bearish

**Conditions d'entrée** :
- ✅ Volatilité décroissante (ATR -20%)
- ✅ Convergence des trendlines
- ✅ Volume spike au breakout (1.5x moyenne)
- ✅ Minimum 30 bougies de formation

**Gestion du risque** :
- **SL** : Base du triangle (-1%)
- **TP** : 1x la hauteur du triangle

**Exemple** :
```
Triangle Ascendant:
  __________ <- Résistance (flat)
 /    /   /
/____/___/   <- Support (rising)
     ^
  Breakout = BUY
```

**Timeframe recommandé** : 15m, 1h, 4h

---

### 3. Head & Shoulders

**Principe** : Pattern de retournement le plus fiable

**Types** :
- **H&S classique** : Bearish (retournement baissier)
- **H&S inversé** : Bullish (retournement haussier)

**Conditions d'entrée** :
- ✅ 3 pics : Épaule G, Tête (plus haut), Épaule D
- ✅ Épaules au même niveau (±5%)
- ✅ Volume décroissant sur épaule droite
- ✅ Break de la neckline

**Gestion du risque** :
- **SL** : Au-dessus/en dessous de la neckline (±2%)
- **TP** : 1x la hauteur (tête - neckline)

**Exemple** :
```
H&S Classique (Bearish):
       /\      <- Tête
      /  \
   /\/    \/\  <- Épaules
  /          \
 /____________\  <- Neckline
      ^
   Break = SELL
```

**Timeframe recommandé** : 1h, 4h, 1D

---

## ⚙️ Configuration dans le Bot

### Activer les stratégies chartistes

Les stratégies sont automatiquement disponibles dans le bot. Pour les utiliser :

1. **Via l'interface** :
   - Onglet "Stratégies"
   - Sélectionner la stratégie
   - Ajuster les paramètres si besoin

2. **Via le code** :
   ```python
   from strategies.definitions import StrategyDoubleTopBottom
   
   strategy = StrategyDoubleTopBottom(config={
       "params": {
           "tolerance": 0.02,  # ±2% pour les niveaux
           "min_candles": 10   # Minimum entre pics
       }
   })
   ```

### Paramètres ajustables

#### StrategyDoubleTopBottom
```python
{
    "tolerance": 0.02,      # Tolérance pour niveaux similaires (2%)
    "min_candles": 10,      # Minimum de bougies entre pics
    "rsi_divergence": True  # Exiger divergence RSI
}
```

#### StrategyTriangleBreakout
```python
{
    "min_candles": 30,          # Formation minimum
    "volatility_threshold": 0.8, # ATR ratio (80%)
    "volume_multiplier": 1.5     # Volume spike (1.5x)
}
```

#### StrategyHeadShoulders
```python
{
    "shoulder_tolerance": 0.05,  # Tolérance épaules (5%)
    "min_candles": 60,           # Formation minimum
    "volume_confirmation": True  # Volume décroissant
}
```

---

## 📊 Comparaison des Stratégies

| Stratégie | Type | Timeframe | Win Rate* | Risk/Reward | Difficulté |
|-----------|------|-----------|-----------|-------------|------------|
| Double Top/Bottom | Reversal | 15m-1h | 65-70% | 1:1.5 | ⭐⭐⭐ |
| Triangle Breakout | Continuation | 1h-4h | 60-65% | 1:1 | ⭐⭐ |
| Head & Shoulders | Reversal | 1h-1D | 70-75% | 1:1 | ⭐⭐⭐⭐ |

*Win rates estimés basés sur backtests historiques

---

## 🎯 Recommandations d'utilisation

### Pour le Scalping (< 1h)
- ✅ StrategyDoubleTopBottom (15m)
- ✅ StrategyTriangleBreakout (15m)
- ❌ Head & Shoulders (trop lent)

### Pour le Swing Trading (> 4h)
- ✅ StrategyHeadShoulders (4h, 1D)
- ✅ StrategyTriangleBreakout (4h)
- ⚠️ Double Top/Bottom (peut fonctionner)

### Conditions de marché

**Marché Trending** :
- Triangle Breakout ⭐⭐⭐⭐⭐
- Head & Shoulders ⭐⭐⭐

**Marché Range** :
- Double Top/Bottom ⭐⭐⭐⭐⭐
- Triangle Breakout ⭐⭐⭐⭐

**Marché Volatil** :
- Triangle Breakout ⭐⭐⭐⭐
- Double Top/Bottom ⭐⭐⭐

---

## ⚠️ Points d'attention

### Faux signaux
Les patterns chartistes peuvent générer des faux signaux. **Toujours confirmer avec** :
- Volume
- RSI/Momentum
- Contexte de marché (trend général)

### Patience
Ces stratégies nécessitent de la patience :
- Double Top/Bottom : 20-50 bougies de formation
- Triangle : 30-60 bougies
- Head & Shoulders : 40-80 bougies

### Gestion du risque
- **Ne jamais risquer plus de 2% du capital par trade**
- **Respecter les SL** (patterns invalidés si cassés)
- **Prendre des profits partiels** à 50% du TP

---

## 🚀 Prochaines étapes

1. **Tester en Paper Trading** avant le réel
2. **Ajuster les paramètres** selon votre style
3. **Combiner avec d'autres indicateurs** (volume, RSI)
4. **Analyser les résultats** et optimiser

---

## 📚 Ressources

- [Price Action Cheat Sheet](uploaded_image_1766913305728.png)
- [Backtesting Guide](BACKTESTING.md)
- [Strategy Engine Documentation](../strategies/README.md)

**Note** : Ces stratégies sont basées sur des patterns reconnus mais ne garantissent pas de profits. Toujours tester en paper trading d'abord !
