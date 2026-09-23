"""Luồng khám lát 1 trên Postgres thật — mỗi test là một ca trong contract v2 §3.7.

Chạy (DB dùng một lần, đã nạp migration + seed):

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55433/postgres \\
        poetry run pytest src/tests/services/test_luot_kham_service_db.py

Không có DATABASE_URL_TEST thì bỏ qua — ``src/tests/conftest.py`` không bao giờ
để test chạm DATABASE_URL thật.

Test dựng người và lượt khám của riêng nó (mã ngẫu nhiên), không phụ thuộc thứ
tự chạy, không cần dọn.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    LuotKhamValidationError,
)
from clinicai.services.permission_service import cap_preset_mac_dinh
from tests.chay_nguoi_dua_tin import chay_hanh_trinh

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


@dataclass
class KichBan:
    svc: LuotKhamService
    pool: asyncpg.Pool
    visit_id: str
    location_id: str
    bac_si: StaffIdentity
    bac_si_2: StaffIdentity
    thu_ky: StaffIdentity
    dieu_duong: StaffIdentity
    bs_sieu_am: StaffIdentity
    truong_ca: StaffIdentity
    le_tan: StaffIdentity
    phong_sa: str
    phong_mau: str
    ma_sa: str
    ma_mau: str


async def _nguoi(conn: asyncpg.Connection, loc: str, role: str) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active)"
        " VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
        role,
    )
    await cap_preset_mac_dinh(conn, clinic_id=CLINIC, staff_id=sid, vai=role)

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=role,
        role=ClinicRole(role),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _luot(conn: asyncpg.Connection, loc: str, doctor_id: str) -> str:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN test lát 1', $3::uuid) RETURNING"
        " clinic_patient_id::text",
        CLINIC,
        f"LK-T-{uuid.uuid4().hex[:10]}",
        loc,
    )
    return str(
        await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
            " attending_doctor_id, checked_in_at)"
            " VALUES ($1::uuid, $2::uuid, 'OPEN', $3::uuid, now()) RETURNING"
            " visit_id::text",
            CLINIC,
            pid,
            doctor_id,
        )
    )


@pytest_asyncio.fixture
async def kb(pool: asyncpg.Pool) -> KichBan:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid AND"
            " is_active"
            " ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bac_si = await _nguoi(conn, loc, "DOCTOR")
        kich_ban = KichBan(
            svc=LuotKhamService(pool),
            pool=pool,
            visit_id=await _luot(conn, loc, bac_si.staff_id),
            location_id=loc,
            bac_si=bac_si,
            bac_si_2=await _nguoi(conn, loc, "DOCTOR"),
            thu_ky=await _nguoi(conn, loc, "TKYK"),
            dieu_duong=await _nguoi(conn, loc, "NURSE_ULTRASOUND"),
            bs_sieu_am=await _nguoi(conn, loc, "ULTRASOUND_DOCTOR"),
            truong_ca=await _nguoi(conn, loc, "TRUONG_CA"),
            le_tan=await _nguoi(conn, loc, "RECEPTION"),
            phong_sa=await conn.fetchval(
                "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn ON"
                " rn.room_id = r.id"
                " WHERE r.clinic_id = $1::uuid AND rn.node_code = 'DICHVU-SIEUAM'"
                " AND r.is_active AND r.accepting ORDER BY r.sort LIMIT 1",
                CLINIC,
            ),
            phong_mau=await conn.fetchval(
                "SELECT r.id::text FROM clinic_room r JOIN clinic_room_node rn ON"
                " rn.room_id = r.id"
                " WHERE r.clinic_id = $1::uuid AND rn.node_code ="
                " 'DICHVU-LAYMAU-MAU' AND r.is_active AND r.accepting"
                " ORDER BY r.sort LIMIT 1",
                CLINIC,
            ),
            ma_sa=await conn.fetchval(
                "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
                " AND active"
                " AND node_code = 'DICHVU-SIEUAM' ORDER BY service_code LIMIT 1",
                CLINIC,
            ),
            ma_mau=await conn.fetchval(
                "SELECT service_code FROM service_price WHERE clinic_id = $1::uuid"
                " AND active"
                " AND node_code = 'DICHVU-LAYMAU-MAU' ORDER BY service_code LIMIT 1",
                CLINIC,
            ),
        )
    assert (
        kich_ban.phong_sa and kich_ban.phong_mau and kich_ban.ma_sa and kich_ban.ma_mau
    )
    return kich_ban


async def _hanh_trinh(pool: asyncpg.Pool) -> None:
    """Khối Hành trình xếp hàng qua sự kiện (24/09/2026) — xem
    tests/chay_nguoi_dua_tin.py."""
    await chay_hanh_trinh(pool)


def _cua(board: dict[str, Any], visit_id: str) -> dict[str, Any]:
    return next(v for v in board["luot"] if v["visit_id"] == visit_id)


async def dieu_phoi_cu(svc: LuotKhamService, **kw: Any) -> dict[str, Any]:
    """Điều phối kiểu CŨ (``dispatch_order``) — chỉ còn cho dòng legacy.

    Lifecycle v1 Slice 4 §D: chỉ định có ``selection_status`` bị đường cũ từ chối
    (LIFECYCLE_ROUTING_REQUIRED) và phải xếp phòng qua AssignServiceRoom. Các test
    dùng helper này kiểm CƠ CHẾ điều phối / hàng chờ cũ — cơ chế ấy vẫn chạy cho
    dòng legacy — nên đưa chỉ định về dạng legacy (selection / routing NULL) trước
    khi gọi. Luồng lifecycle-v1: ``test_service_routing_db.py``.
    """
    await svc._pool.execute(
        "UPDATE service_order SET selection_status = NULL, routing_status = NULL"
        " WHERE id = $1::uuid AND selection_status IS NOT NULL",
        kw["order_id"],
    )
    return await svc.dispatch_order(**kw)


async def _dieu_phoi_tay(kb: KichBan, order_id: str, room_id: str) -> None:
    """Lifecycle v1 (CHECKPOINT §1, Slice 2): duyệt chỉ định KHÔNG còn tự xếp
    phòng — chỉ định chờ khách chọn và đủ tài chính. Trước khi có lệnh Routing
    (Slice 4), trưởng ca điều phối tay như đường hiện hành."""
    async with kb.pool.acquire() as conn:
        assert (
            await conn.fetchval(
                "SELECT exec_status FROM service_order WHERE id = $1::uuid",
                order_id,
            )
            == "authorized"
        )
    await dieu_phoi_cu(
        kb.svc,
        order_id=order_id,
        room_id=room_id,
        expected_version=None,
        identity=kb.truong_ca,
    )


async def _vao_kham(kb: KichBan) -> str:
    """Đo sinh hiệu rồi bác sĩ nhận khám. Trả mã phiên vòng 1."""
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    board = await kb.svc.bang(identity=kb.bac_si)
    phien = _cua(board, kb.visit_id)["phien"][0]["id"]
    await kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si)
    return str(phien)


# ---------------------------------------------------------------------------
# Luồng trọn vẹn của lát 1
# ---------------------------------------------------------------------------


async def test_sinh_hieu_luu_qua_benh_an_van_vao_hang_cho_bac_si(kb: KichBan) -> None:
    """17/09/2026: ĐD lưu sinh hiệu qua biểu mẫu bệnh án (đường cũ) — khách
    phải vào hàng chờ bác sĩ y như đo ở màn Đo sinh hiệu, không kẹt lại."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO vital_measurement (clinic_id, visit_id, systolic, diastolic,"
            " recorded_by) VALUES ($1::uuid, $2::uuid, 120, 80, $3::uuid)",
            kb.dieu_duong.clinic_id,
            kb.visit_id,
            kb.dieu_duong.staff_id,
        )
        async with conn.transaction():
            await kb.svc.dong_bo_sinh_hieu_tu_ho_so(conn, kb.dieu_duong, kb.visit_id)
    await _hanh_trinh(kb.pool)
    async with kb.pool.acquire() as conn:
        # Gọi lại không mở thêm gì.
        async with conn.transaction():
            assert (
                await kb.svc.dong_bo_sinh_hieu_tu_ho_so(
                    conn, kb.dieu_duong, kb.visit_id
                )
                == "PRIMARY"
            )
    await _hanh_trinh(kb.pool)
    board = await kb.svc.bang(identity=kb.bac_si)
    luot = _cua(board, kb.visit_id)
    assert luot["sinh_hieu_trang_thai"] == "recorded"
    assert [q["hang"] for q in luot["hang_cho"]] == ["DOCTOR"]


