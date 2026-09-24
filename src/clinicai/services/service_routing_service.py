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

from clinicai.api.identity import StaffIdentity, danh_tinh_nhan_vien
from clinicai.events.catalogue import DaXepPhong, XepPhongDaHuy
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services import finance_gate
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import cap_nhat_vi_tri, khach_dang_duoc_phuc_vu
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_flow,
    khoa_luot,
    luot_cua,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

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
   -- CÙNG CƠ SỞ với lượt khám (24/09/2026): phòng khám có nhiều cơ sở thì
   -- khách ở Kim Ngưu không được xếp sang phòng Hào Nam. Trước đây câu này
   -- không lọc cơ sở — bộ mô phỏng ngày khám bắt được một xét nghiệm máu bị xếp
   -- sang phòng lấy mẫu của cơ sở khác.
   AND ($3::uuid IS NULL OR r.location_id = $3::uuid)
"""


async def co_so_cua_luot(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    visit_id: str | None = None,
    order_id: str | None = None,
) -> str | None:
    """Cơ sở (clinic_location) nơi khách đang khám — theo lượt hoặc theo chỉ định.

    `visit.location_id` chỉ được ghi từ 24/09/2026; lượt cũ rơi về cơ sở của
    lịch hẹn."""
    if order_id is not None:
        v = await conn.fetchval(
            "SELECT coalesce(v.location_id, a.location_id)::text"
            " FROM service_order o JOIN visit v"
            " ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
            " LEFT JOIN appointment a"
            " ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
            clinic_id,
            order_id,
        )
        return str(v) if v else None
    if visit_id is not None:
        v = await conn.fetchval(
            "SELECT coalesce(v.location_id, a.location_id)::text FROM visit v"
            " LEFT JOIN appointment a"
            " ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id"
            " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid",
            clinic_id,
            visit_id,
        )
        return str(v) if v else None
    return None


@dataclass(frozen=True)
class RoomCandidate:
    room_id: str
    code: str
    sort: int
    co_nguoi_truc: bool
    tai: int


async def eligible_rooms(
    conn: asyncpg.Connection,
    clinic_id: str,
    node_code: str,
    location_id: str | None = None,
) -> list[RoomCandidate]:
    """EligibleRoomQuery — tập phòng hợp lệ của một node, một truy vấn.

    `location_id` = cơ sở của lượt khám; truyền vào thì chỉ lấy phòng cùng cơ
    sở (None = không lọc — chỉ dùng cho màn cấu hình)."""
    return [
        RoomCandidate(
            room_id=r["room_id"],
            code=r["code"],
            sort=int(r["sort"]),
            co_nguoi_truc=bool(r["co_nguoi_truc"]),
            tai=int(r["tai"]),
        )
        for r in await conn.fetch(_ELIGIBLE_SQL, clinic_id, node_code, location_id)
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
# Đọc: chỉ định ĐÃ TRẢ TIỀN chờ vào phòng (Tuyền 24/09/2026)
# ---------------------------------------------------------------------------
#
# "Thanh toán xong vẫn chỉ định [phòng] được bình thường" + "kể cả lễ tân không
# chỉ định thì khách vẫn xuất hiện ở hàng đợi và có thể khám ở các dịch vụ khả
# thi". Hai câu đọc dưới cùng MỘT điều kiện "đã trả, khách làm, chưa bắt đầu";
# xếp / đổi phòng vẫn đi qua lệnh `assign` (quyền, cổng tiền, revision, cơ sở).

_DA_TRA_CHUA_LAM = """
       o.selection_status = 'SELECTED'
   AND o.exec_status IN ('authorized', 'assigned')
   AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
   AND v.status IN ('OPEN', 'IN_PROGRESS')
   -- Đối tác tự lấy mẫu: khách không vào phòng nào của phòng khám.
   AND NOT EXISTS (
       SELECT 1 FROM service_price sp
        WHERE sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
          AND sp.doi_tac_lay_mau)
   -- Phòng đã gọi / đang làm thì không đổi được nữa (lệnh cũng từ chối).
   AND NOT EXISTS (
       SELECT 1 FROM queue_entry q
        WHERE q.clinic_id = o.clinic_id AND q.reason = 'SERVICE'
          AND q.ref_id = o.id AND q.status IN ('called', 'serving'))
