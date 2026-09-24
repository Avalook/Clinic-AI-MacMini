"""DB integration tests for Result File Confirmation (Blocker 1 - Scenarios A to S).

Target:
- Tách UPLOAD khỏi KET_QUA_HOP_LE.
- Tệp đối tác upload bắt đầu ở trạng thái CHO_XAC_NHAN.
- Chỉ tệp được xác nhận HOP_LE mới làm has_valid_result = true cho external order.
- Capability ket_qua.xac_nhan: fail-closed nếu multi-clinic hoặc chưa cấp.
- State machine: CHO_XAC_NHAN -> HOP_LE, CHO_XAC_NHAN -> TU_CHOI, HOP_LE -> THU_HOI.
- 2 tầng chặn gửi khách: Python service + DB trigger.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.schemas.staff import Capability
from clinicai.services.luot_kham_service import LuotKhamConflictError, LuotKhamService
from clinicai.services.tep_ket_qua_service import (
    TepKetQuaService,
    kiem_tra_quyen_xac_nhan,
)

CLINIC_A = "a0000000-0000-4000-8000-000000000001"
CLINIC_B = "a0000000-0000-4000-8000-000000000002"
PDF_DUMMY = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"xref\n0 1\n0000000000 65535 f \n"
    b"trailer<</Size 1/Root 1 0 R>>\nstartxref\n49\n%%EOF"
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _vong_doc_chay_ngay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tệp kết quả → khối VÒNG ĐỌC (sự kiện, 24/09): chạy ngay như worker."""
    from tests.chay_nguoi_dua_tin import vong_doc_chay_ngay_sau_lenh_tep

    vong_doc_chay_ngay_sau_lenh_tep(monkeypatch)


@pytest.fixture(autouse=True)
def _bat_buoc_xac_nhan_tep_doi_tac(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bước xác nhận tệp đối tác OFF từ 23/09/2026 khuya (tệp vào thẳng phiếu
    khám). Bài này canh ĐƯỜNG CŨ (còn giữ, bật lại được) nên bật cờ."""
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(tep_mod, "XAC_NHAN_TEP_DOI_TAC", True)


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


async def _tao_staff(
    conn: asyncpg.Connection,
    clinic_id: str,
    role: str,
    caps: list[str] | None = None,
) -> StaffIdentity:
    sid = str(uuid.uuid4())
    full_name = f"Test Staff {role} {sid[:6]}"
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location "
        "WHERE clinic_id = $1::uuid AND is_active "
        "ORDER BY created_at, id LIMIT 1",
        clinic_id,
    )
    if not loc:
        loc = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO clinic_location (id, clinic_id, code, name, is_active)
            VALUES (
                $1::uuid, $2::uuid, 'CS_TEST_' || substr($1::text, 1, 4),
                'Cơ sở chính test', true
            )
            ON CONFLICT (id) DO NOTHING
            """,
            loc,
            clinic_id,
        )
    dept = role
    if role == "NURSE":
        dept = "NURSE_ULTRASOUND"
        role = "NURSE_ULTRASOUND"

    await conn.execute(
        """
        INSERT INTO staff (
            id, full_name, primary_department, primary_location_id, is_active
        )
        VALUES ($1::uuid, $2, $3, $4::uuid, true)
        ON CONFLICT (id) DO NOTHING
        """,
        sid,
        full_name,
        dept,
        loc,
    )
    await conn.execute(
        """
        INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)
        VALUES ($1::uuid, $2::uuid, $3, true)
        ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true
        """,
        clinic_id,
        sid,
        role,
    )
    # Người thật vào hệ thống được cấp quyền theo vai (CORE-B1) — thiếu dòng này
    # thì bác sĩ không duyệt được kết quả, dù vai đúng.
    await conn.fetch(
        "SELECT public.cap_quyen_theo_preset($1::uuid, $2::uuid, $3)",
        clinic_id,
        sid,
        role,
    )
    if caps:
        # MỘT hệ quyền (23/09/2026): `ket_qua.xac_nhan` cũ = `result.file.confirm`
        # trong `capability_grant`, theo từng phòng khám.
        for c in caps:
            ma = "result.file.confirm" if c == "ket_qua.xac_nhan" else c
            await conn.execute(
                """
                INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)
                SELECT $1::uuid, $2::uuid, c.ma, c.work_pack
                  FROM capability c WHERE c.ma = $3
                ON CONFLICT DO NOTHING
                """,
                clinic_id,
                sid,
                ma,
            )

    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=full_name,
        department=dept,
        role=ClinicRole(role),
        clinic_id=clinic_id,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _tao_benh_nhan_va_visit(
    conn: asyncpg.Connection, clinic_id: str, doctor_id: str
) -> tuple[str, str, str]:
    pid = str(uuid.uuid4())
    pcode = f"BN-{uuid.uuid4().hex[:6].upper()}"
    loc = await conn.fetchval(
        "SELECT id::text FROM clinic_location "
        "WHERE clinic_id = $1::uuid AND is_active "
        "ORDER BY created_at, id LIMIT 1",
        clinic_id,
    )
    if not loc:
        loc = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO clinic_location (id, clinic_id, code, name, is_active)
            VALUES (
                $1::uuid, $2::uuid, 'CS_TEST_' || substr($1::text, 1, 4),
                'Cơ sở chính test', true
            )
            ON CONFLICT (id) DO NOTHING
            """,
            loc,
            clinic_id,
        )
    await conn.execute(
        """
        INSERT INTO patient (
            clinic_id, clinic_patient_id, patient_code, full_name,
            date_of_birth, gender, location_id
        )
        VALUES (
            $1::uuid, $2::uuid, $3, 'Bệnh nhân test', '1990-01-01', 'Nữ',
            $4::uuid
        )
        """,
        clinic_id,
        pid,
        pcode,
        loc,
    )
    stid = await conn.fetchval(
        "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid LIMIT 1",
        clinic_id,
    )
    if not stid:
        stid = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO service_type (
                id, clinic_id, name, code, default_duration_minutes
            )
            VALUES ($1::uuid, $2::uuid, 'Khám test', 'KHAM_TEST', 30)
            ON CONFLICT (id) DO NOTHING
            """,
            stid,
            clinic_id,
        )
    aid = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO appointment (
            id, clinic_id, clinic_patient_id, service_type_id, slot_start,
            slot_end, status, location_id
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid, now(),
            now() + interval '30 minutes', 'CHECKED_IN', $5::uuid
        )
        """,
        aid,
        clinic_id,
        pid,
        stid,
        loc,
    )
    vid = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO visit (
            visit_id, clinic_id, clinic_patient_id, appointment_id, status,
            attending_doctor_id
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'OPEN', $5::uuid)
        """,
        vid,
        clinic_id,
        pid,
        aid,
        doctor_id,
    )
    return pid, aid, vid