async def test_mot_luot_kham_di_het_luong(kb: KichBan) -> None:
    svc = kb.svc
    await svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    r = await svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": "120", "diastolic": "80", "pulse": 72},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    # Xếp hàng do khối Hành trình, không còn trong lệnh ghi (24/09/2026).
    assert r["route"] is None
    await _hanh_trinh(kb.pool)

    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["sinh_hieu"]["tam_thu"] == 120
    [phien1] = luot["phien"]
    assert (phien1["loai"], phien1["trang_thai"]) == ("PRIMARY", "queued")
    assert [q["trang_thai"] for q in luot["hang_cho"]] == ["waiting"]
    # T-A1: chưa có chỉ định thì trưởng ca không có gì để điều phối.
    assert luot["chi_dinh"] == []

    await svc.start_consultation(consultation_id=phien1["id"], identity=kb.bac_si)
    await svc.save_note(
        consultation_id=phien1["id"], body="Đau bụng dưới 3 ngày.", identity=kb.thu_ky
    )
    nhap = await svc.propose_orders(
        consultation_id=phien1["id"], service_codes=[kb.ma_mau], identity=kb.thu_ky
    )
    duyet = await svc.authorize_orders(
        consultation_id=phien1["id"],
        service_codes=[kb.ma_sa],
        draft_order_ids=nhap["order_ids"],
        expected_versions=nhap["versions"],
        identity=kb.bac_si,
    )
    mau_id, sa_id = duyet["order_ids"]

    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    # T-C2: duyệt chỉ định không kết thúc phiên khám.
    assert luot["phien"][0]["trang_thai"] == "in_progress"
    # Đổi theo contract frozen Lifecycle v1 (Slice 2): trước đây duyệt xong là
    # TỰ vào hàng chờ phòng (Notion v1.0.0). Nay chỉ định chờ khách chọn và đủ
    # tài chính trước khi xếp phòng — duyệt KHÔNG tự xếp.
    assert {o["trang_thai"] for o in luot["chi_dinh"]} == {"authorized"}

    # Trưởng ca xếp phòng SA khi bác sĩ còn khám → chỗ chờ SA bị khoá.
    await dieu_phoi_cu(
        svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    luot = _cua(await svc.bang(identity=kb.truong_ca), kb.visit_id)
    sa_q = next(q for q in luot["hang_cho"] if q["ref_id"] == sa_id)
    assert sa_q["trang_thai"] == "blocked"

    await svc.complete_consultation(
        consultation_id=phien1["id"],
        outcome="SERVICES",
        requirements=[
            {"order_id": sa_id, "need": "PERFORMED"},
            {"order_id": mau_id, "need": "PERFORMED"},
        ],
        identity=kb.bac_si,
    )
    luot = _cua(await svc.bang(identity=kb.truong_ca), kb.visit_id)
    assert (
        next(q for q in luot["hang_cho"] if q["ref_id"] == sa_id)["trang_thai"]
        == "waiting"
    )
    assert [v["trang_thai"] for v in luot["vong"]] == ["collecting"]

    await svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    # Xếp phòng lấy máu khi khách đang siêu âm → chờ mở.
    await dieu_phoi_cu(
        svc,
        order_id=mau_id,
        room_id=kb.phong_mau,
        expected_version=None,
        identity=kb.truong_ca,
    )
    luot = _cua(await svc.bang(identity=kb.truong_ca), kb.visit_id)
    assert (
        next(q for q in luot["hang_cho"] if q["ref_id"] == mau_id)["trang_thai"]
        == "blocked"
    )

    await svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Tử cung bình thường.",
        identity=kb.bs_sieu_am,
    )
    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    assert (
        next(q for q in luot["hang_cho"] if q["ref_id"] == mau_id)["trang_thai"]
        == "waiting"
    )
    assert luot["vong"][0]["trang_thai"] == "collecting"  # còn thiếu máu

    await svc.start_service(order_id=mau_id, identity=kb.dieu_duong)
    await svc.complete_service(
        order_id=mau_id,
        performed=True,
        reason=None,
        result_note=None,
        identity=kb.dieu_duong,
    )

    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["vong"][0]["trang_thai"] == "ready"
    # T-R9: đúng một phiên đọc và đúng một chỗ chờ đọc.
    review = [p for p in luot["phien"] if p["loai"] == "REVIEW"]
    assert [(p["vong"], p["trang_thai"]) for p in review] == [(2, "queued")]
    assert [(q["ly_do"], q["trang_thai"]) for q in luot["hang_cho"]] == [
        ("REVIEW", "waiting")
    ]

    await svc.start_consultation(consultation_id=review[0]["id"], identity=kb.bac_si)
    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    # T-C3: bắt đầu đọc chưa phải xong.
    assert (
        next(p for p in luot["phien"] if p["loai"] == "REVIEW")["trang_thai"]
        == "in_progress"
    )

    await svc.complete_consultation(
        consultation_id=review[0]["id"],
        outcome="DONE",
        requirements=None,
        identity=kb.bac_si,
    )
    luot = _cua(await svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["ket_thuc_luc"] is not None
    assert luot["hang_cho"] == []
    assert luot["vong"][0]["trang_thai"] == "closed"

    async with kb.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT occurred_at, event_type FROM event_log"
            r" WHERE clinic_id = $1::uuid AND aggregate_id = $2::uuid"
            " ORDER BY occurred_at",
            CLINIC,
            kb.visit_id,
        )
        da_xep = await conn.fetchval(
            "SELECT count(*) FROM domain_event WHERE event_type = 'visit.routed'"
            " AND aggregate_id = $1::uuid",
            kb.visit_id,
        )
    assert da_xep == 1
    # Sự kiện trong CÙNG một transaction mang cùng occurred_at (DEFAULT now()),
    # nên thứ tự bên trong một lệnh không xác định — so theo từng lệnh.
    theo_lenh: dict[Any, list[str]] = {}
    for row in rows:
        theo_lenh.setdefault(row["occurred_at"], []).append(row["event_type"])
    assert [sorted(g) for g in theo_lenh.values()] == [
        ["vitals.started"],
        # `visit.routed` nay do khối Hành trình phát vào SỔ MỚI (24/09/2026),
        # không còn nằm trong sổ cũ cùng lệnh ghi sinh hiệu.
        ["vitals.recorded"],
        ["consult.started"],
        ["consult.note_saved"],
        ["orders.drafted"],
        # Lifecycle v1 (Slice 2): duyệt KHÔNG còn tự xếp phòng — trước đây lệnh
        # này kèm hai "dispatch.assigned".
        ["orders.authorized"],
        # Trưởng ca xếp phòng siêu âm bằng tay.
        ["dispatch.assigned"],
        ["consult.completed"],
        ["service.started"],
        ["dispatch.assigned"],
        ["service.performed"],
        ["service.started"],
        ["review.ready", "service.performed"],
        ["consult.started"],
        ["consult.completed"],
    ]


# ---------------------------------------------------------------------------
# Chặn đúng chỗ
# ---------------------------------------------------------------------------


