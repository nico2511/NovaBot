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
    Scanner for identifying best trading opportunities on Hyperliquid
    """
    
    def __init__(self):
        self.info = Info(skip_ws=True)
        self.hl_service = HyperliquidService()
        
        # Configuration thresholds
        self.min_volume_24h = 1_000_000  # $1M minimum volume
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
            
            # ALWAYS apply gamification filter - this is the scanner's purpose
            try:
                # Get account balance for gamification level
                account_value = hyperliquid_service.get_account_value()
                gam = AssetGamification(account_value)
                
                # Get allowed assets for current level
                allowed_assets = gam.get_allowed_assets()
                
                # Filter tokens to only allowed ones
                filtered_tokens = [token for token in all_tokens if token in allowed_assets]
                
                # Import ACCESS_RULES for display
                from app.core.asset_gamification import ACCESS_RULES
                
                print(f"🎮 Gamification Level: {gam.level.value} (Balance: ${account_value:.2f})")
                print(f"📊 Allowed tokens: {len(filtered_tokens)}/{len(all_tokens)}")
                print(f"🎯 Tiers: {', '.join([tier.value for tier in ACCESS_RULES[gam.level]['allowed_tiers']])}")
                
                if not filtered_tokens:
                    print("⚠️ No tokens available for current level!")
                    return []
                
                return filtered_tokens
                
            except Exception as e:
                print(f"❌ Gamification error: {e}")
                print("⚠️ Scanner requires gamification - cannot proceed")
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
                
                token_data[symbol] = {
                    'symbol': symbol,
                    'volume_24h': float(ctx.get('dayNtlVlm', 0)),
                    'mark_price': float(ctx.get('markPx', 0)),
                    'prev_day_px': float(ctx.get('prevDayPx', 0)),
                    'funding': float(ctx.get('funding', 0)),
                    'open_interest': float(ctx.get('openInterest', 0)),
                }
            
            return token_data
        except Exception as e:
            print(f"❌ Error fetching market data: {e}")
            return {}
    
    def filter_by_volume(self, token_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Filter tokens by minimum volume"""
        candidates = []
        
        for symbol, data in token_data.items():
            if data['volume_24h'] >= self.min_volume_24h:
                # Calculate 24h momentum
                if data['prev_day_px'] > 0:
                    momentum_pct = ((data['mark_price'] - data['prev_day_px']) / data['prev_day_px']) * 100
                else:
                    momentum_pct = 0
                
                data['momentum_24h'] = momentum_pct
                candidates.append(data)
        
        print(f"✅ {len(candidates)} tokens with volume > ${self.min_volume_24h/1e6:.1f}M")
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
        
        # Volume Score (0-30 points)
        volume_millions = token_data['volume_24h'] / 1_000_000
        volume_score = min(30, volume_millions * 0.5)  # 1 point per $2M, max 30
        score += volume_score
        
        if volume_score >= 20:
            reasons.append(f"High volume: ${volume_millions:.1f}M")
        
        # Volatility Score (0-25 points)
        atr = analysis['atr_pct']
        if self.min_atr_pct <= atr <= self.max_atr_pct:
            vol_score = 25
            reasons.append(f"Optimal volatility: {atr:.2f}%")
        elif atr > self.max_atr_pct:
            # Too volatile, penalize
            vol_score = max(0, 25 - (atr - self.max_atr_pct) * 2)
            if vol_score > 0:
                reasons.append(f"High volatility: {atr:.2f}%")
        else:
            # Too low volatility
            vol_score = atr * 5  # Scale up low volatility
        
        score += vol_score
        
        # Momentum Score (0-25 points)
        momentum = abs(analysis['momentum_pct'])
        if momentum >= self.min_momentum_pct:
            mom_score = min(25, momentum * 2)
            score += mom_score
            reasons.append(f"Strong momentum: {analysis['momentum_pct']:+.2f}%")
        else:
            mom_score = momentum * 2
            score += mom_score
        
        # RSI Score (0-20 points) - Favor extremes for mean reversion
        rsi = analysis['rsi']
        if rsi < 30:
            rsi_score = 20
            reasons.append(f"RSI oversold: {rsi:.0f}")
        elif rsi > 70:
            rsi_score = 20
            reasons.append(f"RSI overbought: {rsi:.0f}")
        elif 40 <= rsi <= 60:
            rsi_score = 15
            reasons.append(f"RSI neutral: {rsi:.0f}")
        else:
            rsi_score = 10
        
        score += rsi_score
        
        # Trend bonus (0-10 points)
        if analysis['trend'] != 'NEUTRAL':
            score += 10
            reasons.append(f"Clear trend: {analysis['trend']}")
        
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
        
        # Step 3: Filter by volume
        print(f"\n🔎 Filtering by volume (min ${self.min_volume_24h/1e6:.1f}M)...")
        candidates = self.filter_by_volume(market_data)
        
        if not candidates:
            print("❌ No tokens meet volume criteria")
            return []
        
        # Step 4: Analyze each candidate
        print(f"\n🔬 Analyzing {len(candidates)} candidates...")
        opportunities = []
        
        for i, token in enumerate(candidates, 1):
            symbol = token['symbol']
            print(f"  [{i}/{len(candidates)}] Analyzing {symbol}...", end='\r')
            
            analysis = self.analyze_token(symbol)
            if not analysis:
                continue
            
            # Calculate score
            scoring = self.calculate_opportunity_score(token, analysis)
            
            opportunities.append({
                **token,
                **analysis,
                **scoring
            })
        
        print("\n")
        
        # Step 5: Sort by score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
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
            print(f"   💰 Volume 24h: ${opp['volume_24h']/1e6:.1f}M")
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
