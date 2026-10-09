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
from clinicai.services import (
    ban_theo_don_service,
    ban_thuoc_service,
    kho_thuoc_service,
)
from clinicai.services.ban_le_service import QUYEN_MO, BanLeService
from clinicai.services.pharmacy_service import GIU_NGUYEN, PharmacyService

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


# ── Khách chỉ đến mua thuốc — lượt Bán lẻ (V8, 30/09/2026) ─────────────────
# "MỞ HẾT": ai giữ lego nhà thuốc hoặc thu tiền đều mở được. Service kiểm lại.
_BAN_LE = cua_quyen(*QUYEN_MO)


@router.get("/pharmacy/ban-le/tim-khach")
async def ban_le_tim_khach(
    q: str = "",
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tìm khách theo SĐT / mã / tên (không dấu) để mở lượt mua thuốc."""
    kq: dict[str, Any] = jsonable_encoder(
        await BanLeService(pool).tim_khach(q=q, identity=identity)
    )
    return kq


class KhachMoiBanLe(BaseModel):
    ho_ten: str = Field(min_length=1, max_length=200)
    sdt: str | None = Field(default=None, max_length=20)
    # Chuỗi/số tuỳ ý: rác → bỏ trống (service `nam_sinh`), không 422.
    nam_sinh: Any = None
    gioi_tinh: str | None = Field(default=None, max_length=20)
    force: bool = False


class MoBanLeRequest(BaseModel):
    clinic_patient_id: UUID | None = None
    khach_moi: KhachMoiBanLe | None = None


@router.post("/pharmacy/ban-le")
async def mo_ban_le(
    body: MoBanLeRequest,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mở (hoặc lấy lại) lượt bán lẻ đang mở của khách — không tiền khám, không
    hàng chờ. Khách mới trùng SĐT → trả `trung` để chọn hồ sơ có sẵn."""
    return await BanLeService(pool).mo_luot(
        identity=identity,
        clinic_patient_id=(
            str(body.clinic_patient_id) if body.clinic_patient_id else None
        ),
        khach_moi=body.khach_moi.model_dump() if body.khach_moi else None,
    )


class NoiDonRequest(BaseModel):
    visit_id: UUID
    don_goc_visit_id: UUID


@router.post("/pharmacy/ban-le/theo-don")
async def ban_le_theo_don(
    body: NoiDonRequest,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """ "Bán theo đơn này": nối lượt bán lẻ về đơn gốc + thêm dòng số còn lại."""
    return await ban_theo_don_service.noi_don(
        pool,
        identity,
        visit_id=str(body.visit_id),
        don_goc_visit_id=str(body.don_goc_visit_id),
    )


@router.get("/pharmacy/ban-le/don-gan-nhat")
async def ban_le_don_gan_nhat(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Vừa chọn khách cũ ở quầy (chưa mở lượt) → đơn gần nhất để xem."""
    kq: dict[str, Any] = jsonable_encoder(
        await BanLeService(pool).don_gan_nhat(
            clinic_patient_id=str(clinic_patient_id), identity=identity
        )
    )
    return kq


class MoTheoDonRequest(BaseModel):
    clinic_patient_id: UUID
    don_goc_visit_id: UUID


@router.post("/pharmacy/ban-le/mo-theo-don")
async def ban_le_mo_theo_don(
    body: MoTheoDonRequest,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Một giao dịch: mở / lấy lại lượt bán lẻ + nối đơn gốc + thêm dòng."""
    return await BanLeService(pool).mo_theo_don(
        clinic_patient_id=str(body.clinic_patient_id),
        don_goc_visit_id=str(body.don_goc_visit_id),
        identity=identity,
    )


class GoDonRequest(BaseModel):
    visit_id: UUID


@router.post("/pharmacy/ban-le/go-don")
async def ban_le_go_don(
    body: GoDonRequest,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác "Bán theo đơn này" khi tiền thuốc chưa thu."""
    return await ban_theo_don_service.go_noi_don(
        pool, identity, visit_id=str(body.visit_id)
    )


@router.get("/pharmacy/ban-le/{visit_id}")
async def doc_ban_le(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoá đơn thuốc của lượt bán lẻ (máy chủ tính) + lần thu + cờ quyền."""
    kq: dict[str, Any] = jsonable_encoder(
        await BanLeService(pool).doc(visit_id=str(visit_id), identity=identity)
    )
    return kq


@router.get("/pharmacy/inventory")
async def ton_kho(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tồn theo lô, kèm hạn dùng và cờ hết hạn."""
    return {"items": await PharmacyService(pool).ton_kho(identity=identity)}


@router.get("/pharmacy/cho-gan-lo")
async def cho_gan_lo(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thuốc đã giao mà chưa gán lô (giao không lô, 28/09/2026) + lô gán được."""
    return await PharmacyService(pool).cho_gan_lo(identity=identity)


class GanLoRequest(BaseModel):
    dong_id: UUID
    drug_batch_id: UUID


@router.post("/pharmacy/gan-lo")
async def gan_lo(
    body: GanLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gán một lần giao chưa gán lô vào lô thật — kho trừ lúc này."""
    return await PharmacyService(pool).gan_lo_da_giao(
        identity=identity,
        dong_id=str(body.dong_id),
        drug_batch_id=str(body.drug_batch_id),
    )


@router.get("/pharmacy/lich-su")
async def lich_su_giao(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dòng đã giao — kèm số kê / số khách mua / số đã giao."""
    return {
        "items": jsonable_encoder(
            await PharmacyService(pool).lich_su_giao(identity=identity)
        )
    }


@router.get("/pharmacy/cho-tu-van")
async def cho_tu_van(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dòng thuốc còn việc — màn Tư vấn dùng thuốc."""
    return {
        "items": jsonable_encoder(
            await PharmacyService(pool).cho_tu_van(identity=identity)
        )
    }


@router.get("/pharmacy/danh-muc")
async def danh_muc_thuoc(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh mục thuốc kho (kể cả thuốc đang tắt) + tổng tồn — màn Kho thuốc."""
    return {
        "items": jsonable_encoder(
            await PharmacyService(pool).danh_muc(identity=identity)
        )
    }


class ThuocRequest(BaseModel):
    # Không có mã = thêm thuốc mới.
    drug_catalog_id: UUID | None = None
    ten: str = Field(min_length=1, max_length=300)
    # Any: luật đọc số nằm ở service và trả câu tiếng Việt.
    gia: Any = None
    ma_hang: str | None = Field(default=None, max_length=100)
    don_vi_ban: str | None = Field(default=None, max_length=50)
    duong_dung: str | None = Field(default=None, max_length=100)
    cach_dung: str | None = Field(default=None, max_length=4000)
    luu_y: str | None = Field(default=None, max_length=4000)
    biet_duoc: str | None = Field(default=None, max_length=300)
    dang_dung: bool = True
    # 29/09: ngưỡng sắp hết hàng. Không gửi = giữ số cũ; gửi rỗng = bỏ canh.
    ton_toi_thieu: Any = None


@router.post("/pharmacy/danh-muc")
async def luu_thuoc(
    body: ThuocRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm / sửa một thuốc: tên, giá bán, đơn vị, hướng dẫn sử dụng, bật/tắt."""
    return await PharmacyService(pool).luu_thuoc(
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id) if body.drug_catalog_id else None,
        ten=body.ten,
        gia=body.gia,
        ma_hang=body.ma_hang,
        don_vi_ban=body.don_vi_ban,
        duong_dung=body.duong_dung,
        cach_dung=body.cach_dung,
        luu_y=body.luu_y,
        biet_duoc=body.biet_duoc,
        dang_dung=body.dang_dung,
        ton_toi_thieu=(
            body.ton_toi_thieu
            if "ton_toi_thieu" in body.model_fields_set
            else GIU_NGUYEN
        ),
    )


# ── Kho kiểu KiotViet (29/09/2026): thẻ kho · XNT · phiếu nhập · kiểm kho ──


@router.get("/pharmacy/the-kho/{drug_catalog_id}")
async def the_kho(
    drug_catalog_id: UUID,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thẻ kho một thuốc: mọi biến động, tồn trước → sau, người làm. Chỉ đọc."""
    kq: dict[str, Any] = jsonable_encoder(
        await kho_thuoc_service.the_kho(
            pool, identity=identity, drug_catalog_id=str(drug_catalog_id)
        )
    )
    return kq


@router.get("/pharmacy/xuat-nhap-ton")
async def xuat_nhap_ton(
    tu: str | None = None,
    den: str | None = None,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xuất – nhập – tồn theo khoảng ngày. Ngày rác → hôm nay (không 422/500)."""
    kq: dict[str, Any] = jsonable_encoder(
        await kho_thuoc_service.xuat_nhap_ton(pool, identity=identity, tu=tu, den=den)
    )
    return kq


@router.get("/pharmacy/phieu-kho")
async def danh_sach_phieu(
    loai: str = "NHAP",
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Phiếu nhập (`loai=NHAP`) hoặc phiếu kiểm kho (`loai=KIEM`) gần nhất."""
    return {
        "items": jsonable_encoder(
            await kho_thuoc_service.danh_sach_phieu(pool, identity=identity, loai=loai)
        )
    }


class DongPhieuNhap(BaseModel):
    drug_catalog_id: UUID
    batch_code: str = Field(min_length=1, max_length=100)
    # Chuỗi: luật đọc ngày ở service (rác → báo dòng nào thiếu hạn, không 422).
    expiry_date: str | None = Field(default=None, max_length=20)
    so_luong: Any = None
    unit: str | None = Field(default=None, max_length=50)
    gia_nhap: Any = None


class PhieuNhapRequest(BaseModel):
    nha_cung_cap: str | None = Field(default=None, max_length=300)
    so_hoa_don: str | None = Field(default=None, max_length=100)
    ngay_chung_tu: str | None = Field(default=None, max_length=20)
    ghi_chu: str | None = Field(default=None, max_length=1000)
    dong: list[DongPhieuNhap] = Field(min_length=1, max_length=200)


@router.post("/pharmacy/phieu-nhap", status_code=201)
async def phieu_nhap(
    body: PhieuNhapRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Phiếu nhập nhiều dòng — một giao dịch. Bắt buộc `Idempotency-Key`: gửi lại
    cùng khoá = cùng phiếu (UNIQUE ở Postgres), không nhập lần hai."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho_thuoc_service.tao_phieu_nhap(
                pool,
                identity=identity,
                khoa_gui=khoa,
                nha_cung_cap=body.nha_cung_cap,
                so_hoa_don=body.so_hoa_don,
                ngay_chung_tu=body.ngay_chung_tu,
                ghi_chu=body.ghi_chu,
                dong=[d.model_dump(mode="json") for d in body.dong],
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class DongKiemKho(BaseModel):
    drug_batch_id: UUID
    thuc_te: Any = None


class KiemKhoRequest(BaseModel):
    ghi_chu: str | None = Field(default=None, max_length=1000)
    dong: list[DongKiemKho] = Field(min_length=1, max_length=200)


@router.post("/pharmacy/kiem-kho", status_code=201)
async def kiem_kho(
    body: KiemKhoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Phiếu kiểm kho: máy chủ tính lệch, ghi điều chỉnh, lưu phiếu — một giao dịch."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho_thuoc_service.kiem_kho(
                pool,
                identity=identity,
                khoa_gui=khoa,
                ghi_chu=body.ghi_chu,
                dong=[d.model_dump(mode="json") for d in body.dong],
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


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
    # Bỏ trống = giao KHÔNG cần lô, gán lô sau (28/09/2026) — chỉ khi lần thu
    # tiền thuốc không gắn lô nào (máy chủ quyết, xem PharmacyService.cap_phat).
    drug_batch_id: UUID | None = None
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
                drug_batch_id=(str(body.drug_batch_id) if body.drug_batch_id else None),
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