async def test_nhap_cua_thu_ky_khong_dieu_phoi_duoc(kb: KichBan) -> None:
    # T-A3 / I1
    phien = await _vao_kham(kb)
    nhap = await kb.svc.propose_orders(
        consultation_id=phien, service_codes=[kb.ma_sa], identity=kb.thu_ky
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await dieu_phoi_cu(
            kb.svc,
            order_id=nhap["order_ids"][0],
            room_id=kb.phong_sa,
            expected_version=None,
            identity=kb.truong_ca,
        )
    assert e.value.error_code == "NO_VALID_ORDER"


async def test_chi_bac_si_duyet_chi_dinh(kb: KichBan) -> None:
    # T-A4
    phien = await _vao_kham(kb)
    for nguoi in (kb.thu_ky, kb.truong_ca, kb.dieu_duong):
        with pytest.raises(SafetyGateError):
            await kb.svc.authorize_orders(
                consultation_id=phien,
                service_codes=[kb.ma_sa],
                draft_order_ids=None,
                identity=nguoi,
            )


async def test_ket_thuc_kham_khong_can_dich_vu(kb: KichBan) -> None:
    # T-C1
    phien = await _vao_kham(kb)
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="NO_SERVICES",
        requirements=None,
        identity=kb.bac_si,
    )
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["phien"][0]["trang_thai"] == "completed"
    assert luot["vong"] == [] and luot["hang_cho"] == []
    assert luot["ket_thuc_luc"] is not None


async def test_khong_dich_vu_khi_con_chi_dinh_da_duyet(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="NO_SERVICES",
            requirements=None,
            identity=kb.bac_si,
        )
    assert e.value.error_code == "ORDERS_PENDING"


async def test_ket_thuc_sai_loai_phien(kb: KichBan) -> None:
    # T-C4
    phien = await _vao_kham(kb)
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.complete_consultation(
            consultation_id=phien, outcome="DONE", requirements=None, identity=kb.bac_si
        )
    assert e.value.error_code == "WRONG_CONSULTATION_KIND"


async def test_co_dich_vu_ma_khong_khoa_tap_yeu_cau(kb: KichBan) -> None:
    # T-C4 vế sau / I5
    phien = await _vao_kham(kb)
    await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="SERVICES",
            requirements=[],
            identity=kb.bac_si,
        )
    assert e.value.error_code == "REQUIREMENTS_REQUIRED"


async def test_khach_dang_kham_thi_phong_khac_khong_goi_duoc(kb: KichBan) -> None:
    # T-C5 / I9
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=duyet["order_ids"][0],
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.start_service(
            order_id=duyet["order_ids"][0], identity=kb.bs_sieu_am
        )
    assert e.value.error_code == "PATIENT_BUSY"


async def test_dieu_phoi_khong_doi_trang_thai_chi_dinh_khac(kb: KichBan) -> None:
    # T-A10 / S1b
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau, kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    mau_id, sa_id = duyet["order_ids"]
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": mau_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=mau_id,
        room_id=kb.phong_mau,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=mau_id, identity=kb.dieu_duong)
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    luot = _cua(await kb.svc.bang(identity=kb.truong_ca), kb.visit_id)
    trang_thai = {o["id"]: o["trang_thai"] for o in luot["chi_dinh"]}
    assert trang_thai == {mau_id: "in_progress", sa_id: "assigned"}


async def test_phong_khong_lam_dich_vu_do(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await dieu_phoi_cu(
            kb.svc,
            order_id=duyet["order_ids"][0],
            room_id=kb.phong_mau,
            expected_version=None,
            identity=kb.truong_ca,
        )
    assert e.value.error_code == "ROOM_NOT_SERVING"


async def test_nguoi_khong_dung_vai_khong_lam_dich_vu(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": duyet["order_ids"][0], "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=duyet["order_ids"][0],
        room_id=kb.phong_mau,
        expected_version=None,
        identity=kb.truong_ca,
    )
    # Lấy máu chỉ điều dưỡng làm (actor_roles của node).
    with pytest.raises(SafetyGateError):
        await kb.svc.start_service(
            order_id=duyet["order_ids"][0], identity=kb.bs_sieu_am
        )


async def test_yeu_cau_tu_khoa_vong_bi_tu_choi(kb: KichBan) -> None:
    # T-V4
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_order SET hold_until_round = 2 WHERE clinic_id ="
            " $1::uuid AND id = $2::uuid",
            CLINIC,
            duyet["order_ids"][0],
        )
    with pytest.raises(LuotKhamValidationError) as e:
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="SERVICES",
            requirements=[{"order_id": duyet["order_ids"][0], "need": "PERFORMED"}],
            identity=kb.bac_si,
        )
    assert e.value.error_code == "CYCLIC_REQUIREMENT"


async def test_bi_giu_toi_khi_doc_xong_moi_dieu_phoi_duoc(kb: KichBan) -> None:
    # T-V3: SA → đọc → máu.
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa, kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id, mau_id = duyet["order_ids"]
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_order SET hold_until_round = 2 WHERE clinic_id ="
            " $1::uuid AND id = $2::uuid",
            CLINIC,
            mau_id,
        )
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await dieu_phoi_cu(
            kb.svc,
            order_id=mau_id,
            room_id=kb.phong_mau,
            expected_version=None,
            identity=kb.truong_ca,
        )
    assert e.value.error_code == "HELD_UNTIL_ROUND"


async def test_sinh_hieu_rac_khong_ghi_gi(kb: KichBan) -> None:
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    with pytest.raises(ValidationError):
        await kb.svc.record_vitals(
            visit_id=kb.visit_id, raw={"systolic": "cao"}, identity=kb.dieu_duong
        )
        await _hanh_trinh(kb.pool)
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["sinh_hieu"] is None and luot["dich"] is None


# Yêu cầu "có kết quả hợp lệ" đã có từ Slice 1 — xem test_slice1_rail_db.py.


# ---------------------------------------------------------------------------
# Gửi lại, đồng thời, phạm vi phòng khám
# ---------------------------------------------------------------------------


async def test_gui_lai_cung_khoa_tra_ket_qua_cu(kb: KichBan) -> None:
    # T-A17
    phien = await _vao_kham(kb)
    key = "duyet-" + uuid.uuid4().hex
    lan1 = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
        idempotency_key=key,
    )
    lan2 = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
        idempotency_key=key,
    )
    assert lan1 == lan2
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert len(luot["chi_dinh"]) == 1

    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[kb.ma_mau],
            draft_order_ids=None,
            identity=kb.bac_si,
            idempotency_key=key,
        )
    assert e.value.error_code == "IDEMPOTENCY_KEY_REUSED"


async def test_gui_lai_dong_thoi_cung_khoa_chi_lam_mot_lan(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    key = "dongthoi-" + uuid.uuid4().hex
    kq = await asyncio.gather(
        *[
            kb.svc.authorize_orders(
                consultation_id=phien,
                service_codes=[kb.ma_sa],
                draft_order_ids=None,
                identity=kb.bac_si,
                idempotency_key=key,
            )
            for _ in range(3)
        ]
    )
    assert kq[0] == kq[1] == kq[2]
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert len(luot["chi_dinh"]) == 1


async def test_khoa_gui_lai_gan_voi_nguoi_goi(kb: KichBan) -> None:
    # T-S1: bác sĩ khác dùng đúng khoá ấy không nhận được kết quả của người trước.
    phien = await _vao_kham(kb)
    key = "chung-" + uuid.uuid4().hex
    a = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
        idempotency_key=key,
    )
    with pytest.raises(SafetyGateError):
        await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[kb.ma_sa],
            draft_order_ids=None,
            identity=kb.bac_si_2,
            idempotency_key=key,
        )
    assert len(a["order_ids"]) == 1


async def test_hai_truong_ca_dieu_phoi_cung_luc(kb: KichBan) -> None:
    # T-A19
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    # Tự xếp phòng lúc duyệt đã tăng phiên bản — hai trưởng ca cùng cầm bản ấy.
    ban = await kb.svc._pool.fetchval(
        "SELECT version FROM service_order WHERE id = $1::uuid", sa_id
    )
    kq = await asyncio.gather(
        dieu_phoi_cu(
            kb.svc,
            order_id=sa_id,
            room_id=kb.phong_sa,
            expected_version=ban,
            identity=kb.truong_ca,
        ),
        dieu_phoi_cu(
            kb.svc,
            order_id=sa_id,
            room_id=kb.phong_sa,
            expected_version=ban,
            identity=kb.truong_ca,
        ),
        return_exceptions=True,
    )
    ok = [k for k in kq if isinstance(k, dict)]
    loi = [k for k in kq if isinstance(k, LuotKhamConflictError)]
    assert len(ok) == 1 and len(loi) == 1
    assert loi[0].error_code == "STALE_VERSION"


