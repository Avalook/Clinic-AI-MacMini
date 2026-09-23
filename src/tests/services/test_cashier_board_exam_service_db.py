"""Kiểm tra nguồn dịch vụ khám chính cho Bảng thu ngân & Hoá đơn.

BUG REPRODUCE:
- Bác sĩ khám xong (exam_completed_at != NULL)
- Loại khám trên Bàn khám: visit.service_type_id = Phụ khoa
- Không có service_order / không chỉ định CLS
- Nếu appointment.service_type_id = NULL hoặc visit không có appointment:
  Trước đây CashierBoardService._SQL chỉ đọc a.service_type_id,
  dẫn tới services=[] và biến mất khỏi QuayThuNgan (l.services.length > 0).
  Đồng thời bill_service.py tính hoá đơn với van_de="chưa xác định loại khám".
"""

# ruff: noqa: F811 — fixture q được import để pytest phát hiện.

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.payment_service import PaymentService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _tao_loai_kham(pool: Any, code: str, name: str, gia: int) -> str:
    st_id = str(
        await pool.fetchval(
            "INSERT INTO service_type (clinic_id, code, name, is_active)"
            " VALUES ($1::uuid, $2, $3, true) RETURNING id::text",
            CLINIC,
            code,
            name,
        )
    )
    await pool.execute(
        'INSERT INTO service_price (clinic_id, "group", service_code, name,'
        " unit_price, billing_owner, node_code)"
        " VALUES ($1::uuid, 'dich_vu', $2, $3, $4, 'CLINIC', 'DICHVU-KHAM')",
        CLINIC,
        code,
        name,
        gia,
    )
    return st_id


async def test_reproduce_visit_service_type_null_appointment_service_type(
    q: Quay,
) -> None:
    """Test bắt buộc:
    - visit.service_type_id = Phụ khoa
    - appointment.service_type_id = NULL
    - exam_completed_at != NULL
    - không có service_order
    => cashier board VẪN có bệnh nhân
    => services chứa đúng dịch vụ Phụ khoa
    => bill/payment tính đúng tiền khám Phụ khoa.
    """
    st_phukhoa = await _tao_loai_kham(
        q.pool, f"PK-{q.duoi}", f"Khám phụ khoa {q.duoi}", 250_000
    )
    appt_id = await q.pool.fetchval(
        "SELECT appointment_id FROM visit WHERE visit_id = $1::uuid", q.visit_id
    )
    old_st_id = await q.pool.fetchval(
        "SELECT service_type_id FROM appointment WHERE id = $1::uuid", appt_id
    )
    try:
        await q.pool.execute(
            "ALTER TABLE appointment ALTER COLUMN service_type_id DROP NOT NULL"
        )
        await q.pool.execute(
            "UPDATE appointment SET service_type_id = NULL WHERE id = $1::uuid",
            appt_id,
        )
        await q.pool.execute(
            "UPDATE visit SET service_type_id = $2::uuid, exam_completed_at = now()"
            " WHERE visit_id = $1::uuid",
            q.visit_id,
            st_phukhoa,
        )

        # 1. Kiểm tra CashierBoardService.board()
        board = await CashierBoardService(q.pool).board(
            identity=q.thu_ngan, modes=["dich_vu"]
        )
        item = next((i for i in board["items"] if i["visit_id"] == q.visit_id), None)
        assert item is not None, "Bệnh nhân phải xuất hiện trên bảng thu ngân"

        svcs = item["services"]
        assert len(svcs) >= 1, "services không được rỗng"
        assert svcs[0]["name"] == f"Khám phụ khoa {q.duoi}"
        assert svcs[0]["price"] == 250_000

        # 2. Kiểm tra bill_service / hoa_don
        hd = item["hoa_don"]["dich_vu"]
        assert hd["thu_duoc"] is True, (
            f"Hoá đơn phải thu được, nhưng có lỗi: {hd.get('van_de')}"
        )
        assert hd["tong"] == 250_000
        dong_kham = next((d for d in hd["dong"] if d["source_type"] == "exam"), None)
        assert dong_kham is not None
        assert dong_kham["ten"] == f"Khám phụ khoa {q.duoi}"
        assert dong_kham["van_de"] is None

        # 3. PaymentService thu được
        pay_res = await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            idempotency_key=f"test-{uuid.uuid4().hex}",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
        )
        assert pay_res["status"] == "PAID"
    finally:
        await q.pool.execute(
            "UPDATE appointment SET service_type_id = $2::uuid WHERE id = $1::uuid",
            appt_id,
            old_st_id,
        )
        await q.pool.execute(
            "ALTER TABLE appointment ALTER COLUMN service_type_id SET NOT NULL"
        )


