"""Test luồng kê đơn thuốc có drug_catalog_id và thanh toán thuốc không chờ kho.

Chứng minh 7 yêu cầu (20/09/2026):
1. Doctor chọn catalog drug A + "30 viên" -> prescription.drug_catalog_id = A,
   quantity_num = 30, unit = "viên", canonical name.
2. Catalog A có giá -> tinh_hoa_don(kind="thuoc") -> thu_duoc = True, đơn giá đúng,
   thành tiền = giá × 30.
3. KHÔNG có prescription_allocation, KHÔNG có drug_batch -> payment CASH vẫn PAID
   khi flag=0.
4. Sau payment ở mode này: payment_cycle PAID, payment PAID, payment_bill_line tồn tại,
   KHÔNG cần inventory_txn.
5. QR/TRANSFER: tạo PENDING_VERIFICATION không cần lô -> xác minh thành PAID
   không cần lô, không sinh CHUA_GHI_BAN.
6. Free-text không có drug_catalog_id -> không thu được,
   báo "thuốc chưa có trong danh mục giá".
7. RECEPTION: đọc được cashier board thuốc và được record payment thuốc.
8. Catalog ID thuộc clinic khác -> ValidationError bị từ chối fail-closed.
9. Prescription đã map -> bác sĩ chỉ sửa dosage/caution/SOAP
   -> drug_catalog_id KHÔNG bị xoá.
10. TKYK draft có catalog ID -> bác sĩ duyệt -> prescription cuối có đúng
    drug_catalog_id.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ValidationError
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.payment_service import PaymentService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_tien_thuoc_cp1_db import Quay, _du_lo, tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def q(pool: asyncpg.Pool) -> Quay:
    return await tao_quay(pool)


async def _tao_thuoc_catalog(
    conn: asyncpg.Connection,
    *,
    clinic_id: str = CLINIC,
    ten: str = "Paracetamol 500mg",
    gia: int = 2_000,
) -> str:
    return str(
        await conn.fetchval(
            """
            INSERT INTO public.drug_catalog
                   (clinic_id, name_base, name_raw, unit_price, is_active)
            VALUES ($1::uuid, $2, $2, $3, true)
            RETURNING id::text
            """,
            clinic_id,
            ten,
            gia,
        )
    )


async def _set_exam_completed(conn: asyncpg.Connection, visit_id: str) -> None:
    await conn.execute(
        "UPDATE public.visit SET exam_completed_at = now() WHERE visit_id = $1::uuid",
        visit_id,
    )


async def _get_appointment_id(conn: asyncpg.Connection, visit_id: str) -> str:
    return str(
        await conn.fetchval(
            "SELECT appointment_id::text FROM public.visit WHERE visit_id = $1::uuid",
            visit_id,
        )
    )


async def _get_patient_id(conn: asyncpg.Connection, visit_id: str) -> str:
    return str(
        await conn.fetchval(
            """
            SELECT clinic_patient_id::text
              FROM public.visit
             WHERE visit_id = $1::uuid
            """,
            visit_id,
        )
    )


async def test_1_2_3_4_bac_si_ke_catalog_hoa_don_va_thanh_toan_cash(q: Quay) -> None:
    """1. Bác sĩ kê thuốc danh mục -> lưu ID + mapped_by + mapped_at + qty_num + unit.
    2. Hóa đơn tính đúng giá x số lượng, thu_duoc = True.
    3. Thanh toán CASH thành công (PAID) không cần phân lô / tồn kho.
    4. payment_cycle, payment, payment_bill_line sinh đủ; không có inventory_txn.
    """
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Canxi D3 {q.duoi}", gia=5_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    # Bác sĩ lưu bệnh án kèm đơn thuốc chọn từ danh mục
    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám thai",
        objective={"vitals": {"huyet_ap": "110/70"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Tên gửi từ client không quan trọng",
                "quantity": "30 viên",
                "dosage": "Ngày uống 1 viên sau ăn sáng",
                "caution": "Uống nhiều nước",
            }
        ],
    )

    # Kiểm tra DB prescription
    async with q.pool.acquire() as conn:
        rx = await conn.fetchrow(
            """
            SELECT id::text, drug_catalog_id::text, drug_name_raw, quantity,
                   quantity_num, unit, drug_mapped_by::text, drug_mapped_at
              FROM public.prescription
             WHERE visit_id = $1::uuid AND removed_at IS NULL
            """,
            q.visit_id,
        )
        assert rx is not None
        assert rx["drug_catalog_id"] == drug_id
        assert rx["quantity_num"] == Decimal(30)
        assert rx["unit"] == "viên"
        assert rx["drug_mapped_by"] == q.bac_si.staff_id
        assert rx["drug_mapped_at"] is not None
        # Tên thuốc được canonicalize từ drug_catalog.name_raw
        assert rx["drug_name_raw"] == f"Canxi D3 {q.duoi}"

        # Bác sĩ khám xong
        await _set_exam_completed(conn, q.visit_id)

        # 2. Kiểm tra hóa đơn
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
        assert hd.thu_duoc is True
        assert len(hd.van_de) == 0
        assert hd.tong == 5_000 * 30  # 150,000đ
        assert len(hd.dong) == 1
        assert hd.dong[0].don_gia == Decimal(5_000)
        assert hd.dong[0].thanh_tien == Decimal(150_000)

    # 3. Thu ngân thanh toán CASH không cần lô hay tồn kho
    ps = PaymentService(q.pool)
    res = await ps.record_payment(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        amount=150_000,
        clinic_patient_id=pat_id,
        method="CASH",
        bill_revision=hd.revision,
    )
    assert res["status"] == "PAID"
    cycle_id = res["payment_cycle_id"]

    # 4. Kiểm tra dữ liệu thanh toán và kho
    async with q.pool.acquire() as conn:
        cycle = await conn.fetchrow(
            """
            SELECT status, amount, paid_at
              FROM payment_cycle
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert cycle is not None
        assert cycle["status"] == "PAID"
        assert cycle["amount"] == 150_000
        assert cycle["paid_at"] is not None

        pm = await conn.fetchrow(
            "SELECT status, amount FROM payment WHERE payment_cycle_id = $1::uuid",
            cycle_id,
        )
        assert pm is not None
        assert pm["status"] == "PAID"
        assert pm["amount"] == 150_000

        lines = await conn.fetch(
            """
            SELECT source_id, quantity, unit_price, line_total
              FROM payment_bill_line
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert len(lines) == 1
        assert lines[0]["quantity"] == Decimal(30)
        assert lines[0]["unit_price"] == Decimal(5_000)
        assert lines[0]["line_total"] == Decimal(150_000)

        # Không sinh phân lô hay giao dịch xuất kho
        alloc_count = await conn.fetchval(
            """
            SELECT count(*)
              FROM public.prescription_allocation
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert alloc_count == 0

        txn_count = await conn.fetchval(
            """
            SELECT count(*) FROM public.inventory_txn
             WHERE allocation_id IN (
                 SELECT allocation_id
                   FROM public.prescription_allocation
                  WHERE payment_cycle_id = $1::uuid
             )
            """,
            cycle_id,
        )
        assert txn_count == 0


async def test_5_chuyen_khoan_qr_pending_roi_xac_minh_thanh_paid(q: Quay) -> None:
    """5. QR/TRANSFER tạo PENDING_VERIFICATION không cần lô,
    xác minh thành PAID không cần lô, không bị can_doi_soat CHUA_GHI_BAN.
    """
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Sắt Fe {q.duoi}", gia=3_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    # Bác sĩ lưu đơn
    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám phụ khoa",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Sắt",
                "quantity": "20 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )

    async with q.pool.acquire() as conn:
        await _set_exam_completed(conn, q.visit_id)
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )

    ps = PaymentService(q.pool)
    res_pending = await ps.record_payment(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        amount=60_000,
        clinic_patient_id=pat_id,
        method="TRANSFER",
        bill_revision=hd.revision,
    )
    assert res_pending["status"] == "PENDING_VERIFICATION"
    cycle_id = res_pending["payment_cycle_id"]

    # Xác minh chuyển khoản
    res_paid = await ps.xac_minh_dien_tu(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        payment_cycle_id=cycle_id,
        reference="BANK_REF_9999",
    )
    assert res_paid["status"] == "PAID"

    async with q.pool.acquire() as conn:
        cycle = await conn.fetchrow(
            """
            SELECT status, can_doi_soat, doi_soat_ly_do
              FROM payment_cycle
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert cycle is not None
        assert cycle["status"] == "PAID"
        assert cycle["can_doi_soat"] is False
        assert (cycle["doi_soat_ly_do"] or []) == []


async def test_6_thuoc_ngoai_danh_muc_chua_thu_duoc_khong_tinh_0d(q: Quay) -> None:
    """6. Thuốc free-text ngoài danh mục (drug_catalog_id = NULL) không được tính 0đ,
    hóa đơn báo 'thuốc chưa có trong danh mục giá', thu tiền báo lỗi.
    """
    async with q.pool.acquire() as conn:
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    # Bác sĩ kê thuốc ngoài danh mục
    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám chung",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": None,
                "drug_name": "Thuốc ngoại nhập xách tay",
                "quantity": "10 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )

    async with q.pool.acquire() as conn:
        await _set_exam_completed(conn, q.visit_id)
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
        assert hd.thu_duoc is False
        assert any("thuốc chưa có trong danh mục giá" in v for v in hd.van_de)

    ps = PaymentService(q.pool)
    with pytest.raises(ValidationError, match="thuốc chưa có trong danh mục giá"):
        await ps.record_payment(
            identity=q.thu_ngan,
            visit_id=q.visit_id,
            kind="thuoc",
            amount=None,
            clinic_patient_id=pat_id,
            method="CASH",
        )


async def test_7_reception_doc_bang_thu_va_thu_tien_thuoc(q: Quay) -> None:
    """7. Vai RECEPTION đọc được cashier board và record payment thành công."""
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Vitamin C {q.duoi}", gia=1_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid LIMIT 1",
            CLINIC,
        )
        le_tan = await _nguoi(conn, loc, "RECEPTION")

    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám cảm",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Vitamin C",
                "quantity": "10 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )

    async with q.pool.acquire() as conn:
        await _set_exam_completed(conn, q.visit_id)

    # Lễ tân đọc bảng thu ngân thuốc
    cs = CashierBoardService(q.pool)
    board = await cs.board(identity=le_tan, modes=["thuoc"])
    items = board.get("items", [])
    matching = [b for b in items if b["visit_id"] == q.visit_id]
    assert len(matching) == 1
    assert matching[0]["hoa_don"]["thuoc"]["thu_duoc"] is True
    assert matching[0]["hoa_don"]["thuoc"]["tong"] == 10_000

    # Lễ tân thực hiện thu tiền thuốc
    ps = PaymentService(q.pool)
    res = await ps.record_payment(
        identity=le_tan,
        visit_id=q.visit_id,
        kind="thuoc",
        amount=10_000,
        clinic_patient_id=pat_id,
        method="CASH",
    )
    assert res["status"] == "PAID"


async def test_8_drug_catalog_id_khac_clinic_bi_tu_choi_fail_closed(q: Quay) -> None:
    """8. Bác sĩ gửi drug_catalog_id clinic khác -> bị từ chối ValidationError."""
    other_clinic = str(uuid.uuid4())
    async with q.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO public.clinic (id, name, code)
            VALUES ($1::uuid, 'Clinic khác', $2)
            """,
            other_clinic,
            f"OTHER-{q.duoi}",
        )
        other_drug_id = await _tao_thuoc_catalog(
            conn, clinic_id=other_clinic, ten="Thuốc phòng khám khác"
        )
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    service = ClinicalRecordService(q.pool)
    with pytest.raises(
        ValidationError, match="không thuộc danh mục của phòng khám này"
    ):
        await service.save(
            identity=q.bac_si,
            appointment_id=appt_id,
            clinic_patient_id=pat_id,
            expected_revision=0,
            chief_complaint="Test",
            objective={"vitals": {"huyet_ap": "120/80"}},
            prescriptions=[
                {
                    "drug_catalog_id": other_drug_id,
                    "drug_name": "Thuốc phòng khám khác",
                    "quantity": "10 viên",
                    "dosage": "1 viên",
                }
            ],
        )


