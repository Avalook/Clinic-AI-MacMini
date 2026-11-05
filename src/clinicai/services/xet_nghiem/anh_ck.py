"""Ảnh chuyển khoản của một khoản THU HỘ đối tác (không bắt buộc) — kế hoạch 4.4 (b).

Bảng riêng `anh_chuyen_khoan_thu_ho` (sổ thu hộ không nối `payment_cycle`, câu chốt 1),
nhưng CÙNG CƠ CHẾ tệp với ảnh CK của quầy thu: kiểm ảnh `kiem_anh`, đọc `doc_anh`, ổ VPS
trước → container day-tep đẩy sang CFS (`day_tep.BANG_TEP`). Gỡ ảnh nhầm = ẩn
(`go_luc`), giữ tệp + dòng. Quyền: như ghi thu hộ (mọi nhân sự bàn XN — gác ở router).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho, don_tren_kho
from clinicai.services import media_service
from clinicai.services.anh_chuyen_khoan_service import doc_anh, kiem_anh
from clinicai.services.nhan_tep_luong import TepDaNhan

logger = structlog.get_logger()


def _uuid(raw: object, cau: str) -> str:
    try:
        return str(uuid.UUID(str(raw)))
    except ValueError:
        raise ValidationError(cau) from None


async def anh_cua_cac_khoan(
    conn: asyncpg.Connection, cid: str, thanh_toan_ids: Sequence[str | None]
) -> dict[str, list[dict[str, Any]]]:
    """Ảnh CÒN HIỆU LỰC của các khoản thu hộ: thanh_toan_id → [{id, luc, boi}]."""
    ids = sorted({str(t) for t in thanh_toan_ids if t})
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT a.id::text AS id, a.thanh_toan_id::text AS thanh_toan_id,
               a.tai_len_luc AS luc, s.full_name AS boi
          FROM public.anh_chuyen_khoan_thu_ho a
          LEFT JOIN public.staff s ON s.id = a.tai_len_boi_staff_id
         WHERE a.clinic_id = $1::uuid AND a.thanh_toan_id = ANY($2::uuid[])
           AND a.go_luc IS NULL
         ORDER BY a.tai_len_luc, a.id
        """,
        cid,
        ids,
    )
    ra: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ra.setdefault(r["thanh_toan_id"], []).append(
            {"id": r["id"], "luc": r["luc"], "boi": r["boi"]}
        )
    return ra


async def tai_len(
    pool: asyncpg.Pool, identity: StaffIdentity, thanh_toan_id: object, tep: TepDaNhan
) -> dict[str, Any]:
    """Cất ảnh (đã ở `.tam` ổ VPS) cho một khoản thu hộ CÒN HIỆU LỰC + một dòng."""
    tid = _uuid(thanh_toan_id, "Khoản thu hộ không hợp lệ.")
    mime, ext = kiem_anh(tep)
    async with pool.acquire() as conn:
        con = await conn.fetchval(
            "SELECT huy_luc IS NULL FROM public.doi_tac_thanh_toan"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            identity.clinic_id,
            tid,
        )
    if con is None:
        raise NotFoundError("Không tìm thấy khoản thu hộ này.")
    if not con:
        raise ConflictError("Khoản thu hộ này đã huỷ — không gắn ảnh được.")
    khoa = f"{identity.clinic_id}/thu-ho/{tid}/{uuid.uuid4().hex}{ext}"
    path = media_service.goc_vps() / khoa
    nguon = tep.duong

    def _dat() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(nguon, path)
        path.chmod(0o600)

    await chay_tren_kho(_dat, kho=KHO_VPS)
    try:
        anh_id = await pool.fetchval(
            """
            INSERT INTO public.anh_chuyen_khoan_thu_ho
                (clinic_id, thanh_toan_id, khoa, mime, so_byte, sha256,
                 tai_len_boi_staff_id, vi_tri)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, 'vps')
            RETURNING id::text
            """,
            identity.clinic_id,
            tid,
            khoa,
            mime,
            tep.so_byte,
            tep.sha256,
            identity.staff_id,
        )
    except BaseException:
        await don_tren_kho(
            lambda: path.unlink(missing_ok=True),
            viec=f"xoa_anh_ck_thu_ho_hong:{path}",
            kho=KHO_VPS,
        )
        raise
    logger.info("anh_ck_thu_ho_tai_len", thanh_toan_id=tid, bytes=tep.so_byte)
    return {"id": anh_id}


async def _dong(pool: asyncpg.Pool, cid: str, anh_id: object) -> asyncpg.Record:
    aid = _uuid(anh_id, "Ảnh không hợp lệ.")
    r = await pool.fetchrow(
        "SELECT id::text AS id, khoa, mime, vi_tri, go_luc"
        "  FROM public.anh_chuyen_khoan_thu_ho"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        cid,
        aid,
    )
    if r is None:
        raise NotFoundError("Không tìm thấy ảnh này.")
    return r


async def doc(
    pool: asyncpg.Pool, identity: StaffIdentity, anh_id: object
) -> tuple[bytes, str]:
    r = await _dong(pool, identity.clinic_id, anh_id)
    return await doc_anh(str(r["khoa"]), str(r["vi_tri"]), str(r["mime"]))


async def go(pool: asyncpg.Pool, identity: StaffIdentity, anh_id: object) -> None:
    """Gỡ ảnh nhầm: ẩn (giữ tệp + dòng). Gỡ lại ảnh đã gỡ ⇒ như cũ."""
    r = await _dong(pool, identity.clinic_id, anh_id)
    await pool.execute(
        "UPDATE public.anh_chuyen_khoan_thu_ho"
        "   SET go_luc = now(), go_boi_staff_id = $3::uuid"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND go_luc IS NULL",
        identity.clinic_id,
        r["id"],
        identity.staff_id,
    )
