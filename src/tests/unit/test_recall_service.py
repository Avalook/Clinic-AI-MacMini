"""Recall projection: CSKH receives instructions, never the SOAP document."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.services.cskh_service import FOLLOWUP_KIND
from clinicai.services.recall_service import RecallService


def _pool(rows: list[dict[str, Any]]) -> tuple[MagicMock, AsyncMock]:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire)
    return pool, conn.fetch


@pytest.mark.asyncio
async def test_recall_projection_is_tenant_bound_and_contains_no_soap_note() -> None:
    pool, fetch = _pool(
        [
            {
                "clinic_patient_id": "patient-1",
                "full_name": "Nguyen A",
                "phone_primary": "0900000000",
                "due_text": "2026-07-31",
                "repeat_tests": ["HM", "SH"],
                "instruction": "Nhịn ăn sáng",
                "last_called_date": None,
            }
        ]
    )

    rows = await RecallService(pool).due_followups(
        clinic_id="clinic-a",
        today=date(2026, 7, 30),
    )

    assert rows[0].clinic_patient_id == "patient-1"
    assert rows[0].repeat_tests == ["HM", "SH"]
    assert rows[0].instruction == "Nhịn ăn sáng"
    assert not hasattr(rows[0], "soap_plan")

    assert fetch.await_args is not None
    sql, clinic_id, since, today, followup_kind = fetch.await_args.args
    assert "v.clinic_id = $1::uuid" in sql
    assert "source_appt.status = 'COMPLETED'" in sql
    assert "v.status IN ('FINALIZED', 'AMENDED')" in sql
    assert "future_appt.clinic_id = $1::uuid" in sql
    assert "due_text::date" not in sql
    assert clinic_id == "clinic-a"
    assert since == date(2026, 1, 28)
    assert today == date(2026, 7, 30)
    # Lần gọi gần nhất lấy từ cskh_log, lọc đúng loại việc "nhắc tái khám" —
    # không phải mọi ghi chú CSKH từng viết cho bệnh nhân này.
    assert followup_kind == FOLLOWUP_KIND
    assert "cskh_log c" in sql
    assert "c.clinic_id = $1::uuid" in sql


@pytest.mark.asyncio
async def test_invalid_repeat_test_payload_fails_closed_to_empty_list() -> None:
    pool, _ = _pool(
        [
            {
                "clinic_patient_id": "patient-2",
                "full_name": "Nguyen B",
                "phone_primary": None,
                "due_text": "2026-07-30",
                "repeat_tests": None,
                "instruction": None,
                "last_called_date": None,
            }
        ]
    )

    rows = await RecallService(pool).due_followups(
        clinic_id="clinic-a",
        today=date(2026, 7, 30),
    )

    assert rows[0].repeat_tests == []
    assert rows[0].instruction == ""
    assert rows[0].last_called_date is None


@pytest.mark.asyncio
async def test_invalid_due_date_skips_only_that_recall_row() -> None:
    pool, _ = _pool(
        [
            {
                "clinic_patient_id": "invalid-date",
                "full_name": "Bad Date",
                "phone_primary": None,
                "due_text": "2026-99-99",
                "repeat_tests": [],
                "instruction": "",
                "last_called_date": None,
            },
            {
                "clinic_patient_id": "valid-date",
                "full_name": "Good Date",
                "phone_primary": None,
                "due_text": "2026-07-30",
                "repeat_tests": [],
                "instruction": "",
                "last_called_date": None,
            },
        ]
    )

    rows = await RecallService(pool).due_followups(
        clinic_id="clinic-a",
        today=date(2026, 7, 30),
    )

    assert [row.clinic_patient_id for row in rows] == ["valid-date"]


@pytest.mark.asyncio
async def test_last_call_date_is_carried_through_for_the_screen() -> None:
    """Gọi xong bệnh nhân VẪN nằm trong danh sách — nên phải thấy đã gọi ngày nào.

    Họ chỉ rời danh sách khi có lịch hẹn mới. Không mang ngày gọi ra thì màn
    hình không phân biệt được người chưa ai đụng tới với người vừa gọi sáng nay.
    """
    pool, _ = _pool(
        [
            {
                "clinic_patient_id": "patient-3",
                "full_name": "Nguyen C",
                "phone_primary": "0900000001",
                "due_text": "2026-07-30",
                "repeat_tests": [],
                "instruction": "",
                "last_called_date": date(2026, 7, 29),
            }
        ]
    )

    rows = await RecallService(pool).due_followups(
        clinic_id="clinic-a",
        today=date(2026, 7, 30),
    )

    assert rows[0].last_called_date == date(2026, 7, 29)
