from __future__ import annotations

from pathlib import Path


def test_entry_balance_preflight_occurs_before_ai_validate_in_source():
    src = Path("app/core/bot.py").read_text(encoding="utf-8")
    pre = src.find("_entry_balance_preflight")
    ai = src.find("ia_service.validate_signal")
    assert pre != -1 and ai != -1
    assert pre < ai
