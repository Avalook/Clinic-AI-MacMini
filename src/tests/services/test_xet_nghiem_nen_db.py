"""Chặng 1 — nền xét nghiệm đối tác (kế hoạch 4.1–4.3, "Xong chặng khi").

Tạo đối tác, gán dịch vụ cho A, bác sĩ chỉ định ⇒ `xet_nghiem_viec` chụp A; đổi gán
sang B ⇒ việc cũ vẫn A, việc mới đi B. Bất biến ép ở DB: chụp không sửa/xoá được,
một dịch vụ một mặc định, mã ngắn không trùng.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.xet_nghiem import doi_tac as dt
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _ca_doi_tac(pool: asyncpg.Pool) -> Ca:  # noqa: F811
    """Ca có dịch vụ `ma_dv` do đối tác thu (dữ liệu test — bảng giá thật do
    Quản lý đổi ở màn Bảng giá)."""
    ca = await _dung(pool)
    await pool.execute(
        "UPDATE service_price SET billing_owner = 'EXTERNAL_PARTNER',"
        " billing_owner_chon_tay = true, unit_price = 550000"
        " WHERE clinic_id = $1::uuid AND service_code = $2",
        CLINIC,
        ca.ma_dv,
    )
    return ca


async def _sp(pool: asyncpg.Pool, ma: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'dich_vu' AND service_code = $2",
            CLINIC,
            ma,
        )
    )


async def _them_dt(
    pool: asyncpg.Pool,  # noqa: F811
    ai: StaffIdentity,
    ma: str,
    **them: Any,
) -> str:
    async with pool.acquire() as conn, conn.transaction():
        return await dt.luu_doi_tac(
            conn, ai, {"ten": f"Đối tác {ma}", "ma_ngan": ma, **them}
        )


async def _gan(
    pool: asyncpg.Pool,  # noqa: F811
    ai: StaffIdentity,
    dt_id: str,
    sp_id: str,
    **them: Any,
) -> str:
    async with pool.acquire() as conn, conn.transaction():
        return await dt.luu_anh_xa(
            conn, ai, {"doi_tac_id": dt_id, "service_price_id": sp_id, **them}
        )


async def _viec(pool: asyncpg.Pool, oid: str) -> asyncpg.Record | None:  # noqa: F811
    return await pool.fetchrow(
        "SELECT doi_tac_id::text, gia_goi_y_luc_chi_dinh FROM xet_nghiem_viec"
        " WHERE service_order_id = $1::uuid",
        oid,
    )


def _ma() -> str:
    return "T" + uuid.uuid4().hex[:6].upper()


async def _chi_dinh(pool: asyncpg.Pool, ca: Ca) -> str:  # noqa: F811
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, oid = await _kham_va_chi_dinh(pool, ca, visit)
    return oid


async def test_xong_chang_1_chup_doi_tac_doi_gan_khong_doi_viec_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    sp = await _sp(pool, ca.ma_dv)
    a = await _them_dt(pool, ca.bac_si, _ma(), hen_tra_so_ngay_mac_dinh=3)
    b = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, sp, gia_goi_y="500.000")

    cu = await _chi_dinh(pool, ca)
    v = await _viec(pool, cu)
    assert v is not None and v["doi_tac_id"] == a
    assert v["gia_goi_y_luc_chi_dinh"] == 500_000

    # Đổi mặc định sang B (cùng giao dịch bỏ mặc định của A).
    await _gan(pool, ca.bac_si, b, sp)
    moi = await _chi_dinh(pool, ca)
    v_moi = await _viec(pool, moi)
    assert v_moi is not None and v_moi["doi_tac_id"] == b
    # B không có giá riêng ⇒ giá bảng giá.
    assert v_moi["gia_goi_y_luc_chi_dinh"] == 550_000
    v_cu = await _viec(pool, cu)
    assert v_cu is not None and v_cu["doi_tac_id"] == a


async def test_dich_vu_khong_gan_doi_tac_khong_chup(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    assert await _viec(pool, await _chi_dinh(pool, ca)) is None


async def test_doi_tac_ngung_khong_nhan_viec_moi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    cu = await _chi_dinh(pool, ca)
    async with pool.acquire() as conn, conn.transaction():
        await dt.ngung_doi_tac(conn, ca.bac_si, a, ngung=True, ly_do="hết hợp đồng")
    assert await _viec(pool, await _chi_dinh(pool, ca)) is None
    # Việc dở của đối tác đã ngưng vẫn còn (không đổi).
    v = await _viec(pool, cu)
    assert v is not None and v["doi_tac_id"] == a


async def test_gia_0_de_trong(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _ca_doi_tac(pool)
    await pool.execute(
        "UPDATE service_price SET unit_price = 0 WHERE clinic_id = $1::uuid"
        " AND service_code = $2",
        CLINIC,
        ca.ma_dv,
    )
    a = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    v = await _viec(pool, await _chi_dinh(pool, ca))
    assert v is not None and v["gia_goi_y_luc_chi_dinh"] is None


async def test_gan_dich_vu_phong_kham_thu_bi_tu_choi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)  # ma_dv do phòng khám thu
    a = await _them_dt(pool, ca.bac_si, _ma())
    with pytest.raises(ConflictError, match="Bảng giá"):
        await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))


async def test_gan_doi_tac_da_ngung_bi_tu_choi(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    async with pool.acquire() as conn, conn.transaction():
        await dt.ngung_doi_tac(conn, ca.bac_si, a, ngung=True, ly_do="tạm dừng")
    with pytest.raises(ConflictError, match="ngưng"):
        await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))


async def test_ma_ngan_trung_409_khong_phan_biet_hoa_thuong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    ma = _ma()
    await _them_dt(pool, ca.bac_si, ma)
    with pytest.raises(ConflictError, match="đã có"):
        await _them_dt(pool, ca.bac_si, ma.lower())


async def test_ngung_bat_buoc_ly_do_va_bat_lai_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    async with pool.acquire() as conn, conn.transaction():
        with pytest.raises(ValidationError):
            await dt.ngung_doi_tac(conn, ca.bac_si, a, ngung=True, ly_do=" x ")
    async with pool.acquire() as conn, conn.transaction():
        await dt.ngung_doi_tac(conn, ca.bac_si, a, ngung=True, ly_do="tạm dừng")
    async with pool.acquire() as conn, conn.transaction():
        await dt.ngung_doi_tac(conn, ca.bac_si, a, ngung=False)
    assert await pool.fetchval(
        "SELECT ngung_luc IS NULL FROM doi_tac WHERE id = $1::uuid", a
    )


async def test_chup_khong_sua_khong_xoa_cho_qua_dat_mot_lan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    b = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    oid = await _chi_dinh(pool, ca)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "UPDATE xet_nghiem_viec SET doi_tac_id = $2::uuid"
            " WHERE service_order_id = $1::uuid",
            oid,
            b,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM xet_nghiem_viec WHERE service_order_id = $1::uuid", oid
        )
    sua = (
        "UPDATE xet_nghiem_viec SET cho_lay_mau_truoc_luc = now(),"
        " cho_lay_mau_truoc_boi = $2::uuid, cho_lay_mau_truoc_ly_do = $3"
        " WHERE service_order_id = $1::uuid"
    )
    await pool.execute(sua, oid, ca.bac_si.staff_id, "khách gấp")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(sua, oid, ca.bac_si.staff_id, "đổi lý do")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM doi_tac WHERE id = $1::uuid", a)


async def test_db_ep_mot_dich_vu_mot_mac_dinh(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Ép ở DB (SO-LUAT Phần 6): hai dòng mặc định cùng dịch vụ ⇒ một dòng thua,
    kể cả khi ai đó bỏ qua bước "bỏ mặc định cũ" trong luu_anh_xa."""
    ca = await _ca_doi_tac(pool)
    sp = await _sp(pool, ca.ma_dv)
    a = await _them_dt(pool, ca.bac_si, _ma())
    b = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, sp)
    with pytest.raises(asyncpg.UniqueViolationError):
        await pool.execute(
            "INSERT INTO doi_tac_dich_vu (clinic_id, doi_tac_id, service_price_id,"
            " mac_dinh) VALUES ($1::uuid, $2::uuid, $3::uuid, true)",
            CLINIC,
            b,
            sp,
        )