async def _tao_external_order(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    node_code: str = "XN_NGOAI_TEST",
) -> str:
    # Đảm bảo node_definition có lam_ben_ngoai = true
    await conn.execute(
        """
        INSERT INTO node_definition (
            clinic_id, code, name, flow_group, workspace, lam_ben_ngoai,
            actor_roles
        )
        VALUES (
            $1::uuid, $2, 'Xét nghiệm ngoài test', 'ket_qua',
            'khu_dieu_duong', true, ARRAY['NURSE_ULTRASOUND']
        )
        ON CONFLICT (clinic_id, code) DO UPDATE SET lam_ben_ngoai = true
        """,
        clinic_id,
        node_code,
    )
    cid = await conn.fetchval(
        "SELECT id::text FROM consultation WHERE visit_id = $1::uuid LIMIT 1",
        visit_id,
    )
    if not cid:
        cid = await conn.fetchval(
            "INSERT INTO consultation (clinic_id, visit_id, round_no, kind) "
            "VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY') RETURNING id::text",
            clinic_id,
            visit_id,
        )
    rec_by = await conn.fetchval(
        "SELECT attending_doctor_id::text FROM visit WHERE visit_id = $1::uuid",
        visit_id,
    )
    room_id = await conn.fetchval(
        "SELECT id::text FROM clinic_room "
        "WHERE clinic_id = $1::uuid AND is_active LIMIT 1",
        clinic_id,
    )
    if not room_id:
        room_id = str(uuid.uuid4())
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid LIMIT 1",
            clinic_id,
        )
        await conn.execute(
            """
            INSERT INTO clinic_room (
                id, clinic_id, location_id, name, code, node_code, is_active,
                la_doi_tac
            )
            VALUES (
                $1::uuid, $2::uuid, $3::uuid, 'Phòng đối tác test', 'P-DT', $4,
                true, true
            )
            ON CONFLICT (id) DO NOTHING
            """,
            room_id,
            clinic_id,
            loc,
            node_code,
        )
    oid = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO service_order (
            id, clinic_id, visit_id, consultation_id, service_code, service_name,
            node_code, exec_status, recorded_by, authorized_by, authorized_at, room_id
        )
        VALUES (
            $1::uuid, $2::uuid, $3::uuid, $4::uuid, 'DV_NGOAI', 'Dịch vụ gửi ngoài',
            $5, 'performed', $6::uuid, $6::uuid, now(), $7::uuid
        )
        """,
        oid,
        clinic_id,
        visit_id,
        cid,
        node_code,
        rec_by,
        room_id,
    )
    return oid


async def _tao_review_round_cho_order(
    conn: asyncpg.Connection,
    clinic_id: str,
    visit_id: str,
    order_id: str,
) -> tuple[str, str]:
    rid = str(uuid.uuid4())
    doc_id = await conn.fetchval(
        "SELECT attending_doctor_id::text FROM visit WHERE visit_id = $1::uuid",
        visit_id,
    )
    await conn.execute(
        """
        INSERT INTO review_round (
            id, clinic_id, visit_id, round_no, status, locked_by, locked_at
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, 2, 'collecting', $4::uuid, now())
        """,
        rid,
        clinic_id,
        visit_id,
        doc_id,
    )
    qid = str(uuid.uuid4())
    await conn.execute(
        """
        INSERT INTO round_requirement (
            id, clinic_id, round_id, service_order_id, need, status
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'VALID_RESULT', 'open')
        """,
        qid,
        clinic_id,
        rid,
        order_id,
    )
    return rid, qid


# ==============================================================================
# SCENARIO K: MIGRATION VERSION KHÔNG TRÙNG
# ==============================================================================
async def test_scenario_k_migration_version_khong_trung() -> None:
    migrations_dir = (
        pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    )
    migration_file = migrations_dir / "20260920000005_xac_nhan_tep_ket_qua.sql"
    assert migration_file.exists(), (
        "Migration 20260920000005_xac_nhan_tep_ket_qua.sql phải tồn tại!"
    )

    # Không được có 20260920000001_xac_nhan_tep_ket_qua.sql
    collision_file = migrations_dir / "20260920000001_xac_nhan_tep_ket_qua.sql"
    assert not collision_file.exists(), (
        "Không được dùng số 00001 đã tồn tại cho migration này!"
    )

    # Kiểm tra nội dung migration có tự kiểm tra các bảng phụ thuộc
    content = migration_file.read_text(encoding="utf-8")
    assert "public.tep_ket_qua" in content
    assert "public.staff" in content
    assert "public.staff_capability" in content
    assert (
        "RAISE EXCEPTION 'Table public.staff_capability does not exist. "
        "Baseline schema required.';" in content
    )
    assert Capability.KET_QUA_XAC_NHAN.value == "ket_qua.xac_nhan"


# ==============================================================================
# SCENARIOS A, B, C: UPLOAD -> CHO_XAC_NHAN -> HOP_LE / TU_CHOI
# ==============================================================================
async def test_scenarios_a_b_c_upload_xac_nhan_hop_le_tu_choi(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)

    # SCENARIO A: Upload file -> CHO_XAC_NHAN, VALID_RESULT = false, REVIEW chưa mở
    pdf_bytes = PDF_DUMMY
    res_up = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="kq-xet-nghiem.pdf",
        service_order_id=oid,
    )
    assert res_up["ok"] is True
    tep_id = res_up["id"]

    async with pool.acquire() as conn:
        tep_row = await conn.fetchrow(
            "SELECT * FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        assert tep_row["xac_nhan_trang_thai"] == "CHO_XAC_NHAN"
        assert tep_row["xac_nhan_luc"] is None
        assert tep_row["cho_phep_gui_luc"] is None

        # Kiểm tra _yeu_cau_cua_vong: co_ket_qua phải là False
        reqs = await svc_lk._yeu_cau_cua_vong(conn, CLINIC_A, rid)
        assert len(reqs) == 1
        assert reqs[0]["co_ket_qua"] is False

        # review_round vẫn collecting, không mở REVIEW
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "collecting"
        con_count = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            vid,
        )
        assert con_count == 0

    # SCENARIO C: Xác nhận TU_CHOI -> VALID_RESULT vẫn là False, REVIEW không mở
    res_tu_choi = await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id,
        trang_thai="TU_CHOI",
        ly_do="Ảnh mờ, thiếu dấu giáp lai của phòng xét nghiệm",
    )
    assert res_tu_choi["ok"] is True
    assert res_tu_choi["trang_thai"] == "TU_CHOI"

    async with pool.acquire() as conn:
        tep_row = await conn.fetchrow(
            "SELECT * FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        assert tep_row["xac_nhan_trang_thai"] == "TU_CHOI"
        assert (
            tep_row["xac_nhan_ly_do"]
            == "Ảnh mờ, thiếu dấu giáp lai của phòng xét nghiệm"
        )

        reqs = await svc_lk._yeu_cau_cua_vong(conn, CLINIC_A, rid)
        assert reqs[0]["co_ket_qua"] is False
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "collecting"

    # SCENARIO D: Upload tệp mới thay thế tệp bị từ chối
    res_up_2 = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="kq-xet-nghiem-ro-net.pdf",
        service_order_id=oid,
    )
    tep_id_2 = res_up_2["id"]

    # SCENARIO B: Xác nhận HOP_LE -> VALID_RESULT = true, đúng 1 REVIEW mở
    res_hop_le = await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id_2,
        trang_thai="HOP_LE",
    )
    assert res_hop_le["ok"] is True
    assert res_hop_le["trang_thai"] == "HOP_LE"

    async with pool.acquire() as conn:
        tep_row_2 = await conn.fetchrow(
            "SELECT * FROM tep_ket_qua WHERE id = $1::uuid", tep_id_2
        )
        assert tep_row_2["xac_nhan_trang_thai"] == "HOP_LE"
        assert tep_row_2["xac_nhan_luc"] is not None
        assert str(tep_row_2["xac_nhan_boi_staff_id"]) == staff_xac_nhan.staff_id

        # Kiểm tra _yeu_cau_cua_vong: co_ket_qua đã là True!
        reqs = await svc_lk._yeu_cau_cua_vong(conn, CLINIC_A, rid)
        assert reqs[0]["co_ket_qua"] is True

        # review_round đã chuyển sang 'ready'!
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "ready"

        # Đúng 1 consultation REVIEW queued
        cons = await conn.fetch(
            "SELECT id::text, status FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            vid,
        )
        assert len(cons) == 1
        assert cons[0]["status"] == "queued"

        # Đúng 1 queue_entry lane DOCTOR reason REVIEW
        q_entries = await conn.fetch(
            "SELECT id::text, lane, reason FROM queue_entry "
            "WHERE visit_id = $1::uuid AND reason = 'REVIEW' "
            "AND status = 'waiting'",
            vid,
        )
        assert len(q_entries) == 1
        assert q_entries[0]["lane"] == "DOCTOR"


# ==============================================================================
# SCENARIO E: HAI TỆP, CHỈ 1 TỆP HỢP LỆ -> ĐẠT YÊU CẦU
# ==============================================================================
async def test_scenario_e_hai_tep_mot_hop_le(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "TKYK", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)

    pdf_bytes = PDF_DUMMY
    t1 = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="f1.pdf",
        service_order_id=oid,
    )
    t2 = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="f2.pdf",
        service_order_id=oid,
    )

    # t1 bị từ chối, t2 được duyệt HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan,
        tep_id=t1["id"],
        trang_thai="TU_CHOI",
        ly_do="Sai format",
    )
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t2["id"], trang_thai="HOP_LE"
    )

    async with pool.acquire() as conn:
        reqs = await svc_lk._yeu_cau_cua_vong(conn, CLINIC_A, rid)
        assert reqs[0]["co_ket_qua"] is True
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "ready"


# ==============================================================================
# SCENARIOS F, G, H, L: CAPABILITY VÀ FAIL-CLOSED TESTS
# ==============================================================================
async def test_scenarios_f_g_h_l_capability_fail_closed(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_no_cap = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[]
        )  # Không có capability
        staff_with_cap = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )

        # Staff có capability nhưng thuộc 2 clinics (multi-clinic)
        staff_multi_clinic = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        # Ensure CLINIC_B exists
        await conn.execute(
            """
            INSERT INTO clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic B Test', 'CLINIC_B')
            ON CONFLICT (id) DO NOTHING
            """,
            CLINIC_B,
        )
        await conn.execute(
            """
            INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)
            VALUES ($1::uuid, $2::uuid, 'NURSE_ULTRASOUND', true)
            ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true
            """,
            CLINIC_B,
            staff_multi_clinic.staff_id,
        )

        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)
    pdf_bytes = PDF_DUMMY
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="test.pdf",
        service_order_id=oid,
    )
    tep_id = t["id"]

    # F: Staff không có capability -> SafetyGateError
    with pytest.raises(SafetyGateError, match="chưa được cấp quyền xác nhận"):
        await svc_tep.xac_nhan_tep(
            identity=staff_no_cap, tep_id=tep_id, trang_thai="HOP_LE"
        )

    # G: Hệ thống không seed quyền cho ai -> mặc định fail-closed
    async with pool.acquire() as conn:
        with pytest.raises(SafetyGateError):
            await kiem_tra_quyen_xac_nhan(conn, identity=doc)

    # H: PARTNER bị chặn không được xác nhận
    with pytest.raises(SafetyGateError, match="Đối tác không có quyền"):
        await svc_tep.xac_nhan_tep(identity=partner, tep_id=tep_id, trang_thai="HOP_LE")

    # H2: Người tải lên không được tự xác nhận tệp của chính mình
    # Giả sử staff_with_cap tự tải lên tệp này
    t_self = await svc_tep.tai_len(
        identity=staff_with_cap,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="self.pdf",
        service_order_id=oid,
    )
    with pytest.raises(SafetyGateError, match="không được tự xác nhận"):
        await svc_tep.xac_nhan_tep(
            identity=staff_with_cap, tep_id=t_self["id"], trang_thai="HOP_LE"
        )

    # L: Quyền THEO TỪNG PHÒNG KHÁM (23/09/2026, một hệ quyền). Bảng cũ không có
    # clinic_id nên người làm ≥2 phòng khám bị chặn hết; giờ quyền cấp ở A chỉ
    # có hiệu lực ở A — sang B vẫn bị chặn, dù cùng một người.
    async with pool.acquire() as conn:
        await kiem_tra_quyen_xac_nhan(conn, identity=staff_multi_clinic)
        o_b = dataclasses.replace(staff_multi_clinic, clinic_id=CLINIC_B)
        with pytest.raises(SafetyGateError, match="chưa được cấp quyền xác nhận"):
            await kiem_tra_quyen_xac_nhan(conn, identity=o_b)


# ==============================================================================
# SCENARIOS I & S: RETRY CONFIRMATION IDEMPOTENT (KHÔNG DUPLICATE REVIEW)
# ==============================================================================
async def test_scenarios_i_s_retry_idempotent(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    svc_tep = TepKetQuaService(pool)
    pdf_bytes = PDF_DUMMY
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="t.pdf",
        service_order_id=oid,
    )

    # Lần 1: HOP_LE -> mở 1 REVIEW
    res1 = await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t["id"], trang_thai="HOP_LE"
    )
    assert res1["ok"] is True

    # Lần 2 (Retry): Idempotent, không lỗi, không sinh thêm consultation/queue_entry
    res2 = await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t["id"], trang_thai="HOP_LE"
    )
    assert res2["ok"] is True
    assert res2.get("already") is True

    async with pool.acquire() as conn:
        cons = await conn.fetch(
            "SELECT id FROM consultation WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            vid,
        )
        assert len(cons) == 1
        q_entries = await conn.fetch(
            "SELECT id FROM queue_entry "
            "WHERE visit_id = $1::uuid AND reason = 'REVIEW'",
            vid,
        )
        assert len(q_entries) == 1


# ==============================================================================
# SCENARIOS J, N, O: DUYỆT GỬI KHÁCH VÀ 2 TẦNG CHẶN
# ==============================================================================
async def test_scenarios_j_n_o_cho_phep_gui_va_2_tang_chan(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)
    pdf_bytes = PDF_DUMMY
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="t.pdf",
        service_order_id=oid,
    )
    tep_id = t["id"]

    # N: Bác sĩ không thể approve-send tệp đang CHO_XAC_NHAN qua Python service
    with pytest.raises(SafetyGateError, match="Chỉ tệp kết quả ở trạng thái HOP_LE"):
        await svc_tep.cho_phep_gui(identity=doc, tep_id=tep_id)

    # N2: Bác sĩ gọi duyet_ket_qua cũng bị chặn nếu chưa có tệp HOP_LE
    with pytest.raises(LuotKhamConflictError) as exc_info:
        await svc_lk.duyet_ket_qua(order_id=oid, danh_gia="Tốt", identity=doc)
    assert exc_info.value.error_code == "NO_VALID_RESULT"

    # O: Direct DB update cho_phep_gui_luc trên CHO_XAC_NHAN bị trigger chặn
    async with pool.acquire() as conn:
        with pytest.raises(
            asyncpg.RaiseError, match="Chỉ tệp kết quả ở trạng thái HOP_LE"
        ):
            await conn.execute(
                "UPDATE tep_ket_qua SET cho_phep_gui_luc = now() WHERE id = $1::uuid",
                tep_id,
            )

    # Xác nhận HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=tep_id, trang_thai="HOP_LE"
    )

    # J: Sau khi HOP_LE, bác sĩ cho_phep_gui thành công
    res_cho_gui = await svc_tep.cho_phep_gui(identity=doc, tep_id=tep_id)
    assert res_cho_gui["ok"] is True

    async with pool.acquire() as conn:
        tep_row = await conn.fetchrow(
            "SELECT cho_phep_gui_luc FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        assert tep_row["cho_phep_gui_luc"] is not None


# ==============================================================================
# SCENARIO M: CHO_QUYET VẪN THẤY EXTERNAL RESULT ĐANG CHO_XAC_NHAN
# ==============================================================================
async def test_scenario_m_cho_quyet_van_thay_cho_xac_nhan(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)

    # Khi đối tác upload: ket_qua_luc được ghi trên service_order,
    # nhưng tệp là CHO_XAC_NHAN
    pdf_bytes = PDF_DUMMY
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="t.pdf",
        service_order_id=oid,
    )

    # Bác sĩ xem cho_quyet: Khách hàng VẪN PHẢI XUẤT HIỆN trong danh sách chờ kết quả!
    # Không được biến mất chỉ vì đối tác đã upload tệp tạm.
    cho_quyet_res = await svc_lk.cho_quyet(identity=doc)
    ds_viec = cho_quyet_res["viec"]
    found = any(v["visit_id"] == vid for v in ds_viec)
    assert found is True, (
        "Khách hàng phải còn trong cho_quyet khi tệp external chưa HOP_LE!"
    )

    # Sau khi xác nhận HOP_LE -> round ready -> khách rời hàng cho_quyet
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t["id"], trang_thai="HOP_LE"
    )
    cho_quyet_sau = await svc_lk.cho_quyet(identity=doc)
    assert not any(v["visit_id"] == vid for v in cho_quyet_sau["viec"])


# ==============================================================================
# SCENARIOS P & Q: HOP_LE -> THU_HOI (AUDIT, REASON, ROLLBACK REVIEW)
# ==============================================================================
async def test_scenarios_p_q_thu_hoi_ket_qua(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)

    pdf_bytes = PDF_DUMMY
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="t.pdf",
        service_order_id=oid,
    )
    tep_id = t["id"]

    # 1. Xác nhận HOP_LE -> round ready
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=tep_id, trang_thai="HOP_LE"
    )
    async with pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "ready"
        original_xac_nhan_luc = await conn.fetchval(
            "SELECT xac_nhan_luc FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )

    # 2. THU_HOI khi REVIEW chưa bắt đầu:
    # - Bắt buộc có lý do
    with pytest.raises(ValidationError, match="bắt buộc phải có lý do"):
        await svc_tep.thu_hoi_tep(identity=staff_xac_nhan, tep_id=tep_id, ly_do="")

    # - Thu hồi thành công:
    res_th = await svc_tep.thu_hoi_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id,
        ly_do="Phát hiện đối tác gửi nhầm mẫu của bệnh nhân khác",
    )
    assert res_th["ok"] is True
    assert res_th["trang_thai"] == "THU_HOI"

    async with pool.acquire() as conn:
        tep_row = await conn.fetchrow(
            "SELECT * FROM tep_ket_qua WHERE id = $1::uuid", tep_id
        )
        assert tep_row["xac_nhan_trang_thai"] == "THU_HOI"
        # Giữ nguyên actor/thời gian xác nhận ban đầu
        assert tep_row["xac_nhan_luc"] == original_xac_nhan_luc
        assert str(tep_row["xac_nhan_boi_staff_id"]) == staff_xac_nhan.staff_id
        # Ghi riêng thông tin thu hồi
        assert tep_row["thu_hoi_luc"] is not None
        assert str(tep_row["thu_hoi_boi_staff_id"]) == staff_xac_nhan.staff_id
        assert (
            tep_row["thu_hoi_ly_do"]
            == "Phát hiện đối tác gửi nhầm mẫu của bệnh nhân khác"
        )
        # Giữ approval history khi thu hồi
        # (test này chưa approve nên vẫn NULL)
        assert tep_row["cho_phep_gui_luc"] is None

        # REVIEW round bị rút lại về 'collecting'
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE id = $1::uuid", rid
        )
        assert r_status == "collecting"

        # queue_entry bị huỷ (cancelled)
        q_cancelled = await conn.fetchval(
            "SELECT status FROM queue_entry "
            "WHERE visit_id = $1::uuid AND reason = 'REVIEW'",
            vid,
        )
        assert q_cancelled == "cancelled"

        # Q: TU_CHOI/THU_HOI không tính VALID_RESULT
        reqs = await svc_lk._yeu_cau_cua_vong(conn, CLINIC_A, rid)
        assert reqs[0]["co_ket_qua"] is False

    # 3. THU_HOI khi REVIEW ĐÃ BẮT ĐẦU -> STOP và báo ConflictError (design boundary)
    # Tạo lượt khám khác và bắt đầu khám REVIEW
    async with pool.acquire() as conn:
        pid2, aid2, vid2 = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid2 = await _tao_external_order(conn, CLINIC_A, vid2, node_code="XN_NGOAI_2")
        rid2, qid2 = await _tao_review_round_cho_order(conn, CLINIC_A, vid2, oid2)

    t2 = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid2,
        data=pdf_bytes,
        ten_hien_thi="t2.pdf",
        service_order_id=oid2,
    )
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t2["id"], trang_thai="HOP_LE"
    )

    # Bác sĩ bắt đầu REVIEW
    async with pool.acquire() as conn:
        cid2 = await conn.fetchval(
            "SELECT id::text FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            vid2,
        )
    await svc_lk.start_consultation(consultation_id=cid2, identity=doc)

    # Thử thu hồi lúc này -> PHẢI CHẶN và báo design case
    with pytest.raises(ConflictError, match="Phiên đọc kết quả đã bắt đầu"):
        await svc_tep.thu_hoi_tep(
            identity=staff_xac_nhan,
            tep_id=t2["id"],
            ly_do="Muốn thu hồi nhưng bác sĩ đang đọc",
        )


# ==============================================================================
# SCENARIO R: PARTNER STATUS LÀ "ĐÃ GỬI TỆP" DÙ VALID_RESULT=FALSE
# ==============================================================================
async def test_scenario_r_partner_status_da_gui_tep(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)
    svc_lk = LuotKhamService(pool)

    pdf_bytes = PDF_DUMMY
    await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=pdf_bytes,
        ten_hien_thi="t.pdf",
        service_order_id=oid,
    )

    # Đối tác xem việc của mình (bàn chỉ hiện việc đã nhận — 24/09/2026)
    from tests.chay_nguoi_dua_tin import danh_dau_doi_tac_da_nhan

    await danh_dau_doi_tac_da_nhan(pool, oid)
    res_dt = await svc_lk.viec_doi_tac(identity=partner)
    khach_list = res_dt["khach"]
    khach_item = next((k for k in khach_list if k["clinic_patient_id"] == pid), None)
    assert khach_item is not None
    viec_list = khach_item["viec"]
    viec_item = next((v for v in viec_list if v["chi_dinh_id"] == oid), None)
    assert viec_item is not None
    assert viec_item["trang_thai"] == "DA_GUI_KET_QUA"


# ==============================================================================
# T1: LEGACY ROWS — xac_nhan_trang_thai = NULL valid via CHECK constraint
# ==============================================================================
async def test_t1_legacy_null_valid(pool: asyncpg.Pool) -> None:
    """Rows inserted with xac_nhan_trang_thai = NULL are valid (legacy/internal)."""
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

        # Direct INSERT with NULL xac_nhan_trang_thai — must succeed
        tep_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO tep_ket_qua
                (id, clinic_id, clinic_patient_id, appointment_id,
                 khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id,
                 xac_nhan_trang_thai)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                    $5, 'ANH', 'image/jpeg', 100, 'abc123', $6::uuid,
                    NULL)
            """,
            tep_id,
            CLINIC_A,
            pid,
            aid,
            f"{CLINIC_A}/{pid}/test.jpg",
            doc.staff_id,
        )
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai, xac_nhan_luc, thu_hoi_luc "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            tep_id,
        )
        assert row["xac_nhan_trang_thai"] is None
        assert row["xac_nhan_luc"] is None
        assert row["thu_hoi_luc"] is None

        # Cleanup
        await conn.execute("DELETE FROM tep_ket_qua WHERE id = $1::uuid", tep_id)


