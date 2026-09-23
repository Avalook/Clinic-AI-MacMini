"""Nhà thuốc: hàng đợi đơn, tồn kho, và bốn thao tác ghi.

Trước file này, bốn màn `/pharmacy` đọc thẳng Supabase và không có đường ghi
nào — RLS chỉ cấp SELECT, nên kể cả có nút thì trình duyệt cũng không ghi được.
Mọi thao tác kho đi qua đây, chạy `service_role` phía sau, đúng luật CLAUDE.md:
"Frontend = UI only. All business logic belongs in the FastAPI backend."
"""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from clinicai.api.idempotency import (
    IdempotencyGuard,
    idempotency_guard,
    tra_khoa_neu_bi_tu_choi,
)
from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import ban_thuoc_service
from clinicai.services.pharmacy_service import PharmacyService

router = APIRouter()

# ĐỌC mở rộng hơn GHI. Thu ngân thuốc cần thấy đơn để thu tiền, Trưởng ca và
# Quản lý cần thấy tồn để biết sắp hết gì — nhưng chỉ người giữ khối "Nhà thuốc"
# mới được chạm vào kho. Hỏi QUYỀN, không hỏi vai (24/09/2026, migration
# 20260924000013): cấp khối trên màn Phân quyền là có hiệu lực ngay.
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")


