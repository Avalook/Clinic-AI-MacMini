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

import json
import math
from datetime import datetime, timezone

import asyncpg
import structlog

from clinicai.api.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import pos_outbox

logger = structlog.get_logger()

PAYMENT_KINDS: frozenset[str] = frozenset({"thuoc", "dich_vu"})
COMPLETED_STATUS = "COMPLETED"
MIN_VOID_REASON_LENGTH = 5
MAX_VOID_REASON_LENGTH = 500


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
    """Round a finite, positive number to an int; anything else → None.

    A payment for zero đồng is not a payment. ``bool`` is rejected even though
    it is an ``int`` subclass.
    """
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)) and math.isfinite(raw):
        rounded = round(raw)
        return rounded if rounded > 0 else None
    return None


def normalize_void_reason(raw: object) -> str | None:
    """Return a trimmed, bounded financial-reversal reason or ``None``."""
    if not isinstance(raw, str):
        return None
    normalized = raw.strip()
    if not MIN_VOID_REASON_LENGTH <= len(normalized) <= MAX_VOID_REASON_LENGTH:
        return None
    return normalized


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

        normalized = normalize_amount(amount)
        if normalized is None:
            raise ValidationError("Số tiền phải là số hữu hạn lớn hơn 0")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                status_row = await conn.fetchrow(
                    """
                    SELECT
                        a.status AS appt_status,
                        v.clinic_patient_id,
                        EXISTS (
                            SELECT 1
                              FROM clinic_membership m
                             WHERE m.staff_id = $3::uuid
                               AND m.clinic_id = v.clinic_id
                               AND m.is_active
                        ) AS staff_in_clinic
                      FROM visit v
                      JOIN appointment a
                        ON a.id = v.appointment_id
                       AND a.clinic_id = v.clinic_id
                       AND a.clinic_patient_id = v.clinic_patient_id
                      JOIN patient p
                        ON p.clinic_patient_id = v.clinic_patient_id
                       AND p.clinic_id = v.clinic_id
                     WHERE v.visit_id = $1::uuid
                       AND v.clinic_id = $2::uuid
                     FOR UPDATE OF v, a
                    """,
                    visit_id,
                    identity.clinic_id,
                    identity.staff_id,
                )
                if status_row is None:
                    raise NotFoundError("Không tìm thấy lượt khám để thu tiền")
                if not status_row["staff_in_clinic"]:
                    raise ValidationError(
                        "Nhân viên thu tiền không thuộc phòng khám này"
                    )
                authoritative_patient_id = str(status_row["clinic_patient_id"])
                if (
                    clinic_patient_id is not None
                    and clinic_patient_id != authoritative_patient_id
                ):
                    raise ValidationError(
                        "Lượt khám không thuộc bệnh nhân thanh toán này"
                    )
                if status_row["appt_status"] != COMPLETED_STATUS:
                    raise ConflictError(
                        "Bác sĩ chưa khám xong lượt này — chưa thể thu tiền"
                    )

                existing_payment = await conn.fetchrow(
                    """
                    SELECT id, status, amount, payment_cycle_id,
                           clinic_patient_id
                      FROM payment
                     WHERE visit_id = $1::uuid
                       AND kind = $2
                       AND clinic_id = $3::uuid
                     FOR UPDATE
                    """,
                    visit_id,
                    kind,
                    identity.clinic_id,
                )
                if (
                    existing_payment is not None
                    and existing_payment["status"] == "PAID"
                ):
                    if (
                        str(existing_payment["clinic_patient_id"] or "")
                        != authoritative_patient_id
                    ):
                        raise ConflictError(
                            "Khoản đã thu đang gắn sai bệnh nhân — "
                            "hãy hoàn tác trước khi thu lại"
                        )
                    if existing_payment["amount"] != normalized:
                        raise ConflictError(
                            "Khoản này đã thu với số tiền khác — "
                            "hãy hoàn tác trước khi thu lại"
                        )
                    # An identical retry is already durable and its POS invoice
                    # is already queued. Rewriting paid_at/actor would create a
                    # false second collection while the outbox correctly dedups.
                    return

                payment = await conn.fetchrow(
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
                        payment_cycle_id  = gen_random_uuid(),
                        voided_at          = NULL,
                        voided_by_staff_id = NULL,
                        void_reason        = NULL,
                        updated_at        = now()
                    WHERE payment.status = 'VOIDED'
                    RETURNING id, payment_cycle_id
                    """,
                    visit_id,
                    authoritative_patient_id,
                    kind,
                    normalized,
                    identity.staff_id,
                    identity.clinic_id,
                )
                if payment is None:
                    # A concurrent collector inserted the same unique
                    # (visit, kind) after our SELECT. Never overwrite it.
                    raise ConflictError(
                        "Khoản thanh toán vừa được người khác ghi, hãy tải lại"
                    )
                payment_id = str(payment["id"])
                payment_cycle_id = str(payment["payment_cycle_id"])
                # Transactional outbox (ADR-0010): queued with the payment, so
                # the push cannot be lost, and pushed later, so an external POS
                # being down cannot fail the cashier. No adapter is imported
                # here — this is an INSERT, not an integration.
                await pos_outbox.enqueue(
                    conn,
                    kind=pos_outbox.INVOICE,
                    subject_id=payment_cycle_id,
                    payload={
                        "clinic_reference": payment_cycle_id,
                        "payment_id": payment_id,
                        "kind": kind,
                        "total_amount": normalized,
                        "paid_at": datetime.now(timezone.utc),
                        "patient_reference": authoritative_patient_id,
                        "visit_id": visit_id,
                    },
                    clinic_id=identity.clinic_id,
                )
                await _log_payment_event(
                    conn,
                    event_type="payment.recorded",
                    payment_id=payment_id,
                    payment_cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    amount=normalized,
                    identity=identity,
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
        reason: object,
        identity: StaffIdentity,
    ) -> None:
        """Soft-void a payment, retaining the row and an immutable audit event."""
        self._assert_kind_allowed(kind, identity)
        normalized_reason = normalize_void_reason(reason)
        if normalized_reason is None:
            raise ValidationError("Lý do hoàn tác phải có từ 5 đến 500 ký tự")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                payment = await conn.fetchrow(
                    """
                    UPDATE payment
                       SET status = 'VOIDED',
                           voided_at = now(),
                           voided_by_staff_id = $4::uuid,
                           void_reason = $5,
                           updated_at = now()
                     WHERE visit_id = $1::uuid
                       AND kind = $2
                       AND clinic_id = $3::uuid
                       AND status = 'PAID'
                    RETURNING id, amount, payment_cycle_id,
                              paid_by_staff_id, paid_at
                    """,
                    visit_id,
                    kind,
                    identity.clinic_id,
                    identity.staff_id,
                    normalized_reason,
                )
                if payment is not None:
                    payment_id = str(payment["id"])
                    payment_cycle_id = str(payment["payment_cycle_id"])
                    # Serialize this void with any relay currently delivering
                    # the invoice for the same payment cycle. If void wins, the
                    # pending invoice becomes DEAD before a stale relay can
                    # send it; if relay wins, invoice completes before void.
                    await conn.execute(
                        """
                        SELECT pg_advisory_xact_lock(
                            hashtextextended($1::text, 0)
                        )
                        """,
                        pos_outbox.causal_lock_name(payment_cycle_id),
                    )
                    await pos_outbox.cancel_pending_invoice(
                        conn,
                        subject_id=payment_cycle_id,
                        clinic_id=identity.clinic_id,
                    )
                    # A POS that was told about the invoice has to be told it is
                    # void; one that never heard of it will no-op.
                    await pos_outbox.enqueue(
                        conn,
                        kind=pos_outbox.INVOICE_VOID,
                        subject_id=payment_cycle_id,
                        payload={
                            "clinic_reference": payment_cycle_id,
                            "payment_id": payment_id,
                            "kind": kind,
                            "visit_id": visit_id,
                            "void_reason": normalized_reason,
                        },
                        clinic_id=identity.clinic_id,
                    )
                    await _log_payment_event(
                        conn,
                        event_type="payment.voided",
                        payment_id=payment_id,
                        payment_cycle_id=payment_cycle_id,
                        visit_id=visit_id,
                        kind=kind,
                        amount=payment["amount"],
                        identity=identity,
                        void_reason=normalized_reason,
                        original_paid_by_staff_id=(
                            str(payment["paid_by_staff_id"])
                            if payment["paid_by_staff_id"] is not None
                            else None
                        ),
                        original_paid_at=payment["paid_at"],
                    )
        logger.info(
            "payment_voided",
            visit_id=visit_id,
            kind=kind,
            by_staff_id=identity.staff_id,
        )


async def _log_payment_event(
    conn: asyncpg.Connection,
    *,
    event_type: str,
    payment_id: str,
    payment_cycle_id: str,
    visit_id: str,
    kind: str,
    amount: int | None,
    identity: StaffIdentity,
    void_reason: str | None = None,
    original_paid_by_staff_id: str | None = None,
    original_paid_at: object | None = None,
) -> None:
    """Append a non-PHI financial audit event in the payment transaction."""
    await conn.execute(
        """
        INSERT INTO event_log (
            clinic_id, event_type, aggregate_type, aggregate_id, payload,
            metadata, source, event_published
        )
        VALUES ($6::uuid, $1, 'payment', $2::uuid, $3, $4, $5, FALSE)
        """,
        event_type,
        payment_id,
        json.dumps(
            {
                "payment_id": payment_id,
                "payment_cycle_id": payment_cycle_id,
                "visit_id": visit_id,
                "kind": kind,
                "amount": amount,
                "void_reason": void_reason,
                "original_paid_by_staff_id": original_paid_by_staff_id,
                "original_paid_at": (
                    original_paid_at.isoformat()
                    if isinstance(original_paid_at, datetime)
                    else original_paid_at
                ),
            }
        ),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
            }
        ),
        f"api:{event_type.replace('.', '-')}",
        identity.clinic_id,
    )
