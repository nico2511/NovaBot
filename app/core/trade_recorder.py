import csv
import logging
import os
import threading
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

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
            # Entry indicators for post-trade analysis
            "entry_regime", "entry_adx", "entry_rsi", "entry_ema20", "entry_ema50",
            "entry_volume_ratio", "ai_confidence", "ai_reasoning",
            # Timeline / multi-trade ids
            "entry_time", "trade_id", "trace_id",
        ]
        self._numeric_columns = (
            "entry_price", "exit_price", "size", "pnl", "leverage",
            "entry_adx", "entry_rsi", "entry_ema20", "entry_ema50",
            "entry_volume_ratio", "ai_confidence",
        )
        
        self._ensure_storage()

    def _coerce_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        for col in self._numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        return df

    def _collapse_csv_row(self, row: list) -> list:
        """Merge overflow columns (unquoted commas in ai_reasoning) back into schema."""
        n = len(self.headers)
        if len(row) <= n:
            return row + [""] * (n - len(row))
        idx = self.headers.index("ai_reasoning")
        tail_count = n - idx - 1
        merged = ",".join(row[idx : len(row) - tail_count])
        return row[:idx] + [merged] + row[-tail_count:]

    def _read_csv_rows(self) -> list[list[str]]:
        with open(self.csv_file, encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            return []
        header = rows[0]
        data_rows = rows[1:] if header == self.headers or "timestamp" in header else rows
        normalized = []
        for row in data_rows:
            if not row:
                continue
            normalized.append(self._collapse_csv_row(row))
        return normalized

    def _maybe_migrate_csv_header(self) -> None:
        if not os.path.exists(self.csv_file):
            return
        try:
            with open(self.csv_file, encoding="utf-8", newline="") as f:
                header = next(csv.reader(f), None)
            if header == self.headers:
                return
            rows = self._read_csv_rows()
            with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(self.headers)
                writer.writerows(rows)
            logger.info(
                "Migrated trade_history.csv schema (%s -> %s columns)",
                len(header or []),
                len(self.headers),
            )
        except Exception as e:
            logger.warning("CSV header migration skipped: %s", e)

    def _read_csv_safe(self) -> pd.DataFrame:
        """Read CSV robustly handling schema evolution and malformed rows."""
        if not os.path.exists(self.csv_file):
            return pd.DataFrame(columns=self.headers)

        self._maybe_migrate_csv_header()
        try:
            rows = self._read_csv_rows()
            if not rows:
                return pd.DataFrame(columns=self.headers)
            df = pd.DataFrame(rows, columns=self.headers)
            return self._coerce_numeric_columns(df)
        except Exception as e:
            logger.warning("CSV Read Error: %s", e)
            return pd.DataFrame(columns=self.headers)
        
    def _ensure_storage(self):
        """Ensure data directory and CSV file exist with correct headers"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        if not os.path.exists(self.csv_file):
            try:
                with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(self.headers)
                logger.info("Created new trade history file: %s", self.csv_file)
            except Exception as e:
                logger.error("Critical error creating trade history file: %s", e)
        else:
            self._maybe_migrate_csv_header()

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
                str(entry_indicators.get("ai_reasoning", ""))[:200],
                trade_data.get("entry_time")
                or trade_data.get("entry_timestamp")
                or (trade_data.get("metadata") or {}).get("entry_time")
                or "",
                trade_data.get("trade_id") or "",
                trade_data.get("trace_id")
                or (trade_data.get("metadata") or {}).get("trace_id")
                or "",
            ]
            
            with self._lock:
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(row)
            
            reasoning_snippet = str(entry_indicators.get("ai_reasoning", "N/A"))[:100]
            logger.info(
                "Trade recorded: %s | PnL: $%.2f | Reasoning: %s...",
                trade_data.get("symbol"), pnl, reasoning_snippet,
            )

        except Exception as e:
            logger.error("Failed to record trade: %s", e)
            logger.debug("Debug trade data: %s", trade_data)

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
            logger.warning("Error reading trade history: %s", e)
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
            logger.warning("Error calculating stats: %s", e)
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
            logger.warning("Error calculating equity curve: %s", e)
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
