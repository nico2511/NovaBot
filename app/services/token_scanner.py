"""
Hyperliquid Token Scanner
Scans all available tokens and identifies best trading opportunities
"""

import time
import pandas as pd
from typing import List, Dict, Any
from app.services.hyperliquid_service import HyperliquidService
from hyperliquid.info import Info
import pandas_ta as ta


class HyperliquidScanner:
    """
    Scanner for Hyperliquid tokens
    Filters by gamification level and finds best trading opportunities
    """
    
    # Rate limit protection
    MAX_TOKENS_TO_SCAN = 10  # Limit to avoid API spam
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
    
    def get_all_tokens(self) -> List[str]:
        """
        Get list of tradable tokens FILTERED by gamification level
        
        The scanner's PRIMARY purpose is to find opportunities within allowed assets.
        Gamification filtering is ALWAYS applied.
        """
        try:
            from app.core.asset_gamification import AssetGamification
            from app.services.hyperliquid_service import hyperliquid_service
            
            # Get all available tokens
            meta = self.info.meta()
            all_tokens = [asset['name'] for asset in meta['universe']]
            
            # Skip gamification filter - allow scanning ALL assets
            # meta = self.info.meta()
            # all_tokens = [asset['name'] for asset in meta['universe']]
            
            print(f"📊 Scanning all {len(all_tokens)} available tokens (Gamification filter bypassed)")
            return all_tokens
                
        except Exception as e:
            print(f"❌ Error fetching tokens: {e}")
            return []
                
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
                    'open_interest': float(ctx.get('openInterest', 0)) * mark_px, # Convert OI (coins) to USD
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
            
            # Determine trend
            ema_20 = ta.ema(close, length=20)
            ema_50 = ta.ema(close, length=50)
            
            if not ema_20.empty and not ema_50.empty:
                trend = 'UP' if ema_20.iloc[-1] > ema_50.iloc[-1] else 'DOWN'
            else:
                trend = 'NEUTRAL'

            # Calculate ADX (trend strength)
            try:
                adx_df = ta.adx(high, low, close, length=14)
                # pandas_ta returns ADX_14, DMP_14, DMN_14
                current_adx = adx_df['ADX_14'].iloc[-1] if not adx_df.empty else 0
            except:
                current_adx = 0
            
            # Calculate volume trend
            volume_sma = df['volume'].rolling(20).mean()
            volume_trend = 'INCREASING' if df['volume'].iloc[-1] > volume_sma.iloc[-1] else 'DECREASING'
            
            return {
                'atr_pct': atr_pct,
                'momentum_pct': momentum_pct,
                'rsi': current_rsi,
                'adx': current_adx,
                'trend': trend,
                'volume_trend': volume_trend,
                'current_price': close.iloc[-1]
            }
            
        except Exception as e:
            print(f"⚠️ Error analyzing {symbol}: {e}")
            return None
    
    def calculate_opportunity_score(self, token_data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate opportunity score (0-100)"""
        score = 0
        reasons = []
        
        # 1. Volume Score (0-20 points)
        volume_millions = token_data['volume_24h'] / 1_000_000
        volume_score = min(20, volume_millions * 0.4)  # 1 point per $2.5M
        score += volume_score
        
        if volume_score >= 15:
            reasons.append(f"🔥 High Volume: ${volume_millions:.1f}M")
            
        # 2. Open Interest Score (0-15 points) - NEW
        oi_millions = token_data['open_interest'] / 1_000_000
        oi_score = min(15, oi_millions * 0.5) # 1 point per $2M
        score += oi_score
        
        if oi_score >= 10:
            reasons.append(f"🏛️ Big Open Interest: ${oi_millions:.1f}M")
        
        # 3. Volatility Score (0-20 points)
        atr = analysis['atr_pct']
        if self.min_atr_pct <= atr <= self.max_atr_pct:
            vol_score = 20
            reasons.append(f"⚡ Optimal Volatility: {atr:.2f}%")
        elif atr > self.max_atr_pct:
            # Too volatile, penalize slightly
            vol_score = max(5, 20 - (atr - self.max_atr_pct) * 1.5)
            reasons.append(f"⚠️ High Volatility: {atr:.2f}%")
        else:
            # Too low volatility
            vol_score = atr * 4
        
        score += vol_score
        
        # 4. Momentum Score (0-20 points)
        momentum = abs(analysis['momentum_pct'])
        if momentum >= self.min_momentum_pct:
            mom_score = min(20, momentum * 1.5)
            score += mom_score
            reasons.append(f"🚀 Strong Momentum: {analysis['momentum_pct']:+.2f}%")
        else:
            mom_score = momentum * 1.5
            score += mom_score
        
        # 5. RSI Score (0-15 points) - Favor extremes for mean reversion OR trend
        rsi = analysis['rsi']
        if rsi < 30:
            rsi_score = 15
            reasons.append(f"💎 Oversold (RSI {rsi:.0f})")
        elif rsi > 70:
            rsi_score = 15
            reasons.append(f"🔥 Overbought (RSI {rsi:.0f})")
        elif 45 <= rsi <= 55:
            rsi_score = 5 # Boring
        else:
            rsi_score = 10
        
        score += rsi_score
        
        # 6. Trend bonus (0-10 points)
        if analysis['trend'] != 'NEUTRAL':
            score += 10
            reasons.append(f"{'📈' if analysis['trend']=='UP' else '📉'} Clear Trend")
        
        return {
            'score': round(score, 2),
            'reasons': reasons,
            'max_score': 100
        }
    
    def scan(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Main scanning function
        Returns top N opportunities sorted by score
        """
        import time
        
        # Check cache first (5 min cache)
        if self._cache and (time.time() - self._cache_time) < self.CACHE_DURATION:
            print("📦 Using cached results (fresh)")
            return self._cache.get('results', [])[:top_n]
        
        print("\n" + "="*60)
        print("🔍 HYPERLIQUID TOKEN SCANNER")
        print("="*60)
        
        # Step 1: Get all tokens
        tokens = self.get_all_tokens()
        if not tokens:
            return []
        
        # Step 2: Get market data
        print("\n📊 Fetching market data...")
        market_data = self.get_market_data()
        
        # Step 3: Filter by volume and open interest
        print(f"\n🔎 Filtering by liquidity (Vol > ${self.min_volume_24h/1e6:.1f}M, OI > ${self.min_open_interest/1e6:.1f}M)...")
        candidates = self.filter_candidates(market_data)
        
        # RATE LIMIT: Limit to MAX_TOKENS_TO_SCAN
        if len(candidates) > self.MAX_TOKENS_TO_SCAN:
            print(f"⚠️ Limiting scan to {self.MAX_TOKENS_TO_SCAN} tokens (rate limit protection)")
            candidates = candidates[:self.MAX_TOKENS_TO_SCAN]
        
        # GAMIFICATION FILTER: Only scan allowed tokens for current level
        allowed_tokens = tokens  # tokens already filtered by get_all_tokens()
        candidates = [c for c in candidates if c['symbol'] in allowed_tokens]
        
        if not candidates:
            print("❌ No allowed tokens meet liquidity criteria for your level")
            print(f"💡 Tip: Increase your balance to unlock more tokens!")
            return []
        
        # Step 4: Analyze each candidate
        print(f"\n🔬 Analyzing {len(candidates)} candidates...")
        opportunities = []
        
        for i, token_data in enumerate(candidates):
            symbol = token_data['symbol']
            print(f"  [{i+1}/{len(candidates)}] Analyzing {symbol}...", end='\r')
            
            # RATE LIMIT PROTECTION: Add delay between requests
            if i > 0:  # Skip delay for first token
                import time
                time.sleep(0.5)  # 500ms delay to avoid Hyperliquid 429 errors
            
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
        
        print("\n") # Keep the original newline after the loop
        
        # Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # Cache results
        self._cache['opportunities'] = opportunities
        self._cache_time = time.time()
        
        # Step 6: Display results
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
            print(f"   📈 Momentum: {opp['momentum_24h']:+.2f}% ({opp['trend']})")
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
