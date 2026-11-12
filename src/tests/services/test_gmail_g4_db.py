"""Gmail G4 — cài đặt nguồn Gmail ở Cài đặt → Đối tác, chạy thật trên DB.

Ca biên: email lưu chữ thường, trùng ⇒ 409 đúng câu (không nhầm "mã ngắn"); ĐỔI email ⇒
đặt lại con trỏ lịch sử Gmail của đối tác đó (giữ ok_cuoi, không đụng Drive), giữ nguyên
email ⇒ không đặt lại; mã bên đối tác chữ hoa, trùng trong đối tác ⇒ 409 đúng câu, gán
lại KHÔNG gửi mã ⇒ giữ mã cũ (bảng gán thứ hai không xoá mất), gửi rỗng ⇒ xoá; mốc tự
ghép lưu / xoá, tương lai / rác ⇒ 422, không ghi đè ô ngưỡng; danh sách trả đèn Email.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import cai_dat_ban, gmail, gmail_cai_dat
from clinicai.services.xet_nghiem import doi_tac as dt
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_xet_nghiem_nen_db import _ca_doi_tac, _gan, _ma, _sp, _them_dt

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def _email() -> str:
    return f"KQ_{uuid.uuid4().hex[:8]}@Lab-Thu.VN"


async def _sua(pool: asyncpg.Pool, ai: Any, dt_id: str, **o: Any) -> None:  # noqa: F811
    async with pool.acquire() as conn, conn.transaction():
        await dt.luu_doi_tac(conn, ai, {"ten": "Lab sửa", **o}, dt_id)


async def _nhip(pool: asyncpg.Pool, dt_id: str, nguon: str) -> Any:  # noqa: F811
    return await pool.fetchrow(
        "SELECT con_tro_lich_su, so_lich_su_con, ok_cuoi FROM drive_nhip"
        " WHERE doi_tac_id = $1::uuid AND nguon = $2",
        dt_id,
        nguon,
    )


async def test_email_luu_chu_thuong_trung_thi_409_dung_cau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    em = _email()
    a = await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua=em)
    assert (
        await pool.fetchval(
            "SELECT email_gui_ket_qua FROM doi_tac WHERE id = $1::uuid", a
        )
        == em.lower()
    )
    with pytest.raises(ConflictError, match="Email"):
        await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua=em.lower())
    ma = _ma()
    await _them_dt(pool, ca.bac_si, ma)
    with pytest.raises(ConflictError, match="Mã ngắn"):  # câu cũ còn đúng
        await _them_dt(pool, ca.bac_si, ma)
    with pytest.raises(ValidationError):
        await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua="khong-phai-email")


async def test_doi_email_dat_lai_con_tro_gmail_giu_ok_cuoi_va_drive(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    ma = _ma()
    em = _email()
    a = await _them_dt(pool, ca.bac_si, ma, email_gui_ket_qua=em)
    for nguon in ("GMAIL", "DRIVE"):
        await pool.execute(
            "INSERT INTO drive_nhip (clinic_id, doi_tac_id, nguon, lan_quet_cuoi,"
            " ok_cuoi, con_tro_lich_su, so_lich_su_con) VALUES ($1::uuid, $2::uuid,"
            " $3, now(), now(), $4, $5)",
            CLINIC,
            a,
            nguon,
            "TRANG9" if nguon == "GMAIL" else None,
            0 if nguon == "GMAIL" else None,
        )
    # Lưu lại cùng email (khác hoa thường) ⇒ KHÔNG nạp lại lịch sử.
    await _sua(pool, ca.bac_si, a, ma_ngan=ma, email_gui_ket_qua=em.upper())
    assert (await _nhip(pool, a, "GMAIL"))["so_lich_su_con"] == 0
    # Đổi email ⇒ con trỏ về đầu, ok_cuoi giữ, Drive không đổi.
    await _sua(pool, ca.bac_si, a, ma_ngan=ma, email_gui_ket_qua=_email())
    g = await _nhip(pool, a, "GMAIL")
    assert (g["con_tro_lich_su"], g["so_lich_su_con"]) == (None, None)
    assert g["ok_cuoi"] is not None
    assert (await _nhip(pool, a, "DRIVE"))["ok_cuoi"] is not None
    # TRANH CHẤP: vòng quét đang chạy bằng email CŨ ghi nhịp "lịch sử đã hết" SAU khi
    # Quản lý đổi email ⇒ không được đè (không thì địa chỉ mới không bao giờ nạp).
    await gmail._nhip(pool, CLINIC, a, None, 0, None, 0, em.lower())
    g = await _nhip(pool, a, "GMAIL")
    assert (g["con_tro_lich_su"], g["so_lich_su_con"]) == (None, None)
    # Nhánh INSERT (chưa có dòng nhịp: vừa đặt email lần đầu, sửa A→B lúc lượt đầu
    # đang chạy) ⇒ dòng mới KHÔNG mang "lịch sử đã hết" của email cũ.
    b = await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua=_email())
    await gmail._nhip(pool, CLINIC, b, None, 0, None, 0, "email.cu@lab-thu.vn")
    g = await _nhip(pool, b, "GMAIL")
    assert (g["con_tro_lich_su"], g["so_lich_su_con"]) == (None, None)
    assert g["ok_cuoi"] is not None  # nhịp vẫn ghi
    # Đổi NULL ↔ có email cũng là đổi ⇒ đặt lại.
    await pool.execute(
        "UPDATE drive_nhip SET so_lich_su_con = 0 WHERE doi_tac_id = $1::uuid"
        " AND nguon = 'GMAIL'",
        a,
    )
    await _sua(pool, ca.bac_si, a, ma_ngan=ma, email_gui_ket_qua="")
    assert (await _nhip(pool, a, "GMAIL"))["so_lich_su_con"] is None


async def test_ma_ben_doi_tac_gan_lai_khong_gui_ma_thi_giu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    sp = await _sp(pool, ca.ma_dv)
    gid = await _gan(pool, ca.bac_si, a, sp, ma_ben_doi_tac=" hpv ")

    async def ma() -> Any:
        return await pool.fetchval(
            "SELECT ma_ben_doi_tac FROM doi_tac_dich_vu WHERE id = $1::uuid", gid
        )

    assert await ma() == "HPV"
    await _gan(pool, ca.bac_si, a, sp, gia_goi_y="600000")  # bảng gán thứ hai
    assert await ma() == "HPV", "gán lại không gửi mã phải giữ mã cũ"
    await _gan(pool, ca.bac_si, a, sp, ma_ben_doi_tac="")
    assert await ma() is None
    with pytest.raises(ValidationError):
        await _gan(pool, ca.bac_si, a, sp, ma_ben_doi_tac="HPV GENO")


async def test_ma_ben_doi_tac_trung_trong_doi_tac_409_dung_cau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    sp = await pool.fetch(
        "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
        " AND \"group\" = 'dich_vu' AND billing_owner = 'EXTERNAL_PARTNER'"
        " ORDER BY id LIMIT 2",
        CLINIC,
    )
    if len(sp) < 2:
        await pool.execute(
            "UPDATE service_price SET billing_owner = 'EXTERNAL_PARTNER',"
            " billing_owner_chon_tay = true WHERE id = (SELECT id FROM service_price"
            " WHERE clinic_id = $1::uuid AND \"group\" = 'dich_vu'"
            " AND billing_owner <> 'EXTERNAL_PARTNER' ORDER BY id LIMIT 1)",
            CLINIC,
        )
        sp = await pool.fetch(
            "SELECT id::text FROM service_price WHERE clinic_id = $1::uuid"
            " AND \"group\" = 'dich_vu' AND billing_owner = 'EXTERNAL_PARTNER'"
            " ORDER BY id LIMIT 2",
            CLINIC,
        )
    await _gan(pool, ca.bac_si, a, sp[0]["id"], ma_ben_doi_tac="HPV", mac_dinh=False)
    with pytest.raises(ConflictError, match="Mã HPV"):
        await _gan(
            pool, ca.bac_si, a, sp[1]["id"], ma_ben_doi_tac="HPV", mac_dinh=False
        )


async def test_moc_tu_ghep_luu_xoa_va_khong_ghi_de_nguong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _ca_doi_tac(pool)
    async with pool.acquire() as conn, conn.transaction():
        await cai_dat_ban.luu_nguong(conn, ca.bac_si, 5, hien_ma_ong=True)
        hom_nay = hom_nay_vn().isoformat()
        moc = await gmail_cai_dat.luu_moc(conn, ca.bac_si, hom_nay)
        assert moc is not None and moc.isoformat() == hom_nay
        cd = await cai_dat_ban.doc_cai_dat(conn, CLINIC)
        # Cùng một dòng cài đặt, hai cửa lưu riêng (#607 + G4): không ô nào đè ô nào.
        assert (cd.nguong_lay_mau_ngay, cd.hien_ma_ong) == (5, True), "mốc Gmail đè"
        ds = await dt.danh_sach(conn, CLINIC)
        assert ds["gmail_tu_ngay"].isoformat() == hom_nay
        await cai_dat_ban.luu_nguong(conn, ca.bac_si, 5, hien_ma_ong=False)
        moc_sau = await gmail_cai_dat.doc_moc(conn, CLINIC)
        assert moc_sau is not None and moc_sau.isoformat() == hom_nay, "công tắc đè mốc"
        for rac in ("2999-01-01", "31/12/2026", "abc"):
            with pytest.raises(ValidationError):
                await gmail_cai_dat.luu_moc(conn, ca.bac_si, rac)
        assert await gmail_cai_dat.luu_moc(conn, ca.bac_si, "") is None
        assert await gmail_cai_dat.doc_moc(conn, CLINIC) is None


async def test_danh_sach_tra_den_email(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _ca_doi_tac(pool)
    co = await _them_dt(pool, ca.bac_si, _ma(), email_gui_ket_qua=_email())
    khong = await _them_dt(pool, ca.bac_si, _ma())
    async with pool.acquire() as conn:
        ds = {d["id"]: d for d in (await dt.danh_sach(conn, CLINIC))["doi_tac"]}
    assert ds[co]["email_den"]["nhan"].startswith("Đã nối email gửi kết quả")
    assert ds[khong]["email_den"] == {
        "nhan": "Chưa nối email gửi kết quả",
        "mau": "neutral",
    }
    assert "g_lan" not in ds[co]  # cột nhịp thô không lộ ra hợp đồng
