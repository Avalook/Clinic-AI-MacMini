"""Service Lifecycle v1 — ConfirmServiceSelection.

Contract: docs/ai/lifecycle-v1/ClinicAI-SELECTION-v1.md (frozen).

Selection chỉ trả lời "trong các chỉ định chính thức khách đang được hỏi, khách
chọn làm dịch vụ nào". Nó không tính tiền, không xếp phòng, không bắt đầu làm,
và không bao giờ xoá chỉ định của bác sĩ: không chọn = ``NOT_SELECTED``.

Phần thuần (``validate_input``, ``classify``, ``plan``) không chạm DB. Lệnh ghi
chạy MỘT transaction theo thứ tự khoá của contract §10: visit → biên nhận →
selection state → các dòng service_order (ORDER BY id) → ghi → sự kiện → biên
nhận. Cùng thứ tự "visit trước" với Payment/Router/Execution nên hai lệnh trên
một lượt luôn nối tiếp nhau.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.luot_kham_service import (
    LuotKhamConflictError,
    LuotKhamService,
    LuotKhamValidationError,
    _uuid,
)
from clinicai.services.payment_service import allowed_kinds

ORIGIN = "api:service-selection"
ACTION = "service_selection.confirm"
EVENT = "service_selection.confirmed"

PENDING = "PENDING"
SELECTED = "SELECTED"
NOT_SELECTED = "NOT_SELECTED"

#: Trần số chỉ định một lần xác nhận — chặn thân yêu cầu phình to; một lượt
#: khám thật chỉ có vài chỉ định.
MAX_ORDERS = 100

#: Trạng thái cũ (``exec_status``) đã sang bước thực hiện hoặc đã kết thúc.
_LEGACY_EXECUTION_LOCK = frozenset(
    {"in_progress", "performed", "not_performed", "cancelled"}
)


# ---------------------------------------------------------------------------
# Quyền — capability seam
# ---------------------------------------------------------------------------


def can_confirm_service_selection(identity: StaffIdentity) -> bool:
    """Capability ``service.selection.confirm``.

    OPEN (SELECTION §14): ánh xạ vai cuối cùng chưa chốt. Tạm dùng ĐÚNG ánh xạ
    đang có của người thu tiền dịch vụ (``allowed_kinds``) — lựa chọn của khách
    hôm nay được ghi nhận ở quầy thu dịch vụ — chứ không đặt vai mới. Khi có
    checkpoint quyền, chỉ đổi hàm này.
    """
    return any("dich_vu" in allowed_kinds(v) for v in identity.cac_vai())


# ---------------------------------------------------------------------------
# Phần thuần
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionInput:
    visit_id: str
    order_ids_seen: tuple[str, ...]
    selected_order_ids: tuple[str, ...]
    expected_selection_revision: int

    def payload(self) -> dict[str, Any]:
        """Payload chuẩn để băm (§7): danh sách đã sắp — thứ tự không phải ý định."""
        return {
            "visit_id": self.visit_id,
            "expected_selection_revision": self.expected_selection_revision,
            "order_ids_seen": sorted(self.order_ids_seen),
            "selected_order_ids": sorted(self.selected_order_ids),
        }


def validate_input(
    *,
    visit_id: Any,
    order_ids_seen: Any,
    selected_order_ids: Any,
    expected_selection_revision: Any,
    idempotency_key: str | None,
) -> SelectionInput:
    if not idempotency_key:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Thiếu Idempotency-Key."
        )
    if not 8 <= len(idempotency_key) <= 200:
        raise LuotKhamValidationError(
            "IDEMPOTENCY_KEY_REQUIRED", "Khoá gửi lại phải dài từ 8 đến 200 ký tự."
        )
    vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
    if type(expected_selection_revision) is not int or expected_selection_revision < 0:
        raise LuotKhamValidationError(
            "SELECTION_REVISION_CONFLICT",
            "expected_selection_revision phải là số nguyên không âm.",
        )
    if not isinstance(order_ids_seen, list) or not isinstance(selected_order_ids, list):
        raise LuotKhamValidationError(
            "SELECTION_ORDER_SET_CHANGED", "Danh sách chỉ định không hợp lệ."
        )
    if len(order_ids_seen) > MAX_ORDERS:
        raise LuotKhamValidationError(
            "SELECTION_ORDER_SET_CHANGED",
            f"Tối đa {MAX_ORDERS} chỉ định một lần xác nhận.",
        )
    seen = [_uuid(x, "Mã chỉ định không hợp lệ.") for x in order_ids_seen]
    selected = [_uuid(x, "Mã chỉ định không hợp lệ.") for x in selected_order_ids]
    # Không tự bỏ trùng (§5): trùng là client đang gửi sai, không phải ý định.
    if len(set(seen)) != len(seen) or len(set(selected)) != len(selected):
        raise LuotKhamValidationError(
            "SELECTION_DUPLICATE_ORDER_ID", "Danh sách có mã chỉ định lặp lại."
        )
    if not set(selected) <= set(seen):
        raise LuotKhamValidationError(
            "SELECTION_SELECTED_NOT_IN_SEEN",
            "Có dịch vụ được chọn nằm ngoài danh sách đang hỏi khách.",
        )
    return SelectionInput(
        vid, tuple(seen), tuple(selected), expected_selection_revision
    )


@dataclass(frozen=True)
class OrderFacts:
    id: str
    exec_status: str
    selection_status: str | None
    routing_status: str | None
    execution_status: str | None
    version: int
    financially_committed: bool


def lock_of(o: OrderFacts) -> str | None:
    """Mã khoá sửa lựa chọn của một chỉ định, hoặc None nếu còn quyết được."""
    if (o.execution_status not in (None, PENDING)) or (
        o.exec_status in _LEGACY_EXECUTION_LOCK
    ):
        return "SELECTION_EXECUTION_LOCKED"
    # Dòng cũ đã "assigned" cũng là đã xếp phòng: Selection không tự tháo (§8).
    if o.routing_status in ("ASSIGNED", "REASSIGNMENT_REQUIRED") or (
        o.exec_status == "assigned"
    ):
        return "SELECTION_ROUTING_LOCKED"
    if o.financially_committed:
        return "SELECTION_FINANCIAL_LOCKED"
    return None


def decision_ids(orders: list[OrderFacts]) -> set[str]:
    """Chỉ định còn ở giai đoạn khách quyết (§8). Nháp không phải chỉ định."""
    return {o.id for o in orders if o.exec_status == "authorized" and not lock_of(o)}


_LOCK_MESSAGES = {
    "SELECTION_EXECUTION_LOCKED": "Dịch vụ đã bắt đầu hoặc đã kết thúc.",
    "SELECTION_ROUTING_LOCKED": "Dịch vụ đã được xếp phòng.",
    "SELECTION_FINANCIAL_LOCKED": (
        "Dịch vụ đã có lần thu tiền — bỏ dịch vụ phải đi luồng tài chính."
    ),
}


def classify(
    inp: SelectionInput, orders: list[OrderFacts], allocation_unknown: bool
) -> None:
    """Ném đúng một lỗi ổn định nếu lần xác nhận này không được phép.

    Thứ tự: khoá cụ thể của chỉ định khách đã thấy trước (cho người dùng biết
    VÌ SAO), rồi tiền cũ không truy được tới chỉ định, rồi tập đã đổi.
    """
    by_id = {o.id: o for o in orders}
    locks = [lock_of(by_id[i]) for i in inp.order_ids_seen if i in by_id]
    for code in (
        "SELECTION_EXECUTION_LOCKED",
        "SELECTION_ROUTING_LOCKED",
        "SELECTION_FINANCIAL_LOCKED",
    ):
        if code in locks:
            raise LuotKhamConflictError(code, _LOCK_MESSAGES[code])
    if allocation_unknown:
        raise LuotKhamConflictError(
            "SELECTION_PAYMENT_ALLOCATION_UNKNOWN",
            "Lượt này có lần thu dịch vụ cũ không truy được tới từng chỉ định"
            " — cần đối soát tài chính trước.",
        )
    current = decision_ids(orders)
    if set(inp.order_ids_seen) != current:
        raise LuotKhamConflictError(
            "SELECTION_ORDER_SET_CHANGED",
            "Danh sách chỉ định vừa thay đổi — tải lại rồi hỏi khách lại.",
        )
    if not current:
        raise LuotKhamConflictError(
            "NO_SELECTABLE_ORDERS", "Lượt này không có chỉ định nào để khách chọn."
        )


def plan(inp: SelectionInput, orders: list[OrderFacts]) -> dict[str, str]:
    """Trạng thái mới của các chỉ định THỰC SỰ đổi: id → SELECTED/NOT_SELECTED."""
    by_id = {o.id: o for o in orders}
    chosen = set(inp.selected_order_ids)
    changes: dict[str, str] = {}
    for oid in inp.order_ids_seen:
        new = SELECTED if oid in chosen else NOT_SELECTED
        if by_id[oid].selection_status != new:
            changes[oid] = new
    return changes


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------

_ORDERS_SQL = """
SELECT o.id::text AS id, o.exec_status, o.selection_status, o.routing_status,
       o.execution_status, o.version,
       EXISTS (
           SELECT 1
             FROM payment_bill_line bl
             JOIN payment_cycle c
               ON c.clinic_id = bl.clinic_id
              AND c.payment_cycle_id = bl.payment_cycle_id
            WHERE bl.clinic_id = o.clinic_id
              AND bl.source_type = 'service_order'
              AND bl.source_id = o.id::text
              -- Chỉ dòng PHÒNG KHÁM thu mới là cam kết tài chính của phòng khám.
              -- Ảnh chụp hoá đơn lưu cả dòng đối tác tự thu (không cộng vào tổng
              -- tiền phòng khám) — lần thu của phòng khám không khoá dịch vụ đó.
              AND bl.billing_owner = 'CLINIC'
              -- Đang chờ xác minh, hoặc ĐÃ TỪNG nhận tiền (kể cả nay VOIDED).
              -- Lần chờ đã huỷ mà chưa từng nhận tiền thì không khoá.
              AND (c.status = 'PENDING_VERIFICATION' OR c.paid_at IS NOT NULL)
       ) AS financially_committed
  FROM service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
 ORDER BY o.id
   FOR UPDATE OF o
