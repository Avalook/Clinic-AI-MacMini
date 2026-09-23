"""Service Lifecycle v1 — Routing chính thức (Slice 4).

Contract: docs/ai/lifecycle-v1/ClinicAI-ROUTING-v1.md (frozen).

Ba thứ tách rời:
  * ``eligible_rooms`` — tập phòng ĐỦ ĐIỀU KIỆN của một node, kèm tải hàng chờ
    và tín hiệu lịch trực, trong MỘT truy vấn;
  * ``rank_rooms`` (RuleBasedRoomAdvisor) — xếp hạng thuần, KHÔNG ghi gì;
  * ``ServiceRoutingService.assign / invalidate`` — lệnh DUY NHẤT đổi trạng thái
    routing. Gợi ý (của luật hay của AI sau này) chỉ là gợi ý: lệnh đọc lại và
    kiểm lại mọi điều kiện trong giao dịch.

Thứ tự khoá (ROUTING §7): lượt → biên nhận → service_order → revision →
selection + FinanceGate + hold → phòng → hàng chờ → trạng thái routing → sự
kiện → biên nhận. Cùng "lượt trước" với Selection / Payment / Execution.

OPEN, không tự chốt ở đây:
  * sinh hiệu có chặn điều phối không → seam ``luot_kham_rules.vitals_routing_block``;
  * ánh xạ vai → capability → ``can_route_*`` bên dưới;
  * có người trực là chốt cứng hay chỉ tín hiệu → ở v1 CHỈ là tín hiệu xếp hạng.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import XepPhongDaHuy
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services import finance_gate
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    LuotKhamValidationError,
    _uuid,
)

ORIGIN = "api:service-routing"
ACTION_ASSIGN = "service_routing.assign"
ACTION_INVALIDATE = "service_routing.invalidate"
EVENT_ROUTED = "service.routed"
EVENT_INVALIDATED = "service.routing_invalidated"
ADVISOR = "rule-v1"

UNASSIGNED = "UNASSIGNED"
ASSIGNED = "ASSIGNED"
REASSIGNMENT_REQUIRED = "REASSIGNMENT_REQUIRED"

ASSIGN_REASONS = frozenset(
    {
        "INITIAL_ASSIGNMENT",
        "LOAD_BALANCE",
        "ROOM_UNAVAILABLE",
        "STAFF_UNAVAILABLE",
        "EQUIPMENT_FAILURE",
        "PATIENT_NEED",
        "MANUAL_CORRECTION",
        "OTHER",
    }
)
INVALIDATE_REASONS = frozenset(
    {
        "ROOM_UNAVAILABLE",
        "STAFF_UNAVAILABLE",
        "EQUIPMENT_FAILURE",
        "CONFIG_CHANGED",
        "OTHER",
    }
)

#: Trục thực hiện: đã bắt đầu → không điều phối thường; đã kết thúc → không điều
#: phối nữa. INTERRUPTED không phải kết thúc (EXECUTION §2) — xếp lại phòng là
#: một bước của luồng thử lại.
_DANG_LAM = frozenset({"IN_PROGRESS"})
_KET_THUC = frozenset({"COMPLETED", "CANCELLED", "NOT_PERFORMED"})
_DANG_LAM_CU = frozenset({"in_progress"})
_KET_THUC_CU = frozenset({"performed", "not_performed", "cancelled"})


# ---------------------------------------------------------------------------
# Quyền — capability seam (ánh xạ vai cuối cùng còn OPEN)
# ---------------------------------------------------------------------------


#: Ba quyền riêng trong MỘT khối "Điều phối khách": quản lý bật cả khối, còn
#: tầng kỹ thuật vẫn tách được "xem gợi ý" khỏi "xếp phòng" khi cần siết.
QUYEN_XEM = "service.routing.view"
QUYEN_XEP = "service.routing.assign"
QUYEN_HUY = "service.routing.invalidate"


async def can_route_recommend(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    return await can(conn, identity, QUYEN_XEM)


async def can_route_assign(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    return await can(conn, identity, QUYEN_XEP)


async def can_route_invalidate(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    return await can(conn, identity, QUYEN_HUY)


# ---------------------------------------------------------------------------
# EligibleRoomQuery + RuleBasedRoomAdvisor
# ---------------------------------------------------------------------------

#: MỘT truy vấn: phòng cùng phòng khám, đang mở, đang nhận khách, làm được node
#: — kèm tải hàng chờ sống và tín hiệu "hôm nay có người trực ở phòng". Tải và
#: lịch trực là TÍN HIỆU xếp hạng, không phải điều kiện.
_ELIGIBLE_SQL = """
SELECT r.id::text AS room_id, r.code, r.sort,
       EXISTS (
           SELECT 1 FROM work_roster w
             JOIN vi_tri_lam_viec v
               ON v.clinic_id = w.clinic_id AND v.code = w.station
            WHERE w.clinic_id = r.clinic_id AND v.room_id = r.id
              AND w.status <> 'REJECTED'
              AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       ) AS co_nguoi_truc,
       (SELECT count(*) FROM queue_entry q
         WHERE q.clinic_id = r.clinic_id AND q.room_id = r.id
           AND q.status IN ('blocked', 'waiting', 'called', 'serving'))::int AS tai
  FROM clinic_room r
  JOIN clinic_room_node rn ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
 WHERE r.clinic_id = $1::uuid AND rn.node_code = $2
   AND r.is_active AND r.accepting AND NOT r.la_doi_tac
