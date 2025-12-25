import streamlit as st
import time
import threading
import pandas as pd
from collections import deque
from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.gemini_service import gemini_service
from app.services.discord_service import discord_service
from strategies.engine import StrategyEngine
from app.ui.sidebar import render_sidebar
from app.ui.charts import render_charts
from app.ui.strategy_monitor import render_strategy_monitor
from app.ui.cards import render_stat_card, render_info_card, render_header_card
from app.ui.theme import CUSTOM_CSS

# Page Config
st.set_page_config(
    page_title="HyperLiquid AI Trader", 
    page_icon="📈", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Apply BoxProof Dark Theme
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# --- Global State (Singleton) ---
class BotContext:
    def __init__(self):
        # ... existing initialization ...
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = deque(maxlen=200) # Performance Fix: Limited history
        self.logs = deque(maxlen=1000)      # Memory Leak Fix: Rolling logs
        self.latest_strategy_result = {}
        self.active_symbol = "BTC"
        self.last_candle_time = None
        self.active_trade = None
        self.sidebar_settings = {}  # Initialize sidebar settings

        # Restore State
        StateManager.load_state(self)

    def background_loop(self):
        """Main Trading Loop"""
        msg = "🤖 Bot Engine STARTED."
        discord_service.send_log(msg)
        self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} {msg}")
        
        while self.is_running:
            try:
                # 1. Fetch Data
                symbol = self.active_symbol 
                df = hyperliquid_service.get_candles(symbol, limit=100)
                
                if not df.empty:
                    self.latest_data = df
                    current_candle_time = df.index[-1]
                    current_price = df['close'].iloc[-1]

                    # --- A. TRADE MANAGER (Exit Logic) ---
                    if self.active_trade:
                        t = self.active_trade
                        # Check Stops
                        sl_hit = (t['side'] == 'BUY' and current_price <= t['sl']) or \
                                 (t['side'] == 'SELL' and current_price >= t['sl'])
                        
                        tp_hit = (t['side'] == 'BUY' and current_price >= t['tp']) or \
                                 (t['side'] == 'SELL' and current_price <= t['tp'])
                        
                        if sl_hit or tp_hit:
                            outcome = "✅ TAKE PROFIT" if tp_hit else "❌ STOP LOSS"
                            msg = f"{outcome} Hit: {t['symbol']} Closed @ {current_price} (Entry: {t['entry']})"
                            
                            pnl = (current_price - t['entry']) / t['entry'] if t['side'] == 'BUY' else (t['entry'] - current_price) / t['entry']
                            self.risk_manager.record_trade_close(pnl * 1000) # Mock size
                            
                            # Log Exit
                            self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} {msg}")
                            discord_service.send_log(msg)
                            self.active_trade = None 
                            
                            # SAVE STATE
                            StateManager.save_state(self)
                    
                    # --- B. SIGNAL FINDER (Entry Logic) ---
                    else:
                        # Only scan on new candle
                        if self.last_candle_time != current_candle_time:
                            self.last_candle_time = current_candle_time
                            
                            # Analyze
                            result = self.strategy_engine.analyze(df)
                            self.latest_strategy_result = result
                            
                            if result.get("signals"):
                                # Take the first valid signal
                                sig_data = result["signals"][0]
                                strat_name = sig_data.get("strategy", "Unknown")
                                action = sig_data.get("signal")
                                entry_price = sig_data.get("price")
                                sl = sig_data.get("sl", entry_price * 0.95)
                                tp = sig_data.get("tp", entry_price * 1.05)
                                
                                can_trade, reason = self.risk_manager.check_can_trade()
                                if can_trade:
                                    # Open Phantom Trade
                                    self.active_trade = {
                                        "symbol": symbol,
                                        "side": action,
                                        "entry": entry_price,
                                        "sl": sl,
                                        "tp": tp,
                                        "strategy": strat_name
                                    }
                                    self.risk_manager.record_trade_open()
                                    
                                    # Log Entry
                                    msg = f"🚨 ENTRY: {action} {symbol} @ {entry_price} (SL: {sl:.2f}, TP: {tp:.2f}) [{strat_name}]"
                                    
                                    log_entry = {
                                        "time": pd.Timestamp.now(),
                                        "symbol": symbol,
                                        "strategy": strat_name,
                                        "type": action,
                                        "price": entry_price,
                                        "action": "OPENED"
                                    }
                                    self.signals_log.append(log_entry)
                                    self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} {msg}")
                                    discord_service.send_log(msg)
                                    
                                    # SAVE STATE
                                    StateManager.save_state(self)

                                    if self.trading_enabled:
                                        # hyperliquid_service.execute_order(...)
                                        pass
                                else:
                                    self.logs.append(f"Skipped Signal: {reason}")
                else:
                    self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} Waiting for data...")
                
                # SAVE STATE PERIODICALLY (e.g. every loop or just on events)
                # To be safe against crashes, we save on events. 
                
                time.sleep(10) # 10s loop
            except Exception as e:
                err_msg = f"Error in loop: {e}"
                print(err_msg)
                self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} ⚠️ {err_msg}")
                time.sleep(5)
        
        stop_msg = "🛑 Bot Engine STOPPED."
        discord_service.send_log(stop_msg)
        self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} {stop_msg}")

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.background_loop, daemon=True)
            self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2.0)

