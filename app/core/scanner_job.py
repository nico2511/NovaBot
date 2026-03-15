import threading
import time
from datetime import datetime
from typing import Tuple, List, Optional
from app.services.token_scanner import HyperliquidScanner
from app.services.discord_service import discord_service
from app.core.state_manager import StateManager
from app.core.config import config
from app.core.asset_gamification import AssetGamification

class ScannerJob:
    """
    Scanner Job - REFACTORED
    
    Improvements:
    - DRY: Extracted _get_scan_context() to avoid code duplication
    - Thread Safety: Added lock for last_results
    - Cleaner imports (moved to top)
    """
    
    def __init__(self, bot_context):
        self.bot = bot_context
        self.is_running = False
        self.thread = None
        self.last_scan_time = 0
        
        # Initialize scanner with funding rate settings from bot context
        scanner_settings = getattr(bot_context, 'scanner_settings', {})
        self.scanner = HyperliquidScanner(
            max_funding_long=scanner_settings.get('max_funding_long', 0.001),
            min_funding_short=scanner_settings.get('min_funding_short', -0.001),
            funding_filter_enabled=scanner_settings.get('funding_filter_enabled', True)
        )
        
        self.last_results = []  # Store last scan results for UI
        self.is_scanning = False  # Status flag
        
        # Thread safety for last_results
        self.results_lock = threading.Lock()
        
    def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        # Initialize last_scan_time to 0 so the first scan runs IMMEDIATELY
        self.last_scan_time = 0
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.bot.add_log("🔍 ScannerJob started (Thread launched)")

    def stop(self):
        self.is_running = False
        if self.thread:
            try:
                self.thread.join(timeout=2)
            except: pass
        self.bot.add_log("⏹️ ScannerJob stopped")
    
    def _get_scan_context(self) -> Tuple[Optional[List[str]], str]:
        """
        Context Resolver - DRY Extraction
        
        Handles gamification logic and returns whitelist + log message
        
        Returns:
            (whitelist, log_message): 
                - whitelist: List of allowed symbols or None (full access)
                - log_message: String to log about gamification status
        """
        whitelist = None
        log_message = ""
        
        gamification_enabled = self.bot.scanner_settings.get('gamification_enabled', True)
        
        if gamification_enabled:
            try:
                # Fetch equity to determine tier
                balance_data = self.scanner.hl_service.get_account_balance()
                equity = balance_data.get("total_equity", 0) if balance_data.get("status") == "success" else 0
                
                gamification = AssetGamification(equity)
                whitelist = gamification.get_allowed_assets()
                log_message = f"🎮 Gamification ON: Level {gamification.level.value} (${equity:.2f}) - {len(whitelist)} assets allowed"
                
            except Exception as e:
                self.bot.add_log(f"⚠️ Context Resolver Error: {e}")
                whitelist = ["BTC", "ETH"]  # Panic fallback
                log_message = "⚠️ Gamification Error - Fallback to BTC/ETH"
        else:
            # Gamification disabled - Full market access
            log_message = "🌍 Gamification OFF: Full Market Access"
        
        return whitelist, log_message

    def _run_loop(self):
        self.bot.add_log("🔍 Scanner Loop Entered")
        while self.is_running:
            try:
                # Check settings
                settings = getattr(self.bot, 'scanner_settings', {})
                enabled = settings.get('enabled', False)
                interval_minutes = settings.get('interval', 15)
                min_score = settings.get('min_score', 50)  # Lowered from 75 for more realistic opportunities
                auto_switch = settings.get('auto_switch', False)

                if not enabled:
                    self.bot.add_log(f"🔍 Scanner LOOP: Skipping (Enabled={enabled})")
                    time.sleep(10)
                    continue

                # CIRCUIT BREAKER: Pause Scanner if Bot is in Focus Mode
                if getattr(self.bot, 'is_focus_mode', False):
                    self.bot.add_log("🔍 Scanner LOOP: Skipping (Focus Mode)")
                    time.sleep(10) 
                    continue

                # Check interval
                now = time.time()
                elapsed = now - self.last_scan_time
                required = interval_minutes * 60
                if elapsed < required:
                    # self.bot.add_log(f"🔍 Scanner LOOP: Waiting (Elapsed {elapsed:.0f}s < {required}s)") # Too spammy
                    time.sleep(10)
                    continue

                self.bot.add_log(f"🔍 Scanner LOOP: Triggering Scan! (Elapsed {elapsed:.0f}s >= {required}s)")

                # RUN SCAN
                self.last_scan_time = now
                self.bot.add_log(f"🕵️ Running periodic scan (Interval: {interval_minutes}m)")
                self.is_scanning = True
                
                # Get scan context (DRY - using extracted method)
                whitelist, log_msg = self._get_scan_context()
                self.bot.add_log(log_msg)

                # Pass whitelist to scanner
                opportunities = self.scanner.scan(top_n=10, whitelist=whitelist)
                
                # Thread-safe write to last_results
                with self.results_lock:
                    self.last_results = opportunities
                
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
                    # No opportunities at all
                    self.bot.add_log("Scanner returned no opportunities")
                    discord_service.send_log(f"🕵️ **Scanner**: No tokens available to scan")


            except Exception as e:
                print(f"❌ ScannerJob Error: {e}")
                time.sleep(60)
            
            time.sleep(5)

    def manual_scan(self):
        """Trigger a manual scan immediately"""
        if self.is_scanning:
            return {"status": "busy", "message": "Scan already in progress"}
            
        self.bot.add_log("🕵️ Starting Manual Scan...")
        self.is_scanning = True
        
        try:
            # Get scan context (DRY - using extracted method)
            whitelist, log_msg = self._get_scan_context()
            self.bot.add_log(log_msg)
            
            # Scan
            opportunities = self.scanner.scan(top_n=10, whitelist=whitelist)
            
            # Thread-safe write to last_results
            with self.results_lock:
                self.last_results = opportunities
            
            # Return results
            min_score = getattr(self.bot, 'scanner_settings', {}).get('min_score', 50)  # Lowered from 75
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
        
        for i, opp in enumerate(opps[:5]):  # Top 5 only
            stars = "⭐⭐⭐" if opp['score'] >= 80 else "⭐⭐" if opp['score'] >= 60 else "⭐"
            trend_icon = "📈" if opp.get('trend') == "UP" else "📉" if opp.get('trend') == "DOWN" else "➡️"
            
            # Format price with appropriate decimals
            price_str = format_price_for_notification(opp.get('current_price', 0))
            
            # Format advanced metrics
            funding_rate = opp.get('funding', 0) * 100
            oi_val = opp.get('open_interest', 0) / 1_000_000 # Millions
            
            description += (
                f"**{i+1}. {opp['symbol']}** {stars}\n"
                f"Score: **{opp['score']:.0f}** | Trend: {trend_icon} | Vol: ${opp['volume_24h']/1e6:.1f}M\n"
                f"Price: {price_str} | `Adx: {opp.get('adx', 0):.1f}` | `Rsi: {opp['rsi']:.0f}`\n"
                f"`Funding: {funding_rate:.4f}%` | `OI: ${oi_val:.1f}M`\n"
            )
            
            # Add Reasons if available
            if opp.get('reasons'):
                for reason in opp['reasons'][:2]:  # Limit to top 2 reasons
                    description += f"> {reason}\n"
            
            description += "\n"
            
        color = "ffa500" if warning else "9b59b6"  # Orange if warning, Purple otherwise
        
        discord_service.send_alert(
            title, 
            description, 
            color=color
        )
