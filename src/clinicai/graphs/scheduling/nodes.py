"""Slot-filling conversation nodes (rule-based parsers).

find_doctor_node uses the real find_work_sessions tool (P9.1-03b).
"""

from __future__ import annotations

from datetime import date as date_type
from uuid import UUID

import structlog

from clinicai.graphs.scheduling.parsers import (
    parse_date,
    parse_time_slot,
    parse_yes_no,
)
from clinicai.graphs.scheduling.session_mapper import map_to_session_type
from clinicai.graphs.scheduling.state import SchedulingState

logger = structlog.get_logger(__name__)

_MARKER = "scheduling_subgraph"


async def ask_date_node(state: SchedulingState) -> dict:
    msg = state.get("user_message", "")
    turn = state.get("turn_count", 0)
    logger.info("scheduling.ask_date", turn=turn)

    if not state.get("preferred_date"):
        parsed = parse_date(msg)
        if parsed:
            return {
                "preferred_date": parsed,
                "step": "ask_time",
                "response": (
                    f"Dạ em đã ghi nhận ngày {parsed}. "
                    "Chị muốn khung giờ sáng, chiều hay tối ạ?"
                ),
                "handled_by": _MARKER,
                "turn_count": turn + 1,
            }
        if turn == 0:
            return {
                "step": "ask_date",
                "response": (
                    "Dạ em hỗ trợ chị đặt lịch khám. "
                    "Chị muốn khám vào ngày nào ạ? (vd: 25/05 hoặc 'mai')"
                ),
                "handled_by": _MARKER,
                "turn_count": 1,
            }
        return {
            "step": "ask_date",
            "response": (
                "Dạ em chưa nhận diện được ngày. "
                "Chị vui lòng nhập lại theo dạng dd/mm hoặc nói 'mai', 'thứ 5' ạ."
            ),
            "handled_by": _MARKER,
            "turn_count": turn + 1,
        }

    return {"step": "ask_time"}


async def ask_time_node(state: SchedulingState) -> dict:
    msg = state.get("user_message", "")
    turn = state.get("turn_count", 0)
    logger.info("scheduling.ask_time", turn=turn)

    parsed = parse_time_slot(msg)
    if parsed:
        return {
            "preferred_time": parsed,
            "step": "find_doctor",
            "response": (
                f"Dạ em đã ghi nhận khung {parsed}. Em đang tra cứu bác sĩ phù hợp..."
            ),
            "handled_by": _MARKER,
            "turn_count": turn + 1,
        }
    return {
        "step": "ask_time",
        "response": "Dạ chị vui lòng cho em biết khung sáng, chiều hay tối ạ?",
        "handled_by": _MARKER,
        "turn_count": turn + 1,
    }


def make_find_doctor_node(pool, location_id: UUID):
    """Closure factory: bind asyncpg pool + location_id into find_doctor_node.

    Uses the real `find_work_sessions` tool to surface doctors available for
    the (location_id, preferred_date, derived session_type) tuple.
    """

    async def find_doctor_node(state: SchedulingState) -> dict:
        from clinicai.tools.scheduling.find_work_sessions import (
            FindWorkSessionsInput,
            find_work_sessions,
        )

        preferred_date_str = state.get("preferred_date")
        preferred_time = state.get("preferred_time")
        turn = state.get("turn_count", 0)
        logger.info(
            "scheduling.find_doctor",
            turn=turn,
            date=preferred_date_str,
            time=preferred_time,
        )

        try:
            preferred_date = date_type.fromisoformat(preferred_date_str)
        except (TypeError, ValueError):
            return {
                "step": "ask_date",
                "preferred_date": None,
                "response": (
                    "Dạ em không đọc được ngày chị chọn. Chị nhập lại giúp em ạ."
                ),
                "handled_by": _MARKER,
                "turn_count": turn + 1,
            }

        session_type = map_to_session_type(preferred_time, preferred_date)
        if session_type is None:
            return {
                "step": "ask_time",
                "preferred_time": None,
                "response": (
                    "Dạ ngày chị chọn phòng khám chỉ có ca tối. "
                    "Chị có muốn đặt ca tối không ạ?"
                ),
                "handled_by": _MARKER,
                "turn_count": turn + 1,
            }

        try:
            result = await find_work_sessions(
                FindWorkSessionsInput(
                    location_id=location_id,
                    session_date=preferred_date,
                    session_type=session_type,
                ),
                pool,
            )
        except Exception as e:
            logger.error(
                "scheduling.find_doctor_tool_failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            return {
                "step": "confirm",
                "candidate_doctors": [],
                "response": (
                    "Dạ em chưa tra cứu được lịch bác sĩ. "
                    "Chị có muốn em chuyển tới nhân viên tư vấn không ạ?"
                ),
                "handled_by": _MARKER,
                "turn_count": turn + 1,
            }

        all_doctors: list[dict] = []
        for session in result.sessions:
            for d in session.available_doctors:
                enriched = dict(d)
                enriched["session_id"] = str(session.session_id)
                enriched["start_time"] = session.start_time
                all_doctors.append(enriched)

        if not all_doctors:
            return {
                "step": "ask_date",
                "preferred_date": None,
                "candidate_doctors": [],
                "response": (
                    f"Dạ ngày {preferred_date_str} không có bác sĩ rảnh ca này. "
                    "Chị chọn ngày khác giúp em ạ."
                ),
                "handled_by": _MARKER,
                "turn_count": turn + 1,
            }

        top = all_doctors[0]
        doctor_name = top.get("full_name") or "bác sĩ trực"
        return {
            "step": "confirm",
            "candidate_doctors": all_doctors,
            "preferred_doctor": doctor_name,
            "response": (
                f"Dạ em tìm thấy {doctor_name} có thể khám ngày "
                f"{preferred_date_str} ca {session_type}. "
                "Chị xác nhận đặt lịch (có/không)?"
            ),
            "handled_by": _MARKER,
            "turn_count": turn + 1,
        }

    return find_doctor_node


async def confirm_node(state: SchedulingState) -> dict:
    msg = state.get("user_message", "")
    turn = state.get("turn_count", 0)
    decision = parse_yes_no(msg)
    logger.info("scheduling.confirm", turn=turn, decision=decision)

    if decision is True:
        return {
            "confirmed": True,
            "step": "done",
            "response": (
                f"Dạ em đã đặt lịch cho chị ngày {state.get('preferred_date')} "
                f"khung {state.get('preferred_time')}. "
                "Em sẽ nhắn xác nhận chi tiết sau ạ."
            ),
            "handled_by": _MARKER,
            "turn_count": turn + 1,
        }
    if decision is False:
        return {
            "confirmed": False,
            "step": "done",
            "response": (
                "Dạ em đã hủy yêu cầu đặt lịch. Chị cần em hỗ trợ gì khác không ạ?"
            ),
            "handled_by": _MARKER,
            "turn_count": turn + 1,
        }
    return {
        "step": "confirm",
        "response": "Dạ chị xác nhận giúp em: có hay không ạ?",
        "handled_by": _MARKER,
        "turn_count": turn + 1,
    }
