"""Cài đặt nguồn Gmail của bàn xét nghiệm đối tác — Gmail G4 (09/11/2026).

Tách khỏi `doi_tac.py` (sát trần 400 dòng). Ba việc:
- đèn "Email ổn / lỗi" trên thẻ đối tác (dùng chung luật `drive.den_nhip`);
- đổi email gửi kết quả ⇒ đặt lại con trỏ lịch sử Gmail của đối tác đó (không thì
  `so_lich_su_con = 0` của địa chỉ cũ làm thư cũ của địa chỉ mới không bao giờ nạp);
- mốc "Tự ghép kết quả email từ ngày" (`xet_nghiem_cai_dat.gmail_tu_ngay`, Quản lý).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem.drive import den_nhip
from clinicai.services.xet_nghiem.o_nhap import doc_ngay_moc


def den_email(
    email: str | None,
    lan_quet: datetime | None,
    ok_cuoi: datetime | None,
    loi: str | None,
    bay_gio: datetime,
) -> dict[str, str]:
    """Đèn nhịp Gmail trên thẻ đối tác (chữ + màu, máy chủ tính)."""
    return den_nhip(
        "Email", "email gửi kết quả", bool(email), lan_quet, ok_cuoi, loi, bay_gio
    )


async def email_cu(conn: asyncpg.Connection, cid: str, dt_id: str | None) -> Any:
    """Email đang lưu (khoá dòng tới hết giao dịch). Đối tác mới ⇒ None."""
    if dt_id is None:
        return None
    return await conn.fetchval(
        "SELECT email_gui_ket_qua FROM public.doi_tac"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
        cid,
        dt_id,
    )


async def neu_doi_email(
    conn: asyncpg.Connection,
    cid: str,
    dt_id: str | None,
    cu: object,
    moi: str | None,
) -> bool:
    """Sửa đối tác mà email ĐỔI (so sau chuẩn hoá chữ thường) ⇒ đặt lại con trỏ.
    Thêm mới / email giữ nguyên ⇒ không làm gì (không quét lại lịch sử mỗi lần lưu)."""
    if dt_id is None or cu == moi:
        return False
    await dat_lai_con_tro(conn, cid, dt_id)
    return True


async def dat_lai_con_tro(conn: asyncpg.Connection, cid: str, dt_id: str) -> None:
    """Email đổi ⇒ nạp lịch sử lại từ đầu cho địa chỉ mới. CHỈ hai cột con trỏ của
    nguồn GMAIL — giữ `ok_cuoi` (mốc thư mới) và không đụng nhịp Drive. Vòng quét
    đang chạy dở có thể ghi đè một lần bằng con trỏ cũ; lượt sau tự đúng."""
    await conn.execute(
        "UPDATE public.drive_nhip SET con_tro_lich_su = NULL, so_lich_su_con = NULL"
        " WHERE clinic_id = $1::uuid AND doi_tac_id = $2::uuid AND nguon = 'GMAIL'",
        cid,
        dt_id,
    )


async def doc_moc(conn: asyncpg.Connection, cid: str) -> date | None:
    v = await conn.fetchval(
        "SELECT gmail_tu_ngay FROM public.xet_nghiem_cai_dat"
        " WHERE clinic_id = $1::uuid",
        cid,
    )
    return v if isinstance(v, date) else None


async def luu_moc(
    conn: asyncpg.Connection, identity: StaffIdentity, raw: object
) -> date | None:
    """Lưu mốc tự ghép (rỗng = chưa tự ghép thư nào). Cột ngưỡng giữ nguyên /
    lấy mặc định khi dòng cài đặt chưa có."""
    from clinicai.services.xet_nghiem.doi_tac import _vet

    moc = doc_ngay_moc(raw, hom_nay_vn())
    await conn.execute(
        """
        INSERT INTO public.xet_nghiem_cai_dat (clinic_id, gmail_tu_ngay, sua_boi)
        VALUES ($1::uuid, $2, $3::uuid)
        ON CONFLICT (clinic_id) DO UPDATE
           SET gmail_tu_ngay = EXCLUDED.gmail_tu_ngay,
               sua_luc = now(), sua_boi = EXCLUDED.sua_boi
        """,
        identity.clinic_id,
        moc,
        identity.staff_id,
    )
    await _vet(
        conn,
        identity,
        "lab.settings_saved",
        "xet_nghiem_cai_dat",
        identity.clinic_id,
        {"gmail_tu_ngay": moc.isoformat() if moc else None},
    )
    return moc
