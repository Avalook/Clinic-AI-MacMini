"""VisitProgressService — the range guard and the shape it returns (ROLE-02).

The SQL itself is exercised against real Postgres by the e2e scripts; what is
worth pinning here is the part that has no database in it: a reversed or absurd
range must be refused rather than turned into a query, and the rows must come
back as flags.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import CLINIC_TZ as _VN
from clinicai.services.visit_progress_service import VisitProgressService


def _pool(rows: list[dict[str, Any]]) -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows)
    acquire = MagicMock()
    acquire.__aenter__ = AsyncMock(return_value=conn)
    acquire.__aexit__ = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire)
    return pool


@pytest.mark.asyncio
async def test_reversed_range_is_refused_without_touching_the_database() -> None:
    pool = _pool([])
    with pytest.raises(ValidationError):
        await VisitProgressService(pool).for_range(
            date_from=date(2026, 7, 30), date_to=date(2026, 7, 1), clinic_id=None
        )
    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_absurd_range_is_refused() -> None:
    pool = _pool([])
    with pytest.raises(ValidationError):
        await VisitProgressService(pool).for_range(
            date_from=date(2026, 1, 1), date_to=date(2026, 12, 31), clinic_id=None
        )
    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_returns_flags_and_sorts_paid_kinds() -> None:
    pool = _pool(
        [
            {
                "appointment_id": "a1",
                "visit_id": "v1",
                "vitals_recorded": True,
                "has_clinical_record": True,
                "has_prescription": False,
                "paid_kinds": ["thuoc", "dich_vu"],
                "exam_started_at": datetime(2026, 7, 30, 9, 14, tzinfo=_VN),
                "paid_at": datetime(2026, 7, 30, 10, 2, tzinfo=_VN),
            }
        ]
    )
    out = await VisitProgressService(pool).for_range(
        date_from=date(2026, 7, 30), date_to=date(2026, 7, 30), clinic_id=None
    )

    assert len(out) == 1
    assert out[0].appointment_id == "a1"
    assert out[0].vitals_recorded is True
    # Sorted so the caller can compare without caring about aggregate order.
    assert out[0].paid_kinds == ["dich_vu", "thuoc"]
    # Giờ của hai mốc giữa đi kèm — thanh tiến trình ở /home in chúng dưới
    # từng nút.
    assert out[0].exam_started_at == datetime(2026, 7, 30, 9, 14, tzinfo=_VN)
    assert out[0].paid_at == datetime(2026, 7, 30, 10, 2, tzinfo=_VN)
    # Nothing from the note itself leaves the service.
    assert not hasattr(out[0], "soap_objective")


@pytest.mark.asyncio
async def test_a_visit_with_no_payments_reports_an_empty_list() -> None:
    pool = _pool(
        [
            {
                "appointment_id": "a2",
                "visit_id": None,
                "vitals_recorded": False,
                "has_clinical_record": False,
                "has_prescription": False,
                "paid_kinds": None,
                "exam_started_at": None,
                "paid_at": None,
            }
        ]
    )
    out = await VisitProgressService(pool).for_range(
        date_from=date(2026, 7, 30), date_to=date(2026, 7, 30), clinic_id=None
    )
    assert out[0].paid_kinds == []
    assert out[0].visit_id is None
    # Chưa ai bắt tay vào và chưa thu đồng nào → không bịa ra giờ.
    assert out[0].exam_started_at is None
    assert out[0].paid_at is None
