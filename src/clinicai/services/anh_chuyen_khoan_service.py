"""ẢNH CHUYỂN KHOẢN của một lần thu (Tuyền 01/10/2026: "thêm chỗ lưu lại ảnh
QR / ảnh chuyển khoản nữa càng tốt").

Nhân viên quầy chụp (điện thoại) hoặc tải ảnh màn hình chuyển khoản của khách
lên ĐÚNG lần thu; xem lại ở lịch sử giao dịch. Không bắt buộc.

CÙNG CƠ CHẾ LƯU TỆP với tệp kết quả (không làm đường thứ hai):
  * thân request chảy thẳng vào ổ VPS (``nhan_tep_luong``), kiểu kiểm bằng byte
    đầu (``sniff_ket_qua``) — chỉ nhận ẢNH;
  * tệp ở ổ VPS (``vi_tri='vps'``) → container day-tep đẩy sang Viettel CFS
    (``day_tep`` đọc cả bảng này); đọc: ổ VPS trước, rồi CFS — qua
    ``chay_tren_kho`` có hạn giờ, ổ chậm không treo API.
Nhưng KHÔNG nằm trong ``tep_ket_qua``: bảng ấy là kết quả khám (gửi khách,
bác sĩ duyệt, chuông báo bác sĩ) — ảnh chuyển khoản là chứng từ của quầy thu.

Quyền: người giữ quyền thu ĐÚNG loại tiền của lần thu (như thu / hoàn tác).
Gỡ ảnh nhầm = ẩn (``go_luc``), giữ tệp và vết.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.kho_tep import KHO_VPS, chay_tren_kho, don_tren_kho
from clinicai.permissions.can import can
from clinicai.services import media_service
from clinicai.services.media_service import sniff_ket_qua
from clinicai.services.nhan_tep_luong import TepDaNhan

logger = structlog.get_logger()

#: Ảnh chụp màn hình điện thoại vài trăm KB; màn đã thu nhỏ trước khi gửi.
#: 15MB đủ cho ảnh gốc từ máy ảnh, vẫn chặn được tệp lạ to bất thường.
TRAN_BYTE = 15 * 1024 * 1024

QUYEN_THU = {
    "dich_vu": "payment.service.collect",
    "thuoc": "payment.medicine.collect",
}


def duong_dan_anh(
    *, clinic_id: str, cycle_id: str, ext: str, goc: Path
) -> tuple[Path, str]:
    """(đường trên đĩa, khoá lưu DB). Không phần nào đến từ người dùng; bắt đầu
    bằng clinic_id như mọi tệp khác (hai phòng khám không đọc chéo được)."""
    khoa = f"{clinic_id}/chuyen-khoan/{cycle_id}/{uuid.uuid4().hex}{ext}"
    return goc / khoa, khoa


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


async def anh_cua_cac_lan_thu(
    conn: asyncpg.Connection, clinic_id: str, cycle_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """Ảnh CÒN HIỆU LỰC (chưa gỡ) của các lần thu: cycle_id → [{id, luc, boi}]."""
    ids = sorted({str(c) for c in cycle_ids if c})
    if not ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT a.id::text AS id, a.cycle_id::text AS cycle_id, a.tai_len_luc,
               s.full_name AS boi
          FROM public.anh_chuyen_khoan a
          LEFT JOIN public.staff s ON s.id = a.tai_len_boi_staff_id
         WHERE a.clinic_id = $1::uuid AND a.cycle_id = ANY($2::uuid[])
           AND a.go_luc IS NULL
         ORDER BY a.tai_len_luc, a.id
        """,
        clinic_id,
        ids,
    )
    ra: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        ra.setdefault(r["cycle_id"], []).append(
            {"id": r["id"], "luc": _iso(r["tai_len_luc"]), "boi": r["boi"]}
        )
    return ra