@router.get("/pharmacy/queue")
async def hang_doi(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đơn thuốc chưa chốt — gồm cả đơn đã cấp một phần."""
    return {"items": await PharmacyService(pool).hang_doi(identity=identity)}


@router.get("/pharmacy/ban-thuoc")
async def man_nha_thuoc(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Màn Nhà thuốc (contract tiền–thuốc CP4): lượt → dòng đơn → phân lô, kèm
    giai đoạn tiền thuốc và các thao tác được phép — máy chủ quyết, giao diện vẽ."""
    kq: dict[str, Any] = jsonable_encoder(
        await ban_thuoc_service.man_nha_thuoc(pool, identity=identity)
    )
    return kq


@router.get("/pharmacy/inventory")
async def ton_kho(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tồn theo lô, kèm hạn dùng và cờ hết hạn."""
    return {"items": await PharmacyService(pool).ton_kho(identity=identity)}


class NhapLoRequest(BaseModel):
    drug_catalog_id: UUID
    so_luong: float = Field(gt=0)
    # Cả ba BẮT BUỘC: `drug_batch` khai NOT NULL. Xem PharmacyService.nhap_lo.
    batch_code: str = Field(min_length=1, max_length=100)
    expiry_date: date
    unit: str = Field(min_length=1, max_length=50)
    cost_price: float | None = Field(default=None, ge=0)
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/receive", status_code=201)
async def nhap_lo(
    body: NhapLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhập hàng vào kho."""
    return await PharmacyService(pool).nhap_lo(
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id),
        so_luong=body.so_luong,
        batch_code=body.batch_code,
        expiry_date=body.expiry_date,
        unit=body.unit,
        cost_price=body.cost_price,
        ly_do=body.ly_do,
    )


class CapPhatRequest(BaseModel):
    prescription_id: UUID
    drug_batch_id: UUID
    so_luong: float = Field(gt=0)


@router.post("/pharmacy/dispense", status_code=201)
async def cap_phat(
    body: CapPhatRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Cấp thuốc cho một dòng đơn. Cấp một phần là chuyện bình thường.

    CHỐNG GỬI TRÙNG — thêm 16/09/2026 sau khi đo được cảnh sau: hai lời gọi
    cấp 1 viên bắn cùng lúc, cả hai trả 201, và lô nhập 50 viên còn **48**.
    Trừ tồn hai lần.

    Vì sao chuyện này không tự chặn được như `/payments`: ở đó một lượt khám
    chỉ có một khoản thu mỗi loại nên ghi đè là đủ, còn ở đây **cấp một phần là
    hợp lệ** — hệ thống không có cách nào phân biệt "bấm nhầm hai lần" với "cố
    ý cấp thêm một viên nữa" nếu người gọi không nói ra. Khoá chống-gửi-trùng
    chính là chỗ người gọi nói ra điều đó: một lần bấm = một khoá, gửi lại bao
    nhiêu lần cũng chỉ trừ tồn một lần.

    Đây là cửa ghi DUY NHẤT động vào vật thật (thuốc), và trước bản này nó là
    cửa ghi duy nhất trong hệ không có lớp bảo vệ ấy.
    """
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        # `jsonable_encoder` TRƯỚC KHI CẤT, không phải sau.
        #
        # Kết quả cấp thuốc mang số lượng tồn dưới dạng `Decimal` — đúng kiểu
        # cho tiền và cho thuốc, nhưng `json.dumps` của lớp chống-gửi-trùng
        # không nuốt được, và nó nổ thành 500 ĐÚNG Ở LẦN BẤM THỨ HAI. Người
        # dùng thấy "lỗi máy chủ" cho một thao tác thực ra đã thành công.
        # `/payments` không vấp vì nó cất `{"ok": true}`.
        ket_qua: dict[str, Any] = jsonable_encoder(
            await PharmacyService(pool).cap_phat(
                identity=identity,
                prescription_id=str(body.prescription_id),
                drug_batch_id=str(body.drug_batch_id),
                so_luong=body.so_luong,
            )
        )
        # Ghi TRONG khối trả-khoá, giống `/payments`: đặt ngoài thì một lỗi
        # nghiệp vụ ở giữa sẽ trả khoá về rồi mới ghi, và lần bấm lại nhận một
        # kết quả cũ của thao tác chưa từng xảy ra.
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class TuChoiRequest(BaseModel):
    prescription_id: UUID
    # Lý do BẮT BUỘC — xem PharmacyService.tu_choi.
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/refuse", status_code=201)
async def tu_choi(
    body: TuChoiRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khách không lấy thuốc."""
    return await PharmacyService(pool).tu_choi(
        identity=identity,
        prescription_id=str(body.prescription_id),
        ly_do=body.ly_do,
    )


class ChotRequest(BaseModel):
    prescription_id: UUID
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/close-line", status_code=201)
async def chot(
    body: ChotRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Không cấp thêm nữa — dùng cho 'lấy 5 rồi thôi' và cho đơn đã cấp đủ."""
    return await PharmacyService(pool).chot(
        identity=identity,
        prescription_id=str(body.prescription_id),
        ly_do=body.ly_do,
    )


class DieuChinhRequest(BaseModel):
    drug_batch_id: UUID
    # Mang dấu: âm là bớt, dương là thêm. 0 bị từ chối ở service.
    so_luong: float
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/adjust", status_code=201)
async def dieu_chinh(
    body: DieuChinhRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Kiểm kê lệch."""
    return await PharmacyService(pool).dieu_chinh(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
    )


class HuyRequest(BaseModel):
    drug_batch_id: UUID
    so_luong: float = Field(gt=0)
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/discard", status_code=201)
async def huy(
    body: HuyRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Huỷ thuốc hỏng hoặc hết hạn. Ra khỏi kho nhưng không ra khỏi sổ."""
    return await PharmacyService(pool).huy(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
    )


class XacDinhThuocRequest(BaseModel):
    prescription_id: UUID
    drug_catalog_id: UUID


@router.post("/pharmacy/xac-dinh-thuoc")
async def xac_dinh_thuoc(
    body: XacDinhThuocRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gắn dòng đơn với một thuốc trong danh mục kho (contract tiền–thuốc C1)."""
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).xac_dinh_thuoc(
            identity=identity,
            prescription_id=str(body.prescription_id),
            drug_catalog_id=str(body.drug_catalog_id),
        )
    )
    return kq


class SoLuongMuaRequest(BaseModel):
    prescription_id: UUID
    so_luong: float = Field(ge=0)


@router.post("/pharmacy/so-luong-mua")
async def khai_so_luong_mua(
    body: SoLuongMuaRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Số khách đồng ý mua (contract tiền–thuốc C2)."""
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).khai_so_luong_mua(
            identity=identity,
            prescription_id=str(body.prescription_id),
            so_luong=body.so_luong,
        )
    )
    return kq


class PhanLoRequest(BaseModel):
    prescription_id: UUID
    drug_batch_id: UUID
    so_luong: float = Field(gt=0)


@router.post("/pharmacy/phan-lo")
async def phan_lo(
    body: PhanLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chọn lô cho dòng đơn trước khi thu tiền thuốc (contract tiền–thuốc CP3).

    Bấm trùng không tạo hai phân lô: mỗi (dòng đơn, lô) chỉ có một phân lô còn
    hiệu lực — ép bằng chỉ mục duy nhất ở DB.
    """
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).phan_lo(
            identity=identity,
            prescription_id=str(body.prescription_id),
            drug_batch_id=str(body.drug_batch_id),
            so_luong=body.so_luong,
        )
    )
    return kq


class BoPhanLoRequest(BaseModel):
    allocation_id: UUID
    ly_do: str


@router.post("/pharmacy/bo-phan-lo")
async def bo_phan_lo(
    body: BoPhanLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ một lô đã chọn, chưa gắn lần thu."""
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).bo_phan_lo(
            identity=identity,
            allocation_id=str(body.allocation_id),
            ly_do=body.ly_do,
        )
    )
    return kq


class DoiLoRequest(BaseModel):
    allocation_id: UUID
    drug_batch_id: UUID
    ly_do: str


@router.post("/pharmacy/doi-lo")
async def doi_lo_khi_cho(
    body: DoiLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi lô đang giữ cho lần chuyển khoản/QR chờ xác minh."""
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).doi_lo_khi_cho(
            identity=identity,
            allocation_id=str(body.allocation_id),
            drug_batch_id=str(body.drug_batch_id),
            ly_do=body.ly_do,
        )
    )
    return kq


