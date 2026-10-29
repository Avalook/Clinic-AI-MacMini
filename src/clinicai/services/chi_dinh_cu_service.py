"""CHỈ ĐỊNH CŨ CHƯA LÀM — hiện cho bác sĩ quyết, KHÔNG tự mang sang (chốt 29/10/2026).

"Hôm nào xong hôm đó": trước đây check-in tự kéo chỉ định cũ chưa làm sang lượt
mới (dây H2) và lịch "đi thẳng phòng" có chỉ định kéo sang thì không vào hàng bác
sĩ nào. Ca thật 28/10: chị Lê Thu Trang đến làm thủ thuật, máy kéo "Đo mật độ
xương" (24/10, chưa thu) sang → khách không nằm ở hàng chờ nào, BS Thành không
thấy để chỉ định soi buồng.

Nay lượt mới luôn trống; bàn khám hiện "Khách còn N chỉ định cũ chưa làm" (đã
đóng tiền hay chưa). Bác sĩ bấm [Làm hôm nay] thì chỉ định ấy dời sang lượt hôm
nay — GIỮ NGUYÊN mã nên tiền đi theo (đã đóng thì quầy không thu lại; chưa đóng
thì hiện ở hoá đơn hôm nay như chỉ định mới). Không tự xếp phòng: làm ở bàn khám
hoặc phòng nhận như chỉ định thường. [Trả về] hoàn tác khi chưa làm, chưa thu ở
lượt này.

Đã đóng tiền mà khách không làm nữa: [Huỷ chỉ định] sẵn có → tiền thừa ở quầy.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.emit import nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services import finance_gate
from clinicai.services.audit import record_event
from clinicai.services.chi_dinh_service import QUYEN_CHI_DINH, ChiDinhService
from clinicai.services.lenh_kham_core import LuotKhamConflictError, khoa_luot

CAU_KHONG_CON_CU = (
    "Chỉ định này không còn là chỉ định cũ chưa làm của khách — tải lại màn."
)
CAU_KHONG_TRA_VE = (
    "Chỉ định đã bắt đầu làm hoặc đã thu tiền ở lượt hôm nay — không trả về lượt"
    " cũ được."
)

#: Chỉ định CŨ chưa làm của chính khách đang ở lượt $2: lượt cũ đã đóng hoặc từ
#: hôm trước, bác sĩ đã duyệt, chưa ai bắt đầu, không còn chỗ chờ sống, ≤180
#: ngày. Khách đã bỏ ở quầy (NOT_SELECTED) không hiện — khách đã quyết.
_SQL_CU = """
SELECT o.id::text AS order_id, o.visit_id::text AS tu_visit_id,
       o.service_code, o.service_name,
       coalesce(v.checked_in_at, v.created_at) AS ngay_luot
  FROM service_order o
  JOIN visit v ON v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id
  JOIN visit moi ON moi.clinic_id = o.clinic_id AND moi.visit_id = $2::uuid
 WHERE o.clinic_id = $1::uuid
   AND v.clinic_patient_id = moi.clinic_patient_id
   AND o.visit_id <> moi.visit_id
   AND v.created_at < moi.created_at
   AND (v.closed_at IS NOT NULL
        OR v.created_at < date_trunc('day', moi.created_at AT TIME ZONE
                                     'Asia/Ho_Chi_Minh')
                          AT TIME ZONE 'Asia/Ho_Chi_Minh')
   AND o.created_at >= moi.created_at - interval '180 days'
   AND o.exec_status IN ('authorized', 'assigned')
   AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
   AND o.selection_status IN ('SELECTED', 'PENDING')
   AND NOT EXISTS (
       SELECT 1 FROM queue_entry q
        WHERE q.clinic_id = o.clinic_id AND q.reason = 'SERVICE'
          AND q.ref_id = o.id
          AND q.status IN ('blocked', 'waiting', 'called', 'serving'))
