"""Lab result classification — rule-based với AI fallback qua AnthropicClient.

Logic:
1. Evaluate rules theo priority desc
2. First rule match → return ClassifyResult (source="RULE")
3. Nếu không rule nào match → fallback LLM qua AnthropicClient
   (tier="gateway" → Haiku 4.5; tier="main_brain" → Sonnet 4.6 cho
   safety-critical keywords)
4. LLM trả về raw text; strip markdown fence, json.loads, validate manual

KHÔNG enforce safety gate ở đây — đó là trách nhiệm của graph node + service.
File này chỉ output classification suggestion + reason. Caller quyết action.

Note on the LLM client: spec gọi là `model_gateway` nhưng repo dùng tên
`AnthropicClient` (src/clinicai/llm/anthropic_client.py). Mapping:
  complexity="simple"  → tier="gateway"     → Haiku 4.5  → source="LLM_HAIKU"
  complexity="complex" → tier="main_brain"  → Sonnet 4.6 → source="LLM_SONNET"
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from clinicai.llm.anthropic_client import AnthropicClient, LLMResponse
from clinicai.tools._common.context import TraceContext
from clinicai.tools.lab._rules import LAB_TRIAGE_RULES
from clinicai.tools.lab.query_lab_result import LabResultRow

logger = logging.getLogger(__name__)

TriageGroup = Literal["GROUP_A", "GROUP_B", "GROUP_C", "PENDING"]
ClassifySource = Literal["RULE", "LLM_HAIKU", "LLM_SONNET"]

_HIGH_RISK_KEYWORDS: tuple[str, ...] = (
    "HIV",
    "NIPT",
    "HBV",
    "HCV",
    "CANCER",
    "TUMOR",
    "MARKER",
    "KARYOTYPE",
)
_VALID_GROUPS: frozenset[str] = frozenset({"GROUP_A", "GROUP_B", "GROUP_C", "PENDING"})


class ClassifyResult(BaseModel):
    """Output của classify_lab_result."""

    triage_group: TriageGroup
    requires_doctor_review: bool
    reason: str
    matched_rule_key: str | None = None
    source: ClassifySource
    confidence: float = Field(ge=0.0, le=1.0)


async def classify_lab_result(
    row: LabResultRow,
    gateway: AnthropicClient,
    trace: TraceContext,
) -> ClassifyResult:
    """Classify a single lab result row.

    Strategy:
        1. Try rules sorted by priority desc — return ngay khi match.
        2. Nếu không rule match → escalate LLM qua AnthropicClient
           (tier chọn theo high-risk keywords).

    Args:
        row: LabResultRow from query_lab_result.
        gateway: AnthropicClient singleton (inject by caller).
        trace: TraceContext for observability.

    Returns:
        ClassifyResult with source="RULE" or "LLM_*".

    Raises:
        ValueError: when the LLM response cannot be parsed into a valid
            triage_group payload.
        Anthropic/network errors propagate unchanged.
    """
    rule_match = _match_rules(row)
    if rule_match is not None:
        rule_key, rule_data = rule_match
        logger.info(
            "lab.classify.rule_match",
            extra={
                "trace_id": str(trace.trace_id),
                "lab_result_id": str(row.lab_result_id),
                "rule_key": rule_key,
                "triage_group": rule_data["triage_group"],
            },
        )
        return ClassifyResult(
            triage_group=rule_data["triage_group"],
            requires_doctor_review=rule_data["requires_doctor_review"],
            reason=rule_data["reason_template"],
            matched_rule_key=rule_key,
            source="RULE",
            confidence=1.0,
        )

    logger.info(
        "lab.classify.llm_fallback",
        extra={
            "trace_id": str(trace.trace_id),
            "lab_result_id": str(row.lab_result_id),
        },
    )
    return await _classify_via_llm(row, gateway, trace)


def _match_rules(row: LabResultRow) -> tuple[str, dict[str, Any]] | None:
    """Evaluate rules theo priority desc. Return first match or None."""
    sorted_rules = sorted(
        LAB_TRIAGE_RULES.items(),
        key=lambda kv: kv[1]["rule_data"].get("priority", 0),
        reverse=True,
    )
    for rule_key, rule_def in sorted_rules:
        rule_data = rule_def["rule_data"]
        if _evaluate_match(row, rule_data["match"]):
            return rule_key, rule_data
    return None


def _evaluate_match(row: LabResultRow, match_spec: dict[str, Any]) -> bool:
    """Pure predicate. Evaluate match spec against row.

    Supported match keys (all AND):
      - panel_code_in: list[str]
      - flag_in: list[str | None]
      - numeric_gt / numeric_gte / numeric_lt / numeric_lte: float
      - numeric_within_range: bool — check result_numeric in
        [reference_range_low, reference_range_high]
    """
    if "panel_code_in" in match_spec:
        if row.panel_code not in match_spec["panel_code_in"]:
            return False

    if "flag_in" in match_spec:
        if row.flag not in match_spec["flag_in"]:
            return False

    if "numeric_gt" in match_spec:
        if row.result_numeric is None:
            return False
        if row.result_numeric <= match_spec["numeric_gt"]:
            return False

    if "numeric_gte" in match_spec:
        if row.result_numeric is None:
            return False
        if row.result_numeric < match_spec["numeric_gte"]:
            return False

    if "numeric_lt" in match_spec:
        if row.result_numeric is None:
            return False
        if row.result_numeric >= match_spec["numeric_lt"]:
            return False

    if "numeric_lte" in match_spec:
        if row.result_numeric is None:
            return False
        if row.result_numeric > match_spec["numeric_lte"]:
            return False

    if match_spec.get("numeric_within_range") is True:
        if row.result_numeric is None:
            return False
        if row.reference_range_low is None or row.reference_range_high is None:
            return False
        if not (
            row.reference_range_low <= row.result_numeric <= row.reference_range_high
        ):
            return False

    return True


async def _classify_via_llm(
    row: LabResultRow,
    gateway: AnthropicClient,
    trace: TraceContext,
) -> ClassifyResult:
    """Call AnthropicClient to classify when no rule matches.

    Default tier="gateway" (Haiku). Escalate to tier="main_brain" (Sonnet)
    when the test name / panel code contains a high-risk keyword
    (HIV, NIPT, HBV, HCV, CANCER, TUMOR, MARKER, KARYOTYPE).
    """
    test_upper = f"{row.test_name or ''} {row.panel_code or ''}".upper()
    use_complex = any(kw in test_upper for kw in _HIGH_RISK_KEYWORDS)
    tier: Literal["gateway", "main_brain"] = "main_brain" if use_complex else "gateway"
    source: ClassifySource = "LLM_SONNET" if use_complex else "LLM_HAIKU"

    user_prompt = _build_classify_prompt(row)
    resp: LLMResponse = await gateway.chat(
        messages=[{"role": "user", "content": user_prompt}],
        tier=tier,
        system=_SYSTEM_PROMPT,
        max_tokens=400,
        temperature=0.0,
        trace_id=trace.trace_id,
    )

    parsed = _parse_llm_response(resp.text)

    # Safety bias: when LLM omits requires_doctor_review, default to True so
    # the human-in-the-loop gate is still applied downstream.
    requires_review = bool(parsed.get("requires_doctor_review", True))
    reason = parsed.get("reason") or "LLM classification (no reason provided)"
    confidence = float(parsed.get("confidence", 0.7))
    # Clamp confidence into [0, 1] (defensive — LLM could return out-of-range).
    confidence = max(0.0, min(1.0, confidence))

    return ClassifyResult(
        triage_group=parsed["triage_group"],
        requires_doctor_review=requires_review,
        reason=reason,
        matched_rule_key=None,
        source=source,
        confidence=confidence,
    )


_SYSTEM_PROMPT = """Bạn là chuyên gia phân loại kết quả xét nghiệm sản phụ khoa.

