"""Huỷ lịch TẠI CHỖ từ menu ⋯ dòng lịch hẹn (Tuyền bấm thật 29/09/2026) — Postgres thật.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55730/postgres \\
        .venv/bin/pytest src/tests/services/test_huy_lich_tai_cho_db.py

Popover "Huỷ lịch (ghi lý do)" gọi `PATCH /api/appointments {action:"cancel",
ly_do_huy_ma, cancellation_reason}` → `BookingService.apply_action`. Lý do là
BẮT BUỘC; rác phải thành 4xx có câu, không bao giờ 500; bị từ chối thì lịch
giữ nguyên.
"""

from __future__ import annotations

import asyncpg
import pydantic
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.v1.routers.booking import ActionRequest
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.booking_service import BookingService
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    _nguoi,
    pool,
)
from tests.services.test_doi_lich_nhanh_db import _dem, _dung, _lich, _mai_9h

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _trang_thai(pool: asyncpg.Pool, appt: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval("SELECT status FROM appointment WHERE id = $1::uuid", appt)
    )


@pytest.mark.parametrize(
    ("ma", "chu"),
    [
        (None, "khách bận"),  # thiếu mã lý do
        ("", None),  # chuỗi rỗng
        ("   ", "  "),  # toàn khoảng trắng
        ("KHAC", "   "),  # "Khác" mà không viết gì
        ("XYZ_RAC", None),  # mã lạ
        ("'; DROP TABLE appointment; --", None),  # rác kiểu tiêm SQL
    ],
)
async def test_thieu_hoac_rac_ly_do_thi_4xx_lich_giu_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
    ma: str | None,
    chu: str | None,
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    with pytest.raises(ValidationError) as loi:
        await BookingService(pool).apply_action(
            appointment_id=appt,
            action="cancel",
            identity=ca["cskh"],
            cancellation_reason=chu,
            ly_do_huy_ma=ma,
        )
    # 422 có câu tiếng Việt — không phải 500.
    assert loi.value.status_code == 422
    assert str(loi.value)
    assert await _trang_thai(pool, appt) == "CONFIRMED"
    assert await _dem(pool, "appointment.cancelled", appt) == 0


async def test_ma_ly_do_qua_dai_bi_chan_o_cua_pydantic() -> None:
    """Thân yêu cầu rác (mã dài hơn cột) dừng ở cửa → 422, không chạm DB."""
    with pytest.raises(pydantic.ValidationError):
        ActionRequest.model_validate({"action": "cancel", "ly_do_huy_ma": "X" * 33})
    with pytest.raises(pydantic.ValidationError):
        ActionRequest.model_validate({"action": "huy_bua"})


async def test_co_ly_do_thi_huy_ghi_ai_huy_va_su_kien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    kq = await BookingService(pool).apply_action(
        appointment_id=appt,
        action="cancel",
        identity=ca["cskh"],
        cancellation_reason="  khách đi công tác  ",
        ly_do_huy_ma="BAO_KHI_NHAC_HEN",
    )
    assert kq["status"] == "CANCELLED"
    dong = await pool.fetchrow(
        "SELECT status, ly_do_huy_ma, cancellation_reason,"
        " cancelled_by_staff_id::text AS ai, cancelled_at"
        " FROM appointment WHERE id = $1::uuid",
        appt,
    )
    assert dong["status"] == "CANCELLED"
    assert dong["ly_do_huy_ma"] == "BAO_KHI_NHAC_HEN"
    assert dong["cancellation_reason"] == "khách đi công tác"
    assert dong["ai"] == ca["cskh"].staff_id
    assert dong["cancelled_at"] is not None
    assert await _dem(pool, "appointment.cancelled", appt) == 1

    # Huỷ lần hai (bấm đúp / hai người cùng bấm) → 409, không ghi thêm sự kiện.
    with pytest.raises(ConflictError):
        await BookingService(pool).apply_action(
            appointment_id=appt,
            action="cancel",
            identity=ca["cskh"],
            ly_do_huy_ma="BAO_KHI_NHAC_HEN",
        )
    assert await _dem(pool, "appointment.cancelled", appt) == 1


async def test_khong_co_quyen_quan_ly_lich_thi_khong_huy_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Nút chỉ hiện với `booking.manage`; máy chủ vẫn tự chặn người không có."""
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    async with pool.acquire() as conn:
        duoc_si = await _nguoi(conn, ca["loc"], "PHARMACIST")
        await ve_goi_mau_cu(conn, duoc_si)  # gói lego cũ (mở full lego 30/09)
    with pytest.raises(SafetyGateError):
        await BookingService(pool).apply_action(
            appointment_id=appt,
            action="cancel",
            identity=duoc_si,
            ly_do_huy_ma="BAO_KHI_NHAC_HEN",
        )
    assert await _trang_thai(pool, appt) == "CONFIRMED"