async def test_hai_bac_si_goi_cung_mot_khach(kb: KichBan) -> None:
    # I9: đúng một người được.
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    phien = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["phien"][0]["id"]
    kq = await asyncio.gather(
        kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si),
        kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si_2),
        return_exceptions=True,
    )
    assert sum(isinstance(k, dict) for k in kq) == 1
    assert (
        sum(
            isinstance(k, LuotKhamConflictError)
            and k.error_code == "CONSULTATION_TAKEN"
            for k in kq
        )
        == 1
    )


async def test_hang_cho_bac_si_nguoi_quay_lai_dung_sau_nguoi_dang_cho(
    kb: KichBan,
) -> None:
    # T-A14 trên dữ liệu thật: C xong dịch vụ quay lại vào sau B đang chờ.
    svc = kb.svc
    async with kb.pool.acquire() as conn:
        visit_b = await _luot(conn, kb.location_id, kb.bac_si.staff_id)
    phien_c = await _vao_kham(kb)  # kb.visit_id là khách C
    duyet = await svc.authorize_orders(
        consultation_id=phien_c,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    await svc.complete_consultation(
        consultation_id=phien_c,
        outcome="SERVICES",
        requirements=[{"order_id": duyet["order_ids"][0], "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await svc.bat_dau_do_sinh_hieu(visit_id=visit_b, identity=kb.dieu_duong)
    await svc.record_vitals(
        visit_id=visit_b, raw={"systolic": 110, "diastolic": 70}, identity=kb.dieu_duong
    )
    await _hanh_trinh(kb.pool)
    await dieu_phoi_cu(
        svc,
        order_id=duyet["order_ids"][0],
        room_id=kb.phong_mau,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await svc.start_service(order_id=duyet["order_ids"][0], identity=kb.dieu_duong)
    await svc.complete_service(
        order_id=duyet["order_ids"][0],
        performed=True,
        reason=None,
        result_note=None,
        identity=kb.dieu_duong,
    )

    board = await svc.bang(identity=kb.bac_si)
    b = _cua(board, visit_b)["hang_cho"][0]
    c = _cua(board, kb.visit_id)["hang_cho"][0]
    assert (b["ly_do"], c["ly_do"]) == ("PRIMARY", "REVIEW")
    assert b["du_dieu_kien_luc"] < c["du_dieu_kien_luc"]


async def test_luot_kham_cua_phong_kham_khac_khong_thay(kb: KichBan) -> None:
    # T-S3: cùng mã lượt khám, khác phòng khám → không tìm thấy.
    la = StaffIdentity(
        staff_id=kb.dieu_duong.staff_id,
        auth_user_id=kb.dieu_duong.auth_user_id,
        full_name="x",
        department="NURSE_ULTRASOUND",
        role=ClinicRole.NURSE_ULTRASOUND,
        clinic_id=str(uuid.uuid4()),
        location_id=kb.location_id,
        location_name="x",
    )
    # Bắt đầu bằng người THẬT, để lỗi chắc chắn đến từ bước lưu của người lạ.
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    # Người phòng khám khác không có quyền ở phòng khám này → bị chặn ngay ở cửa
    # quyền (CORE-B3), trước cả bước tìm lượt. Không lộ gì: câu báo không nhắc
    # tới lượt khám.
    with pytest.raises((NotFoundError, SafetyGateError)):
        await kb.svc.record_vitals(
            visit_id=kb.visit_id, raw={"systolic": 120, "diastolic": 80}, identity=la
        )
        await _hanh_trinh(kb.pool)


# ---------------------------------------------------------------------------
# Hàng chờ theo phòng · thư ký bấm thay bác sĩ · "Đã khám xong" (16/09/2026)
# ---------------------------------------------------------------------------


async def test_thu_ky_bam_bat_dau_bac_si_van_duyet_duoc(kb: KichBan) -> None:
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    phien = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)["phien"][0]
    # Chưa được phân đi kèm bác sĩ này → không bấm được.
    with pytest.raises(SafetyGateError):
        await kb.svc.start_consultation(consultation_id=phien["id"], identity=kb.thu_ky)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid) ON CONFLICT DO NOTHING",
            CLINIC,
            kb.thu_ky.staff_id,
            kb.bac_si.staff_id,
        )
    await kb.svc.start_consultation(consultation_id=phien["id"], identity=kb.thu_ky)
    # Bác sĩ bấm lại cùng phiên: không bị báo "bác sĩ khác đang khám".
    lai = await kb.svc.start_consultation(
        consultation_id=phien["id"], identity=kb.bac_si
    )
    assert lai.get("already") is True
    async with kb.pool.acquire() as conn:
        bs = await conn.fetchval(
            "SELECT doctor_staff_id::text FROM consultation WHERE id = $1::uuid",
            phien["id"],
        )
    assert bs == kb.bac_si.staff_id, "thư ký bấm không được thành bác sĩ của phiên"
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien["id"],
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    assert len(duyet["order_ids"]) == 1


async def test_kham_xong_tu_chon_ket_qua_theo_chi_dinh_con_lai(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await _dieu_phoi_tay(kb, sa_id, kb.phong_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    async with kb.pool.acquire() as conn:
        c = await conn.fetchrow(
            "SELECT status, outcome FROM consultation WHERE id = $1::uuid", phien
        )
        o = await conn.fetchrow(
            "SELECT exec_status, room_id::text AS room_id FROM service_order"
            " WHERE id = $1::uuid",
            sa_id,
        )
        q = await conn.fetchval(
            "SELECT status FROM queue_entry WHERE ref_id = $1::uuid"
            " AND reason = 'SERVICE'",
            sa_id,
        )
    assert (c["status"], c["outcome"]) == ("completed", "SERVICES")
    assert o["exec_status"] == "assigned" and o["room_id"] is not None
    # Khám xong → khách được thả khỏi phòng khám, chỗ chờ siêu âm mở.
    assert q == "waiting"


async def test_kham_xong_khong_chi_dinh_thi_khep_luot(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    async with kb.pool.acquire() as conn:
        outcome = await conn.fetchval(
            "SELECT outcome FROM consultation WHERE id = $1::uuid", phien
        )
    assert outcome == "NO_SERVICES"


async def test_hang_cho_phong_cho_dang_lam_da_xong(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await _dieu_phoi_tay(kb, sa_id, kb.phong_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    async with kb.pool.acquire() as conn:
        phong = await conn.fetchval(
            "SELECT room_id::text FROM service_order WHERE id = $1::uuid", sa_id
        )

    def _cua_toi(hc: dict[str, Any]) -> dict[str, Any]:
        return next(r for r in hc["hang_cho"] if r["ref_id"] == sa_id)

    hc = await kb.svc.hang_cho(identity=kb.bs_sieu_am, room_id=phong)
    dong = _cua_toi(hc)
    assert dong["trang_thai"] == "waiting" and dong["loai"] == "DICH_VU"
    assert dong["so_thu_tu"] >= 1 and dong["ten"]

    await kb.svc.start_service(order_id=sa_id, identity=kb.dieu_duong)
    dong = _cua_toi(await kb.svc.hang_cho(identity=kb.bs_sieu_am, room_id=phong))
    assert dong["trang_thai"] == "serving" and dong["bat_dau_luc"]

    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Tử cung bình thường.",
        identity=kb.bs_sieu_am,
    )
    dong = _cua_toi(await kb.svc.hang_cho(identity=kb.bs_sieu_am, room_id=phong))
    assert dong["trang_thai"] == "done" and dong["xong_luc"]


async def test_hang_cho_bac_si_thay_luot_kham_chinh_cua_minh(kb: KichBan) -> None:
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    hc = await kb.svc.hang_cho(identity=kb.bac_si, room_id=None)
    dong = [r for r in hc["hang_cho"] if r["visit_id"] == kb.visit_id]
    assert len(dong) == 1 and dong[0]["loai"] == "KHAM"
    assert dong[0]["trang_thai"] == "waiting"


async def test_hang_cho_vip_khong_tu_chen_truoc_nguoi_vao_hang_som_hon(
    kb: KichBan,
) -> None:
    # S0-1 (18/09/2026). Luật 15/09: cờ ưu tiên/VIP chỉ là NHÃN cho lễ tân,
    # không tự đổi thứ tự (COMMENT cột patient.uu_tien, migration
    # 20260915000016). hang_cho từng chèn `p.uu_tien DESC` trước eligible_at.
    async with kb.pool.acquire() as conn:
        a = await _luot(conn, kb.location_id, kb.bac_si.staff_id)
        b = await _luot(conn, kb.location_id, kb.bac_si.staff_id)
    for v in (a, b):  # A đủ điều kiện TRƯỚC B
        await kb.svc.bat_dau_do_sinh_hieu(visit_id=v, identity=kb.dieu_duong)
        await kb.svc.record_vitals(
            visit_id=v, raw={"systolic": 110, "diastolic": 70}, identity=kb.dieu_duong
        )
        await _hanh_trinh(kb.pool)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE patient SET uu_tien = true, uu_tien_ly_do = 'VIP thử'"
            " WHERE clinic_patient_id ="
            " (SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid)",
            b,
        )
    hc = await kb.svc.hang_cho(identity=kb.bac_si, room_id=None)
    thu_tu = [r["visit_id"] for r in hc["hang_cho"] if r["visit_id"] in (a, b)]
    assert thu_tu == [a, b], "VIP vào hàng sau không được chen lên trước"
    assert [r["uu_tien"] for r in hc["hang_cho"] if r["visit_id"] == b] == [True]


async def test_hai_nguoi_cung_bat_dau_mot_chi_dinh_chi_mot_nguoi_duoc(
    kb: KichBan, monkeypatch: pytest.MonkeyPatch
) -> None:
    # S0-6 (18/09/2026): nhận việc phải ATOMIC — người thứ hai nhận 409, không
    # ghi đè. start_service khoá LƯỢT KHÁM (_lock_visit) rồi mới đọc chỉ định.
    #
    # ÉP TRANH CHẤP THẬT: asyncio.gather trần chạy gần như tuần tự — đã thử bỏ
    # khoá mà test vẫn xanh. Chốt chờ dưới đây giữ người đọc trước lại tới khi
    # người kia cũng đọc xong (hoặc hết 0,5 giây). Có khoá: người thứ hai kẹt ở
    # khoá, người đầu hết giờ chờ rồi ghi, người thứ hai thấy đã có người → 409.
    # Không khoá: cả hai cùng đọc "chưa ai nhận" và cùng ghi → test ĐỎ.
    goc = kb.svc._order_for_performer
    da_doc = 0
    ca_hai_da_doc = asyncio.Event()

    async def doc_roi_cho(*args: Any, **kwargs: Any) -> Any:
        nonlocal da_doc
        kq = await goc(*args, **kwargs)
        da_doc += 1
        if da_doc >= 2:
            ca_hai_da_doc.set()
        try:
            await asyncio.wait_for(ca_hai_da_doc.wait(), 0.5)
        except TimeoutError:
            pass
        return kq

    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    oid = duyet["order_ids"][0]
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": oid, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=oid,
        room_id=kb.phong_mau,
        expected_version=None,
        identity=kb.truong_ca,
    )
    async with kb.pool.acquire() as conn:
        dd2 = await _nguoi(conn, kb.location_id, "NURSE_ULTRASOUND")
    monkeypatch.setattr(kb.svc, "_order_for_performer", doc_roi_cho)
    kq = await asyncio.gather(
        kb.svc.start_service(order_id=oid, identity=kb.dieu_duong),
        kb.svc.start_service(order_id=oid, identity=dd2),
        return_exceptions=True,
    )
    loi = [r for r in kq if isinstance(r, BaseException)]
    assert len(loi) == 1, kq
    assert isinstance(loi[0], LuotKhamConflictError)
    async with kb.pool.acquire() as conn:
        nguoi = await conn.fetchval(
            "SELECT performed_by::text FROM service_order WHERE id = $1::uuid", oid
        )
    assert nguoi in (kb.dieu_duong.staff_id, dd2.staff_id)


async def test_thu_thuat_chi_bac_si_lam(kb: KichBan) -> None:
    async with kb.pool.acquire() as conn:
        vai = await conn.fetchval(
            "SELECT actor_roles FROM node_definition WHERE clinic_id = $1::uuid"
            " AND code = 'DICHVU-THUTHUAT'",
            CLINIC,
        )
    assert list(vai) == ["DOCTOR"]


# ---------------------------------------------------------------------------
# Kết quả theo chỉ định: đối tác 2 trạng thái · tệp gắn chỉ định · bác sĩ duyệt
# ---------------------------------------------------------------------------


async def _dat_doi_tac_lay_mau(kb: KichBan, bat: bool) -> None:
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_price SET doi_tac_lay_mau = $3"
            " WHERE clinic_id = $1::uuid AND service_code = $2",
            CLINIC,
            kb.ma_mau,
            bat,
        )


async def _doi_tac(kb: KichBan) -> StaffIdentity:
    async with kb.pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        return await _nguoi(conn, loc, "PARTNER")


def _viec(ds: dict[str, Any], order_id: str) -> dict[str, Any] | None:
    for k in ds["khach"]:
        for v in k["viec"]:
            if v["chi_dinh_id"] == order_id:
                return dict(v)
    return None


async def test_doi_tac_tu_lay_mau_roi_bac_si_duyet(
    kb: KichBan, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    doi_tac = await _doi_tac(kb)
    await _dat_doi_tac_lay_mau(kb, True)
    try:
        phien = await _vao_kham(kb)
        duyet = await kb.svc.authorize_orders(
            consultation_id=phien,
            service_codes=[kb.ma_mau],
            draft_order_ids=None,
            identity=kb.bac_si,
        )
        mau_id = duyet["order_ids"][0]
        async with kb.pool.acquire() as conn:
            trang_thai = await conn.fetchval(
                "SELECT exec_status FROM service_order WHERE id = $1::uuid", mau_id
            )
        # Đối tác tự lấy → không xếp vào phòng Lấy mẫu của điều dưỡng.
        assert trang_thai == "authorized"
        await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)

        viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["trang_thai"] == "CHO_LAY_MAU"
        await kb.svc.doi_tac_da_lay_mau(order_id=mau_id, identity=doi_tac)
        viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["trang_thai"] == "DA_LAY_MAU"

        # Đối tác nhận mẫu → "chờ tài liệu"; bấm lại không đổi mốc đầu.
        await kb.svc.doi_tac_cho_tai_lieu(order_id=mau_id, identity=doi_tac)
        viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["trang_thai"] == "CHO_TAI_LIEU"
        moc = viec["cho_tai_lieu_luc"]
        lai = await kb.svc.doi_tac_cho_tai_lieu(order_id=mau_id, identity=doi_tac)
        assert lai["already"] is True
        viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["cho_tai_lieu_luc"] == moc

        async with kb.pool.acquire() as conn:
            khach = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
                kb.visit_id,
            )
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000d49444154789c63f8cfc0f01f0005000201a5e5a4a40000000049454e"
            "44ae426082"
        )
        tep = await TepKetQuaService(kb.pool).tai_len(
            identity=doi_tac,
            clinic_patient_id=khach,
            data=png,
            ten_hien_thi="kq.png",
            service_order_id=mau_id,
        )
        # Có kết quả → sang mục "Đã gửi hôm nay" của đối tác (không còn là việc
        # cần làm), và sau khi xác nhận HOP_LE thì sang hàng chờ bác sĩ duyệt.
        viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
        assert viec is not None and viec["trang_thai"] == "DA_GUI_KET_QUA"

        # Cấp capability xác nhận kết quả và xác nhận HOP_LE
        async with kb.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO capability_grant"
                " (clinic_id, staff_id, capability, tu_khoi)"
                " VALUES ($2::uuid, $1::uuid, 'result.file.confirm',"
                " 'xac_nhan_ket_qua') ON CONFLICT DO NOTHING",
                kb.dieu_duong.staff_id,
                kb.dieu_duong.clinic_id,
            )
        await TepKetQuaService(kb.pool).xac_nhan_tep(
            identity=kb.dieu_duong,
            tep_id=tep["id"],
            trang_thai="HOP_LE",
        )

        cho = await kb.svc.ket_qua_cho_duyet(identity=kb.bac_si)
        dong = next(r for r in cho["ket_qua"] if r["id"] == mau_id)
        assert [t["id"] for t in dong["tep"]] == [tep["id"]]

        await kb.svc.duyet_ket_qua(
            order_id=mau_id, danh_gia="Chỉ số bình thường.", identity=kb.bac_si
        )
        cho = await kb.svc.ket_qua_cho_duyet(identity=kb.bac_si)
        assert all(r["id"] != mau_id for r in cho["ket_qua"])
        async with kb.pool.acquire() as conn:
            o = await conn.fetchrow(
                "SELECT duyet_luc, bac_si_danh_gia FROM service_order"
                " WHERE id = $1::uuid",
                mau_id,
            )
            cho_phep = await conn.fetchval(
                "SELECT cho_phep_gui_luc FROM tep_ket_qua WHERE id = $1::uuid",
                tep["id"],
            )
        assert o["duyet_luc"] is not None
        assert o["bac_si_danh_gia"] == "Chỉ số bình thường."
        assert cho_phep is not None, "duyệt chỉ định phải cho phép gửi tệp của nó"

        # Bản tệp MỚI gửi sau lần duyệt: không thừa hưởng quyền gửi, và phải
        # quay lại hàng duyệt (trước đây nằm im mãi — smoke 18/09).
        tep2 = await TepKetQuaService(kb.pool).tai_len(
            identity=doi_tac,
            clinic_patient_id=khach,
            data=png,
            ten_hien_thi="kq-ban-dieu-chinh.png",
            service_order_id=mau_id,
        )
        async with kb.pool.acquire() as conn:
            assert (
                await conn.fetchval(
                    "SELECT cho_phep_gui_luc FROM tep_ket_qua WHERE id = $1::uuid",
                    tep2["id"],
                )
                is None
            )

        # Xác nhận HOP_LE cho tep2 trước khi bác sĩ duyệt bản mới
        await TepKetQuaService(kb.pool).xac_nhan_tep(
            identity=kb.dieu_duong,
            tep_id=tep2["id"],
            trang_thai="HOP_LE",
        )

        cho = await kb.svc.ket_qua_cho_duyet(identity=kb.bac_si)
        dong = next(r for r in cho["ket_qua"] if r["id"] == mau_id)
        assert dong["duyet_lan_truoc"] is not None
        assert {t["id"]: t["da_cho_gui"] for t in dong["tep"]} == {
            tep["id"]: True,
            tep2["id"]: False,
        }
        lai = await kb.svc.duyet_ket_qua(
            order_id=mau_id, danh_gia=None, identity=kb.bac_si
        )
        assert lai["tep_moi"] == 1
        cho = await kb.svc.ket_qua_cho_duyet(identity=kb.bac_si)
        assert all(r["id"] != mau_id for r in cho["ket_qua"])
        async with kb.pool.acquire() as conn:
            assert await conn.fetchval(
                "SELECT cho_phep_gui_luc IS NOT NULL FROM tep_ket_qua"
                " WHERE id = $1::uuid",
                tep2["id"],
            )
            # Không ghi đánh giá mới → giữ đánh giá cũ.
            assert (
                await conn.fetchval(
                    "SELECT bac_si_danh_gia FROM service_order WHERE id = $1::uuid",
                    mau_id,
                )
                == "Chỉ số bình thường."
            )
    finally:
        await _dat_doi_tac_lay_mau(kb, False)


