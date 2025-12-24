import streamlit as st
import time
import threading
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.gemini_service import gemini_service
from app.services.discord_service import discord_service
from strategies.engine import StrategyEngine
from app.ui.sidebar import render_sidebar
from app.ui.charts import render_charts

# Page Config
st.set_page_config(page_title="HyperLiquid AI Trader", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# --- Global State (Singleton) ---
class BotContext:
    def __init__(self):
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False  # New flag
        self.thread = None
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = [] # List of dicts
        self.logs = [] # Console logs
        self.latest_strategy_result = {}
        self.active_symbol = "BTC"
        self.last_candle_time = None
        self.active_trade = None # Current open position

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
                            
                            # Log Exit
                            self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} {msg}")
                            discord_service.send_log(msg)
                            self.active_trade = None # Reset
                    
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
                                
                                # Open Phantom Trade
                                self.active_trade = {
                                    "symbol": symbol,
                                    "side": action,
                                    "entry": entry_price,
                                    "sl": sl,
                                    "tp": tp,
                                    "strategy": strat_name
                                }
                                
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
                                
                                if self.trading_enabled:
                                    # hyperliquid_service.execute_order(...)
                                    pass
                else:
                    self.logs.append(f"{pd.Timestamp.now().strftime('%H:%M:%S')} Waiting for data...")
                
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
    sidebar_state = render_sidebar(ctx.risk_manager, ctx.is_running)
    ctx.trading_enabled = sidebar_state.get("trading_enabled", False)

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

    # Main Layout
    st.title("⚡ HyperLiquid AI Trader v2.0")

    # Top Metrics
    # Top Metrics - Responsive Layout (Mobile Friendly)
    # Row 1: Status, Asset, Mode
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        if ctx.is_running:
            with st.status("Engine Active", expanded=False, state="running") as status:
                st.write("Fetching market data...")
                if ctx.active_trade:
                    t = ctx.active_trade
                    status.update(label=f"🟢 IN TRADE: {t['side']} {t['symbol']}", state="complete", expanded=False)
                    st.write(f"Entry: {t['entry']}")
                    st.write(f"SL: {t['sl']} | TP: {t['tp']}")
                else:
                    st.write("Scanning for opportunities...")
        else:
            st.metric("Status", "STOPPED", delta_color="off")
    with row1_col2:
        st.metric("Asset", sidebar_state["asset"])
    with row1_col3:
        st.metric("Mode", sidebar_state["mode"])

    # Row 2: Price, Active Strategy
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        last_price = ctx.latest_data['close'].iloc[-1] if not ctx.latest_data.empty else 0.0
        st.metric("Price", f"${last_price:,.2f}")
    with row2_col2:
        # Active Strategy Display
        active_strats = ctx.latest_strategy_result.get("strategies", []) if hasattr(ctx, 'latest_strategy_result') else []
        strat_text = ", ".join(active_strats) if active_strats else "WAITING..."
        st.metric("Active Strategy", strat_text)

    # --- SECTION 1: CHARTS (Always Visible) ---
    st.markdown("### 📊 Market Data")
    if not ctx.latest_data.empty:
        render_charts(ctx.latest_data, ctx.signals_log)
    else:
        st.info("Waiting for data... Ensure Engine is ON.")

    st.divider()

    # --- SECTION 2: INSIGHTS & LOGS (Split View) ---
    c_left, c_right = st.columns([1, 1])

    with c_left:
        if ctx.signals_log:
            st.dataframe(pd.DataFrame(ctx.signals_log), height=200, use_container_width=True)
        else:
            st.info("📡 No Live Signals yet.")

        # Simple log buffer display
        log_text = "\n".join(ctx.logs[-20:]) if hasattr(ctx, 'logs') and ctx.logs else "⏳ Waiting for logs..."
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