async def test_visit_khong_co_appointment_co_service_type_id(q: Quay) -> None:
    """Test thêm:
    - visit không có appointment
    - visit.service_type_id có giá trị
    - exam_completed_at != NULL
    => vẫn hiện Thu ngân
    => services chứa đúng dịch vụ
    => hoá đơn thu được đúng tiền.
    """
    st_phukhoa = await _tao_loai_kham(
        q.pool, f"PK-NOAPPT-{q.duoi}", f"Khám phụ khoa {q.duoi}", 300_000
    )
    await q.pool.execute(
        "UPDATE visit SET appointment_id = NULL, service_type_id = $2::uuid,"
        " exam_completed_at = now() WHERE visit_id = $1::uuid",
        q.visit_id,
        st_phukhoa,
    )

    board = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu"]
    )
    item = next((i for i in board["items"] if i["visit_id"] == q.visit_id), None)
    assert item is not None, (
        "Bệnh nhân không có lịch hẹn nhưng có service_type_id phải hiện trên thu ngân"
    )

    svcs = item["services"]
    assert len(svcs) >= 1, "services không được rỗng"
    assert svcs[0]["name"] == f"Khám phụ khoa {q.duoi}"
    assert svcs[0]["price"] == 300_000

    hd = item["hoa_don"]["dich_vu"]
    assert hd["thu_duoc"] is True, (
        f"Hoá đơn phải thu được, nhưng có lỗi: {hd.get('van_de')}"
    )
    assert hd["tong"] == 300_000

    # 3. PaymentService thu được thành công
    pay_res = await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
    )
    assert pay_res["status"] == "PAID"


async def test_regression_dung_thu_tu_runtime_checkin_soap_hoan_tat_thu_tien(
    q: Quay,
) -> None:
    """1. ĐÚNG THỨ TỰ NGƯỜI DÙNG VỪA TEST TRÊN UI (reproduce case thật):
    check-in
    → lưu hồ sơ/SOAP
    → HOÀN TẤT khám (không còn bước ký, không khoá — 23/09/2026)
    → cashier board phải thấy bệnh nhân
    → bill có đúng dịch vụ khám
    → PaymentService thu thành công.
    """
    st_phukhoa = await _tao_loai_kham(
        q.pool, f"PK-RUNTIME-{q.duoi}", f"Khám phụ khoa {q.duoi}", 220_000
    )
    # Check-in: lịch hẹn CHECKED_IN, chưa có mốc khám xong,
    # gán loại khám Phụ khoa cho visit
    await q.pool.execute(
        """
        UPDATE appointment SET status = 'CHECKED_IN'
         WHERE id = (SELECT appointment_id FROM visit WHERE visit_id = $1::uuid)
        """,
        q.visit_id,
    )
    await q.pool.execute(
        "UPDATE visit SET service_type_id = $2::uuid, checked_in_at = now(),"
        " exam_completed_at = NULL, status = 'OPEN' WHERE visit_id = $1::uuid",
        q.visit_id,
        st_phukhoa,
    )
    # Bác sĩ bắt đầu khám: consultation in_progress
    await q.pool.execute(
        "UPDATE consultation SET status = 'in_progress', started_by = $2::uuid,"
        " doctor_staff_id = $2::uuid WHERE id = $1::uuid",
        q.consultation_id,
        q.bac_si.staff_id,
    )
    # Lưu hồ sơ / SOAP
    await q.pool.execute(
        """
        INSERT INTO clinical_record
            (clinic_id, visit_id, soap_subjective, soap_objective,
             soap_assessment, soap_plan)
        VALUES ($1::uuid, $2::uuid, '{"s": "Khám định kỳ"}',
                '{"o": "Bình thường"}', '{"a": "Viêm nhẹ"}', '{"p": "Theo dõi"}')
        ON CONFLICT (visit_id) DO UPDATE SET soap_subjective = EXCLUDED.soap_subjective
        """,
        CLINIC,
        q.visit_id,
    )

    # TRƯỚC KHI HOÀN TẤT (không còn bước ký riêng, CORE-A 23/09/2026) và
    # CHƯA CÓ CHỈ ĐỊNH nào (có chỉ định thì thu được ngay — nhóm 2, 24/09):
    # - cashier board CHƯA có bệnh nhân
    # - PaymentService chưa cho thu
    board_chua_xong = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu"]
    )
    assert not any(i["visit_id"] == q.visit_id for i in board_chua_xong["items"]), (
        "Khi CHƯA hoàn tất khám, bệnh nhân không được hiện ở Thu ngân"
    )

    with pytest.raises(ConflictError, match="Bác sĩ chưa khám xong lượt này"):
        await PaymentService(q.pool).record_payment(
            visit_id=q.visit_id,
            kind="dich_vu",
            idempotency_key=f"test-{uuid.uuid4().hex}",
            amount=None,
            clinic_patient_id=None,
            identity=q.thu_ngan,
        )

    # 2. HOÀN TẤT: khép phiên khám (không khoá hồ sơ)
    from clinicai.services.luot_kham_service import LuotKhamService

    lk_svc = LuotKhamService(q.pool)
    kham_xong_res = await lk_svc.kham_xong(
        consultation_id=q.consultation_id,
        identity=q.bac_si,
    )
    assert kham_xong_res.get("ok") is True

    # Sau kham_xong():
    # - exam_completed_at IS NOT NULL
    # - cashier board CÓ bệnh nhân
    # - đúng dịch vụ từ visit.service_type_id
    # - PaymentService thu thành công
    v_sau = await q.pool.fetchrow(
        "SELECT exam_completed_at, status, finalized_by::text AS ai FROM visit"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert v_sau["exam_completed_at"] is not None
    # HOÀN TẤT = khám xong, KHÔNG khoá (Tuyền chốt 23/09/2026) — không cần ký.
    assert v_sau["status"] != "FINALIZED"
    assert v_sau["ai"] is None

    # Sang /thu-ngan/dich-vu: Cashier board phải thấy bệnh nhân
    board = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu"]
    )
    item = next((i for i in board["items"] if i["visit_id"] == q.visit_id), None)
    assert item is not None, (
        "Bệnh nhân check-in → lưu SOAP → hoàn tất PHẢI xuất hiện trên Thu ngân"
    )

    # Bill có đúng dịch vụ khám (Phụ khoa 220_000)
    assert len(item["services"]) == 1, (
        "services phải có đúng 1 dòng (tiền khám phụ khoa)"
    )
    assert item["services"][0]["name"] == f"Khám phụ khoa {q.duoi}"
    assert item["services"][0]["price"] == 220_000

    hd = item["hoa_don"]["dich_vu"]
    assert hd["thu_duoc"] is True
    assert hd["tong"] == 220_000
    assert len(hd["dong"]) == 1
    assert hd["dong"][0]["ten"] == f"Khám phụ khoa {q.duoi}"
    assert hd["dong"][0]["thanh_tien"] == 220_000

    # PaymentService thu thành công
    pay_res = await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
    )
    assert pay_res["status"] == "PAID"
    da_thu = await q.pool.fetchval(
        "SELECT amount FROM payment WHERE payment_cycle_id = $1::uuid",
        pay_res["payment_cycle_id"],
    )
    assert da_thu == 220_000


