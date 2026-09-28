"""End-to-end integration & smoke tests for merged PR #174 and PR #175 on main.

Xác minh tính tương thích và hội tụ của 2 tính năng:
1. Xác nhận tệp kết quả (Blocker 1), Capability ket_qua.xac_nhan, Quản lý cấp/thu hồi
   tại màn Nhân sự (PR #174).
2. Kê đơn thuốc theo catalog (drug_catalog_id), thanh toán thuốc đơn giản không chờ kho,
   và chốt an toàn không tính 0đ cho thuốc ngoài danh mục (PR #175).
3. ĐIỂM GIAO NHAU CỐT LÕI:
   - Lượt khám có chỉ định ngoài chờ kết quả (lam_ben_ngoai = true).
   - Bác sĩ kê đơn thuốc catalog.
   - Bác sĩ kết thúc phiên 1 (outcome="SERVICES") -> HANDOFF: visit vẫn OPEN,
     đơn thuốc giữ nguyên drug_catalog_id.
   - File kết quả về (CHO_XAC_NHAN), nhân viên có capability xác nhận HOP_LE.
   - Bác sĩ mở phiên REVIEW, duyệt cho phép gửi file (cho_phep_gui).
   - Bác sĩ hoàn tất bệnh án, bấm Khám xong phiên 2 (outcome="DONE") -> TERMINAL:
     visit kết thúc, exam_completed_at có giá trị,
     đơn thuốc vẫn giữ nguyên drug_catalog_id.
   - Lễ tân thấy hóa đơn tiền thuốc đủ điều kiện thu,
     thực hiện thu CASH thành công (PAID).
"""

from __future__ import annotations

import os
import pathlib
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import clinicai.services.media_service as media_mod
import clinicai.services.tep_ket_qua_service as tep_mod
from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import SafetyGateError
from clinicai.main import app
from clinicai.schemas.staff import Capability
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.payment_service import PaymentService
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    CLINIC_B,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_review_round_cho_order,
    _tao_staff,
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
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database test")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


