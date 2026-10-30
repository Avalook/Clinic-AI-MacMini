"""KHÔNG ĐẾN CÓ LÝ DO + HOÀN TÁC HUỶ / KHÔNG ĐẾN (30/10/2026) — Postgres thật.

    scripts/test-nhanh.sh src/tests/services/test_khong_den_va_hoan_tac_huy_db.py

Nút "Không đến" bấm là ghi luôn, không lý do, không đường quay lại — trái luật
"mọi thao tác nhân viên bấm phải hoàn tác được". Nay: không đến BẮT BUỘC mã lý
do (danh mục chung với huỷ, mã riêng); huỷ / không đến mở lại được
(`action="reopen"`) về đúng trạng thái trước, theo luật đặt lịch (ngày đã qua,
đã có lượt, lịch trùng, khung đầy → không), có vết ai mở lại, lúc nào.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.trang_thai_lich import mo_lai_duoc, ngay_cua_lich, trang_thai_mo_lai
from clinicai.services.booking_service import BookingService
from clinicai.services.ghi_chu_khach_service import GhiChuKhachService
from clinicai.services.tiep_don_service import dung_dong
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_doi_lich_nhanh_db import _dem, _dung, _lich, _mai_9h

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dong(pool: asyncpg.Pool, appt: str) -> asyncpg.Record:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT status, ly_do_huy_ma, cancellation_reason, cancelled_at,"
        " trang_thai_truoc_huy, clinic_patient_id::text AS pid"
        " FROM appointment WHERE id = $1::uuid",
        appt,
    )
    assert r is not None
    return r


async def _khong_den(pool: asyncpg.Pool, ca, appt: str, ma: str | None, chu=None):  # type: ignore[no-untyped-def]  # noqa: F811
    return await BookingService(pool).apply_action(
        appointment_id=appt,
        action="no_show",
        identity=ca["le_tan"],
        ly_do_huy_ma=ma,
        cancellation_reason=chu,
    )


async def _mo_lai(pool: asyncpg.Pool, identity, appt: str):  # type: ignore[no-untyped-def]  # noqa: F811
    return await BookingService(pool).apply_action(
        appointment_id=appt, action="reopen", identity=identity
    )


# ── Hàm thuần ────────────────────────────────────────────────────────────


async def test_luat_thuan_mo_lai_dau_vao_rac_khong_nem() -> None:
    assert trang_thai_mo_lai("SCHEDULED") == "SCHEDULED"
    assert trang_thai_mo_lai("CSKH_CONFIRMED") == "CSKH_CONFIRMED"
    # Không biết / rác / đã có mặt → CONFIRMED (lệnh chặn ca đã có lượt trước).
    for rac in (None, "", "CHECKED_IN", "CANCELLED", 5, ["x"]):
        assert trang_thai_mo_lai(rac) == "CONFIRMED"
    for moc_rac in (None, "", "2026-10-30", 123, datetime(2026, 10, 30, 9, 0)):
        assert ngay_cua_lich(moc_rac) is None
    bay_gio = datetime(2026, 10, 30, 3, 0, tzinfo=UTC)  # 10:00 giờ VN
    hom_qua = bay_gio - timedelta(days=1)
    som_hom_nay = datetime(2026, 10, 30, 0, 30, tzinfo=CLINIC_TZ)  # khung đã qua
    assert mo_lai_duoc("NO_SHOW", False, som_hom_nay, bay_gio) is True
    assert mo_lai_duoc("CANCELLED", False, bay_gio + timedelta(days=3), bay_gio)
    assert mo_lai_duoc("NO_SHOW", False, hom_qua, bay_gio) is False
    assert mo_lai_duoc("CANCELLED", True, bay_gio, bay_gio) is False
    assert mo_lai_duoc("CONFIRMED", False, bay_gio, bay_gio) is False
    assert mo_lai_duoc("NO_SHOW", False, "rác", bay_gio) is False
    assert mo_lai_duoc("NO_SHOW", False, bay_gio, None) is False


# ── Không đến phải có lý do ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ma", "chu"),
    [
        (None, "khách bận"),  # thiếu mã
        ("   ", None),  # rỗng
        ("KHAC", "  "),  # "Khác" mà không viết
        ("BAO_KHI_NHAC_HEN", None),  # mã của HUỶ, không phải của không đến
        ("XYZ_RAC", None),
    ],
)
async def test_khong_den_thieu_hoac_sai_ly_do_thi_4xx_lich_giu_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
    ma: str | None,
    chu: str | None,
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    with pytest.raises(ValidationError) as loi:
        await _khong_den(pool, ca, appt, ma, chu)
    assert loi.value.status_code == 422
    assert (await _dong(pool, appt))["status"] == "CONFIRMED"
    assert await _dem(pool, "appointment.no_show", appt) == 0


async def test_huy_khong_nhan_ma_cua_khong_den(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    with pytest.raises(ValidationError):
        await BookingService(pool).apply_action(
            appointment_id=appt,
            action="cancel",
            identity=ca["cskh"],
            ly_do_huy_ma="QUEN_LICH",
        )


async def test_khong_den_ghi_ly_do_roi_hoan_tac_ve_nhu_cu_co_vet(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    kq = await _khong_den(pool, ca, appt, "QUEN_LICH", "  hẹn gọi lại  ")
    assert kq["status"] == "NO_SHOW"
    d = await _dong(pool, appt)
    assert (d["status"], d["ly_do_huy_ma"], d["cancellation_reason"]) == (
        "NO_SHOW",
        "QUEN_LICH",
        "hẹn gọi lại",
    )
    assert d["trang_thai_truoc_huy"] == "CONFIRMED"
    # Không đến KHÔNG phải huỷ — các màn đọc `cancelled_at` là "huỷ lúc …".
    assert d["cancelled_at"] is None
    su_kien = await pool.fetchval(
        "SELECT payload->>'ly_do_ma' FROM domain_event"
        " WHERE event_type = 'appointment.no_show' AND aggregate_id = $1::uuid",
        appt,
    )
    assert su_kien == "QUEN_LICH"

    # Khung khách + danh sách tiếp đón: có lý do, có nút hoàn tác.
    tt = await GhiChuKhachService(pool).tom_tat(
        identity=ca["le_tan"], clinic_patient_id=d["pid"]
    )
    [lich] = [x for x in tt["lich_da_qua"] if x["id"] == appt]
    assert (lich["ly_do_huy_ma"], lich["mo_lai_duoc"]) == ("QUEN_LICH", True)

    kq = await _mo_lai(pool, ca["le_tan"], appt)
    assert kq["status"] == "CONFIRMED"
    d = await _dong(pool, appt)
    # Lý do cũ rời trạng thái hiện hành…
    assert (d["status"], d["ly_do_huy_ma"], d["cancellation_reason"]) == (
        "CONFIRMED",
        None,
        None,
    )
    assert d["trang_thai_truoc_huy"] is None
    # …nhưng nằm lại trong vết, cùng ai mở lại.
    vet = await pool.fetchrow(
        "SELECT tu_trang_thai, ve_trang_thai, ly_do_huy_ma, ly_do_chu,"
        " hoan_tac_boi_staff_id::text AS ai, hoan_tac_luc"
        " FROM appointment_hoan_tac_huy WHERE appointment_id = $1::uuid",
        appt,
    )
    assert vet is not None
    assert (vet["tu_trang_thai"], vet["ve_trang_thai"]) == ("NO_SHOW", "CONFIRMED")
    assert (vet["ly_do_huy_ma"], vet["ly_do_chu"]) == ("QUEN_LICH", "hẹn gọi lại")
    assert vet["ai"] == ca["le_tan"].staff_id and vet["hoan_tac_luc"] is not None
    assert await _dem(pool, "appointment.reopened", appt) == 1

    # Bấm hoàn tác lần hai → 409, không thêm vết.
    with pytest.raises(ConflictError):
        await _mo_lai(pool, ca["le_tan"], appt)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM appointment_hoan_tac_huy"
            " WHERE appointment_id = $1::uuid",
            appt,
        )
        == 1
    )
    # Mở lại xong lại đánh không đến được (vòng khép kín).
    await _khong_den(pool, ca, appt, "KHONG_LIEN_LAC_DUOC")


async def test_huy_tu_lich_cu_scheduled_hoan_tac_ve_scheduled(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h(), status="SCHEDULED")
    await BookingService(pool).apply_action(
        appointment_id=appt,
        action="cancel",
        identity=ca["cskh"],
        ly_do_huy_ma="BAO_KHI_XAC_NHAN",
    )
    assert (await _mo_lai(pool, ca["cskh"], appt))["status"] == "SCHEDULED"
    d = await _dong(pool, appt)
    assert (d["ly_do_huy_ma"], d["cancelled_at"]) == (None, None)
    huy_boi = await pool.fetchval(
        "SELECT huy_boi_staff_id::text FROM appointment_hoan_tac_huy"
        " WHERE appointment_id = $1::uuid",
        appt,
    )
    assert huy_boi == ca["cskh"].staff_id


async def test_du_lieu_cu_khong_co_trang_thai_truoc_ve_confirmed(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    await pool.execute(
        "UPDATE appointment SET status = 'CANCELLED', ly_do_huy_ma = 'KHAC',"
        " cancellation_reason = 'bận', cancelled_at = now() WHERE id = $1::uuid",
        appt,
    )
    assert (await _mo_lai(pool, ca["cskh"], appt))["status"] == "CONFIRMED"


async def test_hai_nguoi_cung_hoan_tac_chi_mot_nguoi_qua(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    await _khong_den(pool, ca, appt, "KHACH_BAO_BAN")
    kq = await asyncio.gather(
        _mo_lai(pool, ca["le_tan"], appt),
        _mo_lai(pool, ca["le_tan"], appt),
        return_exceptions=True,
    )
    assert sorted(type(x).__name__ for x in kq) == ["ConflictError", "dict"]
    assert await _dem(pool, "appointment.reopened", appt) == 1


async def test_ngay_da_qua_khong_mo_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    hom_qua = _mai_9h() - timedelta(days=2)
    appt = await _lich(pool, ca, hom_qua, status="NO_SHOW")
    with pytest.raises(ValidationError, match="ngày đã qua"):
        await _mo_lai(pool, ca["le_tan"], appt)
    assert (await _dong(pool, appt))["status"] == "NO_SHOW"


async def test_da_co_luot_kham_khong_mo_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    bd = datetime.now(UTC) + timedelta(minutes=30)
    appt = await _lich(pool, ca, bd)
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca["le_tan"]
    )
    await BookingService(pool).apply_action(
        appointment_id=appt,
        action="cancel",
        identity=ca["cskh"],
        ly_do_huy_ma="BAO_VAO_GIO_KHAM",
    )
    with pytest.raises(ConflictError, match="lượt khám"):
        await _mo_lai(pool, ca["cskh"], appt)
    assert (await _dong(pool, appt))["status"] == "CANCELLED"


async def test_khach_da_dat_lai_dung_gio_thi_khong_mo_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    await BookingService(pool).apply_action(
        appointment_id=appt,
        action="cancel",
        identity=ca["cskh"],
        ly_do_huy_ma="DAT_TRUNG",
    )
    d = await _dong(pool, appt)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, 'CONFIRMED')",
        CLINIC,
        d["pid"],
        ca["loc"],
        ca["dv"],
        _mai_9h(),
        _mai_9h() + timedelta(minutes=15),
    )
    with pytest.raises(ConflictError, match="trùng"):
        await _mo_lai(pool, ca["cskh"], appt)


async def test_khung_da_day_khong_mo_lai(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Ghế vãng lai luôn có trần (kể cả tuần chưa công bố lịch trực): đánh không
    đến làm trống ghế, người khác vào ngồi, hoàn tác phải bị chặn."""
    ca = await _dung(pool)
    bd = _mai_9h() + timedelta(hours=2)
    appt = await _lich(pool, ca, bd)
    await pool.execute(
        "UPDATE appointment SET booking_channel = 'WALK_IN', is_walkin = true"
        " WHERE id = $1::uuid",
        appt,
    )
    await _khong_den(pool, ca, appt, "KHONG_LIEN_LAC_DUOC")
    tran = await pool.fetchval(
        "SELECT walkin_cap FROM public.resolve_effective_cap($1::uuid, $2::uuid, $3)",
        CLINIC,
        ca["bs"].staff_id,
        bd,
    )
    for _ in range(int(tran)):
        pid = await pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'Khách vào thay', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"KDT-{uuid.uuid4().hex[:10]}",
            ca["loc"],
        )
        await pool.execute(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, doctor_id, status,"
            " booking_channel, is_walkin) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " $4::uuid, $5, $6, $7::uuid, 'CONFIRMED', 'WALK_IN', true)",
            CLINIC,
            pid,
            ca["loc"],
            ca["dv"],
            bd,
            bd + timedelta(minutes=15),
            ca["bs"].staff_id,
        )
    with pytest.raises(ConflictError, match="vãng lai"):
        await _mo_lai(pool, ca["le_tan"], appt)
    assert (await _dong(pool, appt))["status"] == "NO_SHOW"
    assert await _dem(pool, "appointment.reopened", appt) == 0