async def test_regression_nguon_visit_thang_appointment_khi_lech_loai_kham(
    q: Quay,
) -> None:
    """2. NGUỒN VISIT PHẢI THẮNG APPOINTMENT:
    visit.service_type_id = Phụ khoa (250_000)
    appointment.service_type_id = Nội tiết (350_000)
    → cashier/bill phải lấy Phụ khoa (250_000).
    """
    st_phukhoa = await _tao_loai_kham(
        q.pool, f"PK-THANG-{q.duoi}", f"Khám phụ khoa {q.duoi}", 250_000
    )
    st_noitiet = await _tao_loai_kham(
        q.pool, f"NT-THUA-{q.duoi}", f"Khám nội tiết {q.duoi}", 350_000
    )

    appt_id = await q.pool.fetchval(
        "SELECT appointment_id FROM visit WHERE visit_id = $1::uuid", q.visit_id
    )
    await q.pool.execute(
        "UPDATE appointment SET service_type_id = $2::uuid WHERE id = $1::uuid",
        appt_id,
        st_noitiet,
    )
    await q.pool.execute(
        "UPDATE visit SET service_type_id = $2::uuid, exam_completed_at = now()"
        " WHERE visit_id = $1::uuid",
        q.visit_id,
        st_phukhoa,
    )

    # 1. CashierBoardService phải lấy Phụ khoa (250_000), KHÔNG lấy Nội tiết (350_000)
    board = await CashierBoardService(q.pool).board(
        identity=q.thu_ngan, modes=["dich_vu"]
    )
    item = next((i for i in board["items"] if i["visit_id"] == q.visit_id), None)
    assert item is not None, "Bệnh nhân phải xuất hiện trên bảng thu ngân"

    svcs = item["services"]
    assert len(svcs) == 1, "services phải có đúng 1 dịch vụ khám"
    assert svcs[0]["name"] == f"Khám phụ khoa {q.duoi}", (
        f"Lấy nhầm dịch vụ: {svcs[0]['name']}"
    )
    assert svcs[0]["price"] == 250_000

    # 2. BillService / hoa_don phải tính đúng tiền theo Phụ khoa (250_000)
    hd = item["hoa_don"]["dich_vu"]
    assert hd["thu_duoc"] is True, f"Hoá đơn phải thu được: {hd.get('van_de')}"
    assert hd["tong"] == 250_000, (
        f"Hoá đơn phải có tổng 250_000 (Phụ khoa), nhưng ra {hd['tong']}"
    )
    dong_kham = next((d for d in hd["dong"] if d["source_type"] == "exam"), None)
    assert dong_kham is not None
    assert dong_kham["ten"] == f"Khám phụ khoa {q.duoi}"
    assert dong_kham["thanh_tien"] == 250_000

    # 3. PaymentService thu thành công đúng giá 250_000
    pay_res = await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind="dich_vu",
        idempotency_key=f"test-{uuid.uuid4().hex}",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
    )
    assert pay_res["status"] == "PAID"
    da_thu = await q.pool.fetchval(
        "SELECT amount FROM payment WHERE payment_cycle_id = $1::uuid",
        pay_res["payment_cycle_id"],
    )
    assert da_thu == 250_000


