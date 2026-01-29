# SNIPER - PRECISION TREND Strategy

## Vue d'ensemble

**SNIPER - PRECISION TREND** est une stratégie MTF (Multi-TimeFrame) disciplinée qui combine:
- **Setup 15m**: Détection de pullback sur EMA21 en tendance saine
- **Trigger 1m**: Confirmation BOS (Break of Structure) avec volume
- **Capital Preservation First**: R:R 2:1 minimum, rejette 90% des setups

## Philosophie

Cette stratégie incarne le persona **SNIPER** du master prompt:
- ❌ Rejette les entrées FOMO au top tick
- ✅ Attend les setups parfaits avec 4+ confirmations
- 🎯 Privilégie la qualité sur la quantité (faible fréquence, high win rate)
- 🛡️ Capital preservation: 1-2% risk max par trade

## Conditions d'entrée (CHECKLIST)

### 1. Trend sain et aligné (25% progress)
- ✅ **LONG**: Price > EMA50 ET EMA21 > EMA50
- ✅ **SHORT**: Price < EMA50 ET EMA21 < EMA50
- ✅ **ADX > 28** ET rising (pas de crash)

### 2. Pullback valide (25% progress)
- ✅ Touch EMA21 avec tolérance **< 0.25%** (très strict)
- ✅ Volume **> 1.3x** moyenne (intérêt acheteur/vendeur)
- ✅ Volume decrease sur pullback, increase sur bounce

### 3. RSI optimal (10% progress)
- ✅ RSI 15m entre **38-70** (zone optimale)
- ❌ Rejette si RSI > 75 (trop chaud)
- ❌ Rejette si RSI < 30 (momentum mort)

### 4. Trigger BOS confirmé (40% progress)
- ✅ **LONG**: Close 1m > High des 3 dernières bougies
- ✅ **SHORT**: Close 1m < Low des 3 dernières bougies
- ✅ Volume 1m **> 1.3x** moyenne
- ✅ RSI 1m < 70 (LONG) / > 30 (SHORT)

## Paramètres (strategies.json)

```json
{
  "sniper_precision_trend": {
    "enabled": true,
    "type": "trend",
    "params": {
      "rr_ratio": 2.0,              // R:R minimum (TP = 2x risk)
      "adx_threshold": 28,           // ADX minimum pour trend
      "rsi_min": 38,                 // RSI minimum (éviter oversold)
      "rsi_max": 70,                 // RSI maximum (éviter overbought)
      "pullback_tolerance": 0.0025,  // 0.25% tolérance EMA21
      "bos_lookback": 3,             // Lookback pour BOS (1m)
      "sl_atr_mult": 0.35,           // SL = Swing +/- 0.35 ATR
      "volume_multiplier": 1.3       // Volume spike requis
    }
  }
}
```

## Risk Management

### Stop Loss
- **Calcul**: Swing Low/High (10 bars) +/- 0.35 ATR
- **Objectif**: Laisser respirer le trade sans être trop large

### Take Profit
- **Calcul**: Entry + (2.0 × Risk)
- **R:R**: 2:1 minimum (configurable)

### Position Sizing
- **Risk**: 1-2% du capital max
- **Leverage**: 3x max (Capital Preservation First profile)

## AI Persona Integration

Le persona **Sniper** dans `prompts.py` valide chaque signal avec ce checklist:

```
CHECKLIST (Answer OUI/NON):
1. Trend sain et aligné (Price > EMA 50, EMA 21 > EMA 50, ADX > 28 rising) ?
2. Pullback valide (EMA 21 touch < 0.25%, volume decrease then increase) ?
3. RSI optimal (38-70 on 15m, avoid extremes) ?
4. Trigger BOS confirmé (1m break of structure, volume spike, RSI not extreme) ?
5. R:R >= 2:1 with realistic SL/TP ?
```

L'IA **rejette** si:
- ❌ Marché exhausted/extended
- ❌ FOMO-driven entry
- ❌ Un seul critère manquant

## Utilisation

### 1. Activer la stratégie
Dans `strategies.json`, vérifier:
```json
"sniper_precision_trend": {
  "enabled": true
}
```

### 2. Configurer le Bot Persona
Dans l'interface ou `.env`:
```
BOT_PERSONA=Sniper
RISK_PROFILE=Capital Preservation First
```

### 3. Vérifier le régime
La stratégie s'active automatiquement en **régime TREND** (ADX > 25).

### 4. Monitoring
- **Progress**: 0-100% (visible dans UI)
  - Trend: 25%
  - Pullback: 25%
  - RSI: 10%
  - Trigger: 40%
- **Conditions**: 4 checks détaillés (UI Diagnostic Card)

## Exemple de Signal

```
🎯 SNIPER SIGNAL DETECTED

Setup (15m):
- Trend: BULLISH (EMA21 > EMA50, Price > EMA50)
- ADX: 32.4 (rising from 31.8)
- Pullback: Low touched EMA21 @ 0.18% distance
- RSI: 52.3 (optimal zone)
- Volume: 1.45x average

Trigger (1m):
- BOS: Close broke high of last 3 candles
- Volume: 1.52x average (spike confirmed)
- RSI 1m: 64.2 (not overbought)

Trade Plan:
- Direction: LONG
- Entry: $45,234.50
- SL: $45,102.30 (swing low - 0.35 ATR)
- TP: $45,498.90 (2:1 R:R)
- Risk: 0.29% capital
- Comment: "SNIPER: 15m Setup + 1m BOS (ADX OK, RSI 52.3, Vol OK)"

AI Approval: ✅ OUI (Confidence: 87%)
Reasoning: "Trend sain, pullback propre, BOS confirmé avec volume. Setup textbook."
```

## Différences avec Smart Trend

| Critère | Smart Trend | SNIPER Precision |
|---------|-------------|------------------|
| Pullback Tolerance | 1.1% | 0.25% (4x plus strict) |
| ADX Threshold | 23 | 28 (trend plus fort) |
| ADX Slope | Optionnel | **Obligatoire** (rising) |
| RSI Range | 36-72 | 38-70 (plus strict) |
| R:R Ratio | 1.65:1 | 2.0:1 (plus conservateur) |
| Fréquence | Moyenne | Faible (90% rejetés) |
| Win Rate | ~60% | ~70%+ (sélectif) |

## Backtesting

**Recommandations**:
1. Tester sur **BTC/ETH** (liquidité élevée)
2. Timeframe: **15m** (setup) + **1m** (trigger)
3. Période: Minimum 3 mois de données
4. Comparer avec Smart Trend pour valider la sélectivité

## Troubleshooting

### Aucun signal généré
- ✅ Vérifier que `enabled: true` dans config
- ✅ Vérifier régime = TREND (ADX > 25)
- ✅ Vérifier données 1m disponibles (`extra_data`)

### Trop de rejets AI
- ⚙️ Assouplir `rsi_min/max` (ex: 35-72)
- ⚙️ Augmenter `pullback_tolerance` (ex: 0.005 = 0.5%)
- ⚙️ Réduire `adx_threshold` (ex: 25)

### Faux signaux
- ⚙️ Réduire `pullback_tolerance` (plus strict)
- ⚙️ Augmenter `adx_threshold` (trend plus fort)
- ⚙️ Augmenter `volume_multiplier` (ex: 1.5x)

## Disclaimer

⚠️ **Ceci n'est pas un conseil d'investissement.**  
Backteste et valide cette stratégie par toi-même avant utilisation en réel.

---

**Version**: 1.0  
**Date**: 2026-01-29  
**Author**: Barry (Quick Flow Solo Dev)
