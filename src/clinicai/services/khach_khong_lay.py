"""Khách không mua thuốc — cả đơn một lần, và MỞ LẠI được (16/11/2026).

VÌ SAO FILE NÀY CÓ. Trước đây "Khách không lấy" chỉ bấm được TỪNG DÒNG, gõ lý do
từng dòng, và không có đường mở lại — trái luật CLAUDE.md mục 7 (mọi thao tác nhân
viên bấm phải hoàn tác được). Quầy ngại bấm nên đơn không mua dồn mãi trong hàng
chờ. Tuyền chốt: có nút cả đơn, giữ nút từng dòng, và mở lại được.

KHÔNG VIẾT LẠI LUẬT ĐÓNG DÒNG. Đóng dòng đi đúng `PharmacyService.tu_choi` (giữ
mọi chặn: đã thu / chờ xác minh, còn phần đã bán chưa giao, đã giao). Cả đơn chạy
trong MỘT giao dịch (các lệnh `tu_choi` mượn chung kết nối → savepoint): một dòng
bị chặn thì không dòng nào đóng.

MỞ LẠI = lệnh bù của đúng bước "khách không lấy" (`thiet-ke-code.md` luật 4):
xoá `closed_at`/`refusal_reason` của dòng ấy, ghi sự kiện `pharmacy.refuse_undone`
mang lý do cũ. Dòng "Chốt — không giao thêm" (không có lý do từ chối) KHÔNG mở
bằng đường này. Luật "mở lại được không" nằm ở MỘT hàm — `ly_do_khong_mo_lai` —
dùng chung cho cờ trên màn (`ban_thuoc_service`) và cho lệnh ghi.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, cast

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.pharmacy_service import PharmacyService, ghi_nhat_ky
from clinicai.services.tuong_tac_cskh_service import _ConnectionBoundPool

DA_THU = (
    "Tiền thuốc của lượt này đã thu (hoặc đang chờ xác minh chuyển khoản) — "
    "khách đổi ý thì huỷ phiếu thu / hoàn tiền trước."
)


def ly_do_khong_mo_lai(
    *,
    da_dong: bool,
    khach_khong_lay: bool,
    da_giao: Decimal,
    lich_su: bool,
    da_thu_tien: bool,
) -> str | None:
    """Vì sao dòng này KHÔNG mở lại được; `None` = mở được. Hàm thuần."""
    if not da_dong:
        return "Dòng thuốc này đang xử lý — không có gì để mở lại."
    if lich_su:
        return "Dòng thuốc này đã được bác sĩ đính chính — không mở lại được."
    if not khach_khong_lay:
        return (
            "Dòng này đã “Chốt — không giao thêm”, không phải khách không lấy — "
            "không mở lại bằng nút này."
        )
    if da_giao > 0:
        return "Dòng này đã giao thuốc — không mở lại được."
    if da_thu_tien:
        return DA_THU
    return None


def co_cua_luot(dong: list[dict[str, Any]]) -> dict[str, bool]:
    """Hai cờ cấp LƯỢT cho màn — tính từ cờ từng dòng (máy chủ đã quyết)."""
    return {
        # `tu_choi` của dòng đã gồm: chưa thu tiền thuốc, chưa giao, có quyền ghi.
        "khong_lay_ca_don": any(d["thao_tac"].get("tu_choi") for d in dong),
        "mo_lai_ca_don": any(d["thao_tac"].get("mo_lai") for d in dong),
    }


def _uuid(gia_tri: object, ten: str) -> str:
    """Id rác → 422 tiếng Việt, không để Postgres ném thành 500."""
    try:
        return str(uuid.UUID(str(gia_tri)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError(f"{ten} không hợp lệ.") from exc


async def _khoa_luot(
    conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
) -> None:
    """Khoá LƯỢT trước — cùng thứ tự với lần thu (visit → prescription)."""
    co = await conn.fetchval(
        "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
        " AND visit_id = $2::uuid FOR UPDATE",
        identity.clinic_id,
        visit_id,
    )
    if co is None:
        raise NotFoundError("Không tìm thấy lượt khám này.")


async def khong_lay_ca_don(
    pool: asyncpg.Pool, identity: StaffIdentity, visit_id: object, ly_do: object
) -> dict[str, Any]:
    """Khách không mua cả đơn: đóng mọi dòng hiện hành chưa đóng, chưa giao."""
    vid = _uuid(visit_id, "Mã lượt khám")
    ly = ly_do.strip() if isinstance(ly_do, str) else ""
    if not ly:
        raise ValidationError(
            "Ghi rõ vì sao khách không mua đơn này — hết tiền, đã có thuốc ở "
            "nhà, hay đổi ý sau khi nghe tư vấn."
        )
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_luot(conn, identity, vid)
        # Kiểm TRƯỚC khi đóng dòng nào: đã thu thì từ chối cả lượt.
        if await PharmacyService._da_thu_tien_thuoc(conn, identity, vid):
            raise ConflictError(DA_THU)
        ids = await conn.fetch(
            """
            SELECT id::text FROM public.prescription
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND removed_at IS NULL AND closed_at IS NULL
               AND coalesce(dispensed_qty, 0) = 0
             ORDER BY created_at, id
            """,
            identity.clinic_id,
            vid,
        )
        ph = PharmacyService(cast(asyncpg.Pool, _ConnectionBoundPool(conn)))
        so_dong = 0
        for r in ids:
            kq = await ph.tu_choi(identity=identity, prescription_id=r["id"], ly_do=ly)
            so_dong += 0 if kq.get("da_chot_tu_truoc") else 1
    return {"ok": True, "so_dong": so_dong}


async def _mo_lai(
    conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
) -> bool:
    """Mở lại MỘT dòng trong giao dịch của người gọi. True = vừa mở."""
    don = await PharmacyService._khoa_theo_luot(conn, identity, prescription_id)
    if don["closed_at"] is None:
        return False
    ly_cu = await conn.fetchval(
        "SELECT refusal_reason FROM public.prescription"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid AND removed_at IS NULL",
        prescription_id,
        identity.clinic_id,
    )
    ly_do = ly_do_khong_mo_lai(
        da_dong=True,
        khach_khong_lay=ly_cu is not None,
        da_giao=Decimal(str(don["dispensed_qty"] or 0)),
        lich_su=don["removed_at"] is not None,
        da_thu_tien=await PharmacyService._da_thu_tien_thuoc(
            conn, identity, don["visit_id"]
        ),
    )
    if ly_do:
        raise ConflictError(ly_do)
    await conn.execute(
        """
        UPDATE public.prescription
           SET closed_at = NULL, refusal_reason = NULL, updated_at = now()
         WHERE id = $1::uuid AND clinic_id = $2::uuid AND removed_at IS NULL
           AND closed_at IS NOT NULL AND refusal_reason IS NOT NULL
        """,
        prescription_id,
        identity.clinic_id,
    )
    await ghi_nhat_ky(
        conn,
        identity=identity,
        event_type="pharmacy.refuse_undone",
        aggregate_type="prescription",
        aggregate_id=prescription_id,
        payload={"visit_id": str(don["visit_id"]), "refusal_reason_cu": ly_cu},
    )
    return True


async def mo_lai_dong(
    pool: asyncpg.Pool, identity: StaffIdentity, prescription_id: object
) -> dict[str, Any]:
    """Hoàn tác "Khách không lấy" của một dòng — dòng về lại Đang xử lý."""
    pid = _uuid(prescription_id, "Mã dòng thuốc")
    async with pool.acquire() as conn, conn.transaction():
        vua_mo = await _mo_lai(conn, identity, pid)
    return {"ok": True, "so_dong": 1 if vua_mo else 0}


async def mo_lai_ca_don(
    pool: asyncpg.Pool, identity: StaffIdentity, visit_id: object
) -> dict[str, Any]:
    """Mở lại MỌI dòng "khách không lấy" của lượt — một giao dịch."""
    vid = _uuid(visit_id, "Mã lượt khám")
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_luot(conn, identity, vid)
        if await PharmacyService._da_thu_tien_thuoc(conn, identity, vid):
            raise ConflictError(DA_THU)
        ids = await conn.fetch(
            """
            SELECT id::text FROM public.prescription
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND removed_at IS NULL AND closed_at IS NOT NULL
               AND refusal_reason IS NOT NULL
               AND coalesce(dispensed_qty, 0) = 0
             ORDER BY created_at, id
            """,
            identity.clinic_id,
            vid,
        )
        so_dong = 0
        for r in ids:
            so_dong += 1 if await _mo_lai(conn, identity, r["id"]) else 0
    return {"ok": True, "so_dong": so_dong}
