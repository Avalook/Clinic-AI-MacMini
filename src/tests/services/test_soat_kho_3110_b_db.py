"""Bộ bài từ lượt soát độc lập đợt kho 31/10/2026 (phần kiểm kho, kiểm ca, vật tư trùng mã)."""

# ruff: noqa: E501, F811
from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services import kho_thuoc_service as kho
from clinicai.services import kiem_ke_ca_service as kk
from clinicai.services import lech_kiem_ke_service as lech
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_check_in_lai_sau_hoan_tac_db import CLINIC, pool  # noqa: F401
from tests.services.test_nhieu_don_vi_ban_db import (
    _ban,
    _giao,
    _lo,
    _luu,
    _thu,
    _thuoc_goi,
    _ton,
    _xuat,
)
from tests.services.test_tien_thuoc_cp1_db import Quay, q, tao_quay  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _huy_phieu
from tests.services.test_vat_tu_ban_kho_db import (
    _lich_bac_si,
    _nhap,
    _phong,
    _thu_thuoc,
    _vt_ma,
)
from tests.services.test_vat_tu_ban_kho_db import _ton as _ton_vt

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chot(q: Quay, pid: str) -> dict[str, Any]:
    xem = await kk.xem_lech(q.pool, identity=q.duoc_si, phieu_id=pid)
    return await kk.chot(
        q.pool,
        identity=q.duoc_si,
        phieu_id=pid,
        ly_do_dong=[{**d, "ly_do": "Đếm lệch"} for d in xem["dong"]],
    )


async def _kiem(q: Quay, drug: str, so: Any, dv: str = "viên") -> str:
    p = await kk.mo_phieu(
        q.pool,
        identity=q.duoc_si,
        ngay=hom_nay_vn().isoformat(),
        ca="TOI",
        loai="DOT_XUAT",
    )
    await kk.luu_dem(
        q.pool,
        identity=q.duoc_si,
        phieu_id=p["id"],
        dong=[{"drug_catalog_id": drug, "don_vi": dv, "dem": so}],
    )
    await _chot(q, p["id"])
    return str(p["id"])


async def test_a_quay_doi_don_vi_sau_hoan_tac(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 60)
    rx = await _ban(q, drug, "2 gói")
    lan = await _thu(q)
    await _huy_phieu(q, lan["payment_cycle_id"])
    await QuayThuocService(q.pool).doi_don_vi(
        prescription_id=rx, don_vi="hộp", identity=q.thu_ngan
    )
    assert (
        await q.pool.fetchval("SELECT unit FROM prescription WHERE id=$1::uuid", rx)
        == "hộp"
    )


async def test_a2_quay_doi_so_luong_sau_hoan_tac(q: Quay) -> None:
    drug = await _thuoc_goi(q)
    await _lo(q, drug, 60)
    rx = await _ban(q, drug, "2 gói")
    lan = await _thu(q)
    await _huy_phieu(q, lan["payment_cycle_id"])
    await QuayThuocService(q.pool).doi_so_luong(
        prescription_id=rx, so_luong=3, identity=q.thu_ngan
    )
    assert (
        await q.pool.fetchval(
            "SELECT quantity_num FROM prescription WHERE id=$1::uuid", rx
        )
        == 3
    )


async def _rx_vt(q: Quay, ma: str, don_vi: str, so: int) -> tuple[str, str]:
    thuoc = str(
        await q.pool.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price, ma_hang, don_vi_ban)"
            " VALUES ($1::uuid, $2, $2, 300000, $3, 'cái') RETURNING id::text",
            CLINIC,
            f"Đầu dò {uuid.uuid4().hex[:6]}",
            ma,
        )
    )
    await q.pool.execute(
        "INSERT INTO thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so, gia, dang_ban, cap_nhat_boi)"
        " VALUES ($1::uuid, $2::uuid, 'hộp', 10, 2800000, true, $3::uuid)",
        CLINIC,
        thuoc,
        q.duoc_si.staff_id,
    )
    rx = str(
        await q.pool.fetchval(
            "INSERT INTO prescription (clinic_id, source_ref, visit_id, clinic_patient_id, drug_name_raw, quantity,"
            " quantity_num, unit, drug_catalog_id, drug_mapped_by, drug_mapped_at, nguon)"
            " SELECT $1::uuid, $2, v.visit_id, v.clinic_patient_id, 'Đầu dò', $3, $4, $8, $5::uuid, $6::uuid, now(), 'QUAY'"
            " FROM visit v WHERE v.visit_id = $7::uuid RETURNING id::text",
            CLINIC,
            f"test-rx-{uuid.uuid4().hex}",
            f"{so} {don_vi}",
            so,
            thuoc,
            q.bac_si.staff_id,
            q.visit_id,
            don_vi,
        )
    )
    return thuoc, rx


