"""
SuperTrend-first market scanner.

Ranks Hyperliquid perps by how well they match the live SuperTrend 15m setup
(EMA filter + SuperTrend direction + ADX + volume/RSI guards). Does not fetch
1m triggers — that stays in the trading loop after auto-switch.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.services.hyperliquid_service import hyperliquid_service
from app.services.indicators import ta


DEFAULT_ST_PARAMS = {
    "period": 10,
    "multiplier": 3.0,
    "ema_filter_period": 200,
    "adx_threshold": 18.0,
    "min_volume_ratio_pct": 60.0,
    "rsi_neutral_low": 46.0,
    "rsi_neutral_high": 54.0,
}


class SupertrendScanner:
    """Cross-sectional scanner scored on SuperTrend context quality."""

    BASE_MAX_TOKENS = 40
    CACHE_DURATION = 300
    TOKEN_CACHE_DURATION = 300
    CANDLE_LIMIT = 260
    CANDLE_INTERVAL = "15m"
    INTER_SYMBOL_SLEEP = 0.35

    def __init__(
        self,
        st_params: Optional[Dict[str, Any]] = None,
        min_volume_24h: float = 2_000_000.0,
        min_open_interest: float = 1_000_000.0,
        max_tokens: int = BASE_MAX_TOKENS,
        funding_filter_enabled: bool = False,
        max_funding_long: float = 0.001,
        min_funding_short: float = -0.001,
    ):
        self.st_params = {**DEFAULT_ST_PARAMS, **(st_params or {})}
        self.min_volume_24h = float(min_volume_24h)
        self.min_open_interest = float(min_open_interest)
        self.max_tokens = int(max_tokens)
        self.funding_filter_enabled = bool(funding_filter_enabled)
        self.max_funding_long = float(max_funding_long)
        self.min_funding_short = float(min_funding_short)

        self._cache: List[Dict[str, Any]] = []
        self._cache_time = 0.0
        self._token_cache: Dict[str, Dict[str, Any]] = {}

    def update_settings(
        self,
        st_params: Optional[Dict[str, Any]] = None,
        min_volume_24h: Optional[float] = None,
        min_open_interest: Optional[float] = None,
        max_tokens: Optional[int] = None,
        funding_filter_enabled: Optional[bool] = None,
        max_funding_long: Optional[float] = None,
        min_funding_short: Optional[float] = None,
    ):
        if st_params:
            self.st_params = {**DEFAULT_ST_PARAMS, **st_params}
        if min_volume_24h is not None:
            self.min_volume_24h = float(min_volume_24h)
        if min_open_interest is not None:
            self.min_open_interest = float(min_open_interest)
        if max_tokens is not None:
            self.max_tokens = int(max_tokens)
        if funding_filter_enabled is not None:
            self.funding_filter_enabled = bool(funding_filter_enabled)
        if max_funding_long is not None:
            self.max_funding_long = float(max_funding_long)
        if min_funding_short is not None:
            self.min_funding_short = float(min_funding_short)

    def get_market_data(self) -> Dict[str, Any]:
        """Bulk mark/volume/OI/funding from Hyperliquid meta_and_asset_ctxs."""
        try:
            market_data = hyperliquid_service.info.meta_and_asset_ctxs()
            meta = market_data[0]
            contexts = market_data[1]
            token_data: Dict[str, Any] = {}
            for i, asset in enumerate(meta.get("universe", [])):
                symbol = asset.get("name")
                if not symbol or i >= len(contexts):
                    continue
                ctx = contexts[i]
                mark_px = float(ctx.get("markPx", 0) or 0)
                oi_coins = float(ctx.get("openInterest", 0) or 0)
                token_data[symbol] = {
                    "symbol": symbol,
                    "volume_24h": float(ctx.get("dayNtlVlm", 0) or 0),
                    "mark_price": mark_px,
                    "prev_day_px": float(ctx.get("prevDayPx", 0) or 0),
                    "funding": float(ctx.get("funding", 0) or 0),
                    "open_interest": oi_coins * mark_px if mark_px > 0 else 0.0,
                }
            return token_data
        except Exception as e:
            print(f"❌ SupertrendScanner market data error: {e}")
            return {}

    def filter_candidates(self, token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        candidates = []
        for symbol, data in token_data.items():
            if data["volume_24h"] < self.min_volume_24h:
                continue
            if data["open_interest"] < self.min_open_interest:
                continue
            if self.funding_filter_enabled:
                funding = data.get("funding", 0.0)
                # Extreme crowded funding is risky for fresh entries either side.
                if funding > self.max_funding_long or funding < self.min_funding_short:
                    continue
            prev = data.get("prev_day_px") or 0
            if prev > 0:
                data["momentum_24h"] = ((data["mark_price"] - prev) / prev) * 100.0
            else:
                data["momentum_24h"] = 0.0
            candidates.append(data)
        candidates.sort(key=lambda d: d["volume_24h"], reverse=True)
        return candidates

    def score_dataframe(self, df: pd.DataFrame, market: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Score a 15m OHLCV frame with live SuperTrend params.
        Returns None when there is no usable SuperTrend-aligned bias.
        """
        p = self.st_params
        period = int(p.get("period", 10))
        multiplier = float(p.get("multiplier", 3.0))
        ema_len = int(p.get("ema_filter_period", 200))
        adx_threshold = float(p.get("adx_threshold", 18.0))
        min_vol_pct = float(p.get("min_volume_ratio_pct", 60.0))
        rsi_lo = float(p.get("rsi_neutral_low", 46.0))
        rsi_hi = float(p.get("rsi_neutral_high", 54.0))

        min_bars = max(ema_len + 10, period + 30, 60)
        if df is None or df.empty or len(df) < min_bars:
            return None

        work = df.copy()
        work["EMA_FILTER"] = ta.ema(work["close"], length=ema_len)
        work["ADX_14"] = ta.adx(work["high"], work["low"], work["close"])["ADX"]
        st = ta.supertrend(work["high"], work["low"], work["close"], period=period, multiplier=multiplier)
        work["Supertrend"] = st["Supertrend"]
        work["ST_Direction"] = np.where(work["close"] >= work["Supertrend"], 1, -1)
        work["RSI_14"] = ta.rsi(work["close"], length=14)
        work["ATR_14"] = ta.atr(work["high"], work["low"], work["close"], length=14)

        last = work.iloc[-2]
        close = float(last["close"])
        ema = float(last["EMA_FILTER"])
        adx = float(last["ADX_14"])
        st_dir = int(last["ST_Direction"])
        st_line = float(last["Supertrend"])
        atr = float(last["ATR_14"]) if not pd.isna(last["ATR_14"]) else 0.0
        rsi = float(last["RSI_14"]) if not pd.isna(last["RSI_14"]) else 50.0
        max_ext = float(p.get("max_extension_atr", 1.4))

        if any(np.isnan(x) for x in (close, ema, adx, st_line)):
            return None
        if adx < adx_threshold:
            return None

        if close > ema and st_dir == 1:
            bias = "LONG"
            trend = "UP"
        elif close < ema and st_dir == -1:
            bias = "SHORT"
            trend = "DOWN"
        else:
            return None

        # Prefer pullback-ready locations: skip parabolic extensions for rotation
        if atr > 0:
            extension_atr = abs(close - st_line) / atr
            if extension_atr > max_ext:
                return None
        else:
            extension_atr = 99.0

        vol_ratio_pct = None
        if "volume" in work.columns:
            try:
                vol_now = float(work["volume"].iloc[-2])
                vol_ma = float(work["volume"].iloc[:-1].rolling(50).mean().iloc[-2])
                if vol_ma > 0:
                    vol_ratio_pct = (vol_now / vol_ma) * 100.0
            except Exception:
                vol_ratio_pct = None

        # Thin + neutral RSI = stop-hunt risk (same guard as StrategySupertrend)
        if (
            vol_ratio_pct is not None
            and vol_ratio_pct < min_vol_pct
            and rsi_lo <= rsi <= rsi_hi
        ):
            return None

        reasons: List[str] = []
        score = 0.0

        # ADX strength above threshold (max 40)
        adx_edge = max(0.0, adx - adx_threshold)
        adx_pts = min(40.0, 20.0 + adx_edge * 2.0)
        score += adx_pts
        reasons.append(f"ADX {adx:.1f} (≥{adx_threshold:.0f})")

        # Aligned SuperTrend + EMA filter (30)
        score += 30.0
        reasons.append(f"15m {bias}: price vs EMA{ema_len} + ST")

        # Volume confirmation (max 15)
        if vol_ratio_pct is None:
            score += 5.0
        elif vol_ratio_pct >= min_vol_pct:
            vol_pts = min(15.0, 8.0 + (vol_ratio_pct - min_vol_pct) * 0.05)
            score += vol_pts
            reasons.append(f"Vol {vol_ratio_pct:.0f}% of MA50")
        else:
            score += 3.0
            reasons.append(f"Vol thin ({vol_ratio_pct:.0f}%) but RSI not neutral")

        # RSI not stuck in dead zone (10)
        if rsi < rsi_lo or rsi > rsi_hi:
            score += 10.0
            reasons.append(f"RSI {rsi:.0f} outside neutral band")
        else:
            score += 3.0

        # Prefer setups still near the SuperTrend line (pullback-ready) (max 15)
        dist_pct = abs(close - st_line) / close * 100.0 if close else 99.0
        if extension_atr <= 0.8:
            score += 15.0
            reasons.append(f"Pullback zone ({extension_atr:.2f}x ATR / {dist_pct:.2f}%)")
        elif extension_atr <= 1.2:
            score += 10.0
            reasons.append(f"Near ST ({extension_atr:.2f}x ATR)")
        else:
            score += 4.0
            reasons.append(f"Acceptable extension ({extension_atr:.2f}x ATR)")

        score = float(min(100.0, round(score, 1)))
        market = market or {}
        return {
            "symbol": market.get("symbol"),
            "score": score,
            "bias": bias,
            "trend": trend,
            "adx": round(adx, 2),
            "rsi": round(rsi, 2),
            "st_direction": st_dir,
            "ema_filter": round(ema, 8),
            "supertrend": round(st_line, 8),
            "current_price": round(close, 8),
            "volume_ratio_pct": round(vol_ratio_pct, 1) if vol_ratio_pct is not None else None,
            "volume_24h": market.get("volume_24h", 0),
            "open_interest": market.get("open_interest", 0),
            "funding": market.get("funding", 0),
            "momentum_24h": market.get("momentum_24h", 0),
            "reasons": reasons,
            "st_params": {
                "period": period,
                "multiplier": multiplier,
                "ema_filter_period": ema_len,
                "adx_threshold": adx_threshold,
            },
        }

    def analyze_token(self, symbol: str, market: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        now = time.time()
        cached = self._token_cache.get(symbol)
        if cached and (now - cached["timestamp"]) < self.TOKEN_CACHE_DURATION:
            return cached["data"]

        try:
            df = hyperliquid_service.get_candles(symbol, self.CANDLE_INTERVAL, limit=self.CANDLE_LIMIT)
            payload = self.score_dataframe(df, market={**(market or {}), "symbol": symbol})
            self._token_cache[symbol] = {"data": payload, "timestamp": now}
            return payload
        except Exception as e:
            print(f"⚠️ SupertrendScanner analyze {symbol}: {e}")
            self._token_cache[symbol] = {"data": None, "timestamp": now}
            return None

    def scan(self, top_n: int = 10, whitelist: Optional[List[str]] = None, force: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force and self._cache and (now - self._cache_time) < self.CACHE_DURATION:
            return self._cache[:top_n]

        market = self.get_market_data()
        if not market:
            return []

        candidates = self.filter_candidates(market)
        if whitelist:
            wl = {w.upper().replace("-USD", "").replace("-USDC", "") for w in whitelist}
            filtered = []
            for c in candidates:
                sym = c["symbol"].upper()
                bare = sym[1:] if sym.startswith("K") and len(sym) > 2 else sym
                if sym in wl or bare in wl:
                    filtered.append(c)
            candidates = filtered

        limit = min(self.max_tokens, len(candidates))
        deep = candidates[:limit]
        print(
            f"🕵️ SupertrendScanner: {len(candidates)} liquid → deep-scan {limit} "
            f"(vol≥${self.min_volume_24h/1e6:.1f}M OI≥${self.min_open_interest/1e6:.1f}M)"
        )

        results: List[Dict[str, Any]] = []
        for i, data in enumerate(deep):
            symbol = data["symbol"]
            opp = self.analyze_token(symbol, market=data)
            if opp and opp.get("score") is not None:
                results.append(opp)
            if i < len(deep) - 1:
                time.sleep(self.INTER_SYMBOL_SLEEP)

        results.sort(key=lambda o: o.get("score", 0), reverse=True)
        self._cache = results
        self._cache_time = now
        print(f"✅ SupertrendScanner: {len(results)} ST-aligned setups (top={results[0]['symbol'] if results else 'none'})")
        return results[:top_n]
