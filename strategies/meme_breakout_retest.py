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
        p = self.config.get("params", {})
        self.ema_trend = p.get("ema_trend", 200)
        self.rsi_len = p.get("rsi_period", 14)
        self.atr_len = p.get("atr_period", 14)
        self.lookback = p.get("breakout_lookback", 20)
        self.max_breakout_age = p.get("max_breakout_age", 8)
        self.breakout_buffer = p.get("breakout_buffer", 0.0015)
        self.retest_tolerance = p.get("retest_tolerance", 0.0030)
        self.volume_mult = p.get("volume_multiplier", 1.4)
        self.min_rr = p.get("min_rr", 1.7)
        self.sl_atr_mult = p.get("sl_atr_mult", 1.2)
        self.rsi_buy_min = p.get("rsi_buy_min", 48)
        self.rsi_buy_max = p.get("rsi_buy_max", 72)
        self.rsi_sell_min = p.get("rsi_sell_min", 28)
        self.rsi_sell_max = p.get("rsi_sell_max", 52)

    def add_indicators(self, df):
        df[f"EMA_{self.ema_trend}"] = ta.ema(df["close"], length=self.ema_trend)
        df[f"RSI_{self.rsi_len}"] = ta.rsi(df["close"], length=self.rsi_len)
        df[f"ATRr_{self.atr_len}"] = ta.atr(df["high"], df["low"], df["close"], length=self.atr_len)
        df["VOL_MA_20"] = df["volume"].rolling(20).mean()
        return df

    def _find_recent_breakout(self, df, side):
        """
        Returns tuple (breakout_level, breakout_idx, breakout_close) or (None, None, None).
        Uses confirmed candles only.
        """
        end_idx = len(df) - 3  # exclude current confirmed retest candle (-2) and live candle (-1)
        start_idx = max(self.lookback + 5, end_idx - self.max_breakout_age + 1)

        if end_idx <= start_idx:
            return None, None, None

        for i in range(start_idx, end_idx + 1):
            base_start = max(0, i - self.lookback)
            base = df.iloc[base_start:i]
            if len(base) < self.lookback // 2:
                continue

            if side == "BUY":
                level = float(base["high"].max())
                is_break = float(df["close"].iloc[i]) > level * (1 + self.breakout_buffer)
            else:
                level = float(base["low"].min())
                is_break = float(df["close"].iloc[i]) < level * (1 - self.breakout_buffer)

            if not is_break:
                continue

            vol_ma = float(df["VOL_MA_20"].iloc[i]) if df["VOL_MA_20"].iloc[i] is not None else 0
            vol = float(df["volume"].iloc[i])
            if vol_ma <= 0 or vol < vol_ma * self.volume_mult:
                continue

            return level, i, float(df["close"].iloc[i])

        return None, None, None

    def generate_signal(self, df, extra_data=None):
        if df is None or df.empty or len(df) < max(self.ema_trend + 20, 260):
            return None

        df = self.add_indicators(df.copy())

        curr = df.iloc[-2]  # confirmed retest candle
        live = df.iloc[-1]  # execution context
        ema_trend_col = f"EMA_{self.ema_trend}"
        rsi_col = f"RSI_{self.rsi_len}"
        atr_col = f"ATRr_{self.atr_len}"

        curr_atr = float(curr.get(atr_col, 0) or 0)
        curr_rsi = float(curr.get(rsi_col, 50) or 50)
        curr_close = float(curr["close"])
        curr_open = float(curr["open"])
        curr_low = float(curr["low"])
        curr_high = float(curr["high"])
        trend_ema = float(curr.get(ema_trend_col, curr_close))

        if curr_atr <= 0:
            return None

        # BUY setup: trend up + recent bullish breakout + retest confirmation.
        if curr_close > trend_ema:
            buy_level, _, _ = self._find_recent_breakout(df, side="BUY")
            if buy_level is not None:
                touched_level = curr_low <= buy_level * (1 + self.retest_tolerance)
                closed_back_above = curr_close > buy_level
                bullish_close = curr_close > curr_open
                rsi_ok = self.rsi_buy_min <= curr_rsi <= self.rsi_buy_max

                if touched_level and closed_back_above and bullish_close and rsi_ok:
                    sl = min(curr_low, buy_level) - (self.sl_atr_mult * curr_atr)
                    risk = curr_close - sl
                    if risk > 0:
                        tp = curr_close + (self.min_rr * risk)
                        return {
                            "signal": "BUY",
                            "price": float(live["close"]),
                            "sl": float(sl),
                            "tp": float(tp),
                            "comment": f"Breakout retest long | lvl={buy_level:.6f} | RSI={curr_rsi:.1f}"
                        }

        # SELL setup: trend down + recent bearish breakout + retest confirmation.
        if curr_close < trend_ema:
            sell_level, _, _ = self._find_recent_breakout(df, side="SELL")
            if sell_level is not None:
                touched_level = curr_high >= sell_level * (1 - self.retest_tolerance)
                closed_back_below = curr_close < sell_level
                bearish_close = curr_close < curr_open
                rsi_ok = self.rsi_sell_min <= curr_rsi <= self.rsi_sell_max

                if touched_level and closed_back_below and bearish_close and rsi_ok:
                    sl = max(curr_high, sell_level) + (self.sl_atr_mult * curr_atr)
                    risk = sl - curr_close
                    if risk > 0:
                        tp = curr_close - (self.min_rr * risk)
                        return {
                            "signal": "SELL",
                            "price": float(live["close"]),
                            "sl": float(sl),
                            "tp": float(tp),
                            "comment": f"Breakout retest short | lvl={sell_level:.6f} | RSI={curr_rsi:.1f}"
                        }

        return None

    def calculate_progress(self, df, extra_data=None):
        if df is None or df.empty or len(df) < max(self.ema_trend + 20, 260):
            return {
                "strategy": "MemeBreakoutRetest",
                "score": 0,
                "bias": "NEUTRAL",
                "stages": [{"name": "Data", "status": "WAIT", "details": "Not enough candles"}]
            }

        try:
            df = self.add_indicators(df.copy())
            curr = df.iloc[-1]
            ema_trend = float(curr[f"EMA_{self.ema_trend}"])
            close = float(curr["close"])
            rsi = float(curr[f"RSI_{self.rsi_len}"])
            vol = float(curr["volume"])
            vol_ma = float(curr["VOL_MA_20"]) if curr["VOL_MA_20"] is not None else 0
            vol_ratio = (vol / vol_ma) if vol_ma > 0 else 0

            trend_bias = "LONG" if close > ema_trend else "SHORT" if close < ema_trend else "NEUTRAL"
            trend_ok = trend_bias != "NEUTRAL"
            vol_ok = vol_ratio >= self.volume_mult

            if trend_bias == "LONG":
                rsi_ok = self.rsi_buy_min <= rsi <= self.rsi_buy_max
            elif trend_bias == "SHORT":
                rsi_ok = self.rsi_sell_min <= rsi <= self.rsi_sell_max
            else:
                rsi_ok = False

            score = 0
            if trend_ok:
                score += 40
            if vol_ok:
                score += 30
            if rsi_ok:
                score += 30

            return {
                "strategy": "MemeBreakoutRetest",
                "score": score,
                "bias": trend_bias,
                "stages": [
                    {
                        "name": "Trend Filter",
                        "status": "PASS" if trend_ok else "WAIT",
                        "details": f"Price vs EMA{self.ema_trend}: {trend_bias}"
                    },
                    {
                        "name": "Volume Expansion",
                        "status": "PASS" if vol_ok else "WAIT",
                        "details": f"Vol ratio: {vol_ratio:.2f}x (need {self.volume_mult:.2f}x)"
                    },
                    {
                        "name": "RSI Gate",
                        "status": "PASS" if rsi_ok else "WAIT",
                        "details": f"RSI: {rsi:.1f}"
                    }
                ]
            }
        except Exception as e:
            return {
                "strategy": "MemeBreakoutRetest",
                "score": 0,
                "bias": "NEUTRAL",
                "stages": [{"name": "Error", "status": "FAIL", "details": str(e)}]
            }
