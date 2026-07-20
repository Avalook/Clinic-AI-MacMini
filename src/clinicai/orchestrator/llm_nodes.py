"""LLM-powered nodes. Closure factory pattern: inject AnthropicClient vào graph.

classify_intent_llm_node uses Haiku 4.5 (gateway tier).
respond_node_llm uses Sonnet 4.6 (main_brain tier).
Both fallback to rule-based / template on error.
"""

from __future__ import annotations

import json
from typing import Awaitable, Callable

import structlog

from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.nodes import (
    classify_intent_rule_based,
    map_event_to_route,
    respond_node,
)
from clinicai.orchestrator.state import OrchestratorState

logger = structlog.get_logger(__name__)

VALID_ROUTES: set[str] = {
    "scheduling",
    "lab",
    "communication",
    "task",
    "previsit",
    "general",
    "unknown",
}

CLASSIFY_SYSTEM_PROMPT = """\
Bạn là bộ phân loại ý định cho hệ thống AI phòng khám sản phụ khoa Dr4Women.
Phân loại tin nhắn bệnh nhân vào ĐÚNG MỘT trong 7 route sau:

- "scheduling": Đặt/hủy/đổi lịch hẹn khám, hỏi giờ khám, đăng ký khám
- "lab": Hỏi kết quả xét nghiệm, yêu cầu xét nghiệm, hỏi quy trình xét nghiệm
- "communication": Yêu cầu nhắn tin Zalo, gửi thông báo, nhắc nhở
- "task": Công việc nội bộ nhân viên, giao việc, hỏi việc quá hạn / SLA
- "previsit": Yêu cầu tóm tắt hồ sơ bệnh nhân trước khám (pre-visit brief)
- "general": Tin nhắn chung (chào hỏi, hỏi thông tin chung, tư vấn ngoài các nhóm trên)
- "unknown": Tin nhắn trống, không hiểu được, hoặc spam

CHỈ trả về JSON object đúng format sau, KHÔNG markdown, KHÔNG text khác:
{"route": "<one_of_7>", "confidence": <0.0-1.0>, "reasoning": "<vietnamese 1 sentence>"}

Ví dụ:
Input: "Tôi muốn đặt lịch khám ngày mai"
Output: {"route": "scheduling", "confidence": 0.98, "reasoning": "Yêu cầu đặt lịch"}

Input: "Cho tôi xem kết quả siêu âm hôm qua"
Output: {"route": "lab", "confidence": 0.95, "reasoning": "Hỏi kết quả siêu âm"}

Input: "Có việc nào quá hạn SLA chưa xử lý không"
Output: {"route": "task", "confidence": 0.93, "reasoning": "Hỏi công việc quá hạn"}

Input: "Tóm tắt hồ sơ bệnh nhân trước khám giúp tôi"
Output: {"route": "previsit", "confidence": 0.94, "reasoning": "Tóm tắt trước khám"}

Input: "Xin chào bác sĩ"
Output: {"route": "general", "confidence": 0.9, "reasoning": "Lời chào chung"}
"""


def _strip_markdown_fence(text: str) -> str:
    """Strip ```json ... ``` fence nếu Haiku lỡ wrap."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    parts = text.split("```")
    if len(parts) < 2:
        return text
    inner = parts[1]
    if inner.startswith("json"):
        inner = inner[4:]
    return inner.strip()


def make_classify_intent_llm_node(
    llm: AnthropicClient,
) -> Callable[[OrchestratorState], Awaitable[dict]]:
    """Factory tạo node có inject AnthropicClient qua closure."""

    async def classify_intent_llm_node(state: OrchestratorState) -> dict:
        msg = state.get("user_message", "")
        trace_id = state.get("trace_id")

        # Event-driven dispatch (RabbitMQ): route straight from the event,
        # skip the LLM classifier entirely.
        event_type = state.get("event_type")
        if event_type:
            route = map_event_to_route(event_type)
            logger.info(
                "classify_intent_event_driven",
                trace_id=str(trace_id),
                event_type=event_type,
                route=route,
            )
            return {"route": route}

        if not msg or not msg.strip():
            logger.info("classify_intent_empty_message", trace_id=str(trace_id))
            return {"route": "unknown"}

        resp = None
        try:
            resp = await llm.chat(
                messages=[{"role": "user", "content": msg}],
                tier="gateway",
                system=CLASSIFY_SYSTEM_PROMPT,
                max_tokens=200,
                temperature=0.0,
                trace_id=trace_id,
            )

            text = _strip_markdown_fence(resp.text)
            parsed = json.loads(text)
            route_raw = str(parsed.get("route", "")).strip().lower()

            if route_raw not in VALID_ROUTES:
                raise ValueError(f"Invalid route from LLM: {route_raw!r}")

            confidence = float(parsed.get("confidence", 0.0))
            reasoning = parsed.get("reasoning", "")

            logger.info(
                "classify_intent_llm",
                trace_id=str(trace_id),
                route=route_raw,
                confidence=confidence,
                reasoning=reasoning,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
            return {"route": route_raw}

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            fallback_route = classify_intent_rule_based(msg)
            logger.warning(
                "classify_intent_llm_parse_failed_fallback",
                trace_id=str(trace_id),
                error=str(e),
                raw_text=(resp.text[:200] if resp is not None else None),
                fallback_route=fallback_route,
            )
            return {"route": fallback_route}

        except Exception as e:
            fallback_route = classify_intent_rule_based(msg)
            logger.error(
                "classify_intent_llm_api_failed_fallback",
                trace_id=str(trace_id),
                error=str(e),
                error_type=type(e).__name__,
                fallback_route=fallback_route,
            )
            return {"route": fallback_route}

    return classify_intent_llm_node


RESPOND_SYSTEM_PROMPT = """\
Bạn là trợ lý AI lễ tân của phòng khám sản phụ khoa Dr4Women.