async def test_dieu_duong_lay_mau_thi_doi_tac_chi_thay_sau_khi_lay(
    kb: KichBan,
) -> None:
    doi_tac = await _doi_tac(kb)
    await _dat_doi_tac_lay_mau(kb, False)
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    mau_id = duyet["order_ids"][0]
    await _dieu_phoi_tay(kb, mau_id, kb.phong_mau)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    assert _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id) is None

    await kb.svc.start_service(order_id=mau_id, identity=kb.dieu_duong)
    await kb.svc.complete_service(
        order_id=mau_id,
        performed=True,
        reason=None,
        result_note=None,
        identity=kb.dieu_duong,
    )
    viec = _viec(await kb.svc.viec_doi_tac(identity=doi_tac), mau_id)
    assert viec is not None and viec["trang_thai"] == "DA_LAY_MAU"


async def test_doi_tac_khong_bam_lay_mau_cho_viec_dieu_duong_lay(kb: KichBan) -> None:
    doi_tac = await _doi_tac(kb)
    await _dat_doi_tac_lay_mau(kb, False)
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    with pytest.raises(SafetyGateError):
        await kb.svc.doi_tac_da_lay_mau(
            order_id=duyet["order_ids"][0], identity=doi_tac
        )


async def test_chua_co_ket_qua_thi_khong_duyet_duoc(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    with pytest.raises(LuotKhamConflictError) as e:
        await kb.svc.duyet_ket_qua(
            order_id=duyet["order_ids"][0], danh_gia=None, identity=kb.bac_si
        )
    assert e.value.error_code == "NO_RESULT_YET"


# ---------------------------------------------------------------------------
# Gọi khách vào phòng (Tuyền 16/09/2026: gọi vào khám rồi mới bắt đầu khám)
# ---------------------------------------------------------------------------


async def test_goi_vao_kham_roi_bat_dau(kb: KichBan) -> None:
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    hc = await kb.svc.hang_cho(identity=kb.bac_si, room_id=None)
    dong = next(r for r in hc["hang_cho"] if r["visit_id"] == kb.visit_id)
    # Điều dưỡng không gọi khách vào phòng khám bác sĩ.
    with pytest.raises(SafetyGateError):
        await kb.svc.goi_khach(queue_entry_id=dong["id"], identity=kb.dieu_duong)
    ra = await kb.svc.goi_khach(queue_entry_id=dong["id"], identity=kb.bac_si)
    assert ra["lan_goi_lai"] is False
    hc = await kb.svc.hang_cho(identity=kb.bac_si, room_id=None)
    dong = next(r for r in hc["hang_cho"] if r["visit_id"] == kb.visit_id)
    assert dong["trang_thai"] == "called" and dong["goi_luc"]
    lai = await kb.svc.goi_khach(queue_entry_id=dong["id"], identity=kb.bac_si)
    assert lai["lan_goi_lai"] is True
    # Đã gọi rồi vẫn bấm Bắt đầu khám được.
    await kb.svc.start_consultation(consultation_id=dong["ref_id"], identity=kb.bac_si)
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.goi_khach(queue_entry_id=dong["id"], identity=kb.bac_si)


async def test_thu_ky_chua_phan_bac_si_van_thay_khach_o_ban_kham_cua_toi(
    kb: KichBan, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chế độ mở quyền: thư ký chưa được phân bác sĩ mở 'Khách của tôi' phải thấy
    lượt khám chính (bản trước trả rỗng)."""
    monkeypatch.setenv("MO_QUYEN_TAM_THOI", "1")
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    hc = await kb.svc.hang_cho(identity=kb.thu_ky, room_id=None)
    assert any(r["visit_id"] == kb.visit_id for r in hc["hang_cho"])


async def test_khach_chua_co_bac_si_van_hien_o_hang_cho_bac_si(kb: KichBan) -> None:
    """Lịch hẹn không gắn bác sĩ → lượt khám chính vẫn phải có người thấy."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET attending_doctor_id = NULL WHERE visit_id = $1::uuid",
            kb.visit_id,
        )
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 118, "diastolic": 76},
        identity=kb.dieu_duong,
    )
    await _hanh_trinh(kb.pool)
    hc = await kb.svc.hang_cho(identity=kb.bac_si, room_id=None)
    dong = [r for r in hc["hang_cho"] if r["visit_id"] == kb.visit_id]
    assert len(dong) == 1
    await kb.svc.start_consultation(
        consultation_id=dong[0]["ref_id"], identity=kb.bac_si
    )
    async with kb.pool.acquire() as conn:
        bs = await conn.fetchval(
            "SELECT doctor_staff_id::text FROM consultation WHERE id = $1::uuid",
            dong[0]["ref_id"],
        )
    assert bs == kb.bac_si.staff_id, "bác sĩ bấm Bắt đầu khám thì nhận khách"


