"""FastAPI endpoints for visit payments (Phase 4, cluster #3).

Thin router: server-authoritative role via ``require_role`` (identity #1a), then
delegate to ``PaymentService``. Domain errors (ConflictError/NotFoundError/
SafetyGateError) are mapped to HTTP by the global handlers in ``main.py``.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field, field_validator

from clinicai.api.idempotency import (
    IdempotencyGuard,
    idempotency_guard,
    tra_khoa_neu_bi_tu_choi,
)
from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService

router = APIRouter()

# Roles allowed to touch payments at all; the finer kind↔role rule is in the service.
_CASHIER_GUARD = require_role(
    # Lễ tân kiêm thu ngân (Tuyền 16/09/2026).
    ClinicRole.RECEPTION,
    ClinicRole.CASHIER,
    ClinicRole.CASHIER_THUOC,
    ClinicRole.CASHIER_DV,
    ClinicRole.MANAGEMENT,
)

PaymentKind = Literal["thuoc", "dich_vu"]
PaymentMethod = Literal["CASH", "TRANSFER", "QR"]


class PaymentRecordRequest(BaseModel):
    """Body for recording a payment."""

    visit_id: UUID
    kind: PaymentKind
    # Chỉ để ĐỐI CHIẾU: máy chủ tự tính tiền (contract tiền–thuốc C3).
    amount: float | None = None
    clinic_patient_id: UUID | None = None
    # Dấu hoá đơn thu ngân đang nhìn; khác hoá đơn máy chủ → 409 BILL_CHANGED.
    bill_revision: str | None = Field(default=None, max_length=64)
    # Tiền mặt → PAID ngay; chuyển khoản/QR → chờ xác minh (contract A2).
    method: PaymentMethod = "CASH"


class PaymentVoidRequest(BaseModel):
    """Body for voiding (undoing) a payment — nhắm ĐÚNG một lần thu."""

    payment_cycle_id: UUID
    visit_id: UUID
    kind: PaymentKind
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def strip_reason(cls, value: object) -> object:
        """Reject whitespace-only reasons after normalising surrounding space."""
        return value.strip() if isinstance(value, str) else value


@router.post("/payments")
async def record_payment(
    body: PaymentRecordRequest,
    # Cửa ngoài chỉ "đã đăng nhập": tiền dịch vụ hỏi QUYỀN, tiền thuốc hỏi vai —
    # cả hai trong PaymentService (CORE-B3). Các lệnh khác vẫn qua _CASHIER_GUARD.
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Một lần thu. Tiền mặt → PAID; chuyển khoản/QR → chờ xác minh."""
    if body.kind == "dich_vu":
        # Lifecycle v1 Slice 3: tiền dịch vụ dùng BIÊN NHẬN TRONG CÙNG giao dịch
        # (command_receipt) — một cơ chế chống trùng, khoá bắt buộc. Không đi
        # qua IdempotencyGuard: biên nhận của nó lưu SAU giao dịch nghiệp vụ.
        lan_thu = await PaymentService(pool).record_payment(
            visit_id=str(body.visit_id),
            kind=body.kind,
            amount=body.amount,
            clinic_patient_id=(
                str(body.clinic_patient_id) if body.clinic_patient_id else None
            ),
            bill_revision=body.bill_revision,
            method=body.method,
            identity=identity,
            idempotency_key=idempotency_key,
        )
        return {"ok": True, **lan_thu}
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    # Bọc trả khoá: bị từ chối vì lý do nghiệp vụ (4xx) thì khoá phải được
    # trả lại ngay, kẻo lần bấm lại sau khi sửa vẫn nhận 409 suốt 5 phút và
    # câu giải thích thật biến mất. Xem `IdempotencyGuard.release`.
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        service = PaymentService(pool)
        lan_thu = await service.record_payment(
            visit_id=str(body.visit_id),
            kind=body.kind,
            amount=body.amount,
            clinic_patient_id=(
                str(body.clinic_patient_id) if body.clinic_patient_id else None
            ),
            bill_revision=body.bill_revision,
            method=body.method,
            identity=identity,
        )
        result = {"ok": True, **lan_thu}
        await idem.save(pool, result, status_code=200)

    return result


