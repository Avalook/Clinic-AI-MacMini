"""Payment service: authoritative record/void of visit payments (Phase 4, cluster #3).

Ported from the Next.js route ``src/dashboard/app/api/payment/route.ts`` so the payment
rule lives in the backend instead of the frontend. Rules preserved 1:1:

* Two payment kinds per visit — ``thuoc`` (pharmacy) + ``dich_vu`` (services),
  unique per ``(visit_id, kind)``. Recording is an upsert (status ``PAID``).
* A payment may only be recorded once the visit's appointment is ``COMPLETED``
  (the doctor has finished the exam) → otherwise 409. Void is NOT gated.
* Role → kinds: CASHIER_THUOC ⟶ {thuoc}, CASHIER_DV ⟶ {dich_vu},
  CASHIER/MANAGEMENT ⟶ both. Coarse role gate is done at the router with
  ``require_role``; this finer kind↔role check lives here.

The acting staff is the *server-verified* identity (``StaffIdentity.staff_id``),
not a client-supplied cookie.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import pos_outbox

logger = structlog.get_logger()

PAYMENT_KINDS: frozenset[str] = frozenset({"thuoc", "dich_vu"})
COMPLETED_STATUS = "COMPLETED"


def allowed_kinds(role: ClinicRole) -> frozenset[str]:
    """Return payment kinds a role may act on.

    This mirrors ``allowedKinds`` in the dashboard payment route.
    """
    if role is ClinicRole.CASHIER_THUOC:
        return frozenset({"thuoc"})
    if role is ClinicRole.CASHIER_DV:
        return frozenset({"dich_vu"})
    if role in (ClinicRole.CASHIER, ClinicRole.MANAGEMENT):
        return PAYMENT_KINDS
    return frozenset()


def normalize_amount(raw: object) -> int | None:
    """Round a finite, non-negative number to an int; anything else → None.

    Mirrors the frontend ``Number.isFinite(x) && x >= 0 ? Math.round(x) : null``.
    ``bool`` is rejected even though it is an ``int`` subclass.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and math.isfinite(raw) and raw >= 0:
        return round(raw)
    return None


class PaymentService:
    """Record and void visit payments over the asyncpg pool."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def _assert_kind_allowed(self, kind: str, identity: StaffIdentity) -> None:
        if kind not in PAYMENT_KINDS:
            raise SafetyGateError(f"Loại thanh toán không hợp lệ: {kind!r}")
        if kind not in allowed_kinds(identity.role):
            logger.info("payment_kind_forbidden", role=identity.role.value, kind=kind)
            raise SafetyGateError("Vai trò của bạn không được thu loại thanh toán này")

    async def record_payment(
        self,
        *,
        visit_id: str,
        kind: str,
        amount: object,
        clinic_patient_id: str | None,
        identity: StaffIdentity,
    ) -> None:
        """Upsert a PAID payment for ``(visit_id, kind)``.

        Raises SafetyGateError (403) if the kind is not allowed for the role,
        NotFoundError (404) if the visit/appointment is missing, and
        ConflictError (409) if the appointment is not yet COMPLETED.
        """
        self._assert_kind_allowed(kind, identity)

        status_row = await self._pool.fetchrow(
            """
            SELECT a.status AS appt_status
            FROM visit v
            JOIN appointment a ON a.id = v.appointment_id
            WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
            """,
            visit_id,
            identity.clinic_id,
        )
        if status_row is None:
            raise NotFoundError("Không tìm thấy lượt khám để thu tiền")
        if status_row["appt_status"] != COMPLETED_STATUS:
            raise ConflictError("Bác sĩ chưa khám xong lượt này — chưa thể thu tiền")

        normalized = normalize_amount(amount)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                payment_id = await conn.fetchval(
                    """
                    INSERT INTO payment (
                        clinic_id, visit_id, clinic_patient_id, kind, status,
                        amount, paid_by_staff_id, paid_at, updated_at
                    )
                    VALUES ($6::uuid, $1::uuid, $2::uuid, $3, 'PAID', $4, $5::uuid,
                            now(), now())
                    ON CONFLICT (visit_id, kind) DO UPDATE SET
                        clinic_patient_id = EXCLUDED.clinic_patient_id,
                        amount            = EXCLUDED.amount,
                        status            = 'PAID',
                        paid_by_staff_id  = EXCLUDED.paid_by_staff_id,
                        paid_at           = now(),
                        updated_at        = now()
                    RETURNING id
                    """,
                    visit_id,
                    clinic_patient_id,
                    kind,
                    normalized,
                    identity.staff_id,
                    identity.clinic_id,
                )
                # Transactional outbox (ADR-0010): queued with the payment, so
                # the push cannot be lost, and pushed later, so an external POS
                # being down cannot fail the cashier. No adapter is imported
                # here — this is an INSERT, not an integration.
                await pos_outbox.enqueue(
                    conn,
                    kind=pos_outbox.INVOICE,
                    subject_id=str(payment_id),
                    payload={
                        "clinic_reference": str(payment_id),
                        "kind": kind,
                        "total_amount": normalized,
                        "paid_at": datetime.now(timezone.utc),
                        "patient_reference": clinic_patient_id,
                        "visit_id": visit_id,
                    },
                    clinic_id=identity.clinic_id,
                )
        logger.info(
            "payment_recorded",
            visit_id=visit_id,
            kind=kind,
            by_staff_id=identity.staff_id,
        )

    async def void_payment(
        self,
        *,
        visit_id: str,
        kind: str,
        identity: StaffIdentity,
    ) -> None:
        """Delete the payment row for ``(visit_id, kind)``. Not gated on exam status."""
        self._assert_kind_allowed(kind, identity)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                payment_id = await conn.fetchval(
                    "DELETE FROM payment WHERE visit_id = $1::uuid AND kind = $2 "
                    "AND clinic_id = $3::uuid RETURNING id",
                    visit_id,
                    kind,
                    identity.clinic_id,
                )
                if payment_id is not None:
                    # A POS that was told about the invoice has to be told it is
                    # void; one that never heard of it will no-op.
                    await pos_outbox.enqueue(
                        conn,
                        kind=pos_outbox.INVOICE_VOID,
                        subject_id=str(payment_id),
                        payload={
                            "clinic_reference": str(payment_id),
                            "kind": kind,
                            "visit_id": visit_id,
                        },
                        clinic_id=identity.clinic_id,
                    )
        logger.info(
            "payment_voided",
            visit_id=visit_id,
            kind=kind,
            by_staff_id=identity.staff_id,
        )
