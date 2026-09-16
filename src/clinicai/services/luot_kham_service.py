"""Luồng khám lát 1 — lệnh và bảng làm việc.

Contract: demo-clinicai/docs/handoff/DANH-GIA-THIET-KE-CLAUDE-20260911-v2.md §3.

Luật QUYẾT nằm ở ``luot_kham_rules`` (thuần, test không cần database). File này
đọc, khoá, gọi luật, rồi ghi. Mỗi lệnh chạy trong MỘT transaction và khoá dòng
``visit`` đầu tiên: hai lệnh trên cùng một lượt khám luôn chạy nối tiếp, và thứ
tự khoá cố định (visit → dòng của lệnh) nên không có deadlock chéo.

BIÊN NHẬN NẰM TRONG CÙNG TRANSACTION. Khoá gửi lại (Idempotency-Key) được giữ
bằng advisory lock theo (phòng khám, người gọi, lệnh, khoá), đọc biên nhận, làm
việc, ghi biên nhận, commit — tất cả một lần. Chết giữa chừng thì cả việc lẫn
biên nhận cùng mất; gửi lại thì làm lại từ đầu, không có khoảng hở "đã commit
mà chưa lưu biên nhận" như ``api/idempotency.py`` (S6).

GIỚI HẠN CỦA LÁT 1, nói rõ:
  * Chưa có kết quả theo phiên bản, nên yêu cầu "có kết quả hợp lệ" bị từ chối
    thay vì để vòng đọc kẹt mãi — chỉ nhận "đã làm".
  * Chưa có nhánh kế hoạch trước, huỷ/miễn yêu cầu, rời tạm.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import (
    VAI_LAM_VIEC,
    ClinicRole,
    StaffIdentity,
    mo_quyen_tam_thoi,
)
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

logger = structlog.get_logger()

ORIGIN = "api:luot-kham"

BOARD_ROLES = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)
CHECKIN_ROLES = frozenset({ClinicRole.RECEPTION, ClinicRole.MANAGEMENT})
VITALS_ROLES = frozenset(
    {ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION, ClinicRole.DOCTOR}
)
DOCTOR_ROLES = frozenset({ClinicRole.DOCTOR})
#: Bấm "Bắt đầu khám" / "Đã khám xong" — bác sĩ, hoặc thư ký đi kèm bác sĩ ấy
#: (Tuyền 16/09/2026: *"check-in check-out cho khách ở từng phòng sẽ do thư ký
#: đi kèm bác sĩ hoặc bác sĩ làm"*). DUYỆT chỉ định vẫn chỉ bác sĩ.
CONSULT_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
NOTE_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
DRAFT_ROLES = frozenset({ClinicRole.TKYK})
DISPATCH_ROLES = frozenset({ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT})
#: Duyệt kết quả + cho phép gửi (Notion v1.0.0: bác sĩ chính & bác sĩ siêu âm/xét
#: nghiệm). Không nới theo công tắc — đây là quyết định chuyên môn.
REVIEW_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
PERFORMER_ROLES = frozenset(
    {
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
    }
)
#: NGƯỜI ĐI KÈM Ở PHÒNG DỊCH VỤ (Tuyền 17/09/2026): điều dưỡng hoặc thư ký đi
#: cùng bác sĩ thủ thuật / siêu âm GỌI khách, CHECK-IN (Bắt đầu) và CHECK-OUT
#: (Xong) — y như ở bàn khám bác sĩ chính. Chuyên môn vẫn là của bác sĩ: node
#: giữ actor_roles = DOCTOR, và bác sĩ bấm Xong thì được ghi là người thực hiện.
HO_TRO_PHONG = frozenset({ClinicRole.NURSE_ULTRASOUND, ClinicRole.TKYK})
# Ai đọc được nội dung khám (ghi chú, kết quả). Lễ tân và trưởng ca làm việc
# với trạng thái, không cần đọc chữ bác sĩ viết.
CLINICAL_READ_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
    }
)

_CAU_CHAN_DIEU_PHOI = {
    "NO_VALID_ORDER": "Chỉ định này chưa được bác sĩ duyệt — chưa điều phối được.",
    "ORDER_NOT_DISPATCHABLE": "Chỉ định này không còn ở trạng thái điều phối được.",
    "PLAN_NOT_APPLIED": "Kế hoạch trước chưa được áp hợp lệ cho lượt khám này.",
    "VITALS_REQUIRED": (
        "Khách chưa được đo huyết áp — đo sinh hiệu trước khi điều phối."
    ),
    "ROUTE_NOT_DECIDED": "Lượt khám chưa xác định bước tiếp theo.",
    "HELD_UNTIL_ROUND": "Bác sĩ dặn làm dịch vụ này sau khi đọc kết quả vòng trước.",
}

_LIVE = "('done', 'left', 'cancelled')"


class LuotKhamConflictError(ConflictError):
    """409 kèm mã máy đọc được (``error_code``) và câu cho người đọc."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


