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
from fastapi import APIRouter, Depends, Header, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from clinicai.api.idempotency import (
    IdempotencyGuard,
    idempotency_guard,
    tra_khoa_neu_bi_tu_choi,
)
from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.can import can
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.phieu_kham.khung import doc_ngay
from clinicai.services import (
    ban_theo_don_service,
    ban_thuoc_service,
    kho_thuoc_service,
    kiem_ke_ca_service,
    lo_thuoc_service,
    ma_vach_service,
)
from clinicai.services.ban_le_service import QUYEN_MO, BanLeService
from clinicai.services.pharmacy_service import (
    GIU_NGUYEN,
    PharmacyService,
    tach_kho_quay_bat,
)

router = APIRouter()

# ĐỌC mở rộng hơn GHI. Thu ngân thuốc cần thấy đơn để thu tiền, Trưởng ca và
# Quản lý cần thấy tồn để biết sắp hết gì — nhưng chỉ người giữ khối "Nhà thuốc"
# mới được chạm vào kho. Hỏi QUYỀN, không hỏi vai (24/09/2026, migration
# 20260924000013): cấp khối trên màn Phân quyền là có hiệu lực ngay.
_DOC = cua_quyen("pharmacy.view", "pharmacy.dispense")
_GHI = cua_quyen("pharmacy.dispense")


class SoNgayCanhBaoRequest(BaseModel):
    so_ngay: int = Field(ge=0, le=365000)