async def test_khong_co_quyen_thi_khong_hoan_tac(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    appt = await _lich(pool, ca, _mai_9h())
    await _khong_den(pool, ca, appt, "QUEN_LICH")
    async with pool.acquire() as conn:
        duoc_si = await _nguoi(conn, ca["loc"], "PHARMACIST")
        await ve_goi_mau_cu(conn, duoc_si)
    with pytest.raises(SafetyGateError):
        await _mo_lai(pool, duoc_si, appt)
    assert (await _dong(pool, appt))["status"] == "NO_SHOW"


async def test_danh_sach_tiep_don_dong_khong_den_co_ly_do_va_nut_hoan_tac() -> None:
    bay_gio = datetime.now(CLINIC_TZ)
    dong = {
        "appointment_id": "a",
        "status": "NO_SHOW",
        "slot_start": bay_gio - timedelta(hours=1),
        "ly_do_huy_ma": "KHACH_BAO_BAN",
        "cancellation_reason": None,
    }
    d = dung_dong(dong, [], bay_gio)
    assert d["trang_thai"]["loai"] == "khong_den"
    assert (d["ly_do_ma"], d["mo_lai_lich_duoc"]) == ("KHACH_BAO_BAN", True)
    # Dòng đang chờ: không có lý do, không có nút mở lại.
    cho = dung_dong({**dong, "status": "CONFIRMED"}, [], bay_gio)
    assert (cho["ly_do_ma"], cho["mo_lai_lich_duoc"]) == (None, False)
