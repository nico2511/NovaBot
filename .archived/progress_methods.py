# Progress calculation methods for each strategy
# To be integrated into definitions.py

# ScalpEmaRsi.calculate_progress
def scalp_ema_rsi_progress(self, df, extra_data=None):
    """Calculate progress based on EMA convergence and RSI position"""
    if df.empty or len(df) < 200:
        return 0
    
    self.add_indicators(df)
    params = self.config.get("params", {})
    ema_fast_len = params.get("ema_fast", 9)
    ema_slow_len = params.get("ema_slow", 21)
    rsi_len = params.get("rsi_period", 14)
    
    fast_col = f"EMA_{ema_fast_len}"
    slow_col = f"EMA_{ema_slow_len}"
    trend_col = "EMA_200"
    rsi_col = f"RSI_{rsi_len}"
    
    if trend_col not in df.columns:
        return 0
    
    current_fast = df[fast_col].iloc[-1]
    current_slow = df[slow_col].iloc[-1]
    current_trend = df[trend_col].iloc[-1]
    current_rsi = df[rsi_col].iloc[-1]
    close = df['close'].iloc[-1]
    
    # Calculate EMA distance (normalized)
    ema_diff = abs(current_fast - current_slow)
    ema_avg = (current_fast + current_slow) / 2
    ema_distance_pct = (ema_diff / ema_avg) * 100
    
    # Progress increases as EMAs get closer (50 points max)
    ema_progress = max(0, min(50, 50 * (1 - ema_distance_pct / 0.5)))
    
    # Trend alignment (25 points)
    trend_progress = 0
    if close > current_trend:  # Bullish trend
        if current_fast > current_slow:
            trend_progress = 25
        elif ema_distance_pct < 0.2:
            trend_progress = 15
    elif close < current_trend:  # Bearish trend
        if current_fast < current_slow:
            trend_progress = 25
        elif ema_distance_pct < 0.2:
            trend_progress = 15
    
    # RSI in optimal zone (25 points)
    rsi_progress = 0
    if 50 < current_rsi < 70 or 30 < current_rsi < 50:
        rsi_progress = 25
    elif 40 < current_rsi < 60:
        rsi_progress = 15
    
    return min(100, max(0, int(ema_progress + trend_progress + rsi_progress)))


# StrategySmartTrend.calculate_progress
def smart_trend_progress(self, df, extra_data=None):
    """Calculate progress based on 15m setup + 1m trigger readiness"""
    if df.empty or len(df) < 50:
        return 0
    
    if not extra_data or "1m" not in extra_data:
        return 0
    
    df_1m = extra_data["1m"]
    if df_1m.empty or len(df_1m) < 5:
        return 0
    
    self.add_indicators(df)
    
    # 15m Setup Check (60 points)
    close_15m = df['close'].iloc[-1]
    low_15m = df['low'].iloc[-1]
    high_15m = df['high'].iloc[-1]
    ema_21 = df['EMA_21'].iloc[-1]
    ema_50 = df['EMA_50'].iloc[-1]
    
    setup_progress = 0
    
    # Trend filter (30 points)
    if close_15m > ema_50:  # Bullish trend
        setup_progress += 30
        # Pullback proximity (30 points)
        distance_to_ema21 = abs(low_15m - ema_21) / ema_21 * 100
        if distance_to_ema21 < 0.5:  # Very close
            setup_progress += 30
        elif distance_to_ema21 < 1.0:  # Close
            setup_progress += 20
        elif distance_to_ema21 < 2.0:  # Approaching
            setup_progress += 10
    elif close_15m < ema_50:  # Bearish trend
        setup_progress += 30
        distance_to_ema21 = abs(high_15m - ema_21) / ema_21 * 100
        if distance_to_ema21 < 0.5:
            setup_progress += 30
        elif distance_to_ema21 < 1.0:
            setup_progress += 20
        elif distance_to_ema21 < 2.0:
            setup_progress += 10
    
    # 1m Trigger Check (40 points)
    trigger_progress = 0
    if len(df_1m) >= 4:
        current_1m = df_1m.iloc[-1]
        last_3_1m = df_1m.iloc[-4:-1]
        close_1m = current_1m['close']
        
        high_of_last_3 = last_3_1m['high'].max()
        low_of_last_3 = last_3_1m['low'].min()
        
        # Distance to BOS
        if close_15m > ema_50:  # Looking for bullish BOS
            distance_to_bos = (high_of_last_3 - close_1m) / close_1m * 100
            if distance_to_bos < 0:  # Already broke
                trigger_progress = 40
            elif distance_to_bos < 0.1:  # Very close
                trigger_progress = 35
            elif distance_to_bos < 0.3:  # Close
                trigger_progress = 25
            elif distance_to_bos < 0.5:  # Approaching
                trigger_progress = 15
        elif close_15m < ema_50:  # Looking for bearish BOS
            distance_to_bos = (close_1m - low_of_last_3) / close_1m * 100
            if distance_to_bos < 0:
                trigger_progress = 40
            elif distance_to_bos < 0.1:
                trigger_progress = 35
            elif distance_to_bos < 0.3:
                trigger_progress = 25
            elif distance_to_bos < 0.5:
                trigger_progress = 15
    
    return min(100, max(0, int(setup_progress + trigger_progress)))


# Simple progress for other strategies
def simple_progress(self, df, extra_data=None):
    """Simple progress calculation - returns 50% if conditions partially met"""
    return 50  # Placeholder - can be refined later
