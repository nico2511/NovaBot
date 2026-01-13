"""
Bot Context - Minimal version for gamification integration.
"""

from app.gamification.tier_calculator import TierCalculator
from app.gamification.enums import TierEnum


class BotContext:
    """
    Minimal trading bot context with gamification.
    
    This is a simplified version that demonstrates tier integration.
    Full implementation deferred for next session.
    """
    
    def __init__(self):
        print("\n🤖 [BOOT] BotContext v2.0 (Minimal)\n")
        
        # Services
        self.tier_calculator = TierCalculator()
        
        # State
        self.current_tier = TierEnum.NEBULA
        self.equity = 0.0
        self.running = False
        self.logs = []
        
    def add_log(self, message: str):
        """Add log message"""
        self.logs.append(message)
        print(f"[BOT] {message}")
        
    def update_tier(self, equity: float):
        """Update current tier based on equity"""
        self.equity = equity
        old_tier = self.current_tier
        self.current_tier = self.tier_calculator.calculate(equity)
        
        if old_tier != self.current_tier:
            self.add_log(f"🎯 Tier changed: {old_tier.value} → {self.current_tier.value}")
            
    def start(self):
        """Start the bot"""
        self.running = True
        self.add_log("✅ Bot started")
        
    def stop(self):
        """Stop the bot"""
        self.running = False
        self.add_log("🛑 Bot stopped")
        
    def get_status(self):
        """Get bot status"""
        return {
            "running": self.running,
            "tier": self.current_tier.value,
            "equity": self.equity,
            "logs": self.logs[-10:]  # Last 10 logs
        }
