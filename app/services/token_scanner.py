"""
Hyperliquid Token Scanner - REFACTORED
Scans all available tokens and identifies best trading opportunities
Optimized for k-prefix handling and proper whitelist filtering
"""

import time
import pandas as pd
from typing import List, Dict, Any, Set
from app.services.hyperliquid_service import HyperliquidService
from hyperliquid.info import Info
from app.services.indicators import ta


class HyperliquidScanner:
    """
    Scanner for Hyperliquid tokens
    Filters by gamification level and finds best trading opportunities
    """
    
    # Rate limit protection (INCREASED from 10 to 50)
    MAX_TOKENS_TO_SCAN = 50  # Increased to capture more whitelisted tokens
    CACHE_DURATION = 300  # 5 minutes cache
    
    def __init__(self):
        self.info = Info(skip_ws=True)
        self.hl_service = HyperliquidService()
        
        # Simple cache
        self._cache = {}
        self._cache_time = 0
        
        # Configuration thresholds
        self.min_volume_24h = 10_000_000  # $10M minimum
        self.min_open_interest = 5_000_000 # $5M minimum OI
        self.min_atr_pct = 3.0  # Minimum volatility
        self.max_atr_pct = 8.0  # Maximum volatility
        self.min_momentum_pct = 5.0  # Minimum 24h change
        self.max_spread_pct = 0.1  # Maximum bid/ask spread
    
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
        """Perform technical analysis on a token"""
        try:
            # Get 24h of 15m candles (96 candles)
            df = self.hl_service.get_candles(symbol, "15m", limit=96)
            
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
            
            # Calculate RSI
            rsi_result = ta.rsi(close, length=14)
            current_rsi = rsi_result.iloc[-1] if not rsi_result.empty else 50
            
            # Calculate momentum (24h change)
            momentum_pct = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0]) * 100
            
            # Calculate RVol (Relative Volume)
            vol_sma_20 = df['volume'].rolling(20).mean()
            current_vol = df['volume'].iloc[-1]
            rvol = current_vol / vol_sma_20.iloc[-1] if vol_sma_20.iloc[-1] > 0 else 0
            
            # Calculate EMAs for Trend Alignment
            ema_9 = ta.ema(close, length=9)
            ema_20 = ta.ema(close, length=20)
            ema_50 = ta.ema(close, length=50)
            
            current_ema_9 = ema_9.iloc[-1] if not ema_9.empty else 0
            current_ema_20 = ema_20.iloc[-1] if not ema_20.empty else 0
            current_ema_50 = ema_50.iloc[-1] if not ema_50.empty else 0
            
            # Trend Alignment (Perfect Bullish)
            trend_aligned = (current_ema_9 > current_ema_20 > current_ema_50)
            
            # Mean Reversion Risk
            if current_ema_20 > 0:
                dist_ema_20_pct = ((close.iloc[-1] - current_ema_20) / current_ema_20) * 100
            else:
                dist_ema_20_pct = 0
                
            # Trend Distance (Price vs MA200)
            sma_200 = df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else 0
            if sma_200 == 0 and not ema_50.empty:
                sma_200 = current_ema_50
            
            if sma_200 > 0:
                dist_ma200_pct = ((close.iloc[-1] - sma_200) / sma_200) * 100
            else:
                dist_ma200_pct = 0

            # Calculate ADX with directional components
            try:
                adx_df = ta.adx(high, low, close, length=14)
                current_adx = adx_df['ADX'].iloc[-1] if not adx_df.empty else 0
                current_dmp = adx_df['DMP'].iloc[-1] if not adx_df.empty else 0
                current_dmn = adx_df['DMN'].iloc[-1] if not adx_df.empty else 0
            except:
                current_adx = 0
                current_dmp = 0
                current_dmn = 0
            
            return {
                'atr_pct': atr_pct,
                'momentum_pct': momentum_pct,
                'rsi': current_rsi,
                'adx': current_adx,
                'adx_dmp': current_dmp,
                'adx_dmn': current_dmn,
                'trend_aligned': trend_aligned,
                'rvol': rvol,
                'dist_ema_20_pct': dist_ema_20_pct,
                'dist_ma200_pct': dist_ma200_pct,
                'current_price': close.iloc[-1]
            }
            
        except Exception as e:
            print(f"⚠️ Error analyzing {symbol}: {e}")
            return None
    
    def calculate_opportunity_score(self, token_data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate opportunity score (0-100) - V2 (Dynamic Weights & Veto)
        """
        score = 0
        reasons = []
        details = {}
        
        # --- KILL SWITCHES (Veto) ---
        
        # 1. RSI Extreme (Overbought)
        if analysis['rsi'] > 75:
            return {
                'score': 0, 
                'reasons': [f"⛔ Kill Switch: RSI Overheat ({analysis['rsi']:.0f} > 75)"],
                'max_score': 100
            }
            
        # 2. Low Liquidity
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
        
        # 2. Trend Alignment
        if analysis.get('trend_aligned', False):
            score += 30
            reasons.append("📈 Perfect Trend Alignment (EMA 9>20>50) [+30]")
            details['Trend_Bonus'] = 30
            
        # 3. Mean Reversion Risk
        dist_ema = analysis.get('dist_ema_20_pct', 0)
        if dist_ema > 3.0:
            extension_malus = (dist_ema - 3.0) * 10
            score -= extension_malus
            reasons.append(f"⚠️ Overextended (+{dist_ema:.1f}% vs EMA20) [-{extension_malus:.0f}]")
            details['Extension_Penalty'] = -extension_malus
        
        # 4. ADX Quality
        adx = analysis.get('adx', 0)
        dmp = analysis.get('adx_dmp', 0)
        dmn = analysis.get('adx_dmn', 0)
        
        if adx > 25 and dmp > dmn:
            score += 15
            reasons.append(f"💪 Strong Trend (ADX {adx:.0f}) [+15]")
            details['ADX_Bonus'] = 15
        elif adx > 25 and dmn > dmp:
            score -= 10
            reasons.append(f"📉 Strong Bear Trend (ADX {adx:.0f}) [-10]")
            details['ADX_Bear_Penalty'] = -10
            
        # 5. Base Volatility (ATR)
        atr = analysis['atr_pct']
        if 3.0 <= atr <= 10.0:
            score += 10
        elif atr < 2.0:
            score -= 10
            reasons.append(f"💤 Low Volatility ({atr:.1f}%) [-10]")
            
        # 6. RSI (Fine Tuning)
        if 50 <= analysis['rsi'] <= 65:
            score += 10

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
        Main scanning function - REFACTORED
        
        CRITICAL ORDER OF OPERATIONS:
        1. Get all tokens
        2. Get market data
        3. Apply WHITELIST filter (if provided)
        4. Filter by liquidity (volume + OI)
        5. Limit to MAX_TOKENS_TO_SCAN for deep analysis
        6. Analyze and score
        
        Returns top N opportunities sorted by score
        """
        # Check cache first
        if self._cache and (time.time() - self._cache_time) < self.CACHE_DURATION:
            print("📦 Using cached results (fresh)")
            return self._cache.get('results', [])[:top_n]
        
        print("\n" + "="*60)
        print("🔍 HYPERLIQUID TOKEN SCANNER (Scoring V2 - REFACTORED)")
        print("="*60)
        
        # Step 1: Get all tokens
        tokens = self.get_all_tokens()
        if not tokens:
            return []
        
        # Step 2: Get market data
        print("\n📊 Fetching market data...")
        market_data = self.get_market_data()
        
        # Step 3: WHITELIST FILTER (BEFORE liquidity filter)
        if whitelist is not None:
            print(f"\n🔒 Applying Whitelist Filter: {len(whitelist)} assets allowed")
            filtered_market_data = {}
            for symbol, data in market_data.items():
                if self._is_whitelisted(symbol, whitelist):
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
        
        # Step 5: RATE LIMIT - Limit deep analysis to MAX_TOKENS_TO_SCAN
        if len(candidates) > self.MAX_TOKENS_TO_SCAN:
            print(f"⚠️ Limiting deep analysis to top {self.MAX_TOKENS_TO_SCAN} by volume (rate limit protection)")
            # Sort by volume to prioritize most liquid
            candidates.sort(key=lambda x: x['volume_24h'], reverse=True)
            candidates = candidates[:self.MAX_TOKENS_TO_SCAN]
        
        # Step 6: Analyze each candidate
        print(f"\n🔬 Analyzing {len(candidates)} candidates...")
        opportunities = []
        
        for i, token_data in enumerate(candidates):
            symbol = token_data['symbol']
            print(f"  [{i+1}/{len(candidates)}] Analyzing {symbol}...", end='\r')
            
            # Rate limit protection
            if i > 0:
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
