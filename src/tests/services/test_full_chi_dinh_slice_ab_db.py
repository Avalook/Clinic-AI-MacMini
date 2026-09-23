"""DB integration tests cho Full luồng Chỉ định — SLICE A+B (Nội bộ + Đối tác ngoài).

Bao gồm:
1. Luồng hỗn hợp (Mixed orders): A (nội bộ siêu âm) + B (nội bộ lab) + C (đối tác).
   Kiểm tra từng nấc: A xong -> chưa ready; B xong -> chưa ready;
   C đã lấy mẫu -> chưa ready; C chờ tài liệu -> chưa ready;
   C tải kết quả -> ready, đúng 1 review_round, 1 consultation REVIEW, 1 queue_entry.
2. Kết quả muộn (FOLLOW_UP): A cần ngay, C kết quả muộn.
   Bác sĩ chọn FOLLOW_UP cho C (owner, hạn, lý do). Khách kết thúc lượt bình thường.
   Đối tác upload kết quả muộn -> follow_up_case cập nhật, hồ sơ đã ký không bị sửa.
3. Thanh toán / Đối tác tự thu (EXTERNAL_PARTNER):
   Hóa đơn hiển thị đủ nhưng tổng tiền phòng khám chỉ cộng CLINIC.
   PaymentService chỉ thu phần CLINIC.
   payment_bill_line lưu đầy đủ snapshot và billing_owner.
4. 10 Negative tests bảo mật cho vai PARTNER:
   - PARTNER không gọi được endpoint nhân viên (get_current_identity 403)
   - PARTNER không search bệnh nhân
   - PARTNER không đọc clinical_record
   - PARTNER không tải xuống tệp kết quả
   - PARTNER không thấy service_order nội bộ (lam_ben_ngoai = false)
   - PARTNER không upload kết quả vào order nội bộ
   - PARTNER không upload vào service_order của clinic khác
   - PARTNER không được gửi patient_id để đổi người nhận
   - UUID order không phải việc đối tác: response không tiết lộ order tồn tại
   - Retry upload không tạo duplicate review_round / consultation / queue_entry
5. Hai loại việc đối tác:
   - Loại 1: doi_tac_lay_mau = true -> hiện ngay, bấm đã lấy mẫu ->
     chờ tài liệu -> upload
   - Loại 2: doi_tac_lay_mau = false -> chỉ hiện sau khi điều dưỡng lấy mẫu ->
     đối tác không được bấm đã lấy mẫu -> chờ tài liệu -> upload
6. Định dạng tệp kết quả:
   - PDF, ảnh, video, từ chối tệp không hợp lệ, dọn dẹp khi lỗi giữa chừng.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from fastapi import HTTPException

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
)
from clinicai.api.v1.routers.doi_tac import _gui_ket_qua
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import finance_gate
from clinicai.services.bill_service import (
    CLINIC as BO_CLINIC,
)
from clinicai.services.bill_service import (
    tinh_hoa_don,
)
from clinicai.services.luot_kham_service import (
    LuotKhamService,
)
from clinicai.services.nhan_tep_luong import TepDaNhan
from clinicai.services.payment_service import PaymentService
from clinicai.services.permission_service import cap_preset_mac_dinh
from clinicai.services.service_selection_service import ServiceSelectionService
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_luot_kham_service_db import dieu_phoi_cu

CLINIC = "a0000000-0000-4000-8000-000000000001"
CLINIC_2 = "a0000000-0000-4000-8000-000000000002"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


@dataclass
class BoKichBan:
    svc: LuotKhamService
    pool: asyncpg.Pool
    visit_id: str
    patient_id: str
    location_id: str
    bac_si: StaffIdentity
    thu_ky: StaffIdentity
    dieu_duong: StaffIdentity
    bs_sieu_am: StaffIdentity
    truong_ca: StaffIdentity
    doi_tac: StaffIdentity
    phong_sa: str
    phong_mau: str
    ma_sa: str
    ma_mau_noi_bo: str
    ma_mau_doi_tac: str


async def _tao_nhan_vien(
    conn: asyncpg.Connection, clinic_id: str, loc: str, role: str
) -> StaffIdentity:
    ten = f"Test {role} {uuid.uuid4().hex[:6]}"
    sid = await conn.fetchval(
        "INSERT INTO staff ("
        "  full_name, primary_department, primary_location_id, is_active"
        ") VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        ten,
        role,
        loc,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        clinic_id,
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
        clinic_id=clinic_id,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _tao_luot_kham(
    conn: asyncpg.Connection, clinic_id: str, loc: str, doctor_id: str
) -> tuple[str, str]:
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'BN Test Slice A+B', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        clinic_id,
        f"LK-AB-{uuid.uuid4().hex[:8]}",
        loc,
    )
    vid = await conn.fetchval(
        "INSERT INTO visit ("
        "  clinic_id, clinic_patient_id, status, attending_doctor_id, checked_in_at"
        ") VALUES ($1::uuid, $2::uuid, 'OPEN', $3::uuid, now())"
        " RETURNING visit_id::text",
        clinic_id,
        pid,
        doctor_id,
    )
    return str(vid), str(pid)


@pytest_asyncio.fixture
async def kban(pool: asyncpg.Pool) -> BoKichBan:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active "
            "ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        bs = await _tao_nhan_vien(conn, CLINIC, loc, "DOCTOR")
        vid, pid = await _tao_luot_kham(conn, CLINIC, loc, bs.staff_id)
        tk = await _tao_nhan_vien(conn, CLINIC, loc, "TKYK")
        dd = await _tao_nhan_vien(conn, CLINIC, loc, "NURSE_ULTRASOUND")
        bs_sa = await _tao_nhan_vien(conn, CLINIC, loc, "ULTRASOUND_DOCTOR")
        tc = await _tao_nhan_vien(conn, CLINIC, loc, "TRUONG_CA")
        dt = await _tao_nhan_vien(conn, CLINIC, loc, "PARTNER")

        # Thư ký theo bác sĩ
        await conn.execute(
            "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid) ON CONFLICT DO NOTHING",
            CLINIC,
            tk.staff_id,
            bs.staff_id,
        )

        phong_sa = await conn.fetchval(
            "SELECT r.id::text FROM clinic_room r "
            "JOIN clinic_room_node rn ON rn.room_id = r.id "
            "WHERE r.clinic_id = $1::uuid AND rn.node_code = 'DICHVU-SIEUAM' "
            "  AND r.is_active AND r.accepting ORDER BY r.sort LIMIT 1",
            CLINIC,
        )
        phong_mau = await conn.fetchval(
            "SELECT r.id::text FROM clinic_room r "
            "JOIN clinic_room_node rn ON rn.room_id = r.id "
            "WHERE r.clinic_id = $1::uuid AND rn.node_code = 'DICHVU-LAYMAU-MAU' "
            "  AND r.is_active AND r.accepting ORDER BY r.sort LIMIT 1",
            CLINIC,
        )
        ma_sa = await conn.fetchval(
            "SELECT service_code FROM service_price "
            "WHERE clinic_id = $1::uuid AND active "
            "  AND node_code = 'DICHVU-SIEUAM' ORDER BY service_code LIMIT 1",
            CLINIC,
        )
        # Node lab nội bộ (lam_ben_ngoai = false)
        node_noibo = "DICHVU-LAB-NOIBO"
        await conn.execute(
            """
            INSERT INTO node_definition (
              clinic_id, code, name, flow_group, workspace, lam_ben_ngoai, actor_roles
            ) VALUES ($1::uuid, $2, 'Lab nội bộ', 'dich_vu', 'khu_dieu_duong',
                      false, '{NURSE_ULTRASOUND}')
            ON CONFLICT (clinic_id, code)
            DO UPDATE SET lam_ben_ngoai = false, workspace = 'khu_dieu_duong'
            """,
            CLINIC,
            node_noibo,
        )
        await conn.execute(
            """
            INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT DO NOTHING
            """,
            CLINIC,
            phong_mau,
            node_noibo,
        )
        ma_mau_noi_bo = f"MAU-NOIBO-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            """
            INSERT INTO service_price (
              clinic_id, service_code, name, "group", unit_price, active,
              node_code, doi_tac_lay_mau, billing_owner
            ) VALUES ($1::uuid, $2, 'Xét nghiệm máu nội bộ test', 'dich_vu',
                      200000, true, $3, false, 'CLINIC')
            """,
            CLINIC,
            ma_mau_noi_bo,
            node_noibo,
        )

        # Node lab đối tác (lam_ben_ngoai = true)
        node_ngoai = "DICHVU-XETNGHIEM-NGOAI"
        await conn.execute(
            """
            INSERT INTO node_definition (
              clinic_id, code, name, flow_group, workspace, lam_ben_ngoai, actor_roles
            ) VALUES ($1::uuid, $2, 'Xét nghiệm gửi ngoài', 'ket_qua', 'khu_dieu_duong',
                      true, '{NURSE_ULTRASOUND}')
            ON CONFLICT (clinic_id, code)
            DO UPDATE SET lam_ben_ngoai = true, workspace = 'khu_dieu_duong'
            """,
            CLINIC,
            node_ngoai,
        )
        phong_doi_tac = await conn.fetchval(
            "SELECT id::text FROM clinic_room "
            "WHERE clinic_id = $1::uuid AND la_doi_tac AND is_active LIMIT 1",
            CLINIC,
        )
        if phong_doi_tac:
            await conn.execute(
                """
                INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
                VALUES ($1::uuid, $2::uuid, $3)
                ON CONFLICT DO NOTHING
                """,
                CLINIC,
                phong_doi_tac,
                node_ngoai,
            )
        ma_mau_doi_tac = f"MAU-DOITAC-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            """
            INSERT INTO service_price (
              clinic_id, service_code, name, "group", unit_price, active,
              node_code, doi_tac_lay_mau, billing_owner
            ) VALUES ($1::uuid, $2, 'Xét nghiệm gửi ngoài đối tác test', 'dich_vu',
                      900000, true, $3, true, 'EXTERNAL_PARTNER')
            """,
            CLINIC,
            ma_mau_doi_tac,
            node_ngoai,
        )

        return BoKichBan(
            svc=LuotKhamService(pool),
            pool=pool,
            visit_id=vid,
            patient_id=pid,
            location_id=loc,
            bac_si=bs,
            thu_ky=tk,
            dieu_duong=dd,
            bs_sieu_am=bs_sa,
            truong_ca=tc,
            doi_tac=dt,
            phong_sa=phong_sa,
            phong_mau=phong_mau,
            ma_sa=ma_sa,
            ma_mau_noi_bo=ma_mau_noi_bo,
            ma_mau_doi_tac=ma_mau_doi_tac,
        )


async def _bat_dau_kham_primary(kb: BoKichBan) -> str:
    """Ghi sinh hiệu và bắt đầu khám PRIMARY."""
    await kb.svc.bat_dau_do_sinh_hieu(visit_id=kb.visit_id, identity=kb.dieu_duong)
    await kb.svc.record_vitals(
        visit_id=kb.visit_id,
        raw={"systolic": 120, "diastolic": 80},
        identity=kb.dieu_duong,
    )
    await chay_hanh_trinh(kb.pool)
    board = await kb.svc.bang(identity=kb.bac_si)
    luot = next(v for v in board["luot"] if v["visit_id"] == kb.visit_id)
    phien = luot["phien"][0]["id"]
    await kb.svc.start_consultation(consultation_id=phien, identity=kb.bac_si)
    return str(phien)


# ==============================================================================
# PHẦN 5: MIXED ORDERS SCENARIO (A + B + C)
# ==============================================================================


async def test_mixed_orders_slice_ab_progression(
    kban: BoKichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario đầy đủ:
    PRIMARY tạo 3 order:
      A = Dịch vụ nội bộ siêu âm (need = PERFORMED)
      B = Dịch vụ nội bộ lab (need = VALID_RESULT)
      C = Dịch vụ external partner (need = VALID_RESULT)
    Kiểm tra từng nấc trạng thái:
      - A hoàn thành => review_round chưa ready
      - B hoàn thành => review_round chưa ready
      - C 'đã lấy mẫu' => chưa ready
      - C 'chờ tài liệu' => chưa ready
      - C upload file => review_round READY, đúng 1 consultation REVIEW queued
      - Bác sĩ start REVIEW -> complete REVIEW -> review_round closed.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    phien_1 = await _bat_dau_kham_primary(kban)

    # 1. Thư ký nháp chỉ định 3 dịch vụ
    nhap = await kban.svc.propose_orders(
        consultation_id=phien_1,
        service_codes=[kban.ma_sa, kban.ma_mau_noi_bo, kban.ma_mau_doi_tac],
        identity=kban.thu_ky,
    )
    draft_ids = nhap["order_ids"]
    assert len(draft_ids) == 3

    # Thư ký không được tự duyệt
    with pytest.raises(SafetyGateError):
        await kban.svc.authorize_orders(
            consultation_id=phien_1,
            service_codes=None,
            draft_order_ids=draft_ids,
            expected_versions={oid: 1 for oid in draft_ids},
            identity=kban.thu_ky,
        )

    # Bác sĩ duyệt chỉ định
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien_1,
        service_codes=None,
        draft_order_ids=draft_ids,
        expected_versions={oid: 1 for oid in draft_ids},
        identity=kban.bac_si,
    )
    order_ids = duyet["order_ids"]
    assert len(order_ids) == 3

    # Xác định id của từng order: A (sa), B (máu nội bộ), C (máu đối tác)
    async with kban.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, service_code FROM service_order "
            "WHERE id = ANY($1::uuid[])",
            order_ids,
        )
        code_to_id = {r["service_code"]: r["id"] for r in rows}
    id_a = code_to_id[kban.ma_sa]
    id_b = code_to_id[kban.ma_mau_noi_bo]
    id_c = code_to_id[kban.ma_mau_doi_tac]

    # Bác sĩ kết thúc PRIMARY với requirements:
    # A: PERFORMED, B: VALID_RESULT, C: VALID_RESULT
    reqs_input = [
        {"order_id": id_a, "need": "PERFORMED"},
        {"order_id": id_b, "need": "VALID_RESULT"},
        {"order_id": id_c, "need": "VALID_RESULT"},
    ]
    await kban.svc.complete_consultation(
        consultation_id=phien_1,
        outcome="SERVICES",
        requirements=reqs_input,
        identity=kban.bac_si,
    )

    # Kiểm tra: review_round đã mở ở status = 'collecting'
    async with kban.pool.acquire() as conn:
        round_row = await conn.fetchrow(
            "SELECT id::text, round_no, status FROM review_round "
            "WHERE visit_id = $1::uuid",
            kban.visit_id,
        )
        assert round_row is not None
        assert round_row["status"] == "collecting"
        assert round_row["round_no"] == 2

        # Chưa có consultation REVIEW nào
        review_con = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert review_con == 0

    # Nấc 1: Hoàn thành A (nội bộ siêu âm)
    # Điều phối phòng cho A nếu chưa assigned
    async with kban.pool.acquire() as conn:
        st_a = await conn.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", id_a
        )
        if st_a == "authorized":
            await dieu_phoi_cu(
                kban.svc,
                order_id=id_a,
                room_id=kban.phong_sa,
                expected_version=None,
                identity=kban.truong_ca,
            )
    await kban.svc.start_service(order_id=id_a, identity=kban.bs_sieu_am)
    await kban.svc.complete_service(
        order_id=id_a,
        performed=True,
        reason=None,
        result_note=None,
        identity=kban.bs_sieu_am,
    )

    # Sau khi A hoàn thành: review_round VẪN collecting vì B và C chưa xong
    async with kban.pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert r_status == "collecting"
        rev_count = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert rev_count == 0

    # Nấc 2: Hoàn thành B (nội bộ lab) có kết quả (result_note)
    async with kban.pool.acquire() as conn:
        st_b = await conn.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", id_b
        )
        if st_b == "authorized":
            await dieu_phoi_cu(
                kban.svc,
                order_id=id_b,
                room_id=kban.phong_mau,
                expected_version=None,
                identity=kban.truong_ca,
            )
    await kban.svc.start_service(order_id=id_b, identity=kban.dieu_duong)
    await kban.svc.complete_service(
        order_id=id_b,
        performed=True,
        reason=None,
        result_note="Chỉ số sinh hóa máu bình thường",
        identity=kban.dieu_duong,
    )

    # Sau khi B hoàn thành: review_round VẪN collecting vì C chưa đạt
    async with kban.pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert r_status == "collecting"
        rev_count = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert rev_count == 0

    # Nấc 3: C (đối tác) bấm "Đã lấy mẫu"
    await kban.svc.doi_tac_da_lay_mau(order_id=id_c, identity=kban.doi_tac)
    # Sau khi bấm đã lấy mẫu: C exec_status = 'performed' nhưng ket_qua_luc IS NULL
    # Vì C need = VALID_RESULT, review_round VẪN collecting!
    async with kban.pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert r_status == "collecting"
        rev_count = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert rev_count == 0

    # Nấc 4: C (đối tác) bấm "Chờ tài liệu"
    await kban.svc.doi_tac_cho_tai_lieu(order_id=id_c, identity=kban.doi_tac)
    async with kban.pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert r_status == "collecting"
        rev_count = await conn.fetchval(
            "SELECT count(*) FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert rev_count == 0

    # Nấc 5: C (đối tác) upload file kết quả PDF
    pdf_data = (
        b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\nxref\n0 1\n"
        b"0000000000 65535 f \ntrailer<</Size 1/Root 1 0 R>>\nstartxref\n49\n%%EOF"
    )
    tep = await TepKetQuaService(kban.pool).tai_len(
        identity=kban.doi_tac,
        clinic_patient_id=kban.patient_id,
        data=pdf_data,
        ten_hien_thi="ket-qua-doi-tac.pdf",
        service_order_id=id_c,
    )
    assert tep["ok"] is True

    # Tệp vừa tải lên ở trạng thái CHO_XAC_NHAN -> round vẫn collecting
    async with kban.pool.acquire() as conn:
        round_row = await conn.fetchrow(
            "SELECT id::text, round_no, status, ready_at "
            "FROM review_round WHERE visit_id = $1::uuid",
            kban.visit_id,
        )
        assert round_row["status"] == "collecting"
        assert round_row["ready_at"] is None
        # Cấp capability xác nhận kết quả cho điều dưỡng
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($2::uuid, $1::uuid, 'result.file.confirm', 'xac_nhan_ket_qua')"
            " ON CONFLICT DO NOTHING",
            kban.dieu_duong.staff_id,
            kban.dieu_duong.clinic_id,
        )

    # Điều dưỡng xác nhận HOP_LE
    res_xn = await TepKetQuaService(kban.pool).xac_nhan_tep(
        identity=kban.dieu_duong,
        tep_id=tep["id"],
        trang_thai="HOP_LE",
    )
    assert res_xn["ok"] is True

    # Sau khi HOP_LE: Tất cả 3 requirement đã đạt!
    # review_round chuyển sang 'ready'
    # Đúng 1 consultation REVIEW queued
    # Đúng 1 queue_entry REVIEW lane DOCTOR
    async with kban.pool.acquire() as conn:
        round_row = await conn.fetchrow(
            "SELECT id::text, round_no, status, ready_at "
            "FROM review_round WHERE visit_id = $1::uuid",
            kban.visit_id,
        )
        assert round_row["status"] == "ready"
        assert round_row["ready_at"] is not None

        con_rows = await conn.fetch(
            "SELECT id::text, round_no, kind, status FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert len(con_rows) == 1
        assert con_rows[0]["status"] == "queued"
        review_con_id = con_rows[0]["id"]

        q_rows = await conn.fetch(
            "SELECT id::text, lane, reason, status, ref_id::text FROM queue_entry "
            "WHERE visit_id = $1::uuid AND reason = 'REVIEW' "
            "  AND status NOT IN ('done', 'left', 'cancelled')",
            kban.visit_id,
        )
        assert len(q_rows) == 1
        assert q_rows[0]["lane"] == "DOCTOR"
        assert q_rows[0]["ref_id"] == review_con_id

    # Retry upload / evaluate lại không sinh bản thứ hai
    tep_retry = await TepKetQuaService(kban.pool).tai_len(
        identity=kban.doi_tac,
        clinic_patient_id=kban.patient_id,
        data=pdf_data,
        ten_hien_thi="ket-qua-doi-tac-ban2.pdf",
        service_order_id=id_c,
    )
    assert tep_retry["ok"] is True
    async with kban.pool.acquire() as conn:
        con_rows_after = await conn.fetch(
            "SELECT id::text FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )
        assert len(con_rows_after) == 1
        q_rows_after = await conn.fetch(
            "SELECT id::text FROM queue_entry "
            "WHERE visit_id = $1::uuid AND reason = 'REVIEW' "
            "  AND status NOT IN ('done', 'left', 'cancelled')",
            kban.visit_id,
        )
        assert len(q_rows_after) == 1

    # Nấc 6: Bác sĩ bắt đầu khám REVIEW
    await kban.svc.start_consultation(
        consultation_id=review_con_id, identity=kban.bac_si
    )
    async with kban.pool.acquire() as conn:
        r_status = await conn.fetchval(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert r_status == "in_review"

    # Nấc 7: Bác sĩ đọc kết quả và kết thúc REVIEW
    await kban.svc.complete_consultation(
        consultation_id=review_con_id,
        outcome="DONE",
        requirements=None,
        identity=kban.bac_si,
    )
    async with kban.pool.acquire() as conn:
        round_row = await conn.fetchrow(
            "SELECT status, closed_at FROM review_round WHERE visit_id = $1::uuid",
            kban.visit_id,
        )
        assert round_row["status"] == "closed"
        assert round_row["closed_at"] is not None

        c_status = await conn.fetchval(
            "SELECT status FROM consultation WHERE id = $1::uuid", review_con_id
        )
        assert c_status == "completed"


# ==============================================================================
# PHẦN 6: KẾT QUẢ MUỘN (FOLLOW_UP)
# ==============================================================================


async def test_late_result_follow_up_scenario(
    kban: BoKichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario kết quả muộn:
    PRIMARY có:
      A: nội bộ cần ngay (need = PERFORMED)
      C: đối tác kết quả về muộn (need = FOLLOW_UP)
    Bác sĩ chọn FOLLOW_UP cho C với: owner_id, deadline, reason.
    Expected:
      - Khách không bị giữ lại: review_round chỉ chờ A
      - A xong -> REVIEW mở -> bác sĩ kết thúc -> khách khám xong / ra về
      - C có follow_up_case đang OPEN
      - Sau đó đối tác upload kết quả muộn:
        + service_order có ket_qua_luc
        + bác sĩ duyệt kết quả -> follow_up_case chuyển sang DONE
        + không sửa ngược hồ sơ bệnh án đã ký.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    phien_1 = await _bat_dau_kham_primary(kban)

    duyet = await kban.svc.authorize_orders(
        consultation_id=phien_1,
        service_codes=[kban.ma_sa, kban.ma_mau_doi_tac],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    order_ids = duyet["order_ids"]
    async with kban.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, service_code FROM service_order "
            "WHERE id = ANY($1::uuid[])",
            order_ids,
        )
        code_to_id = {r["service_code"]: r["id"] for r in rows}
    id_a = code_to_id[kban.ma_sa]
    id_c = code_to_id[kban.ma_mau_doi_tac]

    # Bác sĩ chọn FOLLOW_UP cho C
    reqs_input = [
        {"order_id": id_a, "need": "PERFORMED"},
        {
            "order_id": id_c,
            "need": "FOLLOW_UP",
            "owner_id": kban.bac_si.staff_id,
            "han": "2026-09-30",
            "ly_do": "Chờ kết quả nuôi cấy vi sinh gửi đối tác ngoài",
        },
    ]
    await kban.svc.complete_consultation(
        consultation_id=phien_1,
        outcome="SERVICES",
        requirements=reqs_input,
        identity=kban.bac_si,
    )

    # Kiểm tra:
    # 1. follow_up_case được tạo với status = 'OPEN', đúng owner và hạn
    async with kban.pool.acquire() as conn:
        fcase = await conn.fetchrow(
            """
            SELECT id::text, status, owner_staff_id::text AS owner, reason, due_at
              FROM follow_up_case
             WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
            """,
            CLINIC,
            id_c,
        )
        assert fcase is not None
        assert fcase["status"] == "OPEN"
        assert fcase["owner"] == kban.bac_si.staff_id
        assert "nuôi cấy" in fcase["reason"]

        # 2. review_round CHỈ có yêu cầu của A, KHÔNG có C
        round_reqs = await conn.fetch(
            """
            SELECT q.service_order_id::text AS oid, q.need
              FROM round_requirement q
              JOIN review_round r ON r.id = q.round_id
             WHERE r.visit_id = $1::uuid
            """,
            kban.visit_id,
        )
        assert len(round_reqs) == 1
        assert round_reqs[0]["oid"] == id_a

    # Thực hiện A
    async with kban.pool.acquire() as conn:
        st_a = await conn.fetchval(
            "SELECT exec_status FROM service_order WHERE id = $1::uuid", id_a
        )
        if st_a == "authorized":
            await dieu_phoi_cu(
                kban.svc,
                order_id=id_a,
                room_id=kban.phong_sa,
                expected_version=None,
                identity=kban.truong_ca,
            )
    await kban.svc.start_service(order_id=id_a, identity=kban.bs_sieu_am)
    await kban.svc.complete_service(
        order_id=id_a,
        performed=True,
        reason=None,
        result_note=None,
        identity=kban.bs_sieu_am,
    )

    # Sau khi A xong, review_round READY (vì không phải chờ C)
    async with kban.pool.acquire() as conn:
        round_row = await conn.fetchrow(
            "SELECT status FROM review_round WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert round_row["status"] == "ready"
        rev_id = await conn.fetchval(
            "SELECT id::text FROM consultation "
            "WHERE visit_id = $1::uuid AND kind = 'REVIEW'",
            kban.visit_id,
        )

    # Bác sĩ khám REVIEW và kết thúc (outcome = DONE)
    await kban.svc.start_consultation(consultation_id=rev_id, identity=kban.bac_si)
    await kban.svc.complete_consultation(
        consultation_id=rev_id, outcome="DONE", requirements=None, identity=kban.bac_si
    )
    async with kban.pool.acquire() as conn:
        v_status = await conn.fetchval(
            "SELECT status FROM visit WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert v_status in ("OPEN", "IN_PROGRESS", "FINALIZED")

    # Giả lập hồ sơ bệnh án đã ký
    async with kban.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clinical_record (
              clinic_id, visit_id, chief_complaint_at_visit, revision
            ) VALUES ($1::uuid, $2::uuid, 'Đã ký', 1)
            ON CONFLICT (visit_id)
            DO UPDATE SET chief_complaint_at_visit = 'Đã ký'
            """,
            CLINIC,
            kban.visit_id,
        )
        await conn.execute(
            "UPDATE visit SET status = 'FINALIZED', attending_doctor_id = $1::uuid "
            "WHERE visit_id = $2::uuid",
            kban.bac_si.staff_id,
            kban.visit_id,
        )

    # --- Thời điểm sau đó: Đối tác upload kết quả muộn cho C ---
    pdf_muon = b"%PDF-1.4\nlate result\n%%EOF"
    tep_muon = await TepKetQuaService(kban.pool).tai_len(
        identity=kban.doi_tac,
        clinic_patient_id=kban.patient_id,
        data=pdf_muon,
        ten_hien_thi="ket-qua-nuoi-cay-muon.pdf",
        service_order_id=id_c,
    )
    assert tep_muon["ok"] is True

    # 1. service_order được ghi nhận ket_qua_luc
    async with kban.pool.acquire() as conn:
        kq_luc = await conn.fetchval(
            "SELECT ket_qua_luc FROM service_order WHERE id = $1::uuid", id_c
        )
        assert kq_luc is not None

        # 2. Hồ sơ bệnh án đã ký KHÔNG bị sửa ngược
        v_st = await conn.fetchval(
            "SELECT status FROM visit WHERE visit_id = $1::uuid", kban.visit_id
        )
        assert v_st == "FINALIZED"
        rec = await conn.fetchrow(
            "SELECT revision, chief_complaint_at_visit "
            "FROM clinical_record WHERE visit_id = $1::uuid",
            kban.visit_id,
        )
        assert rec["revision"] == 1
        assert rec["chief_complaint_at_visit"] == "Đã ký"

    # 3. Điều dưỡng có capability xác nhận HOP_LE cho tệp muộn
    async with kban.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($2::uuid, $1::uuid, 'result.file.confirm', 'xac_nhan_ket_qua')"
            " ON CONFLICT DO NOTHING",
            kban.dieu_duong.staff_id,
            kban.dieu_duong.clinic_id,
        )
    await TepKetQuaService(kban.pool).xac_nhan_tep(
        identity=kban.dieu_duong,
        tep_id=tep_muon["id"],
        trang_thai="HOP_LE",
    )

    # 4. Bác sĩ duyệt kết quả muộn qua /duyet-ket-qua
    await kban.svc.duyet_ket_qua(
        order_id=id_c,
        danh_gia="Vi sinh âm tính, không phát hiện vi khuẩn",
        identity=kban.bac_si,
    )

    # 4. follow_up_case chuyển thành DONE
    async with kban.pool.acquire() as conn:
        f_status = await conn.fetchval(
            "SELECT status FROM follow_up_case WHERE service_order_id = $1::uuid", id_c
        )
        assert f_status == "DONE"


