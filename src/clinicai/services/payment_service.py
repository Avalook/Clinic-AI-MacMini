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

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError

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
            WHERE v.visit_id = $1::uuid
            """,
            visit_id,
        )
        if status_row is None:
            raise NotFoundError("Không tìm thấy lượt khám để thu tiền")
        if status_row["appt_status"] != COMPLETED_STATUS:
            raise ConflictError("Bác sĩ chưa khám xong lượt này — chưa thể thu tiền")

        await self._pool.execute(
            """
            INSERT INTO payment (
                visit_id, clinic_patient_id, kind, status,
                amount, paid_by_staff_id, paid_at, updated_at
            )
            VALUES ($1::uuid, $2::uuid, $3, 'PAID', $4, $5::uuid, now(), now())
            ON CONFLICT (visit_id, kind) DO UPDATE SET
                clinic_patient_id = EXCLUDED.clinic_patient_id,
                amount            = EXCLUDED.amount,
                status            = 'PAID',
                paid_by_staff_id  = EXCLUDED.paid_by_staff_id,
                paid_at           = now(),
                updated_at        = now()
            """,
            visit_id,
            clinic_patient_id,
            kind,
            normalize_amount(amount),
            identity.staff_id,
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
        await self._pool.execute(
            "DELETE FROM payment WHERE visit_id = $1::uuid AND kind = $2",
            visit_id,
            kind,
        )
        logger.info(
            "payment_voided",
            visit_id=visit_id,
            kind=kind,
            by_staff_id=identity.staff_id,
        )
