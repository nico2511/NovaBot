"""
Backtest Multi-Stratégies - NovaBot (Version Native)
Utilise des stratégies natives backtesting.py au lieu d'importer
"""

import sys
import argparse
from pathlib import Path
import json

# Ajouter le dossier courant au path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Ajouter utils au path
utils_dir = current_dir / "utils"
sys.path.insert(0, str(utils_dir))

from backtesting import Backtest
import pandas as pd

# Imports locaux
import config
from data_loader import load_data, validate_data
from reporter import (
    save_strategy_results,
    print_strategy_summary,
    create_comparison_table,
    print_comparison,
    save_comparison
)

# Import stratégies natives
from native_strategies import STRATEGY_CLASSES


def load_strategy_params(strategy_name):
    """
    Charge les paramètres d'une stratégie depuis strategies.json
    
    Args:
        strategy_name: Nom de la stratégie
    
    Returns:
        dict: Paramètres de la stratégie
    """
    strategies_json = current_dir.parent / "strategies.json"
    
    with open(strategies_json, 'r') as f:
        strategies_config = json.load(f)
    
    if strategy_name in strategies_config.get("strategies", {}):
        return strategies_config["strategies"][strategy_name].get("params", {})
    
    return {}


def run_backtest(strategy_name, strategy_class, data):
    """
    Lance un backtest pour une stratégie
    
    Args:
        strategy_name: Nom de la stratégie
        strategy_class: Classe de la stratégie (native backtesting.py)
        data: DataFrame OHLCV
    
    Returns:
        tuple: (stats, trades) ou (None, None) si erreur
    """
    
    print(f"\n{'='*60}")
    print(f"[>] Backtesting: {strategy_name}")
    print(f"{'='*60}")
    
    try:
        # Charger paramètres depuis strategies.json
        params = load_strategy_params(strategy_name)
        
        # Merger avec paramètres par défaut
        full_params = {**config.DEFAULT_STRATEGY_PARAMS, **params}
        
        # Filtrer params pour ne garder que ceux définis dans la classe
        # (backtesting.py crash si on passe des params inconnus)
        class_params = [attr for attr in dir(strategy_class) if not attr.startswith("__") and not callable(getattr(strategy_class, attr))]
        filtered_params = {k: v for k, v in full_params.items() if k in class_params}
        
        # Lancer backtest avec paramètres filtrés
        bt = Backtest(
            data,
            strategy_class,
            cash=config.INITIAL_CASH,
            commission=config.COMMISSION,
            exclusive_orders=True
        )
        
        # Run avec paramètres filtrés
        stats = bt.run(**filtered_params)
        trades = stats._trades
        
        # Afficher résumé
        print_strategy_summary(strategy_name, stats)
        
        # Sauvegarder résultats
        save_strategy_results(strategy_name, stats, trades, config.RESULTS_DIR)
        
        return stats, trades
    
    except Exception as e:
        print(f"[ERROR] Error backtesting {strategy_name}: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def run_optimization(strategy_name, strategy_class, data):
    """
    Lance l'optimisation pour une stratégie
    """
    print(f"\n{'='*60}")
    print(f"[>] Optimizing: {strategy_name}")
    print(f"{'='*60}")
    
    try:
        bt = Backtest(
            data,
            strategy_class,
            cash=config.INITIAL_CASH,
            commission=config.COMMISSION,
            exclusive_orders=True
        )
        
        # Définir les plages selon la stratégie
        opt_params = {}
        if strategy_name == "fibo_pullback":
            opt_params = {
                "ema_period": range(150, 260, 10),
                "swing_lookback": range(10, 60, 5),
                "min_rr": [1.0, 1.3, 1.5, 2.0, 2.5, 3.0]
            }
        elif strategy_name == "smart_trend":
            opt_params = {
                "ema_fast": range(10, 40, 5),
                "ema_slow": range(40, 100, 10),
                "adx_threshold": range(15, 40, 5)
            }
        elif strategy_name == "institutional_scalp":
            opt_params = {
                "liq_grab_lookback": range(5, 35, 5),
                "min_rr": [1.0, 1.2, 1.5, 2.0, 2.5]
            }
        elif strategy_name == "scalp_ema_rsi":
            opt_params = {
                "rsi_period": range(10, 22, 2),
                "min_rr": [1.0, 1.2, 1.3, 1.5, 2.0]
            }
        elif strategy_name == "bollinger_bounce":
            opt_params = {
                "bb_std": [2.0, 2.5, 3.0],
                "adx_threshold": range(20, 50, 5),
                "min_rr": [1.0, 1.5, 2.0]
            }
        elif strategy_name == "elastic_reversion":
            opt_params = {
                "oversold_rsi": range(15, 35, 5),
                "min_rr": [1.0, 1.5, 2.0]
            }
        elif strategy_name == "rsi_ping_pong":
            opt_params = {
                "rsi_oversold": range(20, 40, 5),
                "min_rr": [1.0, 1.5, 2.0]
            }
        elif strategy_name == "double_bottom":
            opt_params = {
                "min_rr": [1.0, 1.3, 1.5, 2.0, 3.0]
            }
        elif strategy_name == "bull_flag":
             opt_params = {
                 "min_rr": [1.0, 1.3, 1.5, 2.0]
             }
        elif strategy_name == "smart_mean_reversion":
             opt_params = {
                 "rsi_threshold": [25, 30, 35],
                 "roc_floor": [-10, -15, -20],
                 "min_rr": [1.0, 1.5, 2.0]
             }
        else:
            print(f"[WARN] No optimization strategy defined for {strategy_name}")
            return None, None
            
        print(f"Optimizing parameters: {opt_params.keys()}")
        
        # Run optimization
        stats = bt.optimize(
            **opt_params,
            maximize='Sharpe Ratio',
            return_heatmap=False
        )
        
        print("\n[BEST] Best Parameters Found:")
        best_params = stats._strategy
        print(best_params)
        
        # Afficher résumé
        print_strategy_summary(strategy_name, stats)
        
        # Sauvegarder résultats optimisés (suffixe _opt)
        save_strategy_results(strategy_name + "_opt", stats, stats._trades, config.RESULTS_DIR)
        
        return stats, stats._trades
        
    except Exception as e:
        print(f"[ERROR] Optimization failed for {strategy_name}: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    """Point d'entrée principal"""
    
    parser = argparse.ArgumentParser(description="Backtest NovaBot Strategies")
    parser.add_argument("--strategy", help="Backtest une stratégie spécifique")
    parser.add_argument("--start", help="Date de début (YYYY-MM-DD)")
    parser.add_argument("--end", help="Date de fin (YYYY-MM-DD)")
    parser.add_argument("--optimize", action="store_true", help="Lancer l'optimisation des paramètres")
    
    args = parser.parse_args()
    
    # Override config si args fournis
    start_date = args.start or config.START_DATE
    end_date = args.end or config.END_DATE
    
    print("\n" + "="*80)
    print("NOVABOT MULTI-STRATEGY BACKTEST (Native)")
    print("="*80)
    print(f"Symbol: {config.SYMBOL}")
    print(f"Timeframe: {config.TIMEFRAME}")
    print(f"Period: {start_date} -> {end_date}")
    print(f"Initial Capital: ${config.INITIAL_CASH:,}")
    print(f"Commission: {config.COMMISSION*100}%")
    print(f"Mode: {'OPTIMIZATION' if args.optimize else 'BACKTEST'}")
    print("="*80)
    
    # 1. Charger données
    print("\n[INFO] Loading market data...")
    data = load_data(
        config.SYMBOL,
        start_date,
        end_date,
        config.TIMEFRAME,
        config.DATA_SOURCE,
        config.CSV_PATH
    )
    
    # FORCE FLOAT TYPES
    cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in cols:
        data[col] = data[col].astype(float)
        
    validate_data(data)
    
    # 2. Sélectionner stratégies
    strategies = {}
    if args.strategy:
        if args.strategy in STRATEGY_CLASSES:
            strategies = {args.strategy: STRATEGY_CLASSES[args.strategy]}
        else:
            print(f"[ERROR] Strategy '{args.strategy}' not found!")
            print(f"Available: {list(STRATEGY_CLASSES.keys())}")
            return
    else:
        # Filtrer selon config
        for name, cls in STRATEGY_CLASSES.items():
            if name in config.EXCLUDE_STRATEGIES:
                continue
            if config.PRIORITY_STRATEGIES and name not in config.PRIORITY_STRATEGIES:
                continue
            strategies[name] = cls
    
    print(f"\n[INFO] Strategies to process: {len(strategies)}")
    for name in strategies.keys():
        print(f"   [+] {name}")
    
    # 3. Exécuter (Backtest ou Optimisation)
    all_results = {}
    
    for strategy_name, strategy_class in strategies.items():
        if args.optimize:
            stats, trades = run_optimization(strategy_name, strategy_class, data)
        else:
            stats, trades = run_backtest(strategy_name, strategy_class, data)
        
        if stats is not None:
            all_results[strategy_name] = stats
    
    # 4. Comparaison finale
    if len(all_results) > 1:
        print("\n" + "="*100)
        print("[INFO] GENERATING COMPARISON...")
        print("="*100)
        
        comparison_df = create_comparison_table(all_results)
        print_comparison(comparison_df)
        
        if config.SAVE_COMPARISON:
            save_comparison(comparison_df, config.COMPARISON_DIR)
    
    # 5. Résumé final
    print("\n" + "="*80)
    print("[SUCCESS] PROCESS COMPLETED")
    print("="*80)
    print(f"Strategies processed: {len(all_results)}")
    print(f"Results saved in: {config.RESULTS_DIR}/")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
