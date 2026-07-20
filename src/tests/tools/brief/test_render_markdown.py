"""Unit tests for tools.brief.render_markdown — pure function."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from clinicai.tools.brief.generate_brief import PreVisitBrief
from clinicai.tools.brief.render_markdown import render_brief_markdown


def _brief(**overrides) -> PreVisitBrief:
    defaults: dict = {
        "clinic_patient_id": UUID("11111111-1111-1111-1111-111111111111"),
        "patient_code": "BN-2026-000001",
        "generated_at": datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
        "headline": "Headline ngắn.",
        "key_points": ["Point 1", "Point 2"],
        "follow_up_items": ["Follow 1"],
        "pending_reviews": [],
        "medications": ["Folate 5mg"],
        "allergies": ["Penicillin"],
        "pregnancy_context": "Thai kỳ 24 tuần",
        "risk_flags": ["Tiền sản giật"],
        "suggested_questions": ["Q1?", "Q2?"],
        "llm_model": "claude-sonnet-4-6",
        "confidence": 0.8,
    }
    defaults.update(overrides)
    return PreVisitBrief(**defaults)


def test_render__all_sections_present__markdown_has_all_headers() -> None:
    md = render_brief_markdown(_brief())

    # Header line + every section header must appear.
    assert "# Brief — BN-2026-000001" in md
    assert "## 🩺 Key Points" in md
    assert "## 📋 Follow-up" in md
    assert "## 🤰 Pregnancy Context" in md
    assert "## 💊 Medications" in md
    assert "## ⚕️ Allergies" in md
    assert "## 🚨 Risk Flags" in md
    assert "## ❓ Suggested Questions" in md
    assert "Headline ngắn" in md


def test_render__empty_risk_flags__section_hidden_or_indicates_none() -> None:
    md = render_brief_markdown(_brief(risk_flags=[]))

    # Empty list → section omitted entirely.
    assert "🚨 Risk Flags" not in md
    # Other present sections still render.
    assert "🩺 Key Points" in md


def test_render__pregnancy_null__pregnancy_section_omitted() -> None:
    md = render_brief_markdown(_brief(pregnancy_context=None))

    assert "🤰 Pregnancy Context" not in md
    assert "Headline ngắn" in md  # rest still renders


def test_render__pending_reviews__urgent_marker_present() -> None:
    md = render_brief_markdown(
        _brief(
            pending_reviews=[
                {
                    "type": "LAB",
                    "test_name": "HIV antibody",
                    "received_at": "2026-05-20",
                }
            ]
        )
    )

    assert "## ⚠️ Pending Reviews" in md
    assert "**[URGENT]**" in md
    assert "HIV antibody" in md