async def test_b_trung_ma_ban_hop_tru_sai(pool: asyncpg.Pool) -> None:  # noqa: F811
    q = await tao_quay(pool)
    ma = f"SP{uuid.uuid4().hex[:8]}"
    vt = await _vt_ma(pool, ma)
    room = await _phong(pool, q.thu_ngan.location_id)
    await _nhap(pool, q.thu_ngan, vt, room)
    await _lich_bac_si(pool, q.bac_si.staff_id, room)
    before = await _ton_vt(pool, vt, room)
    await _rx_vt(q, ma, "hộp", 1)
    await _thu_thuoc(q)
    after = await _ton_vt(pool, vt, room)
    assert before - after == 10, "1 hộp = 10 cái"
    dong = await pool.fetchrow(
        "SELECT so_luong, don_gia, thanh_tien FROM vat_tu_ban WHERE vat_tu_id = $1::uuid",
        vt,
    )
    assert dong["so_luong"] == 10
    assert dong["don_gia"] * dong["so_luong"] == dong["thanh_tien"]


async def test_c_trung_ma_co_lo_giao_lo_tru_hai_kho(pool: asyncpg.Pool) -> None:  # noqa: F811
    q = await tao_quay(pool)
    ma = f"SP{uuid.uuid4().hex[:8]}"
    vt = await _vt_ma(pool, ma)
    room = await _phong(pool, q.thu_ngan.location_id)
    await _nhap(pool, q.thu_ngan, vt, room)
    await _lich_bac_si(pool, q.bac_si.staff_id, room)
    thuoc, rx = await _rx_vt(q, ma, "cái", 1)
    lo = await _lo(q, thuoc, 5, don_vi="cái")
    await _thu_thuoc(q)
    with pytest.raises(ValidationError, match="Kho vật tư"):
        await PharmacyService(q.pool).cap_phat(
            identity=q.duoc_si, prescription_id=rx, drug_batch_id=lo, so_luong=1
        )
    assert await _ton(q, lo) == 5, "lô thuốc không được trừ: đã trừ ở kho vật tư"


async def test_d_hoan_tac_phieu_cu_sau_khi_co_phieu_moi(q: Quay) -> None:
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    lo = await _lo(q, drug, 50, don_vi="viên")
    a = await _kiem(q, drug, 45)  # sổ 50 → 45
    assert await _ton(q, lo) == 45
    await _kiem(q, drug, 45)  # phiếu sau xác nhận 45
    with pytest.raises(ConflictError, match="lần kiểm sau"):
        await kk.hoan_tac_dieu_chinh(q.pool, identity=q.duoc_si, phieu_id=a)
    assert await _ton(q, lo) == 45


async def test_e_sua_so_cu_sau_khi_co_phieu_moi(q: Quay) -> None:
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    lo = await _lo(q, drug, 50, don_vi="viên")
    a = await _kiem(q, drug, 45)
    await _kiem(q, drug, 45)
    dong = await q.pool.fetchval(
        "SELECT id::text FROM kiem_ke_ca_dong WHERE kiem_ke_ca_id=$1::uuid", a
    )
    with pytest.raises(ConflictError, match="lần kiểm sau"):
        await lech.sua_so_sau_cung(
            q.pool,
            identity=q.duoc_si,
            nguon="CA",
            dong_id=dong,
            so_moi=48,
            ly_do="đếm lại",
        )
    assert await _ton(q, lo) == 45


