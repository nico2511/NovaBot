"""
Strategy Monitor Component
Displays real-time thresholds and conditions for active strategies
"""
import streamlit as st
import pandas as pd

def render_strategy_monitor(df: pd.DataFrame, strategy_result: dict, strategies_config: dict):
    """
    Render real-time strategy monitoring dashboard
    Shows what each active strategy is watching
    
    Args:
        df: Current market data
        strategy_result: Result from StrategyEngine.analyze()
        strategies_config: Configuration from strategies.json
    """
    if df.empty or not strategy_result:
        st.info("⏳ Waiting for market data...")
        return
    
    st.markdown("### 🔬 Strategy Monitor")
    
    # Active strategies
    active_strategies = strategy_result.get('strategies', [])
    
    if not active_strategies:
        st.warning("⚠️ No active strategies for current market regime")
        return
    
    # Get current values
    close = df['close'].iloc[-1]
    
    # Calculate indicators if not already done
    if 'ADX_14' not in df.columns:
        df.ta.adx(length=14, append=True)
    if 'RSI_14' not in df.columns:
        df.ta.rsi(length=14, append=True)
    if 'ATRr_14' not in df.columns:
        df.ta.atr(length=14, append=True)
    
    adx = df['ADX_14'].iloc[-1] if 'ADX_14' in df.columns else 0
    rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
    atr = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else 0
    
    # Market Regime in a compact row
    regime = strategy_result.get('regime', 'UNKNOWN')
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Regime", regime, f"ADX {adx:.1f}")
    with col2:
        rsi_label = "Oversold" if rsi < 30 else "Overbought" if rsi > 70 else "Neutral"
        st.metric("RSI", f"{rsi:.1f}", rsi_label)
    with col3:
        st.metric("ATR", f"${atr:,.2f}")
    
    st.markdown("---")
    
    # Display all strategies in columns (max 2 per row for readability)
    num_strategies = len(active_strategies)
    cols_per_row = min(2, num_strategies)
    
    for i in range(0, num_strategies, cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            if i + j < num_strategies:
                with col:
                    strategy_name = active_strategies[i + j]
                    render_strategy_compact(strategy_name, df, strategies_config, close)

def render_strategy_compact(strategy_name: str, df: pd.DataFrame, strategies_config: dict, close: float):
    """Render a compact strategy card"""
    strat_config = strategies_config.get('strategies', {}).get(strategy_name.lower().replace(' ', '_'), {})
    params = strat_config.get('params', {})
    
    st.markdown(f"**{strategy_name}**")
    
    if strategy_name == "ScalpEmaRsi":
        render_scalp_compact(df, params, close)
    elif strategy_name == "InstitutionalScalp":
        render_institutional_compact(df, params, close)
    elif strategy_name == "SwingTrendPullback":
        render_swing_compact(df, params, close)
    elif strategy_name == "MeanReversion":
        render_mean_reversion_compact(df, params, close)
    elif strategy_name == "SMCFVG":
        render_smcfvg_compact(df, params, close)

def render_scalp_compact(df, params, close):
    """Compact ScalpEmaRsi monitor"""
    ema_fast = params.get('ema_fast', 9)
    ema_slow = params.get('ema_slow', 21)
    
    df.ta.ema(length=ema_fast, append=True)
    df.ta.ema(length=ema_slow, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=14, append=True)
    
    ema9 = df[f'EMA_{ema_fast}'].iloc[-1] if f'EMA_{ema_fast}' in df.columns else 0
    ema21 = df[f'EMA_{ema_slow}'].iloc[-1] if f'EMA_{ema_slow}' in df.columns else 0
    ema200 = df['EMA_200'].iloc[-1] if 'EMA_200' in df.columns else 0
    rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
    
    st.caption(f"{'✅' if ema9 > ema21 else '❌'} EMA {ema_fast}/{ema_slow}: {ema9:.0f}/{ema21:.0f}")
    st.caption(f"{'✅' if close > ema200 else '❌'} Trend: ${close:.0f} vs ${ema200:.0f}")
    st.caption(f"{'✅' if 30 < rsi < 70 else '❌'} RSI: {rsi:.1f}")

def render_institutional_compact(df, params, close):
    """Compact InstitutionalScalp monitor"""
    lookback = params.get('liq_grab_lookback', 20)
    recent = df.tail(lookback + 1)
    recent_high = recent['high'].iloc[:-1].max()
    recent_low = recent['low'].iloc[:-1].min()
    current_high = df['high'].iloc[-1]
    current_low = df['low'].iloc[-1]
    
    st.caption(f"{'✅' if current_low < recent_low and close > recent_low else '❌'} Bull Grab: ${recent_low:.0f}")
    st.caption(f"{'✅' if current_high > recent_high and close < recent_high else '❌'} Bear Grab: ${recent_high:.0f}")
    st.caption(f"Lookback: {lookback} candles")

def render_swing_compact(df, params, close):
    """Compact SwingTrendPullback monitor"""
    ema_trend = params.get('ema_trend', 200)
    ema_fast = params.get('ema_pullback_fast', 20)
    
    df.ta.ema(length=ema_trend, append=True)
    df.ta.ema(length=ema_fast, append=True)
    df.ta.rsi(length=14, append=True)
    
    trend = df[f'EMA_{ema_trend}'].iloc[-1] if f'EMA_{ema_trend}' in df.columns else 0
    ema_fast_val = df[f'EMA_{ema_fast}'].iloc[-1] if f'EMA_{ema_fast}' in df.columns else 0
    rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
    low = df['low'].iloc[-1]
    
    st.caption(f"{'✅' if close > trend else '❌'} Trend: ${trend:.0f}")
    st.caption(f"{'✅' if low <= ema_fast_val else '❌'} Pullback: ${ema_fast_val:.0f}")
    st.caption(f"RSI: {rsi:.1f}")

def render_mean_reversion_compact(df, params, close):
    """Compact MeanReversion monitor"""
    bb_length = params.get('bb_length', 20)
    bb_std = params.get('bb_std', 2.0)
    
    df.ta.bbands(length=bb_length, std=bb_std, append=True)
    df.ta.rsi(length=14, append=True)
    
    bb_upper = df[f'BBU_{bb_length}_{bb_std}'].iloc[-1] if f'BBU_{bb_length}_{bb_std}' in df.columns else 0
    bb_lower = df[f'BBL_{bb_length}_{bb_std}'].iloc[-1] if f'BBL_{bb_length}_{bb_std}' in df.columns else 0
    rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
    
    st.caption(f"BB: ${bb_lower:.0f} - ${bb_upper:.0f}")
    st.caption(f"{'✅' if close <= bb_lower and rsi < 30 else '❌'} Oversold")
    st.caption(f"{'✅' if close >= bb_upper and rsi > 70 else '❌'} Overbought")

def render_smcfvg_compact(df, params, close):
    """Compact SMCFVG monitor"""
    if len(df) < 3:
        st.caption("Not enough data")
        return
    
    candle_1 = df.iloc[-3]
    candle_3 = df.iloc[-1]
    
    bullish_gap = candle_3['low'] - candle_1['high']
    bearish_gap = candle_1['low'] - candle_3['high']
    
    st.caption(f"{'✅' if bullish_gap > 0 else '❌'} Bull FVG: ${bullish_gap:.2f}")
    st.caption(f"{'✅' if bearish_gap > 0 else '❌'} Bear FVG: ${bearish_gap:.2f}")
    st.caption(f"Price: ${close:.0f}")

def render_strategy_details(strategy_name: str, df: pd.DataFrame, strategies_config: dict):
    """
    Render detailed monitoring for a specific strategy
    """
    close = df['close'].iloc[-1]
    
    # Get strategy config
    strat_config = strategies_config.get('strategies', {}).get(strategy_name.lower().replace(' ', '_'), {})
    params = strat_config.get('params', {})
    
    if strategy_name == "ScalpEmaRsi":
        render_scalp_ema_rsi_monitor(df, params, close)
    
    elif strategy_name == "InstitutionalScalp":
        render_institutional_scalp_monitor(df, params, close)
    
    elif strategy_name == "SwingTrendPullback":
        render_swing_trend_monitor(df, params, close)
    
    elif strategy_name == "MeanReversion":
        render_mean_reversion_monitor(df, params, close)
    
    elif strategy_name == "SMCFVG":
        render_smcfvg_monitor(df, params, close)
    
    else:
        st.info(f"Monitoring for {strategy_name} not yet implemented")

def render_scalp_ema_rsi_monitor(df, params, close):
    """ScalpEmaRsi strategy monitor"""
    ema_fast = params.get('ema_fast', 9)
    ema_slow = params.get('ema_slow', 21)
    rsi_period = params.get('rsi_period', 14)
    
    # Calculate indicators
    df.ta.ema(length=ema_fast, append=True)
    df.ta.ema(length=ema_slow, append=True)
    df.ta.ema(length=200, append=True)
    df.ta.rsi(length=rsi_period, append=True)
    
    ema9 = df[f'EMA_{ema_fast}'].iloc[-1] if f'EMA_{ema_fast}' in df.columns else 0
    ema21 = df[f'EMA_{ema_slow}'].iloc[-1] if f'EMA_{ema_slow}' in df.columns else 0
    ema200 = df['EMA_200'].iloc[-1] if 'EMA_200' in df.columns else 0
    rsi = df[f'RSI_{rsi_period}'].iloc[-1] if f'RSI_{rsi_period}' in df.columns else 0
    
    st.markdown("#### 📊 Conditions Monitored")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 LONG Signal Conditions:**")
        
        # EMA Cross
        cross_status = "✅" if ema9 > ema21 else "❌"
        st.markdown(f"{cross_status} EMA {ema_fast} > EMA {ema_slow}")
        st.caption(f"Current: ${ema9:,.2f} vs ${ema21:,.2f}")
        
        # Trend filter
        trend_status = "✅" if close > ema200 else "❌"
        st.markdown(f"{trend_status} Price > EMA 200 (Trend)")
        st.caption(f"Current: ${close:,.2f} vs ${ema200:,.2f}")
        
        # RSI
        rsi_status = "✅" if 50 < rsi < 70 else "❌"
        st.markdown(f"{rsi_status} RSI between 50-70")
        st.caption(f"Current: {rsi:.1f}")
    
    with col2:
        st.markdown("**🔴 SHORT Signal Conditions:**")
        
        # EMA Cross
        cross_status = "✅" if ema9 < ema21 else "❌"
        st.markdown(f"{cross_status} EMA {ema_fast} < EMA {ema_slow}")
        st.caption(f"Current: ${ema9:,.2f} vs ${ema21:,.2f}")
        
        # Trend filter
        trend_status = "✅" if close < ema200 else "❌"
        st.markdown(f"{trend_status} Price < EMA 200 (Trend)")
        st.caption(f"Current: ${close:,.2f} vs ${ema200:,.2f}")
        
        # RSI
        rsi_status = "✅" if 30 < rsi < 50 else "❌"
        st.markdown(f"{rsi_status} RSI between 30-50")
        st.caption(f"Current: {rsi:.1f}")

def render_institutional_scalp_monitor(df, params, close):
    """InstitutionalScalp strategy monitor"""
    lookback = params.get('liq_grab_lookback', 20)
    
    recent = df.tail(lookback + 1)
    recent_high = recent['high'].iloc[:-1].max()
    recent_low = recent['low'].iloc[:-1].min()
    
    current_high = df['high'].iloc[-1]
    current_low = df['low'].iloc[-1]
    
    st.markdown("#### 🎯 Liquidity Zones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 Bullish Liquidity Grab:**")
        
        # Check if wick went below recent low
        wick_status = "✅" if current_low < recent_low else "❌"
        st.markdown(f"{wick_status} Wick below recent low")
        st.caption(f"Current Low: ${current_low:,.2f}")
        st.caption(f"Recent Low: ${recent_low:,.2f}")
        
        # Check if closed above
        close_status = "✅" if close > recent_low else "❌"
        st.markdown(f"{close_status} Close above recent low (rejection)")
        st.caption(f"Close: ${close:,.2f}")
    
    with col2:
        st.markdown("**🔴 Bearish Liquidity Grab:**")
        
        # Check if wick went above recent high
        wick_status = "✅" if current_high > recent_high else "❌"
        st.markdown(f"{wick_status} Wick above recent high")
        st.caption(f"Current High: ${current_high:,.2f}")
        st.caption(f"Recent High: ${recent_high:,.2f}")
        
        # Check if closed below
        close_status = "✅" if close < recent_high else "❌"
        st.markdown(f"{close_status} Close below recent high (rejection)")
        st.caption(f"Close: ${close:,.2f}")
    
    st.info(f"📏 Lookback period: {lookback} candles")

def render_swing_trend_monitor(df, params, close):
    """SwingTrendPullback strategy monitor"""
    ema_trend = params.get('ema_trend', 200)
    ema_fast = params.get('ema_pullback_fast', 20)
    rsi_min_long = params.get('rsi_min_long', 40)
    rsi_max_short = params.get('rsi_max_short', 60)
    
    # Calculate indicators
    df.ta.ema(length=ema_trend, append=True)
    df.ta.ema(length=ema_fast, append=True)
    df.ta.rsi(length=14, append=True)
    df.ta.atr(length=14, append=True)
    
    trend = df[f'EMA_{ema_trend}'].iloc[-1] if f'EMA_{ema_trend}' in df.columns else 0
    ema_fast_val = df[f'EMA_{ema_fast}'].iloc[-1] if f'EMA_{ema_fast}' in df.columns else 0
    rsi = df['RSI_14'].iloc[-1] if 'RSI_14' in df.columns else 0
    atr = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else 0
    
    low = df['low'].iloc[-1]
    high = df['high'].iloc[-1]
    
    st.markdown("#### 📈 Pullback Conditions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 LONG (Bullish Trend):**")
        
        trend_status = "✅" if close > trend else "❌"
        st.markdown(f"{trend_status} Price > EMA {ema_trend} (Uptrend)")
        st.caption(f"${close:,.2f} vs ${trend:,.2f}")
        
        pullback_status = "✅" if low <= ema_fast_val else "❌"
        st.markdown(f"{pullback_status} Low touched EMA {ema_fast}")
        st.caption(f"Low: ${low:,.2f} vs EMA: ${ema_fast_val:,.2f}")
        
        rsi_status = "✅" if rsi > rsi_min_long else "❌"
        st.markdown(f"{rsi_status} RSI > {rsi_min_long}")
        st.caption(f"Current: {rsi:.1f}")
        
        vol_status = "✅" if atr > (close * 0.002) else "❌"
        st.markdown(f"{vol_status} Sufficient volatility")
        st.caption(f"ATR: ${atr:,.2f} (min: ${close * 0.002:,.2f})")
    
    with col2:
        st.markdown("**🔴 SHORT (Bearish Trend):**")
        
        trend_status = "✅" if close < trend else "❌"
        st.markdown(f"{trend_status} Price < EMA {ema_trend} (Downtrend)")
        st.caption(f"${close:,.2f} vs ${trend:,.2f}")
        
        pullback_status = "✅" if high >= ema_fast_val else "❌"
        st.markdown(f"{pullback_status} High touched EMA {ema_fast}")
        st.caption(f"High: ${high:,.2f} vs EMA: ${ema_fast_val:,.2f}")
        
        rsi_status = "✅" if rsi < rsi_max_short else "❌"
        st.markdown(f"{rsi_status} RSI < {rsi_max_short}")
        st.caption(f"Current: {rsi:.1f}")
        
        vol_status = "✅" if atr > (close * 0.002) else "❌"
        st.markdown(f"{vol_status} Sufficient volatility")
        st.caption(f"ATR: ${atr:,.2f} (min: ${close * 0.002:,.2f})")

def render_mean_reversion_monitor(df, params, close):
    """MeanReversion strategy monitor"""
    bb_length = params.get('bb_length', 20)
    bb_std = params.get('bb_std', 2.0)
    rsi_period = params.get('rsi_period', 14)
    
    # Calculate indicators
    df.ta.bbands(length=bb_length, std=bb_std, append=True)
    df.ta.rsi(length=rsi_period, append=True)
    
    bb_upper = df[f'BBU_{bb_length}_{bb_std}'].iloc[-1] if f'BBU_{bb_length}_{bb_std}' in df.columns else 0
    bb_middle = df[f'BBM_{bb_length}_{bb_std}'].iloc[-1] if f'BBM_{bb_length}_{bb_std}' in df.columns else 0
    bb_lower = df[f'BBL_{bb_length}_{bb_std}'].iloc[-1] if f'BBL_{bb_length}_{bb_std}' in df.columns else 0
    rsi = df[f'RSI_{rsi_period}'].iloc[-1] if f'RSI_{rsi_period}' in df.columns else 0
    
    st.markdown("#### 📊 Bollinger Bands + RSI")
    
    # Visual representation
    distance_to_upper = ((close - bb_upper) / bb_upper) * 100
    distance_to_lower = ((close - bb_lower) / bb_lower) * 100
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Upper Band", f"${bb_upper:,.2f}", f"{distance_to_upper:+.2f}%")
    
    with col2:
        st.metric("Middle Band", f"${bb_middle:,.2f}")
    
    with col3:
        st.metric("Lower Band", f"${bb_lower:,.2f}", f"{distance_to_lower:+.2f}%")
    
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 LONG (Oversold Bounce):**")
        
        bb_status = "✅" if close <= bb_lower else "❌"
        st.markdown(f"{bb_status} Price at/below lower band")
        st.caption(f"${close:,.2f} vs ${bb_lower:,.2f}")
        
        rsi_status = "✅" if rsi < 30 else "❌"
        st.markdown(f"{rsi_status} RSI < 30 (Oversold)")
        st.caption(f"Current: {rsi:.1f}")
        
        st.info(f"🎯 Target: Middle Band (${bb_middle:,.2f})")
    
    with col2:
        st.markdown("**🔴 SHORT (Overbought Pullback):**")
        
        bb_status = "✅" if close >= bb_upper else "❌"
        st.markdown(f"{bb_status} Price at/above upper band")
        st.caption(f"${close:,.2f} vs ${bb_upper:,.2f}")
        
        rsi_status = "✅" if rsi > 70 else "❌"
        st.markdown(f"{rsi_status} RSI > 70 (Overbought)")
        st.caption(f"Current: {rsi:.1f}")
        
        st.info(f"🎯 Target: Middle Band (${bb_middle:,.2f})")

def render_smcfvg_monitor(df, params, close):
    """SMCFVG strategy monitor"""
    fvg_threshold = params.get('fvg_threshold', 0.005)
    
    if len(df) < 3:
        st.warning("Not enough candles for FVG detection")
        return
    
    candle_1 = df.iloc[-3]
    candle_2 = df.iloc[-2]
    candle_3 = df.iloc[-1]
    
    # Bullish FVG
    bullish_fvg_top = candle_3['low']
    bullish_fvg_bottom = candle_1['high']
    bullish_gap = bullish_fvg_top - bullish_fvg_bottom
    bullish_gap_pct = (bullish_gap / bullish_fvg_bottom) * 100 if bullish_fvg_bottom > 0 else 0
    
    # Bearish FVG
    bearish_fvg_bottom = candle_3['high']
    bearish_fvg_top = candle_1['low']
    bearish_gap = bearish_fvg_top - bearish_fvg_bottom
    bearish_gap_pct = (bearish_gap / bearish_fvg_top) * 100 if bearish_fvg_top > 0 else 0
    
    st.markdown("#### 🎯 Fair Value Gaps (FVG)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**🔵 Bullish FVG:**")
        
        gap_exists = bullish_gap > 0
        gap_status = "✅" if gap_exists else "❌"
        st.markdown(f"{gap_status} Gap exists")
        
        if gap_exists:
            st.caption(f"Gap: ${bullish_fvg_bottom:,.2f} → ${bullish_fvg_top:,.2f}")
            st.caption(f"Size: ${bullish_gap:,.2f} ({bullish_gap_pct:.2f}%)")
            
            threshold_status = "✅" if bullish_gap_pct >= (fvg_threshold * 100) else "❌"
            st.markdown(f"{threshold_status} Gap > {fvg_threshold*100:.2f}% threshold")
            
            in_zone = bullish_fvg_bottom * 0.998 <= close <= bullish_fvg_top
            zone_status = "✅" if in_zone else "❌"
            st.markdown(f"{zone_status} Price in FVG zone")
        else:
            st.caption("No bullish gap detected")
    
    with col2:
        st.markdown("**🔴 Bearish FVG:**")
        
        gap_exists = bearish_gap > 0
        gap_status = "✅" if gap_exists else "❌"
        st.markdown(f"{gap_status} Gap exists")
        
        if gap_exists:
            st.caption(f"Gap: ${bearish_fvg_bottom:,.2f} → ${bearish_fvg_top:,.2f}")
            st.caption(f"Size: ${bearish_gap:,.2f} ({bearish_gap_pct:.2f}%)")
            
            threshold_status = "✅" if bearish_gap_pct >= (fvg_threshold * 100) else "❌"
            st.markdown(f"{threshold_status} Gap > {fvg_threshold*100:.2f}% threshold")
            
            in_zone = bearish_fvg_bottom <= close <= bearish_fvg_top * 1.002
            zone_status = "✅" if in_zone else "❌"
            st.markdown(f"{zone_status} Price in FVG zone")
        else:
            st.caption("No bearish gap detected")
    
    st.info(f"📏 Minimum gap threshold: {fvg_threshold*100:.2f}%")
