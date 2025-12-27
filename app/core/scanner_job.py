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
                min_score = settings.get('min_score', 75)
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
                self.last_scan_time = now
                self.bot.add_log(f"🕵️ Running periodic scan (Interval: {interval_minutes}m)")
                
                opportunities = self.scanner.scan(top_n=10)
                
                # Filter
                valid_opps = [o for o in opportunities if o['score'] >= min_score]
                
                if not valid_opps:
                    self.bot.add_log("No opportunities found above threshold.")
                    continue

                # Notify & Action
                best_opp = valid_opps[0]
                
                # 1. Send Discord Summary
                self._send_discord_alert(valid_opps)

                # 2. Auto Switch
                # SAFETY: Never switch if we are already in a trade!
                if auto_switch and self.bot.active_symbol != best_opp['symbol']:
                    if self.bot.active_trade:
                        self.bot.add_log(f"⚠️ Scanner found {best_opp['symbol']} ({best_opp['score']}) but skipping switch: Trade Active on {self.bot.active_symbol}")
                    else:
                        old_symbol = self.bot.active_symbol
                        self.bot.active_symbol = best_opp['symbol']
                        
                        # Ensure sidebar settings are also updated so they persist correctly
                        if hasattr(self.bot, 'sidebar_settings'):
                            self.bot.sidebar_settings['asset'] = self.bot.active_symbol
                            
                        self.bot.add_log(f"🔄 Auto-switched market: {old_symbol} -> {self.bot.active_symbol}")
                        
                        # Persist the change
                        StateManager.save_state(self.bot)
                        
                        discord_service.send_log(f"🔄 **Auto-Switch**: Changed market to **{self.bot.active_symbol}** (Score: {best_opp['score']})")

            except Exception as e:
                print(f"❌ ScannerJob Error: {e}")
                time.sleep(60) # Wait a bit on error
            
            time.sleep(5)

    def _send_discord_alert(self, opps):
        """Send a nice formatted list of opportunities"""
        if not opps: return
        
        best = opps[0]
        
        title = f"🔍 SCANNER: {len(opps)} Opportunities Found"
        description = f"Found {len(opps)} assets with Score >= {self.bot.scanner_settings.get('min_score')}\n\n"
        
        for i, opp in enumerate(opps[:5]): # Top 5 only
            stars = "⭐⭐⭐" if opp['score'] >= 80 else "⭐⭐" if opp['score'] >= 60 else "⭐"
            trend_icon = "📈" if opp['trend'] == "UP" else "📉"
            
            description += (
                f"**{i+1}. {opp['symbol']}** {stars}\n"
                f"Score: **{opp['score']:.0f}** | Trend: {trend_icon} | Vol: ${opp['volume_24h']/1e6:.1f}M\n"
                f"`Adx: {opp.get('adx', 0):.1f}` | `Rsi: {opp['rsi']:.0f}`\n\n"
            )
            
        discord_service.send_alert(
            title, 
            description, 
            color="9b59b6" # Purple
        )
