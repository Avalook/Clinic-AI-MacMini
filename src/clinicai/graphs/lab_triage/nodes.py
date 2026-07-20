"""Nodes for lab_triage sub-graph (T-P9.2-04 wires real fetch + classify).

Flow: receive (validate) → fetch (load row) → classify (rule+LLM) →
{advise | (hard_block → create_review_tasks)} → END.

The single-row architecture is intentional: each invocation triages one
lab_result_id end-to-end. Multi-row batch triage (notify-many flow) is
deferred to a later phase via a separate sub-graph builder.

P9.3 wires `create_review_tasks_node` after `hard_block`: a GROUP_C hit
enqueues exactly one URGENT LAB_REVIEW staff task with SLA=4h.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Optional

import asyncpg
import structlog

from clinicai.graphs.lab_triage.state import LabTriageState, LabTriageStep
from clinicai.tools._common.context import new_trace
from clinicai.tools.lab.classify import classify_lab_result
from clinicai.tools.lab.query_lab_result import LabResultRow
from clinicai.tools.task.create_task import CreateTaskInput, create_task

if TYPE_CHECKING:
    from clinicai.llm.anthropic_client import AnthropicClient

logger = structlog.get_logger()


# query_lab_result tool requires a clinic_patient_id filter and has no
# lab_result_id filter (boundary forbids modifying that tool). Use an inline
# SELECT that mirrors LabResultRow column list. Keep the SELECT shape in sync
# with `tools/lab/query_lab_result.py:_SELECT_COLUMNS` if either changes.
_FETCH_BY_ID_SQL = """
    SELECT lab_result_id, clinic_patient_id, visit_id, appointment_id,
           test_code, test_name, panel_code,
           result_value, result_numeric, result_unit,
           reference_range_low, reference_range_high, flag,
           triage_group, triage_reason,
           requires_doctor_review, reviewed_by_staff_id, reviewed_at,
           is_finalized,
           lab_provider, sample_collected_at, result_received_at
    FROM lab_result
    WHERE lab_result_id = $1
    LIMIT 1
