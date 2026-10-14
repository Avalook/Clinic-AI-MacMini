"""Dịch vụ hoá đơn công ty (G5c · Antigravity 14/10/2026).

Bảng `khach_cong_ty`: nhiều công ty/khách, điền sẵn lần trước.
Bảng `hoa_don_cong_ty`: snapshot thông tin công ty tại thời điểm tick cho payment_cycle.
Bảng `hoa_don_cong_ty_lich_su`: lịch sử sửa sau khi xuất.
Bảng `hoa_don_misa_xuat`: đánh dấu "đã xuất MISA" + bản chụp tổng.

MST sai (không 10 số hoặc 10 số + "-" + 3 số) → chỉ nhắc, không chặn.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any
from uuid import UUID, uuid4

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.services.audit import record_event

logger = structlog.get_logger()

_MST_RE = re.compile(r"^[0-9]{10}(-[0-9]{3})?$")


def kiem_mst(mst: str) -> bool:
    """Trả True nếu MST có vẻ hợp lệ (10 số hoặc 10 số + '-' + 3 số)."""
    return bool(_MST_RE.match(mst.strip())) if mst else True  # rỗng = chưa điền → ok


def _canh_bao_mst(mst: str) -> str | None:
    """Trả chuỗi cảnh báo nếu MST sai định dạng; None nếu ổn."""
    mst = mst.strip()
    if mst and not kiem_mst(mst):
        return "Mã số thuế không đúng định dạng (cần 10 số hoặc 10 số + '-' + 3 số) — đã lưu nhưng nên kiểm lại"
    return None


# ─── SQL ─────────────────────────────────────────────────────────────────────

_DOC_CONG_TY_KHACH = """
SELECT id::text, ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,
       is_mac_dinh, ghi_chu
FROM public.khach_cong_ty
WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
ORDER BY is_mac_dinh DESC, tao_luc DESC
"""

_DOC_CONG_TY_KHACH_ONE = """
SELECT id::text, ten_cong_ty, dia_chi_cong_ty, ma_so_thue, email_nhan_hd,
       is_mac_dinh, ghi_chu
FROM public.khach_cong_ty
WHERE clinic_id = $1::uuid AND id = $2::uuid
"""

_LUU_CONG_TY_KHACH = """
INSERT INTO public.khach_cong_ty
    (id, clinic_id, clinic_patient_id, ten_cong_ty, dia_chi_cong_ty,
     ma_so_thue, email_nhan_hd, is_mac_dinh, ghi_chu, tao_boi, sua_boi)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $10)
ON CONFLICT (id) DO UPDATE SET
    ten_cong_ty     = EXCLUDED.ten_cong_ty,
    dia_chi_cong_ty = EXCLUDED.dia_chi_cong_ty,
    ma_so_thue      = EXCLUDED.ma_so_thue,
    email_nhan_hd   = EXCLUDED.email_nhan_hd,
    is_mac_dinh     = EXCLUDED.is_mac_dinh,
    ghi_chu         = EXCLUDED.ghi_chu,
    sua_boi         = EXCLUDED.sua_boi,
    sua_luc         = now()
RETURNING id::text
"""

_DAT_MAC_DINH = """
UPDATE public.khach_cong_ty
SET is_mac_dinh = false, sua_luc = now()
WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid AND id <> $3::uuid
"""

_XOA_CONG_TY_KHACH = """
DELETE FROM public.khach_cong_ty
WHERE clinic_id = $1::uuid AND id = $2::uuid
RETURNING id
"""

_DOC_HOA_DON_CONG_TY = """
SELECT id::text, payment_cycle_id::text, ten_cong_ty, dia_chi_cong_ty,
       ma_so_thue, email_nhan_hd,
       khach_cong_ty_id::text, ghi_luc
