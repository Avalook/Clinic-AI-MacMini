"""Theo dõi lỗi Pha 1 trên Postgres thật (27/09/2026)."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.core.clock import now_vn
from clinicai.events.catalogue import DONG_THOI_GIAN_LUOT
from clinicai.services import canh_gac, kho_loi, nhat_ky_van_hanh
from tests.chay_nguoi_dua_tin import chay_ben_nhan, chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _loi(msg: str) -> Exception:
    try:
        raise RuntimeError(msg)
    except RuntimeError as e:
        return e


async def test_ghi_loi_cong_don_va_da_sua_ma_tai_dien_thi_mo_lai(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    vi = f"GET /thu/{uuid.uuid4().hex[:8]}"
    try:
        await kho_loi.ghi_loi(pool, nguon="api", vi_tri=vi, exc=_loi("a"))
        await kho_loi.ghi_loi(
            pool, nguon="api", vi_tri=vi, exc=_loi("b 0901234567"), ma_yeu_cau="r1"
        )
        r = await pool.fetchrow("SELECT * FROM loi_nhom WHERE vi_tri = $1", vi)
        assert r is not None and r["so_lan"] == 2 and r["ma_yeu_cau"] == "r1"
        assert "0901234567" not in r["thong_diep"]
        await pool.execute(
            "UPDATE loi_nhom SET trang_thai = 'DA_SUA' WHERE vi_tri = $1", vi
        )
        await kho_loi.ghi_loi(pool, nguon="api", vi_tri=vi, exc=_loi("c"))
        tt = await pool.fetchval(
            "SELECT trang_thai FROM loi_nhom WHERE vi_tri = $1", vi
        )
        assert tt == "MOI", "đã sửa mà tái diễn → mở lại"
    finally:
        await pool.execute("DELETE FROM loi_nhom WHERE vi_tri = $1", vi)


async def test_ghi_loi_khong_bao_gio_nem_khi_db_hong() -> None:
    class PoolHong:
        async def execute(self, *_: object) -> None:
            raise OSError("mất kết nối")

    await kho_loi.ghi_loi(PoolHong(), nguon="api", vi_tri="x", exc=_loi("y"))
    await kho_loi.ghi_loi(None, nguon="api", vi_tri="x", exc=_loi("y"))


async def test_canh_gac_mo_mot_lan_roi_tu_dong(pool: asyncpg.Pool) -> None:  # noqa: F811
    vi = f"GET /canh/{uuid.uuid4().hex[:8]}"
    await pool.execute("DELETE FROM canh_bao WHERE ma = 'LOI_MOI'")
    try:
        await kho_loi.ghi_loi(pool, nguon="api", vi_tri=vi, exc=_loi("mới"))
        await canh_gac.mot_vong(pool)
        await canh_gac.mot_vong(pool)
        mo = await pool.fetch(
            "SELECT so_lan FROM canh_bao WHERE ma = 'LOI_MOI' AND dong_luc IS NULL"
        )
        assert len(mo) == 1 and mo[0]["so_lan"] == 2, "một cảnh báo, cộng dồn"
        # Hết lỗi mới (người trực đánh dấu đã biết) → vòng sau tự đóng.
        await pool.execute(
            "UPDATE loi_nhom SET trang_thai = 'DA_BIET' WHERE trang_thai = 'MOI'"
        )
        await canh_gac.mot_vong(pool)
        con_mo = await pool.fetchval(
            "SELECT count(*) FROM canh_bao WHERE ma = 'LOI_MOI' AND dong_luc IS NULL"
        )
        assert con_mo == 0
    finally:
        await pool.execute("DELETE FROM loi_nhom WHERE vi_tri = $1", vi)
        await pool.execute("DELETE FROM canh_bao WHERE ma = 'LOI_MOI'")


async def test_nhat_ky_co_nguoi_lam_va_chi_so(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    await _kham_va_chi_dinh(pool, ca, visit)
    await chay_ben_nhan(pool, DONG_THOI_GIAN_LUOT)
    kq = await nhat_ky_van_hanh.doc_nhat_ky(
        pool, clinic_id=CLINIC, ngay=now_vn().date().isoformat()
    )
    cua = [d for d in kq["dong"] if d["visit_id"] == visit]
    assert any(d["loai"] == "visit.checked_in" and d["nguoi_lam"] for d in cua)
    [luot] = [x for x in kq["theo_luot"] if x["visit_id"] == visit]
    assert luot["cho_kham"] is not None and luot["cho_kham"] >= 0
    # Ngày rác → hôm nay, không ném.
    rac = await nhat_ky_van_hanh.doc_nhat_ky(pool, clinic_id=CLINIC, ngay="abc")
    assert rac["ngay"] == now_vn().date().isoformat()