"""


@dataclass(frozen=True)
class RoomCandidate:
    room_id: str
    code: str
    sort: int
    co_nguoi_truc: bool
    tai: int


async def eligible_rooms(
    conn: asyncpg.Connection, clinic_id: str, node_code: str
) -> list[RoomCandidate]:
    """EligibleRoomQuery — tập phòng hợp lệ của một node, một truy vấn."""
    return [
        RoomCandidate(
            room_id=r["room_id"],
            code=r["code"],
            sort=int(r["sort"]),
            co_nguoi_truc=bool(r["co_nguoi_truc"]),
            tai=int(r["tai"]),
        )
        for r in await conn.fetch(_ELIGIBLE_SQL, clinic_id, node_code)
    ]


def rank_rooms(rooms: Sequence[RoomCandidate]) -> list[dict[str, Any]]:
    """RuleBasedRoomAdvisor — hàm thuần, chỉ xếp hạng TRONG tập đủ điều kiện.

    Cùng luật của ``_tu_xep_phong`` cũ: có người trực hôm nay trước, rồi phòng ít
    người chờ nhất, rồi thứ tự cấu hình. Không có người trực vẫn được gợi ý —
    lịch trực chỉ là tín hiệu.
    """
    xep = sorted(rooms, key=lambda r: (not r.co_nguoi_truc, r.tai, r.sort, r.code))
    it_nhat = min((r.tai for r in rooms), default=0)
    out: list[dict[str, Any]] = []
    for i, r in enumerate(xep, start=1):
        ly_do = ["STAFF_ON_SHIFT" if r.co_nguoi_truc else "NO_ROSTER_SIGNAL"]
        if r.tai == it_nhat:
            ly_do.append("LOWEST_QUEUE")
        out.append(
            {
                "room_id": r.room_id,
                "rank": i,
                "reason_codes": ly_do,
                "queue_load": r.tai,
                "confidence": None,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------


class RoutingFinanceNotReadyError(LuotKhamConflictError):
    """409 SERVICE_FINANCE_NOT_READY kèm lý do CHI TIẾT của FinanceGate —
    Routing không chép luật tài chính, chỉ chuyển lý do (ROUTING §18)."""

    def __init__(self, finance_reason: str | None) -> None:
        super().__init__(
            "SERVICE_FINANCE_NOT_READY",
            f"Dịch vụ chưa đủ điều kiện tài chính ({finance_reason}).",
        )
        self.finance_reason = finance_reason


def _loi(code: str, cau: str) -> LuotKhamConflictError:
    return LuotKhamConflictError(code, cau)


def _can_khoa(key: str | None) -> str:
    if not key:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key."
        )
    if not 8 <= len(key) <= 200:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Khoá gửi lại phải dài từ 8 đến 200 ký tự."
        )
    return key


def _revision(value: Any) -> int:
    if type(value) is not int or value < 0:
        raise LuotKhamValidationError(
            "ROUTING_REVISION_CONFLICT",
            "expected_routing_revision phải là số nguyên không âm.",
        )
    return value


def _ly_do(value: Any, cho_phep: frozenset[str]) -> str:
    if value not in cho_phep:
        raise LuotKhamValidationError(
            "ROUTING_REASON_INVALID", f"Mã lý do không hợp lệ: {value!r}."
        )
    if value == "OTHER":
        # Contract: OTHER cần ghi chú. Chưa có chỗ lưu ghi chú trong contract
        # (sự kiện chỉ mang mã) — từ chối thay vì tự đặt nơi lưu mới.
        raise LuotKhamValidationError(
            "ROUTING_REASON_NOTE_UNSUPPORTED",
            "Lý do OTHER cần ghi chú, nhưng chưa có chỗ lưu ghi chú — chọn mã cụ thể.",
        )
    return str(value)


_ORDER_SQL = """
SELECT id::text AS id, visit_id::text AS visit_id, exec_status, source,
       authorized_by::text AS authorized_by, hold_until_round, node_code,
       selection_status, routing_status, routing_revision, execution_status,
       room_id::text AS room_id
  FROM service_order
 WHERE clinic_id = $1::uuid AND id = $2::uuid
   FOR UPDATE
