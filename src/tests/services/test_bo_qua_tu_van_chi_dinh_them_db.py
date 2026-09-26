"""Tuyền 25/09/2026.

* Điều dưỡng tick "Bỏ qua bác sĩ tư vấn" lúc [Đo xong] → khách rời hàng tư vấn,
  vào thẳng hàng bác sĩ chính. Không tick → vẫn qua tư vấn như thường.
* Tư vấn đã nhận khách thì tick không kéo khách ra giữa chừng.
* Chỉ định thêm trong CÙNG lượt: mỗi chỉ định mang "lần" theo vòng khám.
"""

from __future__ import annotations

import datetime as dt

import asyncpg
import pytest

from clinicai.phieu_kham.ket_qua_chi_dinh import doc_ket_qua_theo_chi_dinh
from clinicai.services.booking_service import BookingService
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.sinh_hieu_service import SinhHieuService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _qua_tu_van(pool: asyncpg.Pool, ca: Ca) -> None:  # noqa: F811
    await pool.execute(
        "UPDATE service_type SET qua_tu_van = true WHERE id = $1::uuid", ca.loai_kham
    )


async def _do(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    *,
    bo_qua: bool,
) -> None:
    svc = SinhHieuService(pool)
    await svc.bat_dau_do_sinh_hieu(visit_id=visit, identity=ca.dd)
    await svc.record_vitals(
        visit_id=visit,
        raw={"systolic": 120, "diastolic": 80},
        identity=ca.dd,
        idempotency_key=_khoa(),
        bo_qua_tu_van=bo_qua,
    )
    await chay_hanh_trinh(pool)


async def _hang(pool: asyncpg.Pool, visit: str) -> dict[str, str]:  # noqa: F811
    return {
        r["lane"]: r["status"]
        for r in await pool.fetch(
            "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid"
            " ORDER BY created_at",
            visit,
        )
    }


async def _duong(pool: asyncpg.Pool, visit: str) -> str | None:  # noqa: F811
    v = await pool.fetchval(
        "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", visit
    )
    return None if v is None else str(v)


async def test_tick_bo_qua_tu_van_vao_thang_bac_si_chinh(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _qua_tu_van(pool, ca)
    thuong = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    bo_qua = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)

    await _do(pool, ca, thuong, bo_qua=False)
    await _do(pool, ca, bo_qua, bo_qua=True)

    assert await _duong(pool, thuong) == "TU_VAN"
    assert (await _hang(pool, thuong)) == {"TU_VAN": "waiting"}

    assert await _duong(pool, bo_qua) == "PRIMARY"
    hang = await _hang(pool, bo_qua)
    assert hang["TU_VAN"] == "cancelled", "rời hàng tư vấn"
    assert hang["DOCTOR"] in ("waiting", "blocked"), "vào hàng bác sĩ chính"
    kinds = {
        r["kind"]: r["status"]
        for r in await pool.fetch(
            "SELECT kind, status FROM consultation WHERE visit_id = $1::uuid", bo_qua
        )
    }
    assert kinds == {"TU_VAN": "cancelled", "PRIMARY": "queued"}


async def test_tu_van_da_nhan_khach_thi_tick_khong_keo_ra(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    await _qua_tu_van(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    tu_van = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'TU_VAN'",
        visit,
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=tu_van, identity=ca.bac_si
    )

    await _do(pool, ca, visit, bo_qua=True)

    assert await _duong(pool, visit) == "TU_VAN"
    assert (
        await pool.fetchval(
            "SELECT status FROM consultation WHERE id = $1::uuid", tu_van
        )
        == "in_progress"
    )


async def test_khach_tai_kham_mac_dinh_van_qua_tu_van(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Dây H1 "khách quen vào thẳng" TẮT mặc định (Tuyền 25/09: "cứ qua bác sĩ
    tư vấn như bình thường") — lịch tái khám vẫn vào hàng tư vấn."""
    ca = await _dung(pool)
    await _qua_tu_van(pool, ca)
    bd = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=40)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status, patient_kind)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED', 'RETURN') RETURNING id::text",
        CLINIC,
        await _benh_nhan(pool, ca),
        ca.loc,
        ca.loai_kham,
        bd,
        bd + dt.timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca.le_tan
    )
    await chay_hanh_trinh(pool)
    visit = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    assert await _duong(pool, visit) == "TU_VAN"


