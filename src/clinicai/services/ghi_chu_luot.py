"""Ô CHỮ TỰ DO của hồ sơ lượt "Khác" (Tuyền chốt 07/10/2026 — bấm thử staging).

Hồ sơ lượt "Khác" chỉ cần MỘT ô chữ to tự do (+ kê chỉ định như có sẵn). Bảng
`luot_ghi_chu` (migration 20261007640000): mỗi lần lưu THÊM một phiên bản, không
sửa / xoá dòng cũ — màn và bản in đọc phiên bản mới nhất; lịch sử = các dòng.

* Hiện ô khi lượt thuộc nhóm KHAC, hoặc lượt đã có ghi chú (đổi dịch vụ sang
  loại khám thật thì chữ cũ vẫn hiện — làm mới không mất cũ). MÁY CHỦ quyết.
* Chống đè: màn gửi `phien_ban` nó đang cầm; người khác vừa lưu → 409, màn nạp
  bản mới. Gửi lại y hệt bản mới nhất → không đẻ phiên bản.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.permissions.y_khoa import doc_duoc_in_phieu
from clinicai.services.doi_dich_vu_kham import QUYEN_DOI_TRONG_HO_SO
from clinicai.services.lenh_kham_core import ma_uuid

DAI_TOI_DA = 20000

_LUOT_SQL = """
SELECT v.status, st.nhom
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""

_BAN_SQL = """
SELECT g.phien_ban, g.noi_dung, g.ghi_luc, s.full_name AS ghi_boi
  FROM public.luot_ghi_chu g
  LEFT JOIN public.staff s ON s.id = g.ghi_boi
 WHERE g.clinic_id = $1::uuid AND g.visit_id = $2::uuid
 ORDER BY g.phien_ban DESC
 LIMIT 1
"""


def hien_o_ghi_chu(nhom: str | None, co_ban: bool) -> bool:
    """Ô ghi chú hiện ở hồ sơ: lượt nhóm KHAC, hoặc đã có chữ — hàm thuần."""
    return nhom == "KHAC" or co_ban


def doc_noi_dung(raw: Any) -> str:
    """Chữ người dùng gửi → chuỗi (rác → rỗng). Không ném vì kiểu."""
    return raw if isinstance(raw, str) else ""


def _ban(r: asyncpg.Record | None) -> dict[str, Any] | None:
    if r is None:
        return None
    return {
        "phien_ban": int(r["phien_ban"]),
        "noi_dung": r["noi_dung"],
        "ghi_luc": r["ghi_luc"].isoformat() if r["ghi_luc"] else None,
        "ghi_boi": r["ghi_boi"],
    }


async def _luot(conn: asyncpg.Connection, cid: str, vid: str) -> asyncpg.Record:
    r = await conn.fetchrow(_LUOT_SQL, cid, vid)
    if r is None:
        raise NotFoundError("Không tìm thấy lượt khám.")
    return r


async def doc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, visit_id: str
) -> dict[str, Any]:
    """Ghi chú của lượt + có hiện / ghi được không. Người hồ sơ khám, hoặc khâu
    in phiếu (bản in lượt có mục Ghi chú)."""
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    async with pool.acquire() as conn:
        if not await doc_duoc_in_phieu(conn, identity):
            await doi_mot_quyen(
                conn,
                identity,
                QUYEN_DOI_TRONG_HO_SO,
                cau="Bạn không có quyền xem hồ sơ khám của lượt này.",
            )
        luot = await _luot(conn, cid, vid)
        ban = _ban(await conn.fetchrow(_BAN_SQL, cid, vid))
    return {
        "visit_id": vid,
        "hien": hien_o_ghi_chu(luot["nhom"], ban is not None),
        "ghi_duoc": luot["status"] in ("OPEN", "IN_PROGRESS"),
        "ban": ban,
    }


async def luu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str,
    noi_dung: Any,
    phien_ban: Any,
) -> dict[str, Any]:
    """Thêm MỘT phiên bản mới (không sửa dòng cũ)."""
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    chu = doc_noi_dung(noi_dung)
    if len(chu) > DAI_TOI_DA:
        raise ValidationError("Ghi chú quá dài.")
    try:
        dang_cam = int(phien_ban or 0)
    except (TypeError, ValueError):
        dang_cam = 0
    async with pool.acquire() as conn, conn.transaction():
        await doi_mot_quyen(
            conn,
            identity,
            QUYEN_DOI_TRONG_HO_SO,
            cau="Bạn không có quyền ghi hồ sơ khám của lượt này.",
        )
        # Khoá lượt: hai lần lưu cùng lúc xếp hàng, người sau thấy bản mới.
        trang_thai = await conn.fetchval(
            "SELECT status FROM public.visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            cid,
            vid,
        )
        if trang_thai is None:
            raise NotFoundError("Không tìm thấy lượt khám.")
        if trang_thai not in ("OPEN", "IN_PROGRESS"):
            raise ValidationError("Lượt khám đã khoá hồ sơ — không sửa được.")
        cu = await conn.fetchrow(_BAN_SQL, cid, vid)
        hien_tai = int(cu["phien_ban"]) if cu else 0
        if hien_tai != dang_cam:
            raise ConflictError(
                "Ghi chú vừa được người khác lưu — đã nạp bản mới, gõ tiếp trên đó."
            )
        if cu is not None and cu["noi_dung"] == chu:
            return {"ok": True, "doi": False, "ban": _ban(cu)}
        await conn.execute(
            "INSERT INTO public.luot_ghi_chu"
            " (clinic_id, visit_id, phien_ban, noi_dung, ghi_boi)"
            " VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)",
            cid,
            vid,
            hien_tai + 1,
            chu,
            identity.staff_id,
        )
        moi = await conn.fetchrow(_BAN_SQL, cid, vid)
    return {"ok": True, "doi": True, "ban": _ban(moi)}


__all__ = ["DAI_TOI_DA", "doc", "doc_noi_dung", "hien_o_ghi_chu", "luu"]