"""


def _routing_hieu_luc(o: asyncpg.Record) -> str:
    """Dòng lifecycle có routing_status NULL (fixture / cutover) coi như chưa xếp
    — KHÔNG suy phòng cũ thành phân phòng chính thức (Slice 4 §B)."""
    return str(o["routing_status"] or UNASSIGNED)


def _kiem_thuc_hien(o: asyncpg.Record) -> None:
    ex, cu = o["execution_status"], o["exec_status"]
    if ex in _DANG_LAM or cu in _DANG_LAM_CU:
        raise _loi(
            "SERVICE_ALREADY_IN_PROGRESS",
            "Dịch vụ đã bắt đầu — gặp sự cố thì dừng dịch vụ, không đổi phòng.",
        )
    if ex in _KET_THUC or cu in _KET_THUC_CU:
        raise _loi("SERVICE_EXECUTION_TERMINAL", "Dịch vụ đã kết thúc.")


class ServiceRoutingService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._luot = LuotKhamService(pool)

    async def recommend(
        self, *, order_id: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Gợi ý phòng. Không ghi gì, không phát sự kiện, không gọi lệnh gán."""
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                QUYEN_XEM,
                cau="Bạn chưa được cấp quyền xem gợi ý điều phối.",
            )
            node = await conn.fetchval(
                "SELECT node_code FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
            )
            if node is None:
                raise _loi("ORDER_NOT_FOUND", "Không tìm thấy chỉ định này.")
            ung_vien = rank_rooms(await eligible_rooms(conn, cid, str(node)))
        luc = datetime.now(timezone.utc).isoformat()
        return {
            "advisor": ADVISOR,
            "generated_at": luc,
            "recommendation_ref": f"{ADVISOR}:{oid}:{luc}",
            "order_id": oid,
            "candidates": ung_vien,
        }

    async def assign(
        self,
        *,
        order_id: Any,
        room_id: Any,
        expected_routing_revision: Any,
        reason_code: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
        recommendation_ref: str | None = None,
    ) -> dict[str, Any]:
        """AssignServiceRoom — lệnh DUY NHẤT xếp / đổi phòng chính thức."""
        key = _can_khoa(idempotency_key)
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        rev = _revision(expected_routing_revision)
        ly_do = _ly_do(reason_code, ASSIGN_REASONS)
        ref = recommendation_ref if isinstance(recommendation_ref, str) else None
        if ref is not None and len(ref) > 300:
            raise LuotKhamValidationError(
                "RECOMMENDATION_REF_INVALID", "recommendation_ref quá dài."
            )
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_routing_revision": rev,
            "reason_code": ly_do,
            "recommendation_ref": ref,
        }
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền trong chính giao dịch của lệnh.
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn chưa được cấp quyền xếp phòng."
            )
            vid = await self._luot._visit_of(conn, "service_order", cid, oid)
            await self._luot._lock_visit(conn, cid, vid)
            cached = await self._luot._receipt_get(
                conn, identity, ACTION_ASSIGN, key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None  # _visit_of đã thấy trong cùng giao dịch
            if int(o["routing_revision"]) != rev:
                raise _loi(
                    "ROUTING_REVISION_CONFLICT",
                    "Chỉ định vừa được điều phối bởi người khác — tải lại.",
                )
            if o["exec_status"] in ("draft", "cancelled") or not o["authorized_by"]:
                raise _loi(
                    "SERVICE_ROUTING_NOT_ALLOWED",
                    "Chỉ định chưa được bác sĩ duyệt hoặc đã huỷ.",
                )
            _kiem_thuc_hien(o)
            if o["selection_status"] != "SELECTED":
                raise _loi("SERVICE_NOT_SELECTED", "Khách chưa chọn làm dịch vụ này.")
            tai_chinh = await finance_gate.can_start(conn, cid, oid)
            if tai_chinh is None or not tai_chinh.financially_ready:
                raise RoutingFinanceNotReadyError(
                    tai_chinh.reason_code if tai_chinh else None
                )
            flow = await self._luot._lock_flow(conn, cid, vid)
            closed = {
                int(r["round_no"])
                for r in await conn.fetch(
                    "SELECT round_no FROM review_round WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND status = 'closed'",
                    cid,
                    vid,
                )
            }
            giu = rules.routing_hold_block(
                source=o["source"],
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            )
            if giu:
                raise _loi(giu, f"Chưa điều phối được ({giu}).")
            await self._kiem_phong(conn, cid, rid, str(o["node_code"]))

            hien = _routing_hieu_luc(o)
            q = await conn.fetchrow(
                """
                SELECT id::text AS id, status, room_id::text AS room_id
                  FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND reason = 'SERVICE' AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if hien == ASSIGNED and o["room_id"] == rid:
                # Cùng phòng: không đổi gì, không tăng revision, không sự kiện.
                result = self._ket_qua(
                    oid,
                    False,
                    ASSIGNED,
                    rid,
                    int(o["routing_revision"]),
                    q["status"] if q else None,
                    ref,
                )
            else:
                queue_status = await self._xep_hang(conn, cid, vid, oid, rid, q)
                moi = await conn.fetchval(
                    """
                    UPDATE service_order
                       SET routing_status = 'ASSIGNED', room_id = $3::uuid,
                           routing_revision = routing_revision + 1,
                           assigned_by = $4::uuid, assigned_at = now(),
                           -- Hình chiếu cho reader cũ tới Slice 6; sự thật
                           -- routing là routing_status + routing_revision.
                           exec_status = 'assigned',
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    RETURNING routing_revision
                    """,
                    cid,
                    oid,
                    rid,
                    identity.staff_id,
                )
                await self._luot._cap_nhat_vi_tri(conn, cid, vid)
                await record_event(
                    conn,
                    event_type=EVENT_ROUTED,
                    aggregate_type="service_order",
                    aggregate_id=oid,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "visit_id": vid,
                        "from_room_id": o["room_id"] if hien == ASSIGNED else None,
                        "to_room_id": rid,
                        "routing_revision": int(moi),
                        "reason_code": ly_do,
                        "recommendation_ref": ref,
                    },
                )
                result = self._ket_qua(
                    oid, True, ASSIGNED, rid, int(moi), queue_status, ref
                )
            await self._luot._receipt_put(
                conn, identity, ACTION_ASSIGN, key, payload, oid, result
            )
        return result

    async def invalidate(
        self,
        *,
        order_id: Any,
        expected_routing_revision: Any,
        reason_code: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """InvalidateServiceRouting — phân phòng mất hiệu lực TRƯỚC khi bắt đầu."""
        key = _can_khoa(idempotency_key)
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rev = _revision(expected_routing_revision)
        ly_do = _ly_do(reason_code, INVALIDATE_REASONS)
        payload = {
            "order_id": oid,
            "expected_routing_revision": rev,
            "reason_code": ly_do,
        }
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            # Kiểm quyền trong chính giao dịch của lệnh.
            await doi_quyen(
                conn, identity, QUYEN_HUY, cau="Bạn chưa được cấp quyền huỷ xếp phòng."
            )
            vid = await self._luot._visit_of(conn, "service_order", cid, oid)
            await self._luot._lock_visit(conn, cid, vid)
            cached = await self._luot._receipt_get(
                conn, identity, ACTION_INVALIDATE, key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None
            if int(o["routing_revision"]) != rev:
                raise _loi(
                    "ROUTING_REVISION_CONFLICT",
                    "Chỉ định vừa được điều phối bởi người khác — tải lại.",
                )
            hien = _routing_hieu_luc(o)
            if hien == REASSIGNMENT_REQUIRED:
                raise _loi(
                    "ROUTING_ALREADY_INVALIDATED", "Phân phòng này đã mất hiệu lực."
                )
            if hien != ASSIGNED:
                raise _loi("ROUTING_NOT_ASSIGNED", "Chỉ định chưa được xếp phòng.")
            _kiem_thuc_hien(o)
            q = await conn.fetchrow(
                """
                SELECT id::text AS id, status FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND reason = 'SERVICE' AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if q is not None and q["status"] == "serving":
                raise _loi(
                    "SERVICE_ALREADY_IN_PROGRESS",
                    "Khách đang được làm ở phòng — dừng dịch vụ thay vì huỷ phòng.",
                )
            if q is not None:
                # Chỗ chờ ở phòng cũ hết hiệu lực; GIỮ eligible_at để lần xếp
                # lại không đẩy khách xuống cuối hàng.
                await conn.execute(
                    "UPDATE queue_entry SET status = 'cancelled',"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    q["id"],
                )
            moi = await conn.fetchval(
                """
                UPDATE service_order
                   SET routing_status = 'REASSIGNMENT_REQUIRED', room_id = NULL,
                       routing_revision = routing_revision + 1,
                       assigned_by = NULL, assigned_at = NULL,
                       -- Hình chiếu cho reader cũ: chưa có phòng.
                       exec_status = 'authorized',
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                RETURNING routing_revision
                """,
                cid,
                oid,
            )
            await self._luot._cap_nhat_vi_tri(conn, cid, vid)
            # Sổ sự kiện nghiệp vụ, cùng giao dịch: phòng vừa mất thì phải có
            # người xếp lại, và người ấy nhận việc qua đây chứ không qua ai nhớ.
            await emit_event(
                conn,
                ten="service.routing_invalidated",
                clinic_id=cid,
                aggregate_id=oid,
                aggregate_version=int(moi),
                payload=XepPhongDaHuy(
                    visit_id=vid,
                    service_order_id=oid,
                    from_room_id=str(o["room_id"]) if o["room_id"] else None,
                    routing_revision=int(moi),
                    ly_do=ly_do,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type=EVENT_INVALIDATED,
                aggregate_type="service_order",
                aggregate_id=oid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "from_room_id": o["room_id"],
                    "routing_revision": int(moi),
                    "reason_code": ly_do,
                },
            )
            result = {
                "ok": True,
                "order_id": oid,
                "changed": True,
                "routing_status": REASSIGNMENT_REQUIRED,
                "room_id": None,
                "routing_revision": int(moi),
            }
            await self._luot._receipt_put(
                conn, identity, ACTION_INVALIDATE, key, payload, oid, result
            )
        return result

    @staticmethod
    async def _kiem_phong(
        conn: asyncpg.Connection, cid: str, rid: str, node_code: str
    ) -> None:
        r = await conn.fetchrow(
            """
            SELECT r.is_active, r.accepting,
                   EXISTS (SELECT 1 FROM clinic_room_node rn
                            WHERE rn.clinic_id = r.clinic_id AND rn.room_id = r.id
                              AND rn.node_code = $3) AS lam_duoc
              FROM clinic_room r
             WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
               FOR SHARE OF r
            """,
            cid,
            rid,
            node_code,
        )
        if r is None:
            raise _loi("ROOM_NOT_FOUND", "Không tìm thấy phòng này.")
        if not r["is_active"]:
            raise _loi("ROOM_INACTIVE", "Phòng đã ngừng hoạt động.")
        if not r["accepting"]:
            raise _loi("ROOM_NOT_ACCEPTING", "Phòng đang tạm ngừng nhận khách.")
        if not r["lam_duoc"]:
            raise _loi("ROOM_NOT_SERVING_SERVICE", "Phòng này không làm dịch vụ này.")

    @staticmethod
    async def _xep_hang(
        conn: asyncpg.Connection,
        cid: str,
        vid: str,
        oid: str,
        rid: str,
        q: asyncpg.Record | None,
    ) -> str:
        """Đúng MỘT chỗ chờ sống cho chỉ định, ở phòng mới, GIỮ tuổi chờ."""
        if q is not None:
            if q["status"] in ("called", "serving"):
                raise _loi(
                    "ROOM_ALREADY_CALLED",
                    "Phòng hiện tại đã gọi khách vào — không chuyển phòng được nữa.",
                )
            # Đổi phòng tại chỗ: eligible_at / created_at giữ nguyên.
            await conn.execute(
                "UPDATE queue_entry SET room_id = $3::uuid, version = version + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                q["id"],
                rid,
            )
            return str(q["status"])
        busy = await LuotKhamService._visit_busy(conn, cid, vid)
        status = rules.initial_queue_status(visit_busy=busy)
        # Sau khi phân phòng cũ mất hiệu lực, chỗ chờ cũ đã huỷ nhưng giữ mốc
        # bắt đầu chờ — xếp lại phòng thì khách giữ tuổi chờ ấy.
        await conn.execute(
            """
            INSERT INTO queue_entry
                (clinic_id, visit_id, lane, room_id, reason, ref_id, status,
                 eligible_at)
            VALUES ($1::uuid, $2::uuid, 'ROOM', $3::uuid, 'SERVICE', $4::uuid, $5,
                    CASE WHEN $5 = 'waiting' THEN coalesce(
                        (SELECT q.eligible_at FROM queue_entry q
                          WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                            AND q.reason = 'SERVICE' AND q.ref_id = $4::uuid
                            AND q.status = 'cancelled' AND q.eligible_at IS NOT NULL
                          ORDER BY q.updated_at DESC LIMIT 1),
                        now()) END)
            """,
            cid,
            vid,
            rid,
            oid,
            status,
        )
        return status

    @staticmethod
    def _ket_qua(
        oid: str,
        changed: bool,
        routing: str,
        rid: str | None,
        rev: int,
        queue_status: str | None,
        ref: str | None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": True,
            "order_id": oid,
            "changed": changed,
            "routing_status": routing,
            "room_id": rid,
            "routing_revision": rev,
            "queue_status": queue_status,
        }
        if ref is not None:
            out["recommendation_ref"] = ref
        return out