"""


async def _loc_da_tra(
    conn: asyncpg.Connection, clinic_id: str, rows: Sequence[asyncpg.Record]
) -> list[asyncpg.Record]:
    tai_chinh = await finance_gate.states_for_orders(
        conn, clinic_id, [r["id"] for r in rows]
    )
    return [
        r
        for r in rows
        if (q := tai_chinh.get(r["id"])) is not None and q.financially_ready
    ]


async def da_tra_cho_vao_phong(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Quầy thu: theo lượt, chỉ định đã trả chưa bắt đầu + phòng hiện tại —
    để lễ tân xếp / đổi phòng SAU khi thu (trước: thu xong là mất chỗ chọn)."""
    if not visit_ids:
        return {}
    rows = await conn.fetch(
        f"""
        SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
               o.routing_revision, o.room_id::text AS room_id, r.name AS phong,
               coalesce(o.routing_status, 'UNASSIGNED') AS routing_status
          FROM service_order o
          JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
          LEFT JOIN clinic_room r ON r.id = o.room_id AND r.clinic_id = o.clinic_id
         WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
           AND {_DA_TRA_CHUA_LAM}
         ORDER BY o.created_at, o.id
        """,
        clinic_id,
        visit_ids,
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for r in await _loc_da_tra(conn, clinic_id, rows):
        out.setdefault(r["visit_id"], []).append(
            {
                "id": r["id"],
                "ten": r["service_name"],
                "room_id": r["room_id"] if r["routing_status"] == ASSIGNED else None,
                "phong": r["phong"] if r["routing_status"] == ASSIGNED else None,
                "routing_revision": int(r["routing_revision"]),
            }
        )
    return out


async def cho_nhan_vao_phong(
    conn: asyncpg.Connection, clinic_id: str, room_id: str
) -> list[dict[str, Any]]:
    """Phòng: khách ĐÃ TRẢ mà CHƯA XẾP PHÒNG, phòng này làm được, cùng cơ sở —
    hiện ở MỌI phòng như vậy để phòng nào rảnh bấm nhận (không để khách kẹt khi
    người thu không xếp, hay dây H4 không tự xếp được)."""
    rows = await conn.fetch(
        f"""
        SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
               o.routing_revision, p.full_name, p.patient_code,
               v.checked_in_at
          FROM clinic_room pr
          JOIN clinic_room_node rn
            ON rn.room_id = pr.id AND rn.clinic_id = pr.clinic_id
          JOIN service_order o
            ON o.clinic_id = pr.clinic_id AND o.node_code = rn.node_code
          JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
          JOIN patient p ON p.clinic_patient_id = v.clinic_patient_id
          LEFT JOIN appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
         WHERE pr.clinic_id = $1::uuid AND pr.id = $2::uuid
           AND pr.is_active AND pr.accepting AND NOT pr.la_doi_tac
           AND coalesce(o.routing_status, 'UNASSIGNED') = 'UNASSIGNED'
           AND (pr.location_id IS NULL
                OR coalesce(v.location_id, a.location_id) IS NULL
                OR pr.location_id = coalesce(v.location_id, a.location_id))
           AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
               = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           AND {_DA_TRA_CHUA_LAM}
         ORDER BY v.checked_in_at, o.created_at, o.id
        """,
        clinic_id,
        room_id,
    )
    return [
        {
            "id": r["id"],
            "visit_id": r["visit_id"],
            "ten": r["service_name"],
            "khach": r["full_name"],
            "ma_khach": r["patient_code"],
            "routing_revision": int(r["routing_revision"]),
        }
        for r in await _loc_da_tra(conn, clinic_id, rows)
    ]


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
            ung_vien = rank_rooms(
                await eligible_rooms(
                    conn, cid, str(node), await co_so_cua_luot(conn, cid, order_id=oid)
                )
            )
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
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(conn, identity, ACTION_ASSIGN, key, payload)
            if cached is not None:
                return cached
            result = await self._gan(
                conn,
                identity,
                vid=vid,
                oid=oid,
                rid=rid,
                rev=rev,
                ly_do=ly_do,
                ref=ref,
                tu_dong=False,
            )
            await bien_nhan_ghi(
                conn, identity, ACTION_ASSIGN, key, payload, oid, result
            )
        return result

    async def _gan(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        rid: str,
        rev: int,
        ly_do: str,
        ref: str | None,
        tu_dong: bool,
    ) -> dict[str, Any]:
        """Lõi AssignServiceRoom — người gọi đã kiểm quyền và khoá lượt.

        Người bấm (``assign``) và khối Hành trình (``tu_xep_da_thu``, dây H4) đi
        CHUNG đường này: cùng mọi điều kiện, cùng một sự kiện. Không có lối tắt
        "hệ thống được xếp bừa".
        """
        cid = identity.clinic_id
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
        flow = await khoa_flow(conn, cid, vid)
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
        await self._kiem_phong(
            conn,
            cid,
            rid,
            str(o["node_code"]),
            await co_so_cua_luot(conn, cid, visit_id=vid),
        )

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
            return self._ket_qua(
                oid,
                False,
                ASSIGNED,
                rid,
                int(o["routing_revision"]),
                q["status"] if q else None,
                ref,
            )
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
        await cap_nhat_vi_tri(conn, cid, vid)
        tu_phong = o["room_id"] if hien == ASSIGNED else None
        # Sổ sự kiện nghiệp vụ (dòng thời gian, bảng hành trình) — cùng giao
        # dịch với việc xếp. Người gây ra là người bấm, hoặc người vừa thu tiền
        # khi khối Hành trình xếp thay (tu_dong).
        await emit_event(
            conn,
            ten="service.routed",
            clinic_id=cid,
            aggregate_id=oid,
            so_ke_tiep=True,
            payload=DaXepPhong(
                visit_id=vid,
                service_order_id=oid,
                room_id=rid,
                from_room_id=str(tu_phong) if tu_phong else None,
                routing_revision=int(moi),
                ly_do=ly_do,
                tu_dong=tu_dong,
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
        await record_event(
            conn,
            event_type=EVENT_ROUTED,
            aggregate_type="service_order",
            aggregate_id=oid,
            identity=identity,
            origin=ORIGIN,
            payload={
                "visit_id": vid,
                "from_room_id": tu_phong,
                "to_room_id": rid,
                "routing_revision": int(moi),
                "reason_code": ly_do,
                "recommendation_ref": ref,
            },
        )
        return self._ket_qua(oid, True, ASSIGNED, rid, int(moi), queue_status, ref)

    async def tu_xep_da_thu(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        staff_id: str | None,
        causation_id: str,
    ) -> list[str]:
        """Dây H4: tiền dịch vụ đã nhận → xếp phòng vắng nhất THAY người vừa thu.

        Tuyền chốt 24/09/2026: "thu tiền xong → hệ thống xếp phòng thay cho người
        vừa thu tiền, dùng quyền của người ấy; ai có quyền điều phối đổi lại
        được, lần sau đè lần trước".

        Chỉ xếp chỉ định CHƯA có phòng (UNASSIGNED). Phòng cũ bị huỷ
        (REASSIGNMENT_REQUIRED) là việc của một NGƯỜI — đã có việc
        OPS-ROUTING-REASSIGN, không tự đẩy khách sang phòng khác (ChatGPT tin
        112). Người thu không có quyền xếp phòng, hay không phòng nào làm được →
        để nguyên, người có quyền xếp tay. Không bao giờ ném lỗi làm hỏng việc
        giao tin: mỗi chỉ định một điểm lưu (savepoint), hỏng cái nào bỏ cái ấy.

        Trả mã các chỉ định đã xếp. Chạy lại được: chỉ định đã có phòng thì bỏ.
        """
        if not staff_id:
            return []
        nguoi_thu = await danh_tinh_nhan_vien(
            conn, clinic_id=clinic_id, staff_id=staff_id
        )
        if nguoi_thu is None or not await can(conn, nguoi_thu, QUYEN_XEP):
            return []
        # Khoá lượt như mọi lệnh điều phối. Lượt đã đóng / khách đã về thì
        # thôi — không ném lỗi (ném là người đưa tin thử lại mãi một việc vô
        # nghĩa); chỉ định đã trả mà chưa làm sẽ được mang sang lượt sau (H2).
        trang_thai = await conn.fetchval(
            "SELECT status FROM visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            clinic_id,
            visit_id,
        )
        # INCOMPLETE (khách bỏ về) / FINALIZED / AMENDED: không xếp phòng.
        if trang_thai not in ("OPEN", "IN_PROGRESS"):
            return []
        orders = await conn.fetch(
            """
            SELECT o.id::text AS id, o.node_code, o.routing_revision,
                   o.phong_du_kien_id::text AS phong_du_kien
              FROM service_order o
             WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
               AND o.selection_status = 'SELECTED'
               AND coalesce(o.routing_status, 'UNASSIGNED') = 'UNASSIGNED'
               AND o.exec_status = 'authorized'
               AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
               -- Đối tác tự lấy mẫu: khách không xếp hàng ở phòng nào của
               -- phòng khám (cùng luật với _tu_xep_phong cũ).
               AND NOT EXISTS (
                   SELECT 1 FROM service_price sp
                    WHERE sp.clinic_id = o.clinic_id
                      AND sp.service_code = o.service_code
                      AND sp.doi_tac_lay_mau)
             ORDER BY o.created_at, o.id
            """,
            clinic_id,
            visit_id,
        )
        tai_chinh = await finance_gate.states_for_orders(
            conn, clinic_id, [o["id"] for o in orders]
        )
        da_xep: list[str] = []
        co_so = await co_so_cua_luot(conn, clinic_id, visit_id=visit_id)
        for o in orders:
            quyet = tai_chinh.get(o["id"])
            if quyet is None or not quyet.financially_ready:
                continue
            ung_vien = rank_rooms(
                await eligible_rooms(conn, clinic_id, o["node_code"], co_so)
            )
            if not ung_vien:
                continue
            # Phòng khách chọn ở quầy (phong_du_kien) thắng — nếu nó vẫn đủ điều
            # kiện (đúng cơ sở, còn nhận khách, làm được bước này). Không thì
            # phòng vắng nhất như cũ: ý định cũ không được làm khách kẹt.
            chon = next(
                (u for u in ung_vien if u["room_id"] == o["phong_du_kien"]),
                ung_vien[0],
            )
            try:
                async with conn.transaction():
                    kq = await self._gan(
                        conn,
                        nguoi_thu,
                        vid=visit_id,
                        oid=o["id"],
                        rid=chon["room_id"],
                        rev=int(o["routing_revision"]),
                        ly_do="INITIAL_ASSIGNMENT",
                        ref=f"{ADVISOR}:hanh-trinh:{causation_id}",
                        tu_dong=True,
                    )
            except LuotKhamConflictError:
                continue
            if kq["changed"]:
                da_xep.append(o["id"])
        return da_xep

    async def dat_phong_du_kien(
        self,
        *,
        order_id: Any,
        room_id: Any,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """PlanServiceRoom — ghi phòng khách sẽ làm, TRƯỚC khi thu tiền.

        Không xếp phòng chính thức (FinanceGate chặn khi chưa trả tiền), không
        vào hàng chờ phòng: chỉ là ý định cho dây H4 dùng khi thu xong. Cùng
        quyền với xếp phòng. ``room_id`` rỗng = bỏ chọn (để hệ thống tự chọn).
        """
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = (
            None if room_id in (None, "") else _uuid(room_id, "Mã phòng không hợp lệ.")
        )
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn chưa được cấp quyền xếp phòng."
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            o = await conn.fetchrow(_ORDER_SQL, cid, oid)
            assert o is not None
            if o["exec_status"] in ("draft", "cancelled"):
                raise _loi("SERVICE_ROUTING_NOT_ALLOWED", "Chỉ định đã huỷ.")
            _kiem_thuc_hien(o)
            if _routing_hieu_luc(o) == "ASSIGNED":
                raise _loi(
                    "ROUTING_ALREADY_ASSIGNED",
                    "Chỉ định đã được xếp phòng — đổi phòng ở Điều phối.",
                )
            if rid is not None:
                await self._kiem_phong(
                    conn,
                    cid,
                    rid,
                    str(o["node_code"]),
                    await co_so_cua_luot(conn, cid, visit_id=vid),
                )
            await conn.execute(
                "UPDATE service_order SET phong_du_kien_id = $3::uuid"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
                rid,
            )
        return {"ok": True, "order_id": oid, "phong_du_kien_id": rid}

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
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(
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
            await cap_nhat_vi_tri(conn, cid, vid)
            # Sổ sự kiện nghiệp vụ, cùng giao dịch: phòng vừa mất thì phải có
            # người xếp lại, và người ấy nhận việc qua đây chứ không qua ai nhớ.
            await emit_event(
                conn,
                ten="service.routing_invalidated",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
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
            await bien_nhan_ghi(
                conn, identity, ACTION_INVALIDATE, key, payload, oid, result
            )
        return result

    @staticmethod
    async def _kiem_phong(
        conn: asyncpg.Connection,
        cid: str,
        rid: str,
        node_code: str,
        co_so: str | None = None,
    ) -> None:
        r = await conn.fetchrow(
            """
            SELECT r.is_active, r.accepting, r.location_id::text AS location_id,
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
        if co_so and r["location_id"] and r["location_id"] != co_so:
            raise _loi(
                "ROOM_OTHER_LOCATION",
                "Phòng này ở cơ sở khác với nơi khách đang khám.",
            )

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
        busy = await khach_dang_duoc_phuc_vu(conn, cid, vid)
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
