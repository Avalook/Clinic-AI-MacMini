"""Lỗ hổng bộ mô phỏng NGÀY KHÁM bắt được (24/09/2026) — mỗi cái một bài kiểm.

1. Khách vãng lai đặt + tự check-in KHÔNG phát `visit.checked_in` → không xếp đường.
2. Tự xếp phòng / xếp tay không lọc CƠ SỞ → khách Kim Ngưu vào phòng Hào Nam.
3. Hai quầy tạo CÙNG MỘT khách cùng lúc → hai hồ sơ trùng.
4. Tuần lịch trực đã công bố, ngày không ai trực → vẫn đặt được bác sĩ nghỉ.
5. Khách quen của bác sĩ chính vẫn bị đưa qua tư vấn.
6. Kê đơn không phát sự kiện nghiệp vụ.
7. Mã tham chiếu không tồn tại (khoá ngoại) → 500.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.core.clock import CLINIC_TZ
from clinicai.schemas.patient import PatientCreateDTO
from clinicai.services.booking_service import BookingService
from clinicai.services.patient_service import PatientService
from clinicai.services.service_routing_service import co_so_cua_luot, eligible_rooms
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    NODE,
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _co_so_khac(pool: asyncpg.Pool, loc: str) -> str:  # noqa: F811
    khac = await pool.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
        " AND id <> $2::uuid ORDER BY created_at LIMIT 1",
        CLINIC,
        loc,
    )
    if khac is None:
        khac = await pool.fetchval(
            "INSERT INTO clinic_location (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, 'Cơ sở thử', true) RETURNING id::text",
            CLINIC,
            f"CS-{uuid.uuid4().hex[:6]}",
        )
    return str(khac)


async def test_xep_phong_chi_trong_co_so_cua_luot(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    khac = await _co_so_khac(pool, ca.loc)
    async with pool.acquire() as conn:
        phong_khac = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3,"
            " 'Phòng cơ sở khác',"
            " $4, true, true, 0) RETURNING id::text",
            CLINIC,
            khac,
            f"CSK-{uuid.uuid4().hex[:6]}",
            NODE,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong_khac,
            NODE,
        )
    pid = await _benh_nhan(pool, ca)
    vid = await _check_in(pool, ca, pid, ca.loai_kham)
    async with pool.acquire() as conn:
        # Lượt mở ra mang cơ sở của lịch hẹn.
        assert await co_so_cua_luot(conn, CLINIC, visit_id=vid) == ca.loc
        assert (
            await conn.fetchval(
                "SELECT location_id::text FROM visit WHERE visit_id = $1::uuid", vid
            )
            == ca.loc
        )
        cung = {r.room_id for r in await eligible_rooms(conn, CLINIC, NODE, ca.loc)}
        assert ca.phong in cung
        assert str(phong_khac) not in cung
        # Không lọc (màn cấu hình) thì vẫn thấy cả hai.
        tat_ca = {r.room_id for r in await eligible_rooms(conn, CLINIC, NODE)}
        assert str(phong_khac) in tat_ca


async def test_hai_quay_tao_cung_mot_khach_cung_luc_chi_mot_ho_so(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    so = f"09{uuid.uuid4().int % 10**8:08d}"
    dto = PatientCreateDTO(
        full_name="Khách Trùng Đồng Thời",
        location_id=uuid.UUID(ca.loc),
        phone_primary=so,
    )
    kq = await asyncio.gather(
        PatientService(pool).create_patient(dto, ca.le_tan),
        PatientService(pool).create_patient(dto, ca.le_tan),
    )
    tao = [r for r in kq if r.patient is not None]
    trung = [r for r in kq if r.duplicate]
    assert len(tao) == 1 and len(trung) == 1, kq
    assert (
        await pool.fetchval("SELECT count(*) FROM patient WHERE phone_primary = $1", so)
        == 1
    )


async def test_tuan_da_cong_bo_ngay_khong_ai_truc_thi_khong_dat_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    # Một tuần xa trong tương lai: công bố, bác sĩ chỉ trực thứ Hai.
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    thu2 = hom_nay + dt.timedelta(days=7 * 20 - hom_nay.weekday())
    thu5 = thu2 + dt.timedelta(days=3)
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, work_date, week_start, shift, station,"
        " staff_id, staff_name, status) VALUES ($1::uuid, $2, $3, 'FULL', 'LICH_KHAM',"
        " $4::uuid, 'BS thử', 'APPROVED')",
        CLINIC,
        thu2,
        thu2,
        ca.bac_si.staff_id,
    )
    await pool.execute(
        "INSERT INTO roster_week (clinic_id, week_start) VALUES ($1::uuid, $2)"
        " ON CONFLICT DO NOTHING",
        CLINIC,
        thu2,
    )
    pid = await _benh_nhan(pool, ca)
    bd = dt.datetime.combine(thu5, dt.time(9, 0), tzinfo=CLINIC_TZ)
    with pytest.raises(ConflictError, match="không có lịch làm việc"):
        await BookingService(pool).create(
            clinic_patient_id=pid,
            service_type_id=ca.loai_kham,
            location_id=ca.loc,
            slot_start=bd,
            slot_end=bd + dt.timedelta(minutes=15),
            identity=ca.le_tan,
            doctor_id=ca.bac_si.staff_id,
        )


async def test_khach_quen_vao_thang_bac_si_chinh(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Dây H1 "khách quen vào thẳng" — TẮT mặc định từ 25/09/2026; quản lý BẬT
    thì khách tái khám vào thẳng bác sĩ chính (mặc định: xem
    test_bo_qua_tu_van_chi_dinh_them_db)."""
    await pool.execute(
        "INSERT INTO day_nghiep_vu (clinic_id, ma, gia_tri)"
        " VALUES ($1::uuid, 'h1_khach_quen_vao_thang_bs', 'true'::jsonb)"
        " ON CONFLICT (clinic_id, ma) DO UPDATE SET gia_tri = 'true'::jsonb",
        CLINIC,
    )
    try:
        await _khach_quen_khi_bat_day(pool)
    finally:
        await pool.execute(
            "DELETE FROM day_nghiep_vu WHERE clinic_id = $1::uuid"
            " AND ma = 'h1_khach_quen_vao_thang_bs'",
            CLINIC,
        )