# ==============================================================================
# T2: IMMUTABLE CONFIRMATION FIELDS — direct SQL sửa fields khi giữ state bị chặn
# ==============================================================================
async def test_t2_immutable_confirmation_fields(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """IS DISTINCT FROM trigger prevents tampering with confirmation fields."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="immutable.pdf",
        service_order_id=oid,
    )
    tep_id = t["id"]

    # Xác nhận HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=tep_id, trang_thai="HOP_LE"
    )

    async with pool.acquire() as conn:
        # Giữ state = HOP_LE nhưng sửa xac_nhan_luc không set state → trigger chặn
        with pytest.raises(asyncpg.RaiseError, match="immutable audit fields"):
            await conn.execute(
                "UPDATE tep_ket_qua SET xac_nhan_luc = now() - interval '1 day' "
                "WHERE id = $1::uuid",
                tep_id,
            )

        # Giữ state = HOP_LE nhưng sửa xac_nhan_boi_staff_id không set state → chặn
        with pytest.raises(asyncpg.RaiseError, match="immutable audit fields"):
            await conn.execute(
                "UPDATE tep_ket_qua SET xac_nhan_boi_staff_id = $1::uuid "
                "WHERE id = $2::uuid",
                doc.staff_id,
                tep_id,
            )

    # Thu hồi tệp
    await svc_tep.thu_hoi_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id,
        ly_do="Phát hiện sai sót sau khi xác nhận",
    )

    async with pool.acquire() as conn:
        # Ở state = THU_HOI, sửa thu_hoi_ly_do bằng direct SQL (không set state) → chặn
        with pytest.raises(asyncpg.RaiseError, match="immutable audit fields"):
            await conn.execute(
                "UPDATE tep_ket_qua SET thu_hoi_ly_do = 'Sửa lý do lén lút' "
                "WHERE id = $1::uuid",
                tep_id,
            )

        # Thử sửa thu_hoi_luc bằng direct SQL (không SET state) → trigger chặn
        with pytest.raises(asyncpg.RaiseError, match="immutable audit fields"):
            await conn.execute(
                "UPDATE tep_ket_qua SET thu_hoi_luc = now() - interval '2 hours' "
                "WHERE id = $1::uuid",
                tep_id,
            )


# ==============================================================================
# T3: INTERNAL / NON-ORDER FILES — xac_nhan_trang_thai = NULL via service
# ==============================================================================
async def test_t3_internal_non_order_null_state(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Internal files (no service_order OR internal order) → NULL state."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

    svc_tep = TepKetQuaService(pool)

    # Case 1: No service_order_id → NULL state
    t1 = await svc_tep.tai_len(
        identity=doc,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="internal-no-order.pdf",
        appointment_id=aid,
    )
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid",
            t1["id"],
        )
        assert row["xac_nhan_trang_thai"] is None

    # Case 2: Internal order (lam_ben_ngoai = false) → NULL state
    async with pool.acquire() as conn:
        # Tạo internal node_definition
        await conn.execute(
            """
            INSERT INTO node_definition (
                clinic_id, code, name, flow_group, workspace, lam_ben_ngoai,
                actor_roles
            )
            VALUES (
                $1::uuid, 'XN_NOI_BO_TEST_T3', 'Xét nghiệm nội bộ test', 'ket_qua',
                'khu_dieu_duong', false, ARRAY['NURSE_ULTRASOUND']
            )
            ON CONFLICT (clinic_id, code) DO UPDATE SET lam_ben_ngoai = false
            """,
            CLINIC_A,
        )
        cid = await conn.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid LIMIT 1",
            vid,
        )
        if not cid:
            cid = await conn.fetchval(
                "INSERT INTO consultation (clinic_id, visit_id, round_no, kind) "
                "VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY') RETURNING id::text",
                CLINIC_A,
                vid,
            )
        rec_by = await conn.fetchval(
            "SELECT attending_doctor_id::text FROM visit WHERE visit_id = $1::uuid",
            vid,
        )
        room_id = await conn.fetchval(
            "SELECT id::text FROM clinic_room "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1",
            CLINIC_A,
        )
        if not room_id:
            loc = await conn.fetchval(
                "SELECT id::text FROM clinic_location"
                " WHERE clinic_id = $1::uuid LIMIT 1",
                CLINIC_A,
            )
            room_id = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO clinic_room
                (id, clinic_id, location_id, name,
                 room_number, is_active)
                VALUES ($1::uuid, $2::uuid, $3::uuid, 'Test room', 'TR', true)
                ON CONFLICT (id) DO NOTHING
                """,
                room_id,
                CLINIC_A,
                loc,
            )
        internal_oid = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO service_order (
                id, clinic_id, visit_id, consultation_id, service_code, service_name,
                node_code, exec_status, recorded_by,
                authorized_by, authorized_at, room_id
            )
            VALUES (
                $1::uuid, $2::uuid, $3::uuid, $4::uuid, 'DV_NOI', 'Dịch vụ nội bộ',
                'XN_NOI_BO_TEST_T3', 'performed', $5::uuid, $5::uuid, now(), $6::uuid
            )
            """,
            internal_oid,
            CLINIC_A,
            vid,
            cid,
            rec_by,
            room_id,
        )

    t2 = await svc_tep.tai_len(
        identity=doc,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="internal-order.pdf",
        service_order_id=internal_oid,
    )
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai FROM tep_ket_qua WHERE id = $1::uuid",
            t2["id"],
        )
        assert row["xac_nhan_trang_thai"] is None


# ==============================================================================
# T4: DOCTOR UPLOADS INTERNAL FILE → AUTO cho_phep_gui
# ==============================================================================
async def test_t4_doctor_upload_auto_cho_phep_gui(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Doctor upload internal file → auto cho_phep_gui (pre-#174)."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

    svc_tep = TepKetQuaService(pool)
    t = await svc_tep.tai_len(
        identity=doc,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="doctor-upload.pdf",
        appointment_id=aid,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai, cho_phep_gui_luc,"
            " cho_phep_gui_boi_staff_id::text "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            t["id"],
        )
        assert row["xac_nhan_trang_thai"] is None
        assert row["cho_phep_gui_luc"] is not None  # Auto-approved!
        assert row["cho_phep_gui_boi_staff_id"] == doc.staff_id


# ==============================================================================
# T5: HOP_LE → THU_HOI PRESERVES DOCTOR APPROVAL HISTORY
# ==============================================================================
async def test_t5_thu_hoi_preserves_approval(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """When revoking a HOP_LE file that was doctor-approved, cho_phep_gui stays."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)

    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="t5.pdf",
        service_order_id=oid,
    )

    # CHO_XAC_NHAN → HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan, tep_id=t["id"], trang_thai="HOP_LE"
    )

    # Bác sĩ cho phép gửi
    await svc_tep.cho_phep_gui(identity=doc, tep_id=t["id"])

    async with pool.acquire() as conn:
        before = await conn.fetchrow(
            "SELECT cho_phep_gui_luc, cho_phep_gui_boi_staff_id::text "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            t["id"],
        )
        assert before["cho_phep_gui_luc"] is not None
        original_gui_luc = before["cho_phep_gui_luc"]
        original_gui_boi = before["cho_phep_gui_boi_staff_id"]

    # THU_HOI
    await svc_tep.thu_hoi_tep(
        identity=staff_xac_nhan,
        tep_id=t["id"],
        ly_do="Thu hồi nhưng giữ lịch sử approval",
    )

    async with pool.acquire() as conn:
        after = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai, cho_phep_gui_luc, "
            "cho_phep_gui_boi_staff_id::text "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            t["id"],
        )
        assert after["xac_nhan_trang_thai"] == "THU_HOI"
        # APPROVAL HISTORY PRESERVED
        assert after["cho_phep_gui_luc"] == original_gui_luc
        assert after["cho_phep_gui_boi_staff_id"] == original_gui_boi


