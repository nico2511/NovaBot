import json
import os
import threading
from datetime import datetime
from typing import Dict, Any, List

class TradeRecorder:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.file_path = os.path.join(data_dir, "trades.json")
        self._lock = threading.Lock()
        self._ensure_data_dir()
        
    def _ensure_data_dir(self):
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
    def load_trades(self) -> List[Dict[str, Any]]:
        """Load all recorded trades"""
        with self._lock:
            if not os.path.exists(self.file_path):
                return []
            try:
                with open(self.file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading trades: {e}")
                return []

    def add_trade(self, trade_data: Dict[str, Any]):
        """Record a closed trade"""
        with self._lock:
            trades = []
            if os.path.exists(self.file_path):
                try:
                    with open(self.file_path, 'r') as f:
                        trades = json.load(f)
                except:
                    trades = []
            
            # Enrich with ID if missing
            if "id" not in trade_data:
                trade_data["id"] = f"trade_{int(datetime.now().timestamp())}_{len(trades)}"
            
            trades.append(trade_data)
            
            try:
                with open(self.file_path, 'w') as f:
                    json.dump(trades, f, indent=2)
                print(f"✅ Trade recorded: {trade_data.get('symbol')} PnL: {trade_data.get('pnl')}")
            except Exception as e:
                print(f"❌ Error saving trade: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Calculate aggregate stats"""
        trades = self.load_trades()
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "profit_factor": 0,
                "best_trade": 0,
                "worst_trade": 0
            }
            
        wins = [t for t in trades if t.get("pnl", 0) > 0]
        losses = [t for t in trades if t.get("pnl", 0) <= 0]
        
        total_pnl = sum(t.get("pnl", 0) for t in trades)
        gross_profit = sum(t.get("pnl", 0) for t in wins)
        gross_loss = abs(sum(t.get("pnl", 0) for t in losses))
        
        return {
            "total_trades": len(trades),
            "win_rate": (len(wins) / len(trades)) * 100 if trades else 0,
            "total_pnl": total_pnl,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "best_trade": max([t.get("pnl", 0) for t in trades], default=0),
            "worst_trade": min([t.get("pnl", 0) for t in trades], default=0)
        }