"""

#: Tiền dịch vụ của lượt mà KHÔNG truy được tới từng chỉ định: lần thu đang chờ
#: hoặc đã từng nhận tiền nhưng không có dòng hoá đơn nào, hoặc dòng ``payment``
#: dịch vụ không trỏ tới lần thu có dòng hoá đơn. Không suy phân bổ từ số tiền,
#: exec_status, phòng hay hình chiếu payment (SELECTION §9).
_ALLOCATION_UNKNOWN_SQL = """
SELECT EXISTS (
           SELECT 1 FROM payment_cycle c
            WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
              AND c.kind = 'dich_vu'
              AND (c.status = 'PENDING_VERIFICATION' OR c.paid_at IS NOT NULL)
              AND NOT EXISTS (
                  SELECT 1 FROM payment_bill_line bl
                   WHERE bl.clinic_id = c.clinic_id
                     AND bl.payment_cycle_id = c.payment_cycle_id))
    OR EXISTS (
           SELECT 1 FROM payment p
            WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid
              AND p.kind = 'dich_vu'
              AND NOT EXISTS (
                  SELECT 1 FROM payment_bill_line bl
                   WHERE bl.clinic_id = p.clinic_id
                     AND bl.payment_cycle_id = p.payment_cycle_id))
"""


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


class ServiceSelectionService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def confirm(
        self,
        *,
        visit_id: Any,
        order_ids_seen: Any,
        selected_order_ids: Any,
        expected_selection_revision: Any,
        identity: StaffIdentity,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        if not can_confirm_service_selection(identity):
            raise SafetyGateError("Vai trò của bạn không xác nhận lựa chọn dịch vụ.")
        inp = validate_input(
            visit_id=visit_id,
            order_ids_seen=order_ids_seen,
            selected_order_ids=selected_order_ids,
            expected_selection_revision=expected_selection_revision,
            idempotency_key=idempotency_key,
        )
        payload = inp.payload()
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await LuotKhamService._lock_visit(conn, cid, inp.visit_id)
            # Gửi lại trước khi xét revision: lần trước đã commit mà mất phản hồi
            # thì revision nay đã tăng, nhưng gửi lại vẫn phải nhận đúng kết quả.
            cached = await LuotKhamService._receipt_get(
                conn, identity, ACTION, idempotency_key, payload
            )
            if cached is not None:
                return cached
            state = await conn.fetchrow(
                "SELECT revision, confirmed_by::text AS confirmed_by, confirmed_at"
                "  FROM service_selection_state"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
                cid,
                inp.visit_id,
            )
            revision = int(state["revision"]) if state else 0
            if inp.expected_selection_revision != revision:
                raise LuotKhamConflictError(
                    "SELECTION_REVISION_CONFLICT",
                    "Lựa chọn dịch vụ vừa được người khác xác nhận — tải lại.",
                )
            orders = [
                OrderFacts(
                    id=r["id"],
                    exec_status=r["exec_status"],
                    selection_status=r["selection_status"],
                    routing_status=r["routing_status"],
                    execution_status=r["execution_status"],
                    version=int(r["version"]),
                    financially_committed=bool(r["financially_committed"]),
                )
                for r in await conn.fetch(_ORDERS_SQL, cid, inp.visit_id)
            ]
            unknown = bool(
                await conn.fetchval(_ALLOCATION_UNKNOWN_SQL, cid, inp.visit_id)
            )
            classify(inp, orders, unknown)
            changes = plan(inp, orders)
            versions = {o.id: o.version for o in orders}
            confirmed_by = state["confirmed_by"] if state else None
            confirmed_at = state["confirmed_at"] if state else None
            if changes:
                ids = sorted(changes)
                for r in await conn.fetch(
                    """
                    UPDATE service_order o
                       SET selection_status = c.status, version = o.version + 1,
                           updated_at = now()
                      FROM unnest($3::uuid[], $4::text[]) AS c(id, status)
                     WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                       AND o.id = c.id
                    RETURNING o.id::text AS id, o.version
                    """,
                    cid,
                    inp.visit_id,
                    ids,
                    [changes[i] for i in ids],
                ):
                    versions[r["id"]] = int(r["version"])
                row = await conn.fetchrow(
                    """
                    INSERT INTO service_selection_state
                        (clinic_id, visit_id, revision, confirmed_by, confirmed_at)
                    VALUES ($1::uuid, $2::uuid, 1, $3::uuid, now())
                    ON CONFLICT (clinic_id, visit_id) DO UPDATE
                       SET revision = service_selection_state.revision + 1,
                           confirmed_by = EXCLUDED.confirmed_by,
                           confirmed_at = EXCLUDED.confirmed_at,
                           updated_at = now()
                    RETURNING revision, confirmed_by::text AS confirmed_by,
                              confirmed_at
                    """,
                    cid,
                    inp.visit_id,
                    identity.staff_id,
                )
                assert row is not None
                revision = int(row["revision"])
                confirmed_by = row["confirmed_by"]
                confirmed_at = row["confirmed_at"]
            chosen = set(inp.selected_order_ids)
            result = {
                "ok": True,
                "visit_id": inp.visit_id,
                "changed": bool(changes),
                "selection_revision": revision,
                "selected_order_ids": sorted(chosen),
                "not_selected_order_ids": sorted(set(inp.order_ids_seen) - chosen),
                "changed_order_ids": sorted(changes),
                "order_versions": {i: versions[i] for i in sorted(inp.order_ids_seen)},
                "confirmed_at": _iso(confirmed_at),
                "confirmed_by": confirmed_by,
            }
            if changes:
                await record_event(
                    conn,
                    event_type=EVENT,
                    aggregate_type="visit",
                    aggregate_id=inp.visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "selection_revision": revision,
                        "selected_order_ids": result["selected_order_ids"],
                        "not_selected_order_ids": result["not_selected_order_ids"],
                        "changed_order_ids": result["changed_order_ids"],
                    },
                )
            await LuotKhamService._receipt_put(
                conn, identity, ACTION, idempotency_key, payload, inp.visit_id, result
            )
        return result
