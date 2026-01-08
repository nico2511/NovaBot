"""
Reporter Utility
Export et affichage des résultats multi-stratégies
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import json
from tabulate import tabulate


def save_strategy_results(strategy_name, stats, trades, output_dir="results"):
    """Sauvegarde résultats d'une stratégie"""
    
    Path(f"{output_dir}/trades").mkdir(parents=True, exist_ok=True)
    Path(f"{output_dir}/equity").mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Stats JSON
    stats_path = f"{output_dir}/{strategy_name}_stats_{timestamp}.json"
    save_stats_json(stats, stats_path)
    
    # Trades CSV
    if trades is not None and not trades.empty:
        trades_path = f"{output_dir}/trades/{strategy_name}_trades_{timestamp}.csv"
        trades.to_csv(trades_path, index=False)
        print(f"[DISK] {strategy_name}: {len(trades)} trades saved")
    
    return stats_path


def save_stats_json(stats, filepath):
    """Sauvegarde stats en JSON"""
    
    stats_dict = {}
    
    # Stats est une pd.Series, on itère sur ses items
    for key, value in stats.items():
        # Gérer les types complexes avant pd.isna()
        if isinstance(value, (pd.Series, pd.DataFrame)):
            stats_dict[str(key)] = str(type(value))
            continue
            
        if pd.isna(value):
            value = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            value = str(value)
        elif isinstance(value, pd.Timedelta):
            value = str(value)
        elif hasattr(value, 'item'): # Handle numpy scalars
             value = value.item()
        elif not isinstance(value, (int, float, str, bool, type(None))):
            # Fallback pour tout autre objet non sérialisable (ex: Strategy object)
            value = str(value)
        
        stats_dict[str(key)] = value
    
    with open(filepath, 'w') as f:
        json.dump(stats_dict, f, indent=2)


def print_strategy_summary(strategy_name, stats):
    """Affiche résumé d'une stratégie"""
    
    print(f"\n{'='*60}")
    print(f"[INFO] {strategy_name.upper()}")
    print(f"{'='*60}")
    
    metrics = [
        ("Return", f"{stats.get('Return [%]', 0):.2f}%"),
        ("Sharpe", f"{stats.get('Sharpe Ratio', 0):.2f}"),
        ("Win Rate", f"{stats.get('Win Rate [%]', 0):.2f}%"),
        ("# Trades", stats.get('# Trades', 0)),
        ("Max DD", f"{stats.get('Max. Drawdown [%]', 0):.2f}%"),
        ("Profit Factor", f"{stats.get('Profit Factor', 0):.2f}"),
    ]
    
    for label, value in metrics:
        print(f"{label:.<25} {value:>30}")
    
    # Verdict
    win_rate = stats.get('Win Rate [%]', 0)
    pf = stats.get('Profit Factor', 0)
    sharpe = stats.get('Sharpe Ratio', 0)
    
    if win_rate >= 50 and pf >= 1.5 and sharpe >= 1.2:
        print("\n[EXCELLENT] EXCELLENT")
    elif win_rate >= 45 and pf >= 1.3:
        print("\n[GOOD]  GOOD")
    else:
        print("\n[FAIL] NEEDS IMPROVEMENT")


def create_comparison_table(all_results):
    """
    Crée tableau comparatif de toutes les stratégies
    
    Args:
        all_results: Dict {strategy_name: stats}
    
    Returns:
        DataFrame comparatif
    """
    
    data = []
    
    for strategy_name, stats in all_results.items():
        row = {
            "Strategy": strategy_name,
            "Return [%]": round(stats.get("Return [%]", 0), 2),
            "Sharpe": round(stats.get("Sharpe Ratio", 0), 2),
            "Win Rate [%]": round(stats.get("Win Rate [%]", 0), 2),
            "# Trades": stats.get("# Trades", 0),
            "Max DD [%]": round(stats.get("Max. Drawdown [%]", 0), 2),
            "Profit Factor": round(stats.get("Profit Factor", 0), 2),
            "Expectancy [%]": round(stats.get("Expectancy [%]", 0), 2),
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    
    # Trier par Sharpe Ratio
    df = df.sort_values("Sharpe", ascending=False)
    
    return df


def print_comparison(comparison_df):
    """Affiche tableau comparatif"""
    
    print("\n" + "="*100)
    print("[RESULTS] STRATEGIES COMPARED - SORTED BY SHARPE RATIO")
    print("="*100)
    
    print(tabulate(comparison_df, headers='keys', tablefmt='grid', showindex=False))
    
    # Meilleure stratégie
    best = comparison_df.iloc[0]
    print(f"\n[BEST] BEST STRATEGY: {best['Strategy']}")
    print(f"   Sharpe: {best['Sharpe']:.2f} | Return: {best['Return [%]']:.2f}% | Win Rate: {best['Win Rate [%]']:.2f}%")


def save_comparison(comparison_df, output_dir="results/comparison"):
    """Sauvegarde tableau comparatif"""
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # CSV
    csv_path = f"{output_dir}/comparison_{timestamp}.csv"
    comparison_df.to_csv(csv_path, index=False)
    
    # Markdown
    md_path = f"{output_dir}/comparison_{timestamp}.md"
    with open(md_path, 'w') as f:
        f.write("# Backtest Comparison\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(comparison_df.to_markdown(index=False))
    
    print(f"\n[DISK] Comparison saved:")
    print(f"   CSV: {csv_path}")
    print(f"   MD:  {md_path}")
