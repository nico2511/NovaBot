import threading
import time
from datetime import datetime
from app.services.token_scanner import HyperliquidScanner
from app.services.discord_service import discord_service
from app.core.state_manager import StateManager

class ScannerJob:
    def __init__(self, bot_context):
        self.bot = bot_context
        self.is_running = False
        self.thread = None
        self.last_scan_time = 0
        self.scanner = HyperliquidScanner()
        self.last_results = [] # Store last scan results for UI
        self.is_scanning = False # Status flag
        
    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print("🔍 ScannerJob started")

    def stop(self):
        self.is_running = False
        if self.thread:
            try:
                self.thread.join(timeout=2)
            except: pass
        print("⏹️ ScannerJob stopped")

    def _run_loop(self):
        while self.is_running:
            try:
                # Check settings
                settings = getattr(self.bot, 'scanner_settings', {})
                enabled = settings.get('enabled', False)
                interval_minutes = settings.get('interval', 15)
                min_score = settings.get('min_score', 75)  # Back to 75 (quality over quantity)
                auto_switch = settings.get('auto_switch', False)

                if not enabled:
                    time.sleep(10)
                    continue

                # Check interval
                now = time.time()
                if now - self.last_scan_time < (interval_minutes * 60):
                    time.sleep(10)
                    continue

                # RUN SCAN
                # RUN SCAN
                self.last_scan_time = now
                self.bot.add_log(f"🕵️ Running periodic scan (Interval: {interval_minutes}m)")
                self.is_scanning = True
                
                # --- CONTEXT RESOLVER (Gamification / Auto-Switch Scope) ---
                from app.core.constants import GAMIFICATION_ENABLED
                from app.core.config import config
                
                whitelist = None
                
                if GAMIFICATION_ENABLED:
                    try:
                        from app.core.asset_gamification import AssetGamification
                        # Fetch equity to determine tier
                        # We can use the bot's bridge or scanner's internal service
                        balance_data = self.scanner.hl_service.get_account_balance()
                        equity = balance_data.get("total_equity", 0) if balance_data.get("status") == "success" else 0
                        
                        gamification = AssetGamification(equity)
                        whitelist = gamification.get_allowed_assets()
                        self.bot.add_log(f"🎮 Context: Gamification Level {gamification.level.value} (${equity:.2f})")
                    except Exception as e:
                        self.bot.add_log(f"⚠️ Context Resolver Error: {e}")
                        # Fallback to safe list? Or keep None (All)? 
                        # User instruction said "Brider le Scanner". Safe fallback is empty or limited.
                        whitelist = ["BTC", "ETH"] # Panic fallback
                else:
                    # If not gamified, check if global whitelist exists
                    if hasattr(config, 'GLOBAL_WHITELIST') and config.GLOBAL_WHITELIST:
                        whitelist = config.GLOBAL_WHITELIST
                        self.bot.add_log(f"🌍 Context: Using Global Whitelist ({len(whitelist)} assets)")
                    else:
                        self.bot.add_log("🌍 Context: Full Market Access (No Gamification)")

                # Pass clean whitelist to scanner
                opportunities = self.scanner.scan(top_n=10, whitelist=whitelist)
                self.last_results = opportunities # Save raw results for UI
                self.is_scanning = False
                
                # Filter by min_score
                valid_opps = [o for o in opportunities if o['score'] >= min_score]
                
                if valid_opps:
                    # Check if trade is active - if so, DO NOT SPAM
                    if self.bot.active_trade:
                        self.bot.add_log(f"🕵️ Scanner found {len(valid_opps)} opps, but skipped alert (Active Trade)")
                    else:
                        # Send valid opportunities
                        self.bot.add_log(f"Found {len(valid_opps)} opportunities >= {min_score}")
                        self._send_discord_alert(valid_opps, min_score)
                    
                    # Auto Switch logic
                    best_opp = valid_opps[0]
                    if auto_switch and self.bot.active_symbol != best_opp['symbol']:
                        if self.bot.active_trade:
                            self.bot.add_log(f"⚠️ Scanner found {best_opp['symbol']} ({best_opp['score']}) but skipping switch: Trade Active on {self.bot.active_symbol}")
                        else:
                            old_symbol = self.bot.active_symbol
                            self.bot.active_symbol = best_opp['symbol']
                            
                            if hasattr(self.bot, 'sidebar_settings'):
                                self.bot.sidebar_settings['asset'] = self.bot.active_symbol
                                
                            self.bot.add_log(f"🔄 Auto-switched market: {old_symbol} -> {self.bot.active_symbol}")
                            StateManager.save_state(self.bot)
                            discord_service.send_log(f"🔄 **Auto-Switch**: Changed market to **{self.bot.active_symbol}** (Score: {best_opp['score']})")
                
                elif opportunities:
                    # No valid opportunities, but send top 3 anyway
                    if self.bot.active_trade:
                        self.bot.add_log(f"🕵️ Scanner: Market calm, skipped alert (Active Trade)")
                    else:
                        top_3 = opportunities[:3]
                        self.bot.add_log(f"No opportunities >= {min_score}. Top score: {top_3[0]['score']:.0f}")
                        self._send_discord_alert(top_3, min_score, warning=True)
                
                else:
                    # No opportunities at all (gamification filtered everything or market issue)
                    self.bot.add_log("Scanner returned no opportunities")
                    discord_service.send_log(f"🕵️ **Scanner**: No tokens available to scan (Level: Goblin)")


            except Exception as e:
                print(f"❌ ScannerJob Error: {e}")
                time.sleep(60) # Wait a bit on error
            
            time.sleep(5)

    def manual_scan(self):
        """Trigger a manual scan immediately"""
        if self.is_scanning:
            return {"status": "busy", "message": "Scan already in progress"}
            
        print("🕵️ Starting Manual Scan...")
        self.is_scanning = True
        
        try:
            # Context Resolver (Replicated for safety)
            from app.core.constants import GAMIFICATION_ENABLED
            from app.core.config import config
            
            whitelist = None
            if GAMIFICATION_ENABLED:
                try:
                    from app.core.asset_gamification import AssetGamification
                    balance_data = self.scanner.hl_service.get_account_balance()
                    equity = balance_data.get("total_equity", 0) if balance_data.get("status") == "success" else 0
                    gamification = AssetGamification(equity)
                    whitelist = gamification.get_allowed_assets()
                except: whitelist = ["BTC", "ETH"] 
            
            # 1. Scan
            opportunities = self.scanner.scan(top_n=10, whitelist=whitelist)
            self.last_results = opportunities
            
            # 2. Return results (don't auto-act, just return)
            min_score = getattr(self.bot, 'scanner_settings', {}).get('min_score', 75)
            valid_opps = [o for o in opportunities if o['score'] >= min_score]
            
            self.bot.add_log(f"🕵️ Manual Scan done. Found {len(valid_opps)} opps >= {min_score}")
            
            self.is_scanning = False
            return {
                "status": "success", 
                "results": opportunities,
                "count": len(opportunities)
            }
        except Exception as e:
            self.is_scanning = False
            self.bot.add_log(f"❌ Manual Scan Error: {e}")
            return {"status": "error", "message": str(e)}

    def _send_discord_alert(self, opps, min_score=75, warning=False):
        """Send a nice formatted list of opportunities"""
        if not opps: return
        
        from app.utils.formatters import format_price_for_notification
        
        if warning:
            title = f"⚠️ SCANNER: Marché Calme (Top {len(opps)})"
            description = f"Aucune opportunité >={min_score}. Voici les meilleurs scores:\n\n"
        else:
            title = f"🔍 SCANNER: {len(opps)} Opportunities Found"
            description = f"Found {len(opps)} assets with Score >= {min_score}\n\n"
        
        for i, opp in enumerate(opps[:5]): # Top 5 only
            stars = "⭐⭐⭐" if opp['score'] >= 80 else "⭐⭐" if opp['score'] >= 60 else "⭐"
            trend_icon = "📈" if opp['trend'] == "UP" else "📉"
            
            # Format price with appropriate decimals
            price_str = format_price_for_notification(opp.get('current_price', 0))
            
            description += (
                f"**{i+1}. {opp['symbol']}** {stars}\n"
                f"Score: **{opp['score']:.0f}** | Trend: {trend_icon} | Vol: ${opp['volume_24h']/1e6:.1f}M\n"
                f"Price: {price_str} | `Adx: {opp.get('adx', 0):.1f}` | `Rsi: {opp['rsi']:.0f}`\n\n"
            )
            
        color = "ffa500" if warning else "9b59b6"  # Orange if warning, Purple otherwise
        
        discord_service.send_alert(
            title, 
            description, 
            color=color
        )
