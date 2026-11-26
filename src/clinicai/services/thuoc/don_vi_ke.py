"""Danh mục → đơn vị của một thuốc: đơn vị MẶC ĐỊNH KHI KÊ và tên đơn vị sạch số
(kế hoạch docs/KE-HOACH-DON-VI-ME-CON-CACH-DUNG.md mục 2, 16 dòng PR C).

  · Mặc định khi kê = cờ `thuoc_quy_doi.mac_dinh_ke` (PR A): dòng đơn để trống đơn
    vị hiểu theo đơn vị này. Một thuốc tối đa một — Postgres ép (chỉ mục duy nhất);
    ở đây chỉ đổi cờ theo thứ tự (gỡ cũ → lưu đơn vị → gắn mới) và nói lỗi tiếng Việt
    thay cho lỗi thô của CHECK `thuoc_quy_doi_me_phai_dang_ban`.
  · Tên đơn vị không được có chữ số: "hộp 30 viên" nhét số vào tên — số phải nằm ở ô
    "1 hộp có bao nhiêu viên?". Chỉ chặn tên MỚI; tên cũ đang dùng (Aktiv, Ecanix)
    vẫn lưu lại được, sửa bằng nút "Đổi tên đơn vị gốc" (`doi_ten_goc`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.don_vi_thuoc import chuan

#: Gửi lên không có khoá `mac_dinh_ke` ở dòng nào = giữ nguyên đơn vị mặc định.
GIU = object()


def kiem_ten_don_vi(chu: str | None) -> None:
    """Tên đơn vị có chữ số → câu chỉ cách làm đúng."""
    ten = " ".join((chu or "").split())
    if re.search(r"\d", ten):
        dau = re.split(r"\s*\d", ten, maxsplit=1)[0] or "hộp"
        raise ValidationError(
            f"Tên đơn vị “{ten}” có chữ số — chỉ ghi tên (“{dau}”); số nằm ở ô "
            f"“1 {dau} có bao nhiêu …?”."
        )


def doc_me_gui_len(ds: Any) -> object | str:
    """Đơn vị mặc định khi kê form gửi: chữ chuẩn của đơn vị có `mac_dinh_ke`, ""
    = đơn vị gốc, `GIU` = form không nói gì. Kiểm luôn tên MỚI không có số."""
    if not isinstance(ds, list):
        return GIU
    co_khoa = False
    me: list[str] = []
    for d in ds:
        if not isinstance(d, Mapping):
            continue  # `doc_don_vi_gui_len` báo lỗi dòng rác
        if not d.get("phien"):
            kiem_ten_don_vi(str(d.get("don_vi") or ""))
        co_khoa = co_khoa or "mac_dinh_ke" in d
        if d.get("mac_dinh_ke") is True:
            me.append(chuan(str(d.get("don_vi") or "")))
    if len(me) > 1:
        raise ValidationError("Chỉ chọn MỘT đơn vị mặc định khi kê.")
    if not co_khoa:
        return GIU
    return me[0] if me else ""


async def khoa_thuoc(
    conn: asyncpg.Connection,
    clinic_id: str,
    thuoc: str | None,
    *,
    chia_se: bool = False,
) -> None:
    """Khoá dòng `drug_catalog` trong giao dịch của người gọi. Lưu danh mục khoá
    độc quyền; nhập lô khoá chia sẻ — cả hai xếp hàng sau "Đổi tên đơn vị gốc"
    (`doi_ten_goc`, FOR UPDATE) nên không đọc gốc cũ rồi ghi sau khi gốc đã đổi."""
    if thuoc is None:
        return
    sql = (
        "SELECT 1 FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR SHARE"
        if chia_se
        else "SELECT 1 FROM public.drug_catalog"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE"
    )
    await conn.execute(sql, clinic_id, thuoc)


async def kiem_ten_goc(
    conn: asyncpg.Connection, clinic_id: str, thuoc: str | None, goc_moi: str | None
) -> None:
    """Đơn vị gốc mới (thuốc mới, hoặc đổi chữ) không được có số; giữ nguyên chữ
    cũ thì cho lưu."""
    cu = None
    if thuoc is not None:
        cu = await conn.fetchval(
            "SELECT don_vi_ban FROM public.drug_catalog"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            thuoc,
        )
    if chuan(cu) != chuan(goc_moi):
        kiem_ten_don_vi(goc_moi)


async def _me_hien_tai(conn: asyncpg.Connection, clinic_id: str, thuoc: str) -> str:
    return str(
        await conn.fetchval(
            "SELECT don_vi FROM public.thuoc_quy_doi WHERE clinic_id = $1::uuid"
            " AND drug_catalog_id = $2::uuid AND mac_dinh_ke",
            clinic_id,
            thuoc,
        )
        or ""
    )


async def truoc_khi_luu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    thuoc: str,
    me: object | str,
    ds: Any,
) -> None:
    """Gọi TRƯỚC `luu_cac_don_vi`: chặn tắt bán đơn vị đang là mặc định kê, và gỡ cờ
    cũ khi đổi mặc định (chỉ mục duy nhất không cho hai cờ cùng lúc)."""
    cu = await _me_hien_tai(conn, identity.clinic_id, thuoc)
    sau = cu if me is GIU else str(me)
    for d in ds if isinstance(ds, list) else []:
        if (
            isinstance(d, Mapping)
            and d.get("dang_ban") is False
            and sau
            and chuan(str(d.get("don_vi") or "")) == sau
        ):
            raise ValidationError(
                f"“{sau}” đang là đơn vị mặc định khi kê — chọn đơn vị khác (hoặc "
                "đơn vị gốc) làm mặc định rồi mới tắt bán."
            )
    if cu and cu != sau:
        # Không đổi `cap_nhat_luc`: đó là dấu phiên bản form vừa gửi kèm, đổi ở đây
        # thì `luu_cac_don_vi` báo nhầm "người khác vừa sửa". Dòng thuốc đã khoá.
        await conn.execute(
            "UPDATE public.thuoc_quy_doi SET mac_dinh_ke = false WHERE"
            " clinic_id = $1::uuid AND drug_catalog_id = $2::uuid AND mac_dinh_ke",
            identity.clinic_id,
            thuoc,
        )


async def sau_khi_luu(
    conn: asyncpg.Connection, identity: StaffIdentity, *, thuoc: str, me: object | str
) -> dict[str, str] | None:
    """Gọi SAU `luu_cac_don_vi`: gắn cờ cho đơn vị mặc định mới. Trả thay đổi để ghi
    nhật ký, None = không đổi."""
    if me is GIU:
        return None
    moi = str(me)
    cu = await _me_hien_tai(conn, identity.clinic_id, thuoc)
    if cu == moi:
        return None
    if moi:
        r = await conn.fetchrow(
            "SELECT dang_ban FROM public.thuoc_quy_doi WHERE clinic_id = $1::uuid"
            " AND drug_catalog_id = $2::uuid AND don_vi = $3",
            identity.clinic_id,
            thuoc,
            moi,
        )
        if r is None or not r["dang_ban"]:
            raise ValidationError(
                f"“{moi}” chưa bán (chưa lưu hoặc đang tắt) — mở bán rồi mới đặt làm "
                "đơn vị mặc định khi kê."
            )
        await conn.execute(
            "UPDATE public.thuoc_quy_doi SET mac_dinh_ke = true,"
            " cap_nhat_boi = $4::uuid, cap_nhat_luc = now() WHERE clinic_id = $1::uuid"
            " AND drug_catalog_id = $2::uuid AND don_vi = $3",
            identity.clinic_id,
            thuoc,
            moi,
            identity.staff_id,
        )
    return {"mac_dinh_ke_cu": cu, "mac_dinh_ke_moi": moi}
