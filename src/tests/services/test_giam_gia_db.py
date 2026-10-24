"""Giảm → thu/QR → hoàn tác kiểm bằng giao dịch Postgres thật."""

# ruff: noqa: F811
from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest

from clinicai.api.exceptions import BillChangedError, ValidationError
from clinicai.services.giam_gia_service import huy, them
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, _du_lo, _hd, _thuoc

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def giam(q: Quay, kind: str = "dich_vu", **kwargs: Any) -> dict[str, Any]:
    hd = await _hd(q, kind)
    args = dict(
        visit_id=q.visit_id,
        kind=kind,
        pham_vi="HOA_DON",
        kieu="PHAN_TRAM",
        gia_tri=10,
        ly_do="Khách thân thiết",
        bill_revision=hd.revision,
    )
    args.update(kwargs)
    return await them(q.pool, q.thu_ngan, **args)


async def thu(q: Quay, kind: str = "dich_vu", method: str = "CASH") -> dict[str, Any]:
    return await PaymentService(q.pool).record_payment(
        visit_id=q.visit_id,
        kind=kind,
        amount=None,
        clinic_patient_id=None,
        bill_revision=(await _hd(q, kind)).revision,
        identity=q.thu_ngan,
        method=method,
        idempotency_key=str(uuid4()),
    )


async def test_giam_thu_anh_chup_va_huy_lan_thu_tra_giam(q: Quay) -> None:
    gd = await giam(q)
    assert gd["hoa_don"]["tong"] == 135000
    lan = await thu(q)
    row = await q.pool.fetchrow(
        "SELECT sum(line_total) AS net,sum(giam) AS discount FROM payment_bill_line WHERE payment_cycle_id=$1::uuid",
        lan["payment_cycle_id"],
    )
    assert (int(row["net"]), int(row["discount"])) == (135000, 15000)
    assert (
        await q.pool.fetchval(
            "SELECT so_tien_ap FROM giam_gia WHERE id=$1::uuid", gd["id"]
        )
        == 15000
    )
    with pytest.raises(ValidationError):
        await huy(
            q.pool,
            q.thu_ngan,
            giam_gia_id=gd["id"],
            ly_do="Sửa sai",
            bill_revision=(await _hd(q, "dich_vu")).revision,
        )
    await PaymentService(q.pool).void_payment(
        payment_cycle_id=lan["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Thu nhầm phiếu",
        identity=q.thu_ngan,
    )
    assert (
        await q.pool.fetchval(
            "SELECT payment_cycle_id FROM giam_gia WHERE id=$1::uuid", gd["id"]
        )
        is None
    )
    assert (await _hd(q, "dich_vu")).tong == 135000
    lan2 = await thu(q)
    assert lan2["payment_cycle_id"] != lan["payment_cycle_id"]


async def test_huy_giam_va_revision_cu_bi_chan(q: Quay) -> None:
    old = (await _hd(q, "dich_vu")).revision
    gd = await giam(q)
    with pytest.raises(BillChangedError):
        await giam(q, bill_revision=old, gia_tri=5)
    kq = await huy(
        q.pool,
        q.thu_ngan,
        giam_gia_id=gd["id"],
        ly_do="Khách đổi ý",
        bill_revision=gd["hoa_don"]["revision"],
    )
    assert kq["hoa_don"]["tong"] == 150000 and kq["hoa_don"]["revision"] == old


async def test_hai_nguoi_cung_giam_mot_dong_chi_mot_thang(q: Quay) -> None:
    hd = await _hd(q, "dich_vu")
    d = hd.dong[0]
    args = dict(
        pham_vi="DONG",
        source_type=d.source_type,
        source_id=d.source_id,
        bill_revision=hd.revision,
    )
    result = await asyncio.gather(
        giam(q, **args), giam(q, **args), return_exceptions=True
    )
    assert sum(isinstance(r, dict) for r in result) == 1
    assert sum(isinstance(r, BillChangedError) for r in result) == 1


@pytest.mark.parametrize("kind", ["dich_vu", "thuoc"])
async def test_qr_giam_xac_minh_khong_doi_soat_va_chan_doi(q: Quay, kind: str) -> None:
    if kind == "thuoc":
        rx = await _don(q)
        await PharmacyService(q.pool).xac_dinh_thuoc(
            identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
        )
        await _du_lo(q)
    gd = await giam(q, kind)
    lan = await thu(q, kind, "QR")
    with pytest.raises(ValidationError, match="Huỷ lần chờ"):
        await huy(
            q.pool,
            q.thu_ngan,
            giam_gia_id=gd["id"],
            ly_do="Sửa giảm giá",
            bill_revision=gd["hoa_don"]["revision"],
        )
    kq = await PaymentService(q.pool).xac_minh_dien_tu(
        payment_cycle_id=lan["payment_cycle_id"],
        visit_id=q.visit_id,
        kind=kind,
        identity=q.thu_ngan,
    )
    assert kq["status"] == "PAID"
    assert not await q.pool.fetchval(
        "SELECT EXISTS(SELECT 1 FROM payment_reconciliation_issue WHERE payment_cycle_id=$1::uuid)",
        lan["payment_cycle_id"],
    )


async def test_qr_huy_tra_giam_va_anh_chup_moi(q: Quay) -> None:
    gd = await giam(q)
    lan = await thu(q, method="TRANSFER")
    await PaymentService(q.pool).huy_cho_xac_minh(
        payment_cycle_id=lan["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        reason="Khách trả tiền mặt",
        identity=q.thu_ngan,
    )
    assert (
        await q.pool.fetchval(
            "SELECT payment_cycle_id FROM giam_gia WHERE id=$1::uuid", gd["id"]
        )
        is None
    )
    await thu(q)


async def test_thuoc_giam_dong_anh_chup(q: Quay) -> None:
    rx = await _don(q)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _du_lo(q)
    await giam(
        q,
        "thuoc",
        pham_vi="DONG",
        source_type="prescription",
        source_id=rx,
        kieu="SO_TIEN",
        gia_tri=5000,
    )
    lan = await thu(q, "thuoc")
    r = await q.pool.fetchrow(
        "SELECT line_total,giam FROM payment_bill_line WHERE payment_cycle_id=$1::uuid",
        lan["payment_cycle_id"],
    )
    assert (int(r["line_total"]), int(r["giam"])) == (45000, 5000)
