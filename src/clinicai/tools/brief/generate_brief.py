"""Tool: brief.generate_brief — produce a structured pre-visit brief.

Sonnet (tier="main_brain") only. Quality matters more than cost for a
clinician-facing brief: the BS reads it for 30 seconds and acts on it,
so hallucination cost dwarfs token cost.

JSON parsing strategy mirrors `tools/lab/classify.py`: strip a
``` markdown fence (Sonnet sometimes wraps despite the prompt) and
validate via Pydantic. On any parse failure the caller sees a clear
ValueError — no silent fallback to a partial brief.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clinicai.llm.models import Tier
from clinicai.services.patient_context_service import PatientContext
from clinicai.tools._common.context import TraceContext

if TYPE_CHECKING:
    from clinicai.llm.anthropic_client import AnthropicClient

logger = logging.getLogger(__name__)

_LLM_TIER: Tier = "main_brain"
_LLM_MAX_TOKENS = 1536
_LLM_TEMPERATURE = 0.2


class PreVisitBrief(BaseModel):
    """Structured pre-visit brief consumed by clinicians."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    clinic_patient_id: UUID
    patient_code: str
    generated_at: datetime

    headline: str
    key_points: list[str] = Field(default_factory=list)
    follow_up_items: list[str] = Field(default_factory=list)
    pending_reviews: list[dict[str, Any]] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    pregnancy_context: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)

    llm_model: str
    confidence: float = Field(ge=0.0, le=1.0)


_SYSTEM_PROMPT = """Bạn là chuyên gia sản phụ khoa hỗ trợ BS chuẩn bị trước ca khám.

NHIỆM VỤ: Đọc dữ liệu BN tổng hợp, tạo BRIEF NGẮN (BS đọc 30 giây) để BS:
1. Nắm tình trạng BN ngay
2. Biết điểm follow-up
3. Biết câu hỏi nên hỏi

NGUYÊN TẮC:
- Headline: 1-2 dòng, gist quan trọng nhất.
- Key points: 3-7 bullets ngắn, mỗi bullet ≤ 20 từ.
- Follow-up: chỉ list cụ thể (vd: "Kiểm tra glucose tuần này"), KHÔNG nói chung chung.
- Pending reviews: nếu có GROUP_C lab chưa review → flag URGENT.
- Risk flags: chỉ liệt kê risk THẬT từ data, KHÔNG suy đoán.
- Suggested questions: 2-4 câu BS hỏi BN, dựa trên context cụ thể.

ĐỊNH DẠNG OUTPUT: JSON đúng schema sau, KHÔNG markdown fence:
{
  "headline": "<1-2 câu>",
  "key_points": ["<bullet 1>", ...],
  "follow_up_items": ["<item>", ...],
  "pending_reviews": [
    {"type": "LAB|IMAGING", "test_name": "...", "received_at": "..."}
  ],
  "medications": ["<med>", ...],
  "allergies": ["<allergen>", ...],
  "pregnancy_context": "<string hoặc null nếu không thai>",
  "risk_flags": ["<flag>", ...],
  "suggested_questions": ["<câu hỏi>", ...],
  "confidence": <0.0-1.0>
}

AN TOÀN: Nếu data thiếu hoặc mâu thuẫn → confidence < 0.5, ghi rõ trong key_points
"Dữ liệu chưa đầy đủ về X". KHÔNG bịa thông tin."""