async def test_f_kiem_kho_quay_giao_sau_dem(q: Quay) -> None:
    """Đếm 50 lúc 08:00, giao 5 lúc 08:05, lưu 08:10."""
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    lo = await _lo(q, drug, 50, don_vi="viên")
    rx = await _ban(q, drug, "5 viên")
    await _thu(q)
    moc = (await q.pool.fetchval("SELECT clock_timestamp()")).isoformat()
    await _giao(q, rx, 5)
    await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=str(uuid.uuid4()),
        dong=[{"drug_batch_id": lo, "thuc_te": 50, "dem_luc": moc}],
    )
    assert await _ton(q, lo) == 45


async def test_g_kho_ui_lech_khac_may_chu(q: Quay) -> None:
    """Hai lô, N = 5, lô A đếm 45/50, lô B đếm 25/30: màn thấy lệch 0 cả hai (ô lý do ẩn)."""
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    rx = await _ban(q, drug, "5 viên")
    await _thu(q)
    await _giao(q, rx, 5)  # chờ gán 5
    a = await _lo(q, drug, 50, don_vi="viên")
    b = await _lo(q, drug, 30, don_vi="viên")
    await kho.kiem_kho(
        q.pool,
        identity=q.duoc_si,
        khoa_gui=str(uuid.uuid4()),
        dong=[
            {"drug_batch_id": a, "thuc_te": 45, "ly_do": "chờ gán"},
            {"drug_batch_id": b, "thuc_te": 25, "ly_do": "chờ gán"},
        ],
    )
    # Sổ trừ N chờ gán đúng một lần trên cả thuốc: tổng sổ − 5 = kệ 70.
    assert await _ton(q, a) + await _ton(q, b) - 5 == 70


async def test_h_thuoc_tra_cho_kiem_dem_ca_khay(q: Quay) -> None:
    """Thuốc khách trả chờ kiểm vẫn nằm trong sổ quầy, nên kiểm ca đếm cả khay ấy; huỷ thì sổ và kệ cùng bớt."""
    drug = await _luu(q, f"Thuoc {uuid.uuid4().hex[:6]}", gia=1000, don_vi_ban="viên")
    lo = await _lo(q, drug, 50, don_vi="viên")
    rx = await _ban(q, drug, "10 viên")
    await _thu(q)
    await _giao(q, rx, 10)
    (x,) = await _xuat(q, rx)
    kq = await PharmacyService(q.pool).khach_tra_thuoc(
        identity=q.duoc_si,
        dispense_txn_id=x["id"],
        so_luong=3,
        ly_do="Khách trả",
        ket_cuc_tien="HOAN",
    )
    await _kiem(q, drug, 43)
    await PharmacyService(q.pool).xu_ly_thuoc_tra(
        identity=q.duoc_si,
        drug_return_id=kq["drug_return_id"],
        quyet_dinh="HUY",
        ly_do="Hỏng bao bì",
    )
    assert await _ton(q, lo) == 40


async def test_i_hoan_tac_giao_vat_tu_khi_da_giao_du(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Giao đủ rồi vẫn hoàn tác được: dòng về chưa giao, sổ vật tư giữ nguyên, giao lại được."""
    q = await tao_quay(pool)
    ma = f"SP{uuid.uuid4().hex[:8]}"
    vt = await _vt_ma(pool, ma)
    room = await _phong(pool, q.thu_ngan.location_id)
    await _nhap(pool, q.thu_ngan, vt, room)
    await _lich_bac_si(pool, q.bac_si.staff_id, room)
    _, rx = await _rx_vt(q, ma, "cái", 1)
    await _thu_thuoc(q)
    ton = await _ton_vt(pool, vt, room)
    await _giao(q, rx, 1)
    await PharmacyService(pool).hoan_tac_giao_vat_tu(
        identity=q.duoc_si, prescription_id=rx, ly_do="Giao nhầm"
    )
    dong = await pool.fetchrow(
        "SELECT dispensed_qty FROM prescription WHERE id=$1::uuid", rx
    )
    assert dong["dispensed_qty"] == 0
    assert await _ton_vt(pool, vt, room) == ton
    await _giao(q, rx, 1)
    assert (
        await pool.fetchval(
            "SELECT dispensed_qty FROM prescription WHERE id=$1::uuid", rx
        )
        == 1
    )
