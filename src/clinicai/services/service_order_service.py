"""Ordering services on a visit — what LUOTKHAM-05 produces.

The doctor picks services; each one is performed by a node the catalogue names
(service_price.node_code), and ordering creates work in that node's room. The
rules that decide which room, whether a service may be ordered at all, and how
several ultrasounds collapse into one visit to the ultrasound room all live in
SQL (order_services), for the same reason instantiation does: they must hold
whoever calls them, and the backend bypasses RLS.

Ordering deliberately does NOT complete LUOTKHAM-05. A doctor often orders,
looks at something, and orders again; closing the step on the first submit would
force her to reopen it, and there is no reopen command. She completes the step
from her board when she is done.
"""

from __future__ import annotations

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.services.route_derivation import derive_route

logger = structlog.get_logger()


class ServiceOrderService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def catalogue(self, *, identity: StaffIdentity) -> list[dict[str, object]]:
        """Orderable services for this clinic.

        Services with no node_code are returned but marked orderable=False, so
        the picker can show them greyed with a reason instead of hiding them —
        a service that has vanished from the list is reported as a bug, while a
        service that is visibly not yet configured is reported as configuration.
        """
        rows = await self._pool.fetch(
            """
            SELECT s.service_code,
                   s.name,
                   s."group",
                   s.category,
                   s.unit_price,
                   s.node_code,
                   n.name AS node_name,
                   n.workspace
              FROM service_price s
              LEFT JOIN node_definition n
                ON n.clinic_id = s.clinic_id AND n.code = s.node_code
             WHERE s.clinic_id = $1::uuid AND s.active
             ORDER BY s.node_code NULLS LAST, s.name
            """,
            identity.clinic_id,
        )
        return [
            {
                "service_code": r["service_code"],
                "name": r["name"],
                "group": r["group"],
                "category": r["category"],
                "unit_price": float(r["unit_price"]) if r["unit_price"] else None,
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "workspace": r["workspace"],
                "orderable": r["node_code"] is not None,
            }
            for r in rows
        ]

    async def duplicates(
        self,
        *,
        visit_id: str,
        codes: list[str],
        identity: StaffIdentity,
        days: int = 30,
    ) -> list[dict[str, object]]:
        """Which of these the patient already had ordered recently."""
        if not codes:
            return []
        patient_id = await self._pool.fetchval(
            "SELECT clinic_patient_id FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            identity.clinic_id,
        )
        if patient_id is None:
            raise NotFoundError("Không tìm thấy lượt khám")

        rows = await self._pool.fetch(
            "SELECT service_code, name, ordered_at "
            "FROM recent_duplicate_services($1::uuid, $2::uuid, $3::text[], $4)",
            identity.clinic_id,
            patient_id,
            codes,
            days,
        )
        return [
            {
                "service_code": r["service_code"],
                "name": r["name"],
                "ordered_at": r["ordered_at"],
            }
            for r in rows
        ]

    async def create(
        self, *, visit_id: str, codes: list[str], identity: StaffIdentity
    ) -> list[dict[str, object]]:
        """Order the services. Returns one row per room the work landed in."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # SERIALISE PER VISIT, INSIDE THE TRANSACTION.
                #
                # order_services() avoids creating a second work item for a node
                # with `WHERE NOT EXISTS (SELECT 1 FROM existing ...)`. That reads
                # and writes in one statement but nothing stands behind it: two
                # overlapping orders both evaluate "not there yet" and both
                # insert. A doctor double-clicking "Chỉ định", or a doctor and a
                # secretary ordering at once, gets the room queue twice.
                #
                # A unique index on (visit_id, node_code) would be the usual
                # answer and is the wrong one here: a visit may legitimately
                # repeat a node — two ultrasounds in one session — so the index
                # would block correct work to stop incorrect work.
                #
                # The advisory lock releases when this transaction ends, and is
                # the same mechanism check_in_appointment uses so two
                # receptionists cannot hand out one queue number.
                await conn.execute(
                    "SELECT order_services_lock_visit($1::uuid)", visit_id
                )
                try:
                    rows = await conn.fetch(
                        "SELECT * FROM order_services("
                        "$1::uuid, $2::uuid, $3::text[], $4::uuid, $5::text)",
                        identity.clinic_id,
                        visit_id,
                        codes,
                        identity.staff_id,
                        identity.role.value,
                    )
                except asyncpg.RaiseError as exc:
                    # The function raises with a message written for a clinician
                    # — it names the service that cannot be ordered. Passing it
                    # through beats replacing it with a generic 409.
                    raise ConflictError(str(exc)) from exc

                await _sync_route(conn, visit_id=visit_id, identity=identity)

        logger.info(
            "services_ordered",
            visit_id=visit_id,
            services=len(codes),
            rooms=len(rows),
            by_staff_id=identity.staff_id,
        )
        return [
            {
                "node_code": r["out_node_code"],
                "work_item_id": str(r["out_work_item_id"]),
                "service_count": r["out_service_count"],
                "created": r["out_created"],
            }
            for r in rows
        ]

    async def charges(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, object]:
        """What this visit owes for, and what has been paid.

        The bill lines come from the work items themselves — every DICHVU node
        carries the services ordered onto it in its payload — because the work
        item IS the order. A separate billing table would be a second truth, and
        the first argument between them would be in front of a patient holding a
        card.

        Amounts are whatever the price list says, INCLUDING nothing: production
        has no prices at all (service_price and drug_catalog are entirely
        unpriced). This returns unit_price as it finds it and reports how many
        lines lack one, so the screen can say so rather than presenting a total
        that quietly means "we could not work it out".
        """
        visit = await self._pool.fetchrow(
            "SELECT visit_id, clinic_patient_id, status FROM visit "
            "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
            visit_id,
            identity.clinic_id,
        )
        if visit is None:
            raise NotFoundError("Không tìm thấy lượt khám")

        rows = await self._pool.fetch(
            """
            SELECT w.node_code,
                   w.status AS node_status,
                   n.name   AS node_name,
                   s ->> 'service_code' AS service_code,
                   s ->> 'name'         AS name,
                   (s ->> 'unit_price')::numeric AS unit_price
              FROM work_item w
              JOIN node_definition n
                ON n.clinic_id = w.clinic_id AND n.code = w.node_code
             CROSS JOIN LATERAL jsonb_array_elements(
                   coalesce(w.payload -> 'services', '[]'::jsonb)) AS s
             WHERE w.clinic_id = $2::uuid
               AND w.visit_id = $1::uuid
               AND w.status <> 'CANCELLED'
             ORDER BY n.name, s ->> 'name'
            """,
            visit_id,
            identity.clinic_id,
        )

        # Voided payments are history, not money. They are returned separately
        # so a cashier can see a correction was made without it counting twice.
        paid = await self._pool.fetch(
            """
            SELECT id, kind, status, amount, paid_at, voided_at, void_reason
              FROM payment
             WHERE clinic_id = $2::uuid AND visit_id = $1::uuid
             ORDER BY paid_at NULLS LAST
            """,
            visit_id,
            identity.clinic_id,
        )

        lines = [
            {
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "node_status": r["node_status"],
                "service_code": r["service_code"],
                "name": r["name"],
                "unit_price": float(r["unit_price"]) if r["unit_price"] else None,
            }
            for r in rows
        ]
        unpriced = sum(1 for line in lines if line["unit_price"] is None)
        subtotal = sum(
            float(line["unit_price"] or 0) for line in lines if line["unit_price"]
        )
        collected = sum(float(p["amount"] or 0) for p in paid if p["voided_at"] is None)

        return {
            "visit_id": str(visit["visit_id"]),
            "visit_status": visit["status"],
            "lines": lines,
            "payments": [
                {
                    "id": str(p["id"]),
                    "kind": p["kind"],
                    "status": p["status"],
                    "amount": float(p["amount"] or 0),
                    "paid_at": p["paid_at"],
                    "voided_at": p["voided_at"],
                    "void_reason": p["void_reason"],
                }
                for p in paid
            ],
            "line_count": len(lines),
            # The number that decides whether the total may be shown at all.
            "unpriced_lines": unpriced,
            "subtotal": subtotal,
            "collected": collected,
            "outstanding": subtotal - collected,
        }


async def _sync_route(
    conn: asyncpg.Connection, *, visit_id: str, identity: StaffIdentity
) -> None:
    """Cập nhật tuyến điều phối cho khớp với chỉ định vừa đặt.

    Bảng Trưởng ca đọc "bước kế tiếp" từ `visit_route`, và trước thay đổi này
    tuyến chỉ được ghi khi có người bấm tay — nên trên prod 0/25 lượt khám có
    tuyến, và cột gợi ý trống với mọi bệnh nhân. Chỉ định chính là thứ quyết
    định bệnh nhân phải đi đâu, nên nó ghi luôn tuyến.

    KHÔNG ĐÈ TUYẾN NGƯỜI TA ĐÃ SỬA TAY. Trưởng ca đổi tuyến giữa chừng phải ghi
    lý do (`is_exception`), tức là một quyết định có chủ ý của con người, có khi
    trái với chỉ định — đè lên nó là xoá một quyết định lâm sàng bằng một tác
    dụng phụ.
    """
    manual = await conn.fetchval(
        "SELECT 1 FROM public.visit_route"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL AND is_exception",
        visit_id,
    )
    if manual:
        return

    pending = await conn.fetch(
        "SELECT node_code FROM public.work_item"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND status IN ('PENDING', 'IN_PROGRESS')"
        " ORDER BY created_at",
        identity.clinic_id,
        visit_id,
    )
    templates = await conn.fetch(
        "SELECT steps FROM public.route_template"
        " WHERE clinic_id = $1::uuid AND is_active",
        identity.clinic_id,
    )
    steps = derive_route(
        [r["node_code"] for r in pending],
        [list(t["steps"]) for t in templates],
    )
    if not steps:
        # visit_route_has_steps đòi ít nhất một bước. Không có gì để đi thì
        # không có tuyến — và tuyến cũ (nếu có) vẫn đúng, cứ để nguyên.
        return

    done = await conn.fetchval(
        "SELECT coalesce(array_agg(node_code), '{}') FROM public.work_item"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND status = 'COMPLETED'",
        identity.clinic_id,
        visit_id,
    )
    current = await conn.fetchval(
        "SELECT steps FROM public.visit_route"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL",
        visit_id,
    )
    if current is not None and list(current) == steps:
        # Chỉ định thêm một dịch vụ cùng khoa phòng thì tuyến không đổi. Ghi
        # một dòng y hệt chỉ làm lịch sử tuyến dài ra mà không nói thêm gì.
        return

    await conn.execute(
        "UPDATE public.visit_route SET superseded_at = now()"
        " WHERE visit_id = $1::uuid AND superseded_at IS NULL",
        visit_id,
    )
    await conn.execute(
        """
        INSERT INTO public.visit_route
            (clinic_id, visit_id, template_id, steps, kept_steps,
             is_exception, reason, applied_by)
        VALUES ($1::uuid, $2::uuid, NULL, $3, $4, FALSE, $5, $6::uuid)
        """,
        identity.clinic_id,
        visit_id,
        steps,
        list(done or []),
        "Suy ra từ chỉ định của bác sĩ",
        identity.auth_user_id,
    )
