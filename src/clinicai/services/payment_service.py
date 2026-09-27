"""Payment service: authoritative record/void of visit payments (Phase 4, cluster #3).

Ported from the Next.js route ``src/dashboard/app/api/payment/route.ts`` so the payment
rule lives in the backend instead of the frontend. Rules preserved 1:1:

* Two payment kinds per visit — ``thuoc`` (pharmacy) + ``dich_vu`` (services),
  unique per ``(visit_id, kind)``. Recording is an upsert (status ``PAID``).
* TIỀN THUỐC chỉ thu được khi bác sĩ đã khám xong — ``visit.exam_completed_at``
  (legacy: appointment ``COMPLETED``), see ``moc_kham_xong`` → otherwise 409.
  TIỀN DỊCH VỤ thu được ngay khi có chỉ định (Tuyền 24/09/2026 — khách trả
  tiền rồi đi làm, phiên bác sĩ còn mở). Void is NOT gated.
* Role → kinds: CASHIER_THUOC ⟶ {thuoc}, CASHIER_DV ⟶ {dich_vu},
  CASHIER/MANAGEMENT ⟶ both. Coarse role gate is done at the router with
  ``require_role``; this finer kind↔role check lives here.

The acting staff is the *server-verified* identity (``StaffIdentity.staff_id``),
not a client-supplied cookie.
"""

from __future__ import annotations

import json
import math
import os
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
from clinicai.events.catalogue import ThuocBiBo, TienDichVuDaThu, TienThuocDaThu
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.permissions.catalogue import tra_quyen
from clinicai.services import pos_outbox
from clinicai.services.bill_service import (
    HoaDon,
    hoa_don_theo_anh_chup,
    tinh_hoa_don,
)
from clinicai.services.lenh_kham_core import bien_nhan_doc, bien_nhan_ghi
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


