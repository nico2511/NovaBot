"""
MockExchange - Simule Hyperliquid sans appeler d'API réelle
"""

class MockExchange:
    """Faux exchange pour backtest isolé"""
    
    def __init__(self, initial_balance: float = 1000.0, fees_pct: float = 0.0005):
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.positions = {}  # {symbol: {...}}
        self.history = []
        self.fees_pct = fees_pct  # 0.05% par défaut
        self.current_candle = None
        
    def set_current_candle(self, candle: dict):
        """Injecte la bougie actuelle pour simulation"""
        self.current_candle = candle
        
    def get_current_price(self, symbol: str) -> float:
        """Retourne le prix de la bougie actuelle"""
        if not self.current_candle:
            raise ValueError("No candle set")
        return self.current_candle['close']
    
    def get_account_balance(self) -> dict:
        """Retourne le solde virtuel (compatible avec hyperliquid_service)"""
        return {
            "status": "success",
            "equity": self.balance,
            "total_equity": self.balance,
            "available": self.balance
        }
    
    def get_positions(self) -> list:
        """Retourne les positions ouvertes"""
        return [
            {
                "symbol": symbol,
                "side": pos["side"],
                "size": pos["size"],
                "entry_price": pos["entry_price"],
                "pnl": self._calculate_unrealized_pnl(symbol)
            }
            for symbol, pos in self.positions.items()
        ]
    
    def _calculate_unrealized_pnl(self, symbol: str) -> float:
        """Calcule le PnL non réalisé d'une position"""
        if symbol not in self.positions:
            return 0.0
        
        pos = self.positions[symbol]
        current_price = self.current_candle['close']
        
        if pos['side'] == "BUY":
            return (current_price - pos['entry_price']) * pos['size']
        else:
            return (pos['entry_price'] - current_price) * pos['size']
    
    def execute_order(self, symbol: str, is_buy: bool, size: float, price: float = None, 
                     sl_price: float = None, tp_price: float = None):
        """
        Simule l'exécution d'un ordre (compatible avec hyperliquid_service.execute_order)
        """
        if not self.current_candle:
            return {"status": "error", "message": "No candle set for execution"}
        
        # Prix d'exécution
        exec_price = price if price else self.current_candle['close']
        
        # Valeur de la position
        position_value = size * exec_price
        
        # Frais
        fees = position_value * self.fees_pct
        
        # Vérifier marge disponible
        if position_value + fees > self.balance:
            return {"status": "error", "message": f"Insufficient margin (need ${position_value + fees:.2f}, have ${self.balance:.2f})"}
        
        # Enregistrer position
        side = "BUY" if is_buy else "SELL"
        self.positions[symbol] = {
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry_price": exec_price,
            "sl": sl_price,
            "tp": tp_price,
            "timestamp": self.current_candle.get('timestamp', 'N/A')
        }
        
        # Déduire frais
        self.balance -= fees
        
        # Historique
        self.history.append({
            "action": "OPEN",
            "symbol": symbol,
            "side": side,
            "size": size,
            "price": exec_price,
            "fees": fees,
            "timestamp": self.current_candle.get('timestamp', 'N/A'),
            "balance_after": self.balance
        })
        
        return {"status": "success", "message": f"Order executed at ${exec_price:.4f}"}
    
    def close_position(self, symbol: str, reason: str = "MANUAL"):
        """Ferme une position et calcule le PnL"""
        if symbol not in self.positions:
            return {"status": "error", "message": "No position"}
        
        pos = self.positions[symbol]
        exec_price = self.current_candle['close']
        
        # Calcul PnL
        if pos['side'] == "BUY":
            pnl = (exec_price - pos['entry_price']) * pos['size']
        else:
            pnl = (pos['entry_price'] - exec_price) * pos['size']
        
        # Frais de sortie
        position_value = pos['size'] * exec_price
        fees = position_value * self.fees_pct
        
        # Mise à jour balance
        net_pnl = pnl - fees
        self.balance += net_pnl
        
        # Historique
        self.history.append({
            "action": "CLOSE",
            "symbol": symbol,
            "side": pos['side'],
            "size": pos['size'],
            "entry_price": pos['entry_price'],
            "exit_price": exec_price,
            "pnl": pnl,
            "fees": fees,
            "net_pnl": net_pnl,
            "reason": reason,
            "timestamp": self.current_candle.get('timestamp', 'N/A'),
            "balance_after": self.balance
        })
        
        del self.positions[symbol]
        return {"status": "success", "pnl": net_pnl}
    
    def check_stops(self):
        """Vérifie si SL/TP sont touchés par la bougie actuelle"""
        candle = self.current_candle
        if not candle:
            return
        
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            
            if pos['side'] == "BUY":
                # Check SL
                if pos['sl'] and candle['low'] <= pos['sl']:
                    self.close_position(symbol, reason="STOP_LOSS")
                # Check TP
                elif pos['tp'] and candle['high'] >= pos['tp']:
                    self.close_position(symbol, reason="TAKE_PROFIT")
            else:  # SELL
                # Check SL
                if pos['sl'] and candle['high'] >= pos['sl']:
                    self.close_position(symbol, reason="STOP_LOSS")
                # Check TP
                elif pos['tp'] and candle['low'] <= pos['tp']:
                    self.close_position(symbol, reason="TAKE_PROFIT")
    
    def get_candles(self, symbol: str, interval: str, limit: int):
        """
        Stub pour compatibilité - retourne un DataFrame vide
        Le backtest engine injectera les vraies données
        """
        import pandas as pd
        return pd.DataFrame()
    
    def get_stats(self) -> dict:
        """Retourne les statistiques du backtest"""
        trades = [h for h in self.history if h['action'] == 'CLOSE']
        
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0,
                "total_pnl": 0,
                "total_fees": sum(h['fees'] for h in self.history),
                "final_balance": self.balance,
                "roi_pct": 0
            }
        
        winning_trades = [t for t in trades if t['net_pnl'] > 0]
        losing_trades = [t for t in trades if t['net_pnl'] <= 0]
        
        total_pnl = sum(t['net_pnl'] for t in trades)
        total_fees = sum(h['fees'] for h in self.history)
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (len(winning_trades) / len(trades) * 100) if trades else 0,
            "total_pnl": total_pnl,
            "total_fees": total_fees,
            "avg_win": sum(t['net_pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            "avg_loss": sum(t['net_pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            "final_balance": self.balance,
            "roi_pct": ((self.balance - self.initial_balance) / self.initial_balance * 100)
        }
