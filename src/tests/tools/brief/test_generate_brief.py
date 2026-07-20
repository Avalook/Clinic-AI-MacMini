"""Unit tests for tools.brief.generate_brief."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from clinicai.tools._common.context import new_trace
from clinicai.tools.brief.generate_brief import PreVisitBrief, generate_brief
from tests.tools.brief.conftest import make_patient_context

_VALID_BRIEF_JSON = {
    "headline": "BN tuần 24 thai kỳ, theo dõi tiền sản giật.",
    "key_points": [
        "GA 24 tuần",
        "Tiền sử tiền sản giật",
        "Chưa có dữ liệu visit gần đây",
    ],
    "follow_up_items": ["Đo huyết áp mỗi tuần"],
    "pending_reviews": [
        {"type": "LAB", "test_name": "CBC", "received_at": "2026-05-21"}
    ],
    "medications": ["Folate 5mg"],
    "allergies": [],
    "pregnancy_context": "Thai kỳ 24 tuần, nguy cơ cao",
    "risk_flags": ["Tiền sản giật"],
    "suggested_questions": ["Chị có đau đầu thường xuyên không?"],
    "confidence": 0.78,
}


@pytest.mark.asyncio
async def test_generate__pregnancy_context__sonnet_called_with_main_brain_tier(
    make_llm,
) -> None:
    """The tool MUST request the Sonnet tier; brief quality > token cost."""
    llm = make_llm(json.dumps(_VALID_BRIEF_JSON))
    ctx = make_patient_context(
        current_pregnancy_id=uuid4(),
        current_ga_weeks=24.0,
        pregnancy_complications=["Tiền sử tiền sản giật"],
    )

    await generate_brief(ctx, llm, new_trace())

    assert llm.chat.await_count == 1
    kwargs = llm.chat.call_args.kwargs
    assert kwargs["tier"] == "main_brain"
    assert kwargs["system"] is not None
    assert "Bạn là chuyên gia sản phụ khoa" in kwargs["system"]


@pytest.mark.asyncio
async def test_generate__llm_json_response__parsed_correctly(make_llm) -> None:
    """Bare JSON (no fence) → PreVisitBrief populated; metadata stamped."""
    llm = make_llm(json.dumps(_VALID_BRIEF_JSON))
    ctx = make_patient_context()

    brief = await generate_brief(ctx, llm, new_trace())

    assert isinstance(brief, PreVisitBrief)
    assert brief.headline.startswith("BN tuần 24")
    assert brief.confidence == 0.78
    # Metadata stamped from context + LLM response, not from JSON payload.
    assert brief.clinic_patient_id == ctx.clinic_patient_id
    assert brief.patient_code == ctx.patient_code
    assert brief.llm_model == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_generate__llm_markdown_fenced_json__stripped_and_parsed(
    make_llm,
) -> None:
    """LLM wrapped output in ```json fence → fence stripped, parse succeeds."""
    fenced = "```json\n" + json.dumps(_VALID_BRIEF_JSON) + "\n```"
    llm = make_llm(fenced)
    ctx = make_patient_context()

    brief = await generate_brief(ctx, llm, new_trace())

    assert brief.headline.startswith("BN tuần 24")


@pytest.mark.asyncio
async def test_generate__llm_invalid_json__raises_value_error(make_llm) -> None:
    """Malformed JSON → ValueError with truncated payload in message."""
    llm = make_llm("not a json — model went off-script")
    ctx = make_patient_context()

    with pytest.raises(ValueError):
        await generate_brief(ctx, llm, new_trace())


@pytest.mark.asyncio
async def test_generate__pending_group_c__included_in_pending_reviews(
    make_llm,
) -> None:
    """GROUP_C in context → user prompt mentions LAB CHƯA REVIEW so LLM sees it."""
    llm = make_llm(json.dumps(_VALID_BRIEF_JSON))
    ctx = make_patient_context(
        pending_lab_review=[
            {
                "test_code": "HIV",
                "test_name": "HIV antibody",
                "triage_group": "GROUP_C",
                "triage_reason": "HIV reactive",
                "is_finalized": False,
                "requires_doctor_review": True,
                "result_received_at": "2026-05-20",
            }
        ],
    )

    await generate_brief(ctx, llm, new_trace())

    user_message = llm.chat.call_args.kwargs["messages"][0]["content"]
    assert "LAB CHƯA REVIEW" in user_message
    assert "HIV antibody" in user_message


@pytest.mark.asyncio
async def test_generate__missing_data__confidence_low(make_llm) -> None:
    """Tool surfaces the LLM's confidence verbatim — sparse context, low confidence."""
    sparse = {
        **_VALID_BRIEF_JSON,
        "confidence": 0.30,
        "key_points": [
            "Dữ liệu chưa đầy đủ về tiền sử",
        ],
    }
    llm = make_llm(json.dumps(sparse))
    ctx = make_patient_context()  # everything default → very thin

    brief = await generate_brief(ctx, llm, new_trace())

    assert brief.confidence == 0.30
    assert any("chưa đầy đủ" in p for p in brief.key_points)
