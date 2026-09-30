"""V9 (30/09/2026) — xoá mềm tệp kết quả, hoàn tác 30 ngày, job dọn ổ.

Kiểm ở ba lớp:
  · Postgres: CHECK đủ bộ, chặn DELETE dòng, chặn sửa đè vết xoá, chỉ khôi
    phục khi chưa dọn; view hiệu lực bỏ tệp đã xoá / thu hồi.
  · Service: ai xoá được (`xoa_duoc`), Đính chính khi đã gửi / phiên đọc đóng,
    cùng giao dịch tính lại `ket_qua_luc` + nhật ký + sự kiện; khôi phục.
  · Job dọn: chỉ tệp xoá > 30 ngày chưa từng xem / duyệt / gửi; tệp tạm `.part`.
"""

from __future__ import annotations

import os
import pathlib
import time
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import don_tep_ket_qua
from clinicai.services.tep_ket_qua_service import TepKetQuaService
from tests.services.test_xac_nhan_tep_ket_qua_db import (
    CLINIC_A,
    PDF_DUMMY,
    _tao_benh_nhan_va_visit,
    _tao_external_order,
    _tao_review_round_cho_order,
    _tao_staff,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_TEST") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=8)
    yield p
    await p.close()


@pytest.fixture
def kho(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    import clinicai.services.media_service as media
    import clinicai.services.tep_ket_qua_service as tep_mod

    monkeypatch.setattr(media, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(tep_mod, "MEDIA_ROOT", tmp_path)
    monkeypatch.delenv("MEDIA_MARKER", raising=False)
    return tmp_path


async def _dung(pool: asyncpg.Pool) -> dict[str, Any]:
    async with pool.acquire() as conn:
        doc = await _tao_staff(conn, CLINIC_A, "DOCTOR")
        cskh = await _tao_staff(conn, CLINIC_A, "CSKH")
        pid, aid, vid = await _tao_benh_nhan_va_visit(conn, CLINIC_A, doc.staff_id)
        oid = await _tao_external_order(conn, CLINIC_A, vid)
    return {"doc": doc, "cskh": cskh, "pid": pid, "aid": aid, "vid": vid, "oid": oid}


async def _tai(pool: asyncpg.Pool, ai: Any, d: dict[str, Any]) -> str:
    kq = await TepKetQuaService(pool).tai_len(
        identity=ai,
        clinic_patient_id=d["pid"],
        data=PDF_DUMMY,
        ten_hien_thi="kq.pdf",
        service_order_id=d["oid"],
    )
    return str(kq["id"])


# ── Postgres ───────────────────────────────────────────────────────────────


async def test_db_chan_xoa_dong_va_sua_de_vet_xoa(pool: asyncpg.Pool, kho: Any) -> None:
    d = await _dung(pool)
    tep = await _tai(pool, d["doc"], d)
    async with pool.acquire() as conn:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute("DELETE FROM tep_ket_qua WHERE id = $1::uuid", tep)
        # Thiếu lý do → CHECK đủ bộ.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE tep_ket_qua SET da_xoa_luc = now(),"
                " da_xoa_boi_staff_id = $2::uuid, da_xoa_loai = 'XOA'"
                " WHERE id = $1::uuid",
                tep,
                d["doc"].staff_id,
            )
        # Đánh dấu dọn khi chưa xoá → trigger.
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE tep_ket_qua SET da_don_tep_luc = now() WHERE id = $1::uuid",
                tep,
            )
        await conn.execute(
            "UPDATE tep_ket_qua SET da_xoa_luc = now(),"
            " da_xoa_boi_staff_id = $2::uuid, da_xoa_ly_do = 'nhầm',"
            " da_xoa_loai = 'XOA' WHERE id = $1::uuid",
            tep,
            d["doc"].staff_id,
        )
        # Sửa đè lý do / người xoá → trigger.
        with pytest.raises(asyncpg.CheckViolationError, match="sửa đè"):
            await conn.execute(
                "UPDATE tep_ket_qua SET da_xoa_ly_do = 'lý do khác'"
                " WHERE id = $1::uuid",
                tep,
            )
        # View hiệu lực không còn thấy tệp.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM v_tep_ket_qua_hieu_luc WHERE id = $1::uuid", tep
            )
            == 0
        )
        # Đã dọn → không khôi phục được nữa.
        await conn.execute(
            "UPDATE tep_ket_qua SET da_don_tep_luc = now() WHERE id = $1::uuid", tep
        )
        with pytest.raises(asyncpg.CheckViolationError, match="đã dọn"):
            await conn.execute(
                "UPDATE tep_ket_qua SET da_xoa_luc = NULL, da_xoa_boi_staff_id = NULL,"
                " da_xoa_ly_do = NULL, da_xoa_loai = NULL, da_don_tep_luc = NULL"
                " WHERE id = $1::uuid",
                tep,
            )


