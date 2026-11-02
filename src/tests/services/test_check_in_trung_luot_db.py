"""Hai sửa sau ca 01/11/2026 (hai record cho một lần đến) — Postgres thật.

    scripts/test-nhanh.sh src/tests/services/test_check_in_trung_luot_db.py

1. Check-in lịch thứ hai khi khách còn lượt mở hôm nay → máy chủ HỎI LẠI
   (409 KHACH_DANG_CO_LUOT), đồng ý thì qua và ghi vết.
2. Lượt đã huỷ lịch rồi check-out MỘT lần thì coi là đã đóng: bản cũ đọc bước
   đóng lượt (đã bị huỷ theo lịch) nên dòng ở lì quầy, bấm 14 lần ghi 14 sự kiện.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.booking_service import BookingService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_lich_nhanh_db import _bay_gio, _dung, _lich

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lich_nua(pool: asyncpg.Pool, ca: dict[str, Any], lich_dau: str) -> str:  # noqa: F811
    """Lịch thứ hai cùng khách, khác giờ — đúng hình dạng lịch dư ca 01/11."""
    return str(
        await pool.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status)"
            " SELECT clinic_id, clinic_patient_id, location_id, service_type_id,"
            " slot_start + interval '30 minutes', slot_end + interval '30 minutes',"
            " doctor_id, 'CONFIRMED' FROM appointment WHERE id = $1::uuid"
            " RETURNING id::text",
            lich_dau,
        )
    )


async def _check_in(
    pool: asyncpg.Pool,  # noqa: F811
    ca: dict[str, Any],
    lich: str,
    **them: Any,
) -> Any:
    return await BookingService(pool).apply_action(
        appointment_id=lich, action="checkin", identity=ca["le_tan"], **them
    )


async def _so_luot(pool: asyncpg.Pool, lich_dau: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM visit WHERE clinic_patient_id ="
            " (SELECT clinic_patient_id FROM appointment WHERE id = $1::uuid)",
            lich_dau,
        )
    )


async def _dat_hai_lich(pool: asyncpg.Pool) -> tuple[dict[str, Any], str, str]:  # noqa: F811
    ca = await _dung(pool)
    dau = await _lich(pool, ca, _bay_gio())
    return ca, dau, await _lich_nua(pool, ca, dau)


async def test_khach_con_luot_mo_thi_hoi_lai_khong_tao_luot(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca, dau, sau = await _dat_hai_lich(pool)
    await _check_in(pool, ca, dau)

    with pytest.raises(LuotKhamConflictError) as loi:
        await _check_in(pool, ca, sau)

    assert loi.value.error_code == "KHACH_DANG_CO_LUOT"
    assert loi.value.chi_tiet == {"ma": "KHACH_DANG_CO_LUOT"}
    assert "lượt thứ hai" in loi.value.message
    assert await _so_luot(pool, dau) == 1
    trang_thai = await pool.fetchval(
        "SELECT status FROM appointment WHERE id = $1::uuid", sau
    )
    assert trang_thai == "CONFIRMED"


async def test_dong_y_thi_qua_va_ghi_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, dau, sau = await _dat_hai_lich(pool)
    await _check_in(pool, ca, dau)

    await _check_in(pool, ca, sau, dong_y_trung_luot=True)

    assert await _so_luot(pool, dau) == 2
    payload = await pool.fetchval(
        "SELECT payload FROM event_log WHERE aggregate_id = $1::uuid"
        " AND event_type = 'appointment.checked_in'",
        sau,
    )
    assert json.loads(payload)["dong_y_trung_luot"] is True


async def test_luot_truoc_da_dong_thi_khong_hoi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Khách về rồi quay lại trong ngày là lượt mới hợp lệ."""
    ca, dau, sau = await _dat_hai_lich(pool)
    await _check_in(pool, ca, dau)
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE appointment_id = $1::uuid", dau
    )

    await _check_in(pool, ca, sau)

    assert await _so_luot(pool, dau) == 2


async def test_luot_mo_tu_hom_truoc_thi_khong_hoi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Lượt quên đóng hôm trước không phải lần đến này."""
    ca, dau, sau = await _dat_hai_lich(pool)
    await _check_in(pool, ca, dau)
    hom_qua = _bay_gio().astimezone(CLINIC_TZ) - timedelta(days=1)
    await pool.execute(
        "UPDATE visit SET checked_in_at = $2 WHERE appointment_id = $1::uuid",
        dau,
        hom_qua,
    )

    await _check_in(pool, ca, sau)

    assert await _so_luot(pool, dau) == 2


async def test_doi_lich_kem_check_in_cung_hoi_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, dau, sau = await _dat_hai_lich(pool)
    await _check_in(pool, ca, dau)
    bd = await pool.fetchrow(
        "SELECT slot_start, slot_end, doctor_id::text AS bs FROM appointment"
        " WHERE id = $1::uuid",
        sau,
    )
    assert bd is not None
    goi: dict[str, Any] = {
        "appointment_id": sau,
        "identity": ca["cskh"],
        "slot_start": bd["slot_start"],
        "slot_end": bd["slot_end"],
        "doctor_id": bd["bs"],
        "ly_do": "Khách tới sớm",
        "check_in": True,
    }

    with pytest.raises(LuotKhamConflictError):
        await BookingService(pool).doi_lich_nhanh(**goi)
    assert await _so_luot(pool, dau) == 1


async def _dem_dong(pool: asyncpg.Pool, visit: str) -> int:  # noqa: F811
    return int(
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1::uuid"
            " AND event_type IN ('dispatch.checkout', 'visit.closed_incomplete')",
            visit,
        )
    )


async def test_luot_huy_lich_chi_dong_mot_lan_va_roi_danh_sach(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    lich = await _lich(pool, ca, _bay_gio())
    await _check_in(pool, ca, lich)
    await BookingService(pool).apply_action(
        appointment_id=lich,
        action="cancel",
        identity=ca["cskh"],
        cancellation_reason="Ấn nhầm",
        ly_do_huy_ma="KHAC",
    )
    visit = str(
        await pool.fetchval(
            "SELECT visit_id FROM visit WHERE appointment_id = $1::uuid", lich
        )
    )
    dv = CheckoutService(pool)

    dau = await dv.close(identity=ca["le_tan"], visit_id=visit, override_reason="x")
    lan_hai = await dv.close(identity=ca["le_tan"], visit_id=visit, override_reason="x")

    assert not dau.get("already_closed")
    assert lan_hai == {"ok": True, "already_closed": True}
    assert await _dem_dong(pool, visit) == 1
    dong = next(
        d
        for d in await dv.pending_list(identity=ca["le_tan"])
        if d["visit_id"] == visit
    )
    assert dong["already_closed"] is True
