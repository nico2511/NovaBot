import csv
import os
import threading
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

class TradeRecorder:
    """
    Production-grade Trade Recorder with CSV persistence and Thread-Safety.
    Single Source of Truth: data/trade_history.csv
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.csv_file = os.path.join(data_dir, "trade_history.csv")
        self._lock = threading.Lock()
        
        # CSV Headers - Extended with entry indicators
        self.headers = [
            "timestamp", "symbol", "side", "entry_price", "exit_price", 
            "size", "pnl", "strategy", "exit_reason", "leverage",
            # NEW: Entry indicators for post-trade analysis
            "entry_regime", "entry_adx", "entry_rsi", "entry_ema20", "entry_ema50",
            "entry_volume_ratio", "ai_confidence", "ai_reasoning"
        ]
        
        self._ensure_storage()

    def _read_csv_safe(self) -> pd.DataFrame:
        """Read CSV robustly handling schema evolution"""
        if not os.path.exists(self.csv_file):
            return pd.DataFrame(columns=self.headers)
        
        try:
            # Force using current headers, fill missing with NaN for old rows
            # header=None + skiprows=1 avoids mismatch error between names and file header
            return pd.read_csv(self.csv_file, names=self.headers, header=None, skiprows=1, engine='python')
        except Exception as e:
            print(f"⚠️ CSV Read Error (Attempting fallback): {e}")
            try:
                return pd.read_csv(self.csv_file) # Fallback to standard read
            except:
                return pd.DataFrame(columns=self.headers)
        
    def _ensure_storage(self):
        """Ensure data directory and CSV file exist with correct headers"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        if not os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(self.headers)
                print(f"✅ Created new trade history file: {self.csv_file}")
            except Exception as e:
                print(f"❌ critical error creating trade history file: {e}")

    def add_trade(self, trade_data: Dict[str, Any]):
        """
        Record a closed trade to CSV.
        Thread-safe.
        
        Args:
            trade_data: Dict containing trade details and optional entry_indicators.
        """
        # Data Normalization & Validation
        try:
            # Map incoming keys to CSV headers if needed
            timestamp = trade_data.get("timestamp") or trade_data.get("exit_time") or datetime.now().isoformat()
            pnl = trade_data.get("pnl") if trade_data.get("pnl") is not None else trade_data.get("pnl_usdc", 0.0)
            
            # Extract entry indicators (with defaults for backward compatibility)
            entry_indicators = trade_data.get("entry_indicators", {})
            
            row = [
                timestamp,
                trade_data.get("symbol", "UNKNOWN"),
                trade_data.get("side", "UNKNOWN"),
                float(trade_data.get("entry_price", 0.0)),
                float(trade_data.get("exit_price", 0.0)),
                float(trade_data.get("size", 0.0)),
                float(pnl),
                trade_data.get("strategy", "Manual"),
                trade_data.get("exit_reason", "Signal"),
                float(trade_data.get("leverage", 1.0)),
                # NEW: Entry indicators columns
                entry_indicators.get("regime", ""),
                entry_indicators.get("adx", ""),
                entry_indicators.get("rsi", ""),
                entry_indicators.get("ema_20", ""),
                entry_indicators.get("ema_50", ""),
                entry_indicators.get("volume_ratio", ""),
                entry_indicators.get("ai_confidence", ""),
                # Truncate reasoning to avoid CSV issues
                str(entry_indicators.get("ai_reasoning", ""))[:200]
            ]
            
            with self._lock:
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(row)
            
            print(f"📝 Trade Recorded: {trade_data.get('symbol')} | PnL: ${pnl:.2f} | Regime: {entry_indicators.get('regime', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Failed to record trade: {e}")
            # Fallback debug
            print(f"Debug Data: {trade_data}")

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent trade history from CSV.
        Returns list of dicts.
        """
        try:
            # Use safe reader
            df = self._read_csv_safe()
            
            if df.empty:
                 return []

            # Sort by timestamp desc (assuming isoformat sort works, or parsing)
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.sort_values(by='timestamp', ascending=False, inplace=True)
                # Convert back to string for consistency
                df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S')
            
            return df.head(limit).fillna("").to_dict('records')
            
        except Exception as e:
            print(f"⚠️ Error reading trade history: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Calculate aggregate statistics from persistence.
        """
        try:
            df = self._read_csv_safe()
            if df.empty:
                return self._empty_stats()
                
            total_trades = len(df)
            wins = df[df['pnl'] > 0]
            losses = df[df['pnl'] <= 0]
            
            win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
            total_pnl = df['pnl'].sum()
            
            gross_profit = wins['pnl'].sum()
            gross_loss = abs(losses['pnl'].sum())
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
            
            return {
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
                "total_pnl": round(total_pnl, 2),
                "profit_factor": round(profit_factor, 2),
                "best_trade": round(df['pnl'].max(), 2),
                "worst_trade": round(df['pnl'].min(), 2)
            }
            
        except Exception as e:
            print(f"⚠️ Error calculating stats: {e}")
            return self._empty_stats()

    def get_equity_curve(self) -> List[Dict[str, Any]]:
        """
        Calculate cumulative PnL curve for charting.
        Returns list of { "time": "YYYY-MM-DD", "value": 123.45 }
        """
        try:
            df = self._read_csv_safe()
            if df.empty:
                return []
                
            # Sort by timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.sort_values(by='timestamp', inplace=True)
            
            # Calculate cumulative PnL
            df['cumulative_pnl'] = df['pnl'].cumsum()
            
            curve = []
            for _, row in df.iterrows():
                curve.append({
                    "time": int(row['timestamp'].timestamp()), # UNIX timestamp for Lightweight Charts
                    "value": round(row['cumulative_pnl'], 2)
                })
                
            return curve
            
        except Exception as e:
            print(f"⚠️ Error calculating equity curve: {e}")
            return []

    def _empty_stats(self):
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "profit_factor": 0,
            "best_trade": 0,
            "worst_trade": 0
        }