async def test_chi_dinh_them_mang_lan_theo_vong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    _con, lan_1 = await _kham_va_chi_dinh(pool, ca, visit)
    # Khách làm xong quay lại: vòng đọc kết quả (REVIEW, vòng 2) đang khám.
    vong_2 = await pool.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id, started_by, started_at)"
        " VALUES ($1::uuid, $2::uuid, 2, 'REVIEW', 'in_progress', $3::uuid,"
        " $3::uuid, now()) RETURNING id::text",
        CLINIC,
        visit,
        ca.bac_si.staff_id,
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=vong_2,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
    )
    lan_2 = str(kq["order_ids"][0])
    async with pool.acquire() as conn:
        ds = await doc_ket_qua_theo_chi_dinh(conn, clinic_id=CLINIC, visit_id=visit)
    lan = {d["service_order_id"]: d["lan"] for d in ds}
    assert lan[lan_1] == 1
    assert lan[lan_2] == 2, "chỉ định thêm ở vòng sau là lần 2 của CÙNG lượt"
    assert all(d["chi_dinh_luc"] for d in ds)
    assert not any(d["mang_sang"] for d in ds)


async def test_o_tick_ap_ngay_va_bo_tick_la_ve_tu_van(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền 25/09 (ca Lê Hoài Thu): tick là áp ngay vào vị trí khách, bỏ tick là
    khách về lại hàng tư vấn; tư vấn xong vẫn sang bác sĩ chính như thường."""
    ca = await _dung(pool)
    await _qua_tu_van(pool, ca)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    await _do(pool, ca, visit, bo_qua=False)
    svc = LuotKhamService(pool)

    await svc.doi_duong_tu_van(visit_id=visit, bo_qua=True, identity=ca.dd)
    assert await _duong(pool, visit) == "PRIMARY"
    await svc.doi_duong_tu_van(visit_id=visit, bo_qua=True, identity=ca.dd)  # lặp: êm

    await svc.doi_duong_tu_van(visit_id=visit, bo_qua=False, identity=ca.dd)
    assert await _duong(pool, visit) == "TU_VAN"
    hang = await pool.fetch(
        "SELECT lane, status FROM queue_entry WHERE visit_id = $1::uuid"
        " AND status NOT IN ('done', 'left', 'cancelled')",
        visit,
    )
    assert [(r["lane"], r["status"]) for r in hang] == [("TU_VAN", "waiting")]

    # Tư vấn nhận khách → không bỏ qua được nữa; xong tư vấn → bác sĩ chính.
    tu_van = await pool.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
        " AND kind = 'TU_VAN'",
        visit,
    )
    await svc.start_consultation(consultation_id=tu_van, identity=ca.bac_si)
    with pytest.raises(LuotKhamConflictError):
        await svc.doi_duong_tu_van(visit_id=visit, bo_qua=True, identity=ca.dd)
    await svc.xong_tu_van(consultation_id=tu_van, identity=ca.bac_si)
    await chay_hanh_trinh(pool)  # H3: tư vấn xong → hàng bác sĩ chính
    assert (
        await pool.fetchval(
            "SELECT status FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
        == "queued"
    )


async def _check_in_chua_h1(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    """Check-in mà KHÔNG chạy người đưa tin — dây H1 chưa kịp xếp đường."""
    bd = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED') RETURNING id::text",
        CLINIC,
        await _benh_nhan(pool, ca),
        ca.loc,
        ca.loai_kham,
        bd,
        bd + dt.timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    await BookingService(pool).apply_action(
        appointment_id=appt, action="checkin", identity=ca.le_tan
    )
    return str(
        await pool.fetchval(
            "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
        )
    )


async def test_tick_bo_qua_truoc_khi_h1_xep_duong_van_vao_thang(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Check-in xong đo NGAY, dây H1 (chạy nền) chưa kịp xếp đường: tick "bỏ
    qua" vẫn phải đưa khách vào thẳng bác sĩ chính — trước 26/09 bị 409 và
    khách vẫn sang tư vấn (mô phỏng K21). H1 tới sau không đẻ lại tư vấn."""
    ca = await _dung(pool)
    await _qua_tu_van(pool, ca)
    o_tick = await _check_in_chua_h1(pool, ca)
    do_xong = await _check_in_chua_h1(pool, ca)
    assert await _duong(pool, o_tick) is None, "H1 chưa chạy"

    # Ô tick (áp ngay) — KHÔNG chạy người đưa tin trước.
    await LuotKhamService(pool).doi_duong_tu_van(
        visit_id=o_tick, bo_qua=True, identity=ca.dd
    )
    # Nút Đo xong kèm tick — cũng trước khi H1 chạy (`_do` chạy người đưa tin
    # SAU khi lệnh đo đã xong).
    await _do(pool, ca, do_xong, bo_qua=True)

    for v in (o_tick, do_xong):
        assert await _duong(pool, v) == "PRIMARY"
        kinds = {
            r["kind"]: r["status"]
            for r in await pool.fetch(
                "SELECT kind, status FROM consultation WHERE visit_id = $1::uuid", v
            )
        }
        assert kinds == {"TU_VAN": "cancelled", "PRIMARY": "queued"}