FROM public.hoa_don_cong_ty
WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid
"""

_UPSERT_HOA_DON_CONG_TY = """
INSERT INTO public.hoa_don_cong_ty
    (id, clinic_id, payment_cycle_id, ten_cong_ty, dia_chi_cong_ty,
     ma_so_thue, email_nhan_hd, khach_cong_ty_id, ghi_boi, ghi_luc)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
ON CONFLICT ON CONSTRAINT uq_hoa_don_cong_ty_cycle DO UPDATE SET
    ten_cong_ty        = EXCLUDED.ten_cong_ty,
    dia_chi_cong_ty    = EXCLUDED.dia_chi_cong_ty,
    ma_so_thue         = EXCLUDED.ma_so_thue,
    email_nhan_hd      = EXCLUDED.email_nhan_hd,
    khach_cong_ty_id   = EXCLUDED.khach_cong_ty_id,
    ghi_boi            = EXCLUDED.ghi_boi,
    ghi_luc            = now()
RETURNING id::text
"""

_LICH_SU_HOA_DON_CT = """
INSERT INTO public.hoa_don_cong_ty_lich_su
    (id, hoa_don_cong_ty_id, clinic_id,
     cu_ten, cu_dia_chi, cu_ma_so_thue, cu_email,
     moi_ten, moi_dia_chi, moi_ma_so_thue, moi_email,
     sua_boi)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
"""

_DOC_LICH_SU = """
SELECT ls.id::text, ls.cu_ten, ls.cu_dia_chi, ls.cu_ma_so_thue, ls.cu_email,
       ls.moi_ten, ls.moi_dia_chi, ls.moi_ma_so_thue, ls.moi_email,
       ls.sua_luc, s.full_name AS sua_boi_ten
FROM public.hoa_don_cong_ty_lich_su ls
LEFT JOIN public.staff s ON s.id = ls.sua_boi
WHERE ls.hoa_don_cong_ty_id = $1::uuid
ORDER BY ls.sua_luc DESC
LIMIT 50
"""

_DOC_MISA_XUAT = """
SELECT id::text, tu_ngay, den_ngay, co_so, so_hoa_don, tong_tien,
       xuat_luc, ghi_chu, ban_chup
FROM public.hoa_don_misa_xuat
WHERE clinic_id = $1::uuid
ORDER BY xuat_luc DESC
LIMIT 200
"""

_THEM_MISA_XUAT = """
INSERT INTO public.hoa_don_misa_xuat
    (id, clinic_id, tu_ngay, den_ngay, co_so, so_hoa_don, tong_tien,
     xuat_boi, ghi_chu, ban_chup)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
RETURNING id::text
"""

_DOC_CONG_TY_CYCLES = """
SELECT payment_cycle_id::text AS id, ten_cong_ty, dia_chi_cong_ty,
       ma_so_thue, email_nhan_hd
