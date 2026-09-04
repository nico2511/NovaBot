"""
Market universe helper for strategy-owned scanners.

Builds liquid Hyperliquid perp candidates (volume / OI / funding filters) and
fetches OHLCV. Scoring belongs on each strategy via ``score_scan_candidate`` —
this module does not rank setups by métier rules.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from app.services.hyperliquid_service import hyperliquid_service


class SupertrendScanner:
    """Universe + candle fetch (legacy name kept for imports / settings wiring)."""

    BASE_MAX_TOKENS = 50
    CACHE_DURATION = 300
    TOKEN_CACHE_DURATION = 300
    CANDLE_LIMIT = 260
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
        # st_params retained for backward-compat callers; unused for scoring.
        self.st_params = dict(st_params or {})
        self.min_volume_24h = float(min_volume_24h)
        self.min_open_interest = float(min_open_interest)
        self.max_tokens = int(max_tokens)
        self.funding_filter_enabled = bool(funding_filter_enabled)
        self.max_funding_long = float(max_funding_long)
        self.min_funding_short = float(min_funding_short)

        self._candle_cache: Dict[str, Dict[str, Any]] = {}

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
        if st_params is not None:
            self.st_params = dict(st_params)
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
            print(f"❌ MarketUniverse market data error: {e}")
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

    def build_universe(self, whitelist: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Liquid candidates, optionally filtered by whitelist, capped at max_tokens."""
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
        return candidates[:limit]

    def get_candles(
        self,
        symbol: str,
        interval: str = "15m",
        limit: int = CANDLE_LIMIT,
        force: bool = False,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV with a short TTL cache keyed by (symbol, interval)."""
        key = f"{symbol}|{interval}|{limit}"
        now = time.time()
        cached = self._candle_cache.get(key)
        if (
            not force
            and cached
            and (now - cached["timestamp"]) < self.TOKEN_CACHE_DURATION
        ):
            return cached["data"]
        try:
            df = hyperliquid_service.get_candles(symbol, interval, limit=limit)
            self._candle_cache[key] = {"data": df, "timestamp": now}
            return df
        except Exception as e:
            print(f"⚠️ Candle fetch {symbol} {interval}: {e}")
            self._candle_cache[key] = {"data": None, "timestamp": now}
            return None

    def score_dataframe(self, df: pd.DataFrame, market: Optional[Dict[str, Any]] = None):
        """
        Backward-compat wrapper: score via StrategySupertrend plan.
        Prefer calling strategy.score_scan_candidate directly from ScannerJob.
        """
        from strategies.supertrend import StrategySupertrend

        strat = StrategySupertrend({"params": {**self.st_params}})
        strat.name = "supertrend"
        symbol = (market or {}).get("symbol") or "UNKNOWN"
        return strat.score_scan_candidate(df, symbol=symbol, meta=market)

    def scan(self, top_n: int = 10, whitelist: Optional[List[str]] = None, force: bool = False):
        """
        Legacy ST-only scan (tests / manual). Prefer ScannerJob multi-lane path.
        """
        from strategies.supertrend import StrategySupertrend

        deep = self.build_universe(whitelist=whitelist)
        print(
            f"🕵️ Universe: deep-scan {len(deep)} "
            f"(vol≥${self.min_volume_24h/1e6:.1f}M OI≥${self.min_open_interest/1e6:.1f}M)"
        )
        strat = StrategySupertrend({"params": {**self.st_params}})
        strat.name = "supertrend"
        results: List[Dict[str, Any]] = []
        for i, data in enumerate(deep):
            symbol = data["symbol"]
            df = self.get_candles(symbol, "15m", force=force)
            opp = strat.score_scan_candidate(df, symbol=symbol, meta=data) if df is not None else None
            if opp and opp.get("score") is not None:
                results.append(opp)
            if i < len(deep) - 1:
                time.sleep(self.INTER_SYMBOL_SLEEP)
        results.sort(key=lambda o: o.get("score", 0), reverse=True)
        return results[:top_n]