def dung_kho_thuoc_khi_thanh_toan() -> bool:
    """Tạm thời Tuyền chốt 20/09/2026: thu tiền thuốc không chờ kho/phân lô.

    Giữ code kho phía sau để bật lại khi scope kho được chốt.
    """
    return os.getenv(
        "CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}


PAYMENT_KINDS: frozenset[str] = frozenset({"thuoc", "dich_vu"})
# Contract tiền–thuốc A2/C6: tiền mặt = nhân viên xác nhận đã nhận đủ; chuyển
# khoản/QR chỉ PAID khi có người xác minh kèm mã giao dịch.
PAYMENT_METHODS: frozenset[str] = frozenset({"CASH", "TRANSFER", "QR"})
DIEN_TU: frozenset[str] = frozenset({"TRANSFER", "QR"})
CHO_XAC_MINH = "PENDING_VERIFICATION"
#: Hành động trong command_receipt của lệnh thu tiền dịch vụ.
_THU_DICH_VU = "payment.record.dich_vu"
# Mã nguyên nhân cần đối soát (CP6) — đúng hai mã DB chấp nhận
# (payment_cycle_doi_soat_ma_hop_le). Thêm mã = thêm vào CHECK cùng lúc.
DOI_SOAT_HOA_DON_DOI = "HOA_DON_DOI"
DOI_SOAT_CHUA_GHI_BAN = "CHUA_GHI_BAN"
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
    # Dược sĩ thu tiền thuốc ở quầy thuốc (bảng "màn mặc định theo vai" Tuyền
    # chốt 23/09: "Thu tiền thuốc + Kho thuốc → Dược sĩ"). Rà quyền nhóm 6.
    if role is ClinicRole.PHARMACIST:
        return frozenset({"thuoc"})
    # LỄ TÂN KIÊM THU NGÂN ở Kim Ngưu (Tuyền 16/09/2026): quầy tiếp đón thu tiền
    # dịch vụ, quầy thuốc thu tiền thuốc — cùng một vai đứng cả hai quầy.
    if role in (ClinicRole.CASHIER, ClinicRole.MANAGEMENT, ClinicRole.RECEPTION):
        return PAYMENT_KINDS
    return frozenset()


#: Loại tiền → quyền thu / huỷ / xác minh (24/09/2026). `allowed_kinds` bên
#: trên chỉ còn cho màn thu ngân chọn ô hiển thị theo vai.
QUYEN_THU: dict[str, str] = {
    "dich_vu": "payment.service.collect",
    "thuoc": "payment.medicine.collect",
}


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

    async def _assert_kind_allowed(self, kind: str, identity: StaffIdentity) -> None:
        """Thu / huỷ / xác minh một loại tiền hỏi QUYỀN của loại ấy (24/09/2026).

        Trước đây theo vai (`allowed_kinds`): người được cấp khối "Thu tiền dịch
        vụ" mà khác vai thì thu được (lệnh thu hỏi quyền) nhưng không huỷ / xác
        minh được chính phiếu mình thu. Nay cùng một câu hỏi cho mọi thao tác.
        """
        if kind not in PAYMENT_KINDS:
            raise SafetyGateError(f"Loại thanh toán không hợp lệ: {kind!r}")
        async with self._pool.acquire() as conn:
            if not await can(conn, identity, QUYEN_THU[kind]):
                logger.info(
                    "payment_kind_forbidden", role=identity.role.value, kind=kind
                )
                raise SafetyGateError(
                    "Bạn chưa được cấp quyền thu loại tiền này"
                    f" (“{tra_quyen(QUYEN_THU[kind]).ten}”)."
                )

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
        idempotency_key: str | None = None,
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
        if kind == "dich_vu":
            # Tiền DỊCH VỤ hỏi QUYỀN `payment.service.collect` trong chính giao
            # dịch thu (CORE-B3, 23/09/2026) — xem `_thu_dich_vu`. Tiền thuốc
            # hỏi `payment.medicine.collect` (24/09/2026).
            if kind not in PAYMENT_KINDS:
                raise SafetyGateError(f"Loại thanh toán không hợp lệ: {kind!r}")
        else:
            await self._assert_kind_allowed(kind, identity)
        if method not in PAYMENT_METHODS:
            raise ValidationError(f"Phương thức thanh toán không hợp lệ: {method!r}")

        so_trinh_duyet: int | None = None
        if amount is not None:
            so_trinh_duyet = normalize_amount(amount)
            if so_trinh_duyet is None:
                raise ValidationError("Số tiền phải là số hữu hạn lớn hơn 0")

        if kind == "dich_vu":
            return await self._thu_dich_vu(
                visit_id=visit_id,
                clinic_patient_id=clinic_patient_id,
                identity=identity,
                bill_revision=bill_revision,
                method=method,
                so_trinh_duyet=so_trinh_duyet,
                idempotency_key=idempotency_key,
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                status_row = await _khoa_luot_thu(conn, visit_id, identity)
                authoritative_patient_id = _kiem_luot_thu(
                    status_row, clinic_patient_id, can_kham_xong=False, kind=kind
                )
                # CP3: khoá theo đúng thứ tự visit → dòng đơn → phân lô → lô,
                # TRƯỚC khi chạm payment_cycle / payment.
                phan_lo: list[PhanLo] = []
                if kind == "thuoc" and dung_kho_thuoc_khi_thanh_toan():
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
                if kind == "thuoc" and dung_kho_thuoc_khi_thanh_toan():
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
                if kind == "thuoc" and payment_id is not None:
                    # Tiền mặt: đã nhận VÀ ảnh chụp hoá đơn đã ghi → so bản
                    # thanh toán cuối với đơn (Tuyền 24/09/2026).
                    await _phat_thuoc_bi_bo(
                        conn, identity=identity, visit_id=visit_id, cycle_id=cycle_id
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

    async def _thu_dich_vu(
        self,
        *,
        visit_id: str,
        clinic_patient_id: str | None,
        identity: StaffIdentity,
        bill_revision: str | None,
        method: str,
        so_trinh_duyet: int | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """Một lần thu TIỀN DỊCH VỤ theo OUTSTANDING BILL (Lifecycle v1 Slice 3).

        Nhiều lần thu PAID trên một lượt là hợp lệ: mỗi lần chỉ thu phần còn nợ
        (tiền khám nếu chưa phủ + chỉ định khách đã chọn mà chưa phủ). Chốt DB
        ``payment_bill_line_mot_lan_phu`` bảo đảm một dòng không bị phủ hai lần,
        kể cả khi hai người thu cùng lúc.

        BIÊN NHẬN TRONG CÙNG GIAO DỊCH (CHECKPOINT §5): khoá lượt → đọc biên
        nhận → (gửi lại thì trả đúng kết quả cũ) → dựng hoá đơn → ghi lần thu +
        ảnh chụp + sự kiện + biên nhận → commit. Đọc biên nhận TRƯỚC khi dựng
        hoá đơn: lần đầu có thể đã commit (các dòng đã thành "đã phủ", hoá đơn
        còn nợ đã đổi) rồi mới mất phản hồi.
        """
        if not idempotency_key:
            raise ValidationError(
                "Thiếu Idempotency-Key — mỗi lần bấm thu tiền dịch vụ phải mang"
                " một khoá (gửi lại cùng thao tác thì dùng lại khoá cũ)."
            )
        payload = {
            "visit_id": visit_id,
            "kind": "dich_vu",
            "clinic_patient_id": clinic_patient_id,
            "bill_revision": bill_revision,
            "method": method,
            "amount": so_trinh_duyet,
        }
        async with self._pool.acquire() as conn:
            try:
                async with conn.transaction():
                    await doi_quyen(conn, identity, "payment.service.collect")
                    status_row = await _khoa_luot_thu(conn, visit_id, identity)
                    cached = await bien_nhan_doc(
                        conn, identity, _THU_DICH_VU, idempotency_key, payload
                    )
                    if cached is not None:
                        return cached
                    patient_id = _kiem_luot_thu(
                        status_row, clinic_patient_id, can_kham_xong=False
                    )
                    kq = await self._ghi_lan_thu_dich_vu(
                        conn,
                        visit_id=visit_id,
                        patient_id=patient_id,
                        identity=identity,
                        bill_revision=bill_revision,
                        method=method,
                        so_trinh_duyet=so_trinh_duyet,
                    )
                    await bien_nhan_ghi(
                        conn,
                        identity,
                        _THU_DICH_VU,
                        idempotency_key,
                        payload,
                        visit_id,
                        kq,
                    )
            except asyncpg.UniqueViolationError as exc:
                # Chốt DB chống phủ trùng / một lần chờ xác minh: người khác vừa
                # thu đúng các dòng này. Cả giao dịch đã lùi — không ghi gì.
                raise ConflictError(
                    "Khoản dịch vụ này vừa được thu ở một lần thu khác — tải lại"
                    " để thấy phần còn nợ."
                ) from exc
        logger.info(
            "payment_recorded",
            visit_id=visit_id,
            kind="dich_vu",
            method=method,
            by_staff_id=identity.staff_id,
        )
        return kq

    async def _ghi_lan_thu_dich_vu(
        self,
        conn: asyncpg.Connection,
        *,
        visit_id: str,
        patient_id: str,
        identity: StaffIdentity,
        bill_revision: str | None,
        method: str,
        so_trinh_duyet: int | None,
    ) -> dict[str, Any]:
        cho = await conn.fetchrow(
            """
            SELECT payment_cycle_id, bill_revision, method
              FROM payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND kind = 'dich_vu' AND status = 'PENDING_VERIFICATION'
             FOR UPDATE
            """,
            identity.clinic_id,
            visit_id,
        )
        if cho is not None:
            # Một lần chờ xác minh tại một thời điểm. Gửi lại ĐÚNG lần chờ ấy
            # (cùng hoá đơn, cùng phương thức) → trả lần chờ, không tạo lần hai.
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
        hoa_don = await tinh_hoa_don(
            conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind="dich_vu"
        )
        if hoa_don.van_de:
            raise ValidationError("Chưa thu được — " + "; ".join(hoa_don.van_de))
        if hoa_don.tong <= 0:
            if hoa_don.chi_doi_tac_thu:
                # Đối tác tự thu (27/09/2026): không phải lỗi của quầy — nói
                # đúng việc, không để lễ tân tưởng hệ thống kẹt.
                raise ValidationError(
                    "Phòng khám không còn khoản nào — dịch vụ còn lại khách trả"
                    " trực tiếp cho đối tác."
                )
            raise ValidationError("Lượt này không còn khoản dịch vụ nào phải thu.")
        if bill_revision is not None and bill_revision != hoa_don.revision:
            raise BillChangedError(
                "Hoá đơn vừa thay đổi (chỉ định, lựa chọn của khách hoặc giá) — "
                "tải lại rồi thu theo hoá đơn mới."
            )
        if so_trinh_duyet is not None and so_trinh_duyet != hoa_don.tong:
            raise BillChangedError(
                f"Số tiền {so_trinh_duyet:,}đ khác hoá đơn máy chủ "
                f"{hoa_don.tong:,}đ — tải lại rồi thu theo hoá đơn mới."
            )
        cycle_id = str(uuid.uuid4())
        dien_tu = method in DIEN_TU
        await conn.execute(
            """
            INSERT INTO payment_cycle (
                payment_cycle_id, clinic_id, visit_id, kind, amount,
                bill_revision, method, status, created_by, paid_at, confirmed_by
            )
            VALUES ($1::uuid, $2::uuid, $3::uuid, 'dich_vu', $4, $5, $6, $7,
                    $8::uuid,
                    CASE WHEN $7 = 'PAID' THEN now() END,
                    CASE WHEN $7 = 'PAID' THEN $8::uuid END)
            """,
            cycle_id,
            identity.clinic_id,
            visit_id,
            hoa_don.tong,
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
                kind="dich_vu",
                amount=hoa_don.tong,
                bill_revision=hoa_don.revision,
                patient_id=patient_id,
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
        if not dien_tu:
            await _phat_da_thu_dich_vu(
                conn,
                cycle_id=cycle_id,
                visit_id=visit_id,
                amount=hoa_don.tong,
                method=method,
                identity=identity,
            )
        if dien_tu:
            await _log_payment_event(
                conn,
                event_type="payment.pending_verification",
                payment_id=cycle_id,
                payment_cycle_id=cycle_id,
                visit_id=visit_id,
                kind="dich_vu",
                amount=hoa_don.tong,
                identity=identity,
                method=method,
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
                   reference, can_doi_soat, doi_soat_ly_do, created_by, confirmed_by,
                   legacy, paid_at
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
        """Xác minh lần chuyển khoản/QR ĐÃ NHẬN TIỀN → PAID.

        Mã giao dịch ngân hàng là TUỲ CHỌN (Tuyền 24/09/2026: "không được bắt
        buộc điền mã mới cho thanh toán xong, open đi"). Có mã thì lưu làm bằng
        chứng; không có thì người bấm (`confirmed_by`) là dấu vết.

        GẮN VỚI ẢNH CHỤP CỦA LẦN THU (review CP2 #3): tiền khách chuyển là cho
        đúng hoá đơn đã chụp lúc tạo lần chờ, với đúng số tiền ấy. Hoá đơn hiện
        tại khác (bảng giá đổi trong lúc chờ…) KHÔNG phủ nhận tiền đã nhận — vẫn
        ghi đã thu theo ảnh chụp và bật `can_doi_soat` để xử lý tài chính sau.

        Gửi lại cùng mã cho lần đã xác minh → thành công như cũ (idempotent).
        HOLD: ai được xác minh (hiện: cùng các vai được thu loại tiền này).
        """
        await self._assert_kind_allowed(kind, identity)
        ma = (reference.strip() if isinstance(reference, str) else "") or None
        if ma is not None and len(ma) > 100:
            raise ValidationError("Mã giao dịch ngân hàng dài quá 100 ký tự.")
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
                    # Gửi lại (mất phản hồi) — không mã, hay cùng mã → như cũ.
                    if ma is None or lan["reference"] == ma:
                        return {
                            "payment_cycle_id": payment_cycle_id,
                            "status": "PAID",
                            "can_doi_soat": lan["can_doi_soat"],
                            "doi_soat_ly_do": list(lan["doi_soat_ly_do"]),
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
                if kind == "dich_vu":
                    # Slice 3 §6: ảnh chụp của CHÍNH lần chờ là khoản khách đang
                    # trả. Outstanding bill hiện tại đã loại các dòng ấy (vì lần
                    # chờ đang phủ chúng) và có thể có chỉ định MỚI của lần thu
                    # sau — so với nó thì luôn "lệch". Chỉ so đúng các nguồn đã
                    # chụp: nguồn đổi giá / đổi bên thu / bị huỷ mới là lệch.
                    hoa_don = await hoa_don_theo_anh_chup(
                        conn,
                        clinic_id=identity.clinic_id,
                        visit_id=visit_id,
                        cycle_id=payment_cycle_id,
                    )
                else:
                    hoa_don = await tinh_hoa_don(
                        conn,
                        clinic_id=identity.clinic_id,
                        visit_id=visit_id,
                        kind=kind,
                    )
                lech = hoa_don.revision != lan["bill_revision"]
                khong_ban_duoc: list[str] = []
                if kind == "thuoc" and bool(phan_lo) and not lan["legacy"]:
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
                    # CP6 Q3: bác sĩ đã đính chính dòng đơn trong lúc lần thu
                    # còn chờ. Tiền thật vẫn ghi đã thu, nhưng dòng lịch sử KHÔNG
                    # nhận SALE mới (DB cũng chặn) → không ghi bán cả lần thu,
                    # đối soát CHUA_GHI_BAN. Bán dở một phần sẽ khó đối soát hơn.
                    khong_ban_duoc += await _dong_da_dinh_chinh(
                        conn, identity.clinic_id, phan_lo
                    )
                # CP6: mã NGUYÊN NHÂN, không chỉ cờ — lịch sử phải nói đúng vì
                # sao lần thu này cần đối soát. DB ép cờ = có ít nhất một mã.
                ly_do_doi_soat = [
                    ma_ld
                    for ma_ld, co in (
                        (DOI_SOAT_HOA_DON_DOI, lech),
                        (DOI_SOAT_CHUA_GHI_BAN, bool(khong_ban_duoc)),
                    )
                    if co
                ]
                can_doi_soat = bool(ly_do_doi_soat)
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
                            reference = $3, payment_id = $4::uuid, can_doi_soat = $5,
                            doi_soat_ly_do = $6::text[]
                      WHERE payment_cycle_id = $1::uuid
                        AND status = 'PENDING_VERIFICATION'
                    """,
                    payment_cycle_id,
                    identity.staff_id,
                    ma,
                    payment_id,
                    can_doi_soat,
                    ly_do_doi_soat,
                )
                if kind == "dich_vu":
                    await _phat_da_thu_dich_vu(
                        conn,
                        cycle_id=payment_cycle_id,
                        visit_id=visit_id,
                        amount=int(lan["amount"]),
                        method=str(lan["method"]),
                        identity=identity,
                    )
                if kind == "thuoc":
                    # Chuyển khoản / QR vừa xác minh: ảnh chụp hoá đơn đã ghi từ
                    # lúc tạo lần chờ — giờ tiền mới thật sự nhận.
                    await _phat_thuoc_bi_bo(
                        conn,
                        identity=identity,
                        visit_id=visit_id,
                        cycle_id=payment_cycle_id,
                    )
                if (
                    kind == "thuoc"
                    and bool(phan_lo)
                    and not lan["legacy"]
                    and not khong_ban_duoc
                ):
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
            "doi_soat_ly_do": ly_do_doi_soat,
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
        await self._assert_kind_allowed(kind, identity)
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
                if phan_lo:
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
        await self._assert_kind_allowed(kind, identity)
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
                # Phiếu DỊCH VỤ huỷ không còn giữ phủ (thu lại được — 24/09/2026),
                # nên phiếu đã có khoản hoàn (đang chờ hoặc đã xong) không được
                # huỷ: huỷ thêm nữa là trả tiền khách hai lần. Tiền thuốc giữ
                # luật CP5 R7 riêng (đã hoàn vẫn huỷ được).
                if kind == "dich_vu" and await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM payment_refund"
                    " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
                    " AND status IN ('PENDING', 'COMPLETED'))",
                    identity.clinic_id,
                    payment_cycle_id,
                ):
                    raise ConflictError(
                        "Phiếu này đã có khoản hoàn tiền — không huỷ phiếu được. "
                        "Xử lý tiếp theo đường hoàn tiền."
                    )
                if kind == "dich_vu":
                    payment = await _huy_hinh_chieu_dich_vu(
                        conn,
                        lan=lan,
                        visit_id=visit_id,
                        identity=identity,
                        reason=normalized_reason,
                    )
                else:
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
                            "SELECT EXISTS (SELECT 1 FROM payment"
                            " WHERE visit_id = $1::uuid AND kind = $2"
                            " AND clinic_id = $3::uuid AND status = 'PAID'"
                            " AND payment_cycle_id = $4::uuid)",
                            visit_id,
                            kind,
                            identity.clinic_id,
                            payment_cycle_id,
                        ):
                            raise SafetyGateError(
                                "Chỉ thu ngân đã thu phiếu này (hoặc quản lý)"
                                " mới huỷ được."
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


async def _khoa_luot_thu(
    conn: asyncpg.Connection, visit_id: str, identity: StaffIdentity
) -> asyncpg.Record | None:
    """Khoá dòng ``visit`` (khoá đầu tiên của mọi lệnh thu) và đọc các mốc cần kiểm.

    "Khám xong" là trạng thái của LƯỢT (moc_kham_xong, review CP4): không INNER
    JOIN lịch hẹn — lượt không có lịch hẹn vẫn thu được. Lịch hẹn nếu có chỉ còn
    là kiểm chéo bệnh nhân. Khoá chỉ `visit`: mốc nằm trên visit, và Postgres
    không cho khoá phía có thể rỗng của LEFT JOIN.
    """
    return await conn.fetchrow(
        f"""
        SELECT
            {kham_xong_sql("v")} AS kham_xong,
            -- Đã có chỉ định chính thức — cùng luật hiện khách ở quầy dịch vụ
            -- (cashier_board_service), để màn và lệnh nói cùng một câu.
            EXISTS (
                SELECT 1 FROM service_order so
                 WHERE so.clinic_id = v.clinic_id AND so.visit_id = v.visit_id
                   AND so.selection_status IS NOT NULL
                   AND so.exec_status NOT IN ('draft', 'cancelled')
            ) AS co_chi_dinh,
            EXISTS (
                SELECT 1 FROM prescription rx
                 WHERE rx.clinic_id = v.clinic_id AND rx.visit_id = v.visit_id
                   AND rx.removed_at IS NULL
            ) AS co_don_thuoc,
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


def _kiem_luot_thu(
    status_row: asyncpg.Record | None,
    clinic_patient_id: str | None,
    *,
    can_kham_xong: bool = True,
    kind: str = "dich_vu",
) -> str:
    """Các chốt trước khi thu; trả mã bệnh nhân chuẩn của lượt.

    ``can_kham_xong=False`` cho TIỀN DỊCH VỤ (Tuyền chốt 23–24/09/2026): chỉ
    định đi làm ở phòng khác là "đợi quay lại", không phải khám xong — khách
    xuống lễ tân trả tiền dịch vụ ngay lúc phiên bác sĩ còn mở. Chỉ cần lượt
    ĐÃ CÓ chỉ định (chưa có gì ngoài tiền khám thì vẫn đợi khám xong — bác sĩ
    còn có thể chỉ định thêm). TIỀN THUỐC cũng vậy từ 24/09/2026 (nhóm 4): lượt
    đã có đơn là thu được; bác sĩ sửa đơn sau đó thì đi đường đính chính.
    """
    if status_row is None or not status_row["hen_khop"]:
        raise NotFoundError("Không tìm thấy lượt khám để thu tiền")
    if not status_row["staff_in_clinic"]:
        raise ValidationError("Nhân viên thu tiền không thuộc phòng khám này")
    authoritative_patient_id = str(status_row["clinic_patient_id"])
    if clinic_patient_id is not None and clinic_patient_id != authoritative_patient_id:
        raise ValidationError("Lượt khám không thuộc bệnh nhân thanh toán này")
    if not status_row["kham_xong"]:
        if can_kham_xong:
            raise ConflictError("Bác sĩ chưa khám xong lượt này — chưa thể thu tiền")
        if kind == "thuoc" and not status_row["co_don_thuoc"]:
            raise ConflictError(
                "Bác sĩ chưa khám xong lượt này và chưa kê đơn thuốc nào"
                " — chưa thể thu tiền thuốc"
            )
        if kind != "thuoc" and not status_row["co_chi_dinh"]:
            raise ConflictError(
                "Bác sĩ chưa khám xong lượt này và chưa có chỉ định dịch vụ nào"
                " — chưa thể thu tiền"
            )
    return authoritative_patient_id


async def _phat_thuoc_bi_bo(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    visit_id: str,
    cycle_id: str,
) -> None:
    """``medicine.declined`` cho từng dòng thuốc khách BỎ / LẤY BỚT ở BẢN CUỐI CÙNG
    THANH TOÁN (Tuyền 24/09/2026). So đơn hiện hành với ảnh chụp hoá đơn của
    chính lần thu này (``payment_bill_line``) — không suy từ trạng thái nào khác.
    Cùng giao dịch với lần thu: tiền nhận ⇔ sự kiện có.
    """
    rows = await conn.fetch(
        """
        SELECT r.id::text AS id, r.nguon, r.quantity_num,
               coalesce(sum(bl.quantity), 0) AS da_thu
          FROM public.prescription r
          LEFT JOIN public.payment_bill_line bl
            ON bl.clinic_id = r.clinic_id AND bl.payment_cycle_id = $3::uuid
           AND bl.source_type = 'prescription' AND bl.source_id = r.id::text
         WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
           AND r.removed_at IS NULL
         GROUP BY r.id, r.nguon, r.quantity_num
        """,
        identity.clinic_id,
        visit_id,
        cycle_id,
    )
    for r in rows:
        ke = r["quantity_num"]
        da_thu = Decimal(str(r["da_thu"]))
        # Bỏ hẳn (0) hoặc lấy bớt so với số kê. Số kê không rõ mà vẫn thu thì
        # không có gì để so — bỏ qua.
        if (ke is None and da_thu > 0) or (
            ke is not None and da_thu >= Decimal(str(ke))
        ):
            continue
        await emit_event(
            conn,
            ten="medicine.declined",
            clinic_id=identity.clinic_id,
            aggregate_id=visit_id,
            payload=ThuocBiBo(
                visit_id=visit_id,
                prescription_id=r["id"],
                payment_cycle_id=cycle_id,
                nguon=r["nguon"],
                so_ke=format(Decimal(str(ke)).normalize(), "f")
                if ke is not None
                else None,
                so_mua=format(da_thu.normalize(), "f"),
            ),
            boi=nguoi(identity),
            correlation_id=visit_id,
        )


async def _huy_hinh_chieu_dich_vu(
    conn: asyncpg.Connection,
    *,
    lan: asyncpg.Record,
    visit_id: str,
    identity: StaffIdentity,
    reason: str,
) -> dict[str, Any]:
    """Huỷ một lần thu dịch vụ khi lượt có thể có NHIỀU lần thu PAID (Slice 3).

    ``payment`` chỉ là hình chiếu cho reader cũ. Huỷ lần cũ không được làm mất
    nghĩa các lần PAID khác: hình chiếu chỉ đổi khi nó đang trỏ ĐÚNG lần bị huỷ
    — khi ấy dựng lại từ sổ, trỏ lần PAID còn hợp lệ gần nhất; không còn lần nào
    thì hình chiếu thành VOIDED như trước. Không sửa lịch sử lần thu nào.

    Ai huỷ được giữ nguyên luật 15/09/2026: chính người đã thu lần ấy, hoặc
    Quản lý. Trả thông tin lần bị huỷ cho sự kiện ``payment.voided``.
    """
    cycle_id = str(lan["payment_cycle_id"])
    if not (
        identity.co_vai({ClinicRole.MANAGEMENT})
        or str(lan["confirmed_by"] or "") == identity.staff_id
    ):
        raise SafetyGateError(
            "Chỉ thu ngân đã thu phiếu này (hoặc quản lý) mới huỷ được."
        )
    proj = await conn.fetchrow(
        """
        SELECT id, payment_cycle_id::text AS payment_cycle_id, status
          FROM payment
         WHERE visit_id = $1::uuid AND kind = 'dich_vu' AND clinic_id = $2::uuid
         FOR UPDATE
        """,
        visit_id,
        identity.clinic_id,
    )
    tro_dung = (
        proj is not None
        and proj["payment_cycle_id"] == cycle_id
        and proj["status"] == "PAID"
    )
    if not tro_dung and lan["legacy"]:
        # Lần thu cũ chỉ còn trong sổ sự kiện — như trước, không huỷ từ đây.
        raise ConflictError(
            "Lần thu này không phải phiếu thu hiện hành của lượt — "
            "không huỷ được từ đây."
        )
    if tro_dung:
        assert proj is not None
        thay = await conn.fetchrow(
            """
            SELECT payment_cycle_id, amount, confirmed_by, paid_at, bill_revision
              FROM payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND kind = 'dich_vu' AND status = 'PAID'
               AND payment_cycle_id <> $3::uuid
             ORDER BY paid_at DESC, created_at DESC, payment_cycle_id DESC
             LIMIT 1
            """,
            identity.clinic_id,
            visit_id,
            cycle_id,
        )
        if thay is not None:
            await conn.execute(
                """
                UPDATE payment
                   SET payment_cycle_id = $2::uuid, amount = $3, status = 'PAID',
                       paid_by_staff_id = $4::uuid, paid_at = $5,
                       bill_revision = $6, voided_at = NULL,
                       voided_by_staff_id = NULL, void_reason = NULL,
                       updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $7::uuid
                """,
                proj["id"],
                thay["payment_cycle_id"],
                thay["amount"],
                thay["confirmed_by"],
                thay["paid_at"],
                thay["bill_revision"],
                identity.clinic_id,
            )
        else:
            await conn.execute(
                """
                UPDATE payment
                   SET status = 'VOIDED', voided_at = now(),
                       voided_by_staff_id = $2::uuid, void_reason = $3,
                       updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $4::uuid
                """,
                proj["id"],
                identity.staff_id,
                reason,
                identity.clinic_id,
            )
    return {
        "id": proj["id"] if proj is not None else cycle_id,
        "amount": int(lan["amount"]),
        "paid_by_staff_id": lan["confirmed_by"],
        "paid_at": lan["paid_at"],
    }


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
        -- dich_vu thu được NHIỀU lần (Slice 3): hình chiếu trỏ lần thu PAID mới
        -- nhất để reader cũ còn sống; sự thật tài chính là payment_cycle +
        -- payment_bill_line, không phải dòng này. thuoc giữ luật cũ.
        WHERE payment.clinic_id = EXCLUDED.clinic_id
          AND (payment.status = 'VOIDED' OR EXCLUDED.kind = 'dich_vu')
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
    # Sự kiện CHUẨN khi tiền thật sự đã nhận (CHECKPOINT §6): tiền mặt thu
    # xong, hoặc chuyển khoản/QR xác minh xong. Trước 22/09/2026 tên là
    # "payment.recorded" — lịch sử cũ giữ nguyên, không viết lại.
    if kind == "thuoc":
        # Sổ sự kiện mới (dòng thời gian). Tiền dịch vụ phát riêng sau khi ảnh
        # chụp hoá đơn đã ghi (`_phat_da_thu_dich_vu`).
        await emit_event(
            conn,
            ten="payment.medicine_collected",
            clinic_id=identity.clinic_id,
            aggregate_id=cycle_id,
            payload=TienThuocDaThu(
                visit_id=visit_id,
                payment_cycle_id=cycle_id,
                so_tien=int(amount),
                phuong_thuc=method or "CASH",
            ),
            boi=nguoi(identity),
            correlation_id=visit_id,
        )
    await _log_payment_event(
        conn,
        event_type="payment.confirmed",
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


async def _dong_da_dinh_chinh(
    conn: asyncpg.Connection, clinic_id: str, phan_lo: list[PhanLo]
) -> list[str]:
    """Phân lô của lần thu mà dòng đơn đã được bác sĩ đính chính (lịch sử)."""
    if not phan_lo:
        return []
    rows = await conn.fetch(
        """
        SELECT drug_name_raw FROM public.prescription
         WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
           AND removed_at IS NOT NULL
         ORDER BY id
        """,
        clinic_id,
        sorted({p.prescription_id for p in phan_lo}),
    )
    return [
        f"“{r['drug_name_raw']}” đã được bác sĩ đính chính — không ghi bán"
        for r in rows
    ]


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


async def _phat_da_thu_dich_vu(
    conn: asyncpg.Connection,
    *,
    cycle_id: str,
    visit_id: str,
    amount: int,
    method: str,
    identity: StaffIdentity,
) -> None:
    """`payment.service_collected` vào sổ sự kiện — CÙNG giao dịch với lần thu.

    Gọi SAU khi ảnh chụp hoá đơn đã ghi (các dòng `payment_bill_line`), để sự
    kiện kể đúng lần thu này phủ những chỉ định nào. Khối Hành trình nghe nó để
    xếp phòng (dây H4); dòng thời gian ghi "đã thu".
    """
    order_ids = [
        str(r["source_id"])
        for r in await conn.fetch(
            "SELECT source_id FROM payment_bill_line"
            " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
            "   AND source_type = 'service_order' AND billing_owner = 'CLINIC'"
            " ORDER BY source_id",
            identity.clinic_id,
            cycle_id,
        )
    ]
    await emit_event(
        conn,
        ten="payment.service_collected",
        clinic_id=identity.clinic_id,
        aggregate_id=cycle_id,
        payload=TienDichVuDaThu(
            visit_id=visit_id,
            payment_cycle_id=cycle_id,
            so_tien=int(amount),
            phuong_thuc=method,
            order_ids=order_ids,
        ),
        boi=nguoi(identity),
        correlation_id=visit_id,
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