async def test_view_bo_tep_thu_hoi(pool: asyncpg.Pool, kho: Any) -> None:
    """Lỗi cũ: danh sách tệp của khách vẫn hiện tệp đã thu hồi."""
    d = await _dung(pool)
    tep = await _tai(pool, d["doc"], d)
    async with pool.acquire() as conn:
        # Tệp đối tác tự HỢP LỆ lúc tải → thu hồi thẳng bằng SQL cho gọn.
        await conn.execute(
            "UPDATE tep_ket_qua SET xac_nhan_trang_thai = 'THU_HOI',"
            " thu_hoi_luc = now(), thu_hoi_boi_staff_id = $2::uuid,"
            " thu_hoi_ly_do = 'nhầm khách' WHERE id = $1::uuid",
            tep,
            d["doc"].staff_id,
        )
    ds = await TepKetQuaService(pool).danh_sach(
        identity=d["doc"], clinic_patient_id=d["pid"]
    )
    assert tep not in {t["id"] for t in ds}


# ── Service ────────────────────────────────────────────────────────────────


async def test_xoa_khoi_phuc_cung_giao_dich(pool: asyncpg.Pool, kho: Any) -> None:
    d = await _dung(pool)
    dv = TepKetQuaService(pool)
    tep = await _tai(pool, d["doc"], d)

    ds = await dv.danh_sach(identity=d["doc"], clinic_patient_id=d["pid"])
    dong = next(t for t in ds if t["id"] == tep)
    assert dong["xoa_duoc"] is True and dong["xoa_loai"] == "XOA"
    assert "x_tai_len_boi" not in dong  # cột nội bộ không lọt ra API

    with pytest.raises(ValidationError, match="lý do"):
        await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="   ")

    kq = await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="Ảnh mờ, chụp lại")
    assert kq["loai"] == "XOA" and kq["khoi_phuc_han"]
    # Gọi lại không lỗi (idempotent).
    assert (await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="x"))["already"]

    ds = await dv.danh_sach(identity=d["doc"], clinic_patient_id=d["pid"])
    assert tep not in {t["id"] for t in ds}
    da_xoa = await dv.da_xoa_gan_day(identity=d["doc"], clinic_patient_id=d["pid"])
    dx = next(t for t in da_xoa if t["id"] == tep)
    assert dx["khoi_phuc_duoc"] is True
    assert dx["da_xoa_ly_do"] == "Ảnh mờ, chụp lại"

    async with pool.acquire() as conn:
        # Chỉ định không còn tệp nào → chưa có kết quả.
        assert (
            await conn.fetchval(
                "SELECT ket_qua_luc FROM service_order WHERE id = $1::uuid", d["oid"]
            )
            is None
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM domain_event"
            " WHERE event_type = 'result_file.deleted' AND aggregate_id = $1::uuid",
            tep,
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM event_log"
            " WHERE event_type = 'tep_ket_qua.xoa' AND aggregate_id = $1",
            tep,
        )
    # Không mở / không gửi được tệp đã xoá.
    with pytest.raises(NotFoundError):
        await dv.duong_dan_de_doc(identity=d["doc"], tep_id=tep)
    with pytest.raises(NotFoundError):
        await dv.danh_dau_da_gui(identity=d["cskh"], tep_id=tep, kenh="ZALO")

    await dv.khoi_phuc_tep(identity=d["doc"], tep_id=tep)
    ds = await dv.danh_sach(identity=d["doc"], clinic_patient_id=d["pid"])
    assert tep in {t["id"] for t in ds}
    async with pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT ket_qua_luc FROM service_order WHERE id = $1::uuid", d["oid"]
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM domain_event"
            " WHERE event_type = 'result_file.restored' AND aggregate_id = $1::uuid",
            tep,
        )


