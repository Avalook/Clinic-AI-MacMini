"""State for lab_triage sub-graph."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LabTriageStep(str, Enum):
    RECEIVE = "receive"
    FETCH = "fetch"
    CLASSIFY = "classify"
    ADVISE = "advise"
    HARD_BLOCK = "hard_block"
    DONE = "done"


class LabTriageState(BaseModel):
    """State passed through lab_triage sub-graph nodes."""

    # Pydantic carries LabResultRow (BaseModel) and ClassifyResult (BaseModel)
    # without per-field type registration; allow arbitrary types so we don't
    # have to import from tools/ here for typing alone.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Input từ orchestrator
    lab_result_id: Optional[UUID] = None
    clinic_patient_id: Optional[UUID] = None

    # Loaded by fetch_node
    lab_result_row: Optional[Any] = None  # tools.lab.query_lab_result.LabResultRow

    # Triage output
    triage_group: Optional[str] = None  # GROUP_A / GROUP_B / GROUP_C / PENDING
    triage_reason: Optional[str] = None
    requires_doctor_review: bool = False
    classify_source: Optional[str] = None  # "RULE" / "LLM_HAIKU" / "LLM_SONNET"
    matched_rule_key: Optional[str] = None

    # Flow control
    step: LabTriageStep = LabTriageStep.RECEIVE
    turn_count: int = 0

    # Output
    response_to_patient: Optional[str] = None  # None nếu GROUP_C (hard block)
    escalation_note: Optional[str] = None
    error: Optional[str] = None

    # Task creation (P9.3: GROUP_C → LAB_REVIEW URGENT task, SLA=4h)
    task_ids: list[UUID] = Field(default_factory=list)
