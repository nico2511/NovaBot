# NovaBot Trading Logic & Safety Mechanisms

## 🛡️ "Guard Angel" System (Position Adoption)
The bot includes a sophisticated **active monitoring system** that detects and manages manually opened positions.

### Workflow:
1. **Detection**:
   - The bot scans Hyperliquid account positions every cycle (or at startup).
   - If a position exists on the exchange but is not in the bot's memory (e.g., opened via phone), it is **adopted**.

2. **Immediate Protection**:
   - **Auto-SL**: If the manual position has no Stop Loss, the bot calculates a safety SL based on Volatility (ATR) and places it immediately.
   - **AI Analysis**: The bot runs an AI check on the position to assess risk and logs the verdict.

3. **Management**:
   - Once adopted, the manual position benefits from all bot features: **Smart Break-Even**, **Trailing Stop**, and **Gamification**.

---

## 🚀 Smart Break-Even & Trailing
To ensure capital preservation and "passive income" security, the bot manages the lifecycle of every trade (Auto or Manual) with dynamic stops.

### 1. Smart Break-Even (Defense)
**Trigger**: When price covers **40%** of the distance to Take Profit.
**Action**:
- Stop Loss is moved to **Entry Price + 0.3%** (covering fees).
- **Result**: The trade is now "Risk-Free".

### 2. Progressive Trailing (Offense)
As the trade moves further into profit, the bot secures gains by moving the SL upwards:

- **Stage 1 (>60% to TP)**: LOCKS **20%** of potential profit.
- **Stage 2 (>75% to TP)**: LOCKS **40%** of potential profit.

### 3. Force Break-Even (Panic Button)
**API**: `POST /api/force_breakeven`
**Action**: Instantly moves SL to Break-Even regardless of current price action (if price allows).
**Use Case**: Manual intervention via Dashboard when market conditions suddenly turn uncertain.

---

## ⛔ "Hard Veto" System (Technical Guardrails)
While the AI provides sophisticated judgment, logical **Hard Veto** rules act as a final, immutable fail-safe to prevent obvious mistakes.

### Logic
Before executing ANY trade (including AI-approved ones), the bot runs a technical check:

- **RSI Overbought Protection**:
  - IF `RSI > 75` AND Signal is `BUY` -> **VETO** (Risk of buying the top).
- **RSI Oversold Protection**:
  - IF `RSI < 25` AND Signal is `SELL` -> **VETO** (Risk of panic selling the bottom).

**Impact**: This prevents the bot from FOMOing into pumped coins or panic-selling during flash crashes, regardless of strategy or AI opinion.
