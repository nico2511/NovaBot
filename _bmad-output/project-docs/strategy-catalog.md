# Strategy Catalog - NovaBot

This document provides a technical overview of all trading strategies currently implemented in NovaBot.

## Strategy Engine (`strategies/engine.py`)
- **Regime Selection**: Market is classified as `TREND` (ADX > 25) or `RANGE` (ADX <= 25).
- **Waterfall Pattern**: Detection of rapid bearish movements to force `TREND_BEAR_STRONG` regime.
- **Global Filters**: 1% Bollinger Band buffer to prevent "buying the top" or "shorting the bottom".

---

## 📈 Trend-Following Strategies

### `scalp_ema_rsi`
- **Logic**: EMA 9/21 Crossover in the direction of the 50 EMA trend.
- **Filters**: RSI between 52-68 (Bull) or 32-48 (Bear). Minimum ADX 25.

### `bollinger_middle_bounce`
- **Logic**: Mean reversion to the middle Bollinger Band during a strong trend.
- **Conditions**: EMA 20 > 50 (Up) or 20 < 50 (Down) + Touch of middle band + Green/Red candle confirmation.

### `smart_trend`
- **Logic**: Multi-Timeframe structure analysis.
- **Trigger**: Micro-BOS (Break of Structure) on 1m chart after 15m pullback setup.

### `fibo_pullback`
- **Logic**: Fibonacci Golden Zone (50%-78.6%) entries in trending markets.
- **Confirmation**: Swing High/Low detection and volume spike.

---

## 📉 Range & Reversion Strategies

### `bollinger_bounce`
- **Logic**: Trading the range extremes in low-volatility environments (ADX < 22).

### `elastic_reversion`
- **Logic**: Mean reversion from extreme RSI levels (>80 or <20) and large EMA extensions (>4%).
- **Target**: Reversion to the EMA.

### `elastic_nibbler`
- **Logic**: High-speed scalping using heavy BB breakouts (3.0 SD) and RSI extremes.

### `institutional_scalp`
- **Logic**: Detection of liquidity sweeps (sweeping recent high/low and rapid reclaim).

### `smart_mean_reversion`
- **Logic**: "Healthy dip" buying in trends using RSI "Recharge" zones (40-55).