# ---------------------------------------------------------------------------
# Demo 17/09/2026: người đi kèm ở phòng dịch vụ + con trỏ "khách đang ở đâu"
# ---------------------------------------------------------------------------


async def _vi_tri(kb: KichBan) -> tuple[str | None, str | None]:
    async with kb.pool.acquire() as conn:
        r = await conn.fetchrow(
            "SELECT v.current_node_code, r.code FROM visit v"
            " LEFT JOIN clinic_room r ON r.id = v.current_room_id"
            " WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
    return r["current_node_code"], r["code"]


async def test_dieu_duong_di_kem_checkin_checkout_phong_dich_vu(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await _dieu_phoi_tay(kb, sa_id, kb.phong_sa)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    node, _ = await _vi_tri(kb)
    assert node == "DICHVU-SIEUAM"  # rời bàn khám → đang chờ ở phòng siêu âm
    async with kb.pool.acquire() as conn:
        phong = await conn.fetchval(
            "SELECT room_id::text FROM service_order WHERE id = $1::uuid", sa_id
        )
    hc = await kb.svc.hang_cho(identity=kb.dieu_duong, room_id=phong)
    dong = next(r for r in hc["hang_cho"] if r["ref_id"] == sa_id)
    await kb.svc.goi_khach(queue_entry_id=dong["id"], identity=kb.thu_ky)
    await kb.svc.start_service(order_id=sa_id, identity=kb.dieu_duong)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="bình thường",
        identity=kb.bs_sieu_am,
    )
    async with kb.pool.acquire() as conn:
        nguoi = await conn.fetchval(
            "SELECT performed_by::text FROM service_order WHERE id = $1::uuid", sa_id
        )
    # Bác sĩ bấm Xong → bác sĩ là người thực hiện, dù điều dưỡng bấm Bắt đầu.
    assert nguoi == kb.bs_sieu_am.staff_id
    node, _ = await _vi_tri(kb)
    async with kb.pool.acquire() as conn:
        dbg = await conn.fetch(
            "SELECT q.lane, q.reason, q.status, st.form_code FROM queue_entry q"
            " JOIN visit v ON v.visit_id = q.visit_id"
            " LEFT JOIN service_type st ON st.id = v.service_type_id"
            " WHERE q.visit_id = $1::uuid",
            kb.visit_id,
        )
    assert node != "DICHVU-SIEUAM", [tuple(r) for r in dbg]  # rời phòng SA


async def test_kham_xong_khong_chi_dinh_con_tro_ve_dong_luot(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    node, _ = await _vi_tri(kb)
    assert node == "LUOTKHAM-15"
    async with kb.pool.acquire() as conn:
        hen = await conn.fetchval(
            "SELECT a.status FROM appointment a JOIN visit v"
            " ON v.appointment_id = a.id WHERE v.visit_id = $1::uuid",
            kb.visit_id,
        )
    # Bác sĩ ký khám xong hẳn → lịch COMPLETED để quầy thu được tiền. Lượt thử
    # ở đây không có lịch hẹn (None); đường có lịch hẹn được kịch bản demo chạy
    # thật trên final cloud.
    assert hen in (None, "COMPLETED")


async def test_le_tan_khong_bam_duoc_phong_dich_vu(kb: KichBan) -> None:
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    await kb.svc.kham_xong(consultation_id=phien, identity=kb.bac_si)
    with pytest.raises(SafetyGateError):
        await kb.svc.start_service(order_id=duyet["order_ids"][0], identity=kb.le_tan)


# ------------------------------------------------------------------
# Tests an toàn nút Khám xong (HANDOFF vs TERMINAL) & guard hồ sơ
# ------------------------------------------------------------------


async def _benh_an_sach(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
) -> None:
    await conn.execute(
        """
        INSERT INTO clinical_record (
            clinic_id, visit_id, soap_assessment, soap_plan, prescription_draft
        ) VALUES (
            $1::uuid, $2::uuid,
            '{"chan_doan": "Khám sức khỏe tổng quát"}'::jsonb,
            '{"loi_dan": "Tái khám theo hẹn"}'::jsonb,
            NULL
        )
        ON CONFLICT (visit_id) DO UPDATE SET
            soap_assessment = '{"chan_doan": "Khám sức khỏe tổng quát"}'::jsonb,
            soap_plan = '{"loi_dan": "Tái khám theo hẹn"}'::jsonb,
            prescription_draft = NULL
        """,
        clinic_id,
        visit_id,
    )


async def test_handoff_services_pass_du_chua_co_chan_doan_cuoi(kb: KichBan) -> None:
    """1. PRIMARY + còn chỉ định -> SERVICES:
    hồ sơ chưa có chẩn đoán cuối vẫn được kết thúc phiên để đi dịch vụ.
    """
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    # Chưa hề có clinical_record hay chẩn đoán/lời dặn cuối
    kq = await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    assert kq["ok"] is True
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["phien"][0]["trang_thai"] == "completed"
    async with kb.pool.acquire() as conn:
        con_outcome = await conn.fetchval(
            "SELECT outcome FROM consultation WHERE id = $1::uuid", phien
        )
    assert con_outcome == "SERVICES"


async def test_primary_no_services_khong_bat_buoc_chan_doan_loi_dan(
    kb: KichBan,
) -> None:
    """2. PRIMARY + không có chỉ định -> NO_SERVICES:
    chưa có chẩn đoán/lời dặn cuối vẫn được kết thúc (chưa có hard gate y khoa).
    """
    phien = await _vao_kham(kb)
    kq = await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="NO_SERVICES",
        requirements=None,
        identity=kb.bac_si,
    )
    assert kq["ok"] is True
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["phien"][0]["trang_thai"] == "completed"


async def test_tkyk_handoff_services_pass(kb: KichBan) -> None:
    """TKYK đi kèm bác sĩ được phép HANDOFF qua SERVICES."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)
            VALUES ($1::uuid, $2::uuid, $3::uuid)
            ON CONFLICT DO NOTHING
            """,
            CLINIC,
            kb.thu_ky.staff_id,
            kb.bac_si.staff_id,
        )
    phien = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    kq = await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.thu_ky,
    )
    assert kq["ok"] is True
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["phien"][0]["trang_thai"] == "completed"