@router.delete("/payments")
async def void_payment(
    body: PaymentVoidRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Huỷ ĐÚNG phiếu thu được nhắm, giữ nguyên lịch sử bất biến."""
    kq = await PaymentService(pool).void_payment(
        payment_cycle_id=str(body.payment_cycle_id),
        visit_id=str(body.visit_id),
        kind=body.kind,
        reason=body.reason,
        identity=identity,
    )
    return {"ok": True, **kq}


class XacMinhRequest(BaseModel):
    """Xác minh chuyển khoản/QR đã nhận tiền, kèm mã giao dịch ngân hàng."""

    payment_cycle_id: UUID
    visit_id: UUID
    kind: PaymentKind
    reference: str = Field(min_length=3, max_length=100)


@router.post("/payments/xac-minh")
async def xac_minh_dien_tu(
    body: XacMinhRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lần chuyển khoản/QR chờ xác minh → PAID (contract tiền–thuốc A2)."""
    kq = await PaymentService(pool).xac_minh_dien_tu(
        payment_cycle_id=str(body.payment_cycle_id),
        visit_id=str(body.visit_id),
        kind=body.kind,
        reference=body.reference,
        identity=identity,
    )
    return {"ok": True, **kq}


class HuyChoRequest(BaseModel):
    payment_cycle_id: UUID
    visit_id: UUID
    kind: PaymentKind
    reason: str = Field(min_length=5, max_length=500)


@router.post("/payments/huy-cho")
async def huy_cho_xac_minh(
    body: HuyChoRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Huỷ lần chuyển khoản/QR chờ xác minh (chưa từng thu)."""
    kq = await PaymentService(pool).huy_cho_xac_minh(
        payment_cycle_id=str(body.payment_cycle_id),
        visit_id=str(body.visit_id),
        kind=body.kind,
        reason=body.reason,
        identity=identity,
    )
    return {"ok": True, **kq}


# ── Hoàn tiền (contract tiền–thuốc CP5) ────────────────────────────────────
# Cửa ngoài giữ nguyên nhóm thu ngân; QUYỀN HOÀN do service kiểm
# (VAI_HOAN_TIEN_TAM_THOI — tạm thời chỉ Quản lý, HOLD J4).


class DongHoanRequest(BaseModel):
    payment_bill_line_id: UUID
    so_luong: float = Field(gt=0)


class HoanTienRequest(BaseModel):
    payment_cycle_id: UUID
    visit_id: UUID
    kind: PaymentKind
    method: PaymentMethod
    reason: str = Field(min_length=5, max_length=500)
    dong: list[DongHoanRequest] = Field(min_length=1)


@router.post("/payments/hoan-tien")
async def hoan_tien(
    body: HoanTienRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Hoàn tiền theo dòng ảnh chụp hoá đơn; số tiền do máy chủ tính.

    CHỐNG GỬI TRÙNG (review CP5 P1-A): hoàn một phần là hợp lệ, nên máy chủ
    không phân biệt được "gửi lại vì mất phản hồi" với "hoàn thêm lần nữa" —
    trừ khi người gọi nói ra bằng `Idempotency-Key`. Cùng khoá → trả lại kết
    quả lần đầu, không tạo khoản hoàn thứ hai.
    """
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq = await _tao_hoan(body, identity, pool)
        await idem.save(pool, kq, status_code=200)
    return kq


async def _tao_hoan(
    body: HoanTienRequest, identity: StaffIdentity, pool: asyncpg.Pool
) -> dict[str, Any]:
    kq = await HoanTienService(pool).tao(
        identity=identity,
        payment_cycle_id=str(body.payment_cycle_id),
        visit_id=str(body.visit_id),
        kind=body.kind,
        dong=[
            {
                "payment_bill_line_id": str(d.payment_bill_line_id),
                "so_luong": d.so_luong,
            }
            for d in body.dong
        ],
        method=body.method,
        reason=body.reason,
    )
    return {"ok": True, **kq}


class XacNhanHoanRequest(BaseModel):
    refund_id: UUID
    reference: str = Field(min_length=3, max_length=100)


@router.post("/payments/hoan-tien/xac-nhan")
async def xac_nhan_hoan(
    body: XacNhanHoanRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khoản hoàn chuyển khoản / QR đã chuyển xong (kèm mã giao dịch)."""
    kq = await HoanTienService(pool).xac_nhan(
        identity=identity, refund_id=str(body.refund_id), reference=body.reference
    )
    return {"ok": True, **kq}


class DongKhoanHoanRequest(BaseModel):
    refund_id: UUID
    trang_thai: Literal["FAILED", "CANCELLED"]
    reason: str = Field(min_length=5, max_length=500)


@router.post("/payments/hoan-tien/dong")
async def dong_khoan_hoan(
    body: DongKhoanHoanRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khoản hoàn đang chờ → FAILED (thử không thành) hoặc CANCELLED (huỷ yêu cầu)."""
    kq = await HoanTienService(pool).dong(
        identity=identity,
        refund_id=str(body.refund_id),
        trang_thai=body.trang_thai,
        reason=body.reason,
    )
    return {"ok": True, **kq}