class LuotKhamValidationError(ValidationError):
    """422 kèm mã — dữ liệu gửi lên tự mâu thuẫn."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


#: Những tập vai NỚI ĐƯỢC theo công tắc mở quyền tạm thời. Tập nào KHÔNG có ở
#: đây thì không bao giờ nới: `DOCTOR_ROLES`, `NOTE_ROLES`, `DRAFT_ROLES` là
#: việc của bác sĩ và thư ký cạnh bác sĩ — Tuyền nói rõ "trừ bác sĩ ra thui".
#:
#: `CLINICAL_READ_ROLES` cũng KHÔNG nới: nó quyết định ai đọc được chữ bác sĩ
#: viết trong bệnh án, và đó là đọc hồ sơ y tế chứ không phải thao tác vận hành.
_TAP_NOI_DUOC: tuple[frozenset[ClinicRole], ...] = (
    BOARD_ROLES,
    CHECKIN_ROLES,
    VITALS_ROLES,
    DISPATCH_ROLES,
    PERFORMER_ROLES,
)


def _require(identity: StaffIdentity, roles: frozenset[ClinicRole], cau: str) -> None:
    """Chặn theo vai — và đây là cửa THẬT, cửa ở router chỉ là lớp ngoài.

    Luật nghiệp vụ nằm trong hàm dịch vụ (CLAUDE.md), nên nới `require_role` ở
    router mà quên chỗ này thì vai mới qua được cửa ngoài rồi ăn `SafetyGateError`
    ở cửa trong — đúng cái đã xảy ra chiều 16/09: CSKH và thu ngân vẫn 403 ở
    bảng lượt khám sau khi đã nới router, và cửa gác ở router thì trông hoàn
    toàn đúng.
    """
    # So theo ĐÚNG TẬP (is), không theo giá trị: hai tập khác nghĩa có thể trùng
    # thành phần — PERFORMER_ROLES từ 17/09 trùng khít CLINICAL_READ_ROLES, và so
    # bằng `in` đã nới nhầm quyền đọc bệnh án.
    if mo_quyen_tam_thoi() and any(roles is t for t in _TAP_NOI_DUOC):
        if identity.co_vai(VAI_LAM_VIEC):
            return
    if not identity.co_vai(roles):
        raise SafetyGateError(cau)


def _uuid(value: Any, cau: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(cau) from None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _num(value: Decimal | int | None) -> float | int | None:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def _cung_ngay_vn(value: datetime) -> bool:
    """Mốc giờ này có thuộc HÔM NAY giờ Việt Nam không."""
    from clinicai.core.clock import now_vn

    return bool(value.astimezone(now_vn().tzinfo).date() == now_vn().date())


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LuotKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Nền: khoá, biên nhận, hàng chờ, D1, D2
    # ------------------------------------------------------------------

    @staticmethod
    async def _lock_visit(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> asyncpg.Record:
        row = await conn.fetchrow(
            """
            SELECT visit_id::text AS visit_id, status,
                   attending_doctor_id::text AS doctor_id
              FROM visit
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        # INCOMPLETE (khách về giữa chừng) nói riêng một câu: người đứng quầy
        # cần biết khách đã rời đi, không phải "lượt đã đóng" như ký xong.
        if row["status"] == "INCOMPLETE":
            raise LuotKhamConflictError(
                "VISIT_INCOMPLETE", "Khách đã rời phòng khám giữa chừng."
            )
        if row["status"] not in ("OPEN", "IN_PROGRESS"):
            raise LuotKhamConflictError("VISIT_CLOSED", "Lượt khám này đã đóng.")
        return row

    @staticmethod
    async def _lock_flow(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> asyncpg.Record:
        await conn.execute(
            """
            INSERT INTO encounter_flow (clinic_id, visit_id)
            VALUES ($1::uuid, $2::uuid)
            ON CONFLICT (visit_id) DO NOTHING
            """,
            clinic_id,
            visit_id,
        )
        row = await conn.fetchrow(
            """
            SELECT vitals_status, plan_check_status, route_decision, content_revision
              FROM encounter_flow
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )
        assert row is not None  # vừa chèn trong cùng transaction
        return row

    @staticmethod
    async def _visit_of(
        conn: asyncpg.Connection, table: str, clinic_id: str, row_id: str
    ) -> str:
        """Lượt khám chứa một phiên khám hoặc một chỉ định — để khoá visit trước."""
        if table == "consultation":
            visit = await conn.fetchval(
                "SELECT visit_id::text FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                row_id,
            )
            cau = "Không tìm thấy phiên khám này."
        else:
            visit = await conn.fetchval(
                "SELECT visit_id::text FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                row_id,
            )
            cau = "Không tìm thấy chỉ định này."
        if visit is None:
            raise NotFoundError(cau)
        return str(visit)

    @staticmethod
    async def _receipt_get(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        action: str,
        key: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not key:
            return None
        if not 8 <= len(key) <= 200:
            raise ValidationError("Khoá gửi lại phải dài từ 8 đến 200 ký tự.")
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"{identity.clinic_id}|{identity.staff_id}|{action}|{key}",
        )
        row = await conn.fetchrow(
            """
            SELECT payload_hash, result
              FROM command_receipt
             WHERE clinic_id = $1::uuid AND actor_staff_id = $2::uuid
               AND action = $3 AND idempotency_key = $4
            """,
            identity.clinic_id,
            identity.staff_id,
            action,
            key,
        )
        if row is None:
            return None
        if row["payload_hash"] != _hash(payload):
            raise LuotKhamConflictError(
                "IDEMPOTENCY_KEY_REUSED",
                "Khoá gửi lại này đã dùng cho một yêu cầu khác.",
            )
        result = row["result"]
        loaded = json.loads(result) if isinstance(result, str) else result
        return dict(loaded)

    @staticmethod
    async def _receipt_put(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        action: str,
        key: str | None,
        payload: dict[str, Any],
        target: str,
        result: dict[str, Any],
    ) -> None:
        if not key:
            return
        await conn.execute(
            """
            INSERT INTO command_receipt
                (clinic_id, actor_staff_id, action, idempotency_key,
                 payload_hash, target_ref, result)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7::jsonb)
            """,
            identity.clinic_id,
            identity.staff_id,
            action,
            key,
            _hash(payload),
            target,
            json.dumps(result),
        )

    @staticmethod
    async def _visit_busy(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> bool:
        return bool(
            await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                " AND status = 'serving')",
                clinic_id,
                visit_id,
            )
        )

    @staticmethod
    async def _block_others(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str, serving_id: str
    ) -> None:
        """Khách vào một phòng thì các chỗ chờ khác của khách tạm khoá (I9)."""
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'blocked', updated_at = now(), version = version + 1
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND id <> $3::uuid AND status IN ('waiting', 'called')
            """,
            clinic_id,
            visit_id,
            serving_id,
        )

    @staticmethod
    async def _release_blocked(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> None:
        """Khách rời phòng: chỗ chờ đang khoá mở ra, tính giờ từ BÂY GIỜ.

        ``eligible_at = now()`` là luật "quay lại sau những người đang chờ,
        trước người vào sau" (START-HERE :49), không phải tiện tay.
        """
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'waiting', eligible_at = now(),
                   updated_at = now(), version = version + 1
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status = 'blocked'
               AND NOT EXISTS (
                   SELECT 1 FROM queue_entry s
                    WHERE s.clinic_id = $1::uuid AND s.visit_id = $2::uuid
                      AND s.status = 'serving')
            """,
            clinic_id,
            visit_id,
        )

    async def _enqueue(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        lane: str,
        reason: str,
        ref_id: str,
        doctor_id: str | None = None,
        room_id: str | None = None,
    ) -> None:
        status = rules.initial_queue_status(
            visit_busy=await self._visit_busy(conn, clinic_id, visit_id)
        )
        await conn.execute(
            """
            INSERT INTO queue_entry
                (clinic_id, visit_id, lane, doctor_staff_id, room_id, reason,
                 ref_id, status, eligible_at)
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5::uuid, $6, $7::uuid, $8,
                    CASE WHEN $8 = 'waiting' THEN now() END)
            ON CONFLICT (visit_id, reason, ref_id)
                WHERE status NOT IN ('done', 'left', 'cancelled')
            DO NOTHING
            """,
            clinic_id,
            visit_id,
            lane,
            doctor_id,
            room_id,
            reason,
            ref_id,
            status,
        )

    async def _decide_route(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit: asyncpg.Record
    ) -> str | None:
        """D1 — chạy cuối mọi lệnh có thể đổi điều kiện của đích."""
        cid, vid = identity.clinic_id, visit["visit_id"]
        flow = await self._lock_flow(conn, cid, vid)
        new = rules.decide_route(
            vitals_recorded=flow["vitals_status"] == "recorded",
            plan_status=flow["plan_check_status"],
            current_route=flow["route_decision"],
        )
        if new is None:
            return str(flow["route_decision"]) if flow["route_decision"] else None
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = $3, route_decided_at = now(), route_reason = $4,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND route_decision IS NULL
            """,
            cid,
            vid,
            new,
            "sinh hiệu đã ghi, không có kế hoạch trước hợp lệ"
            if new == rules.PRIMARY
            else "kế hoạch trước đã áp hợp lệ",
        )
        if new == rules.PRIMARY:
            consultation_id = await conn.fetchval(
                """
                INSERT INTO consultation
                    (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'queued', $3::uuid)
                ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now()
                RETURNING id::text
                """,
                cid,
                vid,
                visit["doctor_id"],
            )
            await self._enqueue(
                conn,
                clinic_id=cid,
                visit_id=vid,
                lane="DOCTOR",
                reason="PRIMARY",
                ref_id=str(consultation_id),
                doctor_id=visit["doctor_id"],
            )
        await record_event(
            conn,
            event_type="visit.routed",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "route": new},
        )
        return new

    async def _evaluate_rounds(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> None:
        """D2 — vòng đọc nào vừa đủ điều kiện thì mở phiên và chỗ chờ, đúng MỘT."""
        cid = identity.clinic_id
        rounds = await conn.fetch(
            """
            SELECT id::text AS id, round_no, status
              FROM review_round
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('collecting', 'ready')
             ORDER BY round_no
               FOR UPDATE
            """,
            cid,
            visit_id,
        )
        for rd in rounds:
            reqs = await conn.fetch(
                """
                SELECT q.id::text AS id, q.service_order_id::text AS order_id,
                       q.need, q.status, o.exec_status
                  FROM round_requirement q
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                 WHERE q.clinic_id = $1::uuid AND q.round_id = $2::uuid
                """,
                cid,
                rd["id"],
            )
            views = []
            for q in reqs:
                view = rules.RequirementView(
                    q["order_id"], q["need"], q["status"], q["exec_status"], False
                )
                if q["status"] != "waived":
                    target = "satisfied" if rules.requirement_met(view) else "open"
                    if target != q["status"]:
                        await conn.execute(
                            "UPDATE round_requirement SET status = $3, updated_at ="
                            " now()"
                            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                            cid,
                            q["id"],
                            target,
                        )
                views.append(view)
            ready = rules.round_ready(views)
            if ready and rd["status"] == "collecting":
                await conn.execute(
                    "UPDATE review_round SET status = 'ready', ready_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                doctor = await conn.fetchval(
                    """
                    SELECT coalesce(
                        (SELECT c.doctor_staff_id FROM consultation c
                          WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                            AND c.round_no = 1),
                        (SELECT v.attending_doctor_id FROM visit v
                          WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid))::text
                    """,
                    cid,
                    visit_id,
                )
                consultation_id = await conn.fetchval(
                    """
                    INSERT INTO consultation
                        (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3, 'REVIEW', 'queued', $4::uuid)
                    ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now()
                    RETURNING id::text
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                    doctor,
                )
                await self._enqueue(
                    conn,
                    clinic_id=cid,
                    visit_id=visit_id,
                    lane="DOCTOR",
                    reason="REVIEW",
                    ref_id=str(consultation_id),
                    doctor_id=doctor,
                )
                await record_event(
                    conn,
                    event_type="review.ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )
            elif not ready and rd["status"] == "ready":
                # Lùi trước khi bác sĩ bắt đầu: huỷ chỗ chờ (không để "blocked",
                # vì blocked nghĩa là "khách đang ở phòng khác" và sẽ tự mở).
                await conn.execute(
                    "UPDATE review_round SET status = 'collecting', ready_at = NULL,"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                await conn.execute(
                    """
                    UPDATE queue_entry q
                       SET status = 'cancelled', updated_at = now(),
                          version = q.version + 1
                      FROM consultation c
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                       AND c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                       AND c.round_no = $3 AND q.ref_id = c.id
                       AND q.reason = 'REVIEW'
                       AND q.status IN ('waiting', 'called', 'blocked')
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                )
                await record_event(
                    conn,
                    event_type="review.not_ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )

    async def _services(
        self, conn: asyncpg.Connection, clinic_id: str, codes: list[str]
    ) -> list[asyncpg.Record]:
        wanted = [c.strip() for c in codes if isinstance(c, str) and c.strip()]
        if not wanted:
            raise ValidationError("Chưa chọn dịch vụ nào.")
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (s.service_code)
                   s.service_code, s.name, s.node_code
              FROM service_price s
             WHERE s.clinic_id = $1::uuid AND s.active
               AND s.service_code = ANY($2::text[])
             ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
            """,
            clinic_id,
            wanted,
        )
        found = {r["service_code"]: r for r in rows}
        missing = [c for c in wanted if c not in found]
        if missing:
            raise ValidationError("Không có dịch vụ: " + ", ".join(missing) + ".")
        unmapped = [found[c]["name"] for c in wanted if not found[c]["node_code"]]
        if unmapped:
            raise LuotKhamConflictError(
                "SERVICE_NOT_MAPPED",
                "Dịch vụ chưa gắn với bước thực hiện: " + ", ".join(unmapped) + ".",
            )
        return [found[c] for c in wanted]

    async def _cap_nhat_vi_tri(
        self, conn: asyncpg.Connection, cid: str, vid: str
    ) -> None:
        """Đặt con trỏ "khách đang ở đâu" (visit.current_node_code/room) theo
        hàng chờ của luồng khám mới.

        Bảng điều phối của trưởng ca, TV phòng chờ và bước đóng lượt đều đọc con
        trỏ này, mà luồng khám mới chưa từng dời nó: demo 17/09/2026 khám xong
        cả vòng rồi mà trưởng ca vẫn thấy khách "đang ở Đo chỉ số", và quầy
        không đóng được lượt.

        Đang được phục vụ ở đâu → ở đó; không thì chỗ đang gọi/đang chờ sớm nhất.
        Chỉ còn chỗ bị chặn (chờ kết quả) → giữ nguyên. Hết mọi chỗ → bước đóng
        lượt ở quầy tiếp đón.
        """
        r = await conn.fetchrow(
            """
            SELECT coalesce(
                       q.room_id,
                       (SELECT vt.room_id
                          FROM work_roster w
                          JOIN vi_tri_lam_viec vt
                            ON vt.clinic_id = w.clinic_id AND vt.code = w.station
                         WHERE w.clinic_id = q.clinic_id
                           AND w.staff_id = coalesce(q.doctor_staff_id,
                                                     c.doctor_staff_id)
                           AND w.status <> 'REJECTED'
                           AND vt.room_id IS NOT NULL
                           AND w.work_date
                               = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                         ORDER BY vt.sort
                         LIMIT 1)
                   ) AS room_id,
                   coalesce(
                       o.node_code,
                       -- Bàn khám chưa rõ phòng (bác sĩ không có ca xếp phòng):
                       -- vẫn nói được khách đang ở bước KHÁM loại nào.
                       CASE WHEN q.reason <> 'SERVICE' THEN
                           CASE st.form_code
                               WHEN 'NT' THEN 'KHAM-NOITIET'
                               WHEN 'PK' THEN 'KHAM-PHUKHOA'
                               WHEN 'SK' THEN 'KHAM-SANKHOA'
                               WHEN 'NK' THEN 'KHAM-NAMKHOA'
                               WHEN 'HMVS' THEN 'KHAM-HIEMMUON-VOSINH'
                           END
                       END
                   ) AS node_code
              FROM queue_entry q
              JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
              LEFT JOIN service_type st ON st.id = v.service_type_id
              LEFT JOIN consultation c
                ON c.id = q.ref_id AND q.reason <> 'SERVICE'
               AND c.clinic_id = q.clinic_id
              LEFT JOIN service_order o
                ON o.id = q.ref_id AND q.reason = 'SERVICE'
               AND o.clinic_id = q.clinic_id
             WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
               AND q.status IN ('serving', 'called', 'waiting')
             ORDER BY CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                      ELSE 2 END,
                      coalesce(q.eligible_at, q.created_at)
             LIMIT 1
            """,
            cid,
            vid,
        )
        if r is not None:
            room_id = r["room_id"]
            node = r["node_code"] or (
                await conn.fetchval(
                    "SELECT node_code FROM clinic_room WHERE id = $1::uuid",
                    room_id,
                )
                if room_id
                else None
            )
        else:
            con_mo = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND status NOT IN ('done', 'left',"
                " 'cancelled'))",
                cid,
                vid,
            )
            if con_mo:
                return
            node = "LUOTKHAM-15"
            room_id = await conn.fetchval(
                "SELECT id FROM clinic_room WHERE clinic_id = $1::uuid"
                " AND node_code = 'LUOTKHAM-01' AND is_active ORDER BY sort LIMIT 1",
                cid,
            )
        # node rỗng (chưa suy ra được bước) vẫn ghi: để trống còn hơn trỏ vào
        # phòng khách đã rời — trưởng ca đọc "đang ở Siêu âm" sai thì điều sai.
        await conn.execute(
            """
            UPDATE visit
               SET previous_node_code = CASE
                       WHEN current_node_code IS DISTINCT FROM $3
                       THEN current_node_code ELSE previous_node_code END,
                   current_node_since = CASE
                       WHEN current_node_code IS DISTINCT FROM $3
                         OR current_room_id IS DISTINCT FROM $4::uuid
                       THEN now() ELSE current_node_since END,
                   current_node_code = $3,
                   current_room_id = $4::uuid,
                   updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('OPEN', 'IN_PROGRESS')
            """,
            cid,
            vid,
            node,
            room_id,
        )

    async def _thu_ky_cua_bac_si(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        doctor_id: str | None,
    ) -> None:
        """Thư ký chỉ bấm được cho khách của bác sĩ mình đi kèm."""
        if not identity.co_vai({ClinicRole.TKYK}):
            return
        ds = await bac_si_cua_thu_ky(conn, identity)
        if ds is not None and (doctor_id is None or doctor_id not in ds):
            raise SafetyGateError(
                "Khách này của bác sĩ khác — thư ký chỉ làm cho bác sĩ mình đi kèm."
            )

    async def _cung_ekip(
        self, conn: asyncpg.Connection, identity: StaffIdentity, c: asyncpg.Record
    ) -> bool:
        """Người gọi thuộc ê-kíp của phiên: chính bác sĩ, hoặc thư ký của bác sĩ ấy."""
        if identity.co_vai({ClinicRole.DOCTOR}):
            return bool(c["doctor_id"] == identity.staff_id)
        if identity.co_vai({ClinicRole.TKYK}):
            ds = await bac_si_cua_thu_ky(conn, identity)
            return ds is None or c["doctor_id"] in ds
        return False

    async def _consultation_in_progress(
        self, conn: asyncpg.Connection, clinic_id: str, consultation_id: str
    ) -> asyncpg.Record:
        c = await conn.fetchrow(
            """
            SELECT id::text AS id, visit_id::text AS visit_id, round_no, kind,
                   status, started_by::text AS started_by,
                   doctor_staff_id::text AS doctor_id
              FROM consultation
             WHERE clinic_id = $1::uuid AND id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            consultation_id,
        )
        if c is None:
            raise NotFoundError("Không tìm thấy phiên khám này.")
        if c["status"] != "in_progress":
            raise LuotKhamConflictError(
                "CONSULTATION_NOT_IN_PROGRESS",
                "Phiên khám chưa bắt đầu hoặc đã kết thúc.",
            )
        return c

    # ------------------------------------------------------------------
    # Bảng làm việc
    # ------------------------------------------------------------------

    async def bang(self, *, identity: StaffIdentity) -> dict[str, Any]:
        _require(identity, BOARD_ROLES, "Vai của bạn không dùng màn lượt khám.")
        cid = identity.clinic_id
        doc_noi_dung = identity.co_vai(CLINICAL_READ_ROLES)
        async with self._pool.acquire() as conn:
            visits = await conn.fetch(
                """
                SELECT v.visit_id::text AS visit_id, v.checked_in_at,
                       v.attending_doctor_id::text AS doctor_id,
                       p.full_name, p.patient_code, d.full_name AS doctor_name,
                       f.vitals_status, f.route_decision, f.finished_at
                  FROM visit v
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN encounter_flow f
                    ON f.visit_id = v.visit_id AND f.clinic_id = v.clinic_id
                 WHERE v.clinic_id = $1::uuid
                   -- INCOMPLETE cố ý không hiện: khách đã về.
                   AND v.status IN ('OPEN', 'IN_PROGRESS')
                   AND v.checked_in_at IS NOT NULL
                   AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   -- Thư ký chỉ thấy lượt của bác sĩ mình (20260915000020).
                   AND coalesce(v.attending_doctor_id::text, '~')
                       = ANY(coalesce(
                             $2::text[],
                             ARRAY[coalesce(v.attending_doctor_id::text, '~')]))
                 ORDER BY v.checked_in_at, v.visit_id
                """,
                cid,
                await bac_si_cua_thu_ky(conn, identity),
            )
            ids = [r["visit_id"] for r in visits]
            vitals: list[asyncpg.Record] = []
            phien: list[asyncpg.Record] = []
            ghi_chu: list[asyncpg.Record] = []
            chi_dinh: list[asyncpg.Record] = []
            hang_cho: list[asyncpg.Record] = []
            vong: list[asyncpg.Record] = []
            yeu_cau: list[asyncpg.Record] = []
            if ids:
                vitals = await conn.fetch(
                    """
                    SELECT DISTINCT ON (m.visit_id)
                           m.visit_id::text AS visit_id, m.systolic, m.diastolic,
                           m.pulse, m.temperature, m.weight_kg, m.height_cm,
                           m.respiratory_rate, m.spo2, m.bmi, m.pain_score,
                           m.created_at, s.full_name AS recorded_by_name
                      FROM vital_measurement m
                      LEFT JOIN staff s ON s.id = m.recorded_by
                     WHERE m.clinic_id = $1::uuid AND m.visit_id = ANY($2::uuid[])
                     ORDER BY m.visit_id, m.created_at DESC
                    """,
                    cid,
                    ids,
                )
                phien = await conn.fetch(
                    """
                    SELECT c.id::text AS id, c.visit_id::text AS visit_id, c.round_no,
                           c.kind, c.status, c.outcome,
                           c.doctor_staff_id::text AS doctor_id,
                           c.started_by::text AS started_by
                      FROM consultation c
                     WHERE c.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                     ORDER BY c.visit_id, c.round_no
                    """,
                    cid,
                    ids,
                )
                if doc_noi_dung:
                    ghi_chu = await conn.fetch(
                        """
                        SELECT n.consultation_id::text AS consultation_id, n.body,
                               n.created_at, s.full_name AS recorded_by_name
                          FROM consultation_note n
                          JOIN consultation c
                            ON c.id = n.consultation_id AND c.clinic_id = n.clinic_id
                          LEFT JOIN staff s ON s.id = n.recorded_by
                         WHERE n.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                         ORDER BY n.created_at
                        """,
                        cid,
                        ids,
                    )
                chi_dinh = await conn.fetch(
                    """
                    SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                           o.consultation_id::text AS consultation_id,
                           o.service_code, o.service_name, o.node_code, o.exec_status,
                           o.room_id::text AS room_id, r.name AS room_name,
                           o.hold_until_round, o.version, o.result_note,
                           o.not_performed_reason,
                           rec.full_name AS recorded_by_name,
                           au.full_name AS authorized_by_name,
                           pf.full_name AS performed_by_name
                      FROM service_order o
                      LEFT JOIN clinic_room r
                        ON r.id = o.room_id AND r.clinic_id = o.clinic_id
                      LEFT JOIN staff rec ON rec.id = o.recorded_by
                      LEFT JOIN staff au ON au.id = o.authorized_by
                      LEFT JOIN staff pf ON pf.id = o.performed_by
                     WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                       AND (o.exec_status <> 'draft' OR $3::boolean)
                     ORDER BY o.created_at, o.id
                    """,
                    cid,
                    ids,
                    identity.co_vai(NOTE_ROLES),
                )
                hang_cho = await conn.fetch(
                    """
                    SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.lane,
                           q.reason, q.ref_id::text AS ref_id, q.status,
                           q.eligible_at, q.created_at,
                           q.room_id::text AS room_id,
                           q.doctor_staff_id::text AS doctor_id
                      FROM queue_entry q
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                    """,
                    cid,
                    ids,
                )
                vong = await conn.fetch(
                    """
                    SELECT r.id::text AS id, r.visit_id::text AS visit_id,
                           r.round_no, r.status
                      FROM review_round r
                     WHERE r.clinic_id = $1::uuid AND r.visit_id = ANY($2::uuid[])
                     ORDER BY r.visit_id, r.round_no
                    """,
                    cid,
                    ids,
                )
                if vong:
                    yeu_cau = await conn.fetch(
                        """
                        SELECT q.round_id::text AS round_id,
                               q.service_order_id::text AS order_id, q.need, q.status
                          FROM round_requirement q
                         WHERE q.clinic_id = $1::uuid AND q.round_id = ANY($2::uuid[])
                        """,
                        cid,
                        [r["id"] for r in vong],
                    )
            phong = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active AND r.accepting
                 GROUP BY r.id, r.code, r.name, r.sort
                 ORDER BY r.sort, r.code
                """,
                cid,
            )
            dich_vu = await conn.fetch(
                """
                SELECT DISTINCT ON (s.service_code)
                       s.service_code, s.name, s.node_code, n.actor_roles
                  FROM service_price s
                  JOIN node_definition n
                    ON n.clinic_id = s.clinic_id AND n.code = s.node_code
                 WHERE s.clinic_id = $1::uuid AND s.active
                   AND s.node_code LIKE 'DICHVU-%'
                 ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
                """,
                cid,
            )
            lich: list[asyncpg.Record] = []
            if identity.co_vai(CHECKIN_ROLES):
                lich = await conn.fetch(
                    """
                    SELECT a.id::text AS id, a.slot_start, a.status,
                           p.full_name, p.patient_code, d.full_name AS doctor_name
                      FROM appointment a
                      JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                      LEFT JOIN staff d ON d.id = a.doctor_id
                     WHERE a.clinic_id = $1::uuid
                       AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     ORDER BY a.slot_start, a.id
                    """,
                    cid,
                )

        by_visit: dict[str, dict[str, Any]] = {}
        for v in visits:
            by_visit[v["visit_id"]] = {
                "visit_id": v["visit_id"],
                "ma_bn": v["patient_code"],
                "ten": v["full_name"],
                "bac_si_id": v["doctor_id"],
                "bac_si": v["doctor_name"],
                "check_in_luc": _iso(v["checked_in_at"]),
                "sinh_hieu_trang_thai": v["vitals_status"] or "pending",
                "dich": v["route_decision"],
                "ket_thuc_luc": _iso(v["finished_at"]),
                "sinh_hieu": None,
                "phien": [],
                "chi_dinh": [],
                "hang_cho": [],
                "vong": [],
            }
        for m in vitals:
            by_visit[m["visit_id"]]["sinh_hieu"] = {
                "tam_thu": m["systolic"],
                "tam_truong": m["diastolic"],
                "mach": m["pulse"],
                "nhiet_do": _num(m["temperature"]),
                "can_nang": _num(m["weight_kg"]),
                "chieu_cao": _num(m["height_cm"]),
                "nhip_tho": m["respiratory_rate"],
                "spo2": m["spo2"],
                "bmi": _num(m["bmi"]),
                "muc_do_dau": m["pain_score"],
                "luc": _iso(m["created_at"]),
                "nguoi_do": m["recorded_by_name"],
            }
        notes_by: dict[str, list[dict[str, Any]]] = {}
        for n in ghi_chu:
            notes_by.setdefault(n["consultation_id"], []).append(
                {
                    "noi_dung": n["body"],
                    "nguoi_ghi": n["recorded_by_name"],
                    "luc": _iso(n["created_at"]),
                }
            )
        for c in phien:
            by_visit[c["visit_id"]]["phien"].append(
                {
                    "id": c["id"],
                    "vong": c["round_no"],
                    "loai": c["kind"],
                    "trang_thai": c["status"],
                    "ket_qua": c["outcome"],
                    "bac_si_id": c["doctor_id"],
                    "nguoi_bat_dau_id": c["started_by"],
                    "ghi_chu": notes_by.get(c["id"], []),
                }
            )
        for o in chi_dinh:
            by_visit[o["visit_id"]]["chi_dinh"].append(
                {
                    "id": o["id"],
                    "phien_id": o["consultation_id"],
                    "ma_dich_vu": o["service_code"],
                    "ten_dich_vu": o["service_name"],
                    "node": o["node_code"],
                    "trang_thai": o["exec_status"],
                    "phong_id": o["room_id"],
                    "phong": o["room_name"],
                    "giu_toi_vong": o["hold_until_round"],
                    "version": o["version"],
                    "nguoi_ghi": o["recorded_by_name"],
                    "nguoi_duyet": o["authorized_by_name"],
                    "nguoi_lam": o["performed_by_name"],
                    "ket_qua": o["result_note"] if doc_noi_dung else None,
                    "ly_do_khong_lam": o["not_performed_reason"],
                }
            )
        views = [
            rules.QueueView(q["id"], q["status"], q["eligible_at"], q["created_at"])
            for q in hang_cho
        ]
        order = {e.id: i for i, e in enumerate(rules.order_queue(views))}
        for q in sorted(hang_cho, key=lambda x: order.get(x["id"], 0)):
            by_visit[q["visit_id"]]["hang_cho"].append(
                {
                    "id": q["id"],
                    "hang": q["lane"],
                    "ly_do": q["reason"],
                    "ref_id": q["ref_id"],
                    "trang_thai": q["status"],
                    "du_dieu_kien_luc": _iso(q["eligible_at"]),
                    "phong_id": q["room_id"],
                    "bac_si_id": q["doctor_id"],
                }
            )
        req_by: dict[str, list[dict[str, Any]]] = {}
        for q in yeu_cau:
            req_by.setdefault(q["round_id"], []).append(
                {
                    "chi_dinh_id": q["order_id"],
                    "can": q["need"],
                    "trang_thai": q["status"],
                }
            )
        for r in vong:
            by_visit[r["visit_id"]]["vong"].append(
                {
                    "id": r["id"],
                    "vong": r["round_no"],
                    "trang_thai": r["status"],
                    "yeu_cau": req_by.get(r["id"], []),
                }
            )
        return {
            "vai": identity.role.value,
            "toi": identity.staff_id,
            "luot": list(by_visit.values()),
            "phong": [
                {
                    "id": p["id"],
                    "ma": p["code"],
                    "ten": p["name"],
                    "nodes": list(p["nodes"]),
                }
                for p in phong
            ],
            "dich_vu": [
                {
                    "ma": s["service_code"],
                    "ten": s["name"],
                    "node": s["node_code"],
                    "vai_lam": list(s["actor_roles"] or []),
                }
                for s in dich_vu
            ],
            "lich_cho_check_in": [
                {
                    "id": a["id"],
                    "gio": _iso(a["slot_start"]),
                    "ten": a["full_name"],
                    "ma_bn": a["patient_code"],
                    "bac_si": a["doctor_name"],
                }
                for a in lich
            ],
        }

    # ------------------------------------------------------------------
    # C0 — check-in: dùng lại đúng máy trạng thái đang chạy
    # ------------------------------------------------------------------

    async def phong_hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Phòng mà người gọi đứng trong lịch HÔM NAY — mỗi phòng một hàng chờ."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT r.id::text AS id, r.code, r.name, r.floor, r.sort,
                       array_agg(DISTINCT w.station) AS vi_tri,
                       array_agg(DISTINCT rn.node_code) AS nodes
                  FROM work_roster w
                  JOIN vi_tri_lam_viec v
                    ON v.clinic_id = w.clinic_id AND v.code = w.station
                  JOIN clinic_room r
                    ON r.id = v.room_id AND r.clinic_id = w.clinic_id AND r.is_active
                  LEFT JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
                   AND w.status <> 'REJECTED'
                   AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
                identity.staff_id,
            )
            tat_ca = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name, r.floor,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
            )
        return {
            "phong_cua_toi": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "vi_tri": list(r["vi_tri"] or []),
                    "nodes": [n for n in (r["nodes"] or []) if n],
                }
                for r in rows
            ],
            "tat_ca_phong": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "nodes": list(r["nodes"] or []),
                }
                for r in tat_ca
            ],
        }

    async def hang_cho(
        self,
        *,
        identity: StaffIdentity,
        room_id: str | None,
    ) -> dict[str, Any]:
        """HÀNG CHỜ của một phòng: ai đang chờ, ai đang trong phòng, ai đã xong.

        Tuyền 16/09/2026: *"sẽ luôn có 1 danh sách các khách đang xếp hàng, sau đó
        bác sĩ chọn rồi ấn bắt đầu khám cho người đó, rồi điền thông tin bên
        trong, khám xong thì ghi đã khám xong — vậy là check-out cho khách ở
        phòng đó"*.

        Một phòng có hai loại chỗ chờ:
          * chỉ định xếp vào phòng (siêu âm, lấy mẫu, thủ thuật) — theo `room_id`;
          * lượt khám chính của BÁC SĨ đứng phòng ấy hôm nay — khám chính chờ theo
            bác sĩ, không theo phòng, nên phải tra lịch để biết bác sĩ nào.

        THỨ TỰ: giờ vào hàng chờ, tức giờ đo sinh hiệu xong hoặc giờ được chỉ
        định; số thứ tự trong ngày là thứ tự CHECK-IN, như phiếu lễ tân phát.
        """
        _require(identity, BOARD_ROLES, "Vai của bạn không dùng hàng chờ phòng.")
        cid = identity.clinic_id
        rid = _uuid(room_id, "Mã phòng không hợp lệ.") if room_id else None
        async with self._pool.acquire() as conn:
            phong = None
            if rid is not None:
                phong = await conn.fetchrow(
                    """
                    SELECT r.id::text AS id, r.code, r.name, r.floor,
                           array_agg(rn.node_code) AS nodes
                      FROM clinic_room r
                      LEFT JOIN clinic_room_node rn
                        ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                     WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                     GROUP BY r.id
                    """,
                    cid,
                    rid,
                )
                if phong is None:
                    raise NotFoundError("Không tìm thấy phòng này.")
            # Bác sĩ có lượt khám chính trong hàng chờ này.
            if rid is not None:
                bac_si = await conn.fetch(
                    """
                    SELECT DISTINCT w.staff_id::text AS id
                      FROM work_roster w
                      JOIN vi_tri_lam_viec v
                        ON v.clinic_id = w.clinic_id AND v.code = w.station
                      JOIN clinic_membership m
                        ON m.staff_id = w.staff_id AND m.clinic_id = w.clinic_id
                       AND m.is_active AND m.role = 'DOCTOR'
                     WHERE w.clinic_id = $1::uuid AND v.room_id = $2::uuid
                       AND w.status <> 'REJECTED'
                       AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                    """,
                    cid,
                    rid,
                )
                ds_bac_si = [r["id"] for r in bac_si]
            else:
                ds_bac_si = []
            so_bac_si_trong_phong = len(ds_bac_si)
            # "Khách của tôi" (không chọn phòng) cho người ĐIỀU PHỐI hoặc thư ký
            # chưa bị giới hạn theo bác sĩ: thấy lượt khám chính của MỌI bác sĩ.
            # Bản trước trả rỗng cho thư ký ở chế độ mở quyền — thư ký mở Bàn khám
            # mà không thấy ai (tự kiểm 16/09/2026).
            tat_ca_bac_si = False
            if identity.co_vai({ClinicRole.DOCTOR}):
                ds_bac_si = sorted({*ds_bac_si, identity.staff_id})
            if identity.co_vai({ClinicRole.TKYK}):
                cua_toi = await bac_si_cua_thu_ky(conn, identity)
                if cua_toi is not None:
                    ds_bac_si = sorted(
                        {*ds_bac_si, *cua_toi} if rid is None else cua_toi
                    )
                elif rid is None:
                    tat_ca_bac_si = True
            if rid is None and identity.co_vai(
                {ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT}
            ):
                tat_ca_bac_si = True
            rows = await conn.fetch(
                """
                WITH stt AS (
                    SELECT v.visit_id,
                           row_number() OVER (ORDER BY v.checked_in_at, v.visit_id)
                               AS so
                      FROM visit v
                     WHERE v.clinic_id = $1::uuid AND v.checked_in_at IS NOT NULL
                       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                )
                SELECT q.id::text AS id, q.status, q.lane, q.reason,
                       q.ref_id::text AS ref_id, q.visit_id::text AS visit_id,
                       q.eligible_at, q.called_at, q.serving_at, q.done_at,
                       q.created_at,
                       stt.so AS so_thu_tu,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code, p.uu_tien, p.uu_tien_ly_do,
                       v.appointment_id::text AS appointment_id,
                       v.checked_in_at,
                       st.name AS dich_vu_kham, st.form_code,
                       d.full_name AS bac_si,
                       coalesce(o.service_name, st.name) AS viec,
                       o.service_code, o.node_code, o.exec_status,
                       o.result_note, o.ket_qua_luc, o.duyet_luc,
                       c.status AS phien_status, c.kind AS phien_kind,
                       r.name AS phong
                  FROM queue_entry q
                  JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
                  JOIN stt ON stt.visit_id = q.visit_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN service_type st ON st.id = v.service_type_id
                  LEFT JOIN staff d
                    ON d.id = coalesce(q.doctor_staff_id, v.attending_doctor_id)
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN clinic_room r ON r.id = q.room_id
                 WHERE q.clinic_id = $1::uuid
                   AND q.status IN ('blocked', 'waiting', 'called', 'serving', 'done')
                   AND (
                        ($2::uuid IS NOT NULL AND q.lane = 'ROOM'
                             AND q.room_id = $2::uuid)
                     OR (q.lane = 'DOCTOR'
                             AND ($4::boolean
                                  OR q.doctor_staff_id::text = ANY($3::text[])
                                  -- Khách CHƯA có bác sĩ (lịch hẹn không gắn
                                  -- bác sĩ): hiện ở mọi hàng chờ khám có bác sĩ,
                                  -- ai bấm Bắt đầu khám thì nhận. Bản trước khách
                                  -- này không nằm trong hàng chờ của AI cả (tự
                                  -- kiểm 16/09/2026).
                                  OR (q.doctor_staff_id IS NULL
                                      AND cardinality($3::text[]) > 0)))
                   )
                 ORDER BY
                   CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                        WHEN 'waiting' THEN 2 WHEN 'blocked' THEN 3 ELSE 4 END,
                   p.uu_tien DESC NULLS LAST,
                   coalesce(q.eligible_at, q.created_at), q.id
                """,
                cid,
                rid,
                ds_bac_si,
                tat_ca_bac_si,
            )
        now_rows = [
            {
                "id": r["id"],
                "trang_thai": r["status"],
                "loai": "KHAM" if r["reason"] != "SERVICE" else "DICH_VU",
                "ref_id": r["ref_id"],
                "visit_id": r["visit_id"],
                "clinic_patient_id": r["clinic_patient_id"],
                "appointment_id": r["appointment_id"],
                "so_thu_tu": int(r["so_thu_tu"]),
                "ten": r["full_name"],
                "ma_bn": r["patient_code"],
                "uu_tien": bool(r["uu_tien"]),
                "uu_tien_ly_do": r["uu_tien_ly_do"],
                "viec": r["viec"],
                "dich_vu_kham": r["dich_vu_kham"],
                "form_code": r["form_code"],
                "service_code": r["service_code"],
                "node_code": r["node_code"],
                "exec_status": r["exec_status"],
                "phien_status": r["phien_status"],
                "bac_si": r["bac_si"],
                "phong": r["phong"],
                "vao_hang_luc": _iso(r["eligible_at"] or r["created_at"]),
                # Mốc check-in của CẢ lượt: khách quay lại bác sĩ chính đọc kết
                # quả thì đồng hồ tổng vẫn chạy từ lúc vào phòng khám.
                "checkin_luc": _iso(r["checked_in_at"]),
                "vong": r["phien_kind"],
                "goi_luc": _iso(r["called_at"]),
                "bat_dau_luc": _iso(r["serving_at"]),
                "xong_luc": _iso(r["done_at"]),
                "ket_qua_luc": _iso(r["ket_qua_luc"]),
                "duyet_luc": _iso(r["duyet_luc"]),
            }
            for r in rows
            # Người đã xong chỉ giữ của hôm nay.
            if r["status"] != "done"
            or (r["done_at"] is not None and _cung_ngay_vn(r["done_at"]))
        ]
        return {
            "phong": (
                {
                    "id": phong["id"],
                    "code": phong["code"],
                    "ten": phong["name"],
                    "tang": phong["floor"],
                    "nodes": [n for n in (phong["nodes"] or []) if n],
                }
                if phong
                else None
            ),
            "hang_cho": now_rows,
            # Phòng khám mà hôm nay chưa có bác sĩ nào trong lịch: màn nói rõ
            # vì sao hàng chờ khám trống, thay vì trông như "hết khách".
            "so_bac_si_trong_phong": so_bac_si_trong_phong if rid else None,
        }

    async def goi_khach(
        self, *, queue_entry_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """GỌI khách vào phòng (Tuyền 16/09/2026: *"gọi khách vào khám rồi ấn bắt
        đầu khám"*). Chờ → Đã gọi; gọi lại thì cập nhật giờ gọi.

        Ai gọi được: lượt khám chính — bác sĩ hoặc thư ký đi kèm bác sĩ ấy; chỉ
        định trong phòng — vai thực hiện bước ấy (thủ thuật: bác sĩ; siêu âm: bác
        sĩ/điều dưỡng siêu âm; lấy mẫu: điều dưỡng), tính cả vai vị trí hôm nay.
        """
        cid = identity.clinic_id
        qid = _uuid(queue_entry_id, "Mã chỗ chờ không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            q = await conn.fetchrow(
                """
                SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.reason,
                       q.status, q.ref_id::text AS ref_id,
                       coalesce(q.doctor_staff_id, c.doctor_staff_id)::text
                           AS doctor_id,
                       n.actor_roles
                  FROM queue_entry q
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                """,
                cid,
                qid,
            )
            if q is None:
                raise NotFoundError("Không tìm thấy khách trong hàng chờ.")
            await self._lock_visit(conn, cid, q["visit_id"])
            if q["reason"] == "SERVICE":
                if not set(identity.ds_vai()) & (
                    set(q["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
                ):
                    raise SafetyGateError("Vai của bạn không làm bước này.")
            else:
                _require(
                    identity,
                    CONSULT_ROLES,
                    "Chỉ bác sĩ hoặc thư ký đi kèm gọi khách vào khám được.",
                )
                await self._thu_ky_cua_bac_si(conn, identity, q["doctor_id"])
            trang_thai = await conn.fetchval(
                "SELECT status FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid FOR UPDATE",
                cid,
                qid,
            )
            if trang_thai not in ("waiting", "called"):
                raise LuotKhamConflictError(
                    "NOT_WAITING",
                    "Khách không còn trong hàng chờ (đang làm bước khác hoặc đã xong).",
                )
            await conn.execute(
                "UPDATE queue_entry SET status = 'called', called_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                qid,
            )
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, q["visit_id"])
            await record_event(
                conn,
                event_type="queue.called",
                aggregate_type="visit",
                aggregate_id=q["visit_id"],
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": q["visit_id"], "queue_entry_id": qid},
            )
        return {
            "ok": True,
            "queue_entry_id": qid,
            "lan_goi_lai": trang_thai == "called",
        }

    async def kham_xong(
        self,
        *,
        consultation_id: str,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Nút "Đã khám xong" — hệ thống tự chọn kết quả phiên, người bấm không phải.

        Còn chỉ định đã duyệt chưa làm → "cần dịch vụ", khách quay lại khi các
        dịch vụ ấy làm xong. Không còn → "không cần dịch vụ", lượt khám chính
        khép lại. Bắt bác sĩ chọn giữa hai mã kỹ thuật ấy là đẩy luật vận hành
        lên đầu người đang khám.
        """
        _require(
            identity,
            CONSULT_ROLES,
            "Chỉ bác sĩ hoặc thư ký đi kèm kết thúc phiên khám được.",
        )
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            c = await conn.fetchrow(
                "SELECT kind, visit_id::text AS visit_id FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                con_id,
            )
            if c is None:
                raise NotFoundError("Không tìm thấy phiên khám này.")
            con_lai = await conn.fetch(
                """
                SELECT id::text AS id FROM service_order
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND exec_status IN ('authorized', 'assigned', 'in_progress')
                   AND hold_until_round IS NULL
                """,
                cid,
                c["visit_id"],
            )
        if con_lai:
            outcome = "SERVICES" if c["kind"] == "PRIMARY" else "MORE_SERVICES"
            reqs = [{"order_id": r["id"], "need": "PERFORMED"} for r in con_lai]
        else:
            outcome = "NO_SERVICES" if c["kind"] == "PRIMARY" else "DONE"
            reqs = []
        return await self.complete_consultation(
            consultation_id=con_id,
            outcome=outcome,
            requirements=reqs,
            identity=identity,
            idempotency_key=idempotency_key,
        )

    async def check_in(
        self,
        *,
        appointment_id: str,
        identity: StaffIdentity,
        xac_minh_cach: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, CHECKIN_ROLES, "Chỉ lễ tân hoặc quản lý check-in được.")
        from clinicai.services.booking_service import BookingService

        result = await BookingService(self._pool).apply_action(
            appointment_id=_uuid(appointment_id, "Mã lịch hẹn không hợp lệ."),
            action="checkin",
            identity=identity,
            xac_minh_cach=xac_minh_cach,
        )
        return {"ok": True, **result}

    # ------------------------------------------------------------------
    # C2 — ghi sinh hiệu
    # ------------------------------------------------------------------

    async def record_vitals(
        self,
        *,
        visit_id: str,
        raw: Any,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, VITALS_ROLES, "Vai của bạn không ghi sinh hiệu được.")
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        vitals, loi = rules.parse_vitals(raw)
        if vitals is None:
            raise ValidationError(loi or "Sinh hiệu không hợp lệ.")
        payload = {
            "visit_id": vid,
            **{k: str(v) if v is not None else None for k, v in asdict(vitals).items()},
        }
        async with self._pool.acquire() as conn, conn.transaction():
            visit = await self._lock_visit(conn, identity.clinic_id, vid)
            cached = await self._receipt_get(
                conn, identity, "vitals.record", idempotency_key, payload
            )
            if cached is not None:
                return cached
            co_thai = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pregnancy p JOIN visit v
                      ON v.clinic_id = p.clinic_id
                     AND v.clinic_patient_id = p.clinic_patient_id
                   WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                     AND coalesce(p.outcome, 'ONGOING') = 'ONGOING')
                """,
                identity.clinic_id,
                vid,
            )
            loi_thai = rules.thieu_sinh_hieu_khi_co_thai(vitals, co_thai=bool(co_thai))
            if loi_thai:
                raise ValidationError(loi_thai)
            await self._lock_flow(conn, identity.clinic_id, vid)
            await conn.execute(
                """
                INSERT INTO vital_measurement
                    (clinic_id, visit_id, systolic, diastolic, pulse, temperature,
                     weight_kg, height_cm, respiratory_rate, spo2, bmi,
                     pain_score, recorded_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13::uuid)
                """,
                identity.clinic_id,
                vid,
                vitals.systolic,
                vitals.diastolic,
                vitals.pulse,
                vitals.temperature,
                vitals.weight_kg,
                vitals.height_cm,
                vitals.respiratory_rate,
                vitals.spo2,
                vitals.bmi,
                vitals.pain_score,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE encounter_flow
                   SET vitals_status = 'recorded',
                       content_revision = content_revision + 1,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                vid,
            )
            await record_event(
                conn,
                event_type="vitals.recorded",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
            route = await self._decide_route(conn, identity, visit)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            result = {"ok": True, "visit_id": vid, "route": route}
            await self._receipt_put(
                conn, identity, "vitals.record", idempotency_key, payload, vid, result
            )
        return result

    # ------------------------------------------------------------------
    # C3 — bác sĩ nhận khách vào phiên khám
    # ------------------------------------------------------------------

    async def start_consultation(
        self, *, consultation_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        _require(
            identity,
            CONSULT_ROLES,
            "Chỉ bác sĩ hoặc thư ký đi kèm nhận khách vào khám được.",
        )
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            c = await conn.fetchrow(
                """
                SELECT id::text AS id, kind, status, started_by::text AS started_by,
                       doctor_staff_id::text AS doctor_id
                  FROM consultation
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                con_id,
            )
            assert c is not None
            await self._thu_ky_cua_bac_si(conn, identity, c["doctor_id"])
            if c["status"] == "in_progress":
                # Thư ký bấm rồi bác sĩ bấm lại (hay ngược lại) là CÙNG một phiên
                # đang khám, không phải bị người khác giành.
                if c["started_by"] == identity.staff_id or await self._cung_ekip(
                    conn, identity, c
                ):
                    return {"ok": True, "consultation_id": con_id, "already": True}
                raise LuotKhamConflictError(
                    "CONSULTATION_TAKEN", "Phiên khám này bác sĩ khác đang khám."
                )
            if c["status"] != "queued":
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_QUEUED", "Phiên khám này không còn chờ khám."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status
                  FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid AND reason = $4
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                con_id,
                c["kind"],
            )
            if (
                entry is None
                or entry["status"] not in ("waiting", "called")
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa gọi vào khám được.",
                )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'in_progress', started_by = $3::uuid,
                      started_at = now(),
                       -- Thư ký bấm thì KHÔNG thành bác sĩ của phiên.
                       doctor_staff_id = coalesce(
                           doctor_staff_id, CASE WHEN $4 THEN $3::uuid END),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                identity.staff_id,
                identity.co_vai({ClinicRole.DOCTOR}),
            )
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id, "kind": c["kind"]},
            )
        return {"ok": True, "consultation_id": con_id}

    # ------------------------------------------------------------------
    # C4 — ghi chú khám (bác sĩ hoặc thư ký gõ hộ)
    # ------------------------------------------------------------------

    async def save_note(
        self, *, consultation_id: str, body: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        _require(
            identity, NOTE_ROLES, "Chỉ bác sĩ hoặc thư ký y khoa ghi chú khám được."
        )
        text = (body or "").strip() if isinstance(body, str) else ""
        if not text:
            raise ValidationError("Ghi chú đang trống.")
        if len(text) > 20000:
            raise ValidationError("Ghi chú quá dài.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            await self._consultation_in_progress(conn, cid, con_id)
            await self._lock_flow(conn, cid, vid)
            await conn.execute(
                "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
                " recorded_by)"
                " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                cid,
                con_id,
                text,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE encounter_flow SET content_revision = content_revision + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid",
                cid,
                vid,
            )
            await record_event(
                conn,
                event_type="consult.note_saved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id},
            )
        return {"ok": True}

    # ------------------------------------------------------------------
    # C5 / C6 — nháp chỉ định (thư ký) và duyệt chỉ định (chỉ bác sĩ)
    # ------------------------------------------------------------------

    async def propose_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str],
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DRAFT_ROLES, "Chỉ thư ký y khoa ghi nháp chỉ định.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        payload = {"consultation_id": con_id, "codes": list(service_codes or [])}
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.draft", idempotency_key, payload
            )
            if cached is not None:
                return cached
            await self._consultation_in_progress(conn, cid, con_id)
            services = await self._services(conn, cid, list(service_codes or []))
            ids = []
            for s in services:
                ids.append(
                    await conn.fetchval(
                        """
                        INSERT INTO service_order
                            (clinic_id, visit_id, consultation_id, service_code,
                             service_name, node_code, exec_status, recorded_by)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'draft',
                           $7::uuid)
                        RETURNING id::text
                        """,
                        cid,
                        vid,
                        con_id,
                        s["service_code"],
                        s["name"],
                        s["node_code"],
                        identity.staff_id,
                    )
                )
            await record_event(
                conn,
                event_type="orders.drafted",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids, "versions": {oid: 1 for oid in ids}}
            await self._receipt_put(
                conn, identity, "orders.draft", idempotency_key, payload, con_id, result
            )
        return result

    async def authorize_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str] | None,
        draft_order_ids: list[str] | None,
        identity: StaffIdentity,
        expected_versions: dict[str, int] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DOCTOR_ROLES, "Chỉ bác sĩ duyệt chỉ định được.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        codes = list(service_codes or [])
        drafts = [
            _uuid(d, "Mã chỉ định nháp không hợp lệ.") for d in (draft_order_ids or [])
        ]
        if not codes and not drafts:
            raise ValidationError("Chưa chọn dịch vụ nào để duyệt.")
        versions = dict(expected_versions or {})
        if drafts and (
            set(versions) != set(drafts)
            or any(type(v) is not int or v < 1 for v in versions.values())
        ):
            raise LuotKhamConflictError(
                "DRAFT_VERSION_REQUIRED",
                "Cần phiên bản hiện tại của từng chỉ định nháp.",
            )
        payload = {
            "consultation_id": con_id,
            "codes": codes,
            "drafts": sorted(drafts),
            "expected_versions": versions,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.authorize", idempotency_key, payload
            )
            if cached is not None:
                return cached
            consultation = await self._consultation_in_progress(conn, cid, con_id)
            # Bác sĩ của phiên duyệt được kể cả khi thư ký là người bấm "Bắt đầu".
            if identity.staff_id not in (
                consultation["doctor_id"],
                consultation["started_by"],
            ) or not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM staff s JOIN clinic_membership m"
                " ON m.staff_id = s.id WHERE s.id = $1::uuid AND s.is_active"
                " AND m.clinic_id = $2::uuid AND m.is_active"
                " AND m.role = 'DOCTOR')",
                identity.staff_id,
                cid,
            ):
                raise SafetyGateError(
                    "Chỉ bác sĩ đang phụ trách phiên khám được duyệt chỉ định."
                )
            ids: list[str] = []
            if drafts:
                selected = await conn.fetch(
                    "SELECT id::text AS id, version, exec_status FROM service_order"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND consultation_id = $3::uuid AND id = ANY($4::uuid[])"
                    " ORDER BY id FOR UPDATE",
                    cid,
                    vid,
                    con_id,
                    drafts,
                )
                if len(selected) != len(set(drafts)) or any(
                    row["exec_status"] != "draft" for row in selected
                ):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Chỉ định nháp không thuộc phiên khám này hoặc đã xử lý.",
                    )
                if any(row["version"] != versions[row["id"]] for row in selected):
                    raise LuotKhamConflictError(
                        "VERSION_CONFLICT",
                        "Chỉ định nháp đã thay đổi — tải lại trước khi duyệt.",
                    )
                flipped = await conn.fetch(
                    """
                    UPDATE service_order
                       SET exec_status = 'authorized', authorized_by = $4::uuid,
                           authorized_at = now(), version = version + 1,
                              updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[]) AND exec_status = 'draft'
                       AND consultation_id = $5::uuid
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    drafts,
                    identity.staff_id,
                    con_id,
                )
                if len(flipped) != len(set(drafts)):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Có chỉ định nháp không thuộc lượt khám này hoặc đã được xử"
                        " lý.",
                    )
                ids.extend(r["id"] for r in flipped)
            if codes:
                for s in await self._services(conn, cid, codes):
                    ids.append(
                        await conn.fetchval(
                            """
                            INSERT INTO service_order
                                (clinic_id, visit_id, consultation_id, service_code,
                                 service_name, node_code, exec_status, recorded_by,
                                 authorized_by, authorized_at)
                            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
                                    'authorized', $7::uuid, $7::uuid, now())
                            RETURNING id::text
                            """,
                            cid,
                            vid,
                            con_id,
                            s["service_code"],
                            s["name"],
                            s["node_code"],
                            identity.staff_id,
                        )
                    )
            await self._tu_xep_phong(conn, identity, vid)
            await record_event(
                conn,
                event_type="orders.authorized",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids}
            await self._receipt_put(
                conn,
                identity,
                "orders.authorize",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # C11 / C12 — kết thúc phiên khám
    # ------------------------------------------------------------------

    async def complete_consultation(
        self,
        *,
        consultation_id: str,
        outcome: str,
        requirements: list[dict[str, Any]] | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(
            identity,
            CONSULT_ROLES,
            "Chỉ bác sĩ hoặc thư ký đi kèm kết thúc phiên khám được.",
        )
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        reqs: list[tuple[str, str]] = []
        seen: set[str] = set()
        for item in requirements or []:
            if not isinstance(item, dict):
                raise ValidationError("Danh sách yêu cầu không đúng dạng.")
            oid = _uuid(item.get("order_id"), "Mã chỉ định trong yêu cầu không hợp lệ.")
            need = str(item.get("need") or "")
            if need not in rules.NEEDS:
                raise ValidationError(
                    "Mỗi yêu cầu phải chọn mức cần: đã làm hoặc có kết quả."
                )
            if need == "VALID_RESULT":
                raise LuotKhamConflictError(
                    "NEED_NOT_SUPPORTED_YET",
                    "Lát này chưa có nhập kết quả theo phiên bản — chọn mức 'đã làm'.",
                )
            if oid not in seen:
                seen.add(oid)
                reqs.append((oid, need))
        payload = {"consultation_id": con_id, "outcome": outcome, "reqs": sorted(reqs)}
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "consult.complete", idempotency_key, payload
            )
            if cached is not None:
                return cached
            c = await self._consultation_in_progress(conn, cid, con_id)
            await self._thu_ky_cua_bac_si(conn, identity, c["doctor_id"])
            if not rules.outcome_allowed(c["kind"], outcome):
                raise LuotKhamConflictError(
                    "WRONG_CONSULTATION_KIND",
                    "Kết quả này không dùng cho loại phiên khám hiện tại.",
                )
            next_round: int | None = None
            if outcome == "NO_SERVICES":
                live = await conn.fetchval(
                    """
                    SELECT count(*) FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status IN ('authorized', 'assigned', 'in_progress')
                    """,
                    cid,
                    vid,
                )
                if live:
                    raise LuotKhamConflictError(
                        "ORDERS_PENDING",
                        "Còn chỉ định đã duyệt chưa làm — không kết thúc 'không cần"
                        " dịch vụ' được.",
                    )
                await conn.execute(
                    """
                    UPDATE service_order
                       SET exec_status = 'cancelled', cancelled_by = $3::uuid,
                           cancel_reason = 'Nháp không được duyệt khi kết thúc khám',
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status = 'draft'
                    """,
                    cid,
                    vid,
                    identity.staff_id,
                )
            elif outcome in rules.OUTCOMES_OPENING_ROUND:
                if not reqs:
                    raise LuotKhamConflictError(
                        "REQUIREMENTS_REQUIRED",
                        "Chọn ít nhất một dịch vụ phải xong trước lần đọc kết quả.",
                    )
                rows = await conn.fetch(
                    """
                    SELECT id::text AS id, exec_status, hold_until_round
                      FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[])
                    """,
                    cid,
                    vid,
                    [oid for oid, _ in reqs],
                )
                found = {r["id"]: r for r in rows}
                bad = [
                    oid
                    for oid, _ in reqs
                    if oid not in found
                    or found[oid]["exec_status"] in ("draft", "cancelled")
                ]
                if bad:
                    raise LuotKhamConflictError(
                        "REQUIREMENT_ORDER_INVALID",
                        "Yêu cầu trỏ tới chỉ định chưa duyệt, đã huỷ hoặc không"
                        " thuộc lượt này.",
                    )
                next_round = int(c["round_no"]) + 1
                cyclic = rules.cyclic_orders(
                    next_round,
                    [(oid, found[oid]["hold_until_round"]) for oid, _ in reqs],
                )
                if cyclic:
                    raise LuotKhamValidationError(
                        "CYCLIC_REQUIREMENT",
                        "Có dịch vụ vừa bắt buộc trước lần đọc kết quả vừa được dặn"
                        " làm sau lần đọc ấy.",
                    )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'completed', outcome = $3, completed_by = $4::uuid,
                       completed_at = now(), version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                outcome,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                con_id,
            )
            if c["kind"] == "REVIEW":
                await conn.execute(
                    "UPDATE review_round SET status = 'closed', closed_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND"
                    " round_no = $3",
                    cid,
                    vid,
                    c["round_no"],
                )
            if next_round is not None:
                round_id = await conn.fetchval(
                    """
                    INSERT INTO review_round (clinic_id, visit_id, round_no, status,
                       locked_by)
                    VALUES ($1::uuid, $2::uuid, $3, 'collecting', $4::uuid)
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    next_round,
                    identity.staff_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO round_requirement (clinic_id, round_id,
                       service_order_id, need)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
                    """,
                    [(cid, round_id, oid, need) for oid, need in reqs],
                )
            if outcome in ("NO_SERVICES", "DONE"):
                await conn.execute(
                    """
                    UPDATE encounter_flow f
                       SET finished_at = now(), version = f.version + 1,
                          updated_at = now()
                     WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid
                       AND NOT EXISTS (
                           SELECT 1 FROM service_order o
                            WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                              AND o.exec_status IN ('authorized', 'assigned',
                                 'in_progress'))
                    """,
                    cid,
                    vid,
                )
            if outcome in ("NO_SERVICES", "DONE"):
                # BÁC SĨ KÝ KHÁM XONG HẲN = lịch hẹn COMPLETED (demo 17/09/2026).
                # Quầy thu tiền và bước đóng lượt đều đợi mốc này; luồng khám mới
                # chưa từng đặt nó nên lễ tân nhận "Bác sĩ chưa khám xong lượt
                # này" dù bác sĩ đã ký. Chỉ khi không còn chỉ định đang dở.
                hen = await conn.fetchval(
                    """
                    UPDATE appointment a
                       SET status = 'COMPLETED', updated_at = now()
                      FROM visit v
                     WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                       AND a.id = v.appointment_id AND a.clinic_id = v.clinic_id
                       AND a.status = 'CHECKED_IN'
                       AND NOT EXISTS (
                           SELECT 1 FROM service_order o
                            WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                              AND o.exec_status IN ('authorized', 'assigned',
                                 'in_progress'))
                    RETURNING a.id::text
                    """,
                    cid,
                    vid,
                )
                if hen:
                    await conn.execute(
                        "UPDATE visit SET exam_completed_at = coalesce("
                        "exam_completed_at, now()), updated_at = now()"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                        cid,
                        vid,
                    )
                    await record_event(
                        conn,
                        event_type="appointment.completed",
                        aggregate_type="appointment",
                        aggregate_id=hen,
                        identity=identity,
                        origin=ORIGIN,
                        payload={"visit_id": vid, "boi": "luot_kham.kham_xong"},
                    )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.completed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "outcome": outcome,
                    "next_round": next_round,
                },
            )
            result = {"ok": True, "consultation_id": con_id, "next_round": next_round}
            await self._receipt_put(
                conn,
                identity,
                "consult.complete",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # C7 — điều phối chỉ định vào phòng
    # ------------------------------------------------------------------

    async def dispatch_order(
        self,
        *,
        order_id: str,
        room_id: str,
        expected_version: int | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DISPATCH_ROLES, "Chỉ trưởng ca hoặc quản lý điều phối được.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_version": expected_version,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "dispatch.assign", idempotency_key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(
                """
                SELECT exec_status, source, authorized_by::text AS authorized_by,
                       hold_until_round, node_code, version
                  FROM service_order
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                oid,
            )
            assert o is not None
            if expected_version is not None and o["version"] != expected_version:
                raise LuotKhamConflictError(
                    "STALE_VERSION",
                    "Chỉ định vừa được người khác cập nhật — tải lại màn hình.",
                )
            flow = await self._lock_flow(conn, cid, vid)
            closed = {
                int(r["round_no"])
                for r in await conn.fetch(
                    "SELECT round_no FROM review_round"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                    " = 'closed'",
                    cid,
                    vid,
                )
            }
            code = rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            )
            if code:
                raise LuotKhamConflictError(code, _CAU_CHAN_DIEU_PHOI[code])
            version = await self._gan_phong(
                conn, identity, vid=vid, oid=oid, rid=rid, o=o
            )
            result = {"ok": True, "order_id": oid, "version": version}
            await self._receipt_put(
                conn, identity, "dispatch.assign", idempotency_key, payload, oid, result
            )
        return result

    async def _gan_phong(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        rid: str,
        o: asyncpg.Record,
    ) -> int:
        """Đặt một chỉ định (đã qua luật chặn) vào hàng chờ của một phòng."""
        cid = identity.clinic_id
        serves = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                   AND rn.node_code = $3 AND r.is_active AND r.accepting)
            """,
            cid,
            rid,
            o["node_code"],
        )
        if not serves:
            raise LuotKhamConflictError(
                "ROOM_NOT_SERVING", "Phòng đã chọn không làm dịch vụ này."
            )
        if o["exec_status"] == "assigned":
            await conn.execute(
                """
                UPDATE queue_entry
                   SET room_id = $4::uuid, version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
                rid,
            )
        else:
            await self._enqueue(
                conn,
                clinic_id=cid,
                visit_id=vid,
                lane="ROOM",
                reason="SERVICE",
                ref_id=oid,
                room_id=rid,
            )
        version = await conn.fetchval(
            """
            UPDATE service_order
               SET exec_status = 'assigned', room_id = $3::uuid,
                  assigned_by = $4::uuid,
                   assigned_at = now(), version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            RETURNING version
            """,
            cid,
            oid,
            rid,
            identity.staff_id,
        )
        await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
        await record_event(
            conn,
            event_type="dispatch.assigned",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "order_id": oid, "room_id": rid},
        )
        return int(version)

    async def _tu_xep_phong(
        self, conn: asyncpg.Connection, identity: StaffIdentity, vid: str
    ) -> list[str]:
        """Chỉ định vừa duyệt TỰ vào hàng chờ phòng làm được việc ấy.

        Notion "Kế hoạch v1.0.0", vai Trưởng ca: *"Ngay khi chỉ định, hệ thống sẽ
        tự phân bổ người bệnh về các phòng dựa trên tình trạng thực tế"*.

        Chọn phòng: có người đứng trong lịch HÔM NAY trước, rồi phòng ít người
        chờ nhất. Chỉ định nào luật chặn (chưa đo huyết áp, dặn làm sau khi đọc
        kết quả…) hoặc không phòng nào làm được thì ĐỂ NGUYÊN "đã duyệt" — trưởng
        ca thấy và xếp tay. Không bao giờ ném lỗi làm hỏng lệnh duyệt.
        """
        cid = identity.clinic_id
        flow = await self._lock_flow(conn, cid, vid)
        closed = {
            int(r["round_no"])
            for r in await conn.fetch(
                "SELECT round_no FROM review_round"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                " = 'closed'",
                cid,
                vid,
            )
        }
        orders = await conn.fetch(
            """
            SELECT id::text AS id, exec_status, source,
                   authorized_by::text AS authorized_by, hold_until_round,
                   node_code, version
              FROM service_order o
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND exec_status = 'authorized'
               -- Đối tác tự lấy mẫu thì khách không xếp hàng ở phòng nào của
               -- phòng khám — việc ấy nằm trên bàn đối tác.
               AND NOT EXISTS (
                   SELECT 1 FROM service_price sp
                    WHERE sp.clinic_id = o.clinic_id
                      AND sp.service_code = o.service_code
                      AND sp.doi_tac_lay_mau)
             ORDER BY created_at, id
               FOR UPDATE
            """,
            cid,
            vid,
        )
        da_xep: list[str] = []
        for o in orders:
            if rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            ):
                continue
            rid = await conn.fetchval(
                """
                SELECT r.id::text
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND rn.node_code = $2
                   AND r.is_active AND r.accepting AND NOT r.la_doi_tac
                 ORDER BY
                   EXISTS (
                       SELECT 1 FROM work_roster w
                         JOIN vi_tri_lam_viec v
                           ON v.clinic_id = w.clinic_id AND v.code = w.station
                        WHERE w.clinic_id = r.clinic_id AND v.room_id = r.id
                          AND w.status <> 'REJECTED'
                          AND w.work_date
                              = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   ) DESC,
                   (SELECT count(*) FROM queue_entry q
                     WHERE q.clinic_id = r.clinic_id AND q.room_id = r.id
                       AND q.status IN ('blocked', 'waiting', 'called', 'serving')
                   ),
                   r.sort, r.code
                 LIMIT 1
                """,
                cid,
                o["node_code"],
            )
            if rid is None:
                continue
            await self._gan_phong(conn, identity, vid=vid, oid=o["id"], rid=rid, o=o)
            da_xep.append(o["id"])
        return da_xep

    # ------------------------------------------------------------------
    # Kết quả: bác sĩ duyệt theo TỪNG chỉ định
    # ------------------------------------------------------------------

    async def ket_qua_cho_duyet(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Chỉ định đã có kết quả (tệp hoặc nội dung) mà bác sĩ chưa duyệt."""
        _require(identity, REVIEW_ROLES, "Chỉ bác sĩ duyệt kết quả.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT o.id::text AS id, o.service_name, o.node_code,
                       o.result_note, o.ket_qua_luc, o.exec_status,
                       o.visit_id::text AS visit_id,
                       v.appointment_id::text AS appointment_id,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code,
                       d.full_name AS bac_si, v.attending_doctor_id::text AS bac_si_id,
                       pf.full_name AS nguoi_lam
                  FROM service_order o
                  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN staff pf ON pf.id = o.performed_by
                 WHERE o.clinic_id = $1::uuid
                   AND o.ket_qua_luc IS NOT NULL AND o.duyet_luc IS NULL
                   AND o.exec_status NOT IN ('draft', 'cancelled')
                   AND o.created_at > now() - interval '60 days'
                 ORDER BY (v.attending_doctor_id = $2::uuid) DESC NULLS LAST,
                          o.ket_qua_luc, o.id
                 LIMIT 200
                """,
                cid,
                identity.staff_id,
            )
            teps = await conn.fetch(
                """
                SELECT t.id::text AS id, t.service_order_id::text AS order_id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte, t.tai_len_luc
                  FROM tep_ket_qua t
                 WHERE t.clinic_id = $1::uuid
                   AND t.service_order_id = ANY($2::uuid[])
                 ORDER BY t.tai_len_luc
                """,
                cid,
                [r["id"] for r in rows],
            )
        theo: dict[str, list[dict[str, Any]]] = {}
        for t in teps:
            theo.setdefault(t["order_id"], []).append(
                {
                    "id": t["id"],
                    "ten": t["ten_hien_thi"],
                    "loai_tep": t["loai_tep"],
                    "mime": t["mime"],
                    "so_byte": int(t["so_byte"]),
                    "tai_len_luc": _iso(t["tai_len_luc"]),
                }
            )
        return {
            "ket_qua": [
                {
                    "id": r["id"],
                    "dich_vu": r["service_name"],
                    "node_code": r["node_code"],
                    "noi_dung": r["result_note"],
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                    "visit_id": r["visit_id"],
                    "appointment_id": r["appointment_id"],
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "bac_si": r["bac_si"],
                    "cua_toi": r["bac_si_id"] == identity.staff_id,
                    "nguoi_lam": r["nguoi_lam"],
                    "tep": theo.get(r["id"], []),
                }
                for r in rows
            ]
        }

    async def duyet_ket_qua(
        self,
        *,
        order_id: str,
        danh_gia: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Bác sĩ đánh giá + PHÊ DUYỆT CHO GỬI kết quả của một chỉ định.

        Notion v1.0.0: *"Dưới kết quả xét nghiệm sẽ có nút Phê duyệt cho gửi và
        chỗ ghi Đánh giá của bác sĩ"*. Duyệt xong thì mọi tệp của chỉ định ấy
        được phép gửi — CSKH thấy "Đã có kết quả".
        """
        _require(identity, REVIEW_ROLES, "Chỉ bác sĩ duyệt kết quả.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ghi = (danh_gia or "").strip() if isinstance(danh_gia, str) else ""
        if len(ghi) > 5000:
            raise ValidationError("Đánh giá quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await conn.fetchrow(
                "SELECT exec_status, ket_qua_luc, duyet_luc FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            assert o is not None
            if o["duyet_luc"] is not None:
                return {"ok": True, "order_id": oid, "already": True}
            if o["ket_qua_luc"] is None:
                raise LuotKhamConflictError(
                    "NO_RESULT_YET", "Chỉ định này chưa có kết quả để duyệt."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET duyet_luc = now(), duyet_boi = $3::uuid,
                       bac_si_danh_gia = nullif($4, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
                ghi,
            )
            await conn.execute(
                """
                UPDATE tep_ket_qua
                   SET cho_phep_gui_luc = now(), cho_phep_gui_boi_staff_id = $3::uuid
                 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                   AND cho_phep_gui_luc IS NULL
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="result.approved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}

    # ------------------------------------------------------------------
    # Đối tác: hai trạng thái "Chờ lấy mẫu" → "Đã lấy mẫu" → (tải kết quả)
    # ------------------------------------------------------------------

    async def viec_doi_tac(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Việc trên bàn đối tác, gom theo khách.

        Hai loại xét nghiệm (Tuyền 16/09/2026: *"cả 2, tuỳ loại xét nghiệm"*):
          * ĐỐI TÁC TỰ LẤY MẪU (`service_price.doi_tac_lay_mau`) — hiện ngay từ
            lúc bác sĩ duyệt, trạng thái "Chờ lấy mẫu", đối tác bấm "Đã lấy mẫu".
          * ĐIỀU DƯỠNG LẤY — chỉ hiện SAU khi điều dưỡng bấm xong ở phòng Lấy
            mẫu; trước đó ống máu còn chưa có, đối tác chẳng có gì để nhận.
        Có kết quả (tệp đầu tiên) là rời bàn — duyệt và gửi là việc bác sĩ, CSKH.
        """
        if not identity.co_vai((ClinicRole.PARTNER, ClinicRole.MANAGEMENT)):
            raise SafetyGateError("Màn này chỉ dành cho đối tác.")
        rows = await self._pool.fetch(
            """
            SELECT o.id::text AS chi_dinh_id, o.service_code, o.exec_status,
                   coalesce(sp.name, o.service_name) AS ten_dich_vu,
                   coalesce(sp.doi_tac_lay_mau, false) AS doi_tac_lay_mau,
                   p.full_name AS ten_khach, p.patient_code AS ma_khach,
                   p.clinic_patient_id::text AS clinic_patient_id,
                   v.appointment_id::text AS appointment_id,
                   o.created_at, o.finished_at
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
               AND n.lam_ben_ngoai
              LEFT JOIN LATERAL (
                   SELECT s.name, s.doi_tac_lay_mau FROM service_price s
                    WHERE s.clinic_id = o.clinic_id
                      AND s.service_code = o.service_code AND s.active
                    ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
             WHERE o.clinic_id = $1::uuid
               AND o.ket_qua_luc IS NULL
               AND o.created_at > now() - interval '60 days'
               AND (
                    o.exec_status = 'performed'
                 OR (coalesce(sp.doi_tac_lay_mau, false)
                     AND o.exec_status IN ('authorized', 'assigned', 'in_progress'))
               )
             ORDER BY o.created_at, o.id
             LIMIT 200
            """,
            identity.clinic_id,
        )
        khach: dict[str, dict[str, Any]] = {}
        for r in rows:
            k = khach.setdefault(
                r["clinic_patient_id"],
                {
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten_khach": r["ten_khach"],
                    "ma_khach": r["ma_khach"],
                    "cho_tu": None,
                    "viec": [],
                },
            )
            luc = _iso(r["created_at"])
            if luc and (k["cho_tu"] is None or luc < k["cho_tu"]):
                k["cho_tu"] = luc
            k["viec"].append(
                {
                    "chi_dinh_id": r["chi_dinh_id"],
                    "ten_dich_vu": r["ten_dich_vu"],
                    "appointment_id": r["appointment_id"],
                    "chi_dinh_luc": luc,
                    "trang_thai": (
                        "DA_LAY_MAU"
                        if r["exec_status"] == "performed"
                        else "CHO_LAY_MAU"
                    ),
                    "lay_mau_luc": _iso(r["finished_at"]),
                }
            )
        return {"khach": list(khach.values()), "so_viec": len(rows)}

    async def doi_tac_da_lay_mau(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đối tác bấm "Đã lấy mẫu" cho xét nghiệm họ tự lấy."""
        if not identity.co_vai((ClinicRole.PARTNER, ClinicRole.MANAGEMENT)):
            raise SafetyGateError("Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                """
                SELECT o.visit_id::text
                  FROM service_order o
                  JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                   AND n.lam_ben_ngoai
                  JOIN service_price sp
                    ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
                   AND sp.doi_tac_lay_mau
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                """,
                cid,
                oid,
            )
            if vid is None:
                # Một câu cho cả "không có" lẫn "không phải việc đối tác tự lấy".
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            await self._lock_visit(conn, cid, vid)
            trang_thai = await conn.fetchval(
                "SELECT exec_status FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            if trang_thai == "performed":
                return {"ok": True, "already": True}
            if trang_thai not in ("authorized", "assigned", "in_progress"):
                raise LuotKhamConflictError(
                    "ORDER_NOT_OPEN", "Việc này không còn chờ lấy mẫu."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'performed', performed_by = $3::uuid,
                       room_id = coalesce(room_id, (
                           SELECT r.id FROM clinic_room r
                             JOIN clinic_room_node rn
                               ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                            WHERE r.clinic_id = $1::uuid AND r.la_doi_tac
                              AND r.is_active AND rn.node_code = service_order.node_code
                            ORDER BY r.sort LIMIT 1)),
                       assigned_by = coalesce(assigned_by, $3::uuid),
                       assigned_at = coalesce(assigned_at, now()),
                       started_at = coalesce(started_at, now()), finished_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                       updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid AND reason = 'SERVICE'
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                oid,
            )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.performed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid, "doi_tac_lay_mau": True},
            )
        return {"ok": True, "order_id": oid}

    # ------------------------------------------------------------------
    # C8 / C9 — người thực hiện bắt đầu và kết thúc dịch vụ
    # ------------------------------------------------------------------

    async def _order_for_performer(
        self, conn: asyncpg.Connection, identity: StaffIdentity, oid: str
    ) -> asyncpg.Record:
        o = await conn.fetchrow(
            """
            SELECT o.exec_status, o.node_code, o.performed_by::text AS performed_by,
                   n.actor_roles
              FROM service_order o
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
               FOR UPDATE OF o
            """,
            identity.clinic_id,
            oid,
        )
        assert o is not None
        duoc = set(o["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
        if not set(identity.ds_vai()) & duoc:
            raise SafetyGateError("Vai của bạn không thực hiện được dịch vụ này.")
        return o

    async def start_service(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if (
                o["exec_status"] == "in_progress"
                and o["performed_by"] == identity.staff_id
            ):
                return {"ok": True, "order_id": oid, "already": True}
            if o["exec_status"] != "assigned":
                raise LuotKhamConflictError(
                    "ORDER_NOT_ASSIGNED", "Dịch vụ này chưa được điều phối vào phòng."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if (
                entry is None
                or entry["status"] not in ("waiting", "called")
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa làm dịch vụ này được.",
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'in_progress', performed_by = $3::uuid,
                      started_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}

    async def complete_service(
        self,
        *,
        order_id: str,
        performed: bool,
        reason: str | None,
        result_note: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly_do = (reason or "").strip() if isinstance(reason, str) else ""
        ghi = (result_note or "").strip() if isinstance(result_note, str) else ""
        if not performed and not ly_do:
            raise ValidationError("Ghi lý do không thực hiện được dịch vụ.")
        if len(ghi) > 20000 or len(ly_do) > 2000:
            raise ValidationError("Nội dung quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if o["exec_status"] != "in_progress":
                raise LuotKhamConflictError(
                    "ORDER_NOT_IN_PROGRESS", "Dịch vụ này chưa bắt đầu hoặc đã xong."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = $3, finished_at = now(),
                       -- Bác sĩ bấm Xong ⇒ bác sĩ là người thực hiện, kể cả khi
                       -- điều dưỡng đi kèm đã bấm Bắt đầu.
                       performed_by = CASE WHEN $6 THEN $7::uuid
                                           ELSE performed_by END,
                       result_note = nullif($4, ''),
                       ket_qua_luc = CASE WHEN nullif($4, '') IS NOT NULL
                                          THEN coalesce(ket_qua_luc, now())
                                          ELSE ket_qua_luc END,
                          not_performed_reason = nullif($5, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                "performed" if performed else "not_performed",
                ghi,
                ly_do,
                bool(set(identity.ds_vai()) & set(o["actor_roles"] or [])),
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
            )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.performed"
                if performed
                else "service.not_performed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}
