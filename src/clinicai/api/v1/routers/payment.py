"""FastAPI endpoints for visit payments (Phase 4, cluster #3).

Thin router: server-authoritative role via ``require_role`` (identity #1a), then
delegate to ``PaymentService``. Domain errors (ConflictError/NotFoundError/
SafetyGateError) are mapped to HTTP by the global handlers in ``main.py``.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from clinicai.api.exceptions import ValidationError
from clinicai.api.idempotency import (
    IdempotencyGuard,
    idempotency_guard,
    tra_khoa_neu_bi_tu_choi,
)
from clinicai.api.identity import (
    StaffIdentity,
    get_current_identity,
)
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.doi_hinh_thuc_service import DoiHinhThucService
from clinicai.services.hoan_tien_service import HoanTienService
from clinicai.services.payment_service import PaymentService

router = APIRouter()

# Ai đụng được vào tiền: người giữ một trong hai khối thu tiền (24/09/2026 —
# thay tập vai cũ, cùng người: Lễ tân, Thu ngân (+DV/+Thuốc), Dược sĩ, Quản lý).
# Loại tiền nào ai được làm do PaymentService hỏi quyền của đúng loại ấy.
_CASHIER_GUARD = cua_quyen("payment.service.collect", "payment.medicine.collect")

PaymentKind = Literal["thuoc", "dich_vu"]
#: QR vẫn NHẬN (client cũ không gãy) nhưng ghi là Chuyển khoản (01/10/2026).
PaymentMethod = Literal["CASH", "TRANSFER", "QR"]


class PhanThuRequest(BaseModel):
    """Một phần của lần thu theo hình thức (01/10/2026). Kiểu lỏng: luật (hình
    thức hợp lệ, số > 0, không trùng, khách đưa ≥ tiền mặt) ở
    ``phan_thu.doc_phan`` — một nơi, câu lỗi tiếng Việt."""

    hinh_thuc: Any = None
    so_tien: Any = None
    khach_dua: Any = None


class LuaChonKhiThu(BaseModel):
    """Lựa chọn dịch vụ khách đang nhìn lúc bấm Thu (quầy một hoá đơn, 27/09).

    Kiểu lỏng (list/int bất kỳ): luật hình dạng nằm ở ``validate_input`` của
    lệnh xác nhận — một nơi, cùng mã lỗi ổn định."""

    order_ids_seen: list[Any] = Field(default_factory=list, max_length=100)
    selected_order_ids: list[Any] = Field(default_factory=list, max_length=100)
    expected_selection_revision: Any = None


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
    # Chỉ tiền dịch vụ: bấm Thu = máy chủ chốt lựa chọn + ghi sổ, MỘT giao dịch.
    chon: LuaChonKhiThu | None = None
    # Chia lần thu theo hình thức (Tiền mặt + Chuyển khoản) — 01/10/2026.
    phan: list[PhanThuRequest] | None = Field(default=None, max_length=5)


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
            chon=body.chon.model_dump() if body.chon is not None else None,
            phan=_phan(body),
        )
        return {"ok": True, **lan_thu}
    if body.chon is not None:
        raise ValidationError("Lựa chọn dịch vụ chỉ đi kèm lần thu tiền dịch vụ.")
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
            phan=_phan(body),
        )
        result = {"ok": True, **lan_thu}
        await idem.save(pool, result, status_code=200)

    return result


def _phan(body: PaymentRecordRequest) -> list[dict[str, Any]] | None:
    return [p.model_dump() for p in body.phan] if body.phan is not None else None


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
    #: Tuỳ chọn (24/09/2026) — thu QR/chuyển khoản xong không bắt nhập mã.
    reference: str | None = Field(default=None, max_length=100)


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


# ── Đổi hình thức thu sau khi đã thu (V7, 30/09/2026) ──────────────────────
# AI CŨNG ĐỔI ĐƯỢC: người giữ một trong hai khối thu tiền (cửa ngoài), không
# theo loại phiếu. Luật đổi được / không (đã huỷ, có hoàn) ở service + trigger.


class DoiHinhThucRequest(BaseModel):
    payment_cycle_id: UUID
    #: Một hình thức cho cả phiếu; bỏ trống khi gửi CHIA (tien_mat + chuyen_khoan).
    hinh_thuc: PaymentMethod | None = None
    #: Hình thức màn đang thấy — người khác vừa đổi thì 409, không đè.
    hinh_thuc_cu: PaymentMethod | None = None
    #: Tuỳ chọn, như lúc thu (mig 20260925000007).
    reference: str | None = Field(default=None, max_length=100)
    ly_do: str | None = Field(default=None, max_length=500)
    #: Đổi sang CHIA (01/10/2026): cả hai số, tổng = số tiền phiếu.
    tien_mat: float | None = None
    chuyen_khoan: float | None = None


@router.post("/payments/doi-hinh-thuc")
async def doi_hinh_thuc(
    body: DoiHinhThucRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi TM / CK / QR của một phiếu đã thu — một dòng sổ chỉ thêm, không huỷ."""
    kq = await DoiHinhThucService(pool).doi(
        identity=identity,
        payment_cycle_id=str(body.payment_cycle_id),
        hinh_thuc=body.hinh_thuc,
        hinh_thuc_cu=body.hinh_thuc_cu,
        reference=body.reference,
        ly_do=body.ly_do,
        tien_mat=body.tien_mat,
        chuyen_khoan=body.chuyen_khoan,
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


# ── Hoàn tác lần thu (Tuyền 01/10/2026) ────────────────────────────────────
# MỘT nút cho mọi lần thu: đã thu → huỷ phiếu; chuyển khoản chờ → huỷ lần chờ.
# Ai giữ quyền thu đúng loại tiền ấy là làm được (service kiểm). Lý do tuỳ chọn.


class HoanTacRequest(BaseModel):
    payment_cycle_id: UUID
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/payments/hoan-tac")
async def hoan_tac_lan_thu(
    body: HoanTacRequest,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác đúng một lần thu — lượt về chưa thu, giữ nguyên vết."""
    kq = await PaymentService(pool).hoan_tac(
        payment_cycle_id=str(body.payment_cycle_id),
        ly_do=body.ly_do,
        identity=identity,
    )
    return {"ok": True, **kq}


# ── Ảnh chuyển khoản (01/10/2026) ───────────────────────────────────────────


@router.post("/payments/anh-chuyen-khoan", status_code=201)
async def tai_anh_chuyen_khoan(
    request: Request,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tải ảnh màn hình chuyển khoản cho một lần thu (multipart: file,
    payment_cycle_id). Quyền kiểm trước khi đọc byte nào của thân."""
    from clinicai.services.anh_chuyen_khoan_service import AnhChuyenKhoanService
    from clinicai.services.nhan_tep_luong import (
        don_tep_tam,
        nhan_multipart,
        uuid_hoac_loi,
    )

    truong, tep = await nhan_multipart(request)
    try:
        return await AnhChuyenKhoanService(pool).tai_len(
            identity=identity,
            payment_cycle_id=str(
                uuid_hoac_loi(
                    truong.get("payment_cycle_id"), "Mã lần thu", bat_buoc=True
                )
            ),
            tep=tep,
        )
    finally:
        await don_tep_tam(tep)


@router.get("/payments/anh-chuyen-khoan/{anh_id}")
async def xem_anh_chuyen_khoan(
    anh_id: UUID,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Nội dung ảnh (ảnh nhỏ — đọc trọn, không theo luồng)."""
    from clinicai.services.anh_chuyen_khoan_service import AnhChuyenKhoanService

    noi_dung, mime = await AnhChuyenKhoanService(pool).doc(
        identity=identity, anh_id=str(anh_id)
    )
    return Response(
        content=noi_dung,
        media_type=mime,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/payments/anh-chuyen-khoan/{anh_id}/go")
async def go_anh_chuyen_khoan(
    anh_id: UUID,
    identity: StaffIdentity = Depends(_CASHIER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ ảnh nhầm (ẩn khỏi màn, giữ tệp + vết)."""
    from clinicai.services.anh_chuyen_khoan_service import AnhChuyenKhoanService

    return await AnhChuyenKhoanService(pool).go(identity=identity, anh_id=str(anh_id))
