from app.services.indicators import ta
from strategies.base import BaseStrategy


class StrategyMemeBreakoutRetest(BaseStrategy):
    """
    Meme Breakout + Retest strategy (15m).

    Idea:
    - Detect a recent breakout with volume expansion.
    - Enter only when price retests breakout level and confirms.
    - Keep risk framed with ATR-based SL and fixed RR TP.
    """

    AI_PERSONA = """
    CODENAME: "BREAKOUT RETEST HUNTER"

    ROLE:
    You are a disciplined breakout trader. You do not chase first impulse candles.

    PRIME DIRECTIVE:
    Enter only after confirmation: breakout first, clean retest second, then continuation.
    """

    def __init__(self, config=None):
        super().__init__(config)
        # NOTE: all tunable params are read dynamically via self.get_param()
        # inside generate_signal()/calculate_progress() so that edits made via
        # POST /api/engine/config/strategy-params take effect without rebuilding
        # the strategy engine.

    def _params_snapshot(self):
        """Snapshot all tunable params in one call (live read)."""
        return {
            "ema_trend":        int(self.get_param("ema_trend", 200)),
            "rsi_len":          int(self.get_param("rsi_period", 14)),
            "atr_len":          int(self.get_param("atr_period", 14)),
            "lookback":         int(self.get_param("breakout_lookback", 20)),
            "max_breakout_age": int(self.get_param("max_breakout_age", 8)),
            "breakout_buffer":  float(self.get_param("breakout_buffer", 0.0015)),
            "retest_tolerance": float(self.get_param("retest_tolerance", 0.0030)),
            "volume_mult":      float(self.get_param("volume_multiplier", 1.4)),
            "min_rr":           float(self.get_param("min_rr", 1.7)),
            "sl_atr_mult":      float(self.get_param("sl_atr_mult", 1.2)),
            "rsi_buy_min":      float(self.get_param("rsi_buy_min", 48)),
            "rsi_buy_max":      float(self.get_param("rsi_buy_max", 72)),
            "rsi_sell_min":     float(self.get_param("rsi_sell_min", 28)),
            "rsi_sell_max":     float(self.get_param("rsi_sell_max", 52)),
        }

    def add_indicators(self, df, p=None):
        p = p or self._params_snapshot()
        df[f"EMA_{p['ema_trend']}"] = ta.ema(df["close"], length=p["ema_trend"])
        df[f"RSI_{p['rsi_len']}"] = ta.rsi(df["close"], length=p["rsi_len"])
        df[f"ATRr_{p['atr_len']}"] = ta.atr(df["high"], df["low"], df["close"], length=p["atr_len"])
        df["VOL_MA_20"] = df["volume"].rolling(20).mean()
        return df

    def _find_recent_breakout(self, df, side, p):
        """
        Returns tuple (breakout_level, breakout_idx, breakout_close) or (None, None, None).
        Uses confirmed candles only.
        """
        end_idx = len(df) - 3  # exclude current confirmed retest candle (-2) and live candle (-1)
        start_idx = max(p["lookback"] + 5, end_idx - p["max_breakout_age"] + 1)

        if end_idx <= start_idx:
            return None, None, None

        for i in range(start_idx, end_idx + 1):
            base_start = max(0, i - p["lookback"])
            base = df.iloc[base_start:i]
            if len(base) < p["lookback"] // 2:
                continue

            if side == "BUY":
                level = float(base["high"].max())
                is_break = float(df["close"].iloc[i]) > level * (1 + p["breakout_buffer"])
            else:
                level = float(base["low"].min())
                is_break = float(df["close"].iloc[i]) < level * (1 - p["breakout_buffer"])

            if not is_break:
                continue

            vol_ma = float(df["VOL_MA_20"].iloc[i]) if df["VOL_MA_20"].iloc[i] is not None else 0
            vol = float(df["volume"].iloc[i])
            if vol_ma <= 0 or vol < vol_ma * p["volume_mult"]:
                continue

            return level, i, float(df["close"].iloc[i])

        return None, None, None

    def generate_signal(self, df, extra_data=None):
        p = self._params_snapshot()
        if df is None or df.empty or len(df) < max(p["ema_trend"] + 20, 260):
            return self._reject("Not enough candles for breakout/retest model")

        df = self.add_indicators(df.copy(), p)

        curr = df.iloc[-2]  # confirmed retest candle
        live = df.iloc[-1]  # execution context
        ema_trend_col = f"EMA_{p['ema_trend']}"
        rsi_col = f"RSI_{p['rsi_len']}"
        atr_col = f"ATRr_{p['atr_len']}"

        curr_atr = float(curr.get(atr_col, 0) or 0)
        curr_rsi = float(curr.get(rsi_col, 50) or 50)
        curr_close = float(curr["close"])
        curr_open = float(curr["open"])
        curr_low = float(curr["low"])
        curr_high = float(curr["high"])
        trend_ema = float(curr.get(ema_trend_col, curr_close))

        if curr_atr <= 0:
            return self._reject("ATR unavailable or zero")

        # BUY setup: trend up + recent bullish breakout + retest confirmation.
        if curr_close > trend_ema:
            buy_level, _, _ = self._find_recent_breakout(df, side="BUY", p=p)
            if buy_level is not None:
                touched_level = curr_low <= buy_level * (1 + p["retest_tolerance"])
                closed_back_above = curr_close > buy_level
                bullish_close = curr_close > curr_open
                rsi_ok = p["rsi_buy_min"] <= curr_rsi <= p["rsi_buy_max"]

                if touched_level and closed_back_above and bullish_close and rsi_ok:
                    sl = min(curr_low, buy_level) - (p["sl_atr_mult"] * curr_atr)
                    risk = curr_close - sl
                    if risk > 0:
                        tp = curr_close + (p["min_rr"] * risk)
                        return {
                            "signal": "BUY",
                            "price": float(live["close"]),
                            "sl": float(sl),
                            "tp": float(tp),
                            "comment": f"Breakout retest long | lvl={buy_level:.6f} | RSI={curr_rsi:.1f}"
                        }

        # SELL setup: trend down + recent bearish breakout + retest confirmation.
        if curr_close < trend_ema:
            sell_level, _, _ = self._find_recent_breakout(df, side="SELL", p=p)
            if sell_level is not None:
                touched_level = curr_high >= sell_level * (1 - p["retest_tolerance"])
                closed_back_below = curr_close < sell_level
                bearish_close = curr_close < curr_open
                rsi_ok = p["rsi_sell_min"] <= curr_rsi <= p["rsi_sell_max"]

                if touched_level and closed_back_below and bearish_close and rsi_ok:
                    sl = max(curr_high, sell_level) + (p["sl_atr_mult"] * curr_atr)
                    risk = sl - curr_close
                    if risk > 0:
                        tp = curr_close - (p["min_rr"] * risk)
                        return {
                            "signal": "SELL",
                            "price": float(live["close"]),
                            "sl": float(sl),
                            "tp": float(tp),
                            "comment": f"Breakout retest short | lvl={sell_level:.6f} | RSI={curr_rsi:.1f}"
                        }

        return self._reject("No confirmed breakout-retest continuation setup")
