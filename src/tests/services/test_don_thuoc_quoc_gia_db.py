"""Liên thông đơn thuốc quốc gia (TT 26/2025, QĐ 808) — hàng chờ trên Postgres.

Mỗi bài dựng một CƠ SỞ riêng (clinic_location mới) nên lượt của bài khác / seed
không lọt vào ứng viên. Nhà cung cấp là `ProviderGiaLap` bơm vào `mot_vong_dtqg`.

Bất biến ép ở Postgres (SO-LUAT Phần 6), test chỉ kiểm KẾT QUẢ:
  · `uq_dtqg_gui_phien_ban` — hai bên cùng vào hàng một nội dung → một dòng.
  · `FOR UPDATE SKIP LOCKED` — hai bên cùng gửi → hệ thống quốc gia nhận một lần.
  · trigger `dtqg_gui_chi_di_tiep` — sự việc đã ghi không sửa / xoá.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.adapters.don_thuoc_quoc_gia.gia_lap import KhongKy, ProviderGiaLap
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import CauHinh, doc_cau_hinh_dtqg
from clinicai.services.don_thuoc_quoc_gia.gui import GO_HET_SAU_KHI_GUI
from clinicai.services.don_thuoc_quoc_gia.vong import mot_vong_dtqg
from tests.services.test_don_thuoc_quoc_gia_anh_xa_db import (
    _canh,
    _go_het,
    _luot,
    _them_dong,
)
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_phieu_kham_db import pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _dong_hang(p: asyncpg.Pool, vid: str) -> list[Any]:
    rows: list[Any] = await p.fetch(
        "SELECT g.*, public.dtqg_trang_thai(g) AS tt FROM dtqg_gui g"
        " WHERE g.clinic_id = $1::uuid AND g.visit_id = $2::uuid ORDER BY phien_ban",
        CLINIC,
        vid,
    )
    return rows


async def _vong(
    p: asyncpg.Pool, c: dict[str, Any], gl: ProviderGiaLap
) -> dict[str, Any]:
    return await mot_vong_dtqg(p, env=c["env"], nha_cung_cap=(gl, KhongKy()))


def _ch(c: dict[str, Any]) -> CauHinh:
    ch = doc_cau_hinh_dtqg(c["env"])
    assert isinstance(ch, CauHinh), ch
    return ch


async def test_don_chot_vao_hang_va_gui(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    ket = await _vong(pool, c, gl)
    assert (ket["vao_hang"], ket["da_gui"]) == (1, 1)
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["phien_ban"], r["nha_cung_cap"], r["so_lan_thu"]) == (
        "DA_GUI",
        1,
        "GIA_LAP",
        1,
    )
    assert r["ma_don"].startswith("79abc") and r["ma_don"].endswith("-c")
    goi = gl.da_nhan[r["ma_don"]]
    assert goi.bac_si is not None and goi.bac_si.so_chung_chi == "000123/HCM-CCHN"
    assert (goi.chan_doan, goi.nguoi_benh.ngay_sinh) == ("Viêm âm đạo", "1990-05-17")
    assert [t.ten_thuoc for t in goi.thuoc] == ["Thuốc 0"]


async def test_luot_chua_dong_khong_vao_hang(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c, dong=False)
    gl = ProviderGiaLap()
    assert (await _vong(pool, c, gl))["vao_hang"] == 0
    assert await _dong_hang(pool, vid) == [] and gl.loi_goi == []


async def test_cong_tac_tat_khong_doi_gi(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    truoc = await pool.fetchval("SELECT count(*) FROM canh_bao")
    gl = ProviderGiaLap()
    for tat in ({**c["env"], "DTQG_BAT": ""}, {**c["env"], "DTQG_BAT": "0"}):
        assert await mot_vong_dtqg(pool, env=tat, nha_cung_cap=(gl, KhongKy())) == {
            "tat": True
        }
    assert await _dong_hang(pool, vid) == [] and gl.loi_goi == []
    assert await pool.fetchval("SELECT count(*) FROM canh_bao") == truoc


async def test_bat_ma_cau_hinh_sai_mo_canh_bao_khong_ghi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    ket = await mot_vong_dtqg(pool, env={**c["env"], "DTQG_MA_CO_SO": "x"})
    assert any("DTQG_MA_CO_SO" in x for x in ket["loi_cau_hinh"])
    assert await _dong_hang(pool, vid) == [] and gl.loi_goi == []
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM canh_bao WHERE ma = 'DTQG_CAU_HINH_SAI'"
            " AND dong_luc IS NULL"
        )
        == 1
    )
    # Sửa cấu hình → vòng sau đóng cảnh báo và gửi bình thường.
    assert (await _vong(pool, c, gl))["da_gui"] == 1
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM canh_bao WHERE ma = 'DTQG_CAU_HINH_SAI'"
            " AND dong_luc IS NULL"
        )
        == 0
    )


async def test_idempotent_hai_vong_mot_dong(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    await _vong(pool, c, gl)
    ket = await _vong(pool, c, gl)
    assert (ket["vao_hang"], ket["da_gui"]) == (0, 0)
    assert len(await _dong_hang(pool, vid)) == 1 and len(gl.loi_goi) == 1


async def test_sua_sau_khi_gui_thanh_don_thay_the(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    await _vong(pool, c, gl)
    await _them_dong(pool, c, vid, "Thuốc thêm")
    await _vong(pool, c, gl)
    v1, v2 = await _dong_hang(pool, vid)
    assert (v1["tt"], v2["tt"], v2["phien_ban"]) == ("DA_GUI", "DA_GUI", 2)
    assert v1["ma_don"] != v2["ma_don"]
    assert len(gl.da_nhan[v2["ma_don"]].thuoc) == 2


async def test_loi_mang_thu_lai_roi_thanh_cong(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap(hong_lan_toi=1)
    assert (await _vong(pool, c, gl))["da_gui"] == 0
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["so_lan_thu"]) == ("CHO_GUI", 1)
    assert "GIA_LAP: hết giờ chờ" in r["loi_cuoi"]
    # Chưa tới giờ thử lại → vòng sau không gửi.
    assert (await _vong(pool, c, gl))["da_gui"] == 0
    await pool.execute("UPDATE dtqg_gui SET thu_lai_luc = now() WHERE id = $1", r["id"])
    assert (await _vong(pool, c, gl))["da_gui"] == 1
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["so_lan_thu"], r["loi_cuoi"]) == ("DA_GUI", 2, None)


async def test_het_luot_thu_thanh_loi_va_canh_bao(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap(hong_lan_toi=10)
    for _ in range(3):
        await pool.execute(
            "UPDATE dtqg_gui SET thu_lai_luc = now()"
            " WHERE visit_id = $1::uuid AND het_luot_luc IS NULL",
            vid,
        )
        ket = await _vong(pool, c, gl)
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["so_lan_thu"]) == ("LOI", 3)
    assert ket["loi"] >= 1
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM canh_bao WHERE ma = 'DTQG_LOI' AND dong_luc IS NULL"
        )
        == 1
    )


async def test_bi_tu_choi_dung_ngay(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap(tu_choi_lan_toi=1)
    await _vong(pool, c, gl)
    (r,) = await _dong_hang(pool, vid)
    assert (r["tt"], r["so_lan_thu"]) == ("LOI", 1)


async def test_thieu_cchn_roi_bo_sung_thanh_ban_moi(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool, cchn=None)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    await _vong(pool, c, gl)
    (r,) = await _dong_hang(pool, vid)
    assert r["tt"] == "LOI" and gl.loi_goi == []
    assert r["loi_cuoi"].startswith("THIEU_DU_LIEU: số chứng chỉ hành nghề")
    await pool.execute(
        "UPDATE staff SET license_number = '000999/HCM' WHERE id = $1::uuid", c["bs"]
    )
    await _vong(pool, c, gl)
    v1, v2 = await _dong_hang(pool, vid)
    assert (v1["tt"], v2["tt"]) == ("BI_THAY", "DA_GUI")


async def test_go_het_sau_khi_gui_bao_nguoi(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    await _vong(pool, c, gl)
    await _go_het(pool, c, vid)
    await _vong(pool, c, gl)
    v1, v2 = await _dong_hang(pool, vid)
    assert (v1["tt"], v2["tt"], v2["la_huy"]) == ("DA_GUI", "LOI", True)
    assert v2["loi_cuoi"] == GO_HET_SAU_KHI_GUI
    assert len(gl.loi_goi) == 1


async def test_go_het_truoc_khi_gui_khong_can(pool: asyncpg.Pool) -> None:  # noqa: F811
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap(hong_lan_toi=1)
    await _vong(pool, c, gl)  # v1 hỏng, chờ thử lại
    await _go_het(pool, c, vid)
    await _vong(pool, c, gl)
    v1, v2 = await _dong_hang(pool, vid)
    assert (v1["tt"], v2["tt"]) == ("BI_THAY", "KHONG_CAN")
    await pool.execute(
        "UPDATE dtqg_gui SET thu_lai_luc = now() WHERE id = $1", v1["id"]
    )
    assert (await _vong(pool, c, gl))["da_gui"] == 0
    assert len(gl.loi_goi) == 1


async def test_doi_sdt_sau_khi_gui_khong_sinh_don_thay_the(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Lễ tân sửa SĐT / địa chỉ sau khi đơn đã lên hệ thống: đơn thuốc không đổi →
    KHÔNG gửi đơn thay thế (người bệnh không cầm hai mã cho một đơn)."""
    c = await _canh(pool)
    vid = await _luot(pool, c)
    gl = ProviderGiaLap()
    await _vong(pool, c, gl)
    await pool.execute(
        "UPDATE patient SET phone_primary = '0900000001', address = 'DEMO mới'"
        " WHERE clinic_patient_id = (SELECT clinic_patient_id FROM visit"
        "  WHERE visit_id = $1::uuid)",
        vid,
    )
    assert (await _vong(pool, c, gl))["vao_hang"] == 0
    assert len(await _dong_hang(pool, vid)) == 1 and len(gl.loi_goi) == 1