async def _tao_thuoc_catalog(
    conn: asyncpg.Connection,
    *,
    clinic_id: str = CLINIC_A,
    ten: str = "Amoxicillin 500mg",
    gia: int = 5_000,
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO public.drug_catalog
                (clinic_id, name_base, name_raw, unit_price, is_active)
            VALUES ($1::uuid, $2, $2, $3, true)
            ON CONFLICT (clinic_id, name_raw)
            DO UPDATE SET unit_price = EXCLUDED.unit_price, is_active = true
            RETURNING id::text
            """,
            clinic_id,
            ten,
            gia,
        )
    )


async def test_smoke_1_external_result_capability_and_audit_events_e2e(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Luồng 4 & 6: Quản lý cấp capability -> nhân viên xác nhận kết quả -> thu hồi.

    Kiểm tra:
    - MANAGEMENT cấp ket_qua.xac_nhan qua HTTP API ->
      sinh audit log 'staff.capability_granted'
    - Read-back thấy quyền
    - Nhân viên vào hàng chờ xác nhận và xác nhận file HOP_LE ->
      sinh audit log 'tep_ket_qua.xac_nhan'
    - Bác sĩ cho phép gửi (2-tier gate vượt qua)
    - MANAGEMENT thu hồi quyền -> sinh audit log 'staff.capability_revoked'
    - Read-back không còn quyền
    - Nhân viên vào lại hàng chờ bị 403 / SafetyGateError
    """
    monkeypatch.setattr(media_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)

    async with pool.acquire() as conn:
        mgr = await _tao_staff(conn, CLINIC_A, "MANAGEMENT")
        nurse = await _tao_staff(conn, CLINIC_A, "NURSE_ULTRASOUND")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
        rid, qid = await _tao_review_round_cho_order(conn, CLINIC_A, vid, oid)

    app.dependency_overrides[get_db_pool] = lambda: pool
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Ban đầu nurse chưa có capability -> gọi queue bị 403
            app.dependency_overrides[get_current_identity] = lambda: nurse
            tep_svc = TepKetQuaService(pool)
            with pytest.raises(SafetyGateError, match="không có quyền xác nhận"):
                await tep_svc.cho_xac_nhan(identity=nurse)

            # 2. MANAGEMENT cấp khối "Xác nhận tệp kết quả" qua màn Phân quyền —
            # MỘT hệ quyền (23/09/2026). Đường cũ /staff/{id}/capabilities đã
            # nghỉ: trả 410, không ghi gì.
            app.dependency_overrides[get_current_identity] = lambda: mgr
            res_cu = await client.post(
                f"/api/v1/staff/{nurse.staff_id}/capabilities",
                json={"capability": "ket_qua.xac_nhan"},
            )
            assert res_cu.status_code == 410
            res_grant = await client.post(
                f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}/cap",
                json={"khoi": "xac_nhan_ket_qua"},
            )
            assert res_grant.status_code == 200, res_grant.text

            # 3. Read-back xác nhận quyền
            res_get = await client.get(f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}")
            assert res_get.status_code == 200
            assert any(
                q["quyen"] == "result.file.confirm"
                for k in res_get.json()["khoi"]
                for q in k["quyen"]
            )

            # Sự kiện cấp quyền có tên người cấp
            async with pool.acquire() as conn:
                granted_event = await conn.fetchrow(
                    "SELECT actor_staff_id::text AS ai FROM domain_event"
                    " WHERE clinic_id = $1::uuid AND event_type = 'capability.granted'"
                    "   AND aggregate_id = $2::uuid"
                    " ORDER BY seq DESC LIMIT 1",
                    CLINIC_A,
                    nurse.staff_id,
                )
                assert granted_event is not None
                assert granted_event["ai"] == mgr.staff_id

            # 4. Partner upload file kết quả ngoài
            res_up = await tep_svc.tai_len(
                identity=partner,
                clinic_patient_id=pid,
                data=PDF_DUMMY,
                ten_hien_thi="kq_xet_nghiem.pdf",
                service_order_id=oid,
            )
            assert res_up["ok"] is True
            tep_id = res_up["id"]

            # Trước khi xác nhận: bác sĩ thử cho phép gửi ->
            # bị trigger DB / 2-tier guard chặn
            with pytest.raises(Exception):
                await tep_svc.cho_phep_gui(tep_id=tep_id, identity=doc)

            # 5. Nurse (đã có capability) vào queue -> thấy file và xác nhận HOP_LE
            app.dependency_overrides[get_current_identity] = lambda: nurse
            queue_items = await tep_svc.cho_xac_nhan(identity=nurse)
            assert any(item["tep_id"] == tep_id for item in queue_items)

            res_conf = await tep_svc.xac_nhan_tep(
                identity=nurse,
                tep_id=tep_id,
                trang_thai="HOP_LE",
                ly_do="Tệp rõ nét, đúng tên bệnh nhân",
            )
            assert res_conf["trang_thai"] == "HOP_LE"

            # Kiểm tra audit log 'tep_ket_qua.xac_nhan'
            async with pool.acquire() as conn:
                conf_event = await conn.fetchrow(
                    """
                    SELECT event_type, payload
                      FROM event_log
                     WHERE clinic_id = $1::uuid
                       AND event_type = 'tep_ket_qua.xac_nhan'
                       AND aggregate_id = $2
                     ORDER BY recorded_at DESC, event_id DESC LIMIT 1
                    """,
                    CLINIC_A,
                    tep_id,
                )
                assert conf_event is not None

            # Bác sĩ cho phép gửi -> thành công!
            app.dependency_overrides[get_current_identity] = lambda: doc
            res_allow = await tep_svc.cho_phep_gui(tep_id=tep_id, identity=doc)
            assert res_allow["ok"] is True

            # 6. MANAGEMENT thu khối qua màn Phân quyền
            app.dependency_overrides[get_current_identity] = lambda: mgr
            res_rev = await client.post(
                f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}/thu",
                json={"khoi": "xac_nhan_ket_qua"},
            )
            assert res_rev.status_code == 200, res_rev.text

            # Read-back xác nhận đã mất quyền
            res_get2 = await client.get(f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}")
            assert res_get2.status_code == 200
            assert not any(
                q["quyen"] == "result.file.confirm"
                for k in res_get2.json()["khoi"]
                for q in k["quyen"]
            )
            async with pool.acquire() as conn:
                rev_event = await conn.fetchval(
                    "SELECT count(*) FROM domain_event"
                    " WHERE clinic_id = $1::uuid AND event_type = 'capability.revoked'"
                    "   AND aggregate_id = $2::uuid",
                    CLINIC_A,
                    nurse.staff_id,
                )
                assert rev_event >= 1

            # 7. Nurse vào lại queue -> lại bị 403 / SafetyGateError
            with pytest.raises(SafetyGateError, match="không có quyền xác nhận"):
                await tep_svc.cho_xac_nhan(identity=nurse)
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        app.dependency_overrides.pop(get_db_pool, None)


