"""V8 (30/09/2026): khách CHỈ ĐẾN MUA THUỐC — lượt Bán lẻ.

Mở lượt (khách có sẵn / khách mới, một lượt đang mở mỗi khách) · quầy thấy lượt
khi chưa có đơn · kê dòng QUAY + thu tiền thuốc (không tiền khám) · thu xong tự
đóng lượt (tiền mặt và chuyển khoản sau xác minh) · báo cáo / điều phối / hành
trình / check-out loại lượt bán lẻ ra, doanh thu thuốc vẫn tính.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import uuid
from typing import Any

import pytest

from clinicai.services import ban_thuoc_service
from clinicai.services.ban_le_service import BanLeService
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.checkout_service import CheckoutService
from clinicai.services.dispatch_service import DispatchService
from clinicai.services.payment_service import PaymentService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi
from tests.services.test_tien_thuoc_cp1_db import Quay, _thuoc, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _khach(q: Quay, ten: str = "Khách mua thuốc") -> str:
    return str(
        await q.pool.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " SELECT $1::uuid, $2, $3, primary_location_id FROM staff"
            " WHERE id = $4::uuid RETURNING clinic_patient_id::text",
            CLINIC,
            f"BL-{uuid.uuid4().hex[:8]}",
            ten,
            q.thu_ngan.staff_id,
        )
    )


async def _mo(q: Quay, pid: str) -> str:
    kq = await BanLeService(q.pool).mo_luot(identity=q.duoc_si, clinic_patient_id=pid)
    return str(kq["visit_id"])


async def _ke_va_hoa_don(q: Quay, vid: str, gia: int = 12_000) -> dict[str, Any]:
    drug = await _thuoc(q, gia=gia)
    await QuayThuocService(q.pool).luu_dong_them(
        visit_id=vid,
        dong=[{"drug_catalog_id": drug, "quantity": "3 viên", "dosage": "Sáng 1"}],
        identity=q.thu_ngan,
    )
    return await BanLeService(q.pool).doc(visit_id=vid, identity=q.thu_ngan)


async def _thu(q: Quay, vid: str, rev: str, method: str = "CASH") -> dict[str, Any]:
    return await PaymentService(q.pool).record_payment(
        visit_id=vid,
        kind="thuoc",
        amount=None,
        clinic_patient_id=None,
        identity=q.thu_ngan,
        bill_revision=rev,
        method=method,
    )


async def test_mo_luot_khong_kham_va_quay_thay_khi_chua_co_don(q: Quay) -> None:
    pid = await _khach(q)
    vid = await _mo(q, pid)
    v = await q.pool.fetchrow(
        "SELECT ban_le, checked_in_at, service_type_id, appointment_id,"
        " attending_doctor_id, closed_at FROM visit WHERE visit_id = $1::uuid",
        vid,
    )
    assert v["ban_le"] is True
    assert (v["checked_in_at"], v["service_type_id"], v["appointment_id"]) == (
        None,
        None,
        None,
    )
    assert (v["attending_doctor_id"], v["closed_at"]) == (None, None)
    # Không vào hàng chờ nào, không mở việc nào.
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM queue_entry WHERE visit_id = $1::uuid", vid
        )
        == 0
    )
    # Bấm lại (hay người khác bấm) → CÙNG lượt.
    kq = await BanLeService(q.pool).mo_luot(identity=q.thu_ngan, clinic_patient_id=pid)
    assert (kq["visit_id"], kq["moi"]) == (vid, False)
    # Màn Nhà thuốc thấy lượt dù chưa có dòng đơn.
    man = await ban_thuoc_service.man_nha_thuoc(q.pool, identity=q.duoc_si)
    [luot] = [x for x in man["luot"] if x["visit_id"] == vid]
    assert (luot["ban_le"], luot["dong"], luot["giai_doan"]) == (True, [], "SAN_SANG")
    assert man["duoc_mo_ban_le"] is True


async def test_ke_thu_khong_tien_kham_va_tu_dong_luot(q: Quay) -> None:
    pid = await _khach(q)
    vid = await _mo(q, pid)
    doc = await _ke_va_hoa_don(q, vid, gia=12_000)
    hd = doc["hoa_don"]
    # Chỉ tiền thuốc: 3 × 12.000 — không có dòng tiền khám.
    assert (hd["tong"], hd["thu_duoc"]) == (36_000, True)
    assert [d["source_type"] for d in hd["dong"]] == ["prescription"]
    assert doc["duoc_thu"] is True
    kq = await _thu(q, vid, hd["revision"])
    assert kq["status"] == "PAID"
    v = await q.pool.fetchrow(
        "SELECT closed_at, closed_by_staff_id::text AS ai FROM visit"
        " WHERE visit_id = $1::uuid",
        vid,
    )
    assert v["closed_at"] is not None and v["ai"] == q.thu_ngan.staff_id
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM event_log WHERE aggregate_id = $1"
            " AND event_type = 'visit.ban_le_closed'",
            vid,
        )
        == 1
    )
    sau = await BanLeService(q.pool).doc(visit_id=vid, identity=q.thu_ngan)
    assert (sau["da_thu"], sau["da_dong"]) == (True, True)
    # Lượt đã đóng → lần mua sau là một lượt MỚI.
    moi = await _mo(q, pid)
    assert moi != vid


async def test_chuyen_khoan_chi_dong_luot_khi_xac_minh(q: Quay) -> None:
    vid = await _mo(q, await _khach(q))
    hd = (await _ke_va_hoa_don(q, vid))["hoa_don"]
    cho = await _thu(q, vid, hd["revision"], method="QR")
    assert cho["status"] == "PENDING_VERIFICATION"
    assert (
        await q.pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", vid
        )
        is None
    )
    doc = await BanLeService(q.pool).doc(visit_id=vid, identity=q.thu_ngan)
    assert doc["cho_xac_minh"]["payment_cycle_id"] == cho["payment_cycle_id"]
    await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=cho["payment_cycle_id"],
        visit_id=vid,
        kind="thuoc",
        reference=None,
        identity=q.thu_ngan,
    )
    assert (
        await q.pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", vid
        )
        is not None
    )


async def test_luot_kham_thuong_thu_thuoc_khong_bi_dong(q: Quay) -> None:
    """Chốt ngược: lượt KHÁM thu tiền thuốc xong vẫn mở (đóng ở quầy check-out)."""
    drug = await _thuoc(q, gia=5_000)
    await QuayThuocService(q.pool).luu_dong_them(
        visit_id=q.visit_id,
        dong=[{"drug_catalog_id": drug, "quantity": "2 viên"}],
        identity=q.thu_ngan,
    )
    async with q.pool.acquire() as conn:
        from clinicai.services.bill_service import tinh_hoa_don

        hd = await tinh_hoa_don(
            conn, clinic_id=CLINIC, visit_id=q.visit_id, kind="thuoc"
        )
    await _thu(q, q.visit_id, hd.revision)
    assert (
        await q.pool.fetchval(
            "SELECT closed_at FROM visit WHERE visit_id = $1::uuid", q.visit_id
        )
        is None
    )


async def test_bao_cao_va_cac_bang_loai_luot_ban_le(q: Quay) -> None:
    vid = await _mo(q, await _khach(q))
    hd = (await _ke_va_hoa_don(q, vid, gia=20_000))["hoa_don"]
    # Trước khi thu: lượt đang mở vẫn KHÔNG vào điều phối / hành trình / check-out.
    async with q.pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT primary_location_id::text FROM staff WHERE id = $1::uuid",
            q.thu_ngan.staff_id,
        )
        ql = await _nguoi(conn, loc, "MANAGEMENT")
    tong_quan = await DispatchService(q.pool).overview(clinic_id=CLINIC)
    assert vid not in {p["visit_id"] for p in tong_quan}
    ht = await BangHanhTrinhService(q.pool).hom_nay(identity=ql)
    assert vid not in {x["visit_id"] for x in ht["luot"]}
    cho_dong = await CheckoutService(q.pool).pending_list(identity=ql)
    assert vid not in {x["visit_id"] for x in cho_dong}

    truoc = await BaoCaoCuoiNgayService(q.pool).bao_cao(identity=ql)
    await _thu(q, vid, hd["revision"])
    sau = await BaoCaoCuoiNgayService(q.pool).bao_cao(identity=ql)
    # Doanh thu thuốc VẪN tính…
    assert sau["tong"]["thu"] - truoc["tong"]["thu"] == 60_000
    thuoc = {x["ma"]: x for x in sau["theo_loai"]}["thuoc"]
    assert thuoc["thu"] - {x["ma"]: x for x in truoc["theo_loai"]}["thuoc"]["thu"] == (
        60_000
    )
    # …nhưng không phải lượt khám.
    assert sau["khach"]["so_luot_kham"] == truoc["khach"]["so_luot_kham"]
    assert sau["khach"]["so_luot_da_thu"] == truoc["khach"]["so_luot_da_thu"]
    assert sau["khach"]["so_luot_ban_le"] == truoc["khach"]["so_luot_ban_le"] + 1


async def test_khach_moi_tao_ho_so_va_trung_sdt(q: Quay) -> None:
    sdt = "09" + str(uuid.uuid4().int)[:8]
    svc = BanLeService(q.pool)
    kq = await svc.mo_luot(
        identity=q.duoc_si,
        khach_moi={"ho_ten": "Nguyễn Thị Mua", "sdt": sdt, "nam_sinh": "abc"},
    )
    assert kq["moi"] is True and kq["ten_khach"] == "Nguyễn Thị Mua"
    by = await q.pool.fetchval(
        "SELECT birth_year FROM patient WHERE clinic_patient_id = $1::uuid",
        kq["clinic_patient_id"],
    )
    assert by is None  # năm sinh rác → bỏ trống, không chặn
    # Cùng SĐT, khách mới khác → báo trùng, không tạo gì.
    trung = await svc.mo_luot(
        identity=q.duoc_si, khach_moi={"ho_ten": "Người khác", "sdt": sdt}
    )
    assert trung["trung"] is True
    assert [m["clinic_patient_id"] for m in trung["matches"]] == [
        kq["clinic_patient_id"]
    ]
    # Tìm theo tên không dấu, theo SĐT.
    tim = await svc.tim_khach(q="nguyen thi mua", identity=q.duoc_si)
    assert kq["clinic_patient_id"] in {x["clinic_patient_id"] for x in tim["items"]}
    tim = await svc.tim_khach(q=sdt[-6:], identity=q.duoc_si)
    assert kq["clinic_patient_id"] in {x["clinic_patient_id"] for x in tim["items"]}
    assert (await svc.tim_khach(q=" a ", identity=q.duoc_si))["items"] == []
