"""Specialty exam forms attached to a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/clinical-form/route.ts``. The rule that
matters is the finalisation gate:

    A visit with status FINALIZED is READ-ONLY. Correcting a closed record goes
    through the amendment flow (ADR-0008) — never by editing the form and never
    by quietly flipping visit.status back.

The route enforced that in the application layer because the append-only
migration was still pending. It is enforced here for the same reason, and the
comment is kept so nobody mistakes it for belt-and-braces.

ONE DELIBERATE DIFFERENCE from the route. The Next version rejected a
service_code that had no *rendering schema* in ``lib/form-schemas`` — a frontend
registry the backend cannot see. Here the code is validated against the clinic's
own ``service_type`` catalogue, which is the real list. The frontend keeps its
own check before offering the form, so a code with no UI still cannot be reached
by a user. Moving form schemas into the database is the proper fix and is
already anticipated by ADR-0011 (config as data).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

FINALIZED = "FINALIZED"


def actor_label(identity: StaffIdentity) -> str:
    """``created_by``/``updated_by`` are free text; keep the route's format."""
    return f"{identity.role.value} · {identity.staff_id}"


def coerce_form_data(raw: Any) -> dict[str, Any]:
    """A form response is an object. Anything else is stored as an empty one.

    Mirrors the route: a list or a scalar is not a partially-valid form, and
    guessing at it would put unreadable data on a clinical record.
    """
    if isinstance(raw, dict):
        return raw
    return {}


class ClinicalFormService:
    """Read and upsert specialty exam forms."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_form(self, *, visit_id: str, service_code: str) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT form_data, updated_at
              FROM clinical_form_response
             WHERE visit_id = $1::uuid AND service_code = $2
            """,
            visit_id,
            service_code.upper(),
        )
        if row is None:
            return {"form_data": {}, "updated_at": None}
        return {
            "form_data": _as_dict(row["form_data"]),
            "updated_at": row["updated_at"],
        }

    async def save_form(
        self,
        *,
        visit_id: str,
        service_code: str,
        form_data: Any,
        identity: StaffIdentity,
    ) -> None:
        """Upsert one form for one visit. Refuses once the visit is finalised."""
        code = (service_code or "").strip().upper()
        if not code:
            raise ValidationError("Thiếu service_code")

        payload = coerce_form_data(form_data)
        actor = actor_label(identity)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                visit = await conn.fetchrow(
                    "SELECT visit_id, status FROM visit WHERE visit_id = $1::uuid",
                    visit_id,
                )
                if visit is None:
                    raise NotFoundError("Không tìm thấy buổi khám")
                if visit["status"] == FINALIZED:
                    raise ConflictError(
                        "Hồ sơ đã chốt (FINALIZED) — luật cấm sửa. "
                        "Phải đính chính qua luồng AMENDED."
                    )

                known_code = await conn.fetchval(
                    "SELECT 1 FROM service_type WHERE upper(code) = $1 LIMIT 1", code
                )
                if not known_code:
                    raise ValidationError(f"Mã dịch vụ không có trong danh mục: {code}")

                # created_by is stamped once and never overwritten — it answers
                # "who opened this form", which an update must not rewrite.
                await conn.execute(
                    """
                    INSERT INTO clinical_form_response
                        (visit_id, service_code, form_data, created_by, updated_by)
                    VALUES ($1::uuid, $2, $3, $4, $4)
                    ON CONFLICT ON CONSTRAINT uq_clinical_form_visit_service
                    DO UPDATE SET
                        form_data  = EXCLUDED.form_data,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = now()
                    """,
                    visit_id,
                    code,
                    json.dumps(payload),
                    actor,
                )

        logger.info(
            "clinical_form_saved",
            visit_id=visit_id,
            service_code=code,
            by_staff_id=identity.staff_id,
        )


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}
