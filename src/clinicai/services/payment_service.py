"""Payment service: authoritative record/void of visit payments (Phase 4, cluster #3).

Ported from the Next.js route ``src/dashboard/app/api/payment/route.ts`` so the payment
rule lives in the backend instead of the frontend. Rules preserved 1:1:

* Two payment kinds per visit — ``thuoc`` (pharmacy) + ``dich_vu`` (services),
  unique per ``(visit_id, kind)``. Recording is an upsert (status ``PAID``).
* A payment may only be recorded once the doctor has finished the exam —
  ``visit.exam_completed_at`` (legacy: appointment ``COMPLETED``), see
  ``moc_kham_xong`` → otherwise 409. Void is NOT gated.
* Role → kinds: CASHIER_THUOC ⟶ {thuoc}, CASHIER_DV ⟶ {dich_vu},
  CASHIER/MANAGEMENT ⟶ both. Coarse role gate is done at the router with
  ``require_role``; this finer kind↔role check lives here.

The acting staff is the *server-verified* identity (``StaffIdentity.staff_id``),
not a client-supplied cookie.
"""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import (
    BillChangedError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import pos_outbox
from clinicai.services.bill_service import HoaDon, tinh_hoa_don
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.phan_lo_service import (
    PhanLo,
    can_theo_hoa_don,
    dao_ban,
    gan_lan_thu,
    ghi_ban,
    go_va_giu_ke_hoach,
    khoa_ban_thuoc,
    van_de_phan_lo,
)

logger = structlog.get_logger()

PAYMENT_KINDS: frozenset[str] = frozenset({"thuoc", "dich_vu"})
# Contract tiền–thuốc A2/C6: tiền mặt = nhân viên xác nhận đã nhận đủ; chuyển
# khoản/QR chỉ PAID khi có người xác minh kèm mã giao dịch.
PAYMENT_METHODS: frozenset[str] = frozenset({"CASH", "TRANSFER", "QR"})
DIEN_TU: frozenset[str] = frozenset({"TRANSFER", "QR"})
CHO_XAC_MINH = "PENDING_VERIFICATION"
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
        method: str = "CASH",
    ) -> dict[str, Any]:
        """Một LẦN THU (payment_cycle) cho ``(visit_id, kind)``.

        Tiền mặt → PAID ngay (nhân viên bấm "đã nhận đủ" là bằng chứng). Chuyển
        khoản / QR → lần thu CHỜ XÁC MINH, chưa PAID; xem ``xac_minh_dien_tu``.
        Trả ``{"payment_cycle_id", "status"}``.

        SỐ TIỀN DO MÁY CHỦ TÍNH (contract tiền–thuốc C3, 19/09/2026). Hoá đơn
        dựng lại trong chính giao dịch này (`bill_service.tinh_hoa_don`);
        ``amount`` và ``bill_revision`` của trình duyệt chỉ để ĐỐI CHIẾU — lệch
        thì từ chối (BILL_CHANGED), không bao giờ ghi số trình duyệt gửi.

        Raises SafetyGateError (403) if the kind is not allowed for the role,
        NotFoundError (404) if the visit/appointment is missing, and
        ConflictError (409) if the doctor has not finished the exam yet.
        """
        self._assert_kind_allowed(kind, identity)
        if method not in PAYMENT_METHODS:
            raise ValidationError(f"Phương thức thanh toán không hợp lệ: {method!r}")

        so_trinh_duyet: int | None = None
        if amount is not None:
            so_trinh_duyet = normalize_amount(amount)
            if so_trinh_duyet is None:
                raise ValidationError("Số tiền phải là số hữu hạn lớn hơn 0")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # "Khám xong" là trạng thái của LƯỢT (moc_kham_xong, review
                # CP4): không INNER JOIN lịch hẹn — lượt không có lịch hẹn vẫn
                # thu được. Lịch hẹn nếu có chỉ còn là kiểm chéo bệnh nhân.
                # Khoá chỉ `visit`: mốc nằm trên visit, và Postgres không cho
                # khoá phía có thể rỗng của LEFT JOIN.
                status_row = await conn.fetchrow(
                    f"""
                    SELECT
                        {kham_xong_sql("v")} AS kham_xong,
                        (v.appointment_id IS NULL OR a.id IS NOT NULL) AS hen_khop,
                        v.clinic_patient_id,
                        EXISTS (
                            SELECT 1
                              FROM clinic_membership m
                             WHERE m.staff_id = $3::uuid
                               AND m.clinic_id = v.clinic_id
                               AND m.is_active
                        ) AS staff_in_clinic
                      FROM visit v
                      LEFT JOIN appointment a
                        ON a.id = v.appointment_id
                       AND a.clinic_id = v.clinic_id
                       AND a.clinic_patient_id = v.clinic_patient_id
                      JOIN patient p
                        ON p.clinic_patient_id = v.clinic_patient_id
                       AND p.clinic_id = v.clinic_id
                     WHERE v.visit_id = $1::uuid
                       AND v.clinic_id = $2::uuid
                     FOR UPDATE OF v
                    """,  # noqa: S608 — chỉ chèn biểu thức cố định
                    visit_id,
                    identity.clinic_id,
                    identity.staff_id,
                )
                if status_row is None or not status_row["hen_khop"]:
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
                if not status_row["kham_xong"]:
                    raise ConflictError(
                        "Bác sĩ chưa khám xong lượt này — chưa thể thu tiền"
                    )
                # CP3: khoá theo đúng thứ tự visit → dòng đơn → phân lô → lô,
                # TRƯỚC khi chạm payment_cycle / payment.
                phan_lo: list[PhanLo] = []
                if kind == "thuoc":
                    phan_lo = await khoa_ban_thuoc(
                        conn,
                        clinic_id=identity.clinic_id,
                        visit_id=visit_id,
                        payment_cycle_id=None,
                    )

                cho = await conn.fetchrow(
                    """
                    SELECT payment_cycle_id, bill_revision, method, amount
                      FROM payment_cycle
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND kind = $3 AND status = 'PENDING_VERIFICATION'
                     FOR UPDATE
                    """,
                    identity.clinic_id,
                    visit_id,
                    kind,
                )
                if cho is not None:
                    if (
                        bill_revision is not None
                        and bill_revision == cho["bill_revision"]
                        and method == cho["method"]
                    ):
                        return {
                            "payment_cycle_id": str(cho["payment_cycle_id"]),
                            "status": CHO_XAC_MINH,
                        }
                    raise ConflictError(
                        "Khoản này đang có một lần chuyển khoản/QR chờ xác minh — "
                        "xác minh đã nhận tiền hoặc huỷ lần chờ trước khi thu lại."
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
                    return {
                        "payment_cycle_id": str(existing_payment["payment_cycle_id"]),
                        "status": "PAID",
                    }

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
                if kind == "thuoc":
                    # CP3: thuốc chỉ thu được khi mọi dòng đã có đủ lô, lô còn
                    # hạn và còn khả dụng — thu xong là bán.
                    can = await can_theo_hoa_don(
                        conn,
                        clinic_id=identity.clinic_id,
                        dong=[
                            (d.source_id, d.ten, d.so_luong)
                            for d in hoa_don.dong
                            if d.source_type == "prescription"
                        ],
                    )
                    phan_lo = [p for p in phan_lo if p.prescription_id in can]
                    van_de = await van_de_phan_lo(
                        conn,
                        clinic_id=identity.clinic_id,
                        can=can,
                        phan_lo=phan_lo,
                        da_giu=False,
                        hom_nay=now_vn().date(),
                    )
                    if van_de:
                        raise ValidationError(
                            "Chưa thu được tiền thuốc — " + "; ".join(van_de)
                        )

                cycle_id = str(uuid.uuid4())
                dien_tu = method in DIEN_TU
                await conn.execute(
                    """
                    INSERT INTO payment_cycle (
                        payment_cycle_id, clinic_id, visit_id, kind, amount,
                        bill_revision, method, status, created_by,
                        paid_at, confirmed_by
                    )
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8,
                            $9::uuid,
                            CASE WHEN $8 = 'PAID' THEN now() END,
                            CASE WHEN $8 = 'PAID' THEN $9::uuid END)
                    """,
                    cycle_id,
                    identity.clinic_id,
                    visit_id,
                    kind,
                    normalized,
                    hoa_don.revision,
                    method,
                    CHO_XAC_MINH if dien_tu else "PAID",
                    identity.staff_id,
                )
                payment_id: str | None = None
                if not dien_tu:
                    payment_id = await _ghi_da_thu(
                        conn,
                        cycle_id=cycle_id,
                        visit_id=visit_id,
                        kind=kind,
                        amount=normalized,
                        bill_revision=hoa_don.revision,
                        patient_id=authoritative_patient_id,
                        identity=identity,
                        method=method,
                        reference=None,
                    )
                await _ghi_anh_hoa_don(
                    conn,
                    clinic_id=identity.clinic_id,
                    payment_id=payment_id,
                    payment_cycle_id=cycle_id,
                    hoa_don=hoa_don,
                )
                if phan_lo:
                    # Chờ xác minh: phân lô thành phần GIỮ của lần thu này.
                    # Tiền mặt: PAID ngay → bán luôn, cùng giao dịch.
                    await gan_lan_thu(
                        conn,
                        clinic_id=identity.clinic_id,
                        cycle_id=cycle_id,
                        phan_lo=phan_lo,
                    )
                    if not dien_tu:
                        await ghi_ban(
                            conn,
                            clinic_id=identity.clinic_id,
                            cycle_id=cycle_id,
                            staff_id=identity.staff_id,
                            phan_lo=phan_lo,
                        )
                if dien_tu:
                    await _log_payment_event(
                        conn,
                        event_type="payment.pending_verification",
                        payment_id=cycle_id,
                        payment_cycle_id=cycle_id,
                        visit_id=visit_id,
                        kind=kind,
                        amount=normalized,
                        identity=identity,
                        method=method,
                    )
        logger.info(
            "payment_recorded",
            visit_id=visit_id,
            kind=kind,
            method=method,
            by_staff_id=identity.staff_id,
        )
        return {
            "payment_cycle_id": cycle_id,
            "status": CHO_XAC_MINH if dien_tu else "PAID",
        }

    @staticmethod
    async def _khoa_lan_thu(
        conn: asyncpg.Connection,
        *,
        payment_cycle_id: str,
        visit_id: str,
        kind: str,
        identity: StaffIdentity,
    ) -> tuple[asyncpg.Record, list[PhanLo]]:
        """Khoá lượt rồi khoá ĐÚNG lần thu được nhắm (review CP2 #1).

        Không bao giờ tìm "lần thu hiện tại" theo (lượt, loại): một lệnh cũ đến
        muộn phải chạm đúng lần thu nó nhắm — A — chứ không trượt sang B vừa tạo
        sau. Lượt, loại, phòng khám vẫn được kiểm chéo.

        Tiền thuốc (CP3): giữa lượt và lần thu còn khoá dòng đơn → phân lô của
        lần thu này → lô, đúng thứ tự chung. Trả kèm các phân lô ấy.
        """
        luot = await conn.fetchrow(
            """
            SELECT v.clinic_patient_id
              FROM visit v
              LEFT JOIN appointment a
                ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
             WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
             FOR UPDATE OF v
            """,
            visit_id,
            identity.clinic_id,
        )
        if luot is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        phan_lo: list[PhanLo] = []
        if kind == "thuoc":
            phan_lo = await khoa_ban_thuoc(
                conn,
                clinic_id=identity.clinic_id,
                visit_id=visit_id,
                payment_cycle_id=payment_cycle_id,
            )
        lan = await conn.fetchrow(
            """
            SELECT payment_cycle_id, status, method, amount, bill_revision,
                   reference, can_doi_soat, created_by, confirmed_by, legacy
              FROM payment_cycle
             WHERE payment_cycle_id = $1::uuid AND clinic_id = $2::uuid
               AND visit_id = $3::uuid AND kind = $4
             FOR UPDATE
            """,
            payment_cycle_id,
            identity.clinic_id,
            visit_id,
            kind,
        )
        if lan is None:
            raise NotFoundError("Không tìm thấy lần thu này của lượt khám.")
        return lan, phan_lo

    async def xac_minh_dien_tu(
        self,
        *,
        payment_cycle_id: str,
        visit_id: str,
        kind: str,
        reference: object,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Xác minh lần chuyển khoản/QR ĐÃ NHẬN TIỀN, kèm mã giao dịch → PAID.

        Khách quét mã không phải bằng chứng; mã giao dịch ngân hàng người xác
        minh nhập mới là bằng chứng (contract A2).

        GẮN VỚI ẢNH CHỤP CỦA LẦN THU (review CP2 #3): tiền khách chuyển là cho
        đúng hoá đơn đã chụp lúc tạo lần chờ, với đúng số tiền ấy. Hoá đơn hiện
        tại khác (bảng giá đổi trong lúc chờ…) KHÔNG phủ nhận tiền đã nhận — vẫn
        ghi đã thu theo ảnh chụp và bật `can_doi_soat` để xử lý tài chính sau.

        Gửi lại cùng mã cho lần đã xác minh → thành công như cũ (idempotent).
        HOLD: ai được xác minh (hiện: cùng các vai được thu loại tiền này).
        """
        self._assert_kind_allowed(kind, identity)
        ma = reference.strip() if isinstance(reference, str) else ""
        if not 3 <= len(ma) <= 100:
            raise ValidationError("Nhập mã giao dịch ngân hàng (3–100 ký tự).")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                lan, phan_lo = await self._khoa_lan_thu(
                    conn,
                    payment_cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    identity=identity,
                )
                if lan["status"] == "PAID":
                    if lan["reference"] == ma:
                        return {
                            "payment_cycle_id": payment_cycle_id,
                            "status": "PAID",
                            "can_doi_soat": lan["can_doi_soat"],
                            "da_xac_minh_tu_truoc": True,
                        }
                    raise ConflictError(
                        "Lần thu này đã được xác minh với một mã giao dịch khác."
                    )
                if lan["status"] != CHO_XAC_MINH:
                    raise ConflictError(
                        "Lần thu này không còn chờ xác minh (đã huỷ) — "
                        "không xác minh được."
                    )
                patient_id = await conn.fetchval(
                    "SELECT clinic_patient_id::text FROM visit"
                    " WHERE visit_id = $1::uuid AND clinic_id = $2::uuid",
                    visit_id,
                    identity.clinic_id,
                )
                hoa_don = await tinh_hoa_don(
                    conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind=kind
                )
                lech = hoa_don.revision != lan["bill_revision"]
                khong_ban_duoc: list[str] = []
                if kind == "thuoc" and not lan["legacy"]:
                    # Phân lô đã GIỮ từ lúc tạo lần chờ, nên bình thường luôn
                    # bán được. Nếu không (dữ liệu hỏng, lô hết hạn qua đêm):
                    # tiền thật vẫn ghi đã thu, KHÔNG ghi bán, bật đối soát.
                    can = await _can_theo_anh_chup(
                        conn, clinic_id=identity.clinic_id, cycle_id=payment_cycle_id
                    )
                    khong_ban_duoc = await van_de_phan_lo(
                        conn,
                        clinic_id=identity.clinic_id,
                        can=can,
                        phan_lo=phan_lo,
                        da_giu=True,
                        hom_nay=now_vn().date(),
                    )
                can_doi_soat = lech or bool(khong_ban_duoc)
                payment_id = await _ghi_da_thu(
                    conn,
                    cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    amount=int(lan["amount"]),
                    bill_revision=lan["bill_revision"],
                    patient_id=str(patient_id),
                    identity=identity,
                    method=lan["method"],
                    reference=ma,
                )
                await conn.execute(
                    """
                    UPDATE payment_cycle
                       SET status = 'PAID', paid_at = now(), confirmed_by = $2::uuid,
                           reference = $3, payment_id = $4::uuid, can_doi_soat = $5
                     WHERE payment_cycle_id = $1::uuid
                       AND status = 'PENDING_VERIFICATION'
                    """,
                    payment_cycle_id,
                    identity.staff_id,
                    ma,
                    payment_id,
                    can_doi_soat,
                )
                if kind == "thuoc" and not lan["legacy"] and not khong_ban_duoc:
                    await ghi_ban(
                        conn,
                        clinic_id=identity.clinic_id,
                        cycle_id=payment_cycle_id,
                        staff_id=identity.staff_id,
                        phan_lo=phan_lo,
                    )
                if khong_ban_duoc:
                    await _log_payment_event(
                        conn,
                        event_type="payment.sale_not_applied",
                        payment_id=payment_id,
                        payment_cycle_id=payment_cycle_id,
                        visit_id=visit_id,
                        kind=kind,
                        amount=int(lan["amount"]),
                        identity=identity,
                        method=lan["method"],
                        note="; ".join(khong_ban_duoc),
                    )
                if lech:
                    await _log_payment_event(
                        conn,
                        event_type="payment.reconciliation_needed",
                        payment_id=payment_id,
                        payment_cycle_id=payment_cycle_id,
                        visit_id=visit_id,
                        kind=kind,
                        amount=int(lan["amount"]),
                        identity=identity,
                        method=lan["method"],
                    )
        return {
            "payment_cycle_id": payment_cycle_id,
            "status": "PAID",
            "can_doi_soat": can_doi_soat,
        }

    async def huy_cho_xac_minh(
        self,
        *,
        payment_cycle_id: str,
        visit_id: str,
        kind: str,
        reason: object,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Huỷ ĐÚNG lần chuyển khoản/QR chờ xác minh (khách không chuyển / chuyển
        sai). Không phải huỷ phiếu thu — chưa từng thu. Gửi lại cho lần đã huỷ
        → thành công như cũ."""
        self._assert_kind_allowed(kind, identity)
        ly_do = normalize_void_reason(reason)
        if ly_do is None:
            raise ValidationError("Lý do huỷ phải có từ 5 đến 500 ký tự")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                lan, phan_lo = await self._khoa_lan_thu(
                    conn,
                    payment_cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    identity=identity,
                )
                if lan["status"] == "CANCELLED":
                    return {
                        "payment_cycle_id": payment_cycle_id,
                        "status": "CANCELLED",
                        "da_huy_tu_truoc": True,
                    }
                if lan["status"] != CHO_XAC_MINH:
                    raise ConflictError(
                        "Lần thu này không còn chờ xác minh — không huỷ lần chờ được."
                    )
                await conn.execute(
                    """
                    UPDATE payment_cycle
                       SET status = 'CANCELLED', closed_at = now(),
                           closed_by = $2::uuid, close_reason = $3
                     WHERE payment_cycle_id = $1::uuid
                       AND status = 'PENDING_VERIFICATION'
                    """,
                    payment_cycle_id,
                    identity.staff_id,
                    ly_do,
                )
                # Bỏ phần giữ lô của lần chờ; kế hoạch lô chép lại (chưa gắn).
                await go_va_giu_ke_hoach(
                    conn,
                    clinic_id=identity.clinic_id,
                    staff_id=identity.staff_id,
                    ly_do=f"Huỷ lần chờ xác minh: {ly_do}",
                    phan_lo=phan_lo,
                )
                await _log_payment_event(
                    conn,
                    event_type="payment.pending_cancelled",
                    payment_id=payment_cycle_id,
                    payment_cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    amount=int(lan["amount"]),
                    identity=identity,
                    void_reason=ly_do,
                    method=lan["method"],
                )
        return {"payment_cycle_id": payment_cycle_id, "status": "CANCELLED"}

    async def void_payment(
        self,
        *,
        payment_cycle_id: str,
        visit_id: str,
        kind: str,
        reason: object,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Huỷ ĐÚNG phiếu thu (lần thu) được nhắm — contract D2, review CP2 #1.

        Giữ nguyên dòng và sự kiện bất biến. AI HUỶ ĐƯỢC (Tuyền chốt 15/09/2026):
        chính người đã thu phiếu đó, hoặc Quản lý. Lệnh cũ đến muộn nhắm A thì
        không bao giờ huỷ B; gửi lại cho A đã huỷ → thành công như cũ.
        """
        self._assert_kind_allowed(kind, identity)
        normalized_reason = normalize_void_reason(reason)
        if normalized_reason is None:
            raise ValidationError("Lý do hoàn tác phải có từ 5 đến 500 ký tự")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                lan, phan_lo = await self._khoa_lan_thu(
                    conn,
                    payment_cycle_id=payment_cycle_id,
                    visit_id=visit_id,
                    kind=kind,
                    identity=identity,
                )
                if lan["status"] == "VOIDED":
                    return {
                        "payment_cycle_id": payment_cycle_id,
                        "status": "VOIDED",
                        "da_huy_tu_truoc": True,
                    }
                if lan["status"] != "PAID":
                    raise ConflictError(
                        "Lần thu này chưa phải phiếu đã thu — không huỷ phiếu được."
                    )
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
                       AND payment_cycle_id = $7::uuid
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
                    payment_cycle_id,
                )
                if payment is None:
                    if await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM payment WHERE visit_id = $1::uuid"
                        " AND kind = $2 AND clinic_id = $3::uuid AND status = 'PAID'"
                        " AND payment_cycle_id = $4::uuid)",
                        visit_id,
                        kind,
                        identity.clinic_id,
                        payment_cycle_id,
                    ):
                        raise SafetyGateError(
                            "Chỉ thu ngân đã thu phiếu này (hoặc quản lý) mới huỷ được."
                        )
                    raise ConflictError(
                        "Lần thu này không phải phiếu thu hiện hành của lượt — "
                        "không huỷ được từ đây."
                    )
                payment_id = str(payment["id"])
                await conn.execute(
                    """
                    UPDATE payment_cycle
                       SET status = 'VOIDED', closed_at = now(),
                           closed_by = $2::uuid, close_reason = $3
                     WHERE payment_cycle_id = $1::uuid AND status = 'PAID'
                    """,
                    payment_cycle_id,
                    identity.staff_id,
                    normalized_reason,
                )
                if phan_lo:
                    # CP3: dòng chưa giao gì → đảo bán đúng một lần; dòng đã
                    # giao → không tự nhập lại kho, ghi cần xử lý trả thuốc (CP5).
                    can_tra = await dao_ban(
                        conn,
                        clinic_id=identity.clinic_id,
                        cycle_id=payment_cycle_id,
                        staff_id=identity.staff_id,
                        ly_do=f"Huỷ phiếu thu: {normalized_reason}",
                        phan_lo=phan_lo,
                    )
                    if can_tra:
                        await _log_payment_event(
                            conn,
                            event_type="payment.drug_return_needed",
                            payment_id=payment_cycle_id,
                            payment_cycle_id=payment_cycle_id,
                            visit_id=visit_id,
                            kind=kind,
                            amount=None,
                            identity=identity,
                            note=",".join(can_tra),
                        )
                # Serialize this void with any relay currently delivering the
                # invoice for the same payment cycle. If void wins, the pending
                # invoice becomes DEAD before a stale relay can send it; if relay
                # wins, invoice completes before void.
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
            payment_cycle_id=payment_cycle_id,
            by_staff_id=identity.staff_id,
        )
        return {"payment_cycle_id": payment_cycle_id, "status": "VOIDED"}


async def _ghi_da_thu(
    conn: asyncpg.Connection,
    *,
    cycle_id: str,
    visit_id: str,
    kind: str,
    amount: int,
    bill_revision: str | None,
    patient_id: str,
    identity: StaffIdentity,
    method: str | None,
    reference: str | None,
) -> str:
    """Hình chiếu "khoản hiện đã thu" (`payment`) + POS outbox + sự kiện.

    Dùng cho thu tiền mặt và cho xác minh chuyển khoản/QR. `payment_cycle_id`
    là CHÍNH lần thu — không sinh mã mới ngầm như bản cũ.
    """
    payment = await conn.fetchrow(
        """
        INSERT INTO payment (
            clinic_id, visit_id, clinic_patient_id, kind, status,
            amount, paid_by_staff_id, paid_at, updated_at, bill_revision,
            payment_cycle_id
        )
        VALUES ($6::uuid, $1::uuid, $2::uuid, $3, 'PAID', $4, $5::uuid,
                now(), now(), $7, $8::uuid)
        ON CONFLICT (visit_id, kind) DO UPDATE SET
            clinic_patient_id = EXCLUDED.clinic_patient_id,
            amount            = EXCLUDED.amount,
            status            = 'PAID',
            paid_by_staff_id  = EXCLUDED.paid_by_staff_id,
            paid_at           = now(),
            payment_cycle_id  = EXCLUDED.payment_cycle_id,
            voided_at          = NULL,
            voided_by_staff_id = NULL,
            void_reason        = NULL,
            bill_revision      = EXCLUDED.bill_revision,
            updated_at        = now()
        WHERE payment.status = 'VOIDED'
        RETURNING id, payment_cycle_id
        """,
        visit_id,
        patient_id,
        kind,
        amount,
        identity.staff_id,
        identity.clinic_id,
        bill_revision,
        cycle_id,
    )
    if payment is None:
        # A concurrent collector inserted the same unique (visit, kind) after
        # our SELECT. Never overwrite it.
        raise ConflictError("Khoản thanh toán vừa được người khác ghi, hãy tải lại")
    payment_id = str(payment["id"])
    await conn.execute(
        "UPDATE payment_cycle SET payment_id = $2::uuid"
        " WHERE payment_cycle_id = $1::uuid AND payment_id IS NULL",
        cycle_id,
        payment_id,
    )
    # Transactional outbox (ADR-0010): queued with the payment, so the push
    # cannot be lost, and pushed later, so an external POS being down cannot
    # fail the cashier. No adapter is imported here — this is an INSERT.
    await pos_outbox.enqueue(
        conn,
        kind=pos_outbox.INVOICE,
        subject_id=cycle_id,
        payload={
            "clinic_reference": cycle_id,
            "payment_id": payment_id,
            "kind": kind,
            "total_amount": amount,
            "paid_at": datetime.now(timezone.utc),
            "patient_reference": patient_id,
            "visit_id": visit_id,
        },
        clinic_id=identity.clinic_id,
    )
    await _log_payment_event(
        conn,
        event_type="payment.recorded",
        payment_id=payment_id,
        payment_cycle_id=cycle_id,
        visit_id=visit_id,
        kind=kind,
        amount=amount,
        identity=identity,
        method=method,
        reference=reference,
    )
    return payment_id


async def _can_theo_anh_chup(
    conn: asyncpg.Connection, *, clinic_id: str, cycle_id: str
) -> dict[str, Any]:
    """Số phải có lô của lần thu, theo ẢNH CHỤP hoá đơn của chính nó."""
    dong = await conn.fetch(
        """
        SELECT source_id, name_snapshot, quantity FROM public.payment_bill_line
         WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid
           AND source_type = 'prescription'
        """,
        clinic_id,
        cycle_id,
    )
    return await can_theo_hoa_don(
        conn,
        clinic_id=clinic_id,
        dong=[
            (str(r["source_id"]), r["name_snapshot"], Decimal(str(r["quantity"])))
            for r in dong
        ],
    )


async def _ghi_anh_hoa_don(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    payment_id: str | None,
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
    method: str | None = None,
    reference: str | None = None,
    note: str | None = None,
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
                "method": method,
                "reference": reference,
                "note": note,
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