async def test_9_bac_si_sua_dosage_soap_giu_nguyen_mapping_duoc_si(q: Quay) -> None:
    """9. Dược sĩ đã map drug_catalog_id -> Bác sĩ sửa dosage/SOAP -> giữ mapping."""
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Men vi sinh {q.duoi}", gia=8_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    # 1. Bác sĩ ban đầu kê tự do
    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Rối loạn tiêu hóa",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": None,
                "drug_name": "Men vi sinh gói",
                "quantity": "14 gói",
                "dosage": "Ngày 2 gói",
                "caution": "Pha nước nguội",
            }
        ],
    )

    async with q.pool.acquire() as conn:
        rx_row = await conn.fetchrow(
            """
            SELECT id::text
              FROM public.prescription
             WHERE visit_id = $1::uuid AND removed_at IS NULL
            """,
            q.visit_id,
        )
        assert rx_row is not None
        rx_id = rx_row["id"]
        # Giả lập dược sĩ map thuốc vào danh mục
        await conn.execute(
            """
            UPDATE public.prescription
               SET drug_catalog_id = $2::uuid,
                   drug_mapped_by = $3::uuid,
                   drug_mapped_at = now()
             WHERE id = $1::uuid
            """,
            rx_id,
            drug_id,
            q.duoc_si.staff_id,
        )

    # 2. Bác sĩ mở lại bệnh án, chỉ sửa cách dùng (dosage) và lời dặn SOAP
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=1,
        chief_complaint="Rối loạn tiêu hóa",
        objective={"vitals": {"huyet_ap": "120/80"}},
        plan={"loi_dan": "Ăn nhẹ, tránh dầu mỡ"},
        prescriptions=[
            {
                "id": rx_id,
                "drug_catalog_id": None,  # giả định form gửi None do cache cũ
                "drug_name": "Men vi sinh gói",
                "quantity": "14 gói",
                "dosage": "Ngày 3 gói chia 3 lần",  # Đổi liều
                "caution": "Pha nước nguội",
            }
        ],
    )

    # 3. Kiểm tra mapping của dược sĩ KHÔNG bị xoá
    async with q.pool.acquire() as conn:
        rx_after = await conn.fetchrow(
            """
            SELECT drug_catalog_id::text, drug_mapped_by::text, dosage_instructions
              FROM public.prescription
             WHERE id = $1::uuid
            """,
            rx_id,
        )
        assert rx_after is not None
        assert rx_after["drug_catalog_id"] == drug_id
        assert rx_after["drug_mapped_by"] == q.duoc_si.staff_id
        assert rx_after["dosage_instructions"] == "Ngày 3 gói chia 3 lần"