async def _khach_quen_khi_bat_day(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    await pool.execute(
        "UPDATE service_type SET qua_tu_van = true WHERE id = $1::uuid", ca.loai_kham
    )
    # Khách mới → qua tư vấn.
    moi = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    # Khách đánh dấu tái khám → vào thẳng bác sĩ chính.
    pid = await _benh_nhan(pool, ca)
    bd = dt.datetime.now(dt.UTC) + dt.timedelta(minutes=40)
    appt = await pool.fetchval(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status, patient_kind)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED', 'RETURN') RETURNING id::text",
        CLINIC,
        pid,
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
    quen = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    duong = {
        r["visit_id"]: r["route_decision"]
        for r in await pool.fetch(
            "SELECT visit_id::text, route_decision FROM encounter_flow"
            " WHERE visit_id = ANY($1::uuid[])",
            [moi, quen],
        )
    }
    assert duong[moi] == "TU_VAN"
    assert duong[quen] == "PRIMARY"


async def test_ke_don_phat_su_kien(pool: asyncpg.Pool) -> None:  # noqa: F811
    from clinicai.services.phieu_kham_service import PhieuKhamService

    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    ca = await _dung(pool)
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    svc = PhieuKhamService(pool, kiem_quyen=_cho_qua)
    await svc.luu_don_thuoc(
        visit_id=vid,
        dong=[
            {
                "drug_name": "Paracetamol 500mg",
                "quantity": "10 viên",
                "dosage": "2 lần/ngày",
            }
        ],
        ly_do=None,
        identity=ca.bac_si,
    )
    sk = await pool.fetch(
        "SELECT payload FROM domain_event WHERE event_type = 'prescription.saved'"
        " AND aggregate_id = $1::uuid",
        vid,
    )
    assert len(sk) == 1
    tai = sk[0]["payload"]
    tai = json.loads(tai) if isinstance(tai, str) else tai
    assert tai["so_dong_them"] == 1 and tai["so_dong"] == 1


async def test_vang_lai_tu_check_in_phat_khach_da_toi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    cu = await pool.fetchval("SELECT settings FROM clinic WHERE id = $1::uuid", CLINIC)
    # Mở cửa + ca làm việc phủ cả ngày để bài kiểm không phụ thuộc giờ chạy.
    await pool.execute(
        "UPDATE clinic SET settings = settings"
        " || jsonb_build_object('ca_lam_viec', $2::jsonb)"
        " || jsonb_build_object('hours', (SELECT jsonb_object_agg(k, $3::jsonb)"
        "    FROM jsonb_object_keys(settings -> 'hours') k))"
        " WHERE id = $1::uuid",
        CLINIC,
        json.dumps(
            {
                "SANG": {"bat_dau": "00:00", "ket_thuc": "08:00"},
                "CHIEU": {"bat_dau": "08:00", "ket_thuc": "16:00"},
                "TOI": {"bat_dau": "16:00", "ket_thuc": "23:59"},
            }
        ),
        json.dumps({"open": "00:00", "close": "23:59"}),
    )
    try:
        pid = await _benh_nhan(pool, ca)
        bd = dt.datetime.now(CLINIC_TZ).replace(second=0, microsecond=0)
        bd = bd - dt.timedelta(minutes=bd.minute % 15)
        # Như lễ tân: khung đầy chỗ vãng lai thì sang khung kế tiếp.
        for lan in range(12):
            try:
                kq = await BookingService(pool).create(
                    clinic_patient_id=pid,
                    service_type_id=ca.loai_kham,
                    location_id=ca.loc,
                    slot_start=bd + dt.timedelta(minutes=15 * lan),
                    slot_end=bd + dt.timedelta(minutes=15 * lan + 15),
                    identity=ca.le_tan,
                    booking_channel="WALK_IN",
                )
                break
            except ConflictError:
                continue
        else:
            pytest.fail("không còn khung vãng lai nào trong 3 giờ tới")
    finally:
        await pool.execute(
            "UPDATE clinic SET settings = $2::jsonb WHERE id = $1::uuid", CLINIC, cu
        )
    appt = str(kq.get("id") or kq.get("appointment_id") or kq["appointment"]["id"])
    vid = await pool.fetchval(
        "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid", appt
    )
    assert vid is not None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'visit.checked_in'"
            " AND aggregate_id = $1::uuid",
            vid,
        )
        == 1
    )
    await chay_hanh_trinh(pool)
    assert await pool.fetchval(
        "SELECT route_decision FROM encounter_flow WHERE visit_id = $1::uuid", vid
    )