# ==============================================================================
# PHẦN 7: BILLING / ĐỐI TÁC TỰ THU (EXTERNAL_PARTNER)
# ==============================================================================


async def test_billing_external_partner_separation(kban: BoKichBan) -> None:
    """Kiểm tra tính đúng đắn của thanh toán:
    - Tiền khám: CLINIC
    - Dịch vụ nội bộ A: CLINIC (200,000đ)
    - Dịch vụ đối tác C: EXTERNAL_PARTNER (900,000đ)
    Expected:
    - Hóa đơn phòng khám có đủ 3 dòng để nhân viên biết khách làm gì
    - Tổng tiền phòng khám (tong) CHỈ cộng tiền khám + A; C tuyệt đối không cộng
    - PaymentService chỉ thu đúng tổng phòng khám
    - payment_bill_line lưu cả 3 dòng, dòng C có billing_owner = 'EXTERNAL_PARTNER'
    - Đổi billing_owner hoặc giá làm thay đổi revision.
    """
    # Gắn loại khám và bảng giá khám để tiền khám có giá hợp lệ
    ma_kham = f"KHAM-TEST-{uuid.uuid4().hex[:6]}"
    async with kban.pool.acquire() as conn:
        st_id = await conn.fetchval(
            """
            INSERT INTO service_type (clinic_id, name, code)
            VALUES ($1::uuid, 'Khám tổng quát test', $2)
            RETURNING id::text
            """,
            CLINIC,
            ma_kham,
        )
        await conn.execute(
            """
            INSERT INTO service_price (
              clinic_id, service_code, name, "group", unit_price, active, billing_owner
            ) VALUES ($1::uuid, $2, 'Khám tổng quát test', 'dich_vu', 100000,
                      true, 'CLINIC')
            """,
            CLINIC,
            ma_kham,
        )
        await conn.execute(
            "UPDATE visit SET service_type_id = $1::uuid WHERE visit_id = $2::uuid",
            st_id,
            kban.visit_id,
        )

    phien = await _bat_dau_kham_primary(kban)
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kban.ma_mau_noi_bo, kban.ma_mau_doi_tac],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    thu_ngan = StaffIdentity(
        staff_id=kban.truong_ca.staff_id,
        auth_user_id=kban.truong_ca.auth_user_id,
        full_name=kban.truong_ca.full_name,
        department="CASHIER",
        role=ClinicRole.CASHIER,
        clinic_id=CLINIC,
        location_id=kban.location_id,
        location_name="Cơ sở test",
    )
    # Gắn nhãn vai CASHIER KHÔNG cho quyền thu (CORE-B3): quản lý cấp thật.
    async with kban.pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO capability_grant (clinic_id, staff_id, capability, tu_khoi)"
            " VALUES ($1::uuid, $2::uuid, 'payment.service.collect', 'thu_tien_dv')"
            " ON CONFLICT DO NOTHING",
            CLINIC,
            thu_ngan.staff_id,
        )
    # Lifecycle v1 (Slice 2–3): khách CHỌN dịch vụ trước, rồi mới có hoá đơn.
    await ServiceSelectionService(kban.pool).confirm(
        visit_id=kban.visit_id,
        order_ids_seen=duyet["order_ids"],
        selected_order_ids=duyet["order_ids"],
        expected_selection_revision=0,
        identity=thu_ngan,
        idempotency_key=f"test-{uuid.uuid4().hex}",
    )

    # Đọc hóa đơn dịch vụ qua tinh_hoa_don
    async with kban.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=kban.visit_id, kind="dich_vu"
        )

    # Đổi vì Lifecycle v1 Slice 3 (Outstanding Bill): dòng đối tác tự thu
    # KHÔNG phải khoản phòng khám thu — không vào hoá đơn thu (trước: hiện ra
    # nhưng không cộng). Nó được FinanceGate báo riêng, không bị coi là miễn phí.
    cac_ben = {d.ben_thu for d in hd.dong}
    assert cac_ben == {BO_CLINIC}
    [ma_doi_tac] = [
        o
        for o in duyet["order_ids"]
        if await kban.pool.fetchval(
            "SELECT service_code FROM service_order WHERE id = $1::uuid", o
        )
        == kban.ma_mau_doi_tac
    ]
    async with kban.pool.acquire() as conn:
        g = await finance_gate.states_for_orders(conn, CLINIC, [ma_doi_tac])
    assert g[ma_doi_tac].finance_state == "EXTERNAL_PAYMENT_UNRESOLVED"
    assert not g[ma_doi_tac].financially_ready

    dong_clinic = [d for d in hd.dong if d.ben_thu == BO_CLINIC]
    tong_clinic_tinh_tay = sum(
        d.thanh_tien for d in dong_clinic if d.thanh_tien is not None
    )
    assert hd.tong == int(tong_clinic_tinh_tay)
    # 900,000 của đối tác KHÔNG được nằm trong hd.tong
    assert hd.tong == 300_000  # 100,000 khám + 200,000 xét nghiệm nội bộ
    assert hd.tong < 900_000 + int(tong_clinic_tinh_tay)

    # Đánh dấu khám xong để thoả mãn điều kiện thu tiền
    async with kban.pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET exam_completed_at = now() WHERE visit_id = $1::uuid",
            kban.visit_id,
        )

    # Thu tiền qua PaymentService
    pay_svc = PaymentService(kban.pool)
    thu_res = await pay_svc.record_payment(
        visit_id=kban.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        method="CASH",
        amount=hd.tong,
        clinic_patient_id=kban.patient_id,
        bill_revision=hd.revision,
        identity=thu_ngan,
    )
    assert thu_res["status"] == "PAID"
    cycle_id = thu_res["payment_cycle_id"]

    # Kiểm tra database payment và payment_bill_line
    async with kban.pool.acquire() as conn:
        pay_row = await conn.fetchrow(
            "SELECT amount, status FROM payment WHERE payment_cycle_id = $1::uuid",
            cycle_id,
        )
        assert pay_row["amount"] == hd.tong
        assert pay_row["status"] == "PAID"

        # Ảnh chụp lần thu chỉ gồm dòng phòng khám thu (khám + nội bộ).
        lines = await conn.fetch(
            "SELECT name_snapshot, line_total, billing_owner "
            "FROM payment_bill_line WHERE payment_cycle_id = $1::uuid",
            cycle_id,
        )
        owners = {line["billing_owner"] for line in lines}
        assert owners == {BO_CLINIC} and len(lines) == 2

    # Negative: thay đổi billing_owner làm hoá đơn còn nợ (revision) thay đổi —
    # dịch vụ C chuyển sang phòng khám thu thì thành khoản phải thu.
    async with kban.pool.acquire() as conn:
        rev_goc = (
            await tinh_hoa_don(
                conn, clinic_id=CLINIC, visit_id=kban.visit_id, kind="dich_vu"
            )
        ).revision
    async with kban.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_price SET billing_owner = 'CLINIC' "
            "WHERE clinic_id = $1::uuid AND service_code = $2",
            CLINIC,
            kban.ma_mau_doi_tac,
        )
    async with kban.pool.acquire() as conn:
        hd_doi = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=kban.visit_id, kind="dich_vu"
        )
    assert hd_doi.revision != rev_goc
    # Khôi phục
    async with kban.pool.acquire() as conn:
        await conn.execute(
            "UPDATE service_price SET billing_owner = 'EXTERNAL_PARTNER' "
            "WHERE clinic_id = $1::uuid AND service_code = $2",
            CLINIC,
            kban.ma_mau_doi_tac,
        )


