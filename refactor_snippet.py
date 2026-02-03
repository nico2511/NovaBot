import threading
import asyncio
from app.services.safe_order_manager import SafeOrderManager
from app.services.position_reconciler import PositionReconciler

# ... inside BotContext __init__ ...
        # Initialize Services
        self.scanner_job = ScannerJob(self)
        self.trade_recorder = TradeRecorder()
        self.gamification = AssetGamification(0)
        
        # New Services (Phase 0 Hardening)
        self.safe_order_manager = SafeOrderManager(hyperliquid_service)
        self.position_reconciler = PositionReconciler(hyperliquid_service, self.safe_order_manager)
        
        # Start Reconciler in background (if loop running)
        # or just allow it to be called periodically
        
# ... remove self.active_trade usages ...
