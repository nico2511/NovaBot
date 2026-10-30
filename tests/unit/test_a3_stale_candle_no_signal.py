from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from strategies.a3_ema_trend_4h import StrategyA3EmaTrend4h


def _df_with_stale_tail():
    idx = pd.date_range("2024-01-01", periods=5, freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "open": [1, 2, 3, 4, 5],
            "high": [1.1, 2.1, 3.1, 4.1, 5.1],
            "low": [0.9, 1.9, 2.9, 3.9, 4.9],
            "close": [1, 2, 3, 4, 5],
            "volume": [10] * 5,
        },
        index=idx,
    )


def test_stale_4h_frame_rejected_by_a3_forming_check():
    strat = StrategyA3EmaTrend4h({"params": {"min_warmup_bars": 3}})
    df = _df_with_stale_tail()
    with patch("strategies.a3_ema_trend_4h.last_candle_is_forming", return_value=(False, "stale")):
        sig = strat.generate_signal(df, extra_data={"4h": df, "symbol": "ETH"})
    assert sig is None