@st.cache_data(ttl=15)
def fetch_candles(symbol):
    return hyperliquid_service.get_candles(symbol, limit=100)

@st.cache_resource
def get_bot_context():
    return BotContext()

if __name__ == "__main__":
    # Initialize
    ctx = get_bot_context()

    # --- UI Rendering ---

    # Sidebar
    sidebar_state = render_sidebar(ctx.risk_manager, ctx.is_running, ctx.sidebar_settings)
    ctx.trading_enabled = sidebar_state.get("trading_enabled", False)
    
    # Save sidebar settings to context for persistence (capture actual values from session state)
    ctx.sidebar_settings = {
        "execution_mode": sidebar_state.get("execution_mode"),
        "trading_enabled": sidebar_state.get("trading_enabled"),
        "size_type": sidebar_state.get("size_type"),
        "size_value": sidebar_state.get("size_value"),
        "leverage": sidebar_state.get("leverage"),
        "max_positions": sidebar_state.get("max_positions"),
        "daily_stop_loss": sidebar_state.get("daily_stop_loss")
    }

    
    # Persist settings immediately when they change
    StateManager.save_state(ctx)

    # Sync Symbol Selection
    if sidebar_state.get("asset") and sidebar_state["asset"] != ctx.active_symbol:
        ctx.active_symbol = sidebar_state["asset"]
        # Reset tracking on symbol change
        ctx.last_candle_time = None 
        ctx.latest_data = pd.DataFrame()
        try:
            st.toast(f"Switched to {ctx.active_symbol}")
        except: pass

    # Handle Engine Switch
    if sidebar_state["is_running"] and not ctx.is_running:
        ctx.start()
    elif not sidebar_state["is_running"] and ctx.is_running:
        ctx.stop()
        
    # --- Main Data Logic (With Cache) ---
    # Trigger data fetch if running
    if ctx.is_running:
         # Implicitly updates cache every 15s via the loop or UI interaction
         pass


    # Header with custom styling
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(30, 41, 59, 0.8)); 
                backdrop-filter: blur(10px); border: 1px solid rgba(59, 130, 246, 0.3); 
                border-radius: 0.75rem; padding: 1rem 1.5rem; margin-bottom: 1rem;'>
        <h1 style='color: #f8fafc; font-size: 1.5rem; font-weight: 700; margin: 0;
                   background: linear-gradient(135deg, #3b82f6, #60a5fa);
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
            ⚡ HyperLiquid AI Trader
        </h1>
        <p style='color: #94a3b8; font-size: 0.75rem; margin: 0.25rem 0 0 0;'>
            Advanced algorithmic trading with AI-powered strategies
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stats Row with native Streamlit metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        last_price = ctx.latest_data['close'].iloc[-1] if not ctx.latest_data.empty else 0.0
        st.metric("💰 Price", f"${last_price:,.2f}", sidebar_state["asset"])
    
    with col2:
        active_strats = ctx.latest_strategy_result.get("strategies", []) if hasattr(ctx, 'latest_strategy_result') else []
        strat_count = len(active_strats) if active_strats else 0
        st.metric("🎯 Strategies", f"{strat_count} active")
    
    with col3:
        regime = ctx.latest_strategy_result.get("regime", "UNKNOWN") if hasattr(ctx, 'latest_strategy_result') and ctx.latest_strategy_result else "UNKNOWN"
        adx_val = ctx.latest_strategy_result.get('adx', 0) if hasattr(ctx, 'latest_strategy_result') and ctx.latest_strategy_result else 0
        st.metric("📊 Regime", regime, f"ADX: {adx_val:.1f}")
    
    with col4:
        mode_short = "Auto" if sidebar_state["mode"] == "Auto (Hyperliquid)" else "Manual"
        status_text = "Live" if ctx.trading_enabled else "Paper"
        st.metric("⚙️ Mode", mode_short, status_text)
    
    with col5:
        if ctx.active_trade:
            t = ctx.active_trade
            st.metric("📈 Trade", f"{t['side']}", f"${t['entry']:.0f}")
        else:
            st.metric("🔍 Trade", "None", "Scanning")
    
    st.markdown("---")

    # --- SECTION 1: CHARTS (Always Visible) ---
    st.markdown("### 📊 Market Data")
    if not ctx.latest_data.empty:
        render_charts(ctx.latest_data, ctx.signals_log)
    else:
        st.info("Waiting for data... Ensure Engine is ON.")

    st.divider()
    
    # --- SECTION 1.5: STRATEGY MONITOR (Live Thresholds) ---
    if not ctx.latest_data.empty and ctx.latest_strategy_result:
        # Load strategies config
        import json
        try:
            with open("strategies.json", "r") as f:
                strategies_config = json.load(f)
        except:
            strategies_config = {}
        
        render_strategy_monitor(ctx.latest_data, ctx.latest_strategy_result, strategies_config)
        st.divider()


    # --- SECTION 2: INSIGHTS & LOGS (Split View) ---
    c_left, c_right = st.columns([1, 1])

    with c_left:
        if ctx.signals_log:
            st.dataframe(pd.DataFrame(ctx.signals_log), height=200, width="stretch")
        else:
            st.info("📡 No Live Signals yet.")

        # Simple log buffer display
        log_text = "\n".join(list(ctx.logs)[-20:]) if hasattr(ctx, 'logs') and ctx.logs else "⏳ Waiting for logs..."
        st.text_area("📝 System Logs", value=log_text, height=200, disabled=True)

    with c_right:
        st.subheader("🧠 AI Market Agent")
        
        if last_price <= 0:
            st.warning("⚠️ Waiting for valid price data...")
        else:
            if st.button("Generate AI Report"):
                with st.spinner("Analyzing market structure..."):
                    # Mock data usage
                    data_summary = {
                        "symbol": sidebar_state["asset"], 
                        "close": last_price, 
                        "volatility": "High (Auto-Detected)" 
                    }
                    analysis = gemini_service.analyze_market(data_summary)
                    ctx.latest_analysis = analysis

        if ctx.latest_analysis and 'raw_output' in ctx.latest_analysis:
            try:
                import json
                data = json.loads(ctx.latest_analysis.get('raw_output', '{}'))
                
                # Semantic Colors
                risk_color = "red" if data.get('risk_level') == "HIGH" else "orange" if data.get('risk_level') == "MEDIUM" else "green"
                
                c1, c2 = st.columns(2)
                c1.markdown(f"**Risk:** :{risk_color}[{data.get('risk_level', 'N/A')}]")
                c2.markdown(f"**Trend:** {data.get('trend', 'N/A')}")
                
                st.info(f"**Summary:** {data.get('summary', 'No summary')}")
                
                with st.expander("Reasoning & Factors", expanded=True):
                    for factor in data.get('reasoning', []):
                        st.write(f"- {factor}")
                
            except json.JSONDecodeError:
                st.error("Error parsing AI response.")
                st.code(ctx.latest_analysis.get('raw_output', ''))

    # Auto-refresh logic (basic)
    if ctx.is_running:
        time.sleep(2)
        st.rerun()