async def test_smoke_2_cross_feature_handoff_terminal_catalog_rx_and_payment_e2e(
    pool: asyncpg.Pool, monkeypatch: Any, tmp_path: pathlib.Path
) -> None:
    """Luồng 1, 7, 8 (Điểm giao nhau cốt lõi giữa PR #174 và PR #175):

    Kê thuốc catalog + Chỉ định ngoài chờ kết quả:
    - Bác sĩ kê thuốc catalog (drug_catalog_id lưu vào prescription).
    - Bác sĩ bấm Khám xong phiên 1 -> HANDOFF: visit vẫn OPEN, giữ nguyên catalog_id.
    - Kết quả ngoài về và được xác nhận HOP_LE.
    - Bác sĩ review, bấm Khám xong phiên 2 -> TERMINAL:
      visit kết thúc (exam_completed_at),
      đơn thuốc chính thức vẫn giữ vẹn nguyên drug_catalog_id.
    - Lễ tân xem bảng thu, thấy hóa đơn thuốc hợp lệ,
      thu tiền CASH thành công khi flag=0.
    """
    monkeypatch.setattr(media_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        reception = await _tao_staff(conn, CLINIC_A, "RECEPTION")
        partner = await _tao_staff(conn, CLINIC_A, "PARTNER")
        nurse = await _tao_staff(
            conn, CLINIC_A, "NURSE_ULTRASOUND", caps=[Capability.KET_QUA_XAC_NHAN.value]
        )
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        await conn.execute(
            "UPDATE visit SET checked_in_at = now() WHERE visit_id = $1::uuid", vid
        )
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid LIMIT 1",
            CLINIC_A,
        )

        # Node & dịch vụ đối tác ngoài
        node_doitac = "DICHVU-XETNGHIEM-NGOAI"
        await conn.execute(
            """
            INSERT INTO node_definition (
              clinic_id, code, name, flow_group, workspace, lam_ben_ngoai, actor_roles
            ) VALUES ($1::uuid, $2, 'Lab đối tác', 'ket_qua', 'khu_dieu_duong',
                      true, '{NURSE_ULTRASOUND}')
            ON CONFLICT (clinic_id, code)
            DO UPDATE SET lam_ben_ngoai = true, workspace = 'khu_dieu_duong'
            """,
            CLINIC_A,
            node_doitac,
        )
        ma_ngoai = f"MAU-DT-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            """
            INSERT INTO service_price (
              clinic_id, service_code, name, "group", unit_price, active,
              node_code, doi_tac_lay_mau, billing_owner
            ) VALUES ($1::uuid, $2, 'Xét nghiệm ngoài test', 'dich_vu',
                      120000, true, $3, true, 'CLINIC')
            """,
            CLINIC_A,
            ma_ngoai,
            node_doitac,
        )
        phong_dt = await conn.fetchval(
            "SELECT id::text FROM clinic_room "
            "WHERE clinic_id = $1::uuid AND la_doi_tac AND is_active LIMIT 1",
            CLINIC_A,
        )
        if not phong_dt:
            phong_dt = str(uuid.uuid4())
            await conn.execute(
                """
                INSERT INTO clinic_room (
                    id, clinic_id, location_id, name, code, node_code,
                    is_active, la_doi_tac
                ) VALUES (
                    $1::uuid, $2::uuid, $3::uuid, 'Phòng đối tác', 'P-DT',
                    $4, true, true
                )
                ON CONFLICT (id) DO NOTHING
                """,
                phong_dt,
                CLINIC_A,
                loc,
                node_doitac,
            )
        await conn.execute(
            """
            INSERT INTO clinic_room_node (clinic_id, room_id, node_code)
            VALUES ($1::uuid, $2::uuid, $3)
            ON CONFLICT DO NOTHING
            """,
            CLINIC_A,
            phong_dt,
            node_doitac,
        )

        drug_id = await _tao_thuoc_catalog(
            conn, clinic_id=CLINIC_A, ten="Augmentin 1g", gia=15_000
        )

    svc_lk = LuotKhamService(pool)
    svc_tep = TepKetQuaService(pool)
    svc_cr = ClinicalRecordService(pool)
    svc_pay = PaymentService(pool)

    # 1. Điều dưỡng ghi sinh hiệu để đưa lượt vào hàng chờ khám (PRIMARY)
    await svc_lk.bat_dau_do_sinh_hieu(visit_id=vid, identity=nurse)
    await svc_lk.record_vitals(
        visit_id=vid,
        raw={"systolic": 120, "diastolic": 80},
        identity=nurse,
    )
    await chay_hanh_trinh(pool)
    board = await svc_lk.bang(identity=doc)
    luot = next(v for v in board["luot"] if v["visit_id"] == vid)
    cid_primary = luot["phien"][0]["id"]

    # 2. Bác sĩ bắt đầu phiên khám chính
    await svc_lk.start_consultation(consultation_id=cid_primary, identity=doc)

    # 3. Bác sĩ duyệt chỉ định ngoài
    duyet = await svc_lk.authorize_orders(
        consultation_id=cid_primary,
        service_codes=[ma_ngoai],
        draft_order_ids=None,
        identity=doc,
    )
    oid = duyet["order_ids"][0]

    # 4. Bác sĩ kê thuốc từ danh mục catalog
    await svc_cr.save(
        identity=doc,
        appointment_id=aid,
        clinic_patient_id=pid,
        expected_revision=0,
        chief_complaint="Đau họng, sốt",
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Augmentin 1g",
                "quantity": "14 viên",
                "dosage": "Ngày uống 2 viên sáng chiều",
                "caution": "Uống sau ăn no",
            }
        ],
    )

    # Kiểm tra DB: prescription đã lưu đúng catalog ID
    async with pool.acquire() as conn:
        rx = await conn.fetchrow(
            """
            SELECT drug_catalog_id::text, quantity_num, unit, drug_name_raw
              FROM prescription
             WHERE visit_id = $1::uuid AND removed_at IS NULL
            """,
            vid,
        )
        assert rx is not None
        assert rx["drug_catalog_id"] == drug_id
        assert rx["quantity_num"] == Decimal(14)
        assert rx["unit"] == "viên"

    # 3. Bác sĩ bấm Khám xong phiên 1 -> HANDOFF sang chờ kết quả dịch vụ ngoài
    kq_handoff = await svc_lk.complete_consultation(
        consultation_id=cid_primary,
        outcome="SERVICES",
        requirements=[{"order_id": oid, "need": "VALID_RESULT"}],
        identity=doc,
    )
    assert kq_handoff["ok"] is True

    # Assert DB State sau HANDOFF:
    # - Visit vẫn OPEN, exam_completed_at chưa có
    # - consultation outcome = SERVICES
    # - Đơn thuốc catalog ID vẫn giữ nguyên
    async with pool.acquire() as conn:
        v_handoff = await conn.fetchrow(
            "SELECT status, exam_completed_at FROM visit WHERE visit_id = $1::uuid", vid
        )
        assert v_handoff["status"] == "OPEN"
        assert v_handoff["exam_completed_at"] is None

        rx_handoff = await conn.fetchrow(
            "SELECT drug_catalog_id::text FROM prescription WHERE visit_id = $1::uuid",
            vid,
        )
        assert rx_handoff["drug_catalog_id"] == drug_id

    # 4. Đối tác lấy mẫu và upload tệp kết quả -> CHO_XAC_NHAN
    await svc_lk.doi_tac_da_lay_mau(order_id=oid, identity=partner)
    res_up = await svc_tep.tai_len(
        identity=partner,
        clinic_patient_id=pid,
        data=PDF_DUMMY,
        ten_hien_thi="ket_qua_mau.pdf",
        service_order_id=oid,
    )
    tep_id = res_up["id"]

    # 5. Nhân viên có capability xác nhận HOP_LE
    await svc_tep.xac_nhan_tep(
        identity=nurse,
        tep_id=tep_id,
        trang_thai="HOP_LE",
        ly_do="Đạt tiêu chuẩn xét nghiệm",
    )

    # 6. Đủ điều kiện đọc kết quả -> phiên REVIEW được sinh ra
    async with pool.acquire() as conn:
        cid_review = await conn.fetchval(
            """
            SELECT id::text FROM consultation
             WHERE visit_id = $1::uuid AND kind = 'REVIEW'
            """,
            vid,
        )
        assert cid_review is not None

    # 7. Bác sĩ mở phiên REVIEW và duyệt cho phép gửi file
    await svc_lk.start_consultation(consultation_id=cid_review, identity=doc)
    await svc_tep.cho_phep_gui(tep_id=tep_id, identity=doc)

    # 8. Bác sĩ hoàn tất bệnh án (chẩn đoán và lời dặn)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO clinical_record (
                clinic_id, visit_id, soap_assessment, soap_plan, prescription_draft
            ) VALUES (
                $1::uuid, $2::uuid,
                '{"chan_doan": "Viêm amidan mủ"}'::jsonb,
                '{"loi_dan": "Tái khám sau 7 ngày"}'::jsonb,
                NULL
            ) ON CONFLICT (visit_id) DO UPDATE SET
                soap_assessment = '{"chan_doan": "Viêm amidan mủ"}'::jsonb,
                soap_plan = '{"loi_dan": "Tái khám sau 7 ngày"}'::jsonb,
                prescription_draft = NULL
            """,
            CLINIC_A,
            vid,
        )

    # 9. Bác sĩ bấm Khám xong phiên 2 -> TERMINAL
    kq_terminal = await svc_lk.complete_consultation(
        consultation_id=cid_review,
        outcome="DONE",
        requirements=None,
        identity=doc,
    )
    assert kq_terminal["ok"] is True

    # Assert DB State sau TERMINAL:
    # - exam_completed_at ĐÃ CÓ (quầy thu ngân được phép thu tiền)
    # - prescription VẪN GIỮ 100% drug_catalog_id
    async with pool.acquire() as conn:
        v_terminal = await conn.fetchrow(
            "SELECT status, exam_completed_at FROM visit WHERE visit_id = $1::uuid", vid
        )
        assert v_terminal["exam_completed_at"] is not None

        rx_terminal = await conn.fetchrow(
            """
            SELECT drug_catalog_id::text, quantity_num, unit
              FROM prescription
             WHERE visit_id = $1::uuid AND removed_at IS NULL
            """,
            vid,
        )
        assert rx_terminal["drug_catalog_id"] == drug_id
        assert rx_terminal["quantity_num"] == Decimal(14)

    # 10. Tiếp tục luồng thu ngân: Lễ tân kiểm tra hóa đơn và thu CASH
    async with pool.acquire() as conn:
        hd = await tinh_hoa_don(conn, clinic_id=CLINIC_A, visit_id=vid, kind="thuoc")
        assert hd.thu_duoc is True
        assert len(hd.van_de) == 0
        expected_total = 15_000 * 14  # 210,000đ
        assert hd.tong == expected_total
        assert len(hd.dong) == 1
        assert hd.dong[0].don_gia == Decimal(15_000)
        assert hd.dong[0].thanh_tien == Decimal(expected_total)

    # Lễ tân thu tiền CASH
    res_pay = await svc_pay.record_payment(
        identity=reception,
        visit_id=vid,
        kind="thuoc",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=expected_total,
        clinic_patient_id=pid,
        method="CASH",
        bill_revision=hd.revision,
    )
    assert res_pay["status"] == "PAID"
    cycle_id = res_pay["payment_cycle_id"]

    # 11. Assert DB State của thanh toán (Simple mode, flag=0):
    async with pool.acquire() as conn:
        cycle = await conn.fetchrow(
            """
            SELECT status, amount FROM payment_cycle
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert cycle["status"] == "PAID"
        assert cycle["amount"] == expected_total

        payment = await conn.fetchrow(
            "SELECT status, amount FROM payment WHERE payment_cycle_id = $1::uuid",
            cycle_id,
        )
        assert payment["status"] == "PAID"
        assert payment["amount"] == expected_total

        bill_line = await conn.fetchrow(
            """
            SELECT quantity, unit_price, line_total
              FROM payment_bill_line
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert bill_line is not None
        assert bill_line["quantity"] == Decimal(14)
        assert bill_line["unit_price"] == Decimal(15_000)
        assert bill_line["line_total"] == Decimal(expected_total)

        # Không có inventory_txn khi flag = 0
        txns = await conn.fetch(
            "SELECT id FROM inventory_txn WHERE payment_cycle_id = $1::uuid", cycle_id
        )
        assert len(txns) == 0


async def test_smoke_3_unlisted_drug_free_text_blocked_at_payment_e2e(
    pool: asyncpg.Pool, monkeypatch: Any
) -> None:
    """Luồng 3: Thuốc ngoài danh mục (free-text không có drug_catalog_id)
    bị chặn thu tiền.

    Kiểm tra:
    - Kê free-text -> drug_catalog_id = NULL
    - tinh_hoa_don báo thu_duoc = False, lý do 'thuốc chưa có trong danh mục giá'
    - Tuyệt đối không tính thành 0đ để thu nhầm
    - PaymentService.record_payment từ chối với ValidationError
    """
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")

    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        reception = await _tao_staff(conn, CLINIC_A, "RECEPTION")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)

    svc_cr = ClinicalRecordService(pool)
    svc_pay = PaymentService(pool)

    # Bác sĩ lưu đơn thuốc tự gõ (free-text, không có drug_catalog_id)
    await svc_cr.save(
        identity=doc,
        appointment_id=aid,
        clinic_patient_id=pid,
        expected_revision=0,
        prescriptions=[
            {
                "drug_catalog_id": None,
                "drug_name": "Thuốc Nam bôi ngoài da gia truyền",
                "quantity": "1 tuýp",
                "dosage": "Bôi ngày 2 lần",
            }
        ],
    )

    # Đánh dấu khám xong
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE visit SET exam_completed_at = now() WHERE visit_id = $1::uuid", vid
        )

        # Kiểm tra hóa đơn
        hd = await tinh_hoa_don(conn, clinic_id=CLINIC_A, visit_id=vid, kind="thuoc")
        assert hd.thu_duoc is False
        # 24/09/2026: thuốc gõ tay vào danh mục kho (cần soát, CHƯA GIÁ).
        assert any("chưa có giá" in v for v in hd.van_de)

    # Thử thu tiền -> bị chặn vì thuốc chưa có giá (không tính 0đ)
    with pytest.raises(ValidationError, match="chưa có giá"):
        await svc_pay.record_payment(
            identity=reception,
            visit_id=vid,
            kind="thuoc",
            idempotency_key=f"test-{uuid.uuid4().hex}",
            amount=None,
            clinic_patient_id=pid,
            method="CASH",
            bill_revision=hd.revision,
        )