QUY TẮC AN TOÀN Y TẾ (BẮT BUỘC):
1. KHÔNG chuẩn đoán bệnh (không kết luận triệu chứng = bệnh gì).
2. KHÔNG kê đơn thuốc, KHÔNG khuyên dùng thuốc cụ thể.
3. KHÔNG tự ý phán đoán kết quả xét nghiệm — chuyển bác sĩ.
4. Câu hỏi y tế nghiêm trọng → khuyên gặp bác sĩ trực tiếp.
5. Dấu hiệu cấp cứu (đau bụng dữ dội, ra máu nhiều, ngất...) → khuyên đến viện ngay.

PHONG CÁCH:
- Tiếng Việt, lễ phép, NGẮN GỌN (≤3 câu).
- Xưng "phòng khám" hoặc "em" tùy ngữ cảnh.
- KHÔNG dùng markdown, KHÔNG emoji.

NHIỆM VỤ:
Trả lời tin nhắn bệnh nhân ngắn gọn, lễ phép. Nếu thuộc nhóm chuyên biệt
(scheduling/lab/communication), thông báo đã nhận và nhân viên/bác sĩ sẽ
liên hệ sớm. Tuyệt đối tuân thủ QUY TẮC AN TOÀN Y TẾ phía trên.
"""


def make_respond_node_llm(
    llm: AnthropicClient,
) -> Callable[[OrchestratorState], Awaitable[dict]]:
    """Factory tạo respond_node có inject AnthropicClient (Sonnet 4.6).

    3-layer fallback to template respond_node:
    - Empty/whitespace user_message → template (no LLM call)
    - LLM returns empty text → template (warn log)
    - Any exception → template (error log)
    """

    async def respond_node_llm(state: OrchestratorState) -> dict:
        msg = state.get("user_message", "")
        route = state.get("route", "unknown")
        trace_id = state.get("trace_id")

        if not msg or not msg.strip():
            logger.info("respond_node_llm_empty_message", trace_id=str(trace_id))
            return await respond_node(state)

        try:
            user_content = f"[Route: {route}]\n\nTin nhắn bệnh nhân:\n{msg}"
            resp = await llm.chat(
                messages=[{"role": "user", "content": user_content}],
                tier="main_brain",
                system=RESPOND_SYSTEM_PROMPT,
                max_tokens=300,
                temperature=0.3,
                trace_id=trace_id,
            )
            text = resp.text.strip()
            if not text:
                raise ValueError("Empty LLM response text")

            logger.info(
                "respond_node_llm",
                trace_id=str(trace_id),
                route=route,
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
                latency_ms=resp.latency_ms,
            )
            return {"response": text}

        except ValueError as e:
            logger.warning(
                "respond_node_llm_empty_response_fallback",
                trace_id=str(trace_id),
                route=route,
                error=str(e),
            )
            return await respond_node(state)

        except Exception as e:
            logger.error(
                "respond_node_llm_api_failed_fallback",
                trace_id=str(trace_id),
                route=route,
                error=str(e),
                error_type=type(e).__name__,
            )
            return await respond_node(state)

    return respond_node_llm
