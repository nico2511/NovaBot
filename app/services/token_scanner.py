"""
Hyperliquid Token Scanner - ENHANCED V3
Scans all available tokens and identifies best trading opportunities
Optimized for k-prefix handling and proper whitelist filtering

ENHANCEMENTS:
- Bear symmetry in scoring (Perfect Bearish = Perfect Bullish inverted)
- Funding rate veto (extreme rates filtered)
- Dynamic MAX_TOKENS_TO_SCAN based on whitelist size
- Per-token cache (5min) to avoid redundant analysis
- Optimized for 5m Timeframe (Responsive)
- ASSET_TIERS integration from gamification module
"""

import time
import pandas as pd
from typing import List, Dict, Any, Set
from app.services.hyperliquid_service import HyperliquidService
from hyperliquid.info import Info
from app.services.indicators import ta
from app.core.asset_gamification import ASSET_TIERS, AssetTier


class HyperliquidScanner:
    """
    Scanner for Hyperliquid tokens
    Filters by gamification level and finds best trading opportunities
    """
    
    # Rate limit protection - Now DYNAMIC (see _calculate_scan_limit)
    BASE_MAX_TOKENS = 30  # Base limit for small whitelists
    CACHE_DURATION = 300  # 5 minutes global cache
    TOKEN_CACHE_DURATION = 300  # 5 minutes per-token cache
    
    def __init__(self, max_funding_long=0.001, min_funding_short=-0.001, funding_filter_enabled=True):
        self.info = Info(skip_ws=True)
        self.hl_service = HyperliquidService()
        
        # Global scan cache
        self._cache = {}
        self._cache_time = 0
        
        # Per-token analysis cache (NEW)
        self._token_cache = {}  # {symbol: {'data': {...}, 'timestamp': float}}
        
        # Funding rate veto thresholds (CONFIGURABLE)
        self.max_funding_long = max_funding_long  # Default: 0.1% (extreme bullish funding = risky long)
        self.min_funding_short = min_funding_short  # Default: -0.1% (extreme bearish funding = risky short)
        self.funding_filter_enabled = funding_filter_enabled
        
        # Configuration thresholds
        self.min_volume_24h = 10_000_000  # $10M minimum
        self.min_open_interest = 5_000_000 # $5M minimum OI
        self.min_atr_pct = 0.3  # Minimum volatility (Adjusted for 5m)
        self.max_atr_pct = 4.0  # Maximum volatility (Adjusted for 5m)
        self.min_momentum_pct = 2.0  # Minimum 24h change (Adjusted for 5m)
        self.max_spread_pct = 0.1  # Maximum bid/ask spread
    
    def _calculate_scan_limit(self, whitelist: List[str] = None) -> int:
        """
        Calculate dynamic MAX_TOKENS_TO_SCAN based on whitelist size
        
        Logic:
        - If no whitelist: Use BASE_MAX_TOKENS (30)
        - If whitelist provided: whitelist_size + 20% margin
        - Cap at 100 to respect API rate limits
        """
        if not whitelist:
            return self.BASE_MAX_TOKENS
        
        # Whitelist size + 20% margin for k-prefix variants
        dynamic_limit = int(len(whitelist) * 1.2)
        
        # Cap at 100 for safety
        max_limit = min(100, dynamic_limit)
        
        print(f"📊 Dynamic scan limit: {max_limit} tokens (whitelist: {len(whitelist)})")
        return max_limit
    
    def _get_combined_whitelist(self, user_whitelist: List[str] = None) -> List[str]:
        """
        Combine user whitelist with ASSET_TIERS if needed
        
        If user provides whitelist, use it as-is.
        Otherwise, combine all ASSET_TIERS for comprehensive scan.
        """
        if user_whitelist is not None:
            return user_whitelist
        
        # Combine all tiers
        combined = []
        for tier in ASSET_TIERS.values():
            combined.extend(tier)
        
        # Remove duplicates
        return list(set(combined))
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol for comparison
        
        Handles:
        - Suffixes: -USD, -USDC
        - Prefix: k (ex: kPEPE -> PEPE)
        - Case normalization
        
        Returns:
            Normalized symbol (ex: "kPEPE-USD" -> "PEPE")
        """
        # Basic cleanup
        s = symbol.upper().replace("-USD", "").replace("-USDC", "").strip()
        
        # Handle k-prefix (Hyperliquid memecoins)
        if s.startswith("K") and len(s) > 2:
            return s[1:]  # Remove 'k' prefix
        
        return s
    
    def _is_whitelisted(self, api_symbol: str, whitelist: List[str]) -> bool:
        """
        Check if a symbol is whitelisted with k-prefix support
        
        Args:
            api_symbol: Symbol from API (may have k-prefix)
            whitelist: List of allowed symbols or None
        
        Returns:
            True if symbol or its normalized version is in whitelist
        """
        if not whitelist:
            return True  # No whitelist = all allowed
        
        # Normalize the API symbol
        normalized = self._normalize_symbol(api_symbol)
        
        # Check both original and normalized
        clean_original = api_symbol.upper().replace("-USD", "").replace("-USDC", "").strip()
        
        # Normalize whitelist items for comparison
        normalized_whitelist = [self._normalize_symbol(w) for w in whitelist]
        
        return normalized in normalized_whitelist or clean_original in normalized_whitelist
    
    def get_all_tokens(self) -> List[str]:
        """
        Get list of ALL tradable tokens from Hyperliquid
        
        Note: Gamification filtering is applied LATER in scan() method
        """
        try:
            meta = self.info.meta()
            all_tokens = [asset['name'] for asset in meta['universe']]
            
            print(f"📊 Fetched {len(all_tokens)} available tokens from Hyperliquid")
            return all_tokens
                
        except Exception as e:
            print(f"❌ Error fetching tokens: {e}")
            return []
    
    def get_market_data(self) -> Dict[str, Any]:
        """Get market data for all tokens"""
        try:
            market_data = self.info.meta_and_asset_ctxs()
            meta = market_data[0]
            contexts = market_data[1]
            
            # Map tokens to their market data
            token_data = {}
            for i, asset in enumerate(meta['universe']):
                symbol = asset['name']
                ctx = contexts[i]
                
                mark_px = float(ctx.get('markPx', 0))
                
                token_data[symbol] = {
                    'symbol': symbol,
                    'volume_24h': float(ctx.get('dayNtlVlm', 0)),
                    'mark_price': mark_px,
                    'prev_day_px': float(ctx.get('prevDayPx', 0)),
                    'funding': float(ctx.get('funding', 0)),
                    'open_interest': float(ctx.get('openInterest', 0)) * mark_px,
                }
            
            return token_data
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")
            return {}
    
    def filter_candidates(self, token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter tokens by minimum volume AND open interest"""
        candidates = []
        
        for symbol, data in token_data.items():
            # Check Volume AND Open Interest
            if data['volume_24h'] >= self.min_volume_24h and data['open_interest'] >= self.min_open_interest:
                # Calculate 24h momentum
                if data['prev_day_px'] > 0:
                    momentum_pct = ((data['mark_price'] - data['prev_day_px']) / data['prev_day_px']) * 100
                else:
                    momentum_pct = 0
                
                data['momentum_24h'] = momentum_pct
                candidates.append(data)
        
        print(f"✅ {len(candidates)} tokens with Volume > ${self.min_volume_24h/1e6:.1f}M & OI > ${self.min_open_interest/1e6:.1f}M")
        return candidates
    
    def analyze_token(self, symbol: str) -> Dict[str, Any]:
        """
        Perform technical analysis on a token with PER-TOKEN CACHE
        
        Cache logic:
        - Check if symbol exists in cache and is fresh (<5min)
        - If yes: return cached data
        - If no: fetch, analyze, cache, return
        """
        # Check per-token cache
        if symbol in self._token_cache:
            cached_entry = self._token_cache[symbol]
            age = time.time() - cached_entry['timestamp']
            
            if age < self.TOKEN_CACHE_DURATION:
                print(f"  💾 Using cached analysis for {symbol} ({age:.0f}s old)", end='\r')
                return cached_entry['data']
        
        # Cache miss or stale - perform analysis
        try:
            # Get 24h of 5m candles (288 candles)
            df = self.hl_service.get_candles(symbol, "5m", limit=288)
            
            if df.empty or len(df) < 20:
                return None
            
            # Calculate ATR
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr = pd.DataFrame({
                'hl': high - low,
                'hc': abs(high - close.shift()),
                'lc': abs(low - close.shift())
            }).max(axis=1)
            
            atr = tr.rolling(14).mean().iloc[-1]
            atr_pct = (atr / close.iloc[-1]) * 100
            
            # Use iloc[-2] for stable technical analysis (Completed Candles)
            stable_close = close.iloc[-2]
            
            # Calculate RSI
            rsi_result = ta.rsi(close, length=14)
            current_rsi = rsi_result.iloc[-2] if not rsi_result.empty else 50
            
            # Calculate momentum (24h change)
            momentum_pct = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0]) * 100
            
            # Calculate RVol (Relative Volume)
            vol_sma_20 = df['volume'].rolling(20).mean()
            current_vol = df['volume'].iloc[-2]
            rvol = current_vol / vol_sma_20.iloc[-2] if vol_sma_20.iloc[-2] > 0 else 0
            
            # Calculate EMAs for Trend Alignment
            ema_9 = ta.ema(close, length=9)
            ema_20 = ta.ema(close, length=20)
            ema_50 = ta.ema(close, length=50)
            
            current_ema_9 = ema_9.iloc[-2] if not ema_9.empty else 0
            current_ema_20 = ema_20.iloc[-2] if not ema_20.empty else 0
            current_ema_50 = ema_50.iloc[-2] if not ema_50.empty else 0
            
            # Trend Alignment (Perfect Bullish OR Bearish)
            trend_aligned_bull = (current_ema_9 > current_ema_20 > current_ema_50)
            trend_aligned_bear = (current_ema_9 < current_ema_20 < current_ema_50)  # NEW
            
            # Mean Reversion Risk
            if current_ema_20 > 0:
                dist_ema_20_pct = ((stable_close - current_ema_20) / current_ema_20) * 100
            else:
                dist_ema_20_pct = 0
                
            # Trend Distance (Price vs MA200)
            sma_200 = df['close'].rolling(200).mean().iloc[-2] if len(df) >= 201 else 0
            if sma_200 == 0 and not ema_50.empty:
                sma_200 = current_ema_50
            
            if sma_200 > 0:
                dist_ma200_pct = ((stable_close - sma_200) / sma_200) * 100
            else:
                dist_ma200_pct = 0

            # Calculate ADX with directional components
            try:
                adx_df = ta.adx(high, low, close, length=14)
                current_adx = adx_df['ADX'].iloc[-2] if not adx_df.empty else 0
                current_dmp = adx_df['DMP'].iloc[-2] if not adx_df.empty else 0
                current_dmn = adx_df['DMN'].iloc[-2] if not adx_df.empty else 0
            except:
                current_adx = 0
                current_dmp = 0
                current_dmn = 0
            
            analysis_result = {
                'atr_pct': atr_pct,
                'momentum_pct': momentum_pct,
                'rsi': current_rsi,
                'adx': current_adx,
                'adx_dmp': current_dmp,
                'adx_dmn': current_dmn,
                'trend_aligned_bull': trend_aligned_bull,
                'trend_aligned_bear': trend_aligned_bear,  # NEW
                'rvol': rvol,
                'dist_ema_20_pct': dist_ema_20_pct,
                'dist_ma200_pct': dist_ma200_pct,
                'current_price': stable_close
            }
            
            # Cache the result
            self._token_cache[symbol] = {
                'data': analysis_result,
                'timestamp': time.time()
            }
            
            return analysis_result
            
        except Exception as e:
            print(f"⚠️ Error analyzing {symbol}: {e}")
            return None
    
    def calculate_opportunity_score(self, token_data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate opportunity score (0-100) - V3 (Bear Symmetry + Funding Veto)
        
        ENHANCEMENTS:
        - Bear symmetry: Perfect bearish trend = inverted bull score
        - Funding rate veto: Extreme rates filtered
        """
        score = 0
        reasons = []
        details = {}
        
        # --- KILL SWITCHES (Veto) ---
        
        # 1. Funding Rate Veto (CONFIGURABLE)
        funding = token_data.get('funding', 0)
        
        if self.funding_filter_enabled:
            # Extreme positive funding = too crowded long (risky to enter long)
            if funding > self.max_funding_long:
                return {
                    'score': 0, 
                    'reasons': [f"⛔ Funding Veto: Extreme Long Crowding ({funding*100:.3f}% > {self.max_funding_long*100:.3f}%)"],
                    'max_score': 100
                }
            
            # Extreme negative funding = too crowded short (risky to enter short)
            # For now we focus on longs, but this could be used for short strategies
            if funding < self.min_funding_short:
                print(f"   ⚠️ {token_data['symbol']}: Extreme short funding ({funding*100:.3f}%) - potential short squeeze")
        
        # 2. RSI Extreme (Overbought)
        if analysis['rsi'] > 75:
            return {
                'score': 0, 
                'reasons': [f"⛔ Kill Switch: RSI Overheat ({analysis['rsi']:.0f} > 75)"],
                'max_score': 100
            }
            
        # 3. Low Liquidity
        volume_millions = token_data['volume_24h'] / 1_000_000
        if volume_millions < 5.0:
             return {
                'score': 0, 
                'reasons': [f"⛔ Kill Switch: Low Volume (${volume_millions:.1f}M < $5M)"],
                'max_score': 100
            }

        # --- SCORING FACTORS ---

        # 1. Relative Volume (RVol)
        rvol = analysis.get('rvol', 0)
        if rvol > 2.5:
            score += 20
            reasons.append(f"🔥 High RVol ({rvol:.1f}x) [+20]")
            details['RVol_Bonus'] = 20
        elif rvol < 1.0:
            score -= 20
            reasons.append(f"❄️ Low RVol ({rvol:.1f}x) [-20]")
            details['RVol_Penalty'] = -20
        else:
            rvol_points = (rvol - 1.0) * 5
            score += rvol_points
        
        # 2. Trend Alignment (ENHANCED: Bear Symmetry)
        if analysis.get('trend_aligned_bull', False):
            score += 30
            reasons.append("📈 Perfect Bull Trend (EMA 9>20>50) [+30]")
            details['Trend_Bonus'] = 30
        elif analysis.get('trend_aligned_bear', False):
            # Bear symmetry: Perfect bearish = good for shorts (inverted scoring)
            # For now, we penalize since we focus on longs
            score -= 15
            reasons.append("📉 Perfect Bear Trend (EMA 9<20<50) [-15]")
            details['Bear_Trend_Penalty'] = -15
            
        # 3. Mean Reversion Risk
        dist_ema = analysis.get('dist_ema_20_pct', 0)
        if dist_ema > 3.0:
            extension_malus = (dist_ema - 3.0) * 10
            score -= extension_malus
            reasons.append(f"⚠️ Overextended (+{dist_ema:.1f}% vs EMA20) [-{extension_malus:.0f}]")
            details['Extension_Penalty'] = -extension_malus
        elif dist_ema < -3.0:
            # Underextended (potential bounce for longs)
            bounce_bonus = abs(dist_ema + 3.0) * 5
            score += bounce_bonus
            reasons.append(f"💎 Underextended ({dist_ema:.1f}% vs EMA20) [+{bounce_bonus:.0f}]")
            details['Bounce_Bonus'] = bounce_bonus
        
        # 4. ADX Quality
        adx = analysis.get('adx', 0)
        dmp = analysis.get('adx_dmp', 0)
        dmn = analysis.get('adx_dmn', 0)
        
        if adx > 25 and dmp > dmn:
            score += 15
            reasons.append(f"💪 Strong Bull Trend (ADX {adx:.0f}) [+15]")
            details['ADX_Bonus'] = 15
        elif adx > 25 and dmn > dmp:
            score -= 10
            reasons.append(f"📉 Strong Bear Trend (ADX {adx:.0f}) [-10]")
            details['ADX_Bear_Penalty'] = -10
            
        # 5. Base Volatility (ATR)
        atr = analysis['atr_pct']
        if 0.3 <= atr <= 3.0:
            score += 10
        elif atr < 0.1:
            score -= 10
            reasons.append(f"💤 Low Volatility ({atr:.1f}%) [-10]")
            
        # 6. RSI (Fine Tuning)
        if 50 <= analysis['rsi'] <= 65:
            score += 10
        elif analysis['rsi'] < 30:
            # Oversold = potential bounce
            score += 5
            reasons.append(f"💎 Oversold RSI ({analysis['rsi']:.0f}) [+5]")

        # 7. Open Interest
        oi_millions = token_data['open_interest'] / 1_000_000
        if oi_millions > 10:
            score += 5
        
        # --- FINAL CLAMP ---
        score = max(0, min(100, score))
        
        return {
            'score': round(score, 2),
            'reasons': reasons,
            'details': details,
            'max_score': 100
        }
    
    def scan(self, top_n: int = 10, whitelist: List[str] = None) -> List[Dict[str, Any]]:
        """
        Main scanning function - ENHANCED V3
        
        CRITICAL ORDER OF OPERATIONS:
        1. Get all tokens
        2. Get market data
        3. Apply WHITELIST filter (if provided)
        4. Filter by liquidity (volume + OI)
        5. Limit to DYNAMIC MAX_TOKENS_TO_SCAN for deep analysis
        6. Analyze and score (with per-token cache)
        
        Returns top N opportunities sorted by score
        """
        # Check global cache first
        if self._cache and (time.time() - self._cache_time) < self.CACHE_DURATION:
            print("📦 Using cached results (fresh)")
            return self._cache.get('results', [])[:top_n]
        
        print("\n" + "="*60)
        print("🔍 HYPERLIQUID TOKEN SCANNER V3 (Bear Symmetry + Funding Veto)")
        print("="*60)
        
        # Step 1: Get all tokens
        tokens = self.get_all_tokens()
        if not tokens:
            return []
        
        # Step 2: Get market data
        print("\n📊 Fetching market data...")
        market_data = self.get_market_data()
        
        # Step 3: WHITELIST FILTER (BEFORE liquidity filter)
        # Use combined whitelist if user didn't provide one
        effective_whitelist = self._get_combined_whitelist(whitelist)
        
        if effective_whitelist:
            print(f"\n🔒 Applying Whitelist Filter: {len(effective_whitelist)} assets allowed")
            filtered_market_data = {}
            for symbol, data in market_data.items():
                if self._is_whitelisted(symbol, effective_whitelist):
                    filtered_market_data[symbol] = data
            
            print(f"   ✅ {len(filtered_market_data)} tokens matched whitelist")
            market_data = filtered_market_data
        
        if not market_data:
            print("❌ No tokens passed whitelist filter")
            return []
        
        # Step 4: Filter by liquidity
        print(f"\n🔎 Filtering by liquidity (Vol > ${self.min_volume_24h/1e6:.1f}M, OI > ${self.min_open_interest/1e6:.1f}M)...")
        candidates = self.filter_candidates(market_data)
        
        if not candidates:
            print("❌ No tokens meet liquidity criteria")
            return []
        
        # Step 5: DYNAMIC RATE LIMIT
        max_tokens_to_scan = self._calculate_scan_limit(effective_whitelist)
        
        if len(candidates) > max_tokens_to_scan:
            print(f"⚠️ Limiting deep analysis to top {max_tokens_to_scan} by volume (dynamic rate limit)")
            # Sort by volume to prioritize most liquid
            candidates.sort(key=lambda x: x['volume_24h'], reverse=True)
            candidates = candidates[:max_tokens_to_scan]
        
        # Step 6: Analyze each candidate (with per-token cache)
        print(f"\n🔬 Analyzing {len(candidates)} candidates (with per-token cache)...")
        opportunities = []
        
        for i, token_data in enumerate(candidates):
            symbol = token_data['symbol']
            print(f"  [{i+1}/{len(candidates)}] Analyzing {symbol}...", end='\r')
            
            # Rate limit protection (only if not using cache)
            if i > 0 and symbol not in self._token_cache:
                time.sleep(0.5)
            
            analysis = self.analyze_token(symbol)
            
            if analysis:
                opportunity = self.calculate_opportunity_score(token_data, analysis)
                opportunity['symbol'] = symbol
                opportunity['volume_24h'] = token_data['volume_24h']
                opportunity['mark_price'] = token_data['mark_price']
                opportunity['prev_day_px'] = token_data['prev_day_px']
                opportunity['funding'] = token_data['funding']
                opportunity['open_interest'] = token_data['open_interest']
                opportunity['momentum_24h'] = token_data['momentum_24h']
                opportunity.update(analysis)
                opportunities.append(opportunity)
        
        print("\n")
        
        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # Cache results
        self._cache['results'] = opportunities
        self._cache_time = time.time()
        
        # Display results
        self.display_results(opportunities[:top_n])
        
        return opportunities[:top_n]
    
    def display_results(self, opportunities: List[Dict[str, Any]]):
        """Display scan results in a nice format"""
        print("\n" + "="*60)
        print(f"🏆 TOP {len(opportunities)} OPPORTUNITIES")
        print("="*60)
        
        for i, opp in enumerate(opportunities, 1):
            # Star rating based on score
            if opp['score'] >= 80:
                stars = "⭐⭐⭐"
            elif opp['score'] >= 60:
                stars = "⭐⭐"
            else:
                stars = "⭐"
            
            print(f"\n{i}. {opp['symbol']} (Score: {opp['score']:.0f}/100) {stars}")
            print(f"   💰 Volume: ${opp['volume_24h']/1e6:.1f}M | OI: ${opp['open_interest']/1e6:.1f}M")
            print(f"   📈 Momentum: {opp['momentum_24h']:+.2f}%")
            print(f"   💸 Funding: {opp['funding']*100:.3f}%")
            print(f"   📊 ATR: {opp['atr_pct']:.2f}%")
            print(f"   🎯 RSI: {opp['rsi']:.0f}")
            print(f"   💵 Price: ${opp['current_price']:.4f}")
            
            if opp['reasons']:
                print(f"   ✅ Reasons:")
                for reason in opp['reasons']:
                    print(f"      - {reason}")
        
        print("\n" + "="*60)
    
    def get_best_asset(self) -> str:
        """Get the single best asset to trade"""
        opportunities = self.scan(top_n=1)
        if opportunities:
            return opportunities[0]['symbol']
        return 'BTC'  # Default fallback


if __name__ == "__main__":
    # Test the scanner
    scanner = HyperliquidScanner()
    top_opportunities = scanner.scan(top_n=10)
    
    if top_opportunities:
        print(f"\n🎯 Best asset to trade: {top_opportunities[0]['symbol']}")
