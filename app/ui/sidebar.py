import streamlit as st
from app.core.config import config
from app.core.risk_manager import RiskManager

def render_sidebar(risk_manager: RiskManager, current_running_state: bool = False):
    st.sidebar.title("🎛️ Control Panel")

    # 1. Engine Control
    st.sidebar.subheader("System Status")
    is_running = st.sidebar.checkbox("🔌 START ENGINE (Data Feed)", value=current_running_state, key="master_switch")
    st.sidebar.caption("Must be ON to fetch data & update charts.")

    # 2. Asset Selector
    st.sidebar.subheader("Market")
    selected_asset = st.sidebar.selectbox("Asset", ["BTC", "ETH", "SOL", "BNB"], index=0)

    # 3. Hybrid Mode
    st.sidebar.subheader("Execution Mode")
    mode = st.sidebar.radio("Mode", ["Manual (Phantom)", "Auto (Hyperliquid)"])
    
    can_trade = False
    if mode == "Auto (Hyperliquid)":
        can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", value=False, help="If unchecked, signals are generated but NOT executed.")
        if can_trade:
            st.sidebar.warning("⚠️ Live Trading ENABLED")

    # 4. Risk Settings
    st.sidebar.subheader("🛡️ Risk Management")
    
    # Position Sizing
    size_type = st.sidebar.selectbox("Sizing Type", ["Fixed (USDC)", "% Equity"])
    size_value = st.sidebar.number_input("Size Value", min_value=1.0, value=100.0, step=10.0)
    
    # Leverage
    leverage = st.sidebar.slider("Leverage", 1, 20, config.DEFAULT_LEVERAGE)
    
    # Safety Limits
    st.sidebar.divider()
    max_pos = st.sidebar.number_input(
        "Max Open Positions", 
        min_value=1, 
        value=risk_manager.max_positions,
        help="Hard limit on concurrent trades."
    )
    
    daily_sl = st.sidebar.number_input(
        "Daily Stop Loss (USDC)", 
        min_value=10.0, 
        value=risk_manager.daily_stop_loss,
        help="Circuit breaker: Stops bot if daily loss exceeds this."
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

    return {
        "is_running": is_running,
        "asset": selected_asset,
        "mode": mode,
        "trading_enabled": can_trade,
        "size_type": size_type,
        "size_value": size_value,
        "leverage": leverage
    }
