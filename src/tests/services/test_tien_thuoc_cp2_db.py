"""Contract tiền–thuốc CP2 (19/09/2026).

Đầu CP2 — lỗi review CP1 #8: bác sĩ lưu lại bệnh án sau khi tiền thuốc đã thu
làm `_replace_prescriptions` xoá rồi chèn lại dòng đơn chưa cấp. Ảnh chụp hoá
đơn còn, nhưng dòng đơn gốc — nguồn để nhà thuốc giao — biến mất.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (khai qua pytest_plugins thì
# không nạp khi chạy trọn bộ); tham số `q` của từng test là chính fixture ấy.

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _du_lo,
    _hd,
    _thu,
    _thuoc,
    q,  # noqa: F401
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _luu_don(q: Quay, dong: list[dict[str, Any]]) -> None:
    """Đúng như `save()`: khoá dòng visit trước, rồi thay đơn thuốc."""
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE",
                q.visit_id,
            )
            pid = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
                q.visit_id,
            )
            await ClinicalRecordService(q.pool)._replace_prescriptions(
                conn,
                visit_id=q.visit_id,
                clinic_patient_id=pid,
                prescriptions=dong,
                clinic_id=CLINIC,
                created_by=q.bac_si.staff_id,
            )


async def _don_da_thu(q: Quay) -> tuple[str, str]:
    rx = await _don(q, 10, ten="Thuốc đã thu")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _thu(q, "thuoc", bill_revision=(await _hd(q, "thuoc")).revision)
    return rx, "10 viên"


async def _cac_dong(q: Quay) -> list[asyncpg.Record]:
    return list(
        await q.pool.fetch(
            "SELECT id::text, drug_name_raw, quantity, dosage_instructions"
            " FROM prescription WHERE visit_id = $1::uuid ORDER BY created_at",
            q.visit_id,
        )
    )


async def test_da_thu_tien_luu_lai_giu_nguyen_dong_chi_doi_lieu_dung(q: Quay) -> None:
    rx, sl = await _don_da_thu(q)
    await _luu_don(
        q,
        [{"id": rx, "drug_name": "Thuốc đã thu", "quantity": sl, "dosage": "Sáng 1"}],
    )
    dong = await _cac_dong(q)
    assert [(d["id"], d["dosage_instructions"]) for d in dong] == [(rx, "Sáng 1")]


async def test_da_thu_tien_khong_xoa_dong_duoc(q: Quay) -> None:
    rx, _ = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="đã thu tiền"):
        await _luu_don(q, [])
    assert [d["id"] for d in await _cac_dong(q)] == [rx]


async def test_da_thu_tien_khong_doi_so_luong_duoc(q: Quay) -> None:
    rx, _ = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="đã thu tiền"):
        await _luu_don(
            q, [{"id": rx, "drug_name": "Thuốc đã thu", "quantity": "20 viên"}]
        )
    assert (await _cac_dong(q))[0]["quantity"] == "10 viên"


async def test_da_thu_tien_khong_them_thuoc_duoc(q: Quay) -> None:
    rx, sl = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="không thêm thuốc"):
        await _luu_don(
            q,
            [
                {"id": rx, "drug_name": "Thuốc đã thu", "quantity": sl},
                {"id": None, "drug_name": "Thuốc thêm", "quantity": "5 viên"},
            ],
        )
    assert [d["id"] for d in await _cac_dong(q)] == [rx]


async def test_chua_thu_tien_van_thay_don_nhu_cu(q: Quay) -> None:
    rx = await _don(q, 10, ten="Nháp")
    await _luu_don(q, [{"id": None, "drug_name": "Thuốc khác", "quantity": "3 viên"}])
    dong = await _cac_dong(q)
    assert [d["drug_name_raw"] for d in dong] == ["Thuốc khác"]
    assert rx not in {d["id"] for d in dong}


# ── Payment cycle: mỗi lần thu một dòng ───────────────────────────────────


async def _rev(q: Quay, kind: str = "dich_vu") -> str:
    r: str = (await _hd(q, kind)).revision
    return r


async def _thu_pt(q: Quay, method: str, kind: str = "dich_vu") -> dict[str, Any]:
    if kind == "thuoc":
        await _du_lo(q)
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind=kind,
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=await _rev(q, kind),
        method=method,
    )


async def _cycles(q: Quay) -> list[asyncpg.Record]:
    return list(
        await q.pool.fetch(
            "SELECT payment_cycle_id::text, status, method, amount, paid_at,"
            " closed_at, reference, payment_id FROM payment_cycle"
            " WHERE visit_id = $1::uuid ORDER BY created_at",
            q.visit_id,
        )
    )


async def test_17_thu_a_huy_a_thu_b_lich_su_du_ca_hai(q: Quay) -> None:
    a = await _thu_pt(q, "CASH")
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=a["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Bấm nhầm khách",
        identity=q.thu_ngan,
    )
    b = await _thu_pt(q, "CASH")
    cs = await _cycles(q)
    assert [(c["payment_cycle_id"], c["status"]) for c in cs] == [
        (a["payment_cycle_id"], "VOIDED"),
        (b["payment_cycle_id"], "PAID"),
    ]
    assert cs[0]["paid_at"] is not None and cs[0]["closed_at"] is not None
    # Hình chiếu `payment` trỏ đúng lần thu hiện tại.
    assert (
        await q.pool.fetchval(
            "SELECT payment_cycle_id::text FROM payment WHERE visit_id = $1::uuid"
            " AND kind = 'dich_vu'",
            q.visit_id,
        )
        == b["payment_cycle_id"]
    )
    lich_su = await CashierBoardService(q.pool).giao_dich(
        identity=q.thu_ngan, tu=None, den=None
    )
    cua_luot = [g for g in lich_su["giao_dich"] if g["visit_id"] == q.visit_id]
    assert {(g["id"], g["trang_thai"], g["phuong_thuc"]) for g in cua_luot} == {
        (a["payment_cycle_id"], "VOIDED", "CASH"),
        (b["payment_cycle_id"], "PAID", "CASH"),
    }


async def _xm(q: Quay, cycle: str, ma: str) -> dict[str, Any]:
    return await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        reference=ma,
        identity=q.thu_ngan,
    )


async def _huy_cho(q: Quay, cycle: str) -> dict[str, Any]:
    return await PaymentService(q.pool).huy_cho_xac_minh(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Khách không chuyển",
        identity=q.thu_ngan,
    )


async def _huy_phieu(q: Quay, cycle: str) -> dict[str, Any]:
    return await PaymentService(q.pool).void_payment(
        payment_cycle_id=cycle,
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Bấm nhầm khách",
        identity=q.thu_ngan,
    )


async def test_chuyen_khoan_cho_xac_minh_chua_phai_da_thu(q: Quay) -> None:
    kq = await _thu_pt(q, "TRANSFER")
    a = kq["payment_cycle_id"]
    assert kq["status"] == "PENDING_VERIFICATION"
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment WHERE visit_id = $1::uuid", q.visit_id
        )
        == 0
    ), "chờ xác minh không được thành phiếu đã thu"
    with pytest.raises(ValidationError, match="mã giao dịch"):
        await _xm(q, a, " ")
    await _xm(q, a, "FT2609191234")
    # Gửi lại cùng mã (mất phản hồi) → thành công như cũ; mã khác → xung đột.
    assert (await _xm(q, a, "FT2609191234"))["da_xac_minh_tu_truoc"] is True
    with pytest.raises(ConflictError, match="mã giao dịch khác"):
        await _xm(q, a, "FT-KHAC")
    [c] = await _cycles(q)
    assert (c["status"], c["method"], c["reference"]) == (
        "PAID",
        "TRANSFER",
        "FT2609191234",
    )
    p = await q.pool.fetchrow(
        "SELECT status, payment_cycle_id::text FROM payment WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert p is not None and (p["status"], p["payment_cycle_id"]) == ("PAID", a)


async def test_dien_tu_khong_the_paid_khong_co_ma_o_db(q: Quay) -> None:
    await _thu_pt(q, "QR")
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "UPDATE payment_cycle SET status = 'PAID', paid_at = now(),"
            " confirmed_by = $2::uuid WHERE visit_id = $1::uuid",
            q.visit_id,
            q.thu_ngan.staff_id,
        )


async def test_bang_gia_doi_trong_luc_cho_van_ghi_da_thu_va_can_doi_soat(
    q: Quay,
) -> None:
    """Review CP2 #3: tiền thật đã vào tài khoản theo ảnh chụp 150.000đ; bảng
    giá đổi sau đó không phủ nhận được khoản ấy."""
    a = (await _thu_pt(q, "TRANSFER"))["payment_cycle_id"]
    await q.pool.execute(
        "UPDATE service_price SET unit_price = 180000 WHERE service_code = $1",
        f"KHAM-{q.duoi}",
    )
    kq = await _xm(q, a, "FT150K")
    assert kq["status"] == "PAID" and kq["can_doi_soat"] is True
    c = await q.pool.fetchrow(
        "SELECT amount, can_doi_soat FROM payment_cycle WHERE payment_cycle_id = $1",
        a,
    )
    assert c is not None and (c["amount"], c["can_doi_soat"]) == (150_000, True)
    assert (
        await q.pool.fetchval(
            "SELECT amount FROM payment WHERE visit_id = $1::uuid", q.visit_id
        )
        == 150_000
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id ="
            " (SELECT id FROM payment WHERE visit_id = $1::uuid)"
            " AND event_type = 'payment.reconciliation_needed'",
            q.visit_id,
        )
        == 1
    )


async def test_hoa_don_khong_doi_thi_khong_can_doi_soat(q: Quay) -> None:
    a = (await _thu_pt(q, "QR"))["payment_cycle_id"]
    assert (await _xm(q, a, "QR-001"))["can_doi_soat"] is False


async def test_huy_cho_roi_thu_lai_duoc(q: Quay) -> None:
    a = (await _thu_pt(q, "TRANSFER"))["payment_cycle_id"]
    # Đang chờ: thu phương thức khác bị chặn cho tới khi huỷ/xác minh.
    with pytest.raises(ConflictError, match="chờ xác minh"):
        await _thu_pt(q, "CASH")
    # Gửi lại đúng lần chờ (cùng hoá đơn, cùng phương thức) → idempotent.
    lai = await _thu_pt(q, "TRANSFER")
    assert (lai["status"], lai["payment_cycle_id"]) == ("PENDING_VERIFICATION", a)
    await _huy_cho(q, a)
    assert (await _huy_cho(q, a))["da_huy_tu_truoc"] is True
    await _thu_pt(q, "CASH")
    assert [c["status"] for c in await _cycles(q)] == ["CANCELLED", "PAID"]


# ── Review CP2 #1: lệnh cũ đến muộn không trượt sang lần thu sau ──────────


async def test_lenh_cu_nham_a_den_muon_khong_dung_b_cho_xac_minh(q: Quay) -> None:
    a = (await _thu_pt(q, "TRANSFER"))["payment_cycle_id"]
    await _huy_cho(q, a)
    b = (await _thu_pt(q, "QR"))["payment_cycle_id"]
    with pytest.raises(ConflictError, match="không còn chờ xác minh"):
        await _xm(q, a, "FT-CUA-A")  # xác minh A đến muộn
    await _huy_cho(q, a)  # huỷ A đến muộn: A đã huỷ → như cũ
    trang = {c["payment_cycle_id"]: c["status"] for c in await _cycles(q)}
    assert trang == {a: "CANCELLED", b: "PENDING_VERIFICATION"}


async def test_huy_phieu_a_den_muon_khong_huy_b(q: Quay) -> None:
    a = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    await _huy_phieu(q, a)
    b = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    kq = await _huy_phieu(q, a)  # lệnh huỷ A cũ đến muộn
    assert kq["da_huy_tu_truoc"] is True
    trang = {c["payment_cycle_id"]: c["status"] for c in await _cycles(q)}
    assert trang == {a: "VOIDED", b: "PAID"}
    assert (
        await q.pool.fetchval(
            "SELECT status FROM payment WHERE visit_id = $1::uuid", q.visit_id
        )
        == "PAID"
    )


async def test_lenh_nham_lan_thu_cua_luot_khac_bi_tu_choi(q: Quay) -> None:
    a = (await _thu_pt(q, "TRANSFER"))["payment_cycle_id"]
    with pytest.raises(NotFoundError):
        await PaymentService(q.pool).xac_minh_dien_tu(
            payment_cycle_id=a,
            visit_id=q.visit_id,
            kind="thuoc",  # đúng lần thu nhưng sai loại
            reference="FT1",
            identity=q.thu_ngan,
        )


# ── Review CP2 #2: lịch sử cũ dựng từ sự kiện đủ bằng chứng ────────────────


async def test_dung_lai_lich_su_cu_tu_su_kien(q: Quay) -> None:
    import json
    import uuid as _uuid

    a, b, thieu = str(_uuid.uuid4()), str(_uuid.uuid4()), str(_uuid.uuid4())

    async def su_kien(loai: str, payload: dict[str, Any], gio: str) -> None:
        await q.pool.execute(
            "INSERT INTO event_log (clinic_id, event_type, aggregate_type,"
            " aggregate_id, payload, metadata, source, event_published,"
            " occurred_at)"
            " VALUES ($1::uuid, $2, 'payment', $3::uuid, $4::jsonb, $5::jsonb,"
            " 'test', false, now() - $6::text::interval)",
            CLINIC,
            loai,
            str(_uuid.uuid4()),
            json.dumps(payload),
            json.dumps({"clinic_staff_id": q.thu_ngan.staff_id}),
            gio,
        )

    goc = {"visit_id": q.visit_id, "kind": "dich_vu"}
    await su_kien(
        "payment.recorded", {**goc, "payment_cycle_id": a, "amount": 100000}, "3 hours"
    )
    await su_kien(
        "payment.voided",
        {**goc, "payment_cycle_id": a, "amount": 100000, "void_reason": "Thu nhầm"},
        "2 hours",
    )
    await su_kien(
        "payment.recorded", {**goc, "payment_cycle_id": b, "amount": 120000}, "1 hour"
    )
    # Thiếu số tiền → không đủ bằng chứng → bỏ qua, không đoán.
    await su_kien("payment.recorded", {**goc, "payment_cycle_id": thieu}, "30 minutes")

    kq = await q.pool.fetchrow("SELECT * FROM payment_cycle_backfill_legacy()")
    assert kq is not None and kq["tu_su_kien"] >= 2
    cs = {
        r["payment_cycle_id"]: r
        for r in await q.pool.fetch(
            "SELECT payment_cycle_id::text, status, amount, legacy, method,"
            " close_reason FROM payment_cycle WHERE visit_id = $1::uuid",
            q.visit_id,
        )
    }
    assert (cs[a]["status"], cs[a]["amount"], cs[a]["close_reason"]) == (
        "VOIDED",
        100000,
        "Thu nhầm",
    )
    assert (cs[b]["status"], cs[b]["amount"]) == ("PAID", 120000)
    assert all(r["legacy"] and r["method"] is None for r in cs.values())
    assert thieu not in cs
    # Chạy lại: không nhân đôi.
    await q.pool.fetchrow("SELECT * FROM payment_cycle_backfill_legacy()")
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE visit_id = $1::uuid", q.visit_id
        )
        == 2
    )
    # Sự kiện dựng lùi 1–3 giờ: chạy trong 00:00–03:00 giờ VN thì lần thu A
    # rơi sang HÔM QUA. Đọc từ hôm qua để test không phụ thuộc giờ chạy (đỏ thật
    # lúc 01:23 ngày 20/09/2026 dù code đúng).
    from datetime import timedelta

    from clinicai.core.clock import now_vn

    hom_qua = (now_vn().date() - timedelta(days=1)).isoformat()
    lich_su = await CashierBoardService(q.pool).giao_dich(
        identity=q.thu_ngan, tu=hom_qua, den=None
    )
    assert {
        (g["id"], g["trang_thai"])
        for g in lich_su["giao_dich"]
        if g["visit_id"] == q.visit_id
    } == {(a, "VOIDED"), (b, "PAID")}


async def _su_kien_thu_cu(q: Quay, cycle: str, amount: int) -> None:
    import json
    import uuid as _uuid

    await q.pool.execute(
        "INSERT INTO event_log (clinic_id, event_type, aggregate_type,"
        " aggregate_id, payload, metadata, source, event_published, occurred_at)"
        " VALUES ($1::uuid, 'payment.recorded', 'payment', $2::uuid, $3::jsonb,"
        " $4::jsonb, 'test', false, now() - interval '1 day')",
        CLINIC,
        str(_uuid.uuid4()),
        json.dumps(
            {
                "visit_id": q.visit_id,
                "kind": "dich_vu",
                "payment_cycle_id": cycle,
                "amount": amount,
            }
        ),
        json.dumps({"clinic_staff_id": q.thu_ngan.staff_id}),
    )


async def _co_lan_thu(q: Quay, cycle: str) -> bool:
    return bool(
        await q.pool.fetchval(
            "SELECT count(*) FROM payment_cycle WHERE payment_cycle_id = $1::uuid",
            cycle,
        )
    )


async def test_khong_hoi_sinh_lan_thu_cu_khi_lan_moi_da_huy(q: Quay) -> None:
    import uuid as _uuid

    # Dòng payment hiện tại là lần thu B, và B đã huỷ.
    b = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    await _huy_phieu(q, b)
    # A cũ chỉ có "đã thu", không có "đã huỷ".
    a = str(_uuid.uuid4())
    await _su_kien_thu_cu(q, a, 90000)

    kq = await q.pool.fetchrow("SELECT * FROM payment_cycle_backfill_legacy()")
    assert not await _co_lan_thu(q, a)
    assert kq is not None and kq["su_kien_bo_qua"] >= 1
    assert [c["status"] for c in await _cycles(q)] == ["VOIDED"]


async def test_chay_lai_sau_khi_b_huy_van_khong_hoi_sinh_a(q: Quay) -> None:
    import uuid as _uuid

    b = (await _thu_pt(q, "CASH"))["payment_cycle_id"]
    a = str(_uuid.uuid4())
    await _su_kien_thu_cu(q, a, 90000)
    await q.pool.fetchrow("SELECT * FROM payment_cycle_backfill_legacy()")
    assert not await _co_lan_thu(q, a)

    await _huy_phieu(q, b)
    await q.pool.fetchrow("SELECT * FROM payment_cycle_backfill_legacy()")
    assert not await _co_lan_thu(q, a)
    assert [c["status"] for c in await _cycles(q)] == ["VOIDED"]


async def test_cho_xac_minh_thuoc_cung_khoa_dong_don(q: Quay) -> None:
    rx = await _don(q, 10)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _thu_pt(q, "QR", kind="thuoc")
    with pytest.raises(ConflictError, match="đã thu"):
        await PharmacyService(q.pool).khai_so_luong_mua(
            identity=q.duoc_si, prescription_id=rx, so_luong=3
        )
    with pytest.raises(ConflictError):
        await _luu_don(q, [])


async def test_19_hai_thu_ngan_bam_cung_luc_chi_mot_lan_thu(q: Quay) -> None:
    import asyncio

    rev = await _rev(q)
    kq = await asyncio.gather(
        *(
            PaymentService(q.pool).record_payment(
                visit_id=q.visit_id,
                kind="dich_vu",
                amount=None,
                clinic_patient_id=None,
                identity=q.thu_ngan,
                bill_revision=rev,
                method="CASH",
            )
            for _ in range(4)
        ),
        return_exceptions=True,
    )
    thanh_cong = [k for k in kq if isinstance(k, dict)]
    assert thanh_cong and len({k["payment_cycle_id"] for k in thanh_cong}) == 1
    assert [c["status"] for c in await _cycles(q)] == ["PAID"]


async def test_so_lan_thu_chi_chuyen_trang_thai_dung_duong(q: Quay) -> None:
    await _thu_pt(q, "CASH")
    for sql in (
        "UPDATE payment_cycle SET amount = 1 WHERE visit_id = $1::uuid",
        "UPDATE payment_cycle SET status = 'PENDING_VERIFICATION'"
        " WHERE visit_id = $1::uuid",
        "DELETE FROM payment_cycle WHERE visit_id = $1::uuid",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await q.pool.execute(sql, q.visit_id)
