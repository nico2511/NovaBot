from app.services.indicators import TaAdapter
from strategies.base import BaseStrategy

# Use the singleton adapter
ta = TaAdapter()

class StrategyMemeHunter(BaseStrategy):
    """
    MEME HUNTER STRATEGY
    Designed for volatile assets using 15m Momentum.

    Trigger:
    - EMA fast/slow crossover (defaults 20/50)

    Filters (tunable via strategies.json):
    - Trend Filter: Price vs ema_trend (default 200)
    - RSI: buy below rsi_buy_max / sell above rsi_sell_min
    - Slope: |EMA slow slope %| >= min_slope
    - Volatility: Bollinger Band Width expanding (or > 0.02)

    Risk: SL = atr_multiplier * ATR ; TP = min_rr * risk
    """

    AI_PERSONA = """
    CODENAME: "VOLATILITY VOYAGER"
    
    ROLE:
    You are a momentum sniper. You don't fear extreme RSI; you fear missing a confirmed trend shift.
    
    PRIME DIRECTIVE:
    Identify when the short-term momentum (EMA 20) flips the medium-term balance (EMA 50) in a high-volatility environment.
    """

    def __init__(self, config=None):
        super().__init__(config)
        # All tunable params read dynamically via self.get_param() — see BaseStrategy.

    def _params_snapshot(self):
        """Snapshot all tunable params in one call (live read)."""
        return {
            "ema_fast":      int(self.get_param("ema_fast", 20)),
            "ema_slow":      int(self.get_param("ema_slow", 50)),
            "ema_trend":     int(self.get_param("ema_trend", 200)),
            "rsi_buy_max":   float(self.get_param("rsi_buy_max", 85)),
            "rsi_sell_min":  float(self.get_param("rsi_sell_min", 15)),
            "atr_mult":      float(self.get_param("atr_multiplier", 2.0)),
            "rr_ratio":      float(self.get_param("min_rr", 1.5)),
            "min_slope":     float(self.get_param("min_slope", 0.001)),
            "test_mode":     bool(self.get_param("test_mode", False)),
        }

    def add_indicators(self, df, p=None):
        """Add indicators to dataframe"""
        p = p or self._params_snapshot()
        df[f"EMA_{p['ema_fast']}"] = ta.ema_std(df["close"], length=p["ema_fast"])
        df[f"EMA_{p['ema_slow']}"] = ta.ema_std(df["close"], length=p["ema_slow"])
        df[f"EMA_{p['ema_trend']}"] = ta.ema_std(df["close"], length=p["ema_trend"])

        df["RSI"] = ta.rsi(df["close"], length=14)
        df["ATR"] = ta.atr(df["high"], df["low"], df["close"], length=14)

        # Bollinger Bands for volatility check
        bb = ta.bbands(df["close"], length=20, std=2.0)
        df["BB_Width"] = (bb["BBU"] - bb["BBL"]) / bb["BBM"]

        return df

    def generate_signal(self, df, extra_data=None):
        """Generate signals based on EMA crossover and volatility"""
        p = self._params_snapshot()
        if len(df) < p["ema_trend"] + 10:  # Extra padding for accurate EMA/Slope
            return self._reject("Not enough candles for stable EMA trend/slope")

        df = self.add_indicators(df.copy(), p)

        # --- STABILITY FIX ---
        # Use iloc[-2] (last confirmed candle) and iloc[-3] (previous confirmed)
        # to detect the crossover on CLOSED data. This prevents repainting.
        curr = df.iloc[-2]
        prev = df.iloc[-3]

        # Also get forming candle (iloc[-1]) just for logging price context
        live = df.iloc[-1]

        ema_fast_col = f"EMA_{p['ema_fast']}"
        ema_slow_col = f"EMA_{p['ema_slow']}"
        ema_trend_col = f"EMA_{p['ema_trend']}"

        # Calculate Slope (EMA 50 orientation)
        ema_slow_prev_slope = df[ema_slow_col].iloc[-7]  # 5 candles lookback
        ema_slope = (curr[ema_slow_col] - ema_slow_prev_slope) / ema_slow_prev_slope * 100

        min_slope = p["min_slope"]
        test_mode = p["test_mode"]
        buy_rsi_limit = p["rsi_buy_max"]
        sell_rsi_limit = p["rsi_sell_min"]

        # Crossover Detection
        is_bullish_cross = prev[ema_fast_col] <= prev[ema_slow_col] and curr[ema_fast_col] > curr[ema_slow_col]
        is_bearish_cross = prev[ema_fast_col] >= prev[ema_slow_col] and curr[ema_fast_col] < curr[ema_slow_col]


        # --- BULLISH SIGNAL ---
        if is_bullish_cross:
            # 1. Trend Filter
            if not curr['close'] > curr[ema_trend_col]:
                print(f"[MemeHunter] Cross UP detected but rejected: Price ({curr['close']:.4f}) below EMA 200 ({curr[ema_trend_col]:.4f})")
                return self._reject("Bull cross below EMA trend filter")
            
            # 2. Slope Filter
            if ema_slope < min_slope:
                print(f"[MemeHunter] Cross UP detected but rejected: EMA 50 Slope ({ema_slope:.5f}) below Min ({min_slope})")
                return self._reject("Bull cross slope below minimum")

            # 3. RSI Filter
            if not curr['RSI'] < buy_rsi_limit:
                print(f"[MemeHunter] Cross UP detected but rejected: RSI ({curr['RSI']:.1f}) above limit ({buy_rsi_limit})")
                return self._reject("Bull cross RSI above buy limit")

            vol_ok = curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02
            if not vol_ok:
                print(f"[MemeHunter] Cross UP detected but rejected: BB Width ({curr['BB_Width']:.4f}) not expanding")
                return self._reject("Bull cross volatility filter failed")

            # If all PASS -> BUY
            sl = curr['close'] - (p["atr_mult"] * curr['ATR'])
            risk = curr['close'] - sl
            tp = curr['close'] + (risk * p["rr_ratio"])

            return {
                "signal": "BUY",
                "price": float(live['close']),  # Use live price for entry
                "sl": float(sl),
                "tp": float(tp),
                "strategy": "MemeVolatilityHunter",
                "comment": f"{'[TEST MODE] ' if test_mode else ''}EMA {p['ema_fast']}/{p['ema_slow']} Golden Cross | Slope: {ema_slope:.4f}"
            }

        # --- BEARISH SIGNAL ---
        elif is_bearish_cross:
            # 1. Trend Filter
            if not curr['close'] < curr[ema_trend_col]:
                print(f"[MemeHunter] Cross DOWN detected but rejected: Price ({curr['close']:.4f}) above EMA 200")
                return self._reject("Bear cross above EMA trend filter")
                
            # 2. Slope Filter
            if ema_slope > -min_slope:
                print(f"[MemeHunter] Cross DOWN detected but rejected: EMA 50 Slope ({ema_slope:.5f}) not negative enough (< {-min_slope})")
                return self._reject("Bear cross slope not negative enough")

            # 3. RSI Filter
            if not curr['RSI'] > sell_rsi_limit:
                print(f"[MemeHunter] Cross DOWN detected but rejected: RSI ({curr['RSI']:.1f}) below limit ({sell_rsi_limit})")
                return self._reject("Bear cross RSI below sell limit")

            vol_ok = curr['BB_Width'] > prev['BB_Width'] or curr['BB_Width'] > 0.02
            if not vol_ok:
                print(f"[MemeHunter] Cross DOWN detected but rejected: BB Width not expanding")
                return self._reject("Bear cross volatility filter failed")

            # If all PASS -> SELL
            sl = curr['close'] + (p["atr_mult"] * curr['ATR'])
            risk = sl - curr['close']
            tp = curr['close'] - (risk * p["rr_ratio"])

            return {
                "signal": "SELL",
                "price": float(live['close']),
                "sl": float(sl),
                "tp": float(tp),
                "strategy": "MemeVolatilityHunter",
                "comment": f"EMA {p['ema_fast']}/{p['ema_slow']} Death Cross | Slope: {ema_slope:.4f}"
            }
                        
        return self._reject("No fresh EMA20/50 crossover on confirmed candles")
