# 📋 Optimisations Stratégies - Corrections

## Feedback Utilisateur

### 1. ✅ Filtre ADX déjà présent
**Commentaire:** "normalement tu as déjà dans le bot ce filtre"  
**Réponse:** Oui, `swing_trend_pullback` a déjà `min_adx: 25`, MAIS `ScalpEmaRsi` (qui génère 76% des signaux) n'en a PAS.

**Action:** Ajouter filtre ADX à ScalpEmaRsi dans `strategies.json`

---

### 2. ✅ RSIReversal - Objectif Oversold/Overbought
**Commentaire:** "Le but n'est pas d'attraper les oversold ou buy ?"  
**Réponse:** Si ! C'est exactement ça. Le problème actuel:
- Seuils trop stricts (RSI < 30 / > 70)
- Seulement 2 signaux en 52 jours
- Besoin d'assouplir à 35/65 pour plus d'opportunités

**Action:** Modifier seuils RSI dans `strategies.json`

---

### 3. ✅ GoldenCross - Timeframe Adapté
**Commentaire:** "quel timeframe alors ?"  
**Réponse:** GoldenCross (EMA 50/200) fonctionne mieux sur:
- **4h** (swing trading court terme)
- **1d** (swing trading moyen terme)
- **1w** (position trading)

Sur 15m, les EMAs 50/200 sont trop lentes (lag énorme).

**Action:** Désactiver GoldenCross sur 15m, ou utiliser EMAs plus courtes (9/21)

---

### 4. ✅ RSIReversal - Meilleur sur Alts/Memecoins
**Commentaire:** "n'est-il pas plus adapté sur des alt ou meme coin ? donc exit BTC/ETH ou même les majeurs?"  
**Réponse:** **EXCELLENT POINT !** RSI Reversal fonctionne mieux sur:
- **Memecoins** (PEPE, DOGE, FARTCOIN) → Volatilité élevée, reversals fréquents
- **Altcoins** (SOL, AVAX, LINK) → Bons pour mean reversion
- **Pas BTC/ETH** → Trop stables, peu de reversals extrêmes

**Action:** Tester RSIReversal sur PEPE/DOGE au lieu de BTC

---

## 🔧 Configuration Optimisée

```json
{
  "strategies": {
    "scalp_ema_rsi": {
      "enabled": true,
      "params": {
        "ema_fast": 9,
        "ema_slow": 21,
        "rsi_period": 14,
        "rsi_overbought": 65,
        "rsi_oversold": 35,
        "min_adx": 25
      }
    },
    "rsi_reversal": {
      "enabled": true,
      "params": {
        "rsi_oversold": 35,
        "rsi_overbought": 65,
        "preferred_assets": ["PEPE", "DOGE", "FARTCOIN", "SOL", "AVAX"]
      }
    },
    "golden_cross": {
      "enabled": false,
      "reason": "Inadapté au timeframe 15m, utiliser 4h/1d"
    }
  }
}
```

---

## 🧪 Plan de Test

### Test 1: BTC avec ScalpEmaRsi + ADX Filter
- Ajouter `min_adx: 25` à ScalpEmaRsi
- Relancer backtest BTC 15m
- **Attendu:** Moins de signaux, meilleur win rate

### Test 2: PEPE avec RSIReversal
- Télécharger données PEPE 15m
- Activer seulement RSIReversal
- Assouplir seuils (35/65)
- **Attendu:** Plus de signaux, bon pour reversals

### Test 3: Désactiver GoldenCross
- Mettre `enabled: false`
- Relancer backtest
- **Attendu:** Pas d'impact (seulement 2 signaux)

---

## 📊 Résultats Attendus

**Avant optimisation:**
- ROI: -1.22%
- Trades: 100
- Win Rate: 42%

**Après optimisation:**
- ROI: +3% à +8%
- Trades: 60-80 (moins mais meilleurs)
- Win Rate: 50%+

**Changements clés:**
1. Filtre ADX sur ScalpEmaRsi (qualité > quantité)
2. RSIReversal sur memecoins (asset adapté)
3. GoldenCross désactivé (timeframe inadapté)
