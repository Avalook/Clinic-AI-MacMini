"""Báo cáo kho / hàng hoá / tab Thuốc trong kho KHÔNG tính lô mẫu `DEMO1709-*`.

Prod 20/11/2026: lô mẫu nạp 17/09 ghi đơn vị "hộp", lô thật nhập 14/11 ghi "hộp 30
viên" / "viên" → báo cáo kho (gom theo thuốc + đơn vị lô) hiện 2 dòng cho 17 thuốc
và 40 dòng chỉ có lô mẫu, kể cả sau khi lô mẫu đã huỷ về 0 (khoảng mặc định 30
ngày còn thấy tồn đầu + dòng huỷ). Lô mẫu không có thật nên lịch sử của nó cũng
không thuộc báo cáo nào.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

from clinicai.core.clock import CLINIC_TZ, hom_nay_vn
from clinicai.services import kho_thuoc_service
from clinicai.services.kiem_ke_ca_service import xnt_theo_ca
from clinicai.services.lo_mau import LO_MAU_TIEN_TO
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_kho_quay_db import (
    Co,
    _bat,
    _chuyen,
    _id_dich,
    _nhap_kho,
    co,  # noqa: F401
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import _thuoc, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _lo_mau_va_lo_that(co: Co) -> tuple[str, str, str, str]:  # noqa: F811
    """Một thuốc: lô mẫu "hộp" ở KHO (20) + 5 chuyển ra QUẦY, lô thật "viên" 30."""
    await _bat(co)
    thuoc = await _thuoc(co.q)
    mau = await _nhap_kho(co, thuoc, 20)
    await co.q.pool.execute(
        "UPDATE drug_batch SET batch_code = $2, unit = 'hộp' WHERE id = $1::uuid",
        mau,
        f"{LO_MAU_TIEN_TO}{uuid.uuid4().hex[:6]}",
    )
    mau_quay = _id_dich(await _chuyen(co, mau, 5))
    that = await _nhap_kho(co, thuoc, 30)
    return thuoc, mau, mau_quay, that


async def test_bao_cao_kho_mot_dong_chi_lo_that(co: Co) -> None:  # noqa: F811
    thuoc, *_ = await _lo_mau_va_lo_that(co)
    hom_nay = hom_nay_vn().isoformat()
    kq = await kho_thuoc_service.xuat_nhap_ton(
        co.q.pool, identity=co.ds, tu=hom_nay, den=hom_nay
    )
    dong = [d for d in kq["dong"] if d["drug_catalog_id"] == thuoc]
    assert [(d["don_vi"], d["nhap"], d["ton_cuoi"]) for d in dong] == [("viên", 30, 30)]


async def test_hang_hoa_khoi_quay_khong_co_lo_mau(co: Co) -> None:  # noqa: F811
    thuoc, *_ = await _lo_mau_va_lo_that(co)
    async with co.q.pool.acquire() as conn:
        xnt = await xnt_theo_ca(
            conn,
            clinic_id=CLINIC,
            location_id=co.loc,
            tu=datetime.now(CLINIC_TZ) - timedelta(hours=1),
            den=datetime.now(CLINIC_TZ) + timedelta(hours=1),
        )
    assert [r for r in xnt if r["drug_catalog_id"] == thuoc] == []


async def test_tab_thuoc_trong_kho_khong_liet_ke_lo_mau(co: Co) -> None:  # noqa: F811
    thuoc, mau, mau_quay, that = await _lo_mau_va_lo_that(co)
    lo = {
        r["id"]
        for r in await PharmacyService(co.q.pool).ton_kho(identity=co.ds)
        if r["drug_catalog_id"] == thuoc
    }
    assert that in lo and not lo & {mau, mau_quay}
