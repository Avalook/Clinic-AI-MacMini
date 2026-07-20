"""Unit tests for lab.classify (rules + LLM fallback via AnthropicClient).

LLM fallback paths use AsyncMock to swap out `AnthropicClient.chat`. Rule
paths still pass a mock gateway, then assert gateway.chat is never awaited
to verify we short-circuited on the rule.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.llm.anthropic_client import LLMResponse
from clinicai.tools._common.context import new_trace
from clinicai.tools.lab.classify import (
    ClassifyResult,
    classify_lab_result,
)
from clinicai.tools.lab.query_lab_result import LabResultRow

_NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def make_lab_row(**overrides: Any) -> LabResultRow:
    """Build a LabResultRow with sane defaults; tests override what they care about."""
    defaults: dict[str, Any] = {
        "lab_result_id": uuid4(),
        "clinic_patient_id": uuid4(),
        "visit_id": None,
        "appointment_id": None,
        "test_code": "TEST",
        "test_name": "Generic test",
        "panel_code": None,
        "result_value": None,
        "result_numeric": None,
        "result_unit": None,
        "reference_range_low": None,
        "reference_range_high": None,
        "flag": None,
        "triage_group": "PENDING",
        "triage_reason": None,
        "requires_doctor_review": False,
        "reviewed_by_staff_id": None,
        "reviewed_at": None,
        "is_finalized": False,
        "lab_provider": None,
        "sample_collected_at": None,
        "result_received_at": _NOW,
    }
    defaults.update(overrides)
    return LabResultRow(**defaults)


def _mock_gateway_with_text(text: str) -> MagicMock:
    """Return a MagicMock gateway whose `.chat(...)` resolves to LLMResponse."""
    gateway = MagicMock()
    gateway.chat = AsyncMock(
        return_value=LLMResponse(
            text=text,
            model="claude-haiku-4-5-20251001",
            input_tokens=10,
            output_tokens=20,
            latency_ms=30,
            stop_reason="end_turn",
        )
    )
    return gateway


# ─────────────────────────── Rule matching tests ───────────────────────────


@pytest.mark.asyncio
async def test_classify__hiv_positive_panel__group_c_with_review_required() -> None:
    row = make_lab_row(
        test_name="HIV antibody",
        test_code="HIV-AB",
        panel_code="HIV",
        flag="POSITIVE",
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert isinstance(result, ClassifyResult)
    assert result.source == "RULE"
    assert result.triage_group == "GROUP_C"
    assert result.requires_doctor_review is True
    assert result.matched_rule_key == "HIV_REACTIVE"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__nipt_high_risk__group_c() -> None:
    row = make_lab_row(
        test_name="NIPT Trisomy 21",
        test_code="NIPT-T21",
        panel_code="NIPT_T21",
        flag="HIGH_RISK",
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_C"
    assert result.requires_doctor_review is True
    assert result.matched_rule_key == "NIPT_HIGH_RISK"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__glucose_gestational__group_b_no_review() -> None:
    row = make_lab_row(
        test_name="Glucose",
        test_code="GLU",
        panel_code="GLU",
        result_numeric=Decimal("8.5"),
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_B"
    assert result.requires_doctor_review is False
    assert result.matched_rule_key == "GLUCOSE_GESTATIONAL_HIGH"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__hemoglobin_low__group_b() -> None:
    row = make_lab_row(
        test_name="Hemoglobin",
        test_code="HGB",
        panel_code="HGB",
        result_numeric=Decimal("10.0"),
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_B"
    assert result.matched_rule_key == "HEMOGLOBIN_LOW_PREGNANCY"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__normal_in_range__group_a() -> None:
    row = make_lab_row(
        test_name="CBC",
        test_code="CBC",
        panel_code="CBC",
        result_numeric=Decimal("5.0"),
        reference_range_low=Decimal("4.0"),
        reference_range_high=Decimal("6.0"),
        flag="N",
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_A"
    assert result.matched_rule_key == "FLAG_NORMAL"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__priority_order__group_c_wins_over_group_b() -> None:
    """HIV (priority 100) must beat FLAG_HIGH_GENERIC (priority 10) when both match."""
    row = make_lab_row(
        test_name="HIV antibody",
        test_code="HIV-AB",
        panel_code="HIV",
        flag="POSITIVE",
        result_numeric=Decimal("99.0"),
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_C"
    assert result.matched_rule_key == "HIV_REACTIVE"


@pytest.mark.asyncio
async def test_classify__hbv_high_viral_load__group_c() -> None:
    row = make_lab_row(
        test_name="HBV DNA viral load",
        test_code="HBV-DNA",
        panel_code="HBV_DNA",
        result_numeric=Decimal("150000"),
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_C"
    assert result.matched_rule_key == "HBV_HIGH_VIRAL_LOAD"
    gateway.chat.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify__hcg_declining__group_c() -> None:
    row = make_lab_row(
        test_name="Beta hCG",
        test_code="BHCG",
        panel_code="BETA_HCG",
        flag="DECLINING",
    )
    gateway = _mock_gateway_with_text("unused")

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "RULE"
    assert result.triage_group == "GROUP_C"
    assert result.matched_rule_key == "HCG_PREGNANCY_DECLINING"
    gateway.chat.assert_not_awaited()


# ─────────────────────────── LLM fallback tests ───────────────────────────


@pytest.mark.asyncio
async def test_classify__no_rule_match__fallback_haiku() -> None:
    row = make_lab_row(
        test_name="Unknown screening",
        test_code="UNK-1",
        panel_code="UNKNOWN_PANEL",
        flag=None,
        result_numeric=None,
    )
    llm_json = (
        '{"triage_group": "GROUP_B", "requires_doctor_review": false,'
        ' "reason": "Theo dõi", "confidence": 0.6}'
    )
    gateway = _mock_gateway_with_text(llm_json)

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "LLM_HAIKU"
    assert result.triage_group == "GROUP_B"
    assert result.matched_rule_key is None
    gateway.chat.assert_awaited_once()
    kwargs = gateway.chat.await_args.kwargs
    assert kwargs["tier"] == "gateway"


@pytest.mark.asyncio
async def test_classify__no_rule_match_high_risk_keyword__fallback_sonnet() -> None:
    """High-risk keyword in test_name escalates LLM fallback to Sonnet.

    The HIV rule won't match (panel_code/flag don't satisfy it), but the
    keyword in `test_name` still flips the tier.
    """
    row = make_lab_row(
        test_name="HIV antibody screening",
        test_code="HIV-SCR",
        panel_code="HIV_SCREEN_NEW",  # not in rule whitelist
        flag=None,
    )
    llm_json = (
        '{"triage_group": "GROUP_C", "requires_doctor_review": true,'
        ' "reason": "Cần BS xác nhận", "confidence": 0.85}'
    )
    gateway = _mock_gateway_with_text(llm_json)

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.source == "LLM_SONNET"
    assert result.triage_group == "GROUP_C"
    assert result.requires_doctor_review is True
    kwargs = gateway.chat.await_args.kwargs
    assert kwargs["tier"] == "main_brain"


@pytest.mark.asyncio
async def test_classify__llm_returns_invalid_json__raises_value_error() -> None:
    row = make_lab_row(panel_code="UNKNOWN_PANEL")
    gateway = _mock_gateway_with_text("not a json")

    with pytest.raises(ValueError):
        await classify_lab_result(row, gateway, new_trace())


@pytest.mark.asyncio
async def test_classify__llm_returns_invalid_group__raises() -> None:
    row = make_lab_row(panel_code="UNKNOWN_PANEL")
    gateway = _mock_gateway_with_text('{"triage_group": "GROUP_X", "reason": "weird"}')

    with pytest.raises(ValueError):
        await classify_lab_result(row, gateway, new_trace())


@pytest.mark.asyncio
async def test_classify__llm_markdown_fence__parsed_correctly() -> None:
    row = make_lab_row(panel_code="UNKNOWN_PANEL")
    fenced = (
        "```json\n"
        '{"triage_group": "GROUP_A", "requires_doctor_review": false,'
        ' "reason": "OK", "confidence": 0.9}\n'
        "```"
    )
    gateway = _mock_gateway_with_text(fenced)

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.triage_group == "GROUP_A"
    assert result.requires_doctor_review is False


# ─────────────────────────── Safety bias tests ───────────────────────────


@pytest.mark.asyncio
async def test_classify__llm_missing_requires_review__defaults_true() -> None:
    """When LLM omits the field, classifier defaults requires_doctor_review=True."""
    row = make_lab_row(panel_code="UNKNOWN_PANEL")
    gateway = _mock_gateway_with_text(
        '{"triage_group": "GROUP_B", "reason": "Theo dõi"}'
    )

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.requires_doctor_review is True


@pytest.mark.asyncio
async def test_classify__pending_classification__valid() -> None:
    """LLM may return PENDING when it lacks information — that's a valid output."""
    row = make_lab_row(panel_code="UNKNOWN_PANEL")
    gateway = _mock_gateway_with_text(
        '{"triage_group": "PENDING", "requires_doctor_review": true,'
        ' "reason": "Thiếu data", "confidence": 0.3}'
    )

    result = await classify_lab_result(row, gateway, new_trace())

    assert result.triage_group == "PENDING"
    assert result.requires_doctor_review is True