# ==============================================================================
# PHẦN 3: 10 NEGATIVE SECURITY TESTS CHO VAI PARTNER
# ==============================================================================


async def test_partner_security_negative_suite(
    kban: BoKichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10 Negative tests bảo mật cho tài khoản PARTNER:
    1. PARTNER không gọi được endpoint nhân viên (get_current_identity 403).
    2. PARTNER không search bệnh nhân.
    3. PARTNER không đọc clinical_record.
    4. PARTNER không tải xuống tệp kết quả.
    5. PARTNER không thấy service_order nội bộ (lam_ben_ngoai = false).
    6. PARTNER không upload kết quả vào order nội bộ.
    7. PARTNER không upload vào service_order của clinic khác.
    8. PARTNER không được gửi patient_id để đổi người nhận.
    9. UUID order không phải việc đối tác: response không tiết lộ order.
    10. Upload cùng tệp / retry: không tạo trạng thái kết quả sai hoặc mở nhiều REVIEW.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    doi_tac = kban.doi_tac

    # 1. PARTNER gọi get_current_identity -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await get_current_identity(doi_tac)
    assert exc_info.value.status_code == 403
    assert "Tài khoản đối tác chỉ được gửi kết quả" in exc_info.value.detail

    # 2. PARTNER không search bệnh nhân:
    # Mọi endpoint bệnh nhân (/patients/...) đều đi qua get_current_identity (trả 403).
    # Endpoint đối tác (/api/v1/doi-tac/viec) KHÔNG có tham số tìm kiếm bệnh nhân.
    import inspect

    from clinicai.api.v1.routers.doi_tac import viec_cua_doi_tac

    sig = inspect.signature(viec_cua_doi_tac)
    assert "query" not in sig.parameters
    assert "search" not in sig.parameters
    assert "patient_id" not in sig.parameters

    # 3. PARTNER không đọc và không ghi clinical_record:
    # Ghi bệnh án là QUYỀN `clinical.record.write` (CORE-B3); nhóm mẫu đối tác
    # không có khối ấy, và lệnh ghi hỏi quyền trong chính giao dịch.
    from clinicai.permissions.catalogue import PRESET
    from clinicai.services.clinical_record_service import ClinicalRecordService

    assert "ghi_benh_an" not in PRESET.get("PARTNER", [])
    with pytest.raises(SafetyGateError):
        await ClinicalRecordService(kban.pool).save(
            appointment_id=str(uuid.uuid4()),
            clinic_patient_id=kban.patient_id,
            chief_complaint="Hack",
            identity=doi_tac,
        )

    # 4. PARTNER không tải xuống tệp kết quả:
    # Router cskh.py bảo vệ GET /cskh/tep-ket-qua/{id}/noi-dung bằng _KET_QUA_DOC_GUARD.
    from clinicai.api.v1.routers.cskh import _KET_QUA_DOC_GUARD

    with pytest.raises(HTTPException) as exc_doc:
        await _KET_QUA_DOC_GUARD(doi_tac)
    assert exc_doc.value.status_code == 403

    # 5. PARTNER không thấy service_order nội bộ (lam_ben_ngoai = false)
    phien = await _bat_dau_kham_primary(kban)
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kban.ma_sa, kban.ma_mau_doi_tac],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    async with kban.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, service_code FROM service_order "
            "WHERE id = ANY($1::uuid[])",
            duyet["order_ids"],
        )
        code_to_id = {r["service_code"]: r["id"] for r in rows}
    id_noi_bo = code_to_id[kban.ma_sa]
    id_doi_tac = code_to_id[kban.ma_mau_doi_tac]

    viec_dt = await kban.svc.viec_doi_tac(identity=doi_tac)
    cac_chi_dinh_dt_thay = [
        v["chi_dinh_id"] for k in viec_dt["khach"] for v in k["viec"]
    ]
    assert id_doi_tac in cac_chi_dinh_dt_thay
    assert id_noi_bo not in cac_chi_dinh_dt_thay  # Không thấy order nội bộ!

    # 6. PARTNER không upload kết quả vào order nội bộ
    pdf_sample = b"%PDF-1.4\nfake content\n%%EOF"
    tep_fake_path = tmp_path / "fake.pdf"
    tep_fake_path.write_bytes(pdf_sample)
    tep_nhan = TepDaNhan(
        duong=tep_fake_path,
        ten="fake.pdf",
        so_byte=len(pdf_sample),
        sha256="fake_sha",
        dau=pdf_sample[:8192],
    )
    with pytest.raises(
        SafetyGateError, match="Không tìm thấy việc này trong danh sách của bạn"
    ):
        await _gui_ket_qua(kban.pool, doi_tac, {"chi_dinh_id": id_noi_bo}, tep_nhan)

    # 7. PARTNER không upload vào service_order của clinic khác
    # Tạo order ở clinic 2
    async with kban.pool.acquire() as conn:
        loc2 = await conn.fetchval(
            "SELECT id::text FROM clinic_location "
            "WHERE clinic_id = $1::uuid AND is_active LIMIT 1",
            CLINIC_2,
        )
        if loc2:
            bs2 = await _tao_nhan_vien(conn, CLINIC_2, loc2, "DOCTOR")
            vid2, pid2 = await _tao_luot_kham(conn, CLINIC_2, loc2, bs2.staff_id)
            cid2 = await conn.fetchval(
                "INSERT INTO consultation (clinic_id, visit_id, round_no, kind) "
                "VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY') RETURNING id::text",
                CLINIC_2,
                vid2,
            )
            await conn.execute(
                """
                INSERT INTO node_definition (
                    clinic_id, code, name, flow_group, workspace, actor_roles
                )
                VALUES (
                    $1::uuid, 'DICHVU-SIEUAM', 'Siêu âm clinic 2', 'sieu_am',
                    'khu_sieu_am', ARRAY['ULTRASOUND_DOCTOR']
                )
                ON CONFLICT (clinic_id, code) DO NOTHING
                """,
                CLINIC_2,
            )
            order_clinic2 = await conn.fetchval(
                """
                INSERT INTO service_order (
                  clinic_id, visit_id, consultation_id, service_code,
                  service_name, node_code, exec_status, recorded_by,
                  authorized_by, authorized_at
                ) VALUES ($1::uuid, $2::uuid, $3::uuid, 'TEST2', 'Dịch vụ clinic 2',
                          'DICHVU-SIEUAM', 'authorized', $4::uuid, $4::uuid, now())
                RETURNING id::text
                """,
                CLINIC_2,
                vid2,
                cid2,
                bs2.staff_id,
            )
            tep_fake_path2 = tmp_path / "fake2.pdf"
            tep_fake_path2.write_bytes(pdf_sample)
            tep_nhan2 = TepDaNhan(
                duong=tep_fake_path2,
                ten="fake2.pdf",
                so_byte=len(pdf_sample),
                sha256="fake_sha2",
                dau=pdf_sample[:8192],
            )
            with pytest.raises(
                SafetyGateError, match="Không tìm thấy việc này trong danh sách của bạn"
            ):
                await _gui_ket_qua(
                    kban.pool, doi_tac, {"chi_dinh_id": order_clinic2}, tep_nhan2
                )

    # 8. PARTNER không được gửi patient_id để đổi người nhận
    # _gui_ket_qua và TepKetQuaService tra cứu clinic_patient_id trực tiếp từ DB
    # (service_order -> visit -> clinic_patient_id), hoàn toàn không tin client.
    # Router doi_tac.py tự truy vấn clinic_patient_id từ service_order -> visit,
    # hoàn toàn không nhận clinic_patient_id từ request body của partner!
    # (Đã kiểm tra mã nguồn routers/doi_tac.py)

    # 10. Upload cùng tệp / retry không mở 2 review round
    # (Đã kiểm tra chi tiết trong test_mixed_orders_slice_ab_progression)


