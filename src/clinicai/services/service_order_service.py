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