@router.get("/pharmacy/so-ngay-canh-bao")
async def so_ngay_canh_bao(
    identity: StaffIdentity = Depends(_DOC), pool: asyncpg.Pool = Depends(get_db_pool)
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        return {
            "so_ngay_sap_het_han": await lo_thuoc_service.so_ngay_canh_bao(
                conn, identity.clinic_id
            ),
            "sua_canh_bao_duoc": await can(conn, identity, "config.clinic.manage"),
        }


@router.post("/pharmacy/so-ngay-canh-bao")
async def doi_canh_bao(
    body: SoNgayCanhBaoRequest,
    identity: StaffIdentity = Depends(cua_quyen("config.clinic.manage")),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await lo_thuoc_service.doi_canh_bao(
        pool, identity=identity, so_ngay=body.so_ngay
    )


class SuaLoRequest(BaseModel):
    drug_batch_id: UUID
    batch_code: str = Field(min_length=1, max_length=100)
    expiry_date: Any = None


@router.post("/pharmacy/sua-lo")
async def sua_lo(
    body: SuaLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await lo_thuoc_service.sua_lo(
        pool,
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        batch_code=body.batch_code,
        expiry_date=body.expiry_date,
    )


class HuyLoHetHanRequest(BaseModel):
    drug_batch_id: UUID
    ly_do: str = Field(min_length=1, max_length=1000)


@router.post("/pharmacy/huy-lo-het-han")
async def huy_lo_het_han(
    body: HuyLoHetHanRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    khoa: UUID = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await lo_thuoc_service.huy_lo(
        pool,
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        ly_do=body.ly_do,
        khoa_gui=str(khoa),
    )


class HoanHuyLoRequest(BaseModel):
    inventory_txn_id: UUID


@router.post("/pharmacy/hoan-huy-lo")
async def hoan_huy_lo(
    body: HoanHuyLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await lo_thuoc_service.hoan_huy_lo(
        pool, identity=identity, inventory_txn_id=str(body.inventory_txn_id)
    )


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


@router.get("/pharmacy/ban-le/lich-su-don")
async def ban_le_lich_su_don(
    clinic_patient_id: UUID,
    trang: str | None = Query(default=None, max_length=10),
    identity: StaffIdentity = Depends(_BAN_LE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Vừa chọn khách ở quầy (chưa mở lượt) → lịch sử đơn thuốc, mới → cũ, theo
    trang. Trang rác → trang đầu (không 422)."""
    kq: dict[str, Any] = jsonable_encoder(
        await BanLeService(pool).lich_su_don(
            clinic_patient_id=str(clinic_patient_id), trang=trang, identity=identity
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
    async with pool.acquire() as conn:
        tach = await tach_kho_quay_bat(conn, identity)
    return {
        "items": await PharmacyService(pool).ton_kho(identity=identity),
        "tach_kho_quay": tach,
    }


@router.get("/pharmacy/tra-ma")
async def tra_ma(
    ma: str = "",
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Một chuỗi quét (tem lô / mã vạch thuốc / mã vuông GS1 / mã hàng) → thuốc
    hoặc lô, kèm gợi ý lô FEFO. Chỉ đọc; mã lạ trả `loai: "la"`, không lỗi."""
    kq: dict[str, Any] = jsonable_encoder(
        await ma_vach_service.tra_ma(pool, identity=identity, ma=ma)
    )
    return kq


class GanMaVachRequest(BaseModel):
    drug_catalog_id: UUID
    ma: str = Field(min_length=1, max_length=256)
    nguon: str = "quet"


@router.post("/pharmacy/gan-ma-vach")
async def gan_ma_vach(
    body: GanMaVachRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gắn mã vạch cho thuốc (người có quyền kho). Mã đã thuộc thuốc khác → 409."""
    return await ma_vach_service.gan_ma(
        pool,
        identity=identity,
        drug_catalog_id=str(body.drug_catalog_id),
        ma=body.ma,
        nguon=body.nguon,
    )


class GoMaVachRequest(BaseModel):
    ma_vach_id: UUID


@router.post("/pharmacy/go-ma-vach")
async def go_ma_vach(
    body: GoMaVachRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ mã vạch gắn nhầm (hoàn tác của gắn mã) — ghi nhật ký."""
    return await ma_vach_service.go_ma(
        pool, identity=identity, ma_vach_id=str(body.ma_vach_id)
    )


@router.get("/pharmacy/tem-lo")
async def tem_lo(
    ids: str = "",
    phieu: str = "",
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dữ liệu in tem: lô theo danh sách `ids` (cách nhau dấu phẩy) hoặc theo
    phiếu nhập `phieu`. Id rác bị bỏ qua; tối đa 200 tem."""
    lo_ids: list[str] = []
    for x in ids.split(","):
        try:
            lo_ids.append(str(UUID(x.strip())))
        except ValueError:
            continue
    try:
        phieu_id: str | None = str(UUID(phieu.strip())) if phieu.strip() else None
    except ValueError:
        phieu_id = None
    kq: dict[str, Any] = jsonable_encoder(
        {
            "items": await ma_vach_service.du_lieu_tem(
                pool, identity=identity, lo_ids=lo_ids, phieu_kho_id=phieu_id
            )
        }
    )
    return kq


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


@router.get("/pharmacy/xuat-nhap-ton.xlsx")
async def xuat_nhap_ton_xlsx(
    tu: str | None = None,
    den: str | None = None,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Download stock records using the same clinic permission and date scope."""
    from clinicai.services.excel_export import XLSX_MEDIA_TYPE, xlsx_inventory

    report = await kho_thuoc_service.xuat_nhap_ton(
        pool, identity=identity, tu=tu, den=den
    )
    return Response(
        content=xlsx_inventory(report),
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": (
                f'attachment; filename="xuat-nhap-ton_'
                f'{report["tu"]}_{report["den"]}.xlsx"'
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


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
    # Nhập khác đơn vị bán: 1 <unit> = he_so đơn vị bán. Bỏ trống = dùng hệ số
    # đã nhớ; chưa nhớ thì máy chủ hỏi (xem `quy_doi_dong_nhap`).
    he_so: Any = None
    xac_nhan_he_so: bool = False


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


class DongChuyenKho(BaseModel):
    drug_batch_id: UUID
    so_luong: Any = None


class ChuyenKhoRequest(BaseModel):
    huong: str = Field(max_length=20)
    ly_do: str | None = Field(default=None, max_length=1000)
    dong: list[DongChuyenKho] = Field(min_length=1, max_length=200)


@router.post("/pharmacy/chuyen-kho", status_code=201)
async def chuyen_kho(
    body: ChuyenKhoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Phiếu chuyển KHO → QUẦY hoặc QUẦY → KHO — một giao dịch, hai dòng sổ đối
    ứng mỗi dòng. Bắt buộc `Idempotency-Key`. Người làm được thì hệ cho làm (luật
    open); ai/lúc/lý do nằm trên phiếu và hoàn tác được."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho_thuoc_service.chuyen_kho(
                pool,
                identity=identity,
                khoa_gui=khoa,
                huong=body.huong,
                ly_do=body.ly_do,
                dong=[d.model_dump(mode="json") for d in body.dong],
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class HoanTacChuyenRequest(BaseModel):
    phieu_id: UUID


@router.post("/pharmacy/hoan-tac-chuyen-kho", status_code=201)
async def hoan_tac_chuyen_kho(
    body: HoanTacChuyenRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Hoàn tác một phiếu chuyển bằng phiếu chuyển ngược (mỗi phiếu một lần)."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho_thuoc_service.hoan_tac_chuyen(
                pool,
                identity=identity,
                khoa_gui=khoa,
                phieu_id=str(body.phieu_id),
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class TachKhoQuayRequest(BaseModel):
    bat: bool


@router.get("/pharmacy/tach-kho-quay")
async def tach_kho_quay(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    async with pool.acquire() as conn:
        return {
            "tach_kho_quay": await tach_kho_quay_bat(conn, identity),
            "sua_duoc": await can(conn, identity, "config.clinic.manage"),
        }


@router.post("/pharmacy/tach-kho-quay")
async def dat_tach_kho_quay(
    body: TachKhoQuayRequest,
    identity: StaffIdentity = Depends(cua_quyen("config.clinic.manage")),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật / tắt tách kho-quầy của CƠ SỞ đang làm (mặc định tắt)."""
    return await kho_thuoc_service.dat_tach_kho_quay(
        pool, identity=identity, bat=body.bat
    )


# ── Kiểm kê đầu / cuối ca ở QUẦY (G6, 14/10/2026) ────────────────────────
# Đọc: ai xem được kho. Ghi: khối "Nhà thuốc" (lego, không gác theo vai); luật
# (ngày/ca/số rác → 422, chốt rồi không sửa, điều chỉnh có lý do + hoàn tác) ở
# `kiem_ke_ca_service`.


class MoKiemKeRequest(BaseModel):
    ngay: str | None = None
    ca: str | None = None
    loai: str | None = None
    ghi_chu: str | None = Field(default=None, max_length=500)


class DongDemRequest(BaseModel):
    drug_catalog_id: str
    don_vi: str
    # Chuỗi / số / null: rỗng = bỏ dòng; rác → 422 ở service (không ghi gì).
    dem: Any = None


class LuuDemRequest(BaseModel):
    dong: list[DongDemRequest] = Field(max_length=500)


class DieuChinhKiemKeRequest(BaseModel):
    ly_do: str | None = Field(default=None, max_length=1000)


@router.get("/pharmacy/kiem-ke-ca")
async def ds_kiem_ke_ca(
    ngay: str | None = None,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return {
        "items": jsonable_encoder(
            await kiem_ke_ca_service.danh_sach(pool, identity=identity, ngay=ngay)
        )
    }


@router.get("/pharmacy/kiem-ke-ca/nhac")
async def nhac_kiem_ke_ca(
    ngay: str | None = None,
    ca: str | None = None,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhắc (không chặn bán): ca chưa kiểm đầu ca / ca trước chưa kiểm cuối ca."""
    return await kiem_ke_ca_service.nhac_thieu_kiem(
        pool, identity=identity, ngay=ngay, ca=ca
    )


@router.post("/pharmacy/kiem-ke-ca", status_code=201)
async def mo_kiem_ke_ca(
    body: MoKiemKeRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.mo_phieu(
            pool,
            identity=identity,
            ngay=body.ngay,
            ca=body.ca,
            loai=body.loai,
            ghi_chu=body.ghi_chu,
        )
    )
    return kq


@router.get("/pharmacy/kiem-ke-ca/{phieu_id}")
async def doc_kiem_ke_ca(
    phieu_id: str,
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.doc_phieu(pool, identity=identity, phieu_id=phieu_id)
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/dem")
async def luu_dem_kiem_ke_ca(
    phieu_id: str,
    body: LuuDemRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.luu_dem(
            pool,
            identity=identity,
            phieu_id=phieu_id,
            dong=[d.model_dump() for d in body.dong],
        )
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/dung-so-cuoi-ca-truoc")
async def dung_so_cuoi_ca_truoc(
    phieu_id: str,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.dung_so_cuoi_ca_truoc(
            pool, identity=identity, phieu_id=phieu_id
        )
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/chot")
async def chot_kiem_ke_ca(
    phieu_id: str,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.chot(pool, identity=identity, phieu_id=phieu_id)
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/sua-so-dem")
async def sua_so_dem_kiem_ke_ca(
    phieu_id: str,
    body: DieuChinhKiemKeRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đính chính số đếm bằng phiên bản mới, không thay snapshot đã chốt."""
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.sua_so_dem(
            pool, identity=identity, phieu_id=phieu_id, ly_do=body.ly_do
        )
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/dieu-chinh")
async def dieu_chinh_kiem_ke_ca(
    phieu_id: str,
    body: DieuChinhKiemKeRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bước RIÊNG sau chốt: ghi ADJUST đưa tồn máy về số đếm (có lý do)."""
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.dieu_chinh_theo_kiem_ke(
            pool, identity=identity, phieu_id=phieu_id, ly_do=body.ly_do
        )
    )
    return kq


@router.post("/pharmacy/kiem-ke-ca/{phieu_id}/hoan-tac-dieu-chinh")
async def hoan_tac_dieu_chinh_kiem_ke_ca(
    phieu_id: str,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        await kiem_ke_ca_service.hoan_tac_dieu_chinh(
            pool, identity=identity, phieu_id=phieu_id
        )
    )
    return kq


class NhapLoRequest(BaseModel):
    drug_catalog_id: UUID
    so_luong: float = Field(gt=0, allow_inf_nan=False)
    # Số lô và đơn vị bắt buộc; hạn có thể bổ sung sau.
    batch_code: str = Field(min_length=1, max_length=100)
    expiry_date: date | None = None
    unit: str = Field(min_length=1, max_length=50)
    cost_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    ly_do: str | None = Field(default=None, max_length=500)
    # Chuỗi/số tuỳ ý: hệ số rác → câu tiếng Việt từ service, không 422 chung chung.
    he_so: Any = None
    xac_nhan_he_so: bool = False

    @field_validator("expiry_date", mode="before")
    @classmethod
    def doc_han_dung(cls, value: Any) -> date | None:
        return value if isinstance(value, date) else doc_ngay(value)


@router.post("/pharmacy/receive", status_code=201)
async def nhap_lo(
    body: NhapLoRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    khoa: UUID = Header(alias="Idempotency-Key"),
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
        idempotency_key=str(khoa),
        he_so=body.he_so,
        xac_nhan_he_so=body.xac_nhan_he_so,
    )


@router.get("/pharmacy/quy-doi")
async def xem_quy_doi_nhap(
    drug_catalog_id: UUID,
    unit: str = Query(default="", max_length=50),
    he_so: str | None = Query(default=None, max_length=20),
    so_luong: str | None = Query(default=None, max_length=20),
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xem trước một dòng nhập: có phải đổi về đơn vị bán không, hệ số nào (đã nhớ
    hoặc vừa gõ), kết quả "= N <đơn vị bán>", và có cần xác nhận hệ số lạ không."""
    kq: dict[str, Any] = jsonable_encoder(
        await kho_thuoc_service.xem_truoc_quy_doi(
            pool,
            identity=identity,
            drug_catalog_id=str(drug_catalog_id),
            unit=unit,
            he_so=he_so,
            so_luong=so_luong,
        )
    )
    return kq


class CapPhatRequest(BaseModel):
    prescription_id: UUID
    # Bỏ trống = máy TỰ CHỌN lô hết hạn sớm nhất và trừ kho ngay (27/10/2026);
    # kho chưa đủ lô thì phần thiếu vẫn giao, ghi chờ gán lô (28/09/2026). Chỉ khi
    # lần thu tiền thuốc không gắn lô nào (máy chủ quyết, xem PharmacyService.cap_phat).
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
    so_luong: float = Field(allow_inf_nan=False)
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/adjust", status_code=201)
async def dieu_chinh(
    body: DieuChinhRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    khoa: UUID = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Kiểm kê lệch."""
    return await PharmacyService(pool).dieu_chinh(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
        idempotency_key=str(khoa),
    )


class HuyRequest(BaseModel):
    drug_batch_id: UUID
    so_luong: float = Field(gt=0, allow_inf_nan=False)
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/pharmacy/discard", status_code=201)
async def huy(
    body: HuyRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    khoa: UUID = Header(alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Huỷ thuốc hỏng hoặc hết hạn. Ra khỏi kho nhưng không ra khỏi sổ."""
    return await PharmacyService(pool).huy(
        identity=identity,
        drug_batch_id=str(body.drug_batch_id),
        so_luong=body.so_luong,
        ly_do=body.ly_do,
        idempotency_key=str(khoa),
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


@router.get("/pharmacy/thuoc-tra-cho-kiem")
async def thuoc_tra_cho_kiem(
    identity: StaffIdentity = Depends(_DOC),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thuốc khách đã trả mà chưa quyết xử lý (nhập lại bán được / huỷ)."""
    dong = await PharmacyService(pool).thuoc_tra_cho_kiem(identity=identity)
    return {"dong": jsonable_encoder(dong)}


class XuLyThuocTraRequest(BaseModel):
    drug_return_id: UUID
    #: BAN_LAI | HUY — máy chủ báo câu tiếng Việt khi thiếu / sai.
    quyet_dinh: str | None = None
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/xu-ly-thuoc-tra")
async def xu_ly_thuoc_tra(
    body: XuLyThuocTraRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quyết định MỘT LẦN cho thuốc khách trả: nhập lại bán được, hoặc huỷ (ghi
    DISCARD cùng giao dịch). Gửi lại → "đã xử lý rồi" (không cần Idempotency-Key)."""
    kq: dict[str, Any] = jsonable_encoder(
        await PharmacyService(pool).xu_ly_thuoc_tra(
            identity=identity,
            drug_return_id=str(body.drug_return_id),
            quyet_dinh=body.quyet_dinh,
            ly_do=body.ly_do,
        )
    )
    return kq


class KhachTraRequest(BaseModel):
    dispense_txn_id: UUID
    so_luong: float = Field(gt=0)
    ly_do: str
    #: G4d · R3 (Tuyền chốt E): HOAN | DOI | GIU_LAI — bắt buộc, máy chủ báo câu
    #: tiếng Việt khi thiếu. Hình thức hoàn bỏ trống = theo lần thu gốc.
    ket_cuc_tien: str | None = None
    hinh_thuc: str | None = None
    ly_do_tien: str | None = Field(default=None, max_length=500)


@router.post("/pharmacy/khach-tra")
async def khach_tra_thuoc(
    body: KhachTraRequest,
    identity: StaffIdentity = Depends(_GHI),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Ghi nhận thuốc khách trả lại quầy (CP5) — thuốc chưa quyết xử lý (HOLD
    J1/J2); TIỀN phần trả bắt chọn hoàn / đổi / giữ lại (G4d · R3).

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
                ket_cuc_tien=body.ket_cuc_tien,
                hinh_thuc=body.hinh_thuc,
                ly_do_tien=body.ly_do_tien,
            )
        )
        await idem.save(pool, kq, status_code=200)
    return kq
