"""Pure-function rendering: PreVisitBrief → Markdown string.

The BS reads this directly in the app / web UI. No LLM call, no DB
access — keep this safe to call from anywhere (including tests).
Empty sections collapse so a thin context doesn't render a wall of
"none" placeholders.
"""

from __future__ import annotations

from typing import Any

from clinicai.tools.brief.generate_brief import PreVisitBrief


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{idx}. {item}" for idx, item in enumerate(items, start=1))


def _format_pending(item: dict[str, Any]) -> str:
    kind = item.get("type") or "PENDING"
    name = item.get("test_name") or "?"
    received = item.get("received_at") or "?"
    return f"**[URGENT]** {kind} — {name} (received {received})"


def render_brief_markdown(brief: PreVisitBrief) -> str:
    """Render a PreVisitBrief as a clinician-facing Markdown document.

    Sections with no content are omitted. The headline always renders.
    """
    sections: list[str] = []

    sections.append(f"# Brief — {brief.patient_code}")
    sections.append(
        f"_Generated {brief.generated_at.isoformat()}_  \n"
        f"_Model: {brief.llm_model} · Confidence: {brief.confidence:.2f}_"
    )
    sections.append(f"> **{brief.headline}**")

    if brief.pending_reviews:
        sections.append(
            "## ⚠️ Pending Reviews\n"
            + "\n".join(f"- {_format_pending(p)}" for p in brief.pending_reviews)
        )

    if brief.key_points:
        sections.append("## 🩺 Key Points\n" + _bullets(brief.key_points))

    if brief.follow_up_items:
        sections.append("## 📋 Follow-up\n" + _bullets(brief.follow_up_items))

    if brief.pregnancy_context:
        sections.append("## 🤰 Pregnancy Context\n" + brief.pregnancy_context)

    if brief.medications:
        sections.append("## 💊 Medications\n" + _bullets(brief.medications))

    if brief.allergies:
        sections.append("## ⚕️ Allergies\n" + _bullets(brief.allergies))

    if brief.risk_flags:
        sections.append("## 🚨 Risk Flags\n" + _bullets(brief.risk_flags))

    if brief.suggested_questions:
        sections.append(
            "## ❓ Suggested Questions\n" + _numbered(brief.suggested_questions)
        )

    return "\n\n".join(sections) + "\n"