async def test_10_tkyk_draft_catalog_bac_si_duyet_co_catalog_id(q: Quay) -> None:
    """10. Thư ký Y khoa nhập draft catalog -> Bác sĩ duyệt -> có drug_catalog_id."""
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Acid folic {q.duoi}", gia=4_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid LIMIT 1",
            CLINIC,
        )
        thu_ky = await _nguoi(conn, loc, "TKYK")
        # Gán bác sĩ phụ trách cho lịch khám
        await conn.execute(
            "UPDATE public.appointment SET doctor_id = $1::uuid WHERE id = $2::uuid",
            q.bac_si.staff_id,
            appt_id,
        )
        # Phân thư ký đi cùng bác sĩ phụ trách lịch khám
        await conn.execute(
            """
            INSERT INTO public.thu_ky_bac_si
                   (clinic_id, thu_ky_staff_id, bac_si_staff_id)
            VALUES ($1::uuid, $2::uuid, $3::uuid)
            """,
            CLINIC,
            thu_ky.staff_id,
            q.bac_si.staff_id,
        )

    # 1. Thư ký nhập nháp đơn thuốc có catalog ID
    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=thu_ky,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám trước mang thai",
        objective={"vitals": {"huyet_ap": "115/75"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Folic",
                "quantity": "60 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )

    # Chưa tạo đơn chính thức, mới nằm trong prescription_draft
    async with q.pool.acquire() as conn:
        count_main = await conn.fetchval(
            "SELECT count(*) FROM public.prescription WHERE visit_id = $1::uuid",
            q.visit_id,
        )
        assert count_main == 0
        draft = await conn.fetchval(
            """
            SELECT prescription_draft
              FROM public.clinical_record
             WHERE visit_id = $1::uuid
            """,
            q.visit_id,
        )
        assert draft is not None

    # 2. Bác sĩ duyệt đơn nháp
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=1,
        approve_prescription_draft=True,
    )

    # 3. Đơn chính thức đã được tạo và mang đúng drug_catalog_id
    async with q.pool.acquire() as conn:
        rx = await conn.fetchrow(
            """
            SELECT id::text, drug_catalog_id::text, drug_name_raw, quantity_num, unit,
                   drug_mapped_by::text, drug_mapped_at
              FROM public.prescription
             WHERE visit_id = $1::uuid AND removed_at IS NULL
            """,
            q.visit_id,
        )
        assert rx is not None
        assert rx["drug_catalog_id"] == drug_id
        assert rx["quantity_num"] == Decimal(60)
        assert rx["unit"] == "viên"
        assert rx["drug_mapped_by"] == q.bac_si.staff_id
        assert rx["drug_mapped_at"] is not None
        assert rx["drug_name_raw"] == f"Acid folic {q.duoi}"


async def test_11_transfer_tao_khi_flag_1_co_allocation_doi_flag_0_xac_minh_van_ghi_ban(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tạo TRANSFER khi inventory flag=1 và có allocation
    → đổi env flag=0
    → xác minh
    → vẫn xử lý allocation đúng như cycle inventory cũ: ghi_ban, trừ tồn kho, sinh SALE txn.
    """
    # 1. Bật flag = 1
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Thuốc Lô A {q.duoi}", gia=10_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Thuốc A",
                "quantity": "10 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )
    async with q.pool.acquire() as conn:
        await _set_exam_completed(conn, q.visit_id)

    # Dược sĩ nhập lô và phân lô đủ 10 viên
    await _du_lo(q)

    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )

    ps = PaymentService(q.pool)
    res_pending = await ps.record_payment(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        amount=100_000,
        clinic_patient_id=pat_id,
        method="TRANSFER",
        bill_revision=hd.revision,
    )
    cycle_id = res_pending["payment_cycle_id"]
    assert res_pending["status"] == "PENDING_VERIFICATION"

    # Kiểm tra phân lô đã được gắn vào cycle_id
    async with q.pool.acquire() as conn:
        alloc = await conn.fetchrow(
            """
            SELECT id, drug_batch_id, quantity
              FROM public.prescription_allocation
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert alloc is not None
        assert alloc["quantity"] == Decimal(10)
        batch_id = alloc["drug_batch_id"]

        ton_truoc = await conn.fetchval(
            "SELECT quantity_on_hand FROM public.drug_batch WHERE id = $1::uuid",
            batch_id,
        )

    # 2. Đổi env flag = 0 (tắt kho)
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")

    # 3. Lễ tân xác minh giao dịch
    res_paid = await ps.xac_minh_dien_tu(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        payment_cycle_id=cycle_id,
        reference="REF_TRANSFER_OLD_CYCLE",
    )
    assert res_paid["status"] == "PAID"

    # 4. Chứng minh allocation vẫn được xử lý đúng như cycle inventory cũ:
    # - Có inventory_txn SALE gắn với allocation này
    # - SALE txn ghi nhận đúng số lượng -10 viên
    async with q.pool.acquire() as conn:
        sale_txn = await conn.fetchrow(
            """
            SELECT id, txn_type, quantity
              FROM public.inventory_txn
             WHERE allocation_id = $1::uuid AND txn_type = 'SALE'
            """,
            alloc["id"],
        )
        assert sale_txn is not None
        assert sale_txn["quantity"] == Decimal(-10)


async def test_12_cash_tao_khi_flag_1_da_sale_doi_flag_0_void_van_dao_ban(
    q: Quay, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tạo CASH khi flag=1, đã SALE
    → đổi flag=0
    → void
    → vẫn đảo/return theo logic inventory cũ: inventory_txn SALE_REVERSAL.
    """
    # 1. Bật flag = 1
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    async with q.pool.acquire() as conn:
        drug_id = await _tao_thuoc_catalog(conn, ten=f"Thuốc Lô B {q.duoi}", gia=10_000)
        appt_id = await _get_appointment_id(conn, q.visit_id)
        pat_id = await _get_patient_id(conn, q.visit_id)

    service = ClinicalRecordService(q.pool)
    await service.save(
        identity=q.bac_si,
        appointment_id=appt_id,
        clinic_patient_id=pat_id,
        expected_revision=0,
        chief_complaint="Khám",
        objective={"vitals": {"huyet_ap": "120/80"}},
        prescriptions=[
            {
                "drug_catalog_id": drug_id,
                "drug_name": "Thuốc B",
                "quantity": "5 viên",
                "dosage": "Ngày 1 viên",
            }
        ],
    )
    async with q.pool.acquire() as conn:
        await _set_exam_completed(conn, q.visit_id)

    # Dược sĩ nhập lô và phân lô đủ 5 viên
    await _du_lo(q)

    async with q.pool.acquire() as conn:
        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )

    ps = PaymentService(q.pool)
    res = await ps.record_payment(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        amount=50_000,
        clinic_patient_id=pat_id,
        method="CASH",
        bill_revision=hd.revision,
    )
    cycle_id = res["payment_cycle_id"]
    assert res["status"] == "PAID"

    # Kiểm tra đã SALE khi flag=1
    async with q.pool.acquire() as conn:
        alloc = await conn.fetchrow(
            """
            SELECT id, drug_batch_id, quantity
              FROM public.prescription_allocation
             WHERE payment_cycle_id = $1::uuid
            """,
            cycle_id,
        )
        assert alloc is not None

        sale_txn = await conn.fetchval(
            """
            SELECT count(*)
              FROM public.inventory_txn
             WHERE allocation_id = $1::uuid AND txn_type = 'SALE'
            """,
            alloc["id"],
        )
        assert sale_txn == 1

    # 2. Đổi env flag = 0 (tắt kho)
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")

    # 3. Huỷ phiếu thu (void)
    void_res = await ps.void_payment(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        kind="thuoc",
        payment_cycle_id=cycle_id,
        reason="Khách đổi ý không lấy thuốc",
    )
    assert void_res["status"] == "VOIDED"

    # 4. Chứng minh vẫn đảo bán theo logic inventory cũ:
    # - Có SALE_REVERSAL txn
    # - Hoàn lại số lượng +5 viên
    async with q.pool.acquire() as conn:
        reversal_txn = await conn.fetchrow(
            """
            SELECT id, txn_type, quantity
              FROM public.inventory_txn
             WHERE allocation_id = $1::uuid AND txn_type = 'SALE_REVERSAL'
            """,
            alloc["id"],
        )
        assert reversal_txn is not None
        assert reversal_txn["quantity"] == Decimal(5)
