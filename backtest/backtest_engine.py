"""
BacktestEngine - Moteur de simulation temporelle
"""

import pandas as pd
from backtest.mock_exchange import MockExchange

class BacktestEngine:
    """Moteur de simulation pour backtest de stratégies"""
    
    def __init__(self, initial_balance: float = 1000.0):
        self.exchange = MockExchange(initial_balance)
        self.results = []
        
    def run(self, data_csv_path: str, strategy_func, symbol: str = "BTC", warmup_candles: int = 50):
        """
        Exécute le backtest.
        
        Args:
            data_csv_path: Chemin vers CSV (colonnes: timestamp, open, high, low, close, volume)
            strategy_func: Fonction qui prend (df_slice, exchange) et retourne un signal ou None
            symbol: Symbole du token (pour logs)
            warmup_candles: Nombre de bougies nécessaires pour les indicateurs
        
        Returns:
            dict: Statistiques du backtest
        """
        # Charger données
        print(f"📂 Loading data from {data_csv_path}...")
        df = pd.read_csv(data_csv_path)
        
        # Vérifier colonnes requises
        required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")
        
        # Convertir timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        print(f"📊 Backtest: {len(df)} candles loaded")
        print(f"📅 Period: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        print(f"💰 Initial Balance: ${self.exchange.initial_balance:.2f}")
        print("="*60)
        
        # Boucle temporelle
        for i in range(warmup_candles, len(df)):
            # Contexte: Données disponibles jusqu'à t (ANTI LOOK-AHEAD BIAS)
            df_slice = df.iloc[:i+1].copy()
            current_candle = df.iloc[i].to_dict()
            
            # Injecter bougie actuelle
            self.exchange.set_current_candle(current_candle)
            
            # Vérifier SL/TP (AVANT d'appeler la stratégie)
            self.exchange.check_stops()
            
            # Appeler stratégie SEULEMENT si pas de position
            if not self.exchange.positions:
                try:
                    signal = strategy_func(df_slice, self.exchange, symbol)
                    
                    # Exécuter signal
                    if signal:
                        result = self.exchange.execute_order(
                            symbol=signal['symbol'],
                            is_buy=(signal['side'] == "BUY"),
                            size=signal['size'],
                            sl_price=signal.get('sl'),
                            tp_price=signal.get('tp')
                        )
                        
                        if result['status'] == 'success':
                            timestamp = current_candle['timestamp']
                            print(f"[{timestamp}] 🚀 {signal['side']} {signal['size']:.4f} {symbol} @ ${current_candle['close']:.4f}")
                        else:
                            print(f"[{timestamp}] ❌ Order failed: {result['message']}")
                            
                except Exception as e:
                    print(f"⚠️ Strategy error at candle {i}: {e}")
        
        # Fermer position finale si ouverte
        if self.exchange.positions:
            for symbol in list(self.exchange.positions.keys()):
                self.exchange.close_position(symbol, reason="END_OF_BACKTEST")
                print(f"🔚 Closed final position on {symbol}")
        
        # Rapport final
        stats = self.exchange.get_stats()
        self.print_report(stats)
        
        return stats
        
    def print_report(self, stats: dict):
        """Affiche le rapport de performance"""
        print("\n" + "="*60)
        print("📈 BACKTEST RESULTS")
        print("="*60)
        print(f"Initial Balance: ${self.exchange.initial_balance:.2f}")
        print(f"Final Balance:   ${stats['final_balance']:.2f}")
        print(f"Total PnL:       ${stats['total_pnl']:.2f}")
        print(f"Total Fees:      ${stats['total_fees']:.2f}")
        print(f"ROI:             {stats['roi_pct']:+.2f}%")
        print("-"*60)
        print(f"Total Trades:    {stats['total_trades']}")
        print(f"Winning:         {stats['winning_trades']} ({stats['win_rate']:.1f}%)")
        print(f"Losing:          {stats['losing_trades']}")
        
        if stats['total_trades'] > 0:
            print(f"Avg Win:         ${stats['avg_win']:.2f}")
            print(f"Avg Loss:        ${stats['avg_loss']:.2f}")
            
            if stats['avg_loss'] != 0:
                profit_factor = abs(stats['avg_win'] * stats['winning_trades']) / abs(stats['avg_loss'] * stats['losing_trades'])
                print(f"Profit Factor:   {profit_factor:.2f}")
        
        print("="*60)
        
        # Verdict
        if stats['roi_pct'] > 10:
            print("✅ STRATEGY PROFITABLE")
        elif stats['roi_pct'] > 0:
            print("⚠️ STRATEGY MARGINALLY PROFITABLE")
        else:
            print("❌ STRATEGY LOSING")