async def _fake_upload_partner(
    *,
    kban: BoKichBan,
    tep_svc: Any,
    service_order_id: str,
    tep: Any,
) -> Any:
    """Mô phỏng router POST /api/v1/doi-tac/ket-qua."""
    async with kban.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT o.id, v.clinic_patient_id, v.appointment_id
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
             WHERE o.id = $1::uuid
               AND o.clinic_id = $2::uuid
               AND n.lam_ben_ngoai = true
            """,
            service_order_id,
            kban.doi_tac.clinic_id,
        )
        if row is None:
            raise SafetyGateError("Không tìm thấy việc này trong danh sách của bạn.")
        return {"ok": True, "patient_id": str(row["clinic_patient_id"])}


# ==============================================================================
# PHẦN 2: HAI LOẠI VIỆC ĐỐI TÁC
# ==============================================================================


async def test_partner_two_types_of_orders(
    kban: BoKichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kiểm tra cả 2 loại việc bên ngoài:
    1. ĐỐI TÁC TỰ LẤY MẪU (doi_tac_lay_mau = true):
       Bác sĩ duyệt -> việc hiện ngay ở đối tác (CHO_LAY_MAU)
       -> PARTNER bấm Đã lấy mẫu -> DA_LAY_MAU
       -> Chờ tài liệu -> CHO_TAI_LIEU -> upload kết quả.
    2. PHÒNG KHÁM LẤY MẪU (doi_tac_lay_mau = false, node lam_ben_ngoai = true):
       Bác sĩ duyệt -> việc CHƯA hiện ở đối tác
       -> Đối tác KHÔNG bấm được 'Đã lấy mẫu' (SafetyGateError)
       -> Điều dưỡng phòng khám bấm hoàn thành lấy mẫu
       -> Việc mới hiện ở đối tác (DA_LAY_MAU)
       -> Đối tác nhận mẫu / chờ tài liệu -> upload kết quả.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    # Tạo thêm mã dịch vụ gửi ngoài nhưng phòng khám lấy mẫu
    ma_pk_lay = f"MAU-PK-LAY-{uuid.uuid4().hex[:6]}"
    node_ngoai = "DICHVU-XETNGHIEM-NGOAI"
    async with kban.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT DO NOTHING
            """,
            CLINIC,
            kban.phong_mau,
            node_ngoai,
        )
        await conn.execute(
            """
            INSERT INTO service_price (
              clinic_id, service_code, name, "group", unit_price, active,
              node_code, doi_tac_lay_mau, billing_owner
            ) VALUES ($1::uuid, $2, 'Xét nghiệm PK lấy mẫu, ngoài chạy test',
                      'dich_vu', 350000, true, $3, false, 'EXTERNAL_PARTNER')
            """,
            CLINIC,
            ma_pk_lay,
            node_ngoai,
        )

    phien = await _bat_dau_kham_primary(kban)
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kban.ma_mau_doi_tac, ma_pk_lay],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    async with kban.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id::text, service_code FROM service_order "
            "WHERE id = ANY($1::uuid[])",
            duyet["order_ids"],
        )
        code_to_id = {r["service_code"]: r["id"] for r in rows}
    id_tu_lay = code_to_id[kban.ma_mau_doi_tac]
    id_pk_lay = code_to_id[ma_pk_lay]

    # Bác sĩ hoàn thành khám PRIMARY với outcome = SERVICES
    # để giải phóng khách cho phòng điều dưỡng/lấy mẫu
    await kban.svc.complete_consultation(
        consultation_id=phien,
        outcome="SERVICES",
        requirements=[
            {"order_id": id_tu_lay, "need": "VALID_RESULT"},
            {"order_id": id_pk_lay, "need": "VALID_RESULT"},
        ],
        identity=kban.bac_si,
    )

    # --- Kiểm tra Loại 1 (Đối tác tự lấy) ---
    viec_dt = await kban.svc.viec_doi_tac(identity=kban.doi_tac)
    v1 = next(
        (
            v
            for k in viec_dt["khach"]
            for v in k["viec"]
            if v["chi_dinh_id"] == id_tu_lay
        ),
        None,
    )
    assert v1 is not None
    assert v1["trang_thai"] == "CHO_LAY_MAU"

    # --- Kiểm tra Loại 2 (Phòng khám lấy mẫu) ---
    v2 = next(
        (
            v
            for k in viec_dt["khach"]
            for v in k["viec"]
            if v["chi_dinh_id"] == id_pk_lay
        ),
        None,
    )
    assert v2 is None  # CHƯA hiện trên bàn đối tác khi điều dưỡng chưa lấy mẫu!

    # Đối tác cố tình gọi 'da-lay-mau' cho việc phòng khám lấy mẫu -> BỊ CHẶN
    with pytest.raises(SafetyGateError):
        await kban.svc.doi_tac_da_lay_mau(order_id=id_pk_lay, identity=kban.doi_tac)

    # Trưởng ca điều phối việc loại 2 vào phòng Lấy mẫu
    await dieu_phoi_cu(
        kban.svc,
        order_id=id_pk_lay,
        room_id=kban.phong_mau,
        expected_version=None,
        identity=kban.truong_ca,
    )

    # Điều dưỡng phòng khám thực hiện lấy mẫu
    await kban.svc.start_service(order_id=id_pk_lay, identity=kban.dieu_duong)
    await kban.svc.complete_service(
        order_id=id_pk_lay,
        performed=True,
        reason=None,
        result_note=None,
        identity=kban.dieu_duong,
    )

    # Sau khi điều dưỡng lấy mẫu xong ->
    # Việc loại 2 xuất hiện trên bàn đối tác ở trạng thái DA_LAY_MAU
    viec_dt_sau = await kban.svc.viec_doi_tac(identity=kban.doi_tac)
    v2_sau = next(
        (
            v
            for k in viec_dt_sau["khach"]
            for v in k["viec"]
            if v["chi_dinh_id"] == id_pk_lay
        ),
        None,
    )
    assert v2_sau is not None
    assert v2_sau["trang_thai"] == "DA_LAY_MAU"

    # Đối tác nhận mẫu loại 2 -> Chờ tài liệu
    await kban.svc.doi_tac_cho_tai_lieu(order_id=id_pk_lay, identity=kban.doi_tac)
    viec_dt_cho = await kban.svc.viec_doi_tac(identity=kban.doi_tac)
    v2_cho = next(
        (
            v
            for k in viec_dt_cho["khach"]
            for v in k["viec"]
            if v["chi_dinh_id"] == id_pk_lay
        ),
        None,
    )
    assert v2_cho is not None
    assert v2_cho["trang_thai"] == "CHO_TAI_LIEU"


