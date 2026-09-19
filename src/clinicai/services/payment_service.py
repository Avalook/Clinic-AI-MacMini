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
    BillChangedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import pos_outbox
from clinicai.services.bill_service import HoaDon, tinh_hoa_don

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
    # LỄ TÂN KIÊM THU NGÂN ở Kim Ngưu (Tuyền 16/09/2026): quầy tiếp đón thu tiền
    # dịch vụ, quầy thuốc thu tiền thuốc — cùng một vai đứng cả hai quầy.
    if role in (ClinicRole.CASHIER, ClinicRole.MANAGEMENT, ClinicRole.RECEPTION):
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
        duoc_thu = {k for v in identity.cac_vai() for k in allowed_kinds(v)}
        if kind not in duoc_thu:
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
        bill_revision: str | None = None,
    ) -> None:
        """Upsert a PAID payment for ``(visit_id, kind)``.

        SỐ TIỀN DO MÁY CHỦ TÍNH (contract tiền–thuốc C3, 19/09/2026). Hoá đơn
        dựng lại trong chính giao dịch này (`bill_service.tinh_hoa_don`);
        ``amount`` và ``bill_revision`` của trình duyệt chỉ để ĐỐI CHIẾU — lệch
        thì từ chối (BILL_CHANGED), không bao giờ ghi số trình duyệt gửi.

        Raises SafetyGateError (403) if the kind is not allowed for the role,
        NotFoundError (404) if the visit/appointment is missing, and
        ConflictError (409) if the appointment is not yet COMPLETED.
        """
        self._assert_kind_allowed(kind, identity)

        so_trinh_duyet: int | None = None
        if amount is not None:
            so_trinh_duyet = normalize_amount(amount)
            if so_trinh_duyet is None:
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
                           clinic_patient_id, bill_revision
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
                    # ĐÃ THU — xét TRƯỚC khi tính hoá đơn hiện tại (review CP1
                    # #4). Lần gửi lại của CHÍNH hoá đơn đã thu (cùng revision,
                    # cùng số nếu có gửi) là thành công, kể cả khi bảng giá đã đổi
                    # sau đó. Hoá đơn KHÁC — dù cùng tổng tiền — không bao giờ
                    # được coi là đã trả.
                    da_luu = existing_payment["bill_revision"]
                    if bill_revision is not None:
                        cung_hoa_don = bill_revision == da_luu
                    else:
                        # Client cũ không gửi revision: chỉ nhận lại phiếu trước
                        # CP1 (chưa có revision) với đúng số tiền đã thu.
                        cung_hoa_don = (
                            da_luu is None
                            and so_trinh_duyet is not None
                            and so_trinh_duyet == existing_payment["amount"]
                        )
                    if not cung_hoa_don or (
                        so_trinh_duyet is not None
                        and so_trinh_duyet != existing_payment["amount"]
                    ):
                        raise ConflictError(
                            "Khoản này đã thu theo một hoá đơn khác — cần xử lý "
                            "tài chính: hãy hoàn tác phiếu thu trước khi thu lại"
                        )
                    # An identical retry is already durable and its POS invoice
                    # is already queued. Rewriting paid_at/actor would create a
                    # false second collection while the outbox correctly dedups.
                    return

                hoa_don = await tinh_hoa_don(
                    conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind=kind
                )
                if hoa_don.van_de:
                    raise ValidationError(
                        "Chưa thu được — " + "; ".join(hoa_don.van_de)
                    )
                if hoa_don.tong <= 0:
                    raise ValidationError("Lượt này không có khoản nào để thu.")
                if bill_revision is not None and bill_revision != hoa_don.revision:
                    raise BillChangedError(
                        "Hoá đơn vừa thay đổi (chỉ định, số lượng hoặc giá) — "
                        "tải lại rồi thu theo hoá đơn mới."
                    )
                if so_trinh_duyet is not None and so_trinh_duyet != hoa_don.tong:
                    raise BillChangedError(
                        f"Số tiền {so_trinh_duyet:,}đ khác hoá đơn máy chủ "
                        f"{hoa_don.tong:,}đ — tải lại rồi thu theo hoá đơn mới."
                    )
                normalized = hoa_don.tong

                payment = await conn.fetchrow(
                    """
                    INSERT INTO payment (
                        clinic_id, visit_id, clinic_patient_id, kind, status,
                        amount, paid_by_staff_id, paid_at, updated_at, bill_revision
                    )
                    VALUES ($6::uuid, $1::uuid, $2::uuid, $3, 'PAID', $4, $5::uuid,
                            now(), now(), $7)
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
                        bill_revision      = EXCLUDED.bill_revision,
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
                    hoa_don.revision,
                )
                if payment is None:
                    # A concurrent collector inserted the same unique
                    # (visit, kind) after our SELECT. Never overwrite it.
                    raise ConflictError(
                        "Khoản thanh toán vừa được người khác ghi, hãy tải lại"
                    )
                payment_id = str(payment["id"])
                payment_cycle_id = str(payment["payment_cycle_id"])
                await _ghi_anh_hoa_don(
                    conn,
                    clinic_id=identity.clinic_id,
                    payment_id=payment_id,
                    payment_cycle_id=payment_cycle_id,
                    hoa_don=hoa_don,
                )
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
        """Soft-void a payment, retaining the row and an immutable audit event.

        AI HUỶ ĐƯỢC (Tuyền chốt 15/09/2026): chính THU NGÂN ĐÃ THU phiếu đó tự
        gạch phiếu bấm nhầm, không cần quản lý duyệt. Thu ngân khác không gạch
        được phiếu của người khác (trước đây được); Quản lý vẫn gạch được.
        """
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
                       AND ($6::boolean OR paid_by_staff_id = $4::uuid)
                    RETURNING id, amount, payment_cycle_id,
                              paid_by_staff_id, paid_at
                    """,
                    visit_id,
                    kind,
                    identity.clinic_id,
                    identity.staff_id,
                    normalized_reason,
                    identity.co_vai({ClinicRole.MANAGEMENT}),
                )
                if payment is None and await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM payment WHERE visit_id = $1::uuid "
                    "AND kind = $2 AND clinic_id = $3::uuid AND status = 'PAID')",
                    visit_id,
                    kind,
                    identity.clinic_id,
                ):
                    raise SafetyGateError(
                        "Chỉ thu ngân đã thu phiếu này (hoặc quản lý) mới huỷ được."
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


async def _ghi_anh_hoa_don(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    payment_id: str,
    payment_cycle_id: str,
    hoa_don: HoaDon,
) -> None:
    """Ảnh chụp từng dòng hoá đơn của LẦN THU này (C4) — chỉ thêm, bất biến."""
    await conn.executemany(
        """
        INSERT INTO public.payment_bill_line (
            clinic_id, payment_id, payment_cycle_id, visit_id, kind,
            source_type, source_id, name_snapshot, quantity, unit,
            unit_price, line_total, billing_owner, drug_catalog_id
        )
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14::uuid)
        """,
        [
            (
                clinic_id,
                payment_id,
                payment_cycle_id,
                hoa_don.visit_id,
                hoa_don.kind,
                d.source_type,
                d.source_id,
                d.ten,
                d.so_luong,
                d.don_vi,
                # Chưa biết giá là NULL, không phải 0đ (review CP1 #5).
                d.don_gia,
                d.thanh_tien,
                d.ben_thu,
                d.drug_catalog_id,
            )
            for d in hoa_don.dong
        ],
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
                # Vai tài khoản gốc (vai dùng có thể khác).
                "vai_tai_khoan": identity.vai_goc.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
            }
        ),
        f"api:{event_type.replace('.', '-')}",
        identity.clinic_id,
    )
