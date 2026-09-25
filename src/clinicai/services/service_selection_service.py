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
from clinicai.events.catalogue import KhachDaChonDichVu
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.bill_service import THU_CU_KHONG_TRUY_DUOC_SQL
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

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


#: Quyền thật, khai trong `permissions/catalogue.py`, thuộc khối "Khách chọn
#: dịch vụ". Trước đây chỗ này tạm mượn ánh xạ vai của người thu tiền vì mô hình
#: quyền chưa có; nay đã có, nên hỏi thẳng.
QUYEN_CHON_DICH_VU = "service_selection.confirm"


async def can_confirm_service_selection(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> bool:
    """Người này có được xác nhận lựa chọn dịch vụ của khách không?

    Hỏi capability, KHÔNG hỏi vai: quản lý muốn cho ai làm việc này thì tick một
    ô, không cần ai sửa dòng code này.
    """
    return await can(conn, identity, QUYEN_CHON_DICH_VU)


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
    #: Bác sĩ tick "Bắt buộc" (25/09/2026) — quầy không bỏ được.
    bat_buoc: bool = False


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
        if new == NOT_SELECTED and by_id[oid].bat_buoc:
            raise LuotKhamConflictError(
                "SERVICE_REQUIRED",
                "Dịch vụ này bác sĩ đánh dấu bắt buộc — muốn bỏ phải quay lại"
                " người chỉ định.",
            )
        if by_id[oid].selection_status != new:
            changes[oid] = new
    return changes


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------

_ORDERS_SQL = """
SELECT o.id::text AS id, o.exec_status, o.selection_status, o.routing_status,
       o.execution_status, o.version, o.bat_buoc,
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
              -- Đang chờ xác minh hoặc đang PAID. Phiếu đã huỷ không khoá nữa
              -- (Tuyền 24/09/2026: huỷ rồi thu lại / chọn lại được).
              AND c.status IN ('PENDING_VERIFICATION', 'PAID')
       ) AS financially_committed
  FROM service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
 ORDER BY o.id
   FOR UPDATE OF o
"""

#: Tiền dịch vụ cũ không truy được tới từng chỉ định — cùng MỘT luật với
#: Outstanding Bill (``bill_service.THU_CU_KHONG_TRUY_DUOC_SQL``).
_ALLOCATION_UNKNOWN_SQL = THU_CU_KHONG_TRUY_DUOC_SQL


_CHO_QUYET_SQL = """
SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
       o.exec_status, o.selection_status, o.routing_status, o.execution_status,
       o.version, o.mang_tu_visit_id IS NOT NULL AS mang_sang, o.bat_buoc,
       o.node_code, o.phong_du_kien_id::text AS phong_du_kien_id,
       -- Làm bên ngoài (đối tác): quầy nói ra "Đối tác làm" (24/09/2026).
       EXISTS (SELECT 1 FROM node_definition n
                WHERE n.clinic_id = o.clinic_id AND n.code = o.node_code
                  AND n.lam_ben_ngoai) AS doi_tac,
       (SELECT min(pr.unit_price) FROM service_price pr
         WHERE pr.clinic_id = o.clinic_id AND pr.service_code = o.service_code
           AND pr.active AND pr."group" = 'dich_vu') AS gia,
       EXISTS (
           SELECT 1
             FROM payment_bill_line bl
             JOIN payment_cycle c
               ON c.clinic_id = bl.clinic_id
              AND c.payment_cycle_id = bl.payment_cycle_id
            WHERE bl.clinic_id = o.clinic_id
              AND bl.source_type = 'service_order'
              AND bl.source_id = o.id::text
              AND bl.billing_owner = 'CLINIC'
              AND c.status IN ('PENDING_VERIFICATION', 'PAID')
       ) AS financially_committed,
       coalesce(s.revision, 0) AS revision
  FROM service_order o
  LEFT JOIN service_selection_state s
    ON s.clinic_id = o.clinic_id AND s.visit_id = o.visit_id
 WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
 ORDER BY o.created_at, o.id
"""


async def cho_khach_quyet(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Màn thu ngân hỏi: lượt nào còn chỉ định để khách chọn làm hay không.

    CHỈ ĐỌC. Cùng luật khoá với lệnh (``lock_of`` / ``decision_ids``) — màn
    không tự suy "cái nào còn chọn được". Trả, theo lượt: ``revision`` (gửi lại
    đúng số này khi xác nhận) và các chỉ định đang ở giai đoạn khách quyết.
    Lượt không còn gì để quyết thì không có trong kết quả.
    """
    if not visit_ids:
        return {}
    # Phòng chọn được cho từng chỉ định (Tuyền 24/09/2026: quầy chọn phòng khách
    # làm TRƯỚC khi chốt + thu). Đúng tập của dây H4 — cùng cơ sở, còn nhận
    # khách, làm được bước này — xếp theo gợi ý (vắng nhất lên đầu).
    from clinicai.services.service_routing_service import (
        co_so_cua_luot,
        eligible_rooms,
        rank_rooms,
    )

    ten_phong: dict[str, str] = {
        r["id"]: r["name"]
        for r in await conn.fetch(
            "SELECT id::text AS id, name FROM clinic_room"
            " WHERE clinic_id = $1::uuid AND is_active",
            clinic_id,
        )
    }
    phong_theo: dict[tuple[str, str | None, str], list[dict[str, Any]]] = {}

    async def phong_chon_duoc(node: str | None, vid: str) -> list[dict[str, Any]]:
        if not node:
            return []
        co_so = await co_so_cua_luot(conn, clinic_id, visit_id=vid)
        khoa = (node, co_so, vid)
        if khoa not in phong_theo:
            phong_theo[khoa] = [
                {
                    "id": u["room_id"],
                    "ten": ten_phong.get(u["room_id"], "Phòng"),
                    "dang_cho": u["queue_load"],
                }
                for u in rank_rooms(
                    await eligible_rooms(conn, clinic_id, node, co_so, tru_luot=vid)
                )
            ]
        return phong_theo[khoa]

    out: dict[str, dict[str, Any]] = {}
    for r in await conn.fetch(_CHO_QUYET_SQL, clinic_id, visit_ids):
        facts = OrderFacts(
            id=r["id"],
            exec_status=r["exec_status"],
            selection_status=r["selection_status"],
            routing_status=r["routing_status"],
            execution_status=r["execution_status"],
            version=int(r["version"]),
            financially_committed=bool(r["financially_committed"]),
        )
        if not decision_ids([facts]):
            continue
        luot = out.setdefault(
            r["visit_id"], {"revision": int(r["revision"]), "chi_dinh": []}
        )
        luot["chi_dinh"].append(
            {
                "id": r["id"],
                "ten": r["service_name"],
                "selection_status": r["selection_status"],
                "gia": int(r["gia"]) if r["gia"] is not None else None,
                "mang_sang": bool(r["mang_sang"]),
                "bat_buoc": bool(r["bat_buoc"]),
                "phong_du_kien_id": r["phong_du_kien_id"],
                "doi_tac": bool(r["doi_tac"]),
                "phong_chon_duoc": await phong_chon_duoc(r["node_code"], r["visit_id"]),
            }
        )
    return out


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
            # Kiểm quyền trong CHÍNH giao dịch này: quyền vừa bị thu ở lệnh
            # trước thì lệnh này phải thấy ngay.
            await doi_quyen(
                conn,
                identity,
                QUYEN_CHON_DICH_VU,
                cau="Bạn chưa được cấp quyền xác nhận lựa chọn dịch vụ.",
            )
            await khoa_luot(conn, cid, inp.visit_id)
            # Gửi lại trước khi xét revision: lần trước đã commit mà mất phản hồi
            # thì revision nay đã tăng, nhưng gửi lại vẫn phải nhận đúng kết quả.
            cached = await bien_nhan_doc(
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
                    bat_buoc=bool(r["bat_buoc"]),
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
                # Sự kiện NGHIỆP VỤ (không chỉ nhật ký): khối Vòng đọc nghe để
                # chỉ định khách bỏ không giữ vòng đọc lại (24/09/2026).
                await emit_event(
                    conn,
                    ten="service_selection.confirmed",
                    clinic_id=identity.clinic_id,
                    aggregate_id=inp.visit_id,
                    payload=KhachDaChonDichVu(
                        visit_id=inp.visit_id,
                        selection_revision=revision,
                        selected_order_ids=sorted(chosen),
                        not_selected_order_ids=sorted(set(inp.order_ids_seen) - chosen),
                    ),
                    boi=nguoi(identity),
                    correlation_id=inp.visit_id,
                )
            await bien_nhan_ghi(
                conn, identity, ACTION, idempotency_key, payload, inp.visit_id, result
            )
        return result