async def test_smoke_4_capability_security_guards_matrix_http(
    pool: asyncpg.Pool,
) -> None:
    """Luồng 5: Ma trận chốt an toàn quyền tại lớp HTTP API — hệ quyền MỚI.

    Từ 23/09/2026 chỉ còn một hệ quyền (`capability_grant`, màn Phân quyền).
    - đường cũ /staff/{id}/capabilities: 410 với mọi thao tác, không ghi gì
    - không có permission.manage mà cấp/thu -> 403
    - khối không tồn tại -> 422
    - người ngoài phòng khám -> bị từ chối
    - người làm ở 2 phòng khám: quyền theo TỪNG phòng khám — cấp ở A được
    """
    app.dependency_overrides[get_db_pool] = lambda: pool

    async with pool.acquire() as conn:
        mgr = await _tao_staff(conn, CLINIC_A, "MANAGEMENT")
        nurse = await _tao_staff(conn, CLINIC_A, "NURSE_ULTRASOUND")
        cashier = await _tao_staff(conn, CLINIC_A, "CASHIER")
        # Phòng khám B phải có TRƯỚC nhân sự của nó (chạy song song mới lộ:
        # trước đây nhờ tệp khác tạo sẵn).
        await conn.execute(
            """
            INSERT INTO clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic B Smoke', 'CLINIC_B_SMOKE')
            ON CONFLICT (id) DO NOTHING
            """,
            CLINIC_B,
        )
        staff_b = await _tao_staff(conn, CLINIC_B, "NURSE_ULTRASOUND")

        # Staff multi-clinic
        staff_multi = await _tao_staff(conn, CLINIC_A, "NURSE_ULTRASOUND")
        await conn.execute(
            """
            INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)
            VALUES ($1::uuid, $2::uuid, 'NURSE_ULTRASOUND', true)
            ON CONFLICT (clinic_id, staff_id, role) DO UPDATE SET is_active = true
            """,
            CLINIC_B,
            staff_multi.staff_id,
        )

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 0. Đường cũ đã nghỉ: kể cả quản lý cũng nhận 410, không ghi gì.
            app.dependency_overrides[get_current_identity] = lambda: mgr
            for method, url in (
                ("POST", f"/api/v1/staff/{nurse.staff_id}/capabilities"),
                ("GET", f"/api/v1/staff/{nurse.staff_id}/capabilities"),
                (
                    "DELETE",
                    f"/api/v1/staff/{nurse.staff_id}/capabilities/ket_qua.xac_nhan",
                ),
            ):
                r = await client.request(
                    method, url, json={"capability": "ket_qua.xac_nhan"}
                )
                assert r.status_code == 410, (method, url, r.text)

            # 1. Không có permission.manage (thu ngân) cấp / thu -> 403
            app.dependency_overrides[get_current_identity] = lambda: cashier
            for hanh_dong in ("cap", "thu"):
                r = await client.post(
                    f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}/{hanh_dong}",
                    json={"khoi": "xac_nhan_ket_qua"},
                )
                assert r.status_code == 403, r.text

            # 2. Khối không tồn tại -> 422
            app.dependency_overrides[get_current_identity] = lambda: mgr
            r = await client.post(
                f"/api/v1/phan-quyen/nhan-su/{nurse.staff_id}/cap",
                json={"khoi": "DOCTOR_CONSULTATION"},
            )
            assert r.status_code == 422, r.text

            # 3. Người ngoài phòng khám (chỉ ở CLINIC_B) -> bị từ chối, không ghi
            r = await client.post(
                f"/api/v1/phan-quyen/nhan-su/{staff_b.staff_id}/cap",
                json={"khoi": "xac_nhan_ket_qua"},
            )
            assert r.status_code in (403, 404, 422), r.text
            async with pool.acquire() as conn:
                assert not await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM capability_grant"
                    " WHERE staff_id = $1::uuid"
                    "   AND capability = 'result.file.confirm')",
                    staff_b.staff_id,
                )

            # 4. Làm ở 2 phòng khám: quyền theo từng phòng khám -> cấp ở A được,
            # và chỉ có hiệu lực ở A.
            r = await client.post(
                f"/api/v1/phan-quyen/nhan-su/{staff_multi.staff_id}/cap",
                json={"khoi": "xac_nhan_ket_qua"},
            )
            assert r.status_code == 200, r.text
            async with pool.acquire() as conn:
                pk = await conn.fetch(
                    "SELECT clinic_id::text FROM capability_grant"
                    " WHERE staff_id = $1::uuid AND capability = 'result.file.confirm'"
                    "   AND revoked_at IS NULL",
                    staff_multi.staff_id,
                )
                assert [x["clinic_id"] for x in pk] == [CLINIC_A]
    finally:
        app.dependency_overrides.pop(get_current_identity, None)
        app.dependency_overrides.pop(get_db_pool, None)
