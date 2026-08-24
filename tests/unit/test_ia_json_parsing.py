"""
Unit tests for IAService JSON extraction and repair (AI validation responses).
"""
from __future__ import annotations

import json

import pytest

from app.services.ia import IAService


@pytest.fixture
def ia():
    return IAService()


def test_extract_json_from_markdown_fence(ia):
    raw = """Here is my analysis:
```json
{
  "approved": true,
  "confidence": 80,
  "reasoning": "Strong trend"
}
```
"""
    extracted = ia.extract_json(raw)
    parsed = json.loads(extracted)
    assert parsed["approved"] is True
    assert parsed["confidence"] == 80


def test_extract_json_nested_object_not_truncated(ia):
    raw = json.dumps(
        {
            "approved": False,
            "confidence": 55,
            "suggested_adjustments": {"sl": 0.12, "tp": 0.11},
            "reasoning": "nested",
        }
    )
    assert json.loads(ia.extract_json(raw))["suggested_adjustments"]["sl"] == 0.12


def test_repair_json_placeholder_confidence(ia):
    broken = """{
  "approved": false,
  "confidence": <0-100>,
  "reasoning": "test"
}"""
    repaired = ia.repair_json(broken)
    parsed = json.loads(repaired)
    assert parsed["confidence"] == 50


def test_parse_json_response_repairs_template_literals(ia):
    broken = """{
  "approved": true|false,
  "confidence": <0-100>,
  "risk_score": <1-10>,
  "reasoning": "Momentum aligned",
  "rejection_reason_category": "See System Prompt ENUM" | null
}"""
    parsed = ia.parse_json_response(broken)
    assert parsed["approved"] is False
    assert parsed["confidence"] == 50
    assert parsed["risk_score"] == 5
    assert parsed["rejection_reason_category"] is None


def test_parse_validation_payload_handles_malformed_llm_output(ia):
    result = {
        "raw_output": """{
  "approved": false,
  "confidence": <0-100>,
  "reasoning": "Counter-trend risk"
}""",
        "model": "test-model",
    }
    out = ia._parse_validation_payload(result)
    assert out.get("rejection_reason_category") != "AI_PARSE_ERROR"
    assert out["approved"] is False
    assert out["confidence"] == 50
    assert "Counter-trend risk" in out["reasoning"]


def test_parse_json_response_repairs_unquoted_risk_level_enum(ia):
    broken = """{
  "approved": false,
  "risk_level": LOW|MEDIUM|HIGH,
  "confidence": 68,
  "reasoning": "Weak momentum"
}"""
    parsed = ia.parse_json_response(broken)
    assert parsed["risk_level"] == "MEDIUM"
    assert parsed["confidence"] == 68


def test_parse_json_response_recovers_partial_json_via_fallback(ia):
    broken = """{
  "approved": true,
  "confidence": 81,
  "reasoning": "Breakout confirmed",
  "risk_level": LOW|MEDIUM|HIGH,
  "suggested_adjustments": {"sl": number | null}
}"""
    parsed = ia.parse_json_response(broken)
    assert parsed["approved"] is True
    assert parsed["confidence"] == 81


def test_parse_json_response_repairs_quoted_null_prices(ia):
    raw = """{
  "approved": true,
  "confidence": 66,
  "reasoning": "ok",
  "suggested_adjustments": {"sl": "null", "tp": "null"}
}"""
    repaired = ia.repair_json(raw)
    assert '"sl":null' in repaired.replace(" ", "")
    out = ia.parse_json_response(raw)
    assert out["suggested_adjustments"]["sl"] is None
    assert out["suggested_adjustments"]["tp"] is None


def test_coerce_optional_price_null_like():
    from app.services.ia import coerce_optional_price

    assert coerce_optional_price(None) is None
    assert coerce_optional_price("null") is None
    assert coerce_optional_price("NULL") is None
    assert coerce_optional_price("") is None
    assert coerce_optional_price("n/a") is None
    assert coerce_optional_price(0.095) == pytest.approx(0.095)
    assert coerce_optional_price("$0.10") == pytest.approx(0.10)
    assert coerce_optional_price("abc") is None


def test_normalize_suggested_adjustments_string_null():
    from app.services.ia import normalize_suggested_adjustments

    payload = {"suggested_adjustments": {"sl": "null", "tp": "0.12"}}
    out = normalize_suggested_adjustments(payload)
    assert out["suggested_adjustments"]["sl"] is None
    assert out["suggested_adjustments"]["tp"] == pytest.approx(0.12)


def test_parse_validation_payload_normalizes_quoted_null(ia):
    result = {
        "raw_output": """{
  "approved": true,
  "confidence": 66,
  "reasoning": "Strong R:R",
  "suggested_adjustments": {"sl": "null", "tp": "null"}
}""",
        "model": "test-model",
    }
    out = ia._parse_validation_payload(result)
    assert out["approved"] is True
    assert out["suggested_adjustments"]["sl"] is None
    assert out["suggested_adjustments"]["tp"] is None


def test_parse_validation_payload_marks_unrecoverable_as_parse_error(ia):
    result = {"raw_output": "not json at all", "model": "test-model"}
    out = ia._parse_validation_payload(result)
    assert out["rejection_reason_category"] == "AI_PARSE_ERROR"
    assert out["approved"] is False
