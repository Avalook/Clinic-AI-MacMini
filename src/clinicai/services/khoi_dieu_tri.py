"""KHỐI 4 "ĐIỀU TRỊ" của hồ sơ khám (Tuyền chốt 07/10/2026 — T6 của
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md).

Hai ô chữ tự do "Cảm nhận" + "Vấn đề sau điều trị" theo LƯỢT, bảng riêng
`luot_dieu_tri_ghi` (không nhét vào 7 mẫu phiếu JSON). Tự lưu: mỗi lần lưu THÊM
một phiên bản (bảng chỉ thêm — trigger chặn sửa / xoá), màn hiện bản mới nhất.
Dùng được cả lượt không có phiếu (Điều trị, Khác). In kèm phiếu khi có nội dung.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.permissions.y_khoa import QUYEN_Y_KHOA, doc_duoc_in_phieu
from clinicai.services.doi_dich_vu_kham import QUYEN_DOI_TRONG_HO_SO
from clinicai.services.lenh_kham_core import ma_uuid

_MOI_NHAT_SQL = """
SELECT g.phien_ban, g.cam_nhan, g.van_de_sau, g.ghi_luc, s.full_name AS ghi_boi
  FROM public.luot_dieu_tri_ghi g
  LEFT JOIN public.staff s ON s.id = g.ghi_boi
 WHERE g.clinic_id = $1::uuid AND g.visit_id = $2::uuid
 ORDER BY g.phien_ban DESC
 LIMIT 1
"""


async def moi_nhat(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any] | None:
    """Bản mới nhất của khối (None = chưa ai ghi)."""
    g = await conn.fetchrow(_MOI_NHAT_SQL, clinic_id, visit_id)
    if g is None:
        return None
    return {
        "phien_ban": int(g["phien_ban"]),
        "cam_nhan": g["cam_nhan"],
        "van_de_sau": g["van_de_sau"],
        "ghi_luc": g["ghi_luc"].isoformat() if g["ghi_luc"] else None,
        "ghi_boi": g["ghi_boi"],
    }


async def doc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, visit_id: str
) -> dict[str, Any]:
    """Đọc: người đọc được y khoa / trưởng ca, hoặc khâu quầy in phiếu."""
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    async with pool.acquire() as conn:
        if not await doc_duoc_in_phieu(conn, identity):
            await doi_mot_quyen(
                conn,
                identity,
                QUYEN_DOI_TRONG_HO_SO,
                cau="Bạn không có quyền xem hồ sơ khám của lượt này.",
            )
        return {"dieu_tri": await moi_nhat(conn, identity.clinic_id, vid)}


async def luu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str,
    cam_nhan: str,
    van_de_sau: str,
    phien_ban: int,
) -> dict[str, Any]:
    """Thêm MỘT phiên bản mới (không sửa bản cũ).

    ``phien_ban`` = bản người dùng đang nhìn (0 = chưa có). Người khác vừa lưu
    bản mới hơn → 409 để màn nạp lại, không đè im lặng. Nội dung y hệt bản mới
    nhất → không thêm bản (tự lưu gửi lại không đẻ dòng rác).
    """
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    cam = (cam_nhan or "").strip()[:5000]
    van = (van_de_sau or "").strip()[:5000]
    async with pool.acquire() as conn, conn.transaction():
        await doi_mot_quyen(
            conn,
            identity,
            QUYEN_Y_KHOA,
            cau="Bạn không có quyền ghi hồ sơ khám (cần khối khám / ghi bệnh án).",
        )
        if not await conn.fetchval(
            "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            cid,
            vid,
        ):
            raise NotFoundError("Không tìm thấy lượt khám.")
        ban = await moi_nhat(conn, cid, vid)
        so = ban["phien_ban"] if ban else 0
        if ban and (ban["cam_nhan"], ban["van_de_sau"]) == (cam, van):
            return {"ok": True, "doi": False, "dieu_tri": ban}
        if so != phien_ban:
            raise ConflictError(
                "Người khác vừa lưu khối Điều trị — tải bản mới rồi gõ lại phần"
                " của bạn."
            )
        await conn.execute(
            "INSERT INTO public.luot_dieu_tri_ghi"
            " (clinic_id, visit_id, phien_ban, cam_nhan, van_de_sau, ghi_boi)"
            " VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)",
            cid,
            vid,
            so + 1,
            cam,
            van,
            identity.staff_id,
        )
        return {"ok": True, "doi": True, "dieu_tri": await moi_nhat(conn, cid, vid)}


__all__ = ["doc", "luu", "moi_nhat"]