class HuyChuaGiaoRequest(BaseModel):
    prescription_id: UUID
    ly_do: str


@router.post("/pharmacy/huy-phan-chua-giao")
async def huy_phan_chua_giao(
    body: HuyChuaGiaoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Nhả phần đã bán mà chưa giao (CP5) — cần căn cứ: huỷ phiếu / đã hoàn tiền.

    Sổ kho đã chặn đảo hai lần; khoá chống-gửi-trùng để lần gửi lại nhận đúng
    kết quả lần đầu thay vì câu "không còn phần chưa giao" gây hoảng.
    """
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq: dict[str, Any] = jsonable_encoder(
            await PharmacyService(pool).huy_phan_chua_giao(
                identity=identity,
                prescription_id=str(body.prescription_id),
                ly_do=body.ly_do,
            )
        )
        await idem.save(pool, kq, status_code=200)
    return kq


class KhachTraRequest(BaseModel):
    dispense_txn_id: UUID
    so_luong: float = Field(gt=0)
    ly_do: str


@router.post("/pharmacy/khach-tra")
async def khach_tra_thuoc(
    body: KhachTraRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Ghi nhận thuốc khách trả lại quầy (CP5) — chưa quyết xử lý (HOLD J1/J2).

    CHỐNG GỬI TRÙNG (review CP5 P1-A): trả nhiều lần là hợp lệ, DB chỉ chặn tổng
    trả ≤ số đã giao — nên gửi lại sau khi mất phản hồi sẽ thành "khách trả
    thêm". Cùng `Idempotency-Key` → không có lần trả / RETURN_RECEIVED thứ hai.
    """
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq: dict[str, Any] = jsonable_encoder(
            await PharmacyService(pool).khach_tra_thuoc(
                identity=identity,
                dispense_txn_id=str(body.dispense_txn_id),
                so_luong=body.so_luong,
                ly_do=body.ly_do,
            )
        )
        await idem.save(pool, kq, status_code=200)
    return kq