"""


def _uuid(v: Any) -> str | None:
    """Mã UUID chuẩn; rác → None (không ném: đầu vào người dùng)."""
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError, AttributeError):
        return None


def nhan_tien(finance_state: str | None) -> str:
    """Nhãn tiền cho người đọc — hàm thuần."""
    if finance_state == finance_gate.PAID:
        return "Đã đóng tiền"
    if finance_state in (finance_gate.NOT_REQUIRED, finance_gate.PARTNER_COLLECTS):
        return "Không thu ở quầy"
    return "Chưa đóng tiền"


async def danh_sach(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    """Chỉ định cũ chưa làm ĐÃ ĐÓNG TIỀN của khách ở lượt này, cũ trước. Mã rác
    → rỗng.

    Chỉ chỉ định đã đóng tiền (Tuyền 29/10/2026: "chỉ hiện loại đã đóng tiền để
    nhắc làm; chưa đóng tiền thì lịch sử vẫn ghi, không cần hiện ở đây") — khách
    đã trả mà chưa được làm là nợ dịch vụ của phòng khám; chưa trả thì chỉ là
    lần bác sĩ chỉ định cũ, xem ở Lịch sử khám."""
    vid = _uuid(visit_id)
    if vid is None:
        return []
    rows = await conn.fetch(
        _SQL_CU + " ORDER BY ngay_luot, o.created_at, o.id", clinic_id, vid
    )
    if not rows:
        return []
    tien = await finance_gate.states_for_orders(
        conn, clinic_id, [r["order_id"] for r in rows]
    )
    ra = []
    for r in rows:
        q = tien.get(r["order_id"])
        tt = q.finance_state if q is not None else None
        if tt != finance_gate.PAID:
            continue
        ra.append(
            {
                "order_id": r["order_id"],
                "tu_visit_id": r["tu_visit_id"],
                "service_code": r["service_code"],
                "service_name": r["service_name"],
                "ngay_luot": r["ngay_luot"].isoformat(),
                "da_dong_tien": tt == finance_gate.PAID,
                "nhan_tien": nhan_tien(tt),
            }
        )
    return ra


async def lam_hom_nay(
    pool: asyncpg.Pool, *, visit_id: str, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """[Làm hôm nay] — dời MỘT chỉ định cũ sang lượt đang mở (bác sĩ quyết)."""
    cid = identity.clinic_id
    vid, oid = _uuid(visit_id), _uuid(order_id)
    if vid is None or oid is None:
        raise LuotKhamConflictError("ORDER_NOT_CARRYABLE", CAU_KHONG_CON_CU)
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen(conn, identity, QUYEN_CHI_DINH)
        await khoa_luot(conn, cid, vid)
        o = await conn.fetchrow(
            _SQL_CU + " AND o.id = $3::uuid FOR UPDATE OF o", cid, vid, oid
        )
        if o is None:
            raise LuotKhamConflictError("ORDER_NOT_CARRYABLE", CAU_KHONG_CON_CU)
        q = (await finance_gate.states_for_orders(conn, cid, [oid])).get(oid)
        da_thu = q is not None and q.finance_state == finance_gate.PAID
        await ChiDinhService.chuyen_sang_luot(
            conn,
            clinic_id=cid,
            order_id=oid,
            tu_visit_id=o["tu_visit_id"],
            visit_id=vid,
            service_code=o["service_code"],
            da_thu=da_thu,
            boi=nguoi(identity),
        )
    return {"ok": True, "order_id": oid, "da_dong_tien": da_thu}


async def tra_ve(
    pool: asyncpg.Pool, *, visit_id: str, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """[Trả về] — hoàn tác [Làm hôm nay]: chỉ định về lại lượt cũ, khi chưa ai
    bắt đầu và chưa thu ở lượt hôm nay."""
    cid = identity.clinic_id
    vid, oid = _uuid(visit_id), _uuid(order_id)
    if vid is None or oid is None:
        raise LuotKhamConflictError("ORDER_NOT_REVERTIBLE", CAU_KHONG_TRA_VE)
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen(conn, identity, QUYEN_CHI_DINH)
        await khoa_luot(conn, cid, vid)
        o = await conn.fetchrow(
            "SELECT mang_tu_visit_id::text AS ve, execution_status"
            "  FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid AND visit_id = $3::uuid"
            "   AND mang_tu_visit_id IS NOT NULL FOR UPDATE",
            cid,
            oid,
            vid,
        )
        da_thu_hom_nay = bool(
            await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM payment_bill_line b"
                "  JOIN payment_cycle pc ON pc.payment_cycle_id = b.payment_cycle_id"
                " WHERE b.clinic_id = $1::uuid AND b.visit_id = $2::uuid"
                "   AND b.source_type = 'service_order' AND b.source_id = $3"
                "   AND pc.status <> 'VOIDED')",
                cid,
                vid,
                oid,
            )
        )
        if (
            o is None
            or (o["execution_status"] or "PENDING") != "PENDING"
            or da_thu_hom_nay
        ):
            raise LuotKhamConflictError("ORDER_NOT_REVERTIBLE", CAU_KHONG_TRA_VE)
        await conn.execute(
            """
            UPDATE service_order
               SET visit_id = mang_tu_visit_id, mang_tu_visit_id = NULL,
                   mang_sang_luc = NULL,
                   routing_status = CASE WHEN routing_status IS NULL
                                         THEN NULL ELSE 'UNASSIGNED' END,
                   routing_revision = routing_revision + 1,
                   room_id = NULL, assigned_by = NULL, assigned_at = NULL,
                   exec_status = 'authorized',
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            """,
            cid,
            oid,
        )
        await conn.execute(
            "UPDATE queue_entry SET status = 'cancelled', version = version + 1,"
            "       updated_at = now()"
            " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid AND reason = 'SERVICE'"
            "   AND status NOT IN ('done', 'left', 'cancelled')",
            cid,
            oid,
        )
        await record_event(
            conn,
            event_type="service_order.carry_reverted",
            aggregate_type="service_order",
            aggregate_id=oid,
            identity=identity,
            origin="ban_kham",
            payload={"tu_visit_id": vid, "ve_visit_id": o["ve"]},
            correlation_id=vid,
        )
    return {"ok": True, "order_id": oid}


__all__ = [
    "CAU_KHONG_CON_CU",
    "CAU_KHONG_TRA_VE",
    "danh_sach",
    "lam_hom_nay",
    "nhan_tien",
    "tra_ve",
]