Phân loại kết quả vào 1 trong 4 nhóm:
- GROUP_A: Bình thường, CSKH có thể notify BN trực tiếp
- GROUP_B: Cần theo dõi, nhưng không cấp cứu
- GROUP_C: Nguy hiểm, BẮT BUỘC BS review trước khi notify BN
- PENDING: Không đủ thông tin để phân loại

Nguyên tắc:
- Nếu nghi ngờ → ưu tiên GROUP_C (an toàn BN)
- Nếu test liên quan HIV/NIPT/Cancer marker → MẶC ĐỊNH GROUP_C
- Nếu chỉ là chỉ số ngoài range nhẹ → GROUP_B
- Nếu trong range → GROUP_A

Trả về JSON đúng schema, KHÔNG markdown, KHÔNG text khác:
{
  "triage_group": "GROUP_A" | "GROUP_B" | "GROUP_C" | "PENDING",
  "requires_doctor_review": true | false,
  "reason": "<lý do ngắn gọn tiếng Việt>",
  "confidence": <0.0-1.0>
}
"""


def _build_classify_prompt(row: LabResultRow) -> str:
    """Build user prompt từ row data."""
    return (
        "Phân loại kết quả xét nghiệm sau:\n\n"
        f"Test: {row.test_name} (code: {row.test_code}, "
        f"panel: {row.panel_code})\n"
        f"Giá trị: {row.result_value} {row.result_unit or ''}\n"
        f"Numeric: {row.result_numeric}\n"
        f"Reference range: {row.reference_range_low} - "
        f"{row.reference_range_high}\n"
        f"Flag: {row.flag}\n\n"
        "Trả về JSON theo schema đã quy định."
    )


def _strip_markdown_fence(text: str) -> str:
    """Strip ```json ... ``` fence nếu LLM lỡ wrap."""
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


def _parse_llm_response(response_text: str) -> dict[str, Any]:
    """Parse LLM raw text into a validated dict.

    Raises:
        ValueError: when JSON parse fails or triage_group is invalid/missing.
    """
    text = _strip_markdown_fence(response_text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM response is not valid JSON: {text[:200]!r}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"LLM response is not a JSON object: {data!r}")

    triage_group = data.get("triage_group")
    if triage_group not in _VALID_GROUPS:
        raise ValueError(f"Invalid triage_group from LLM: {triage_group!r}")

    return data
