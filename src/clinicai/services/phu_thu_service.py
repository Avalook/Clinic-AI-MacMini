"""Phụ thu kèm dịch vụ — tick "thêm đầu dò" ở THU TIỀN DỊCH VỤ (28/09/2026).

Tuyền: "thêm ô tick vào thu dịch vụ là thêm đầu dò và điền được giá vào". Món
kèm của một dịch vụ khai ở `phu_thu_mau` (migration 20260928000099); tick cho
MỘT chỉ định lưu ở `luot_phu_thu` kèm giá chốt (sửa được trước khi thu). Tiền
vào hoá đơn DỊCH VỤ (dòng `phu_thu`, `bill_service`) — thu cùng lần với dịch vụ.
Kho gắn sau, không trừ ở đây.

Đã thu (lần thu đang giữ phủ dòng ấy) → khoá: đổi phải huỷ phiếu trước.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.bill_service import _DA_PHU
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

#: Quầy thu dịch vụ / chọn dịch vụ cho khách.
QUYEN_PHU_THU = ("payment.service.collect", "service_selection.confirm")

_MON_KEM_SQL = """
SELECT o.id::text AS order_id, o.service_name, m.id::text AS mau_id, m.ten,
       m.gia_mac_dinh, p.id::text AS dong_id, p.don_gia,
       CASE WHEN p.id IS NULL THEN false
            ELSE {da_phu} END AS da_thu
  FROM public.service_order o
  JOIN public.service_price sp
    ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code AND sp.active
  JOIN public.phu_thu_mau m
    ON m.clinic_id = o.clinic_id AND m.service_price_id = sp.id AND m.active
  LEFT JOIN public.luot_phu_thu p
    ON p.clinic_id = o.clinic_id AND p.service_order_id = o.id
   AND p.phu_thu_mau_id = m.id AND p.bo_luc IS NULL
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
   AND coalesce(o.selection_status, 'SELECTED') <> 'NOT_SELECTED'
 ORDER BY o.created_at, o.id, m.thu_tu, m.ten
"""


def _gia(v: Any) -> Decimal:
    try:
        g = Decimal(str(v).replace(".", "").replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValidationError("Giá không hợp lệ.") from None
    if g < 0 or g > Decimal("1000000000"):
        raise ValidationError("Giá không hợp lệ.")
    return g


async def _duoc(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_PHU_THU:
        if await can(conn, identity, q):
            return True
    return False


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        _MON_KEM_SQL.format(
            da_phu=_DA_PHU.format(loai="'phu_thu'", nguon="p.id::text")
        ),
        clinic_id,
        visit_id,
    )
    theo_don: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = theo_don.setdefault(
            r["order_id"],
            {"order_id": r["order_id"], "dich_vu": r["service_name"], "mon": []},
        )
        d["mon"].append(
            {
                "mau_id": r["mau_id"],
                "ten": r["ten"],
                "gia_mac_dinh": (
                    int(r["gia_mac_dinh"]) if r["gia_mac_dinh"] is not None else None
                ),
                "chon": r["dong_id"] is not None,
                "don_gia": int(r["don_gia"]) if r["don_gia"] is not None else None,
                "da_thu": bool(r["da_thu"]),
            }
        )
    return list(theo_don.values())


class PhuThuService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            return {
                "dich_vu": await _doc(conn, identity.clinic_id, vid),
                "duoc_sua": await _duoc(conn, identity),
            }

    async def dat(
        self,
        *,
        order_id: str,
        mau_id: str,
        chon: bool,
        don_gia: Any,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Tick / bỏ tick / sửa giá một món kèm của một chỉ định."""
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        mid = _uuid(mau_id, "Mã món kèm không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            if not await _duoc(conn, identity):
                raise SafetyGateError("Bạn không có quyền thu tiền dịch vụ.")
            vid = await conn.fetchval(
                "SELECT visit_id::text FROM public.service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
            )
            if vid is None:
                raise NotFoundError("Không tìm thấy chỉ định này.")
            await khoa_luot(conn, cid, vid, cho_phep_da_ky=True)
            hien = next(
                (
                    m
                    for d in await _doc(conn, cid, vid)
                    if d["order_id"] == oid
                    for m in d["mon"]
                    if m["mau_id"] == mid
                ),
                None,
            )
            if hien is None:
                raise ValidationError("Dịch vụ này không có món kèm ấy.")
            if hien["da_thu"]:
                raise ConflictError(
                    "Món kèm này đã thu tiền — huỷ phiếu thu trước khi đổi."
                )
            ten = hien["ten"]
            gia = (
                _gia(don_gia)
                if don_gia not in (None, "")
                else Decimal(hien["don_gia"] or hien["gia_mac_dinh"] or 0)
            )
            gia_hien_tai = (
                Decimal(str(hien["don_gia"])) if hien["don_gia"] is not None else None
            )
            if bool(hien["chon"]) == chon and (not chon or gia_hien_tai == gia):
                # Idempotent theo trạng thái nghiệp vụ: rời ô giá hoặc retry
                # không được tạo UUID/audit/revision hoá đơn mới.
                return {
                    "dich_vu": await _doc(conn, cid, vid),
                    "duoc_sua": True,
                }
            if hien["chon"]:
                await conn.execute(
                    "UPDATE public.luot_phu_thu SET bo_luc = now(), bo_boi = $4::uuid"
                    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                    " AND phu_thu_mau_id = $3::uuid AND bo_luc IS NULL",
                    cid,
                    oid,
                    mid,
                    identity.staff_id,
                )
            if chon:
                await conn.execute(
                    "INSERT INTO public.luot_phu_thu (clinic_id, visit_id,"
                    " service_order_id, phu_thu_mau_id, ten, don_gia, chon_boi)"
                    " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6,"
                    " $7::uuid)",
                    cid,
                    vid,
                    oid,
                    mid,
                    ten,
                    gia,
                    identity.staff_id,
                )
            await record_event(
                conn,
                event_type="visit.surcharge_set",
                aggregate_type="service_order",
                aggregate_id=oid,
                identity=identity,
                origin="api:phu-thu",
                payload={"mau_id": mid, "chon": chon, "don_gia": str(gia)},
                correlation_id=vid,
            )
            return {
                "dich_vu": await _doc(conn, cid, vid),
                "duoc_sua": True,
            }


__all__ = ["QUYEN_PHU_THU", "PhuThuService"]
