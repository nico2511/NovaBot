"""
Backtest Configuration - Multi-Strategy
Configuration globale pour backtester toutes les stratégies NovaBot
"""

# ============================================
# DONNÉES
# ============================================

# Symbole à backtester
SYMBOL = "BTC/USDT"
TIMEFRAME = "15m"  # Trading 15M

# Période de backtest (6 mois de données Binance)
START_DATE = "2024-07-01"  # 6 mois de données
END_DATE = "2025-01-08"  # Aujourd'hui

# Source de données
DATA_SOURCE = "csv"  # Utiliser CSV Binance
CSV_PATH = "../data/BTC_15m_6months.csv"  # Données téléchargées

# ============================================
# CAPITAL & RISK MANAGEMENT
# ============================================

# Capital initial
INITIAL_CASH = 1_000_000  # USD

# Taille de position
POSITION_SIZE = 0.95  # 95% du capital par trade

# Frais de trading
COMMISSION = 0.001  # 0.1% par trade (maker/taker moyen)

# Slippage
SLIPPAGE = 0.0005  # 0.05% de slippage

# ============================================
# STRATÉGIES
# ============================================

# Stratégies à EXCLURE du backtest
# (utile pour désactiver temporairement certaines stratégies)
EXCLUDE_STRATEGIES = [
    # "fibo_pullback",  # Exemple: décommenter pour exclure
]

# Stratégies à tester en priorité (si vide, teste toutes)
PRIORITY_STRATEGIES = [
    # "fibo_pullback",
    # "smart_trend",
    # "institutional_scalp",
]

# Paramètres par défaut pour toutes les stratégies
# (utilisés si la stratégie n'a pas de params dans strategies.json)
DEFAULT_STRATEGY_PARAMS = {
    "min_rr": 1.5
}

# ============================================
# OPTIMISATION
# ============================================

# Activer l'optimisation globale
ENABLE_OPTIMIZATION = False

# Paramètres d'optimisation par stratégie
# Format: {"strategy_name": {"param": [values]}}
OPTIMIZATION_PARAMS = {
    "fibo_pullback": {
        "adx_threshold": range(15, 30, 5),
        "swing_confirmation_bars": range(5, 15, 5),
        "volume_multiplier": [1.3, 1.5, 2.0],
        "min_rr": [1.2, 1.5, 2.0]
    },
    "smart_trend": {
        "min_rr": [1.2, 1.5, 2.0]
    },
    # Ajouter d'autres stratégies ici
}

# Métrique d'optimisation
OPTIMIZE_METRIC = "Sharpe Ratio"  # Options: "Return [%]", "Sharpe Ratio", "Profit Factor"

# Contraintes d'optimisation
OPTIMIZE_CONSTRAINTS = {
    "min_trades": 10,  # Minimum de trades
    "max_drawdown": 0.25  # Max 25% drawdown
}

# ============================================
# RÉSULTATS
# ============================================

# Dossiers de sortie
RESULTS_DIR = "results"
EQUITY_DIR = f"{RESULTS_DIR}/equity"
TRADES_DIR = f"{RESULTS_DIR}/trades"
PLOTS_DIR = f"{RESULTS_DIR}/plots"
COMPARISON_DIR = f"{RESULTS_DIR}/comparison"

# Format de sauvegarde
SAVE_TRADES_CSV = True
SAVE_EQUITY_PNG = True
SAVE_PLOT_HTML = False  # HTML plots peuvent être lourds
SAVE_COMPARISON = True  # Tableau comparatif

# ============================================
# AFFICHAGE
# ============================================

# Verbosité
VERBOSE = True

# Afficher les plots interactifs
SHOW_PLOTS = False  # True = ouvre navigateur, False = sauvegarde seulement

# Afficher comparaison finale
SHOW_COMPARISON = True

# Métriques à afficher pour chaque stratégie
DISPLAY_METRICS = [
    "Return [%]",
    "Sharpe Ratio",
    "Win Rate [%]",
    "# Trades",
    "Max. Drawdown [%]",
    "Profit Factor"
]

# Métriques complètes (pour export JSON)
FULL_METRICS = [
    "Start",
    "End",
    "Duration",
    "Exposure Time [%]",
    "Equity Final [$]",
    "Equity Peak [$]",
    "Return [%]",
    "Buy & Hold Return [%]",
    "Return (Ann.) [%]",
    "Volatility (Ann.) [%]",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Calmar Ratio",
    "Max. Drawdown [%]",
    "Avg. Drawdown [%]",
    "Max. Drawdown Duration",
    "# Trades",
    "Win Rate [%]",
    "Best Trade [%]",
    "Worst Trade [%]",
    "Avg. Trade [%]",
    "Max. Trade Duration",
    "Avg. Trade Duration",
    "Profit Factor",
    "Expectancy [%]",
    "SQN"
]
