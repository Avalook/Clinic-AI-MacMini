"""Tồn tiền ngày cũ phải hiện, và chỉ thuộc phòng khám/cơ sở được chọn."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.bao_cao_viec_tien_service import doc_viec_tien
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.tien_thua_service import TienThuaService
from tests.services.test_doi_tac_tu_thu_db import _nguoi_vai
from tests.services.test_tien_thua_phan_e_db import _da_thu_roi_bo
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp2_db import _thu_pt, _xm

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_cho_ngay_cu_va_xac_minh(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    ck = await _thu_pt(q, "TRANSFER")
    cid = q.thu_ngan.clinic_id
    async with pool.acquire() as conn:
        bc = await doc_viec_tien(conn, cid, co_so=None, loai=None)
        assert ck["payment_cycle_id"] in {r["id"] for r in bc["cho_xac_minh"]["ds"]}
        khac = await doc_viec_tien(conn, str(uuid.uuid4()), co_so=None, loai=None)
        assert khac["cho_xac_minh"]["so_tien"] == 0
        sai_cs = await doc_viec_tien(conn, cid, co_so=str(uuid.uuid4()), loai=None)
        assert sai_cs["cho_xac_minh"]["so_tien"] == 0
        thuoc = await doc_viec_tien(conn, cid, co_so=None, loai="thuoc")
        assert ck["payment_cycle_id"] not in {
            r["id"] for r in thuoc["cho_xac_minh"]["ds"]
        }
    await _xm(q, ck["payment_cycle_id"], f"FT{uuid.uuid4().hex}")
    async with pool.acquire() as conn:
        sau = await doc_viec_tien(conn, cid, co_so=None, loai=None)
        assert sau["cho_xac_minh"]["so_tien"] == bc["cho_xac_minh"]["so_tien"] - 150000
    report = await BaoCaoCuoiNgayService(pool).bao_cao(
        identity=q.thu_ngan,
        tu="2000-01-01",
        den="2000-01-01",
    )
    assert report["tong"]["thuc_thu"] == 0
    assert report["can_xu_ly"]["cho_xac_minh"] == sau["cho_xac_minh"]


async def test_hoan_cho_khong_tru_thuc_thu_va_xac_nhan_het_cho(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    order = await _da_thu_roi_bo(q, 300000)
    line = await pool.fetchrow(
        "SELECT id::text, payment_cycle_id::text FROM payment_bill_line"
        " WHERE clinic_id = $1::uuid AND source_id = $2",
        q.thu_ngan.clinic_id,
        order,
    )
    assert line is not None
    ql = await _nguoi_vai(q, "MANAGEMENT")
    svc = HoanTienService(pool)
    refund = await svc.tao(
        identity=ql,
        payment_cycle_id=line["payment_cycle_id"],
        visit_id=q.visit_id,
        kind="dich_vu",
        dong=[{"payment_bill_line_id": line["id"], "so_luong": 1}],
        method="TRANSFER",
        reason="Khách không làm dịch vụ",
    )
    async with pool.acquire() as conn:
        bc = await doc_viec_tien(conn, ql.clinic_id, co_so=None, loai=None)
        assert refund["refund_id"] in {r["id"] for r in bc["hoan_cho"]["ds"]}
        assert q.visit_id not in {r["visit_id"] for r in bc["tien_thua"]["ds"]}
    await svc.xac_nhan(
        identity=ql,
        refund_id=refund["refund_id"],
        reference=f"HT{uuid.uuid4().hex}",
    )
    async with pool.acquire() as conn:
        sau = await doc_viec_tien(conn, ql.clinic_id, co_so=None, loai=None)
        assert sau["hoan_cho"]["so_tien"] == bc["hoan_cho"]["so_tien"] - 300000


async def test_tien_thua_luot_cu_va_giu_lai(pool: asyncpg.Pool) -> None:
    q = await tao_quay(pool)
    await _da_thu_roi_bo(q, 300000)
    await pool.execute(
        "UPDATE visit SET created_at = now() - interval '10 days',"
        " checked_in_at = now() - interval '10 days' WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    async with pool.acquire() as conn:
        bc = await doc_viec_tien(conn, q.thu_ngan.clinic_id, co_so=None, loai=None)
        row = next(r for r in bc["tien_thua"]["ds"] if r["visit_id"] == q.visit_id)
        assert row["so_tien"] == 300000
    await TienThuaService(pool).giu_lai(
        identity=q.thu_ngan,
        visit_id=q.visit_id,
        ly_do="Khách gửi lại",
    )
    async with pool.acquire() as conn:
        sau = await doc_viec_tien(conn, q.thu_ngan.clinic_id, co_so=None, loai=None)
        assert q.visit_id not in {r["visit_id"] for r in sau["tien_thua"]["ds"]}
