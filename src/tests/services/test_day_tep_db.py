"""Tải lên lưu ổ VPS trước, đẩy sang Viettel CFS sau (01/10/2026) — lớp DB.

· Tải lên: dòng ``vi_tri='vps'`` + tệp ở ổ VPS; CFS không bị chạm.
· Đẩy: sha khớp → ``vi_tri='cfs'``; sha lệch → không đánh dấu, cộng lỗi,
  lùi dần; CFS treo → dừng lô, KHÔNG cộng lỗi cho tệp.
· Dọn bản VPS: 7 ngày + trần — không bao giờ xoá tệp chưa đẩy.
· V9 xoá mềm / khôi phục / job dọn đúng với cả hai vị trí.
· CHECK, canh gác, migration chạy 2 lần.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import threading
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.core import kho_tep
from clinicai.services import canh_gac, day_tep, don_tep_ket_qua, media_service
from clinicai.services import tep_ket_qua_service as tep_mod
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_staff,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase/migrations/20261001000000_tep_luu_vps_truoc.sql"
)


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    kho_tep.mo_lai()
    yield p
    kho_tep.mo_lai()
    await p.close()


@pytest.fixture
def hai_o(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> tuple[Path, Path]:
    vps, cfs = tmp_path / "vps", tmp_path / "cfs"
    vps.mkdir()
    cfs.mkdir()
    monkeypatch.setattr(media_service, "MEDIA_LOCAL_ROOT", vps)
    monkeypatch.setattr(media_service, "MEDIA_ROOT", cfs)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", cfs)
    monkeypatch.setattr(tep_mod, "MEDIA_LOCAL_MIN_FREE_BYTES", 0)
    monkeypatch.setattr(tep_mod, "MEDIA_MIN_FREE_BYTES", 0)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return vps, cfs


async def _dung(pool: asyncpg.Pool) -> dict[str, Any]:
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
    return {"doc": doc, "pid": pid, "oid": oid}


async def _tai(pool: asyncpg.Pool, d: dict[str, Any]) -> str:
    kq = await TepKetQuaService(pool).tai_len(
        identity=d["doc"],
        clinic_patient_id=d["pid"],
        data=PDF_DUMMY,
        ten_hien_thi="kq.pdf",
        service_order_id=d["oid"],
    )
    return str(kq["id"])


async def _dong(pool: asyncpg.Pool, tep: str) -> asyncpg.Record:
    r = await pool.fetchrow(
        "SELECT khoa, vi_tri, da_day_luc, so_lan_day_loi, loi_day_cuoi,"
        "       day_loi_luc, da_xoa_ban_vps_luc, sha256"
        "  FROM tep_ket_qua WHERE id = $1::uuid",
        tep,
    )
    assert r is not None
    return r


async def _chi_tep(pool: asyncpg.Pool, tep: str) -> None:
    """Bộ test dùng chung một database: đẩy/dọn chỉ tệp của bài này."""
    await pool.execute(
        "UPDATE tep_ket_qua SET day_loi_luc = now() + interval '1 day',"
        "       so_lan_day_loi = so_lan_day_loi + 20"
        " WHERE vi_tri = 'vps' AND id <> $1::uuid",
        tep,
    )
    await pool.execute(
        "UPDATE tep_ket_qua SET day_loi_luc = NULL, so_lan_day_loi = 0"
        " WHERE id = $1::uuid",
        tep,
    )


async def _lui_moc_xoa(pool: asyncpg.Pool, tep: str) -> None:
    """Đẩy mốc xoá mềm về 31 ngày trước. Trigger V9 cấm sửa vết xoá (đúng luật)
    — bài kiểm tắt trigger trong MỘT phiên để giả lập thời gian trôi."""
    async with pool.acquire() as conn:
        await conn.execute("SET session_replication_role = replica")
        try:
            await conn.execute(
                "UPDATE tep_ket_qua SET da_xoa_luc = now() - interval '31 days',"
                "       tai_len_luc = now() - interval '32 days'"
                " WHERE id = $1::uuid",
                tep,
            )
        finally:
            await conn.execute("RESET session_replication_role")


# ── tải lên ────────────────────────────────────────────────────────────────


async def test_tai_len_ghi_o_vps_khong_cham_cfs(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    tep = await _tai(pool, d)
    r = await _dong(pool, tep)
    assert r["vi_tri"] == "vps" and r["da_day_luc"] is None
    assert (vps / r["khoa"]).read_bytes() == PDF_DUMMY
    assert list(cfs.rglob("*")) == []
    # Đọc: bản ổ VPS.
    p, _mime, so_byte, _ten = await TepKetQuaService(pool).duong_dan_de_doc(
        identity=d["doc"], tep_id=tep
    )
    assert p == (vps / r["khoa"]).resolve() and so_byte == len(PDF_DUMMY)


# ── đẩy ────────────────────────────────────────────────────────────────────


async def test_day_sha_khop_thi_chuyen_cfs_roi_doc_tu_cfs_sau_khi_don(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    tep = await _tai(pool, d)
    await _chi_tep(pool, tep)
    ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert ket["da_day"] >= 1 and ket["bo_qua"] is None
    r = await _dong(pool, tep)
    assert r["vi_tri"] == "cfs" and r["da_day_luc"] is not None
    assert hashlib.sha256((cfs / r["khoa"]).read_bytes()).hexdigest() == r["sha256"]
    # Chưa quá 7 ngày: bản VPS còn, đọc vẫn ưu tiên VPS.
    await day_tep.don_ban_vps(pool, goc_vps=vps)
    assert (vps / r["khoa"]).exists()
    # Quá 7 ngày → xoá bản VPS, ghi mốc; đọc chuyển sang CFS.
    await pool.execute(
        "UPDATE tep_ket_qua SET da_day_luc = now() - interval '8 days'"
        " WHERE id = $1::uuid",
        tep,
    )
    kq = await day_tep.don_ban_vps(pool, goc_vps=vps)
    assert kq["het_han"] >= 1
    assert not (vps / r["khoa"]).exists()
    assert (await _dong(pool, tep))["da_xoa_ban_vps_luc"] is not None
    p, *_ = await TepKetQuaService(pool).duong_dan_de_doc(identity=d["doc"], tep_id=tep)
    assert p == (cfs / r["khoa"]).resolve()


async def test_sha_lech_khong_danh_dau_va_lui_dan(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    tep = await _tai(pool, d)
    await _chi_tep(pool, tep)
    r = await _dong(pool, tep)
    (vps / r["khoa"]).write_bytes(PDF_DUMMY + b"hong")
    ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert ket["loi"] == 1 and ket["da_day"] == 0
    r = await _dong(pool, tep)
    assert r["vi_tri"] == "vps" and r["so_lan_day_loi"] == 1
    assert "sha256" in r["loi_day_cuoi"] and r["day_loi_luc"] is not None
    assert not (cfs / r["khoa"]).exists()
    # Đang lùi dần (60s sau lần lỗi 1): lượt ngay sau không chọn lại.
    ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert ket["loi"] == 0
    # Hết thời gian lùi + tệp đã sửa → đẩy được.
    (vps / r["khoa"]).write_bytes(PDF_DUMMY)
    await pool.execute(
        "UPDATE tep_ket_qua SET day_loi_luc = now() - interval '2 minutes'"
        " WHERE id = $1::uuid",
        tep,
    )
    ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert ket["da_day"] == 1
    assert (await _dong(pool, tep))["vi_tri"] == "cfs"


async def test_cfs_treo_thi_dung_lo_khong_cong_loi(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    tep = await _tai(pool, d)
    await _chi_tep(pool, tep)
    nha = threading.Event()

    def _treo(*_a: Any) -> None:
        nha.wait(5)

    monkeypatch.setattr(day_tep, "chep_va_kiem", _treo)
    monkeypatch.setattr(day_tep, "han_day", lambda _n: 0.2)
    try:
        ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    finally:
        nha.set()
    assert ket["bo_qua"] == "kho_cham"
    r = await _dong(pool, tep)
    assert r["vi_tri"] == "vps" and r["so_lan_day_loi"] == 0
    assert kho_tep.dang_ngat("cfs") and not kho_tep.dang_ngat("vps")


# ── dọn bản VPS: không bao giờ xoá tệp chưa đẩy ─────────────────────────────


async def test_tran_chi_xoa_ban_da_day_cu_nhat_khong_dung_tep_chua_day(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    # Xoá sạch ổ VPS của bài: dọn mọi dòng đã đẩy của các bài khác khỏi phạm vi.
    await pool.execute(
        "UPDATE tep_ket_qua SET da_xoa_ban_vps_luc = now()"
        " WHERE vi_tri = 'cfs' AND da_day_luc IS NOT NULL"
        "   AND da_xoa_ban_vps_luc IS NULL"
    )
    cu, moi, chua = await _tai(pool, d), await _tai(pool, d), await _tai(pool, d)
    for t in (cu, moi):
        await _chi_tep(pool, t)
        await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    await pool.execute(
        "UPDATE tep_ket_qua SET da_day_luc = now() - interval '2 days'"
        " WHERE id = $1::uuid",
        cu,
    )
    # Tệp chưa đẩy CŨ hơn mọi tệp khác — vẫn không được đụng.
    await pool.execute(
        "UPDATE tep_ket_qua SET tai_len_luc = now() - interval '30 days'"
        " WHERE id = $1::uuid",
        chua,
    )
    k = {t: (await _dong(pool, t))["khoa"] for t in (cu, moi, chua)}
    co = len(PDF_DUMMY)
    # Trần = 2 tệp: xoá đúng MỘT bản đã đẩy cũ nhất.
    kq = await day_tep.don_ban_vps(pool, goc_vps=vps, tran=2 * co)
    assert kq["vuot_tran"] == 1
    assert not (vps / k[cu]).exists() and (vps / k[moi]).exists()
    assert (vps / k[chua]).exists()
    # Trần = 0: xoá hết bản đã đẩy, tệp chưa đẩy VẪN còn.
    await day_tep.don_ban_vps(pool, goc_vps=vps, tran=1)
    assert not (vps / k[moi]).exists()
    assert (vps / k[chua]).read_bytes() == PDF_DUMMY
    r = await _dong(pool, chua)
    assert r["vi_tri"] == "vps" and r["da_xoa_ban_vps_luc"] is None


async def test_check_khong_cho_danh_dau_xoa_ban_vps_cua_tep_chua_day(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    d = await _dung(pool)
    tep = await _tai(pool, d)
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE tep_ket_qua SET da_xoa_ban_vps_luc = now() WHERE id = $1::uuid",
            tep,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "UPDATE tep_ket_qua SET vi_tri = 'khac' WHERE id = $1::uuid", tep
        )


# ── V9 với hai vị trí ──────────────────────────────────────────────────────


async def test_v9_xoa_mem_khoi_phuc_va_don_voi_tep_o_vps(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    vps, cfs = hai_o
    d = await _dung(pool)
    dv = TepKetQuaService(pool)
    tep = await _tai(pool, d)
    khoa = (await _dong(pool, tep))["khoa"]
    await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="tải nhầm")
    await dv.khoi_phuc_tep(identity=d["doc"], tep_id=tep)
    # Khôi phục xong vẫn đẩy được (trigger V9 không chặn các cột đẩy).
    await _chi_tep(pool, tep)
    await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert (await _dong(pool, tep))["vi_tri"] == "cfs"

    # Tệp CHƯA đẩy, xoá mềm quá 30 ngày → job dọn xoá bản VPS, ghi đã dọn, và
    # từ đó không còn trong hàng đẩy.
    tep2 = await _tai(pool, d)
    khoa2 = (await _dong(pool, tep2))["khoa"]
    await dv.xoa_tep(identity=d["doc"], tep_id=tep2, ly_do="trùng")
    await _lui_moc_xoa(pool, tep2)
    # Tệp đã đẩy, xoá mềm quá 30 ngày → xoá CẢ bản CFS lẫn bản VPS còn giữ.
    await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="nhầm khách")
    await _lui_moc_xoa(pool, tep)
    kq = await don_tep_ket_qua.mot_luot(
        pool, goc=cfs, goc_vps=vps, kiem_kho=lambda: (True, "")
    )
    assert kq["bo_qua"] is None and kq["da_don"] >= 2
    assert not (vps / khoa2).exists()
    assert not (vps / khoa).exists() and not (cfs / khoa).exists()
    for t in (tep, tep2):
        assert (
            await pool.fetchval(
                "SELECT da_don_tep_luc FROM tep_ket_qua WHERE id = $1::uuid", t
            )
            is not None
        )
    await _chi_tep(pool, tep2)
    ket = await day_tep.day_mot_lo(pool, goc_vps=vps, goc_cfs=cfs)
    assert ket["loi"] == 0 and ket["da_day"] == 0
    assert (await _dong(pool, tep2))["vi_tri"] == "vps"


# ── canh gác + /ops + migration ─────────────────────────────────────────────


async def test_canh_gac_dem_tep_cho_lau_va_loi_nhieu(
    pool: asyncpg.Pool, hai_o: tuple[Path, Path]
) -> None:
    d = await _dung(pool)
    async with pool.acquire() as conn:
        truoc = await canh_gac.do_so(conn)
    tep = await _tai(pool, d)
    await pool.execute(
        "UPDATE tep_ket_qua SET tai_len_luc = now() - interval '7 hours',"
        "       so_lan_day_loi = 5, day_loi_luc = now()"
        " WHERE id = $1::uuid",
        tep,
    )
    async with pool.acquire() as conn:
        sau = await canh_gac.do_so(conn)
        so = await day_tep.so_lieu(conn)
    assert sau["tep_cho_lau"] == truoc["tep_cho_lau"] + 1
    assert sau["tep_loi_day"] == truoc["tep_loi_day"] + 1
    ma = {k.ma for k in canh_gac.danh_gia(sau) if k.co_chuyen}
    assert {"DAY_TEP_CHO_LAU", "DAY_TEP_LOI"} <= ma
    assert so["cho_day"] >= 1 and so["loi_nang"] >= 1
    assert day_tep.danh_gia_suc_khoe(so)


async def test_migration_chay_hai_lan_va_giu_nghia_view(pool: asyncpg.Pool) -> None:
    sql = MIGRATION.read_text()
    await pool.execute(sql)
    await pool.execute(sql)
    cot = {
        r["column_name"]
        for r in await pool.fetch(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'v_tep_ket_qua_hieu_luc'"
        )
    }
    assert {"vi_tri", "da_day_luc", "da_xoa_ban_vps_luc", "da_xoa_luc"} <= cot
    # Dòng cũ (không khai vi_tri) = đã ở CFS.
    assert (
        await pool.fetchval(
            "SELECT column_default FROM information_schema.columns"
            " WHERE table_name = 'tep_ket_qua' AND column_name = 'vi_tri'"
        )
        == "'cfs'::text"
    )
