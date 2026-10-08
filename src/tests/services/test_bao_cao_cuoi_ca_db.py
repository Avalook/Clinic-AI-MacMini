"""Báo cáo CUỐI CA + thuốc kê vs thực bán (08/10/2026) — database thật.

Kịch bản: bác sĩ kê 10 viên, quầy chọn thuốc kho rồi thu → báo cáo phải hiện
thuốc KHO (không phải chữ bác sĩ gõ), kê 10 / thực bán 10, đúng ca chứa giờ thu
và vắng ở ca khác.

DB dùng chung → lọc theo lượt của bài này, không đếm tuyệt đối.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.core.shifts import CAC_CA, ca_tu_settings, khung_chot_ca
from clinicai.services.bao_cao_cuoi_ngay_service import (
    BaoCaoCuoiNgayService,
    csv_bao_cao,
    csv_hang_hoa,
)
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp3_db import _san_sang
from tests.services.test_tien_thuoc_cp3_db import _thu as _thu_thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


def _khach(bc: dict[str, Any], visit_id: str) -> dict[str, Any] | None:
    tt = bc.get("thuoc_theo_khach") or {"khach": []}
    return next((k for k in tt["khach"] if k["visit_id"] == visit_id), None)


@pytest.mark.db
@pytest.mark.asyncio
async def test_thuoc_theo_khach_va_loc_ca(
    pool: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    rx, drug, _lo = await _san_sang(q, so=10)
    th = await _thu_thuoc(q)
    ql = await _nguoi_vai(q, "MANAGEMENT")
    ten_kho, ten_bs = await pool.fetchrow(
        "SELECT c.name_raw, r.drug_name_raw FROM prescription r"
        " JOIN drug_catalog c ON c.id = r.drug_catalog_id WHERE r.id = $1::uuid",
        rx,
    )

    svc = BaoCaoCuoiNgayService(pool)
    bc = await svc.bao_cao(identity=ql, loai="thuoc")
    k = _khach(bc, q.visit_id)
    assert k is not None and len(k["dong"]) == 1
    d = k["dong"][0]
    assert d["ten"] == ten_kho
    assert d["ten_bac_si"] == (ten_bs if ten_bs.lower() != ten_kho.lower() else None)
    assert (d["so_ke"], d["thuc_ban"], d["chenh"], d["trang_thai"]) == (
        10,
        10,
        0,
        "da_ban",
    )
    assert d["thanh_tien"] == k["tien"] > 0
    assert q.thu_ngan.full_name in k["nguoi_thu"]
    assert any(t["ten"] == ten_kho for t in bc["thuoc_theo_khach"]["tieu_hao"])
    assert ten_kho in csv_bao_cao(bc)
    # Hàng hoá khuôn KiotViet: thuốc kho, SL bán 10, doanh thu = tiền dòng.
    hh = {m["ten"]: m for m in bc["hang_hoa"]["thuoc"]["dong"]}
    assert (hh[ten_kho]["sl_ban"], hh[ten_kho]["doanh_thu_thuan"]) == (
        10,
        d["thanh_tien"],
    )
    assert "SL mặt hàng" in csv_hang_hoa(bc, "thuoc")
    # Báo cáo dịch vụ không có khối thuốc.
    assert (await svc.bao_cao(identity=ql, loai="dich_vu"))["thuoc_theo_khach"] is None

    # Ca chứa giờ thu thấy lần thu; ca khác không thấy (so theo giờ THẬT trong DB).
    paid_at, settings = await pool.fetchrow(
        "SELECT pc.paid_at, c.settings FROM payment_cycle pc"
        " JOIN clinic c ON c.id = pc.clinic_id WHERE pc.payment_cycle_id = $1::uuid",
        th["payment_cycle_id"],
    )
    vn = paid_at.astimezone(CLINIC_TZ)
    phut = vn.hour * 60 + vn.minute
    bang = ca_tu_settings(settings)
    ca_thu = next(
        m for m in CAC_CA if (w := khung_chot_ca(m, bang)) and w[0] <= phut < w[1]
    )
    ngay = vn.date().isoformat()
    trong = await svc.bao_cao(identity=ql, tu=ngay, den=ngay, ca=ca_thu)
    assert trong["ca"]["ma"] == ca_thu
    assert _khach(trong, q.visit_id) is not None
    assert th["payment_cycle_id"] not in {
        o["id"] for o in trong["hoan_huy"]
    }  # vẫn PAID
    nguoi = {o["ten"]: o["thu"] for o in trong["theo_nguoi_thu"]}
    assert nguoi.get(q.thu_ngan.full_name, 0) >= d["thanh_tien"]
    for khac in (m for m in CAC_CA if m != ca_thu):
        ngoai = await svc.bao_cao(identity=ql, tu=ngay, den=ngay, ca=khac)
        assert ngoai["ca"]["ma"] == khac
        assert q.thu_ngan.full_name not in {o["ten"] for o in ngoai["theo_nguoi_thu"]}
        assert _khach(ngoai, q.visit_id) is None
    # Ca rác hoặc nhiều ngày → cả ngày, không 500.
    assert (await svc.bao_cao(identity=ql, tu=ngay, den=ngay, ca="ĐÊM"))["ca"] is None
    hom_qua = date.fromordinal(vn.date().toordinal() - 1).isoformat()
    nhieu = await svc.bao_cao(identity=ql, tu=hom_qua, den=ngay, ca=ca_thu)
    assert nhieu["ca"] is None and _khach(nhieu, q.visit_id) is not None
    _ = drug
