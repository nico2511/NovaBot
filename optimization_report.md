# Strategy Optimization Report
**Date:** 2026-02-01
**Objective:** Activate "silent" Sniper strategy and fine-tune Smart Trend.

## 1. Sniper Precision Trend Tuning
We ran a backtest simulation on 6 months of BTC data (15m timeframe) to find why the strategy was silent.

### Backtest Results (6 Months)
| Configuration | ADX Min | Pullback Tol | Setups Found | Daily Avg | Verdict |
|--------------|---------|--------------|--------------|-----------|---------|
| **Previous** | 28      | 0.25%        | 488          | ~2.7      | Too Strict |
| **Balanced** | **25**  | **0.50%**    | **1168**     | **~6.4**  | **Optimal** |
| Loose        | 20      | 1.00%        | 2130         | ~11.6     | Too Noisy |

### Changes Applied
- **ADX Threshold:** Lowered from `28` to `25` (Allows capturing trends slightly earlier).
- **Pullback Tolerance:** Increased from `0.25%` to `0.5%` (Widens the entry zone on EMA21).

---

## 2. Smart Trend Fine-Tuning
Smart Trend was found to have a very loose pullback tolerance (1.1%), which could lead to "chasing" entries far from validity.

### Analysis
- **Previous Tolerance:** 1.1% (Very permissive).
- **Optimization:** Tightened to **0.8%**.
- **Impact:** Filters out entries with poor Risk/Reward ratio while keeping the strategy active for strong trends.

### Summary of Parameters
| Strategy | Type | ADX | Pullback Tol | Role |
|----------|------|-----|--------------|------|
| **Sniper** | Precision Trend | 25 | 0.5% | High Precision, Lower Frequency |
| **Smart Trend** | General Trend | 25 | 0.8% | Broader Catch, Medium Frequency |

## Validation
- **Files Updated:** 
    - `strategies/sniper_precision_trend.py`
    - `data/config/strategies.json` (Source of Truth)
- Scripts `scripts/backtest_sniper.py` and `scripts/backtest_smart_trend.py` act as proof of concept.