async def test_nguong_luu_va_doc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    async with pool.acquire() as conn, conn.transaction():
        assert await dt.luu_nguong(conn, ca.bac_si, "3") == 3
        assert await dt.doc_nguong(conn, CLINIC) == 3
        with pytest.raises(ValidationError):
            await dt.luu_nguong(conn, ca.bac_si, "0")
        await dt.luu_nguong(conn, ca.bac_si, 2)


async def test_danh_sach_co_anh_xa_va_dich_vu_thu_ho(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    sp = await _sp(pool, ca.ma_dv)
    ax = await _gan(pool, ca.bac_si, a, sp, hen_tra_so_ngay="5")
    async with pool.acquire() as conn:
        ds = await dt.danh_sach(conn, CLINIC)
    dong = next(d for d in ds["doi_tac"] if d["id"] == a)
    assert [m["hen_tra_so_ngay"] for m in dong["dich_vu"]] == [5]
    assert sp in {r["id"] for r in ds["dich_vu_thu_ho"]}
    async with pool.acquire() as conn, conn.transaction():
        await dt.bo_anh_xa(conn, ca.bac_si, ax)
    async with pool.acquire() as conn:
        ds = await dt.danh_sach(conn, CLINIC)
    assert next(d for d in ds["doi_tac"] if d["id"] == a)["dich_vu"] == []


async def test_hop_dong_api_doc_duoc_du_lieu_that(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Hợp đồng `DanhSachDoiTacOut` nhận đúng thứ service trả (numeric → int,
    timestamptz → datetime) — lỗi kiểu ở đây là 500 ở màn Cài đặt."""
    from clinicai.api.v1.routers.xet_nghiem import DanhSachDoiTacOut
    from clinicai.services.xet_nghiem.cai_dat import CaiDatDoiTac

    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma(), drive_folder="1AbCdEfGhIjK_lmn")
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv), gia_goi_y=450000)
    sv = CaiDatDoiTac(pool)
    await sv.ngung(ca.bac_si, a, True, "thử hợp đồng")
    out = DanhSachDoiTacOut.model_validate(await sv.danh_sach(ca.bac_si))
    dong = next(d for d in out.doi_tac if d.id == a)
    assert dong.ngung_luc is not None and dong.drive_folder_id == "1AbCdEfGhIjK_lmn"
    assert [g.gia_goi_y for g in dong.dich_vu] == [450000]
    # Máy chủ tính sẵn giá trị hiệu lực + cờ gán (soát PR 1.3, luật 7).
    assert [(g.gia_hieu_luc, g.hen_tra_hieu_luc) for g in dong.dich_vu] == [
        (450000, None)
    ]
    assert dong.gan_duoc is False


async def test_hieu_luc_lay_mac_dinh_doi_tac_va_gia_bang_gia(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma(), hen_tra_so_ngay_mac_dinh=3)
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv))
    async with pool.acquire() as conn:
        ds = await dt.danh_sach(conn, CLINIC)
    g = next(d for d in ds["doi_tac"] if d["id"] == a)["dich_vu"][0]
    assert (g["gia_hieu_luc"], g["hen_tra_hieu_luc"]) == (550000, 3)


def test_moi_cua_xet_nghiem_co_response_model() -> None:
    from fastapi.routing import APIRoute

    from clinicai.api.v1.routers.xet_nghiem import router

    thieu = [
        r.path
        for r in router.routes
        if isinstance(r, APIRoute) and r.response_model is None
    ]
    assert not thieu, f"Cửa thiếu response_model (luật 7): {thieu}"
