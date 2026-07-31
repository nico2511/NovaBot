"""Unit tests for Hyperliquid tick-size price rounding."""
from __future__ import annotations

import pytest

from app.services.hyperliquid_service import HyperliquidService


# BCH-like: szDecimals=2 → max 4 decimal places, still ≤5 sig figs
BCH_SZ = 2


@pytest.mark.parametrize(
    "raw,sz,expected",
    [
        # Discord incident: trailing SL 206.1280 must snap to 5 sig figs
        (206.1280, BCH_SZ, 206.13),
        (203.5000, BCH_SZ, 203.5),
        (203.5 * 1.05, BCH_SZ, 213.68),  # aggressive TP limit for short close
        (97000.55, 5, 97001.0),  # 5 sig figs → 97001
        (1234.56, 5, 1234.6),  # 5 sig figs, max 1 decimal
        (0.012345, 1, 0.01235),  # 5 sig figs then max 5 decimals
        (100001.7, 5, 100002.0),  # >100k → integer always valid
        (0.0, BCH_SZ, 0.0),
        (-1.0, BCH_SZ, 0.0),
    ],
)
def test_round_price_hl_rules(raw, sz, expected):
    assert HyperliquidService._round_price(raw, sz) == pytest.approx(expected)


def test_round_price_rejects_too_many_sig_figs_for_bch_sl():
    """The exact value that Hyperliquid rejected as 'not divisible by tick size'."""
    rounded = HyperliquidService._round_price(206.1280, 2)
    # Must have ≤5 significant figures
    assert len(f"{rounded:.10g}".replace(".", "").replace("-", "").lstrip("0")) <= 5
    assert rounded == 206.13
