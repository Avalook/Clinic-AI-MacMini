"""Kiểm kê tiền mặt két đầu ca – cuối ca (31/10/2026), database thật.

    scripts/test-nhanh.sh src/tests/services/test_ket_tien_mat_db.py

Kịch bản: quỹ đầu 1.000.000 → thu tiền mặt 300.000 trong ca → dự kiến 1.300.000
(đúng dòng Tiền mặt của báo cáo ca) → đếm 1.300.000 = khớp. Đếm lệch thì bắt lý
do; Postgres giữ công thức dự kiến / lệch, tổng khớp bảng đếm, không xoá. Mở lại
có lý do, số cũ còn trong vết; sửa quỹ đầu sau khi đếm phải mở lại trước. Quỹ cuối
ca trước gợi ý quỹ đầu ca sau. Báo cáo cuối ngày có khối két.

Mỗi bài dùng CƠ SỞ RIÊNG (như bài chốt ca) — không chạm bài khác cùng DB.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import now_vn
from clinicai.services.ket_tien_mat_service import KetTienMatService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_chot_so_ca_db import (
    _bc,
    _ca_bay_gio,
    _co_so_rieng,
    _luot_o,
    _ql,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_quy_dau_thu_tien_mat_dem_khop(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ma = await _ca_bay_gio(pool)
    ngay = now_vn().date().isoformat()
    svc = KetTienMatService(pool)
    # Đếm theo mệnh giá: 2 × 500k = 1.000.000 (máy chủ cộng).
    await svc.quy_dau(
        identity=ql, ngay=ngay, ca=ma, co_so=cs, dem={"500000": 2, "1000": 0}
    )
    await _luot_o(pool, ca, cs)  # thu 300k tiền mặt trong ca
    xem = await svc.xem(identity=ql, ngay=ngay, ca=ma, co_so=cs)
    bc = await _bc(pool, ql, cs, ca=ma)
    tm = next(r for r in bc["theo_hinh_thuc"] if r["ma"] == "CASH")
    # Cùng nguồn số với báo cáo cuối ca.
    assert xem["tien_mat"]["thuc_thu"] == tm["thuc_thu"] == 300_000
    assert xem["du_kien_song"] == 1_300_000
    kq = await svc.dem_cuoi(
        identity=ql, ngay=ngay, ca=ma, co_so=cs, tong=1_300_000, nguoi_nhan=" Chị Lan "
    )
    assert (kq["du_kien"], kq["lech"]) == (1_300_000, 0)
    xem = await svc.xem(identity=ql, ngay=ngay, ca=ma, co_so=cs)
    k = xem["ket"]
    assert k["da_dem"] and k["nguoi_nhan"] == "Chị Lan"
    assert k["quy_dau_dem"] == {"500000": 2}
    assert [h["hanh_dong"] for h in xem["lich_su"]] == ["QUY_DAU", "DEM_CUOI"]
    # Báo cáo cuối ngày có khối két (cả ngày lẫn đúng ca).
    for kw in ({}, {"ca": ma}):
        r = await _bc(pool, ql, cs, **kw)
        assert [
            (x["quy_dau"], x["du_kien"], x["dem_cuoi"], x["lech"])
            for x in r["ket_tien_mat"]
        ] == [(1_000_000, 1_300_000, 1_300_000, 0)]


async def test_lech_bat_ly_do_mo_lai_co_vet(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ngay = (date.today() - timedelta(days=300)).isoformat()
    svc = KetTienMatService(pool)
    with pytest.raises(ValidationError, match="quỹ đầu"):
        await svc.dem_cuoi(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=0)
    await svc.quy_dau(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=500_000)
    # Sửa quỹ đầu (chưa đếm cuối) bắt lý do.
    with pytest.raises(ValidationError, match="lý do sửa"):
        await svc.quy_dau(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=600_000)
    await svc.quy_dau(
        identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=600_000, ly_do="Gõ nhầm"
    )
    with pytest.raises(ValidationError, match="lý do lệch"):
        await svc.dem_cuoi(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=550_000)
    kq = await svc.dem_cuoi(
        identity=ql,
        ngay=ngay,
        ca="SANG",
        co_so=cs,
        tong=550_000,
        ly_do_lech="Trả lại khách 50k chưa ghi",
    )
    assert kq["lech"] == -50_000
    with pytest.raises(ConflictError, match="Mở lại"):
        await svc.quy_dau(
            identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=1, ly_do="thử sửa"
        )
    with pytest.raises(ConflictError, match="vừa được kiểm kê"):
        await svc.dem_cuoi(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=600_000)
    with pytest.raises(ValidationError, match="lý do mở lại"):
        await svc.mo_lai(identity=ql, ngay=ngay, ca="SANG", co_so=cs, ly_do=" ")
    await svc.mo_lai(
        identity=ql, ngay=ngay, ca="SANG", co_so=cs, ly_do="Tìm thấy 50k kẹp sổ"
    )
    await svc.dem_cuoi(identity=ql, ngay=ngay, ca="SANG", co_so=cs, tong=600_000)
    xem = await svc.xem(identity=ql, ngay=ngay, ca="SANG", co_so=cs)
    assert xem["ket"]["lech"] == 0 and xem["ket"]["ly_do_lech"] is None
    viec = [h["hanh_dong"] for h in xem["lich_su"]]
    assert viec == ["QUY_DAU", "SUA_QUY_DAU", "DEM_CUOI", "MO_LAI", "DEM_CUOI"]
    # Vết MO_LAI giữ số đếm cũ (550k, lệch −50k).
    mo = next(h for h in xem["lich_su"] if h["hanh_dong"] == "MO_LAI")
    assert (mo["ban_chup"]["dem_cuoi"], mo["ban_chup"]["lech"]) == (550_000, -50_000)


async def test_goi_y_quy_dau_tu_ca_truoc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    d = date.today() - timedelta(days=200)
    svc = KetTienMatService(pool)
    await svc.quy_dau(identity=ql, ngay=d.isoformat(), ca="TOI", co_so=cs, tong=0)
    await svc.dem_cuoi(identity=ql, ngay=d.isoformat(), ca="TOI", co_so=cs, tong=0)
    hom_sau = (d + timedelta(days=1)).isoformat()
    xem = await svc.xem(identity=ql, ngay=hom_sau, ca="SANG", co_so=cs)
    assert xem["ket"] is None
    assert xem["goi_y_quy_dau"]["ca"] == "TOI"
    assert xem["goi_y_quy_dau"]["ngay"] == d.isoformat()


async def test_postgres_ep_cong_thuc_va_khong_xoa(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    ql = _ql(ca)
    cs = await _co_so_rieng(pool)
    ngay = (date.today() - timedelta(days=100)).isoformat()
    svc = KetTienMatService(pool)
    kq = await svc.quy_dau(
        identity=ql, ngay=ngay, ca="CHIEU", co_so=cs, dem={"200000": 3}
    )
    kid = kq["id"]
    # Tổng lệch bảng đếm.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE ket_tien_mat_ca SET quy_dau = 1 WHERE id = $1::uuid", kid
        )
    # Mệnh giá lạ trong bảng đếm.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE ket_tien_mat_ca SET quy_dau_dem = $2::jsonb WHERE id = $1::uuid",
            kid,
            json.dumps({"300000": 2}),
        )
    # Dự kiến sai công thức / lệch không lý do.
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE ket_tien_mat_ca SET dem_cuoi = 0, thu_tien_mat = 0, du_kien = 1,"
            " lech = -1, dem_boi = quy_dau_boi, dem_luc = now() WHERE id = $1::uuid",
            kid,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE ket_tien_mat_ca SET dem_cuoi = 0, thu_tien_mat = 0,"
            " du_kien = 600000, lech = -600000, dem_boi = quy_dau_boi,"
            " dem_luc = now() WHERE id = $1::uuid",
            kid,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM ket_tien_mat_ca WHERE id = $1::uuid", kid)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM ket_tien_mat_ca_lich_su WHERE ket_id = $1::uuid", kid
        )


@pytest.mark.parametrize(
    ("ngay", "ca_"),
    [("rác", "SANG"), ("2026-13-45", "SANG"), (None, "TOI"), ("2026-10-01", "DEM")],
)
async def test_ngay_ca_rac_thi_422(
    pool: asyncpg.Pool,  # noqa: F811
    ngay: object,
    ca_: object,
) -> None:
    ca = await _dung(pool)
    cs = await _co_so_rieng(pool)
    with pytest.raises(ValidationError):
        await KetTienMatService(pool).xem(identity=_ql(ca), ngay=ngay, ca=ca_, co_so=cs)