def _format_optional(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    return str(value)


def _build_user_prompt(context: PatientContext) -> str:
    """Render PatientContext as a compact Vietnamese text block for the LLM."""
    age = (
        date_age_years(context.date_of_birth)
        if context.date_of_birth is not None
        else None
    )
    lines: list[str] = []
    lines.append(f"BN: {context.patient_code} — {context.full_name}")
    lines.append(f"Tuổi: {age if age is not None else 'không rõ'}")
    lines.append(f"Nhóm máu: {_format_optional(context.blood_type)}")

    if context.current_pregnancy_id is not None:
        ga = (
            f"{context.current_ga_weeks} tuần"
            if context.current_ga_weeks is not None
            else "không xác định"
        )
        lines.append(f"Thai kỳ hiện tại: GA {ga}")
        if context.pregnancy_complications:
            lines.append(
                "Biến chứng / nguy cơ thai kỳ: "
                + "; ".join(context.pregnancy_complications)
            )
    else:
        lines.append("Thai kỳ hiện tại: không có ONGOING pregnancy.")

    if context.chronic_diseases:
        lines.append("Bệnh mãn tính: " + ", ".join(context.chronic_diseases))
    if context.current_medications:
        lines.append("Thuốc đang dùng: " + ", ".join(context.current_medications))
    if context.allergies:
        lines.append("Dị ứng: " + ", ".join(context.allergies))

    if context.last_visit_date is not None:
        lines.append(
            "Lần khám gần nhất: "
            f"{context.last_visit_date.isoformat()} "
            f"(tổng số visit: {context.total_visits})"
        )
    else:
        lines.append("Lần khám gần nhất: chưa có dữ liệu.")

    if context.next_appointment_at is not None:
        lines.append(
            "Lịch hẹn sắp tới: "
            f"{context.next_appointment_at.isoformat()} "
            f"({_format_optional(context.next_appointment_status)})"
        )

    if context.latest_lab_results:
        lines.append("Lab gần đây:")
        for lab in context.latest_lab_results:
            received = lab.get("result_received_at") or "?"
            lines.append(
                f"  - {lab.get('test_name')} "
                f"({lab.get('test_code')}) "
                f"flag={lab.get('flag')} "
                f"triage={lab.get('triage_group')} "
                f"value={_format_optional(lab.get('result_value'))} "
                f"received={received}"
            )

    if context.pending_lab_review:
        lines.append("LAB CHƯA REVIEW (GROUP_C, URGENT):")
        for lab in context.pending_lab_review:
            lines.append(
                f"  ! {lab.get('test_name')} "
                f"({lab.get('test_code')}) "
                f"reason={_format_optional(lab.get('triage_reason'))}"
            )

    if context.latest_ultrasound_summary:
        lines.append("Siêu âm gần đây:")
        for us in context.latest_ultrasound_summary:
            performed = us.get("performed_at") or "?"
            lines.append(
                f"  - {_format_optional(us.get('ultrasound_type'))} "
                f"GA={_format_optional(us.get('gestational_age_weeks'))}w "
                f"impression={_format_optional(us.get('impression'))} "
                f"performed={performed}"
            )

    if not context.ongoing_issues:
        lines.append("Vấn đề đang theo dõi: chưa có dữ liệu cấu trúc.")
    else:
        lines.append("Vấn đề đang theo dõi: " + "; ".join(context.ongoing_issues))

    return "\n".join(lines)


def date_age_years(dob: Any) -> int:
    """Compute age in completed years from a date object. Returns 0 if dob is today."""
    today = datetime.now(tz=timezone.utc).date()
    years: int = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return max(years, 0)


def _strip_markdown_fence(text: str) -> str:
    """Strip ```json ... ``` fence if the LLM wrapped despite instructions."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    parts = stripped.split("```")
    if len(parts) < 2:
        return stripped
    inner = parts[1]
    if inner.startswith("json"):
        inner = inner[4:]
    return inner.strip()


def _parse_brief_response(
    raw: str | dict[str, Any],
    context: PatientContext,
    llm_model: str,
) -> PreVisitBrief:
    """Parse + validate LLM output and stamp deterministic metadata fields.

    Raises:
        ValueError: JSON parse failure or schema validation failure.
    """
    if isinstance(raw, dict):
        data = raw
    else:
        text = _strip_markdown_fence(raw)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM brief response is not valid JSON: {text[:200]!r}"
            ) from exc

    if not isinstance(data, dict):
        raise ValueError(f"LLM brief response is not a JSON object: {data!r}")

    # Stamp deterministic metadata — the LLM is not authoritative for these.
    data["clinic_patient_id"] = context.clinic_patient_id
    data["patient_code"] = context.patient_code
    data["generated_at"] = datetime.now(tz=timezone.utc)
    data["llm_model"] = llm_model

    try:
        return PreVisitBrief.model_validate(data)
    except Exception as exc:
        raise ValueError(f"LLM brief failed schema validation: {exc}") from exc


async def generate_brief(
    context: PatientContext,
    llm_client: "AnthropicClient",
    trace: TraceContext,
) -> PreVisitBrief:
    """Generate a pre-visit brief from aggregated patient context.

    Args:
        context: aggregated PatientContext (patient_summary VIEW + ultrasound).
        llm_client: shared AnthropicClient (Sonnet via tier=main_brain).
        trace: per-invocation TraceContext.

    Returns:
        PreVisitBrief.

    Raises:
        ValueError: LLM output is not valid JSON or fails schema validation.
        Any AnthropicClient retryable errors propagate after exhausted retry.
    """
    user_prompt = _build_user_prompt(context)
    logger.debug(
        "tool.brief.generate_brief",
        extra={
            "trace_id": str(trace.trace_id),
            "clinic_patient_id": str(context.clinic_patient_id),
            "lab_recent_count": len(context.latest_lab_results),
            "pending_review_count": len(context.pending_lab_review),
            "ultrasound_count": len(context.latest_ultrasound_summary),
        },
    )

    resp = await llm_client.chat(
        messages=[{"role": "user", "content": user_prompt}],
        tier=_LLM_TIER,
        max_tokens=_LLM_MAX_TOKENS,
        temperature=_LLM_TEMPERATURE,
        system=_SYSTEM_PROMPT,
        trace_id=trace.trace_id,
    )

    return _parse_brief_response(resp.text, context, resp.model)