async def test_nguoi_tai_len_xoa_duoc_khi_chua_ai_xem(
    pool: asyncpg.Pool, kho: Any
) -> None:
    """CSKH không có lego Kết quả: xoá được tệp CỦA MÌNH khi chưa ai khác xem."""
    d = await _dung(pool)
    dv = TepKetQuaService(pool)
    cua_cskh = await _tai(pool, d["cskh"], d)
    cua_bs = await _tai(pool, d["doc"], d)

    ds = {
        t["id"]: t
        for t in await dv.danh_sach(identity=d["cskh"], clinic_patient_id=d["pid"])
    }
    assert ds[cua_cskh]["xoa_duoc"] is True
    assert ds[cua_bs]["xoa_duoc"] is False and ds[cua_bs]["xoa_ly_do"]
    with pytest.raises(SafetyGateError):
        await dv.xoa_tep(identity=d["cskh"], tep_id=cua_bs, ly_do="nhầm")

    # Bác sĩ đã xem tệp của CSKH → CSKH không tự xoá nữa.
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tep_ket_qua SET da_xem_luc = now(), da_xem_boi_staff_id = $2::uuid"
            " WHERE id = $1::uuid",
            cua_cskh,
            d["doc"].staff_id,
        )
    with pytest.raises(SafetyGateError, match="đã xem"):
        await dv.xoa_tep(identity=d["cskh"], tep_id=cua_cskh, ly_do="nhầm")
    # Bác sĩ (lego Kết quả) vẫn xoá được.
    await dv.xoa_tep(identity=d["doc"], tep_id=cua_cskh, ly_do="nhầm khách")


async def test_da_gui_khach_chi_con_dinh_chinh(pool: asyncpg.Pool, kho: Any) -> None:
    d = await _dung(pool)
    dv = TepKetQuaService(pool)
    tep = await _tai(pool, d["cskh"], d)
    await dv.danh_dau_da_gui(identity=d["cskh"], tep_id=tep, kenh="ZALO")

    ds = {
        t["id"]: t
        for t in await dv.danh_sach(identity=d["cskh"], clinic_patient_id=d["pid"])
    }
    assert ds[tep]["xoa_duoc"] is False  # CSKH không có quyền duyệt kết quả
    with pytest.raises(SafetyGateError, match="đính chính"):
        await dv.xoa_tep(identity=d["cskh"], tep_id=tep, ly_do="sai")

    ds = {
        t["id"]: t
        for t in await dv.danh_sach(identity=d["doc"], clinic_patient_id=d["pid"])
    }
    assert ds[tep]["xoa_loai"] == "DINH_CHINH"
    kq = await dv.xoa_tep(identity=d["doc"], tep_id=tep, ly_do="Gửi nhầm bản cũ")
    assert kq["loai"] == "DINH_CHINH"
    # Khôi phục tệp Đính chính cần quyền duyệt kết quả — CSKH không được.
    with pytest.raises(SafetyGateError):
        await dv.khoi_phuc_tep(identity=d["cskh"], tep_id=tep)
    await dv.khoi_phuc_tep(identity=d["doc"], tep_id=tep)


