"""Dịch vụ khách trả đối tác (billing_owner = EXTERNAL_PARTNER) KHÔNG được vào tiền
phòng khám ở BẤT KỲ đầu ra nào: phiếu thu, file Excel hoá đơn, danh sách hoá đơn,
báo cáo cuối ngày, báo cáo hàng hoá (Tuyền 16/10: "chị thấy note thu hộ đối tác rồi
mà vẫn bị tính về báo cáo của mình?").

Bất biến (kiểm với MỌI tập con chỉ định, MỌI hình thức thu):
  · phiếu thu = tổng các dòng phòng khám đã chọn, không cộng đối tác;
  · Excel hoá đơn / danh sách hoá đơn: không dòng đối tác, tổng đúng;
  · báo cáo cuối ngày: tiền đối tác chỉ nằm ở khối `doi_tac` (tham khảo).
DB dùng chung → so HIỆU (sau − trước).
"""

from __future__ import annotations

import itertools
import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import now_vn
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.danh_sach_hoa_don_service import DanhSachHoaDonService
from clinicai.services.payment_service import PaymentService
from clinicai.services.xuat_hoa_don_service import XuatHoaDonService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_quay_thu_mot_hoa_don_db import _dong, _kich_ban
from tests.services.test_tien_thuoc_cp2_db import _xm

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_GIA = {"sa": 250_000, "soi": 300_000, "hpv": 900_000}
_PHI_KHAM = 150_000
_TAP_CON = [
    c for n in range(1, 4) for c in itertools.combinations(("sa", "soi", "hpv"), n)
]


@pytest.mark.parametrize("hinh_thuc", ["CASH", "TRANSFER"])
@pytest.mark.parametrize("chon", _TAP_CON, ids=lambda c: "+".join(c))
async def test_dich_vu_doi_tac_khong_vao_tien_phong_kham(
    pool: asyncpg.Pool, chon: tuple[str, ...], hinh_thuc: str
) -> None:
    q, sa, soi, hpv = await _kich_ban(pool)
    id_ = {"sa": sa, "soi": soi, "hpv": hpv}
    ql = await _nguoi_vai(q1 := q, "MANAGEMENT")
    ngay = now_vn().date().isoformat()
    xuat = XuatHoaDonService(pool)
    ds = DanhSachHoaDonService(pool)
    bao_cao = BaoCaoCuoiNgayService(pool)
    truoc = await bao_cao.bao_cao(identity=ql)

    qt = (await _dong(q1))["quay_thu"]
    kq: dict[str, Any] = await PaymentService(pool).record_payment(
        visit_id=q1.visit_id,
        kind="dich_vu",
        amount=sum(_GIA[c] for c in chon if c != "hpv") + _PHI_KHAM,
        bill_revision=None,
        clinic_patient_id=None,
        identity=q1.thu_ngan,
        method=hinh_thuc,
        idempotency_key=f"dtkv-{uuid.uuid4().hex}",
        chon={
            "order_ids_seen": qt["lua_chon"]["order_ids_seen"],
            "selected_order_ids": [id_[c] for c in chon],
            "expected_selection_revision": qt["lua_chon"]["revision"],
        },
    )
    chi_pk = sum(_GIA[c] for c in chon if c != "hpv") + _PHI_KHAM
    cycle = kq["payment_cycle_id"]
    if hinh_thuc == "TRANSFER":  # chuyển khoản phải xác minh mới thành PAID
        await _xm(q1, cycle, f"FT{uuid.uuid4().hex[:8]}")

    # (1) phiếu thu + dòng đã chụp: không có dòng đối tác nào gắn "phòng khám thu".
    assert (
        int(
            await pool.fetchval(
                "SELECT amount FROM payment_cycle WHERE payment_cycle_id=$1::uuid",
                cycle,
            )
        )
        == chi_pk
    )
    dong = await pool.fetch(
        "SELECT name_snapshot, billing_owner, line_total FROM payment_bill_line"
        " WHERE payment_cycle_id=$1::uuid",
        cycle,
    )
    assert sum(int(r["line_total"]) for r in dong) == chi_pk
    assert all(r["billing_owner"] == "CLINIC" for r in dong)
    assert not any(str(r["name_snapshot"]).startswith("HPV") for r in dong)

    # (2) Excel hoá đơn + danh sách hoá đơn.
    hd = {
        h["payment_cycle_id"]: h
        for h in (await xuat.xem(identity=ql, tu=ngay, den=ngay))["hoa_don"]
    }[cycle]
    assert hd["tong"] == chi_pk
    assert not any(d["ten"].startswith("HPV") for d in hd["dong"])
    khach = (await ds.xem(identity=ql, tu=ngay, den=ngay))["khach"]
    phieu = next(p for k in khach for p in k["phieu"] if p["id"] == cycle)
    assert sum(int(d["thanh_tien"]) for d in phieu["dong"]) == chi_pk

    # (3) báo cáo cuối ngày: thực thu tăng đúng phần phòng khám.
    sau = await bao_cao.bao_cao(identity=ql)
    assert int(sau["tong"]["thu"]) - int(truoc["tong"]["thu"]) == chi_pk
    assert int(sau["tong"]["thuc_thu"]) - int(truoc["tong"]["thuc_thu"]) == chi_pk
    assert sau["doi_tac"]["tong"] == truoc["doi_tac"]["tong"]  # chưa ghi đã thu