class AnhChuyenKhoanService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _lan_thu(
        self, conn: asyncpg.Connection, identity: StaffIdentity, cycle_id: str
    ) -> asyncpg.Record:
        lan = await conn.fetchrow(
            "SELECT payment_cycle_id::text AS id, kind FROM public.payment_cycle"
            " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid",
            identity.clinic_id,
            cycle_id,
        )
        if lan is None:
            raise NotFoundError("Không tìm thấy lần thu này.")
        if not await can(conn, identity, QUYEN_THU[str(lan["kind"])]):
            raise SafetyGateError("Bạn không có quyền thu loại tiền của lần thu này.")
        return lan

    async def tai_len(
        self, *, identity: StaffIdentity, payment_cycle_id: str, tep: TepDaNhan
    ) -> dict[str, Any]:
        """Cất ảnh (đã nằm ở ``.tam`` của ổ VPS) về chỗ ở thật + một dòng."""
        if tep.so_byte <= 0:
            raise ValidationError("Tệp rỗng.")
        mime, ext, loai = sniff_ket_qua(tep.dau)
        if loai != "ANH" or mime == "application/dicom":
            raise ValidationError(
                "Chỉ nhận ẢNH chuyển khoản (JPG/PNG/WEBP) — chụp hoặc chọn"
                " ảnh màn hình."
            )
        if tep.so_byte > TRAN_BYTE:
            raise ValidationError(
                f"Ảnh quá lớn (tối đa {TRAN_BYTE // 1024 // 1024}MB)."
            )
        async with self._pool.acquire() as conn:
            await self._lan_thu(conn, identity, payment_cycle_id)
        goc = media_service.goc_vps()
        path, khoa = duong_dan_anh(
            clinic_id=identity.clinic_id, cycle_id=payment_cycle_id, ext=ext, goc=goc
        )
        nguon = tep.duong

        def _dat() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(nguon, path)
            path.chmod(0o600)

        await chay_tren_kho(_dat, kho=KHO_VPS)
        try:
            async with self._pool.acquire() as conn:
                anh_id = await conn.fetchval(
                    """
                    INSERT INTO public.anh_chuyen_khoan
                        (clinic_id, cycle_id, khoa, mime, so_byte, sha256,
                         tai_len_boi_staff_id, vi_tri)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, 'vps')
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    payment_cycle_id,
                    khoa,
                    mime,
                    tep.so_byte,
                    tep.sha256,
                    identity.staff_id,
                )
        except BaseException:
            await don_tren_kho(
                lambda: path.unlink(missing_ok=True),
                viec=f"xoa_anh_ck_hong:{path}",
                kho=KHO_VPS,
            )
            raise
        logger.info(
            "anh_chuyen_khoan_tai_len",
            payment_cycle_id=payment_cycle_id,
            bytes=tep.so_byte,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "id": anh_id, "payment_cycle_id": payment_cycle_id}

    async def doc(self, *, identity: StaffIdentity, anh_id: str) -> tuple[bytes, str]:
        """(nội dung, mime) — ổ VPS trước, rồi CFS (tệp đã đẩy)."""
        from clinicai.services.tep_ket_qua_service import _tim_ban

        async with self._pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT cycle_id::text AS cycle_id, khoa, mime, vi_tri"
                "  FROM public.anh_chuyen_khoan"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                identity.clinic_id,
                anh_id,
            )
            if r is None:
                raise NotFoundError("Không tìm thấy ảnh này.")
            await self._lan_thu(conn, identity, r["cycle_id"])
        duong, kho, f = await _tim_ban(str(r["khoa"]), str(r["vi_tri"]), mo=True)
        assert f is not None
        mo = f
        try:
            noi_dung = await chay_tren_kho(lambda: mo.read(TRAN_BYTE + 1), kho=kho)
        finally:
            await don_tren_kho(mo.close, viec=f"dong_anh_ck:{duong}", kho=kho)
        return noi_dung, str(r["mime"])

    async def go(self, *, identity: StaffIdentity, anh_id: str) -> dict[str, Any]:
        """Gỡ ảnh nhầm: ẩn khỏi màn (giữ tệp + dòng). Gỡ lại → như cũ."""
        async with self._pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT cycle_id::text AS cycle_id, go_luc FROM public.anh_chuyen_khoan"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                identity.clinic_id,
                anh_id,
            )
            if r is None:
                raise NotFoundError("Không tìm thấy ảnh này.")
            await self._lan_thu(conn, identity, r["cycle_id"])
            if r["go_luc"] is None:
                await conn.execute(
                    "UPDATE public.anh_chuyen_khoan"
                    "   SET go_luc = now(), go_boi_staff_id = $3::uuid"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid AND go_luc IS NULL",
                    identity.clinic_id,
                    anh_id,
                    identity.staff_id,
                )
        return {"ok": True, "id": anh_id, "payment_cycle_id": r["cycle_id"]}


__all__ = [
    "AnhChuyenKhoanService",
    "TRAN_BYTE",
    "anh_cua_cac_lan_thu",
    "duong_dan_anh",
]