async def test_phien_doc_dong_chi_con_dinh_chinh(pool: asyncpg.Pool, kho: Any) -> None:
    d = await _dung(pool)
    dv = TepKetQuaService(pool)
    tep = await _tai(pool, d["doc"], d)
    async with pool.acquire() as conn:
        rid, _ = await _tao_review_round_cho_order(conn, CLINIC_A, d["vid"], d["oid"])
        await conn.execute(
            "UPDATE review_round SET status = 'closed', closed_at = now()"
            " WHERE id = $1::uuid",
            rid,
        )
    ds = {
        t["id"]: t
        for t in await dv.danh_sach(identity=d["doc"], clinic_patient_id=d["pid"])
    }
    assert ds[tep]["xoa_loai"] == "DINH_CHINH"
    assert "Phiên đọc" in (ds[tep]["xoa_ly_do"] or "")


# ── Job dọn ổ ──────────────────────────────────────────────────────────────


async def _chen_tep_da_xoa(
    conn: asyncpg.Connection,
    d: dict[str, Any],
    goc: pathlib.Path,
    *,
    ngay: int,
    da_xem: bool = False,
) -> tuple[str, pathlib.Path]:
    tep = str(uuid.uuid4())
    khoa = f"{CLINIC_A}/{d['pid']}/{tep}.pdf"
    p = goc / khoa
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(PDF_DUMMY)
    await conn.execute(
        """
        INSERT INTO tep_ket_qua
            (id, clinic_id, clinic_patient_id, khoa, loai_tep, mime, so_byte,
             sha256, tai_len_boi_staff_id, da_xoa_luc, da_xoa_boi_staff_id,
             da_xoa_ly_do, da_xoa_loai, da_xem_luc, da_xem_boi_staff_id)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, 'PDF', 'application/pdf', 10,
                'x', $5::uuid, now() - make_interval(days => $6), $5::uuid,
                'nhầm', 'XOA',
                CASE WHEN $7 THEN now() END, CASE WHEN $7 THEN $5::uuid END)
        """,
        tep,
        CLINIC_A,
        d["pid"],
        khoa,
        d["doc"].staff_id,
        ngay,
        da_xem,
    )
    return tep, p


async def test_job_don_chi_tep_qua_30_ngay_chua_vao_ho_so(
    pool: asyncpg.Pool, kho: pathlib.Path
) -> None:
    d = await _dung(pool)
    async with pool.acquire() as conn:
        cu, p_cu = await _chen_tep_da_xoa(conn, d, kho, ngay=31)
        moi, p_moi = await _chen_tep_da_xoa(conn, d, kho, ngay=5)
        da_xem, p_xem = await _chen_tep_da_xoa(conn, d, kho, ngay=40, da_xem=True)
    tam = kho / ".tam"
    tam.mkdir()
    sot = tam / "a.part"
    sot.write_bytes(b"x")
    cu_ts = time.time() - 2 * 86400
    os.utime(sot, (cu_ts, cu_ts))
    dang_tai = tam / "b.part"
    dang_tai.write_bytes(b"x")

    kq = await don_tep_ket_qua.mot_luot(pool, goc=kho, kiem_kho=lambda: (True, ""))
    assert kq["bo_qua"] is None
    assert not p_cu.exists() and p_moi.exists() and p_xem.exists()
    assert not sot.exists() and dang_tai.exists()
    async with pool.acquire() as conn:
        don = {
            r["id"]: r["da_don_tep_luc"]
            for r in await conn.fetch(
                "SELECT id::text, da_don_tep_luc FROM tep_ket_qua"
                " WHERE id = ANY($1::uuid[])",
                [cu, moi, da_xem],
            )
        }
    assert don[cu] is not None and don[moi] is None and don[da_xem] is None


async def test_job_bo_qua_khi_kho_chua_gan(
    pool: asyncpg.Pool, kho: pathlib.Path
) -> None:
    d = await _dung(pool)
    async with pool.acquire() as conn:
        _, p = await _chen_tep_da_xoa(conn, d, kho, ngay=31)
    kq = await don_tep_ket_qua.mot_luot(
        pool, goc=kho, kiem_kho=lambda: (False, "chua_dat_MEDIA_ROOT")
    )
    assert kq["bo_qua"] == "chua_dat_MEDIA_ROOT" and p.exists()
