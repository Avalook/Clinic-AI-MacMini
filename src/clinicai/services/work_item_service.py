"""The Command API behind the workflow kernel (W4, ADR-0011, doc §4.3).

A work item never changes because someone PATCHed a status. It changes because
somebody issued a business command — start, complete, skip, cancel — and the
command was allowed. Everything that decides "allowed" lives here:

* the transition is legal for the current status;
* the caller's role is one the node definition names as an actor;
* the blocking dependency gate for that command is open (FS/SS gate `start`,
  FF/SF gate `complete`), evaluated by ``work_item_gate_blockers`` in SQL so no
  caller can route around it;
* nobody else moved the item in the meantime — the UPDATE carries the version
  the caller read, and a lost race is a 409 rather than a silent overwrite.

The status change and its ``work_item_event`` row are written in one
transaction, so history cannot disagree with state.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Literal

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.queue_rows import thu_tu_goi_theo_ngay

logger = structlog.get_logger()

Command = Literal["start", "complete", "skip", "cancel"]

PENDING = "PENDING"
IN_PROGRESS = "IN_PROGRESS"
COMPLETED = "COMPLETED"
SKIPPED = "SKIPPED"
CANCELLED = "CANCELLED"

TERMINAL: frozenset[str] = frozenset({COMPLETED, SKIPPED, CANCELLED})

# command -> (statuses it may be issued from, resulting status)
_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "start": (frozenset({PENDING}), IN_PROGRESS),
    "complete": (frozenset({IN_PROGRESS}), COMPLETED),
    # Skipping and cancelling are decisions available at any point before the
    # item is finished — a nurse can skip vitals she has already started.
    "skip": (frozenset({PENDING, IN_PROGRESS}), SKIPPED),
    "cancel": (frozenset({PENDING, IN_PROGRESS}), CANCELLED),
}

# Only start and complete are gated. Skipping and cancelling are how a stuck
# flow gets unstuck, so a shut gate must never prevent them.
_GATED: dict[str, str] = {"start": "start", "complete": "complete"}


def resolve_transition(command: str) -> tuple[frozenset[str], str]:
    """(statuses the command may be issued from, resulting status).

    Pure, so the state machine is testable without a database.
    """
    try:
        return _TRANSITIONS[command]
    except KeyError:
        raise ValueError(f"Lệnh không hợp lệ: {command!r}") from None


def is_terminal(status: str) -> bool:
    return status in TERMINAL


class WorkItemService:
    """Issue commands against work items."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def issue(
        self,
        *,
        work_item_id: str,
        command: Command,
        identity: StaffIdentity,
        expected_version: int | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        """Run one command. Returns the item's new status and version.

        Raises NotFoundError (404) when the item is not in the caller's clinic,
        SafetyGateError (403) when the caller's role may not act on the node,
        and ConflictError (409) for an illegal transition, a shut gate, or a
        version that someone else has already moved past.
        """
        allowed_from, next_status = resolve_transition(command)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                item = await conn.fetchrow(
                    """
                    SELECT w.id, w.status, w.version, w.node_code, w.clinic_id,
                           n.actor_roles, n.name AS node_name,
                           m.role AS membership_role
                      FROM work_item w
                      JOIN clinic_membership m
                        ON m.clinic_id = w.clinic_id
                       AND m.staff_id = $2::uuid
                       AND m.is_active
                       AND m.clinic_id = $3::uuid
                       AND m.role = $4
                      LEFT JOIN node_definition n
                        ON n.clinic_id = w.clinic_id
                       AND n.code = w.node_code
                     WHERE w.id = $1::uuid
                       AND w.clinic_id = $3::uuid
                     FOR UPDATE OF w
                    """,
                    work_item_id,
                    identity.staff_id,
                    identity.clinic_id,
                    identity.role.value,
                )
                # Both halves of the identity are re-checked against the same
                # active membership. A membership in some other clinic (or a
                # stale role changed after identity resolution) grants nothing.
                if item is None:
                    raise NotFoundError("Không tìm thấy đầu việc")

                current: str = item["status"]
                if current not in allowed_from:
                    raise ConflictError(
                        f"Không thể '{command}' khi đầu việc đang ở "
                        f"trạng thái {current}"
                    )

                actor_roles: list[str] = list(item["actor_roles"] or [])
                membership_role = str(item["membership_role"])
                # The catalogue's empty default means "nobody yet", never
                # "every working role".  Fail closed if configuration is
                # incomplete or the live node no longer names this role.
                if not actor_roles or membership_role not in actor_roles:
                    logger.info(
                        "work_item_role_forbidden",
                        node_code=item["node_code"],
                        role=membership_role,
                        allowed=actor_roles,
                    )
                    raise SafetyGateError(
                        f"Vai trò của bạn không phụ trách bước '{item['node_name']}'"
                    )

                phase = _GATED.get(command)
                if phase is not None:
                    blockers = await conn.fetch(
                        "SELECT node_code, dependency_type "
                        "FROM work_item_gate_blockers($1::uuid, $2)",
                        work_item_id,
                        phase,
                    )
                    if blockers:
                        names = ", ".join(sorted({b["node_code"] for b in blockers}))
                        raise ConflictError(f"Còn bước chưa xong: {names}")

                updated = await conn.fetchrow(
                    """
                    UPDATE work_item
                       SET status      = $2,
                           started_at  = CASE
                                             WHEN $2 = 'IN_PROGRESS' THEN now()
                                             ELSE started_at
                                         END,
                           finished_at = CASE
                                             WHEN $2 IN
                                                  ('COMPLETED', 'SKIPPED', 'CANCELLED')
                                             THEN now()
                                             ELSE finished_at
                                         END,
                           version     = version + 1,
                           updated_at  = now()
                     WHERE id = $1::uuid
                       AND status = $3
                       AND ($4::integer IS NULL OR version = $4::integer)
                       AND clinic_id = $5::uuid
                    RETURNING version
                    """,
                    work_item_id,
                    next_status,
                    current,
                    expected_version,
                    identity.clinic_id,
                )
                if updated is None:
                    raise ConflictError(
                        "Đầu việc vừa được người khác cập nhật — hãy tải lại"
                    )

                await conn.execute(
                    """
                    INSERT INTO work_item_event
                        (clinic_id, work_item_id, command, from_status, to_status,
                         actor_staff_id, actor_role, reason, metadata)
                    VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7, $8, $9)
                    """,
                    identity.clinic_id,
                    work_item_id,
                    command,
                    current,
                    next_status,
                    identity.staff_id,
                    membership_role,
                    reason,
                    json.dumps({"node_code": item["node_code"]}),
                )

        logger.info(
            "work_item_command",
            work_item_id=work_item_id,
            command=command,
            node_code=item["node_code"],
            from_status=current,
            to_status=next_status,
            by_staff_id=identity.staff_id,
            by_role=membership_role,
        )
        return {
            "id": work_item_id,
            "status": next_status,
            "version": updated["version"],
        }

    async def list_for_visit(
        self,
        *,
        visit_id: str,
        identity: StaffIdentity,
    ) -> list[dict[str, object]]:
        """The caller's visit work items, in flow order, with what they may do.

        Joins the LIVE node_definition, not the pinned
        node_definition_version.snapshot. The two can differ, and `issue()`
        authorises from the live row — so displaying the snapshot's actor_roles
        would produce an item that looks actionable to a role the gate then
        refuses. Pinning is for history; authorisation is live, and the read
        path has to agree with the write path or the UI lies.

        Membership is re-checked in the query rather than trusted from the
        identity, the same way issue() does it: the backend bypasses RLS, so
        this join is the only thing standing between a caller and another
        clinic's board.  It also scopes normal roles to nodes they own;
        management and the shift lead are the explicit coordination exception.
        """
        rows = await self._pool.fetch(
            """
            -- Flow order, not alphabetical. Ordering by flow_group sorted the
            -- board kham → sinh_hieu → thu_ngan → tiep_nhan, i.e. "tạo chỉ
            -- định" above the check-in that has to happen first. Depth is
            -- distance from a node nothing depends on, so the board reads in
            -- the order the day actually happens, for any catalogue.
            WITH RECURSIVE depth AS (
                SELECT n.code, 0 AS level
                  FROM node_definition n
                 WHERE n.clinic_id = $2::uuid
                   AND NOT EXISTS (
                       SELECT 1 FROM node_dependency d
                        WHERE d.clinic_id = n.clinic_id
                          AND d.successor_code = n.code)
                UNION
                SELECT d.successor_code, p.level + 1
                  FROM node_dependency d
                  JOIN depth p ON p.code = d.predecessor_code
                 WHERE d.clinic_id = $2::uuid
                   AND p.level < 64          -- a cycle terminates, not hangs
            ),
            flow AS (
                SELECT code, max(level) AS level FROM depth GROUP BY code
            )
            SELECT w.id,
                   w.node_code,
                   w.status,
                   w.priority,
                   w.version,
                   w.assigned_role,
                   w.assigned_to,
                   w.started_at,
                   w.finished_at,
                   n.name        AS node_name,
                   n.flow_group,
                   n.workspace,
                   n.actor_roles,
                   -- Who the step is about. A screen that acts on a visit has
                   -- to be able to name the patient: the order composer read
                   -- this endpoint and had nothing to show, so a doctor picked
                   -- an ultrasound for an unnamed visit. Same join, same shape
                   -- as list_worklist, so both boards name a patient alike.
                   p.clinic_patient_id,
                   p.patient_code,
                   p.full_name,
                   p.date_of_birth,
                   p.gender,
                   p.phone_primary,
                   -- Mine to act on? An empty actor list means "nobody yet"
                   -- in the catalogue, so it must never light up a command.
                   (m.role = ANY (n.actor_roles))     AS actionable_by_me,
                   EXISTS (
                       SELECT 1 FROM work_item_gate_blockers(w.id, 'start')
                   )                                   AS blocked
              FROM work_item w
              JOIN clinic_membership m
                ON m.clinic_id = w.clinic_id
               AND m.staff_id = $3::uuid
               AND m.is_active
               AND m.role = $4
              LEFT JOIN node_definition n
                ON n.clinic_id = w.clinic_id
               AND n.code = w.node_code
              LEFT JOIN patient p
                ON p.clinic_patient_id = w.clinic_patient_id
               AND p.clinic_id = w.clinic_id
              LEFT JOIN flow f ON f.code = w.node_code
             WHERE w.visit_id = $1::uuid
               AND w.clinic_id = $2::uuid
               AND w.status <> 'CANCELLED'
               -- The route guard establishes a normal role owns a current
               -- task on this visit.  Keep the returned rows scoped too: an
               -- otherwise valid reception step must not reveal a doctor's
               -- or cashier's work (or its patient data) on the same visit.
               -- Management and shift leads are the deliberate read-only
               -- cross-station exception.
               AND (m.role IN ('MANAGEMENT', 'TRUONG_CA')
                    OR m.role = ANY(n.actor_roles))
             ORDER BY f.level NULLS LAST, w.node_code
            """,
            visit_id,
            identity.clinic_id,
            identity.staff_id,
            identity.role.value,
        )

        return [
            {
                "id": str(r["id"]),
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "flow_group": r["flow_group"],
                "workspace": r["workspace"],
                "status": r["status"],
                "priority": r["priority"],
                "version": r["version"],
                "assigned_role": r["assigned_role"],
                "assigned_to": str(r["assigned_to"]) if r["assigned_to"] else None,
                "actor_roles": list(r["actor_roles"] or []),
                "actionable_by_me": bool(r["actionable_by_me"]),
                "blocked": bool(r["blocked"]),
                "started_at": r["started_at"],
                "finished_at": r["finished_at"],
                "patient": {
                    "clinic_patient_id": (
                        str(r["clinic_patient_id"]) if r["clinic_patient_id"] else None
                    ),
                    "patient_code": r["patient_code"],
                    "full_name": r["full_name"],
                    "date_of_birth": r["date_of_birth"],
                    "gender": r["gender"],
                    "phone_primary": r["phone_primary"],
                },
            }
            for r in rows
        ]

    async def list_worklist(
        self,
        *,
        workspace: str,
        identity: StaffIdentity,
        day: date | None = None,
        mine_only: bool = False,
    ) -> list[dict[str, object]]:
        """One workspace's open work for a day, across every visit.

        list_for_visit answers "what is left for this patient"; a front desk
        needs the transpose — "who is waiting for me" — and there was no query
        for it, which is why the reception screen had nothing to read.

        The filter is `workspace`, a column the node catalogue already carries
        (bang_dieu_phoi, thu_ngan_dong_luot, khu_dat_lich…). Filtering on that
        rather than on a list of node codes in Python keeps the board
        data-driven: a clinic that adds a node to its reception desk gets it on
        the board without a deploy, which is the same reason instantiate walks
        node_dependency instead of a hard-coded spine.

        Finished work is excluded. A queue is what is still to do; completed
        items belong to the visit's history, which list_for_visit already
        serves.

        `day` is OPTIONAL and defaults to every open item, not to today. The
        first version filtered on created_at::date = today and the board emptied
        itself at midnight: a patient who arrived at 23:50 and was still waiting
        at 00:10 vanished from the desk's screen while she sat in the waiting
        room. Open work does not stop being open because a calendar day ended.
        The parameter stays for looking back at a specific day.
        """
        rows = await self._pool.fetch(
            """
            SELECT w.id,
                   w.node_code,
                   w.status,
                   w.priority,
                   w.version,
                   w.visit_id,
                   w.appointment_id,
                   w.assigned_to,
                   w.assigned_role,
                   w.due_at,
                   w.created_at,
                   w.started_at,
                   n.name        AS node_name,
                   n.actor_roles,
                   p.clinic_patient_id,
                   p.patient_code,
                   p.full_name,
                   p.date_of_birth,
                   p.gender,
                   p.phone_primary,
                   a.queue_number,
                   a.slot_start,
                   a.booking_channel,
                   a.is_priority_slot,
                   -- LOẠI DỊCH VỤ KHÁM. Bàn khám cần biết đây là khám Phụ
                   -- khoa hay Sản khoa để mở đúng biểu mẫu — không có nó thì
                   -- màn hình chỉ biết "đang ở bước nào", không biết "khám gì".
                   st.code       AS service_code,
                   st.name       AS service_name,
                   -- MÃ BIỂU MẪU, không phải mã dịch vụ. Nhiều dịch vụ dùng
                   -- chung một biểu mẫu (Sản 1/2/3 — số là TẦNG — đều dùng SK),
                   -- nên bàn khám phải hỏi cột này chứ không suy từ tên.
                   st.form_code,
                   v.checked_in_at,
                   -- Mốc gọi vào khám: màn hàng đợi cần nó để vẽ nút tròn
                   -- thứ hai ở trạng thái đã-xong, và để đo ĐỒNG HỒ KHÁM
                   -- tách khỏi đồng hồ chờ (Tuyền 20/08/2026).
                   v.exam_started_at,
                   v.status                             AS visit_status,
                   a.doctor_id,
                   -- ĐỘ DÀI KHUNG GIỜ ÁP DỤNG CHO CHÍNH LỊCH NÀY — nguyên
                   -- liệu để suy ra cửa sổ "đến đúng giờ".
                   --
                   -- Dùng `resolve_effective_cap` y như bảng gọi số và như
                   -- trigger sức chứa, KHÔNG đọc thẳng clinic.settings: đây là
                   -- chỗ ba bên phải nói cùng một con số. Bảng của Lễ tân nghĩ
                   -- khung 15 phút trong khi bảng tivi nghĩ 30 là loại lệch
                   -- không ai lần ra được từ triệu chứng.
                   cap.slot_minutes,
                   (m.role = ANY (n.actor_roles))      AS actionable_by_me,
                   EXISTS (
                       SELECT 1 FROM work_item_gate_blockers(w.id, 'start')
                   )                                    AS blocked
              FROM work_item w
              JOIN clinic_membership m
                ON m.clinic_id = w.clinic_id
               AND m.staff_id = $4::uuid
               AND m.is_active
               AND m.role = $5
              JOIN node_definition n
                ON n.clinic_id = w.clinic_id
               AND n.code = w.node_code
               AND n.workspace = $1
              LEFT JOIN patient p
                ON p.clinic_patient_id = w.clinic_patient_id
               AND p.clinic_id = w.clinic_id
              LEFT JOIN appointment a
                ON a.id = w.appointment_id
               AND a.clinic_id = w.clinic_id
              LEFT JOIN visit v
                ON v.visit_id = w.visit_id
               AND v.clinic_id = w.clinic_id
              -- Cùng phòng khám mới ghép: `service_type` có clinic_id riêng, và
              -- một FK một cột không chặn được việc trỏ sang danh mục của phòng
              -- khám khác.
              LEFT JOIN LATERAL public.resolve_effective_cap(
                  w.clinic_id, a.doctor_id, a.slot_start
              ) cap ON a.id IS NOT NULL
              LEFT JOIN service_type st
                ON st.id = a.service_type_id
               AND st.clinic_id = w.clinic_id
             WHERE w.clinic_id = $3::uuid
               AND w.status IN ('PENDING', 'IN_PROGRESS')
               -- A role can be admitted to the workspace because it owns one
               -- node there (for example Reception owns checkout), but that
               -- must not turn into read access to every other station's
               -- financial or clinical rows.  Coordinators are deliberately
               -- the only cross-node exception.
               AND (m.role IN ('MANAGEMENT', 'TRUONG_CA')
                    OR m.role = ANY(n.actor_roles))
               AND ($2::date IS NULL
                    OR (w.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $2)
               AND ($6::boolean IS NOT TRUE
                    OR w.assigned_to = $4::uuid
                    OR m.role = ANY (n.actor_roles))
             ORDER BY w.priority, w.created_at
            """,
            workspace,
            day,
            identity.clinic_id,
            identity.staff_id,
            identity.role.value,
            mine_only,
        )

        # THỨ TỰ GỌI LÀ CỦA BACKEND, KHÔNG PHẢI CỦA MÀN HÌNH.
        #
        # Trước 20/08/2026 màn hàng đợi tự xếp ở trình duyệt theo "ai chờ lâu
        # nhất". Bảng tivi và `/api/v1/queue` thì xếp theo luật thật
        # (`queue_order.py`): ƯT → có kết quả vào lại → có hẹn đến đúng khung →
        # vãng lai/đến muộn. Hai bảng nói hai thứ tự khác nhau, và người ngồi
        # chờ nhìn thấy điều đó ngay: quầy gọi tên một người mà bảng đang để
        # người khác ở đầu.
        #
        # Dùng `thu_tu_goi_theo_ngay` — CÙNG cầu nối mà bảng bác sĩ và lưới tuần
        # đang dùng. Module luật đã cảnh báo: từng có một bản TypeScript chép
        # lại rồi lệch, và bản ấy đã bị xoá. Bản thứ tư ở đây sẽ lặp lại đúng
        # sai lầm đó.
        #
        # Chỉ xếp những dòng CÓ LỊCH HẸN: luật đứng trên `appointment`, còn việc
        # không gắn lịch (nếu có) thì không có khung giờ để so.
        xep = thu_tu_goi_theo_ngay(
            [r for r in rows if r["appointment_id"] is not None],
            id_key="appointment_id",
        )

        def _thu_hang(r: Any) -> dict[str, Any]:
            """Thứ hạng gọi + LÝ DO, hoặc rỗng nếu dòng này không xếp được."""
            appt = r["appointment_id"]
            d = xep.get(str(appt)) if appt else None
            if d is None:
                return {
                    "call_order": None,
                    "call_tier": None,
                    "call_reason": None,
                    "promoted_over": 0,
                }
            return {
                # `call_order` = vị trí trong hàng (0 là người gọi tiếp theo),
                # `call_tier` = làn. Trả cả hai: màn cần cái đầu để XẾP và cái
                # sau để GIẢI THÍCH vì sao ai đó vượt lên.
                "call_order": d.call_order,
                "call_tier": d.call_tier,
                "call_reason": d.call_reason,
                "promoted_over": d.promoted_over,
            }

        return [
            {
                **_thu_hang(r),
                "id": str(r["id"]),
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "status": r["status"],
                "priority": r["priority"],
                "version": r["version"],
                "visit_id": str(r["visit_id"]) if r["visit_id"] else None,
                "appointment_id": (
                    str(r["appointment_id"]) if r["appointment_id"] else None
                ),
                "assigned_to": str(r["assigned_to"]) if r["assigned_to"] else None,
                "assigned_role": r["assigned_role"],
                "actor_roles": list(r["actor_roles"] or []),
                "actionable_by_me": bool(r["actionable_by_me"]),
                "blocked": bool(r["blocked"]),
                "due_at": r["due_at"],
                "created_at": r["created_at"],
                "started_at": r["started_at"],
                "patient": {
                    "clinic_patient_id": (
                        str(r["clinic_patient_id"]) if r["clinic_patient_id"] else None
                    ),
                    "patient_code": r["patient_code"],
                    "full_name": r["full_name"],
                    "date_of_birth": r["date_of_birth"],
                    "gender": r["gender"],
                    "phone_primary": r["phone_primary"],
                },
                "queue_number": r["queue_number"],
                "slot_start": r["slot_start"],
                "booking_channel": r["booking_channel"],
                "is_priority_slot": bool(r["is_priority_slot"]),
                "service_code": r["service_code"],
                "service_name": r["service_name"],
                "form_code": r["form_code"],
                "checked_in_at": r["checked_in_at"],
                "exam_started_at": r["exam_started_at"],
            }
            for r in rows
        ]

    async def blockers(
        self,
        *,
        work_item_id: str,
        phase: str,
        identity: StaffIdentity,
    ) -> list[dict[str, str]]:
        """Return blockers only when the item belongs to the active membership."""
        rows = await self._pool.fetch(
            """
            SELECT w.id AS scoped_work_item_id,
                   b.node_code,
                   b.dependency_type
              FROM work_item w
              JOIN clinic_membership m
                ON m.clinic_id = w.clinic_id
               AND m.staff_id = $4::uuid
               AND m.is_active
               AND m.role = $5
              LEFT JOIN LATERAL
                   work_item_gate_blockers(w.id, $2) b ON TRUE
             WHERE w.id = $1::uuid
               AND w.clinic_id = $3::uuid
            """,
            work_item_id,
            phase,
            identity.clinic_id,
            identity.staff_id,
            identity.role.value,
        )
        if not rows:
            # Cross-clinic and nonexistent identifiers are deliberately
            # indistinguishable at this boundary.
            raise NotFoundError("Không tìm thấy đầu việc")
        return [
            {"node_code": r["node_code"], "dependency_type": r["dependency_type"]}
            for r in rows
            if r["node_code"] is not None
        ]
