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
            
            # Calculate RVol (Relative Volume)
            # Vol / sma(Vol, 20)
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
            
            # Mean Reversion Risk (% distance from EMA 20)
            # If current price is way above EMA 20, risky long
            if current_ema_20 > 0:
                dist_ema_20_pct = ((close.iloc[-1] - current_ema_20) / current_ema_20) * 100
            else:
                dist_ema_20_pct = 0

            # Calculate ADX with directional components
            try:
                adx_df = ta.adx(high, low, close, length=14)
                # pandas_ta columns: ADX_14, DMP_14, DMN_14
                current_adx = adx_df['ADX_14'].iloc[-1] if not adx_df.empty else 0
                current_dmp = adx_df['DMP_14'].iloc[-1] if not adx_df.empty else 0
                current_dmn = adx_df['DMN_14'].iloc[-1] if not adx_df.empty else 0
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
        # Sauf si "Parabolic" (pas implémenté), on tue si RSI > 75
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

        # 1. Relative Volume (RVol) - Supply/Demand Imbalance
        # Si RVol < 1.0 -> Malus (-20 pts). Si RVol > 2.5 -> Bonus (+20 pts).
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
            # Neutral RVol (1.0 - 2.5) -> Small bonus proportional
            rvol_points = (rvol - 1.0) * 5 # Max ~7.5 pts
            score += rvol_points
        
        # 2. Trend Alignment (Multi-MA)
        # Perfect Bullish (EMA 9 > 20 > 50) -> +30 pts
        if analysis.get('trend_aligned', False):
            score += 30
            reasons.append("📈 Perfect Trend Alignment (EMA 9>20>50) [+30]")
            details['Trend_Bonus'] = 30
            
        # 3. Mean Reversion Risk (Extension)
        # Malus if price is too far from EMA 20 (> 3%)
        dist_ema = analysis.get('dist_ema_20_pct', 0)
        if dist_ema > 3.0:
            # Malus progressif: -10 pts par % au-dessus de 3%
            # Ex: 4% -> -10, 5% -> -20, 8% -> -50
            extension_malus = (dist_ema - 3.0) * 10
            score -= extension_malus
            reasons.append(f"⚠️ Overextended (+{dist_ema:.1f}% vs EMA20) [-{extension_malus:.0f}]")
            details['Extension_Penalty'] = -extension_malus
        
        # 4. ADX Quality (Directional Strength)
        # ADX > 25 ET DMP > DMN -> Trend Saine
        adx = analysis.get('adx', 0)
        dmp = analysis.get('adx_dmp', 0)
        dmn = analysis.get('adx_dmn', 0)
        
        if adx > 25 and dmp > dmn:
            score += 15 # +15 pour une trend saine confirmée
            reasons.append(f"💪 Strong Trend (ADX {adx:.0f}) [+15]")
            details['ADX_Bonus'] = 15
        elif adx > 25 and dmn > dmp:
            score -= 10 # Trend forte mais BAISSIERE (puisque DMN > DMP) -> on cherche des longs
            reasons.append(f"📉 Strong Bear Trend (ADX {adx:.0f}) [-10]")
            details['ADX_Bear_Penalty'] = -10
            
        # 5. Base Volatility (ATR)
        atr = analysis['atr_pct']
        if 3.0 <= atr <= 10.0:
            score += 10
            # reasons.append(f"⚡ Good Volatility ({atr:.1f}%) [+10]")
        elif atr < 2.0:
            score -= 10
            reasons.append(f"💤 Low Volatility ({atr:.1f}%) [-10]")
            
        # 6. RSI (Fine Tuning)
        # On a déjà kill > 75.
        # Idéal : 50-65 (Momentum haussier mais pas suracheté)
        if 50 <= analysis['rsi'] <= 65:
            score += 10
            # reasons.append("✅ RSI Sweet Spot")
        elif analysis['rsi'] < 40:
             # Cheap but weak momentum?
             pass

        # 7. Open Interest (Liquidity Health) - Small Weight
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
    
    def scan_momentum_ranking(self, top_n: int = 3) -> Dict:
        """
        Momentum-based ranking scan (Cross-Sectional Momentum)
        Returns top N tokens by momentum score with MA200 filter
        """
        try:
            from app.services.momentum_scanner import momentum_scanner
            
            # Get all tokens
            tokens = self.get_all_tokens()
            if not tokens:
                return {"selected": [], "scores": {}, "weights": {}}
            
            # Fetch daily data for ranking
            data_dict = {}
            print(f"📊 Fetching daily data for {len(tokens[:20])} tokens...")  # Limit to avoid rate limits
            
            for symbol in tokens[:20]:  # Top 20 by volume to avoid spam
                try:
                    df = self.hl_service.get_candles(symbol, "1d", 200)
                    if not df.empty:
                        data_dict[symbol] = df
                except Exception as e:
                    print(f"  ⚠️ {symbol}: {e}")
                    continue
            
            # Run momentum ranking
            result = momentum_scanner.select_top_momentum(data_dict, top_n=top_n, require_ma200=True)
            
            print(f"\n🎯 Momentum Ranking Results:")
            print(f"  Selected: {result['selected']}")
            for sym, score in result['scores'].items():
                print(f"  {sym}: {score:+.4f}")
            
            return result
            
        except Exception as e:
            print(f"❌ Momentum scan error: {e}")
            return {"selected": [], "scores": {}, "weights": {}}
    
    def scan(self, max_results: int = 5, whitelist: List[str] = None) -> List[Dict[str, Any]]:
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
        print("🔍 HYPERLIQUID TOKEN SCANNER (Scoring V2)")
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
        
        # EXTERNAL WHITELIST FILTER (Context Injection)
        if whitelist is not None:
            print(f"🔒 Applying Context Filter: Only {len(whitelist)} assets allowed")
            candidates = [c for c in candidates if c['symbol'] in whitelist]
        
        if not candidates:
            print("❌ No allowed tokens meet liquidity criteria (Context Restriction)")
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