async def test_trigger_integrity_finalized_visit(q: Quay) -> None:
    """Kiểm tra độ chặt chẽ (integrity) của trigger visit_finalized_block_update:
    1. FINALIZED + chỉ set exam_completed_at (+ updated_at) => PASS
    2. FINALIZED + set exam_completed_at + đổi service_type_id => BLOCK
    3. FINALIZED + set exam_completed_at + đổi attending_doctor_id => BLOCK
    4. Đổi exam_completed_at lần thứ hai => BLOCK
    5. FINALIZED -> AMENDED vẫn PASS như cũ
    """
    st1 = await _tao_loai_kham(q.pool, f"ST1-{q.duoi}", f"Khám 1 {q.duoi}", 100_000)
    st2 = await _tao_loai_kham(q.pool, f"ST2-{q.duoi}", f"Khám 2 {q.duoi}", 200_000)

    staff_rows = await q.pool.fetch(
        "SELECT staff_id FROM clinic_membership"
        " WHERE clinic_id = $1::uuid AND is_active LIMIT 2",
        CLINIC,
    )
    doc1 = staff_rows[0]["staff_id"]
    doc2 = staff_rows[1]["staff_id"] if len(staff_rows) > 1 else doc1

    pid = await q.pool.fetchval(
        "SELECT clinic_patient_id FROM visit WHERE visit_id = $1::uuid", q.visit_id
    )

    async def _tao_visit_finalized() -> str:
        vid = await q.pool.fetchval(
            """
            INSERT INTO visit (clinic_id, clinic_patient_id, service_type_id,
                               attending_doctor_id, status, checked_in_at)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, 'OPEN', now())
            RETURNING visit_id::text
            """,
            CLINIC,
            pid,
            st1,
            doc1,
        )
        await q.pool.execute(
            "UPDATE visit SET status = 'FINALIZED', finalized_at = now()"
            " WHERE visit_id = $1::uuid",
            vid,
        )
        return str(vid)

    # 1. FINALIZED + chỉ set exam_completed_at (+ updated_at) => PASS
    v1 = await _tao_visit_finalized()
    await q.pool.execute(
        "UPDATE visit SET exam_completed_at = now(), updated_at = now()"
        " WHERE visit_id = $1::uuid",
        v1,
    )
    v1_kx = await q.pool.fetchval(
        "SELECT exam_completed_at FROM visit WHERE visit_id = $1::uuid", v1
    )
    assert v1_kx is not None

    # 2. FINALIZED + set exam_completed_at + đổi service_type_id => BLOCK
    v2 = await _tao_visit_finalized()
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await q.pool.execute(
            "UPDATE visit SET exam_completed_at = now(), service_type_id = $2::uuid,"
            " updated_at = now() WHERE visit_id = $1::uuid",
            v2,
            st2,
        )

    # 3. FINALIZED + set exam_completed_at + đổi attending_doctor_id => BLOCK
    v3 = await _tao_visit_finalized()
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await q.pool.execute(
            "UPDATE visit SET exam_completed_at = now(),"
            " attending_doctor_id = $2::uuid, updated_at = now()"
            " WHERE visit_id = $1::uuid",
            v3,
            doc2,
        )

    # 4. Đổi exam_completed_at lần thứ hai => BLOCK
    v4 = await _tao_visit_finalized()
    await q.pool.execute(
        "UPDATE visit SET exam_completed_at = now(), updated_at = now()"
        " WHERE visit_id = $1::uuid",
        v4,
    )
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await q.pool.execute(
            "UPDATE visit SET exam_completed_at = now(), updated_at = now()"
            " WHERE visit_id = $1::uuid",
            v4,
        )

    # 5. FINALIZED -> AMENDED vẫn PASS như cũ
    v5 = await _tao_visit_finalized()
    await q.pool.execute(
        "UPDATE visit SET status = 'AMENDED', updated_at = now()"
        " WHERE visit_id = $1::uuid",
        v5,
    )
    v5_status = await q.pool.fetchval(
        "SELECT status FROM visit WHERE visit_id = $1::uuid", v5
    )
    assert v5_status == "AMENDED"
