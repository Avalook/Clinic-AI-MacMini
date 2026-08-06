"""Specialty exam forms attached to a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/clinical-form/route.ts``. The rule that
matters is the finalisation gate:

    A visit with status FINALIZED is READ-ONLY. Correcting a closed record goes
    through the amendment flow (ADR-0008) — never by editing the form and never
    by quietly flipping visit.status back.

The route enforced that in the application layer because the append-only
migration was still pending. It is enforced here for the same reason, and the
comment is kept so nobody mistakes it for belt-and-braces.

WHICH LIST THE CODE IS CHECKED AGAINST. ``service_code`` is a FORM code — PK,
SK, NT, HMVS, NK — not a ``service_type`` code. ClinicalRecordForm derives it
from the service *name* via ``resolveServiceCode`` and ServiceFormEngine sends
it, so that is what the column has always held.

This first validated against ``service_type`` instead, on the reasoning that the
backend cannot see ``lib/form-schemas``. That reasoning was right and the
conclusion was wrong: the two vocabularies do not intersect, so every save
failed once the route was switched over — the catalogue code refused by Next,
the UI's code refused here. The list of forms now lives in
``clinical_form_catalogue`` (migration 20260730000011), which is the fix ADR-0011
anticipated: config as data, readable by both sides. Rendering stays in the
frontend; this only answers whether the clinic uses that form at all.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event

logger = structlog.get_logger()

# Trạng thái lượt khám còn GHI ĐƯỢC hồ sơ.
#
# Danh sách TRẮNG, không phải kiểm `!= FINALIZED`. Cố ý: một trạng thái CUỐI
# thêm sau này sẽ không lọt qua được, còn danh sách đen thì lọt.
#
# INCOMPLETE (khách về giữa chừng) nằm TRONG danh sách này. Nó là trạng thái
# KHÔNG-CUỐI: khách còn quay lại, và khoá bút lúc này là bắt bác sĩ phải đính
# chính một hồ sơ chưa ai ký. FINALIZED và AMENDED thì bất biến theo Thông tư 13.
WRITABLE_VISIT_STATUSES: frozenset[str] = frozenset(
    {"OPEN", "IN_PROGRESS", "INCOMPLETE"}
)


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

    async def get_form(
        self, *, visit_id: str, service_code: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        row = await self._pool.fetchrow(
            """
            SELECT form_data, updated_at
              FROM clinical_form_response
             WHERE visit_id = $1::uuid AND service_code = $2
               AND clinic_id = $3::uuid
            """,
            visit_id,
            service_code.upper(),
            identity.clinic_id,
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
                    "SELECT visit_id, status FROM visit "
                    "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
                    visit_id,
                    identity.clinic_id,
                )
                if visit is None:
                    raise NotFoundError("Không tìm thấy buổi khám")
                if visit["status"] not in WRITABLE_VISIT_STATUSES:
                    raise ConflictError(
                        "Hồ sơ không còn ở trạng thái cho phép sửa — luật cấm sửa. "
                        "Phải đính chính qua luồng AMENDED."
                    )

                known_code = await conn.fetchval(
                    "SELECT 1 FROM clinical_form_catalogue "
                    "WHERE form_code = $1 AND is_active "
                    "AND clinic_id = $2::uuid "
                    "LIMIT 1",
                    code,
                    identity.clinic_id,
                )
                if not known_code:
                    raise ValidationError(f"Phòng khám chưa dùng phiếu: {code}")

                # created_by is stamped once and never overwritten — it answers
                # "who opened this form", which an update must not rewrite.
                await conn.execute(
                    """
                    INSERT INTO clinical_form_response
                        (clinic_id, visit_id, service_code, form_data,
                         created_by, updated_by)
                    VALUES ($5::uuid, $1::uuid, $2, $3, $4, $4)
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
                    identity.clinic_id,
                )

                # Phiếu khám là ghi chép lâm sàng. Lưu MÃ phiếu và các nhóm
                # trường đã điền, KHÔNG lưu giá trị — /audit-log mở cho vai vận
                # hành, còn nội dung phiếu thì không.
                await record_event(
                    conn,
                    event_type="clinical_form.saved",
                    aggregate_type="clinical_form_response",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin="api:clinical-form",
                    payload={
                        "visit_id": visit_id,
                        "service_code": code,
                        "field_groups": (
                            sorted(payload.keys()) if isinstance(payload, dict) else []
                        ),
                    },
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