"""


def make_receive_node():
    """Validate lab_result_id is present, transition to FETCH."""

    async def receive_node(state: LabTriageState) -> LabTriageState:
        logger.info("lab_triage.receive", lab_result_id=str(state.lab_result_id))
        if not state.lab_result_id:
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "missing lab_result_id",
                }
            )
        return state.model_copy(
            update={
                "step": LabTriageStep.FETCH,
                "turn_count": state.turn_count + 1,
            }
        )

    return receive_node


def make_fetch_node(pool: Optional[asyncpg.Pool]):
    """Load the lab_result row by id via inline SQL. Pool=None → safe stub."""

    async def fetch_node(state: LabTriageState) -> LabTriageState:
        if pool is None:
            logger.warning(
                "lab_triage.fetch_no_pool",
                lab_result_id=str(state.lab_result_id),
            )
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "no db pool wired",
                }
            )

        try:
            async with pool.acquire() as conn:
                record = await conn.fetchrow(_FETCH_BY_ID_SQL, state.lab_result_id)
        except Exception as exc:
            logger.error(
                "lab_triage.fetch_failed",
                lab_result_id=str(state.lab_result_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "fetch_failed",
                }
            )

        if record is None:
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "lab_result not found",
                }
            )

        row = LabResultRow.model_validate(dict(record))
        return state.model_copy(
            update={
                "lab_result_row": row,
                "step": LabTriageStep.CLASSIFY,
                "turn_count": state.turn_count + 1,
            }
        )

    return fetch_node


def make_classify_node(
    pool: Optional[asyncpg.Pool],
    llm_client: Optional["AnthropicClient"],
):
    """Call classify_lab_result(row, gateway, trace). Safety-biased fallback
    when llm_client is missing: triage as PENDING with requires_review=True.
    """

    async def classify_node(state: LabTriageState) -> LabTriageState:
        row = state.lab_result_row
        if row is None:
            logger.error(
                "lab_triage.classify_missing_row",
                lab_result_id=str(state.lab_result_id),
            )
            return state.model_copy(
                update={
                    "triage_group": "PENDING",
                    "triage_reason": "row not loaded",
                    "requires_doctor_review": True,
                    "step": LabTriageStep.HARD_BLOCK,
                    "turn_count": state.turn_count + 1,
                }
            )

        if llm_client is None:
            logger.warning(
                "lab_triage.classify_no_llm_fallback",
                lab_result_id=str(state.lab_result_id),
            )
            return state.model_copy(
                update={
                    "triage_group": "PENDING",
                    "triage_reason": "no llm client wired",
                    "requires_doctor_review": True,
                    "classify_source": None,
                    "step": LabTriageStep.HARD_BLOCK,
                    "turn_count": state.turn_count + 1,
                }
            )

        trace = new_trace()
        try:
            result = await classify_lab_result(row, llm_client, trace)
        except Exception as exc:
            logger.error(
                "lab_triage.classify_failed_fallback_hard_block",
                lab_result_id=str(state.lab_result_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            # Safety bias: classifier failed → escalate to BS review.
            return state.model_copy(
                update={
                    "triage_group": "PENDING",
                    "triage_reason": "classifier error — escalated for review",
                    "requires_doctor_review": True,
                    "step": LabTriageStep.HARD_BLOCK,
                    "turn_count": state.turn_count + 1,
                }
            )

        next_step = (
            LabTriageStep.HARD_BLOCK
            if result.triage_group == "GROUP_C"
            else LabTriageStep.ADVISE
        )
        return state.model_copy(
            update={
                "triage_group": result.triage_group,
                "triage_reason": result.reason,
                "requires_doctor_review": result.requires_doctor_review,
                "classify_source": result.source,
                "matched_rule_key": result.matched_rule_key,
                "step": next_step,
                "turn_count": state.turn_count + 1,
            }
        )

    return classify_node


def make_advise_node(pool: Optional[asyncpg.Pool]):
    """Compose patient-facing message for GROUP_A/B (and PENDING with review)."""

    async def advise_node(state: LabTriageState) -> LabTriageState:
        logger.info("lab_triage.advise", triage_group=state.triage_group)
        if state.triage_group == "GROUP_A":
            msg = "Kết quả xét nghiệm của bạn trong giới hạn bình thường."
        else:
            msg = "Kết quả có một số chỉ số cần bác sĩ xem xét. Vui lòng chờ xác nhận."
        return state.model_copy(
            update={
                "response_to_patient": msg,
                "step": LabTriageStep.DONE,
                "turn_count": state.turn_count + 1,
            }
        )

    return advise_node


def make_hard_block_node(pool: Optional[asyncpg.Pool]):
    """GROUP_C — HARD BLOCK: no patient response, escalation note for BS.

    Step is left at HARD_BLOCK (not DONE) so the graph can route into
    create_review_tasks afterwards. The final DONE transition happens
    inside create_review_tasks_node.
    """

    async def hard_block_node(state: LabTriageState) -> LabTriageState:
        logger.warning(
            "lab_triage.hard_block",
            lab_result_id=str(state.lab_result_id),
            triage_group=state.triage_group,
        )
        return state.model_copy(
            update={
                "response_to_patient": None,
                "escalation_note": (
                    f"[URGENT] Kết quả GROUP_C lab_result_id={state.lab_result_id}. "
                    "Yêu cầu bác sĩ xem xét ngay."
                ),
                "requires_doctor_review": True,
                "step": LabTriageStep.HARD_BLOCK,
                "turn_count": state.turn_count + 1,
            }
        )

    return hard_block_node


# SLA target for GROUP_C lab review — 4 hours from creation. Locked by
# clinical safety: P9.3 task spec. Do not relax without sign-off.
_LAB_REVIEW_SLA_HOURS = 4


def make_create_review_tasks_node(pool: Optional[asyncpg.Pool]):
    """After HARD_BLOCK, enqueue exactly one URGENT LAB_REVIEW staff task.

    Single-row architecture: one lab_triage invocation triages one
    lab_result_id, so this node creates at most one task per run (a list
    is returned for symmetry with the future batch flow).

    Safety bias: if the pool is missing or the task INSERT fails we still
    let the graph terminate (escalation_note already carries the alert)
    but log loudly and surface `error` on the state.
    """

    async def create_review_tasks_node(state: LabTriageState) -> LabTriageState:
        if state.lab_result_id is None:
            logger.warning("lab_triage.create_review_tasks.no_lab_result_id")
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "turn_count": state.turn_count + 1,
                }
            )

        if pool is None:
            logger.warning(
                "lab_triage.create_review_tasks.no_pool",
                lab_result_id=str(state.lab_result_id),
            )
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "no db pool wired",
                    "turn_count": state.turn_count + 1,
                }
            )

        row = state.lab_result_row
        test_name = getattr(row, "test_name", None) or "lab result"
        due_at = datetime.now(tz=timezone.utc) + timedelta(hours=_LAB_REVIEW_SLA_HOURS)

        task_input = CreateTaskInput(
            task_type="LAB_REVIEW",
            priority="URGENT",
            source_type="LAB_RESULT",
            source_id=state.lab_result_id,
            title=f"Review {test_name} — GROUP_C",
            description=state.triage_reason,
            due_at=due_at,
            sla_hours=_LAB_REVIEW_SLA_HOURS,
        )

        trace = new_trace()
        try:
            created = await create_task(pool, task_input, trace)
        except Exception as exc:
            logger.error(
                "lab_triage.create_review_tasks.failed",
                lab_result_id=str(state.lab_result_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return state.model_copy(
                update={
                    "step": LabTriageStep.DONE,
                    "error": "create_review_task_failed",
                    "turn_count": state.turn_count + 1,
                }
            )

        logger.info(
            "lab_triage.create_review_tasks.ok",
            lab_result_id=str(state.lab_result_id),
            task_id=str(created.task_id),
        )

        return state.model_copy(
            update={
                "task_ids": [*state.task_ids, created.task_id],
                "step": LabTriageStep.DONE,
                "turn_count": state.turn_count + 1,
            }
        )

    return create_review_tasks_node