def test_khoa_ngoai_sai_tra_422_khong_500() -> None:
    from fastapi.testclient import TestClient

    from clinicai.main import app

    @app.get("/__thu_khoa_ngoai")
    async def _no() -> None:
        raise asyncpg.exceptions.ForeignKeyViolationError("fk")

    try:
        r = TestClient(app, raise_server_exceptions=False).get("/__thu_khoa_ngoai")
    finally:
        app.router.routes.pop()
    assert r.status_code == 422
    assert r.json()["error"] == "VALIDATION_ERROR"


async def test_truong_ca_duoc_bao_khong_phong_nao_o_co_so_nay_lam_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phòng làm được bước này chỉ có ở CƠ SỞ KHÁC → vẫn phải báo 'không phòng'."""
    import clinicai.services.luot_kham_doc as lkd

    async def _cho_qua(*_a: object, **_k: object) -> None:
        return None

    # 7a (27/09): xem điều phối hỏi lego Điều phối khách — bài này đo luật PHÒNG,
    # không đo quyền; trưởng ca giả không có dòng lego trong DB thử.
    monkeypatch.setattr(lkd, "doi_quyen", _cho_qua)
    from clinicai.api.identity import ClinicRole, StaffIdentity
    from clinicai.services.luot_kham_doc import BangLuotKham
    from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
        _kham_va_chi_dinh,
    )

    ca = await _dung(pool)
    khac = await _co_so_khac(pool, ca.loc)
    ma = f"NODE-THU-{uuid.uuid4().hex[:6]}"
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO node_definition SELECT (jsonb_populate_record("
            " NULL::node_definition,"
            " to_jsonb(n) || jsonb_build_object('code', $3::text,"
            " 'id', gen_random_uuid())"
            ")).* FROM node_definition n WHERE n.clinic_id = $1::uuid AND n.code = $2",
            CLINIC,
            NODE,
            ma,
        )
        phong_khac = await conn.fetchval(
            "INSERT INTO clinic_room (clinic_id, location_id, code, name, node_code,"
            " is_active, accepting, sort) VALUES ($1::uuid, $2::uuid, $3,"
            " 'Chỉ ở cơ sở khác', $4, true, true, 0) RETURNING id::text",
            CLINIC,
            khac,
            f"CSK-{uuid.uuid4().hex[:6]}",
            ma,
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong_khac,
            ma,
        )
    vid = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _, don = await _kham_va_chi_dinh(pool, ca, vid)
    await pool.execute(
        "UPDATE service_order SET node_code = $2 WHERE id = $1::uuid", don, ma
    )
    truong_ca = StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Trưởng ca thử",
        department=ClinicRole.TRUONG_CA.value,
        role=ClinicRole.TRUONG_CA,
        clinic_id=CLINIC,
        location_id=ca.loc,
        location_name="x",
    )
    kq = await BangLuotKham(pool).chi_dinh_hom_nay(identity=truong_ca)
    dong = next(d for d in kq["chi_dinh"] if d["id"] == don)
    assert dong["khong_co_phong"] is True


async def test_cong_bo_lich_truc_bac_si_nghi_thi_chuong_cskh_va_truong_ca(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Tuyền chốt 24/09/2026: lịch mất bác sĩ sau công bố phải có chuông riêng."""
    from clinicai.services.config_service import RosterService

    ca = await _dung(pool)
    hom_nay = dt.datetime.now(CLINIC_TZ).date()
    tuan = 30 + uuid.uuid4().int % 400
    thu2 = hom_nay + dt.timedelta(days=7 * tuan - hom_nay.weekday())
    thu5 = thu2 + dt.timedelta(days=3)
    await pool.execute(
        "INSERT INTO work_roster (clinic_id, work_date, week_start, shift, station,"
        " staff_id, staff_name, status) VALUES ($1::uuid, $2, $2, 'FULL',"
        " 'LICH_KHAM', $3::uuid, 'BS thử', 'APPROVED')",
        CLINIC,
        thu2,
        ca.bac_si.staff_id,
    )
    bd = dt.datetime.combine(thu5, dt.time(9, 0), tzinfo=CLINIC_TZ)
    await pool.execute(
        "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
        " service_type_id, slot_start, slot_end, doctor_id, status)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::uuid,"
        " 'CONFIRMED')",
        CLINIC,
        await _benh_nhan(pool, ca),
        ca.loc,
        ca.loai_kham,
        bd,
        bd + dt.timedelta(minutes=15),
        ca.bac_si.staff_id,
    )
    await RosterService(pool).apply_week(week_start=thu2, identity=ca.le_tan)
    chuong = await pool.fetch(
        "SELECT vai_nhan, tieu_de FROM thong_bao WHERE clinic_id = $1::uuid"
        " AND nguon = 'lich_mat_bac_si' AND nguon_id LIKE $2",
        CLINIC,
        f"{thu2.isoformat()}:%",
    )
    assert {r["vai_nhan"] for r in chuong} == {"CSKH", "TRUONG_CA"}
    assert all("1 lịch hẹn mất bác sĩ" in r["tieu_de"] for r in chuong)