FROM public.hoa_don_cong_ty
WHERE clinic_id = $1::uuid AND payment_cycle_id = ANY($2::uuid[])
"""


class HoaDonCongTyService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    # ── Công ty của khách ───────────────────────────────────────────────────

    async def doc_cong_ty_khach(
        self, *, identity: StaffIdentity, clinic_patient_id: str
    ) -> list[dict[str, Any]]:
        """Danh sách công ty của khách (mặc định đứng đầu)."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                _DOC_CONG_TY_KHACH,
                identity.clinic_id,
                UUID(clinic_patient_id),
            )
        return [dict(r) for r in rows]

    async def luu_cong_ty_khach(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        id: str | None = None,
        ten_cong_ty: str,
        dia_chi_cong_ty: str = "",
        ma_so_thue: str = "",
        email_nhan_hd: str = "",
        is_mac_dinh: bool = True,
        ghi_chu: str = "",
    ) -> dict[str, Any]:
        """Tạo hoặc cập nhật công ty của khách. MST sai → nhắc nhở qua canh_bao."""
        ten = ten_cong_ty.strip()
        if not ten:
            raise ValidationError("Tên công ty không được để trống")
        rec_id = UUID(id) if id else uuid4()
        canh_bao = _canh_bao_mst(ma_so_thue)
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if is_mac_dinh:
                    await conn.execute(
                        _DAT_MAC_DINH,
                        identity.clinic_id,
                        UUID(clinic_patient_id),
                        rec_id,
                    )
                row = await conn.fetchrow(
                    _LUU_CONG_TY_KHACH,
                    rec_id,
                    identity.clinic_id,
                    UUID(clinic_patient_id),
                    ten,
                    dia_chi_cong_ty.strip(),
                    ma_so_thue.strip(),
                    email_nhan_hd.strip(),
                    is_mac_dinh,
                    ghi_chu.strip(),
                    identity.staff_id,
                )
        await record_event(
            self.pool,
            source="api:hoa-don-cong-ty",
            clinic_id=identity.clinic_id,
            staff_id=identity.staff_id,
            action="luu_cong_ty_khach",
            meta={"id": str(rec_id), "ten": ten},
        )
        return {"id": row["id"], "canh_bao_mst": canh_bao}

    async def xoa_cong_ty_khach(
        self, *, identity: StaffIdentity, id: str
    ) -> None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                _XOA_CONG_TY_KHACH, identity.clinic_id, UUID(id)
            )
        if not row:
            raise ResourceNotFoundError("Không tìm thấy công ty")
        await record_event(
            self.pool,
            source="api:hoa-don-cong-ty",
            clinic_id=identity.clinic_id,
            staff_id=identity.staff_id,
            action="xoa_cong_ty_khach",
            meta={"id": id},
        )

    # ── Hoá đơn công ty (snapshot theo payment_cycle) ──────────────────────

    async def doc_hoa_don_cong_ty(
        self, *, identity: StaffIdentity, payment_cycle_id: str
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                _DOC_HOA_DON_CONG_TY,
                identity.clinic_id,
                UUID(payment_cycle_id),
            )
        return dict(row) if row else None

    async def ghi_hoa_don_cong_ty(
        self,
        *,
        identity: StaffIdentity,
        payment_cycle_id: str,
        ten_cong_ty: str,
        dia_chi_cong_ty: str = "",
        ma_so_thue: str = "",
        email_nhan_hd: str = "",
        khach_cong_ty_id: str | None = None,
    ) -> dict[str, Any]:
        """Tạo/cập nhật snapshot công ty cho payment_cycle.

        Nếu đã có bản ghi cũ (đã xuất MISA trước đó), ghi lịch sử sửa.
        """
        ten = ten_cong_ty.strip()
        if not ten:
            raise ValidationError("Tên công ty không được để trống")
        canh_bao = _canh_bao_mst(ma_so_thue)
        rec_id = uuid4()
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Kiểm tra có bản ghi cũ không (để ghi lịch sử nếu cần)
                old = await conn.fetchrow(
                    _DOC_HOA_DON_CONG_TY,
                    identity.clinic_id,
                    UUID(payment_cycle_id),
                )
                row = await conn.fetchrow(
                    _UPSERT_HOA_DON_CONG_TY,
                    rec_id,
                    identity.clinic_id,
                    UUID(payment_cycle_id),
                    ten,
                    dia_chi_cong_ty.strip(),
                    ma_so_thue.strip(),
                    email_nhan_hd.strip(),
                    UUID(khach_cong_ty_id) if khach_cong_ty_id else None,
                    identity.staff_id,
                )
                # Nếu cũ khác mới → ghi lịch sử
                if old and (
                    old["ten_cong_ty"] != ten
                    or old["dia_chi_cong_ty"] != dia_chi_cong_ty.strip()
                    or old["ma_so_thue"] != ma_so_thue.strip()
                    or old["email_nhan_hd"] != email_nhan_hd.strip()
                ):
                    await conn.execute(
                        _LICH_SU_HOA_DON_CT,
                        uuid4(),
                        UUID(row["id"]),
                        identity.clinic_id,
                        old["ten_cong_ty"],
                        old["dia_chi_cong_ty"],
                        old["ma_so_thue"],
                        old["email_nhan_hd"],
                        ten,
                        dia_chi_cong_ty.strip(),
                        ma_so_thue.strip(),
                        email_nhan_hd.strip(),
                        identity.staff_id,
                    )
        await record_event(
            self.pool,
            source="api:hoa-don-cong-ty",
            clinic_id=identity.clinic_id,
            staff_id=identity.staff_id,
            action="ghi_hoa_don_cong_ty",
            meta={"payment_cycle_id": payment_cycle_id, "ten": ten},
        )
        return {"id": row["id"], "canh_bao_mst": canh_bao}

    async def doc_lich_su(
        self, *, identity: StaffIdentity, hoa_don_cong_ty_id: str
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(_DOC_LICH_SU, UUID(hoa_don_cong_ty_id))
        return [dict(r) for r in rows]

    # ── Batch: lấy thông tin công ty cho nhiều payment_cycle ───────────────

    async def doc_cong_ty_cho_cycles(
        self, *, clinic_id: UUID, cycle_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        """Trả {payment_cycle_id: {ten_cong_ty, dia_chi, ma_so_thue, email}}."""
        if not cycle_ids:
            return {}
        ids = [UUID(x) for x in cycle_ids]
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(_DOC_CONG_TY_CYCLES, clinic_id, ids)
        return {r["id"]: dict(r) for r in rows}

    # ── Đánh dấu xuất MISA ─────────────────────────────────────────────────

    async def doc_misa_xuat(
        self, *, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(_DOC_MISA_XUAT, identity.clinic_id)
        return [
            {**dict(r), "ban_chup": r["ban_chup"] or []}
            for r in rows
        ]

    async def danh_dau_xuat_misa(
        self,
        *,
        identity: StaffIdentity,
        tu_ngay: str,
        den_ngay: str,
        hoa_don: list[dict[str, Any]],
        co_so: str | None = None,
        ghi_chu: str = "",
    ) -> dict[str, Any]:
        """Đánh dấu đã xuất kỳ này sang MISA. `hoa_don` = kết quả `xuat_hoa_don`."""
        import json

        so = len(hoa_don)
        tong = sum(int(h.get("tong") or 0) for h in hoa_don)
        # bản chụp nhỏ gọn: stt, ma_phieu, tong, ten_cong_ty
        ban_chup = [
            {
                "stt": h.get("stt"),
                "ma_phieu": h.get("ma_phieu"),
                "tong": h.get("tong"),
                "ten_cong_ty": h.get("ten_cong_ty") or "",
            }
            for h in hoa_don
        ]
        rec_id = uuid4()

        # parse ngày
        tu = _parse_ngay(tu_ngay)
        den = _parse_ngay(den_ngay)
        if not tu or not den:
            raise ValidationError("Ngày không đúng định dạng — nhập dd/mm/yyyy")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                _THEM_MISA_XUAT,
                rec_id,
                identity.clinic_id,
                tu,
                den,
                co_so,
                so,
                tong,
                identity.staff_id,
                ghi_chu.strip(),
                json.dumps(ban_chup, ensure_ascii=False),
            )
        await record_event(
            self.pool,
            source="api:hoa-don-cong-ty",
            clinic_id=identity.clinic_id,
            staff_id=identity.staff_id,
            action="danh_dau_xuat_misa",
            meta={"tu": tu_ngay, "den": den_ngay, "so_hoa_don": so},
        )
        return {"id": row["id"], "so_hoa_don": so, "tong_tien": tong}


def _parse_ngay(s: str) -> date | None:
    """dd/mm/yyyy → date; rác → None (không ném)."""
    try:
        from datetime import datetime

        return datetime.strptime(s.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None
