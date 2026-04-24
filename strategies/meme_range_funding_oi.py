from app.services.indicators import ta
from strategies.base import BaseStrategy


class StrategyMemeRangeFundingOi(BaseStrategy):
    """
    Range fade strategy for meme coins with contrarian crowding filters.

    Core use-case:
    - Prefer SELL near upper range when longs look crowded
      (positive funding + rising OI pressure).
    - Optional BUY near lower range when shorts are crowded.
    """

    AI_PERSONA = """
    CODENAME: "RANGE CROWD FADE"

    ROLE:
    You fade crowded positioning at range extremes, not momentum breakouts.

    PRIME DIRECTIVE:
    Prioritize mean-reversion entries only when range context is intact.
    """

    def __init__(self, config=None):
        super().__init__(config)
        # All tunable params read dynamically via self.get_param().

    def _params_snapshot(self):
        return {
            "range_lookback":      int(self.get_param("range_lookback", 48)),
            "rsi_period":          int(self.get_param("rsi_period", 14)),
            "atr_period":          int(self.get_param("atr_period", 14)),
            "adx_max":             float(self.get_param("adx_max", 24)),
            "upper_zone":          float(self.get_param("upper_zone", 0.82)),
            "lower_zone":          float(self.get_param("lower_zone", 0.18)),
            "min_funding_short":   float(self.get_param("min_funding_short", 0.00015)),
            "max_funding_long":    float(self.get_param("max_funding_long", -0.00015)),
            "min_oi_vs_ma":        float(self.get_param("min_oi_vs_ma", 1.03)),
            "min_oi_change_pct":   float(self.get_param("min_oi_change_pct", 0.15)),
            "rsi_sell_min":        float(self.get_param("rsi_sell_min", 56)),
            "rsi_buy_max":         float(self.get_param("rsi_buy_max", 44)),
            "sl_atr_mult":         float(self.get_param("sl_atr_mult", 1.2)),
            "min_rr":              float(self.get_param("min_rr", 1.4)),
            "allow_longs":         bool(self.get_param("allow_longs", False)),
            "allow_shorts":        bool(self.get_param("allow_shorts", True)),
        }

    def add_indicators(self, df, p=None):
        p = p or self._params_snapshot()
        df["RSI_14"] = ta.rsi(df["close"], length=p["rsi_period"])
        df["ATRr_14"] = ta.atr(df["high"], df["low"], df["close"], length=p["atr_period"])
        if "ADX_14" not in df.columns:
            adx_df = ta.adx(df["high"], df["low"], df["close"], length=14)
            df["ADX_14"] = adx_df["ADX"]
        return df

    def _range_position(self, close_price: float, range_low: float, range_high: float) -> float:
        width = range_high - range_low
        if width <= 0:
            return 0.5
        return (close_price - range_low) / width

    def generate_signal(self, df, extra_data=None):
        p = self._params_snapshot()
        if df is None or df.empty or len(df) < max(120, p["range_lookback"] + 5):
            return self._reject("Not enough candles for range crowd fade")

        extra_data = extra_data or {}
        funding_rate = float(extra_data.get("funding_rate", 0.0) or 0.0)

        df = self.add_indicators(df.copy(), p)
        curr = df.iloc[-2]  # confirmed candle
        live = df.iloc[-1]  # execution price context
        window = df.iloc[-(p["range_lookback"] + 2):-2]
        if window.empty:
            return self._reject("Range window unavailable")

        range_high = float(window["high"].max())
        range_low = float(window["low"].min())
        curr_close = float(curr["close"])
        curr_high = float(curr["high"])
        curr_low = float(curr["low"])
        curr_rsi = float(curr.get("RSI_14", 50) or 50)
        curr_atr = float(curr.get("ATRr_14", 0) or 0)
        curr_adx = float(curr.get("ADX_14", 50) or 50)
        oi_vs_ma = float(curr.get("OI_vs_MA", 1.0) or 1.0)
        oi_change = float(curr.get("OI_Change_Pct", 0.0) or 0.0)

        if curr_atr <= 0:
            return self._reject("ATR unavailable or zero")
        if curr_adx > p["adx_max"]:
            return self._reject(f"ADX too high for range fade ({curr_adx:.1f} > {p['adx_max']:.1f})")

        # P5 FIX: Vérification explicite des colonnes OI (calculées dans trading_loop).
        # Si absentes, la stratégie lirait 0.0 et ne se déclencherait jamais silencieusement.
        oi_cols_present = "OI_vs_MA" in curr.index and "OI_Change_Pct" in curr.index
        if not oi_cols_present:
            return self._reject("Colonnes OI (OI_vs_MA / OI_Change_Pct) absentes du df — vérifier l'intégration OI dans trading_loop")

        pos = self._range_position(curr_close, range_low, range_high)

        # Preferred use-case: SELL upper range under crowded longs.
        if p["allow_shorts"]:
            short_crowding_ok = (
                funding_rate >= p["min_funding_short"] and
                oi_vs_ma >= p["min_oi_vs_ma"] and
                oi_change >= p["min_oi_change_pct"]
            )
            short_zone_ok = pos >= p["upper_zone"]
            short_momentum_ok = curr_rsi >= p["rsi_sell_min"]
            rejection_wick_ok = (curr_high - curr_close) >= (0.15 * max(1e-9, (curr_high - curr_low)))

            if short_crowding_ok and short_zone_ok and short_momentum_ok and rejection_wick_ok:
                sl = max(curr_high, range_high) + (p["sl_atr_mult"] * curr_atr)
                risk = sl - curr_close
                if risk > 0:
                    tp = curr_close - (p["min_rr"] * risk)
                    return {
                        "signal": "SELL",
                        "price": float(live["close"]),
                        "sl": float(sl),
                        "tp": float(tp),
                        "comment": (
                            f"Upper-range fade short | funding={funding_rate:.5f} | "
                            f"OIvsMA={oi_vs_ma:.3f} | OIchg={oi_change:.2f}% | pos={pos:.2f}"
                        ),
                        "metadata": {
                            "range_high": round(range_high, 8),
                            "range_low": round(range_low, 8),
                            "range_pos": round(pos, 3),
                            "funding_rate": round(funding_rate, 6),
                            "oi_vs_ma": round(oi_vs_ma, 4),
                            "oi_change_pct": round(oi_change, 3),
                        }
                    }

        # Optional mirror setup: BUY lower range under crowded shorts.
        if p["allow_longs"]:
            long_crowding_ok = (
                funding_rate <= p["max_funding_long"] and
                oi_vs_ma >= p["min_oi_vs_ma"] and
                oi_change >= p["min_oi_change_pct"]
            )
            long_zone_ok = pos <= p["lower_zone"]
            long_momentum_ok = curr_rsi <= p["rsi_buy_max"]
            rejection_wick_ok = (curr_close - curr_low) >= (0.15 * max(1e-9, (curr_high - curr_low)))

            if long_crowding_ok and long_zone_ok and long_momentum_ok and rejection_wick_ok:
                sl = min(curr_low, range_low) - (p["sl_atr_mult"] * curr_atr)
                risk = curr_close - sl
                if risk > 0:
                    tp = curr_close + (p["min_rr"] * risk)
                    return {
                        "signal": "BUY",
                        "price": float(live["close"]),
                        "sl": float(sl),
                        "tp": float(tp),
                        "comment": (
                            f"Lower-range fade long | funding={funding_rate:.5f} | "
                            f"OIvsMA={oi_vs_ma:.3f} | OIchg={oi_change:.2f}% | pos={pos:.2f}"
                        ),
                        "metadata": {
                            "range_high": round(range_high, 8),
                            "range_low": round(range_low, 8),
                            "range_pos": round(pos, 3),
                            "funding_rate": round(funding_rate, 6),
                            "oi_vs_ma": round(oi_vs_ma, 4),
                            "oi_change_pct": round(oi_change, 3),
                        }
                    }

        return self._reject("No range-crowding contrarian setup")

