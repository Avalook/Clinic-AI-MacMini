"""Bộ bài từ lượt soát độc lập đợt kho 31/10/2026: mỗi bài là một tình huống đã từng sai."""

# ruff: noqa: E501, F811
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import bao_cao_cuoi_ngay_service as bc
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services import lech_kiem_ke_service as lech
from clinicai.services import vat_tu_ban_service as vb
from clinicai.services.don_vi_thuoc import kiem_doi_don_vi_goc
from clinicai.services.payment_service import PaymentService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_nhieu_don_vi_ban_db import (
    _ban,
    _dong_rx,
    _giao,
    _han,
    _ke,
    _lo,
    _luu,
    _thu,
    _thuoc_goi,
    _ton,
    _xuat,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _huy_phieu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_1_hoan_tac_1_goi_khong_giam_da_giao(q: Quay) -> None:
    """Bán 1 hộp (30 gói): lô A còn 1 gói hạn sớm, lô B 59. Hoàn tác lần giao 1 gói."""
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 1, han=_han(100))
    await _lo(q, drug, 59, han=_han(400))
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    ds = await _xuat(q, rx)
    lan_1 = next(x for x in ds if x["so"] == 1)
    await PharmacyService(q.pool).hoan_tac_giao(
        identity=q.duoc_si, dispense_txn_id=lan_1["id"]
    )
    r = await _dong_rx(q, rx)
    assert Decimal(str(r["dispensed_qty"])) < 1, (
        "đã về quầy 1 gói mà dòng vẫn 'đã giao đủ 1 hộp'"
    )


async def test_2_hoan_tac_29_goi_roi_giao_du_31_goi(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    a = await _lo(q, drug, 1, han=_han(100))
    b = await _lo(q, drug, 59, han=_han(400))
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    await _giao(q, rx, 1)
    ds = await _xuat(q, rx)
    lan_29 = next(x for x in ds if x["so"] == 29)
    await PharmacyService(q.pool).hoan_tac_giao(
        identity=q.duoc_si, dispense_txn_id=lan_29["id"]
    )
    with pytest.raises(ValidationError, match="không giao quá"):
        await _giao(q, rx, 1)
    await _giao(q, rx, 29, don_vi_giao="gói")
    ton = await _ton(q, a) + await _ton(q, b)
    assert ton == 30, f"giao đúng 30 gói cho 1 hộp thì tồn phải còn 30, thấy {ton}"


async def test_3_hoan_tac_10_goi_khong_giao_lai_duoc(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 60)
    rx = await _ban(q, drug, "1 hộp")
    await _thu(q)
    for _ in range(3):
        await _giao(q, rx, 10, don_vi_giao="gói")
    ds = await _xuat(q, rx)
    await PharmacyService(q.pool).hoan_tac_giao(
        identity=q.duoc_si, dispense_txn_id=ds[0]["id"]
    )
    await _giao(q, rx, 10, don_vi_giao="gói")
    r = await _dong_rx(q, rx)
    assert Decimal(str(r["dispensed_qty"])) == 1


async def test_4_void_sau_hoan_bao_cao_tru_hai_lan(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 60)
    rx = await _ban(q, drug, "10 gói")
    lan = await _thu(q)
    await _giao(q, rx, 10)
    (x,) = await _xuat(q, rx)
    await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=x["id"],
        so_luong=3,
        ly_do="Khách dị ứng",
        ket_cuc_tien="HOAN",
    )
    xem = await PaymentService(q.pool).xem_truoc_hoan_tac(
        payment_cycle_id=lan["payment_cycle_id"], identity=q.thu_ngan
    )
    await _huy_phieu(q, lan["payment_cycle_id"])
    hn = hom_nay_vn()
    kq = bc.gom_bao_cao(
        tu=hn,
        den=hn,
        lan_thu=[
            {
                "id": lan["payment_cycle_id"],
                "status": "VOIDED",
                "amount": xem["da_thu"],
                "kind": "thuoc",
                "method": "CASH",
                "paid_at": None,
                "closed_at": None,
                "visit_id": q.visit_id,
                "da_hoan": xem["da_hoan"],
                "da_hoan_tm": xem["da_hoan"],
            }
        ],
        hoan=[
            {
                "refund_id": "r",
                "amount": xem["da_hoan"],
                "status": "COMPLETED",
                "method": "CASH",
                "kind": "thuoc",
                "created_at": None,
            }
        ],
        dong=[],
        doi_tac=[],
        so_luot_kham=0,
    )
    # Két thật: +thu − hoàn lẻ − phần trả lúc hoàn tác = 0.
    assert kq["tong"]["thuc_thu"] == 0


async def test_5_don_vi_viet_tat_kiem_ca_tru_hai_lan(q: Quay) -> None:
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    rx = await _ke(q, drug, "10 v")
    await _thu(q)
    await _giao(q, rx, 10)  # chưa có lô: vào chờ gán
    await _lo(q, drug, 50, don_vi="viên")
    ids = q.duoc_si
    p = await kk.mo_phieu(
        q.pool, identity=ids, ngay=hom_nay_vn().isoformat(), ca="TOI", loai="DOT_XUAT"
    )
    # kệ thật: 50 − 10 đã giao = 40
    await kk.luu_dem(
        q.pool,
        identity=ids,
        phieu_id=p["id"],
        dong=[{"drug_catalog_id": drug, "don_vi": "viên", "dem": 40}],
    )
    xem = await kk.xem_lech(q.pool, identity=ids, phieu_id=p["id"])
    assert not xem["dong"], "kệ khớp, phần chờ gán phải được tách"


async def test_7_den_ngay_cuc_dai(q: Quay) -> None:
    await lech.ds_lech(q.pool, identity=q.duoc_si, tu="2026-10-01", den="9999-12-31")


async def test_8_den_ngay_cuc_dai_vat_tu(q: Quay) -> None:
    await vb.doc_ban(q.pool, identity=q.duoc_si, tu="2026-10-01", den="9999-12-31")


async def test_9_huy_cho_gan_van_chan_doi_goc(q: Quay) -> None:
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    rx = await _ban(q, drug, "5 viên")
    await _thu(q)
    await _giao(q, rx, 5)
    d = await q.pool.fetchval(
        "SELECT id::text FROM thuoc_giao_chua_gan_lo WHERE prescription_id = $1::uuid",
        rx,
    )
    await PharmacyService(q.pool).huy_dong_cho_gan_lo(identity=q.duoc_si, dong_id=d)
    async with q.pool.acquire() as conn:
        await kiem_doi_don_vi_goc(conn, q.duoc_si, thuoc=drug, goc_moi="gói")