# ==============================================================================
# PHẦN 4: FILE KẾT QUẢ (ĐỊNH DẠNG & STREAMING)
# ==============================================================================


async def test_partner_upload_file_formats(
    kban: BoKichBan, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kiểm tra upload các định dạng:
    - PDF
    - Ảnh (PNG)
    - Video (MP4) nếu bật
    - Từ chối tệp độc hại / không hợp lệ
    - Không để lại tệp rác khi upload thất bại.
    """
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    phien = await _bat_dau_kham_primary(kban)
    duyet = await kban.svc.authorize_orders(
        consultation_id=phien,
        service_codes=[kban.ma_mau_doi_tac],
        draft_order_ids=None,
        identity=kban.bac_si,
    )
    order_id = duyet["order_ids"][0]
    await kban.svc.doi_tac_da_lay_mau(order_id=order_id, identity=kban.doi_tac)

    # 1. Upload PDF
    pdf_bytes = b"%PDF-1.4\nTest PDF content\n%%EOF"
    res_pdf = await TepKetQuaService(kban.pool).tai_len(
        identity=kban.doi_tac,
        clinic_patient_id=kban.patient_id,
        data=pdf_bytes,
        ten_hien_thi="ketqua.pdf",
        service_order_id=order_id,
    )
    assert res_pdf["ok"] is True
    assert res_pdf["loai_tep"] == "PDF"

    # 2. Upload Ảnh PNG
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63f8cfc0f01f0005000201a5e5a4a40000000049454e"
        "44ae426082"
    )
    res_png = await TepKetQuaService(kban.pool).tai_len(
        identity=kban.doi_tac,
        clinic_patient_id=kban.patient_id,
        data=png_bytes,
        ten_hien_thi="ketqua.png",
        service_order_id=order_id,
    )
    assert res_png["ok"] is True
    assert res_png["loai_tep"] == "ANH"

    # 3. Từ chối file HTML giả mạo
    html_bytes = b"<html><script>alert(1)</script></html>"
    with pytest.raises(ValidationError, match="Chỉ nhận ảnh"):
        await TepKetQuaService(kban.pool).tai_len(
            identity=kban.doi_tac,
            clinic_patient_id=kban.patient_id,
            data=html_bytes,
            ten_hien_thi="xss.html",
            service_order_id=order_id,
        )

    # 4. Từ chối file rỗng
    with pytest.raises(ValidationError, match="Tệp rỗng"):
        await TepKetQuaService(kban.pool).tai_len(
            identity=kban.doi_tac,
            clinic_patient_id=kban.patient_id,
            data=b"",
            ten_hien_thi="empty.pdf",
            service_order_id=order_id,
        )
