"""Parser tests for the Binance Vision proxy. No network."""
from app.core.proxy_ohlcv import funding_csv_to_frame, gap_count, klines_csv_to_frame, proxy_symbol


KLINE = """1709251200000,64000,64100,63900,64050,12.5,1709251259999,1,2,3,4,0
1709251260000,64050,64200,64040,64110,8.0,1709251319999,1,2,3,4,0
"""

KLINE_HEADER = """open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore
1709251200000,64000,64100,63900,64050,12.5,1709251259999,1,2,3,4,0
"""

FUNDING = """calc_time,funding_interval_hours,last_funding_rate
1785542400000,8,0.00004123
1785571200000,8,-0.00001000
"""


def test_proxy_symbol_maps_to_usdt_perp():
    assert proxy_symbol("btc") == "BTCUSDT"
    assert proxy_symbol("HYPE") == "HYPEUSDT"


def test_klines_csv_without_header():
    frame = klines_csv_to_frame(KLINE)
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert len(frame) == 2
    assert frame.index.tz is not None
    assert float(frame["close"].iloc[0]) == 64050.0
    assert float(frame["volume"].iloc[1]) == 8.0


def test_klines_csv_with_header():
    frame = klines_csv_to_frame(KLINE_HEADER)
    assert len(frame) == 1
    assert float(frame["open"].iloc[0]) == 64000.0


def test_funding_csv_is_settlement_rate():
    frame = funding_csv_to_frame(FUNDING)
    assert list(frame.columns) == ["funding_rate"]
    assert len(frame) == 2
    assert abs(float(frame["funding_rate"].iloc[0]) - 0.00004123) < 1e-12
    assert float(frame["funding_rate"].iloc[1]) < 0


def test_gap_count_flags_a_hole():
    text = """1709251200000,1,1,1,1,1,0,0,0,0,0,0
1709251260000,1,1,1,1,1,0,0,0,0,0,0
1709251440000,1,1,1,1,1,0,0,0,0,0,0
"""
    frame = klines_csv_to_frame(text)
    assert gap_count(frame, "1m") == 1
