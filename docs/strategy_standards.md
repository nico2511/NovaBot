# 📘 Standards de Développement de Stratégies (NovaBot Protocol)

Ce document définit les règles strictes pour l'ajout de nouvelles stratégies dans le bot. Toute Pull Request ou modification doit respecter ce protocole pour garantir la robustesse et éviter le "Repainting".

## 1. La Philosophie : L'Approche en Entonnoir (Funnel)

Nous ne mélangeons jamais les régimes de marché. Une stratégie doit savoir "quand ne pas jouer".

### Structure Obligatoire du Code
```python
def generate_signal(self, df):
    # 1. LE GARDIEN (Regime Filter)
    # Bloque 50% des faux signaux immédiatement
    if not is_market_regime_valid(df):
        return None

    # 2. LE SETUP (Configuration)
    # Vérifie si le contexte technique est bon
    if not is_setup_valid(df):
        return None

    # 3. LE TRIGGER (Gâchette)
    # Validation finale pour l'entrée
    return check_trigger(df)
```

## 2. Règles Techniques Critiques

### 🚫 Anti-Repainting (Règle d'Or)
L'utilisation de la dernière ligne du DataFrame (`iloc[-1]`) est **INTERDITE** pour la prise de décision, car cette bougie n'est pas finie. Ses valeurs changent jusqu'à la clôture.

- ❌ **MAUVAIS :** `if df['close'].iloc[-1] > df['ema'].iloc[-1]:` (Le signal peut disparaître/repeindre).
- ✅ **BON :** `if df['close'].iloc[-2] > df['ema'].iloc[-2]:` (Le signal est gravé dans le marbre).

### 🛡️ Filtres de Régime (ADX)
L'ADX est notre juge de paix. Il détermine si le marché a de l'énergie et filtre le bruit.

- **Stratégies de TENDANCE (Trend Following) & Continuation :**
  - Doivent exiger **ADX > 20** (ou 25).
  - *Pourquoi ?* Pour ne pas se faire "hacher" (whipsaw) dans un range sans direction.

- **Stratégies de RANGE (Mean Reversion) & Reversal :**
  - Doivent exiger **ADX < 25** (ou un ADX qui ne casse pas 30).
  - *Cas Spécial Reversal :* Exiger **ADX > 15** pour éviter les marchés morts (zéro volatilité).
  - *Pourquoi ?* Pour ne pas shorter une fusée (Breakout) ou acheter un couteau qui tombe (Crash).

### 🔊 Validation par le Volume
Un mouvement de prix sans volume est suspect (Fakeout).

- Les stratégies de **Renversement** (ex: Double Bottom, Liquidity Grab) DOIVENT vérifier que le volume sur la bougie de signal est supérieur à la moyenne.
- **Formule :** `current_volume > sma_volume_20 * 1.5` (ou au moins `> sma_volume_20`).
- **Rappel Anti-Repainting :** Utiliser `df['volume'].iloc[-2]`.

## 3. Checklist Avant Déploiement

Avant d'activer une stratégie en LIVE, cochez ces cases :

- [ ] **Type Défini :** La stratégie est-elle classée Trend ou Range ? est-ce documenté ?
- [ ] **Gardien ADX :** Y a-t-il une "Guard Clause" (if ADX...) au tout début de `generate_signal` ?
- [ ] **Indexation :** Toutes les conditions utilisent-elles `iloc[-2]` (ou antérieur) ? Aucune trace de `iloc[-1]` ?
- [ ] **Volume :** Si c'est un pattern ou un reversal, le volume est-il vérifié sur la bougie close ?
- [ ] **Risk Management :** Le Stop Loss et le Take Profit sont-ils dynamiques (basés sur l'ATR ou la structure) et non fixes (%) ?
