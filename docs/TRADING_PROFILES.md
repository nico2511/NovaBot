# 🧠 Trading Profiles Configuration Guide

Configure your bot's AI behavior via `.env` file using **Bot Personas** and **Risk Profiles**.

---

## 📋 Bot Personas

| Persona | Style | Focus | Best For | Trade Frequency |
|---------|-------|-------|----------|----------------|
| **Conservative Scalper** | Quick in-and-out with tight stops | Capital preservation | Stable markets, beginners | High (5-10/day) |
| **Aggressive Day Trader** | Active trading, larger positions | Maximize daily profits | Volatile markets, experienced | Very High (10-20/day) |
| **Sniper** | Patient, precision entries | Quality over quantity | Ranging markets, patterns | Low (1-3/day) |

### Configuration

```bash
# In your .env file
BOT_PERSONA=Conservative Scalper
```

**Available Options:**
- `Conservative Scalper` (Default)
- `Aggressive Day Trader`
- `Sniper`

---

## 🎯 Risk Profiles

| Profile | Risk/Trade | Max Drawdown | Position Size | Stop Loss | Best For |
|---------|-----------|--------------|---------------|-----------|----------|
| **Capital Preservation First** | 1-2% | 2-5% | Conservative (1-2%) | Tight | Accounts <$1000, beginners |
| **Balanced Growth** | 2-5% | 5-10% | Standard (2-5%) | Moderate | Accounts $1000-$10,000 |
| **High Volatility Hunter** | 5-10% | 10-20% | Aggressive (5-10%) | Wide | Accounts >$10,000, experienced |

### Configuration

```bash
# In your .env file
RISK_PROFILE=Capital Preservation First
```

**Available Options:**
- `Capital Preservation First` (Default)
- `Balanced Growth`
- `High Volatility Hunter`

---

## ⏱️ Trading Timeframes

| Timeframe | Style | Candle Duration | Best For |
|-----------|-------|-----------------|----------|
| `1m` | Ultra-short scalping | 1 minute | High-frequency traders |
| `5m` | Short-term scalping | 5 minutes | Active day traders |
| `15m` | Balanced (Default) | 15 minutes | Most traders |
| `1h` | Swing trading | 1 hour | Position traders |
| `4h` | Position trading | 4 hours | Long-term trends |
| `1d` | Long-term trends | 1 day | Investors |

### Configuration

```bash
# In your .env file
TRADING_TIMEFRAME=15m
```

---

## 🎨 Recommended Combinations

### 🛡️ Mode Safe (Débutants)
**Pour:** Comptes <$1000, traders débutants, marchés incertains

```bash
BOT_PERSONA=Conservative Scalper
RISK_PROFILE=Capital Preservation First
TRADING_TIMEFRAME=15m
```

**Caractéristiques:**
- ✅ Stops serrés (0.5-1%)
- ✅ Petits profits (1-2%)
- ✅ Haute sélectivité
- ✅ Capital protégé

---

### ⚖️ Mode Équilibré (Intermédiaires)
**Pour:** Comptes $1000-$10,000, traders intermédiaires

```bash
BOT_PERSONA=Aggressive Day Trader
RISK_PROFILE=Balanced Growth
TRADING_TIMEFRAME=5m
```

**Caractéristiques:**
- ⚡ Stops modérés (1-2%)
- ⚡ Profits moyens (3-5%)
- ⚡ Fréquence élevée
- ⚡ Croissance stable

---

### 🚀 Mode Degen (Expérimentés)
**Pour:** Comptes >$10,000, traders expérimentés, haute volatilité

```bash
BOT_PERSONA=Sniper
RISK_PROFILE=High Volatility Hunter
TRADING_TIMEFRAME=1h
```

**Caractéristiques:**
- 🎯 Stops larges (2-5%)
- 🎯 Gros profits (5-10%)
- 🎯 Sélectivité extrême
- 🎯 Haute conviction

---

### 📐 Mode Pattern Trader
**Pour:** Traders de patterns, marchés ranging

```bash
BOT_PERSONA=Sniper
RISK_PROFILE=Capital Preservation First
TRADING_TIMEFRAME=1h
```

**Caractéristiques:**
- 📊 Attente de setups parfaits
- 📊 Patterns techniques (double bottom, H&S)
- 📊 Haute précision
- 📊 Faible fréquence

---

## 📝 Example .env Configuration

```bash
# ============================================
# AI MODULAR CONFIGURATION
# ============================================

# Bot Persona
BOT_PERSONA=Conservative Scalper

# Risk Profile
RISK_PROFILE=Capital Preservation First

# Trading Timeframe
TRADING_TIMEFRAME=15m

# AI Provider
AI_PROVIDER=openrouter
AI_MODEL_NAME=meta-llama/llama-3.1-8b-instruct
OPENROUTER_API_KEY=your_key_here

# Hyperliquid
HL_PRIVATE_KEY=your_private_key
HL_ACCOUNT_ADDRESS=your_address
```

---

## 🔄 How to Apply Changes

1. **Edit `.env` file** with your desired configuration
2. **Restart the bot**:
   ```bash
   pm2 restart hl-backend
   ```
3. **Verify** in logs that new persona is loaded:
   ```bash
   pm2 logs hl-backend --lines 20
   ```

---

## ⚠️ Important Notes

- **Case Sensitive**: Copy the exact values shown in tables
- **Restart Required**: Changes take effect after bot restart
- **Test First**: Start with conservative settings
- **Monitor Performance**: Track results and adjust as needed
- **Market Conditions**: Adapt your profile to current market volatility

---

## 💡 Quick Decision Guide

**Choose your persona based on:**
- **Time available**: More time = Aggressive Day Trader, Less time = Sniper
- **Experience**: Beginner = Conservative Scalper, Expert = Any
- **Capital**: Small = Conservative, Large = Aggressive

**Choose your risk profile based on:**
- **Account size**: <$1000 = Capital Preservation, >$10,000 = High Volatility
- **Risk tolerance**: Low = Capital Preservation, High = High Volatility
- **Market conditions**: Stable = Balanced Growth, Volatile = High Volatility Hunter

---

## 🎓 Learning Path

1. **Week 1-2**: Start with **Mode Safe**
2. **Week 3-4**: Graduate to **Mode Équilibré**
3. **Month 2+**: Experiment with **Mode Degen** (if profitable)

**Remember**: Consistency beats aggression. Master one mode before switching!