# ==============================================================================
# T6: INTERNAL FILE danh_dau_da_gui — no HOP_LE needed
# ==============================================================================
async def test_t6_internal_danh_dau_da_gui(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Internal files can be marked as sent without needing HOP_LE state."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

    svc_tep = TepKetQuaService(pool)

    # Doctor uploads internal file → auto cho_phep_gui
    t = await svc_tep.tai_len(
        identity=doc,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="internal-sendable.pdf",
        appointment_id=aid,
    )

    # CSKH can mark it as sent — xac_nhan_trang_thai is NULL, not HOP_LE
    res = await svc_tep.danh_dau_da_gui(identity=cskh, tep_id=t["id"], kenh="ZALO")
    assert res["ok"] is True

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT gui_luc, gui_kenh, xac_nhan_trang_thai "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            t["id"],
        )
        assert row["gui_luc"] is not None
        assert row["gui_kenh"] == "ZALO"
        assert row["xac_nhan_trang_thai"] is None  # Still NULL


# ==============================================================================
# T7: NULL→CHO_XAC_NHAN via UPDATE blocked by trigger
# ==============================================================================
async def test_t7_null_to_non_null_blocked(pool: asyncpg.Pool) -> None:
    """Cannot switch a NULL (internal) file to the confirmation flow via UPDATE."""
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

        tep_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO tep_ket_qua
                (id, clinic_id, clinic_patient_id, appointment_id,
                 khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id,
                 xac_nhan_trang_thai)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                    $5, 'ANH', 'image/jpeg', 100, 'abc789', $6::uuid,
                    NULL)
            """,
            tep_id,
            CLINIC_A,
            pid,
            aid,
            f"{CLINIC_A}/{pid}/t7.jpg",
            doc.staff_id,
        )

        with pytest.raises(asyncpg.RaiseError, match="nội bộ.*NULL"):
            await conn.execute(
                "UPDATE tep_ket_qua SET xac_nhan_trang_thai = 'CHO_XAC_NHAN' "
                "WHERE id = $1::uuid",
                tep_id,
            )

        # Cleanup
        await conn.execute("DELETE FROM tep_ket_qua WHERE id = $1::uuid", tep_id)


# ==============================================================================
# T8: INTERNAL FILE APPEARS IN cho_bac_si_cho_phep QUEUE
# ==============================================================================
async def test_t8_internal_in_cho_bac_si_queue(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Internal files (NULL state) with no approval yet appear in doctor queue."""
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

    svc_tep = TepKetQuaService(pool)

    # CSKH uploads internal file → no auto cho_phep_gui (not a doctor)
    t = await svc_tep.tai_len(
        identity=cskh,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="cskh-upload.pdf",
        appointment_id=aid,
    )

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai, cho_phep_gui_luc "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            t["id"],
        )
        assert row["xac_nhan_trang_thai"] is None
        assert row["cho_phep_gui_luc"] is None  # CSKH not auto-approved

    # File should appear in doctor's approval queue
    queue = await svc_tep.cho_bac_si_cho_phep(identity=doc)
    tep_ids = [item["id"] for item in queue]
    assert t["id"] in tep_ids

    # Doctor approves
    res = await svc_tep.cho_phep_gui(identity=doc, tep_id=t["id"])
    assert res["ok"] is True

    # Now it should be gone from the queue
    queue2 = await svc_tep.cho_bac_si_cho_phep(identity=doc)
    tep_ids2 = [item["id"] for item in queue2]
    assert t["id"] not in tep_ids2


