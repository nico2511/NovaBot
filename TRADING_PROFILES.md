# 🧠 Trading Profiles Configuration Guide

This document lists all available **Bot Personas** and **Risk Profiles** that can be configured via the `.env` file to customize the AI's trading behavior.

---

## 📋 Available Bot Personas

Copy one of these values into your `.env` file as `BOT_PERSONA`:

### 1. **Conservative Scalper** (Default)
```
BOT_PERSONA=Conservative Scalper
```
- **Style**: Quick in-and-out trades with tight stop losses
- **Focus**: Capital preservation over aggressive gains
- **Best For**: Stable markets, risk-averse traders
- **Characteristics**: 
  - Prefers high-probability setups
  - Exits quickly on adverse moves
  - Targets small, consistent profits

### 2. **Aggressive Day Trader**
```
BOT_PERSONA=Aggressive Day Trader
```
- **Style**: Active trading with larger position sizes
- **Focus**: Maximizing daily profit potential
- **Best For**: Volatile markets, experienced traders
- **Characteristics**:
  - Takes more trades per day
  - Wider stop losses for trend continuation
  - Seeks larger profit targets

### 3. **Sniper**
```
BOT_PERSONA=Sniper
```
- **Style**: Patient, precision-based entries
- **Focus**: Quality over quantity
- **Best For**: Ranging markets, pattern-based trading
- **Characteristics**:
  - Waits for perfect setups
  - Very selective entry criteria
  - High win rate, low trade frequency

---

## 🎯 Available Risk Profiles

Copy one of these values into your `.env` file as `RISK_PROFILE`:

### 1. **Capital Preservation First** (Default)
```
RISK_PROFILE=Capital Preservation First
```
- **Risk Tolerance**: Very Low
- **Max Drawdown Target**: 2-5% per trade
- **Position Sizing**: Conservative (1-2% of capital)
- **Stop Loss**: Tight, respects technical levels
- **Best For**: Accounts under $1000, beginners

### 2. **Balanced Growth**
```
RISK_PROFILE=Balanced Growth
```
- **Risk Tolerance**: Moderate
- **Max Drawdown Target**: 5-10% per trade
- **Position Sizing**: Standard (2-5% of capital)
- **Stop Loss**: Moderate, allows for volatility
- **Best For**: Accounts $1000-$10,000, intermediate traders

### 3. **High Volatility Hunter**
```
RISK_PROFILE=High Volatility Hunter
```
- **Risk Tolerance**: High
- **Max Drawdown Target**: 10-20% per trade
- **Position Sizing**: Aggressive (5-10% of capital)
- **Stop Loss**: Wide, designed for large swings
- **Best For**: Accounts over $10,000, experienced traders, high-volatility assets

---

## ⚙️ Timeframe Configuration

Set the primary analysis timeframe via `.env`:

```
TRADING_TIMEFRAME=15m
```

**Available Options:**
- `1m` - 1 Minute (Ultra-short scalping)
- `5m` - 5 Minutes (Short-term scalping)
- `15m` - 15 Minutes (Default, balanced)
- `1h` - 1 Hour (Swing trading)
- `4h` - 4 Hours (Position trading)
- `1d` - 1 Day (Long-term trends)

---

## 📝 Example .env Configuration

```bash
# AI Configuration
BOT_PERSONA=Conservative Scalper
RISK_PROFILE=Capital Preservation First
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
3. **Verify** in logs that new persona is loaded

---

## 💡 Recommended Combinations

### For Beginners
```
BOT_PERSONA=Conservative Scalper
RISK_PROFILE=Capital Preservation First
TRADING_TIMEFRAME=15m
```

### For Experienced Traders
```
BOT_PERSONA=Aggressive Day Trader
RISK_PROFILE=Balanced Growth
TRADING_TIMEFRAME=5m
```

### For Pattern Traders
```
BOT_PERSONA=Sniper
RISK_PROFILE=Capital Preservation First
TRADING_TIMEFRAME=1h
```

---

## ⚠️ Important Notes

- **Case Sensitive**: Copy the exact values shown above
- **Restart Required**: Changes take effect after bot restart
- **Test First**: Try conservative settings before aggressive ones
- **Monitor Performance**: Track results and adjust as needed
