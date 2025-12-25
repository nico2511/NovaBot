import streamlit as st
from app.core.config import config
from app.core.risk_manager import RiskManager
from app.services.hyperliquid_service import hyperliquid_service

def render_sidebar(risk_manager: RiskManager, current_running_state: bool = False, persisted_settings: dict = None):
    st.sidebar.title("🎛️ Control Panel")
    
    # Initialize persisted settings
    if persisted_settings is None:
        persisted_settings = {}
    
    # Initialize session state from persisted settings on first load
    if 'settings_initialized' not in st.session_state:
        st.session_state.settings_initialized = True
        # Restore persisted values to session state
        for key, value in persisted_settings.items():
            if key not in st.session_state:
                st.session_state[key] = value

    # 1. Engine Control
    st.sidebar.subheader("System Status")
    is_running = st.sidebar.checkbox("🔌 START ENGINE (Data Feed)", value=current_running_state, key="master_switch")
    st.sidebar.caption("Must be ON to fetch data & update charts.")

    # 2. Account Balance (Hyperliquid)
    st.sidebar.subheader("💰 Account Balance")
    
    # Use session state to cache balance and avoid excessive API calls
    if 'last_balance_fetch' not in st.session_state:
        st.session_state.last_balance_fetch = None
        st.session_state.balance_data = None
    
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        if st.session_state.balance_data and st.session_state.balance_data.get('status') == 'success':
            equity = st.session_state.balance_data.get('equity', 0.0)
            st.metric("Total Equity", f"${equity:.2f}")
        else:
            st.metric("Total Equity", "--")
    
    with col2:
        if st.button("🔄", help="Refresh balance"):
            st.session_state.balance_data = hyperliquid_service.get_account_balance()
            st.session_state.last_balance_fetch = st.session_state.get('_main_loop_counter', 0)
    
    # Auto-fetch balance on first load or if not cached
    if st.session_state.balance_data is None:
        st.session_state.balance_data = hyperliquid_service.get_account_balance()
    
    # Display additional balance info
    if st.session_state.balance_data and st.session_state.balance_data.get('status') == 'success':
        available = st.session_state.balance_data.get('available', 0.0)
        margin_used = st.session_state.balance_data.get('margin_used', 0.0)
        
        c1, c2 = st.sidebar.columns(2)
        c1.caption(f"Available: ${available:.2f}")
        c2.caption(f"Margin: ${margin_used:.2f}")
    elif st.session_state.balance_data and st.session_state.balance_data.get('status') == 'error':
        st.sidebar.warning(f"⚠️ {st.session_state.balance_data.get('message', 'Failed to fetch balance')}")
    
    st.sidebar.divider()
    
    # 3. Asset Selector
    st.sidebar.subheader("Market")
    selected_asset = st.sidebar.selectbox("Asset", ["BTC", "ETH", "SOL", "BNB"], index=0)

    # 4. Hybrid Mode
    st.sidebar.subheader("Execution Mode")
    
    # Restore mode from persisted settings
    default_mode = st.session_state.get('execution_mode', persisted_settings.get('execution_mode', 'Manual (Phantom)'))
    mode_options = ["Manual (Phantom)", "Auto (Hyperliquid)"]
    mode_index = mode_options.index(default_mode) if default_mode in mode_options else 0
    mode = st.sidebar.radio("Mode", mode_options, index=mode_index, key='execution_mode')
    
    can_trade = False
    if mode == "Auto (Hyperliquid)":
        # Restore trading_enabled from persisted settings
        default_trading_enabled = st.session_state.get('trading_enabled', persisted_settings.get('trading_enabled', False))
        can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", value=default_trading_enabled, key='trading_enabled', help="If unchecked, signals are generated but NOT executed.")
        if can_trade:
            st.sidebar.warning("⚠️ Live Trading ENABLED")

    # 5. Risk Settings
    st.sidebar.subheader("🛡️ Risk Management")
    
    # Position Sizing - use session state with persisted values as defaults
    default_size_type = st.session_state.get('size_type', persisted_settings.get('size_type', 'Fixed (USDC)'))
    size_type_options = ["Fixed (USDC)", "% Equity"]
    size_type_index = size_type_options.index(default_size_type) if default_size_type in size_type_options else 0
    size_type = st.sidebar.selectbox("Sizing Type", size_type_options, index=size_type_index, key='size_type')
    
    default_size_value = st.session_state.get('size_value', persisted_settings.get('size_value', 100.0))
    size_value = st.sidebar.number_input("Size Value", min_value=1.0, value=float(default_size_value), step=10.0, key='size_value_input')
    
    # Leverage - use session state with persisted value as default
    default_leverage = st.session_state.get('leverage', persisted_settings.get('leverage', config.DEFAULT_LEVERAGE))
    leverage = st.sidebar.slider("Leverage", 1, 20, int(default_leverage), key='leverage')
    
    # Safety Limits
    st.sidebar.divider()
    
    # Use session state for max_positions and daily_stop_loss
    default_max_pos = st.session_state.get('max_positions', persisted_settings.get('max_positions', risk_manager.max_positions))
    max_pos = st.sidebar.number_input(
        "Max Open Positions", 
        min_value=1, 
        value=int(default_max_pos),
        help="Hard limit on concurrent trades.",
        key='max_positions'
    )
    
    default_daily_sl = st.session_state.get('daily_stop_loss', persisted_settings.get('daily_stop_loss', risk_manager.daily_stop_loss))
    daily_sl = st.sidebar.number_input(
        "Daily Stop Loss (USDC)", 
        min_value=10.0, 
        value=float(default_daily_sl),
        help="Circuit breaker: Stops bot if daily loss exceeds this.",
        key='daily_stop_loss'
    )

    # Update Risk Manager
    if st.sidebar.button("Apply Risk Settings"):
        risk_manager.update_settings(max_pos, daily_sl)
        st.sidebar.success("Settings Updated!")

    # Display Current Risk State
    status = risk_manager.get_status()
    st.sidebar.metric("Daily PnL", f"${status['daily_pnl']:.2f}", delta=status['daily_pnl'])
    if status['is_stop_mode']:
        st.sidebar.error(f"⛔ STOP MODE: {status['stop_reason']}")

    # Return all settings including those to be persisted
    return {
        "is_running": is_running,
        "asset": selected_asset,
        "mode": mode,
        "execution_mode": mode,  # Add for persistence
        "trading_enabled": can_trade,
        "size_type": size_type,
        "size_value": size_value,
        "leverage": leverage,
        "max_positions": max_pos,
        "daily_stop_loss": daily_sl
    }