# ==============================================================================
# T9: DB MUST BLOCK SEND AFTER THU_HOI — direct SQL set gui_luc bị chặn
# ==============================================================================
async def test_t9_db_blocks_send_after_thu_hoi(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """External HOP_LE -> doctor approve -> THU_HOI -> direct SQL set gui_luc.

    Database trigger must reject the send attempt.
    Also verifies that service danh_dau_da_gui rejects.
    Approval history (cho_phep_gui_luc) is preserved, but send is blocked.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        staff_xac_nhan = await _tao_staff(
            conn, CLINIC_A, "NURSE", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)

    svc_tep = TepKetQuaService(pool)

    # 1. Partner uploads external file -> CHO_XAC_NHAN
    t = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="thu-hoi-send.pdf",
        service_order_id=oid,
    )
    tep_id = t["id"]

    # 2. Nurse confirms HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id,
        trang_thai="HOP_LE",
    )

    # 3. Doctor approves -> cho_phep_gui_luc set
    res_bs = await svc_tep.cho_phep_gui(identity=doc, tep_id=tep_id)
    assert res_bs["ok"] is True

    # 4. Nurse revokes -> THU_HOI
    await svc_tep.thu_hoi_tep(
        identity=staff_xac_nhan,
        tep_id=tep_id,
        ly_do="Phát hiện sai sót nghiêm trọng",
    )

    # Verify state in DB: xac_nhan_trang_thai = THU_HOI, cho_phep_gui_luc preserved
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT xac_nhan_trang_thai, cho_phep_gui_luc "
            "FROM tep_ket_qua WHERE id = $1::uuid",
            tep_id,
        )
        assert row["xac_nhan_trang_thai"] == "THU_HOI"
        assert row["cho_phep_gui_luc"] is not None  # Approval history preserved!

        # 5. Direct SQL attempt to set gui_luc -> DB trigger must REJECT!
        with pytest.raises(
            (asyncpg.RaiseError, asyncpg.CheckViolationError),
            match="THU_HOI.*không được phép gửi",
        ):
            await conn.execute(
                """
                UPDATE tep_ket_qua
                   SET gui_luc = now(),
                       gui_boi_staff_id = $1::uuid,
                       gui_kenh = 'ZALO'
                 WHERE id = $2::uuid
                """,
                cskh.staff_id,
                tep_id,
            )

    # 6. Service danh_dau_da_gui also rejects
    with pytest.raises(ConflictError, match="chưa ở trạng thái hợp lệ để gửi"):
        await svc_tep.danh_dau_da_gui(
            identity=cskh,
            tep_id=tep_id,
            kenh="ZALO",
        )


# ==============================================================================
# T10: DIRECT TAMPERING ON INTERNAL FILE (NULL STATE) REJECTED AT DB LEVEL
# ==============================================================================
async def test_t10_internal_direct_tamper_rejected_at_db(
    pool: asyncpg.Pool,
) -> None:
    """Internal files (NULL state) cannot be manipulated with confirmation fields."""
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        tep_id = str(uuid.uuid4())

        # Direct INSERT with NULL state but setting xac_nhan_luc -> rejected by CHECK
        with pytest.raises(
            (asyncpg.RaiseError, asyncpg.CheckViolationError),
            match="chk_tep_ket_qua_xac_nhan",
        ):
            await conn.execute(
                """
                INSERT INTO tep_ket_qua
                    (id, clinic_id, clinic_patient_id, appointment_id,
                     khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id,
                     xac_nhan_trang_thai, xac_nhan_luc)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                        $5, 'PDF', 'application/pdf', 100, 'abc', $6::uuid,
                        NULL, now())
                """,
                tep_id,
                CLINIC_A,
                pid,
                aid,
                f"{CLINIC_A}/{pid}/t10.pdf",
                doc.staff_id,
            )

        # Valid internal insert
        await conn.execute(
            """
            INSERT INTO tep_ket_qua
                (id, clinic_id, clinic_patient_id, appointment_id,
                 khoa, loai_tep, mime, so_byte, sha256, tai_len_boi_staff_id,
                 xac_nhan_trang_thai)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,
                    $5, 'PDF', 'application/pdf', 100, 'abc', $6::uuid,
                    NULL)
            """,
            tep_id,
            CLINIC_A,
            pid,
            aid,
            f"{CLINIC_A}/{pid}/t10.pdf",
            doc.staff_id,
        )

        # Direct UPDATE adding confirmation timestamp without state change -> rejected
        with pytest.raises(
            asyncpg.RaiseError, match="Tệp nội bộ.*không được có thông tin xác nhận"
        ):
            await conn.execute(
                "UPDATE tep_ket_qua SET xac_nhan_luc = now() WHERE id = $1::uuid",
                tep_id,
            )

        # Tệp NỘI BỘ gửi được mà không cần bác sĩ cho phép (Tuyền chốt
        # 23/09/2026 — luật 15/09 đã tắt ở migration 20260923000021).
        await conn.execute(
            """
            UPDATE tep_ket_qua
               SET gui_luc = now(),
                   gui_boi_staff_id = $1::uuid,
                   gui_kenh = 'ZALO'
             WHERE id = $2::uuid
            """,
            doc.staff_id,
            tep_id,
        )

        # Cleanup
        await conn.execute("DELETE FROM tep_ket_qua WHERE id = $1::uuid", tep_id)
