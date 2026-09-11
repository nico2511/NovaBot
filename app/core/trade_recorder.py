import csv
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _entry_value(entry_indicators: Optional[Dict[str, Any]], *keys: str, default: Any = ""):
    """Read first present key from entry snapshot (supports ai_context aliases)."""
    src = entry_indicators or {}
    for key in keys:
        if key not in src:
            continue
        val = src[key]
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        return val
    return default


def normalize_entry_indicators(entry_indicators: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Map strategy ai_context keys to trade journal columns.

    ai_context uses rsi_val/adx_val; legacy callers may still pass rsi/adx.
    """
    src = dict(entry_indicators or {})
    out: Dict[str, Any] = {
        "regime": _entry_value(src, "regime"),
        "adx": _entry_value(src, "adx_val", "adx"),
        "rsi": _entry_value(src, "rsi_val", "rsi"),
        "ema_20": _entry_value(src, "ema_20"),
        "ema_50": _entry_value(src, "ema_50"),
        "volume_ratio": _entry_value(src, "volume_ratio"),
        "bb_position": _entry_value(src, "bb_position"),
        "adx_slope": _entry_value(src, "adx_slope"),
        "vol_slope": _entry_value(src, "vol_slope"),
        "macd_hist": _entry_value(src, "macd_hist"),
        "market_bias": _entry_value(src, "market_bias"),
        "strategy_timeframe": _entry_value(src, "strategy_timeframe"),
        "ai_confidence": _entry_value(src, "ai_confidence"),
        "ai_reasoning": _entry_value(src, "ai_reasoning"),
    }
    for num_key in ("adx", "rsi", "ema_20", "ema_50", "volume_ratio", "adx_slope", "vol_slope", "macd_hist", "ai_confidence"):
        raw = out.get(num_key)
        if raw == "" or raw is None:
            continue
        try:
            out[num_key] = float(raw)
        except (TypeError, ValueError):
            out[num_key] = ""
    return out

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
            # Extended instant-T snapshot (v2 journal schema)
            "entry_bb_position", "entry_adx_slope", "entry_vol_slope",
            "entry_macd_hist", "entry_market_bias", "entry_strategy_tf",
        ]
        self._numeric_columns = (
            "entry_price", "exit_price", "size", "pnl", "leverage",
            "entry_adx", "entry_rsi", "entry_ema20", "entry_ema50",
            "entry_volume_ratio", "ai_confidence",
            "entry_adx_slope", "entry_vol_slope", "entry_macd_hist",
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
        idx = self.headers.index("ai_reasoning")
        legacy_tail = 3  # entry_time, trade_id, trace_id
        ext_cols = max(0, n - idx - 1 - legacy_tail)
        min_fields = idx + 1 + legacy_tail

        if len(row) == n:
            return row

        if len(row) < min_fields:
            return row + [""] * (n - len(row))

        # Missing trailing extension columns, or reasoning commas without extra tail fields.
        if min_fields <= len(row) < n:
            if len(row) > min_fields:
                tail_start = len(row) - legacy_tail
                merged = ",".join(row[idx:tail_start])
                tail = row[tail_start:] + [""] * ext_cols
                return row[:idx] + [merged] + tail
            return row + [""] * (n - len(row))

        # len(row) > n OR unquoted commas expanded the reasoning field count.
        tail_start = len(row) - legacy_tail
        merged = ",".join(row[idx:tail_start])
        tail = row[tail_start:] + [""] * ext_cols
        return row[:idx] + [merged] + tail

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

    def _backup_csv(self, reason: str = "schema_migration") -> Optional[str]:
        """Copy trade_history.csv to data/backups/ before schema changes."""
        if not os.path.exists(self.csv_file):
            return None
        try:
            backup_dir = Path(self.data_dir) / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            dest = backup_dir / f"trade_history_{stamp}_{reason}.csv"
            shutil.copy2(self.csv_file, dest)
            logger.info("Trade history backup: %s", dest)
            return str(dest)
        except Exception as e:
            logger.warning("Trade history backup skipped: %s", e)
            return None

    def _maybe_migrate_csv_header(self) -> None:
        if not os.path.exists(self.csv_file):
            return
        try:
            with open(self.csv_file, encoding="utf-8", newline="") as f:
                header = next(csv.reader(f), None)
            if header == self.headers:
                return
            self._backup_csv()
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
            
            snap = normalize_entry_indicators(trade_data.get("entry_indicators", {}))

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
                snap.get("regime", ""),
                snap.get("adx", ""),
                snap.get("rsi", ""),
                snap.get("ema_20", ""),
                snap.get("ema_50", ""),
                snap.get("volume_ratio", ""),
                snap.get("ai_confidence", ""),
                str(snap.get("ai_reasoning", ""))[:200],
                trade_data.get("entry_time")
                or trade_data.get("entry_timestamp")
                or (trade_data.get("metadata") or {}).get("entry_time")
                or "",
                trade_data.get("trade_id") or "",
                trade_data.get("trace_id")
                or (trade_data.get("metadata") or {}).get("trace_id")
                or "",
                snap.get("bb_position", ""),
                snap.get("adx_slope", ""),
                snap.get("vol_slope", ""),
                snap.get("macd_hist", ""),
                snap.get("market_bias", ""),
                snap.get("strategy_timeframe", ""),
            ]
            
            with self._lock:
                with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(row)
            
            reasoning_snippet = str(snap.get("ai_reasoning", "N/A"))[:100]
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