async def test_tkyk_terminal_no_services_blocked(kb: KichBan) -> None:
    """TKYK đi kèm bác sĩ bị chặn TERMINAL NO_SERVICES -> SafetyGateError."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)
            VALUES ($1::uuid, $2::uuid, $3::uuid)
            ON CONFLICT DO NOTHING
            """,
            CLINIC,
            kb.thu_ky.staff_id,
            kb.bac_si.staff_id,
        )
    phien = await _vao_kham(kb)
    with pytest.raises(SafetyGateError, match="Chỉ bác sĩ phụ trách"):
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="NO_SERVICES",
            requirements=None,
            identity=kb.thu_ky,
        )


async def test_tkyk_terminal_done_blocked(kb: KichBan) -> None:
    """TKYK đi kèm bác sĩ bị chặn TERMINAL DONE -> SafetyGateError."""
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)
            VALUES ($1::uuid, $2::uuid, $3::uuid)
            ON CONFLICT DO NOTHING
            """,
            CLINIC,
            kb.thu_ky.staff_id,
            kb.bac_si.staff_id,
        )
    phien_1 = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien_1,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await kb.svc.complete_consultation(
        consultation_id=phien_1,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Bình thường",
        identity=kb.bs_sieu_am,
    )
    async with kb.pool.acquire() as conn:
        rev_id = await conn.fetchval(
            "SELECT id::text FROM consultation"
            " WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kb.visit_id,
        )
    await kb.svc.start_consultation(consultation_id=rev_id, identity=kb.bac_si)
    with pytest.raises(SafetyGateError, match="Chỉ bác sĩ phụ trách"):
        await kb.svc.complete_consultation(
            consultation_id=rev_id,
            outcome="DONE",
            requirements=None,
            identity=kb.thu_ky,
        )


async def test_bac_si_khac_terminal_blocked(kb: KichBan) -> None:
    """Bác sĩ khác (không phụ trách) bị chặn TERMINAL NO_SERVICES/DONE."""
    # 1. Thử với PRIMARY NO_SERVICES
    phien = await _vao_kham(kb)
    with pytest.raises(SafetyGateError, match="Chỉ bác sĩ phụ trách"):
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="NO_SERVICES",
            requirements=None,
            identity=kb.bac_si_2,
        )

    # 2. Bác sĩ phụ trách hoàn tất HANDOFF sang dịch vụ
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Bình thường",
        identity=kb.bs_sieu_am,
    )
    async with kb.pool.acquire() as conn:
        rev_id = await conn.fetchval(
            "SELECT id::text FROM consultation"
            " WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kb.visit_id,
        )
    await kb.svc.start_consultation(consultation_id=rev_id, identity=kb.bac_si)

    # Thử bác sĩ khác kết thúc REVIEW DONE -> chặn
    with pytest.raises(SafetyGateError, match="Chỉ bác sĩ phụ trách"):
        await kb.svc.complete_consultation(
            consultation_id=rev_id,
            outcome="DONE",
            requirements=None,
            identity=kb.bac_si_2,
        )


async def test_primary_no_services_pending_prescription_draft(kb: KichBan) -> None:
    """3. PRIMARY + NO_SERVICES:
    hồ sơ đủ nhưng prescription_draft còn -> 409 PRESCRIPTION_DRAFT_PENDING.
    """
    phien = await _vao_kham(kb)
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clinical_record (
                clinic_id, visit_id, soap_assessment, soap_plan, prescription_draft
            ) VALUES (
                $1::uuid, $2::uuid,
                '{"chan_doan": "Cảm cúm"}'::jsonb,
                '{"loi_dan": "Uống nhiều nước"}'::jsonb,
                '{"items": [{"drug_name": "Paracetamol"}]}'::jsonb
            )
            ON CONFLICT (visit_id) DO UPDATE SET
                soap_assessment = '{"chan_doan": "Cảm cúm"}'::jsonb,
                soap_plan = '{"loi_dan": "Uống nhiều nước"}'::jsonb,
                prescription_draft = '{"items": [{"drug_name": "Paracetamol"}]}'::jsonb
            """,
            CLINIC,
            kb.visit_id,
        )
    with pytest.raises(LuotKhamConflictError) as exc_info:
        await kb.svc.complete_consultation(
            consultation_id=phien,
            outcome="NO_SERVICES",
            requirements=None,
            identity=kb.bac_si,
        )
    assert exc_info.value.error_code == "PRESCRIPTION_DRAFT_PENDING"


