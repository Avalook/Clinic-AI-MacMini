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
                "vitals_status": "recorded",
                "vitals_benh_an_cu": False,
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
                "vitals_status": None,
                "vitals_benh_an_cu": False,
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


@pytest.mark.asyncio
async def test_regression_a_visit_co_appointment_paid() -> None:
    """Test A: visit có appointment + PAID -> progress trả paid_kinds đúng."""
    pool = _pool(
        [
            {
                "appointment_id": "a-101",
                "visit_id": "v-101",
                "vitals_status": "recorded",
                "vitals_benh_an_cu": False,
                "has_clinical_record": True,
                "has_prescription": False,
                "paid_kinds": ["dich_vu"],
                "exam_started_at": datetime(2026, 9, 20, 8, 30, tzinfo=_VN),
                "paid_at": datetime(2026, 9, 20, 9, 15, tzinfo=_VN),
            }
        ]
    )
    out = await VisitProgressService(pool).for_range(
        date_from=date(2026, 9, 20), date_to=date(2026, 9, 20), clinic_id=None
    )
    assert len(out) == 1
    assert out[0].appointment_id == "a-101"
    assert out[0].visit_id == "v-101"
    assert out[0].paid_kinds == ["dich_vu"]
    assert out[0].paid_at == datetime(2026, 9, 20, 9, 15, tzinfo=_VN)


@pytest.mark.asyncio
async def test_regression_b_visit_appointment_id_null_paid() -> None:
    """Test B: visit appointment_id NULL + payment dich_vu PAID:
    progress VẪN có row theo visit_id và paid_kinds=['dich_vu'].
    """
    pool = _pool(
        [
            {
                "appointment_id": None,
                "visit_id": "v-walkin-202",
                "vitals_status": "recorded",
                "vitals_benh_an_cu": False,
                "has_clinical_record": True,
                "has_prescription": False,
                "paid_kinds": ["dich_vu"],
                "exam_started_at": datetime(2026, 9, 20, 10, 0, tzinfo=_VN),
                "paid_at": datetime(2026, 9, 20, 10, 45, tzinfo=_VN),
            }
        ]
    )
    out = await VisitProgressService(pool).for_range(
        date_from=date(2026, 9, 20), date_to=date(2026, 9, 20), clinic_id=None
    )
    assert len(out) == 1
    assert out[0].appointment_id is None
    assert out[0].visit_id == "v-walkin-202"
    assert out[0].paid_kinds == ["dich_vu"]
    assert out[0].paid_at == datetime(2026, 9, 20, 10, 45, tzinfo=_VN)


@pytest.mark.asyncio
async def test_regression_c_appointmentless_khong_prescription_home_paid_true() -> None:
    """Test C: appointmentless visit không prescription:
    home tính paid=true sau dịch vụ PAID.
    """
    p = (
        await VisitProgressService(
            _pool(
                [
                    {
                        "appointment_id": None,
                        "visit_id": "v-smoke",
                        "vitals_status": "recorded",
                        "vitals_benh_an_cu": False,
                        "has_clinical_record": True,
                        "has_prescription": False,
                        "paid_kinds": ["dich_vu"],
                        "exam_started_at": datetime(2026, 9, 20, 13, 0, tzinfo=_VN),
                        "paid_at": datetime(2026, 9, 20, 13, 15, tzinfo=_VN),
                    }
                ]
            )
        ).for_range(
            date_from=date(2026, 9, 20), date_to=date(2026, 9, 20), clinic_id=None
        )
    )[0]

    # Mô phỏng logic tính v.paid ở home/page.tsx:
    kinds = set(p.paid_kinds)
    paid = "dich_vu" in kinds and (not p.has_prescription or "thuoc" in kinds)
    assert paid is True
    assert p.paid_at is not None


@pytest.mark.asyncio
async def test_regression_d_appointmentless_co_prescription() -> None:
    """Test D: appointmentless visit có prescription:
    chỉ dịch_vu PAID => chưa thanh toán đủ (paid=False).
    dich_vu + thuoc PAID => paid=True.
    """
    # 1. Chỉ mới thu dịch vụ, chưa thu thuốc
    p1 = (
        await VisitProgressService(
            _pool(
                [
                    {
                        "appointment_id": None,
                        "visit_id": "v-rx",
                        "vitals_status": "recorded",
                        "vitals_benh_an_cu": False,
                        "has_clinical_record": True,
                        "has_prescription": True,
                        "paid_kinds": ["dich_vu"],
                        "exam_started_at": datetime(2026, 9, 20, 13, 0, tzinfo=_VN),
                        "paid_at": datetime(2026, 9, 20, 13, 15, tzinfo=_VN),
                    }
                ]
            )
        ).for_range(
            date_from=date(2026, 9, 20), date_to=date(2026, 9, 20), clinic_id=None
        )
    )[0]
    kinds1 = set(p1.paid_kinds)
    paid1 = "dich_vu" in kinds1 and (not p1.has_prescription or "thuoc" in kinds1)
    assert paid1 is False

    # 2. Đã thu cả dịch vụ và thuốc
    p2 = (
        await VisitProgressService(
            _pool(
                [
                    {
                        "appointment_id": None,
                        "visit_id": "v-rx",
                        "vitals_status": "recorded",
                        "vitals_benh_an_cu": False,
                        "has_clinical_record": True,
                        "has_prescription": True,
                        "paid_kinds": ["dich_vu", "thuoc"],
                        "exam_started_at": datetime(2026, 9, 20, 13, 0, tzinfo=_VN),
                        "paid_at": datetime(2026, 9, 20, 13, 30, tzinfo=_VN),
                    }
                ]
            )
        ).for_range(
            date_from=date(2026, 9, 20), date_to=date(2026, 9, 20), clinic_id=None
        )
    )[0]
    kinds2 = set(p2.paid_kinds)
    paid2 = "dich_vu" in kinds2 and (not p2.has_prescription or "thuoc" in kinds2)
    assert paid2 is True


def test_regression_e_sql_excludes_voided_payments_and_anchors_visit() -> None:
    """Test E: SQL anchor trên visit v và loại trừ payment VOIDED."""
    from clinicai.services.visit_progress_service import _PROGRESS_SQL

    # Phải bắt đầu từ visit v, không phải appointment a
    assert "FROM visit v" in _PROGRESS_SQL
    assert "LEFT JOIN appointment a" in _PROGRESS_SQL
    # Payment phải loại trừ voided_at
    assert "pm.status = 'PAID'" in _PROGRESS_SQL
    assert "pm.voided_at IS NULL" in _PROGRESS_SQL