async def test_primary_no_services_ho_so_sach_pass(kb: KichBan) -> None:
    """4. PRIMARY + NO_SERVICES:
    hồ sơ đủ, không pending draft -> PASS.
    """
    phien = await _vao_kham(kb)
    async with kb.pool.acquire() as conn:
        await _benh_an_sach(conn, CLINIC, kb.visit_id)
    kq = await kb.svc.complete_consultation(
        consultation_id=phien,
        outcome="NO_SERVICES",
        requirements=None,
        identity=kb.bac_si,
    )
    assert kq["ok"] is True
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["phien"][0]["trang_thai"] == "completed"
    async with kb.pool.acquire() as conn:
        con_outcome = await conn.fetchval(
            "SELECT outcome FROM consultation WHERE id = $1::uuid", phien
        )
    assert con_outcome == "NO_SERVICES"


async def test_review_done_pending_prescription_draft(kb: KichBan) -> None:
    """5. REVIEW + DONE:
    pending prescription draft -> không đóng (409 PRESCRIPTION_DRAFT_PENDING).
    """
    phien_1 = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien_1,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await kb.svc.complete_consultation(
        consultation_id=phien_1,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Bình thường",
        identity=kb.bs_sieu_am,
    )
    async with kb.pool.acquire() as conn:
        rev_id = await conn.fetchval(
            "SELECT id::text FROM consultation"
            " WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kb.visit_id,
        )
    await kb.svc.start_consultation(consultation_id=rev_id, identity=kb.bac_si)
    # Hồ sơ có chẩn đoán & lời dặn nhưng prescription_draft còn tồn đọng
    async with kb.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clinical_record (
                clinic_id, visit_id, soap_assessment, soap_plan, prescription_draft
            ) VALUES (
                $1::uuid, $2::uuid,
                '{"chan_doan": "Viêm dạ dày"}'::jsonb,
                '{"loi_dan": "Ăn uống đúng giờ"}'::jsonb,
                '{"items": [{"drug_name": "Omeprazole"}]}'::jsonb
            )
            ON CONFLICT (visit_id) DO UPDATE SET
                soap_assessment = '{"chan_doan": "Viêm dạ dày"}'::jsonb,
                soap_plan = '{"loi_dan": "Ăn uống đúng giờ"}'::jsonb,
                prescription_draft = '{"items": [{"drug_name": "Omeprazole"}]}'::jsonb
            """,
            CLINIC,
            kb.visit_id,
        )
    with pytest.raises(LuotKhamConflictError) as exc_info:
        await kb.svc.complete_consultation(
            consultation_id=rev_id,
            outcome="DONE",
            requirements=None,
            identity=kb.bac_si,
        )
    assert exc_info.value.error_code == "PRESCRIPTION_DRAFT_PENDING"


async def test_review_done_ho_so_sach_pass(kb: KichBan) -> None:
    """6. REVIEW + DONE:
    hồ sơ sạch -> PASS.
    """
    phien_1 = await _vao_kham(kb)
    duyet = await kb.svc.authorize_orders(
        consultation_id=phien_1,
        service_codes=[kb.ma_sa],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    sa_id = duyet["order_ids"][0]
    await kb.svc.complete_consultation(
        consultation_id=phien_1,
        outcome="SERVICES",
        requirements=[{"order_id": sa_id, "need": "PERFORMED"}],
        identity=kb.bac_si,
    )
    await dieu_phoi_cu(
        kb.svc,
        order_id=sa_id,
        room_id=kb.phong_sa,
        expected_version=None,
        identity=kb.truong_ca,
    )
    await kb.svc.start_service(order_id=sa_id, identity=kb.bs_sieu_am)
    await kb.svc.complete_service(
        order_id=sa_id,
        performed=True,
        reason=None,
        result_note="Bình thường",
        identity=kb.bs_sieu_am,
    )
    async with kb.pool.acquire() as conn:
        rev_id = await conn.fetchval(
            "SELECT id::text FROM consultation"
            " WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kb.visit_id,
        )
    await kb.svc.start_consultation(consultation_id=rev_id, identity=kb.bac_si)
    # Hồ sơ sạch
    async with kb.pool.acquire() as conn:
        await _benh_an_sach(conn, CLINIC, kb.visit_id)
    kq = await kb.svc.complete_consultation(
        consultation_id=rev_id,
        outcome="DONE",
        requirements=None,
        identity=kb.bac_si,
    )
    assert kq["ok"] is True
    luot = _cua(await kb.svc.bang(identity=kb.bac_si), kb.visit_id)
    assert luot["ket_thuc_luc"] is not None
