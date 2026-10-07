"""Luồng khám lát 1 — màn `/luot-kham` của sáu vai.

Router mỏng: đọc thân, gác vai, chuyển cho ``LuotKhamService``. Mọi luật nằm ở
service và ``luot_kham_rules``. Service tự gác vai lần nữa — gọi thẳng service
từ chỗ khác cũng không vượt quyền được.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    StaffIdentity,
    get_current_identity,
)
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.nhan_tai_phong import NhanTaiPhongService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import KHONG_DOI, ServiceRoutingService
from clinicai.services.service_selection_service import ServiceSelectionService
from clinicai.services.sinh_hieu_service import SinhHieuService

router = APIRouter()
logger = structlog.get_logger()

#: LỐI CŨ ĐÃ TẮT (24/09/2026, đợt bóc lõi `luot_kham` bước 2). Không màn nào
#: còn gọi các cửa dưới — đường mới đã thay (xem `_tat_loi_cu`). Cũ thì OFF,
#: KHÔNG xoá (luật Tuyền): bật lại = đặt True. Bài kiểm luồng cũ bật cờ này.
LOI_CU_MO = False


def _tat_loi_cu(identity: StaffIdentity, endpoint: str, thay: str) -> None:
    """Trả 410 cho cửa cũ và ghi log người gọi — để biết còn ai dùng."""
    if LOI_CU_MO:
        return
    logger.warning(
        "endpoint_retired_called",
        endpoint=endpoint,
        staff_id=identity.staff_id,
        role=identity.role.value,
    )
    raise HTTPException(
        status_code=410,
        detail={"error": "ENDPOINT_RETIRED", "message": f"Lối cũ đã tắt — {thay}"},
    )


# BẢNG LƯỢT KHÁM · HÀNG CHỜ · PHÒNG HÔM NAY hỏi LEGO (đợt 3, 27/09/2026): cửa
# router chỉ còn "đã đăng nhập"; hàm dịch vụ tự hỏi quyền của lego dùng bảng ấy
# (`permissions/doc_bang.py`). Trước đây là danh sách VAI — tài khoản chỉ bật
# lego Khám tư vấn bị 403 ở hàng chờ tư vấn của chính mình.
_BANG_GUARD = get_current_identity
# ĐƯỜNG KHÁM CHÍNH HỎI QUYỀN (CORE-B3, 23/09/2026): check-in, sinh hiệu, khám,
# ghi chú, duyệt kết quả — cửa ở router chỉ còn "đã đăng nhập"; quyền thật
# (`capability_grant`) do hàm dịch vụ hỏi trong chính giao dịch. Để lại cửa
# vai ở đây là còn hai hệ quyền: người được cấp quyền vẫn ăn 403 ở cửa ngoài.
# Công tắc mở quyền tạm thời KHÔNG nới các việc này nữa — quản lý cấp quyền.
_CHECKIN_GUARD = get_current_identity
_VITALS_GUARD = get_current_identity
# "CHỈ DÙNG LEGO" (Tuyền 27/09/2026, đợt 3): điều phối hỏi `dispatch.manage`,
# duyệt chỉ định + nháp chỉ định hỏi `clinical.order.place` (28/09: thư ký /
# điều dưỡng cùng phòng như bác sĩ) — trong hàm dịch vụ. Không còn cửa VAI.
_DISPATCH_GUARD = get_current_identity
_DOCTOR_GUARD = get_current_identity
_TKYK_GUARD = get_current_identity
# (Cũ, OFF 410) hai lệnh thực hiện dịch vụ đời trước — đường mới
# `/orders/{id}/execution/*` hỏi capability. Giữ cửa vai của lối cũ khi bật lại.
# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN làm dịch vụ (kể cả theo phòng nhờ lịch).
_PERFORMER_GUARD = cua_quyen(
    "service.execute.start", "service.execute.complete", moi_phong=True
)

_NOTE_GUARD = get_current_identity
#: Bắt đầu / kết thúc phiên khám: quyền Khám của lego Bàn khám (hàm dịch vụ).
_CONSULT_GUARD = get_current_identity


class CheckInBody(BaseModel):
    appointment_id: UUID
    #: TUỲ CHỌN: lễ tân xác minh khách bằng cách nào (CACH_XAC_MINH).
    xac_minh_cach: str | None = None


class VitalsBody(BaseModel):
    # Any, không phải số: luật đọc đầu vào người dùng nằm ở parse_vitals và trả
    # CÂU tiếng Việt. Để Pydantic ép kiểu thì người dùng nhận một mảng lỗi kỹ thuật.
    systolic: Any = None
    diastolic: Any = None
    pulse: Any = None
    temperature: Any = None
    weight_kg: Any = None
    height_cm: Any = None
    # Bốn chỉ số thêm 16/09/2026. Thiếu chúng ở ĐÂY là mất dữ liệu trong im
    # lặng: parse_vitals đọc được, cột trong bảng có, nhưng Pydantic cắt trường
    # lạ khỏi thân trước khi service kịp nhìn thấy — không ai báo lỗi.
    respiratory_rate: Any = None
    spo2: Any = None
    bmi: Any = None
    pain_score: Any = None
    # Điều dưỡng tick "Bỏ qua bác sĩ tư vấn" (Tuyền 25/09/2026) → khách vào thẳng
    # hàng bác sĩ chính. Không phải chỉ số — tách khỏi `raw` trước parse_vitals.
    bo_qua_tu_van: bool = False


class NoteBody(BaseModel):
    body: str = Field(max_length=20000)


class DraftBody(BaseModel):
    service_codes: list[str] = Field(min_length=1, max_length=30)


class AuthorizeBody(BaseModel):
    service_codes: list[str] = Field(default_factory=list, max_length=30)
    draft_order_ids: list[UUID] = Field(default_factory=list, max_length=30)
    expected_versions: dict[UUID, Annotated[int, Field(strict=True, ge=1)]] = Field(
        default_factory=dict, max_length=30
    )


class RequirementBody(BaseModel):
    order_id: UUID
    need: Literal["PERFORMED", "VALID_RESULT", "FOLLOW_UP"]
    # Chỉ với FOLLOW_UP: ai theo dõi, hạn (YYYY-MM-DD), vì sao. Bỏ trống thì
    # mặc định bác sĩ của phiên và hạn theo luật CSKH CHO_KQ_XN.
    owner_id: UUID | None = None
    han: str | None = Field(default=None, max_length=10)
    ly_do: str | None = Field(default=None, max_length=2000)


class KhamXongBody(BaseModel):
    #: {mã chỉ định: PERFORMED | VALID_RESULT | FOLLOW_UP} — đổi mức mặc định.
    ke_hoach: dict[UUID, Literal["PERFORMED", "VALID_RESULT", "FOLLOW_UP"]] = Field(
        default_factory=dict, max_length=30
    )


class QuyetYeuCauBody(BaseModel):
    hanh_dong: Literal["WAIVE", "FOLLOW_UP"]
    ly_do: str = Field(min_length=1, max_length=2000)
    owner_id: UUID | None = None
    han: str | None = Field(default=None, max_length=10)


class CompleteConsultationBody(BaseModel):
    outcome: Literal["NO_SERVICES", "SERVICES", "DONE", "MORE_SERVICES"]
    requirements: list[RequirementBody] = Field(default_factory=list, max_length=30)


class DispatchBody(BaseModel):
    room_id: UUID
    expected_version: int | None = None


class CompleteServiceBody(BaseModel):
    performed: bool
    reason: str | None = Field(default=None, max_length=2000)
    result_note: str | None = Field(default=None, max_length=20000)


@router.get("/luot-kham/bang")
async def bang(
    ngay: str | None = Query(default=None, max_length=32),
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng làm việc hôm nay, đủ cho mọi vai; màn hình lọc theo vai.

    `ngay=YYYY-MM-DD` (29/09/2026): xem lại + sửa lượt của một ngày cũ; rác =
    hôm nay."""
    return await BangLuotKham(pool).bang(identity=identity, ngay=ngay)


@router.post("/luot-kham/check-in")
async def check_in(
    body: CheckInBody,
    identity: StaffIdentity = Depends(_CHECKIN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LuotKhamService(pool).check_in(
        appointment_id=str(body.appointment_id),
        identity=identity,
        xac_minh_cach=body.xac_minh_cach,
    )


@router.post("/luot-kham/visits/{visit_id}/vitals")
async def record_vitals(
    visit_id: UUID,
    body: VitalsBody,
    identity: StaffIdentity = Depends(_VITALS_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await SinhHieuService(pool).record_vitals(
        visit_id=str(visit_id),
        raw=body.model_dump(exclude={"bo_qua_tu_van"}),
        identity=identity,
        idempotency_key=idempotency_key,
        bo_qua_tu_van=body.bo_qua_tu_van,
    )


class BoQuaTuVanBody(BaseModel):
    bo_qua: bool


@router.post("/luot-kham/visits/{visit_id}/bo-qua-tu-van")
async def doi_duong_tu_van(
    visit_id: UUID,
    body: BoQuaTuVanBody,
    identity: StaffIdentity = Depends(_VITALS_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô tick "Bỏ qua bác sĩ tư vấn" (màn đo sinh hiệu) — áp ngay vào vị trí khách:
    tick → hàng bác sĩ chính, bỏ tick → về hàng tư vấn (Tuyền 25/09/2026)."""
    return await LuotKhamService(pool).doi_duong_tu_van(
        visit_id=str(visit_id), bo_qua=body.bo_qua, identity=identity
    )


class LamTruocThuSauBody(BaseModel):
    bat: bool
    #: Quầy thu gửi đúng lựa chọn đang tick trên màn (tuỳ chọn) — không có thì
    #: mọi chỉ định chờ quyết tính là khách làm.
    chon: dict[str, Any] | None = None


@router.get("/luot-kham/visits/{visit_id}/lam-truoc-thu-sau")
async def doc_lam_truoc_thu_sau(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tick "Làm trước – thu sau" của lượt + cờ bấm được (máy chủ quyết)."""
    from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService

    return await LamTruocThuSauService(pool).doc(
        visit_id=str(visit_id), identity=identity
    )


@router.post("/luot-kham/visits/{visit_id}/lam-truoc-thu-sau")
async def dat_lam_truoc_thu_sau(
    visit_id: UUID,
    body: LamTruocThuSauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật / bỏ tick "Làm trước – thu sau" (30/09/2026 tối). Quyền: lego Bàn khám
    hoặc thu tiền dịch vụ — service hỏi trong chính giao dịch."""
    from clinicai.services.lam_truoc_thu_sau import LamTruocThuSauService

    return await LamTruocThuSauService(pool).dat(
        visit_id=str(visit_id), bat=body.bat, chon=body.chon, identity=identity
    )


@router.post("/luot-kham/visits/{visit_id}/vitals/start")
async def bat_dau_do_sinh_hieu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_VITALS_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """[Bắt đầu] đo sinh hiệu — thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026).

    Bấm lại chính mình thì `already=true`, không sự kiện thứ hai. Người khác
    bấm sau thì bị từ chối kèm tên và giờ người đã bắt đầu.
    """
    return await SinhHieuService(pool).bat_dau_do_sinh_hieu(
        visit_id=str(visit_id), identity=identity
    )


@router.post("/luot-kham/visits/{visit_id}/goi-do")
async def goi_do_sinh_hieu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_VITALS_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Điều dưỡng gọi khách vào đo sinh hiệu."""
    _tat_loi_cu(
        identity,
        "POST /luot-kham/visits/{id}/goi-do",
        "màn Đo sinh hiệu dùng nút [Bắt đầu đo].",
    )
    return await SinhHieuService(pool).goi_do_sinh_hieu(
        visit_id=str(visit_id), identity=identity
    )


@router.get("/luot-kham/phong-hom-nay")
async def phong_hom_nay(
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Phòng người gọi đứng hôm nay (theo lịch) + danh sách mọi phòng."""
    return await BangLuotKham(pool).phong_hom_nay(identity=identity)


@router.get("/luot-kham/hang-cho")
async def hang_cho(
    phong: UUID | None = None,
    tu_van: bool = False,
    ngay: str | None = Query(default=None, max_length=32),
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hàng chờ một phòng: đang chờ · đang trong phòng · đã xong hôm nay.

    `tu_van=true`: hàng CHUNG của bác sĩ tư vấn (dây H1, 24/09/2026).
    `ngay=YYYY-MM-DD` (29/09/2026): xem lại một ngày cũ; rác = hôm nay."""
    return await BangLuotKham(pool).hang_cho(
        identity=identity,
        room_id=str(phong) if phong else None,
        tu_van=tu_van,
        ngay=ngay,
    )


class DuyetKetQuaBody(BaseModel):
    danh_gia: str | None = Field(default=None, max_length=5000)


#: Duyệt kết quả là quyết định chuyên môn — không mở theo công tắc.
_REVIEW_GUARD = get_current_identity


@router.get("/luot-kham/ket-qua-cho-duyet")
async def ket_qua_cho_duyet(
    identity: StaffIdentity = Depends(_REVIEW_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chỉ định đã có kết quả, chờ bác sĩ đánh giá và cho phép gửi."""
    return await BangLuotKham(pool).ket_qua_cho_duyet(identity=identity)


@router.post("/luot-kham/orders/{order_id}/duyet-ket-qua")
async def duyet_ket_qua(
    order_id: UUID,
    body: DuyetKetQuaBody,
    identity: StaffIdentity = Depends(_REVIEW_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LuotKhamService(pool).duyet_ket_qua(
        order_id=str(order_id), danh_gia=body.danh_gia, identity=identity
    )


@router.post("/luot-kham/hang-cho/{queue_entry_id}/goi")
async def goi_khach(
    queue_entry_id: UUID,
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gọi khách vào phòng. Ai được gọi là do bước của chỗ chờ quyết."""
    _tat_loi_cu(
        identity,
        "POST /luot-kham/hang-cho/{id}/goi",
        "bấm [Bắt đầu khám] / [Bắt đầu] ở phòng.",
    )
    return await LuotKhamService(pool).goi_khach(
        queue_entry_id=str(queue_entry_id), identity=identity
    )


@router.post("/luot-kham/consultations/{consultation_id}/kham-xong")
async def kham_xong(
    consultation_id: UUID,
    body: KhamXongBody | None = None,
    identity: StaffIdentity = Depends(_CONSULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Nút "Đã khám xong": máy chủ tự chọn kết quả phiên theo chỉ định còn lại."""
    return await LuotKhamService(pool).kham_xong(
        consultation_id=str(consultation_id),
        identity=identity,
        idempotency_key=idempotency_key,
        ke_hoach={str(k): v for k, v in (body.ke_hoach if body else {}).items()},
    )


@router.get("/luot-kham/chi-dinh-hom-nay")
async def chi_dinh_hom_nay(
    identity: StaffIdentity = Depends(_DISPATCH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chỉ định hôm nay chia bốn nhóm điều phối (trưởng ca)."""
    return await BangLuotKham(pool).chi_dinh_hom_nay(identity=identity)


@router.get("/luot-kham/cho-quyet")
async def cho_quyet(
    identity: StaffIdentity = Depends(_CONSULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Kết quả chưa về / dịch vụ không làm được đang chờ bác sĩ quyết."""
    return await LuotKhamService(pool).cho_quyet(identity=identity)


@router.post("/luot-kham/yeu-cau/{requirement_id}/quyet")
async def quyet_yeu_cau(
    requirement_id: UUID,
    body: QuyetYeuCauBody,
    # Quyền "Hoàn tất khám" do lệnh hỏi trong chính nó (24/09/2026).
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Bác sĩ miễn hoặc chuyển theo dõi một yêu cầu của vòng đọc kết quả."""
    return await LuotKhamService(pool).quyet_yeu_cau(
        requirement_id=str(requirement_id),
        hanh_dong=body.hanh_dong,
        ly_do=body.ly_do,
        owner_id=str(body.owner_id) if body.owner_id else None,
        han=body.han,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/consultations/{consultation_id}/start")
async def start_consultation(
    consultation_id: UUID,
    identity: StaffIdentity = Depends(_CONSULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LuotKhamService(pool).start_consultation(
        consultation_id=str(consultation_id), identity=identity
    )


@router.post("/luot-kham/consultations/{consultation_id}/xong-tu-van")
async def xong_tu_van(
    consultation_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """`CompleteIntake` — tư vấn xong, chuyển bác sĩ chính (dây H3)."""
    return await LuotKhamService(pool).xong_tu_van(
        consultation_id=str(consultation_id), identity=identity
    )


class NoiDungTuVanBody(BaseModel):
    noi_dung: str = Field(default="", max_length=20000)


class VatTuThemBody(BaseModel):
    service_price_id: UUID
    so_luong: int = Field(default=1, ge=1, le=99)
    #: Mặt hàng đã có dòng chờ thu: True (nút chọn nhanh) = cộng thêm số lượng.
    cong_don: bool = True
    #: Hàng cần quản lý duyệt (Mirena): quản lý đã duyệt + lý do.
    duyet_boi: UUID | None = None
    ly_do_duyet: str | None = Field(default=None, max_length=500)


class VatTuSoLuongBody(BaseModel):
    so_luong: int = Field(ge=1, le=99)


@router.get("/luot-kham/visits/{visit_id}/vat-tu")
async def doc_vat_tu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh mục vật tư + dòng đã thêm của lượt — quầy Thu tiền dịch vụ (C13)."""
    from clinicai.services.vat_tu_service import VatTuService

    return await VatTuService(pool).doc(visit_id=str(visit_id), identity=identity)


@router.post("/luot-kham/visits/{visit_id}/vat-tu")
async def them_vat_tu(
    visit_id: UUID,
    body: VatTuThemBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm một vật tư vào hoá đơn dịch vụ của lượt (tiền DỊCH VỤ)."""
    from clinicai.services.vat_tu_service import VatTuService

    return await VatTuService(pool).them(
        visit_id=str(visit_id),
        service_price_id=str(body.service_price_id),
        so_luong=body.so_luong,
        cong_don=body.cong_don,
        duyet_boi=str(body.duyet_boi) if body.duyet_boi else None,
        ly_do_duyet=body.ly_do_duyet,
        identity=identity,
    )


@router.post("/luot-kham/vat-tu/{dong_id}")
async def dat_so_luong_vat_tu(
    dong_id: UUID,
    body: VatTuSoLuongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi số lượng một dòng vật tư chưa thu."""
    from clinicai.services.vat_tu_service import VatTuService

    return await VatTuService(pool).dat_so_luong(
        dong_id=str(dong_id), so_luong=body.so_luong, identity=identity
    )


@router.post("/luot-kham/vat-tu/{dong_id}/bo")
async def bo_vat_tu(
    dong_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bỏ một dòng vật tư chưa thu khỏi hoá đơn."""
    from clinicai.services.vat_tu_service import VatTuService

    return await VatTuService(pool).bo(dong_id=str(dong_id), identity=identity)


class PhiKhamBody(BaseModel):
    #: Dạng cũ: đặt cả tập. Có `ids` thì `them` / `bo` bị bỏ qua.
    ids: list[UUID] | None = Field(default=None, max_length=40)
    #: Dạng đổi từng dịch vụ (C18): tính trên tập hiện có ở máy chủ.
    them: list[UUID] = Field(default_factory=list, max_length=40)
    bo: list[UUID] = Field(default_factory=list, max_length=40)


@router.get("/luot-kham/visits/{visit_id}/phi-kham")
async def doc_phi_kham(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dịch vụ khám chọn được (mã KiotViet) + đã chọn của lượt (28/09/2026)."""
    from clinicai.services.phi_kham_service import PhiKhamService

    return await PhiKhamService(pool).doc(visit_id=str(visit_id), identity=identity)


@router.post("/luot-kham/visits/{visit_id}/phi-kham")
async def chon_phi_kham(
    visit_id: UUID,
    body: PhiKhamBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tick dịch vụ khám → tiền khám tính theo đúng các dịch vụ đã chọn."""
    from clinicai.services.phi_kham_service import PhiKhamService

    return await PhiKhamService(pool).chon(
        visit_id=str(visit_id),
        ids=None if body.ids is None else [str(i) for i in body.ids],
        them_vao=[str(i) for i in body.them],
        bo_di=[str(i) for i in body.bo],
        identity=identity,
    )


@router.post("/luot-kham/consultations/{consultation_id}/noi-dung-tu-van")
async def luu_noi_dung_tu_van(
    consultation_id: UUID,
    body: NoiDungTuVanBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ô chữ tự do của bác sĩ tư vấn (24/09/2026) — sang mục "mang sang"."""
    return await LuotKhamService(pool).luu_noi_dung_tu_van(
        consultation_id=str(consultation_id),
        noi_dung=body.noi_dung,
        identity=identity,
    )


@router.post("/luot-kham/consultations/{consultation_id}/notes")
async def save_note(
    consultation_id: UUID,
    body: NoteBody,
    identity: StaffIdentity = Depends(_NOTE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    _tat_loi_cu(
        identity,
        "POST /luot-kham/consultations/{id}/notes",
        "ghi vào phiếu khám (tự lưu).",
    )
    return await LuotKhamService(pool).save_note(
        consultation_id=str(consultation_id), body=body.body, identity=identity
    )


#: Lát CD-01: bác sĩ VÀ thư ký y khoa ngang quyền chỉ định (Tuyền, tin #149).
#: Cửa theo QUYỀN "Chỉ định dịch vụ" (24/09/2026): trước đây cửa theo vai chặn
#: người được cấp quyền mà khác vai (điều dưỡng, quản lý ăn 403 ở cửa ngoài
#: trong khi lệnh bên trong cho phép). Lệnh vẫn tự kiểm lại.
_CHI_DINH_GUARD = cua_quyen("clinical.order.place")


class ChiDinhBody(BaseModel):
    service_codes: list[str] = Field(min_length=1, max_length=30)
    #: Dịch vụ bác sĩ tick "Bắt buộc" (25/09/2026) — quầy thu không bỏ được.
    bat_buoc_codes: list[str] = Field(default_factory=list, max_length=30)
    #: Nút "Chỉ định thêm (lần N)" (06/10/2026): mở lần mới. Mặc định vào lần
    #: hiện tại. `lan_dang_thay` = lần hiện tại màn đang thấy.
    lan_moi: bool = False
    lan_dang_thay: int | None = None


class BatBuocBody(BaseModel):
    bat_buoc: bool


@router.post("/luot-kham/consultations/{consultation_id}/service-orders")
async def dat_chi_dinh(
    consultation_id: UUID,
    body: ChiDinhBody,
    identity: StaffIdentity = Depends(_CHI_DINH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """`PlaceServiceOrders` — xem `docs/slices/CD-01-bac-si-chi-dinh-dich-vu.md`."""
    return await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=str(consultation_id),
        service_codes=body.service_codes,
        identity=identity,
        idempotency_key=idempotency_key,
        bat_buoc_codes=body.bat_buoc_codes,
        lan_moi=body.lan_moi,
        lan_dang_thay=body.lan_dang_thay,
    )


@router.post("/luot-kham/orders/{order_id}/bat-buoc")
async def doi_bat_buoc(
    order_id: UUID,
    body: BatBuocBody,
    identity: StaffIdentity = Depends(_CHI_DINH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bật / tắt "Bắt buộc" của một chỉ định (chưa thu tiền) — Tuyền 25/09/2026."""
    return await ChiDinhService(pool).doi_bat_buoc(
        order_id=str(order_id), bat_buoc=body.bat_buoc, identity=identity
    )


@router.post("/luot-kham/consultations/{consultation_id}/draft-orders")
async def propose_orders(
    consultation_id: UUID,
    body: DraftBody,
    identity: StaffIdentity = Depends(_TKYK_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _tat_loi_cu(
        identity,
        "POST /luot-kham/consultations/{id}/draft-orders",
        "chỉ định trong phiếu khám (một lệnh, không nháp).",
    )
    return await LuotKhamService(pool).propose_orders(
        consultation_id=str(consultation_id),
        service_codes=body.service_codes,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/consultations/{consultation_id}/authorize-orders")
async def authorize_orders(
    consultation_id: UUID,
    body: AuthorizeBody,
    identity: StaffIdentity = Depends(_DOCTOR_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await LuotKhamService(pool).authorize_orders(
        consultation_id=str(consultation_id),
        service_codes=body.service_codes,
        draft_order_ids=[str(d) for d in body.draft_order_ids],
        expected_versions={str(k): v for k, v in body.expected_versions.items()},
        identity=identity,
        idempotency_key=idempotency_key,
    )


#: Cửa ngoài của ConfirmServiceSelection và hai lệnh điều phối: từ 23/09/2026
#: quyền thật là CAPABILITY, kiểm trong service và trong chính giao dịch của
#: lệnh. Router chỉ còn hỏi "đã đăng nhập chưa" — giữ thêm một danh sách vai ở
#: đây là giữ bản luật thứ hai, và hai bản luật thì sẽ có ngày nói ngược nhau.
_SELECTION_GUARD = get_current_identity


class ServiceSelectionBody(BaseModel):
    # Any: kiểm UUID, trùng lặp và tập con nằm ở service để trả mã lỗi ổn định
    # của contract thay vì mảng lỗi Pydantic.
    order_ids_seen: list[Any]
    selected_order_ids: list[Any]
    expected_selection_revision: Any


@router.post("/luot-kham/visits/{visit_id}/service-selection/confirm")
async def confirm_service_selection(
    visit_id: UUID,
    body: ServiceSelectionBody,
    identity: StaffIdentity = Depends(_SELECTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceSelectionService(pool).confirm(
        visit_id=str(visit_id),
        order_ids_seen=body.order_ids_seen,
        selected_order_ids=body.selected_order_ids,
        expected_selection_revision=body.expected_selection_revision,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/consultations/{consultation_id}/complete")
async def complete_consultation(
    consultation_id: UUID,
    body: CompleteConsultationBody,
    identity: StaffIdentity = Depends(_CONSULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    _tat_loi_cu(
        identity,
        "POST /luot-kham/consultations/{id}/complete",
        "bấm [Hoàn tất] (kham-xong).",
    )
    return await LuotKhamService(pool).complete_consultation(
        consultation_id=str(consultation_id),
        outcome=body.outcome,
        requirements=[
            {
                "order_id": str(r.order_id),
                "need": r.need,
                "owner_id": str(r.owner_id) if r.owner_id else None,
                "han": r.han,
                "ly_do": r.ly_do,
            }
            for r in body.requirements
        ],
        identity=identity,
        idempotency_key=idempotency_key,
    )


class AssignRoomBody(BaseModel):
    # Any: kiểm UUID / revision / mã lý do nằm ở service để trả mã lỗi ổn định.
    room_id: Any
    expected_routing_revision: Any
    reason_code: Any
    recommendation_ref: str | None = Field(default=None, max_length=300)
    #: Màn gọi lệnh: quay_thu · truong_ca · khac (mặc định). Trưởng ca đè quầy thu.
    nguon: str | None = Field(default=None, max_length=20)
    #: Bác sĩ trong phòng nhiều bác sĩ (30/09/2026). KHÔNG gửi = giữ lựa chọn
    #: cũ; null / "" = bỏ chọn; mã = bác sĩ đang trực làn của phòng hôm nay.
    bac_si_lam_id: Any = None


def _bac_si_gui(body: BaseModel) -> Any:
    """Trường `bac_si_lam_id` có trong thân lệnh không — không gửi ≠ gửi null."""
    return (
        getattr(body, "bac_si_lam_id", None)
        if "bac_si_lam_id" in body.model_fields_set
        else KHONG_DOI
    )


class InvalidateRoutingBody(BaseModel):
    expected_routing_revision: Any
    reason_code: Any


# Lifecycle v1 Slice 4 — Routing chính thức. Cửa ngoài giữ đúng cửa điều phối
# TỪ 23/09/2026: cửa thật là CAPABILITY trong ServiceRoutingService, kiểm trong
# chính giao dịch của lệnh. Router không giữ danh sách vai nữa — hai bản luật thì
# sẽ có ngày nói ngược nhau.
@router.post("/luot-kham/orders/{order_id}/routing/assign")
async def assign_service_room(
    order_id: UUID,
    body: AssignRoomBody,
    # QUYỀN, KHÔNG VAI (23/09/2026): trước đây chỉ Trưởng ca/Quản lý qua được
    # cửa này dù lễ tân, điều dưỡng, thư ký, bác sĩ đều có khối Điều phối. Cửa
    # thật là `service.routing.assign` trong ServiceRoutingService.
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceRoutingService(pool).assign(
        order_id=str(order_id),
        room_id=body.room_id,
        expected_routing_revision=body.expected_routing_revision,
        reason_code=body.reason_code,
        recommendation_ref=body.recommendation_ref,
        identity=identity,
        idempotency_key=idempotency_key,
        nguon=body.nguon,
        bac_si_lam_id=_bac_si_gui(body),
    )


class PhongDuKienBody(BaseModel):
    #: Rỗng = bỏ chọn, để hệ thống tự chọn phòng vắng nhất sau khi thu tiền.
    room_id: UUID | None = None
    #: quay_thu (mặc định) · truong_ca (29/09/2026: trưởng ca đặt trước thu tiền).
    nguon: str | None = Field(default=None, max_length=20)
    #: Như lệnh xếp phòng: không gửi = giữ; null = bỏ chọn; mã = bác sĩ trực.
    bac_si_lam_id: Any = None


class ChuyenPhongDangLamBody(BaseModel):
    # Any: kiểm UUID / revision / lý do nằm ở service để trả mã lỗi ổn định.
    room_id: Any
    expected_routing_revision: Any
    #: Bắt buộc — hiện ở lịch sử lượt ("Trưởng ca chuyển phòng A → B: …").
    ly_do: Any = None


@router.post("/luot-kham/orders/{order_id}/routing/phong-du-kien")
async def plan_service_room(
    order_id: UUID,
    body: PhongDuKienBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quầy chọn phòng khách sẽ làm, trước khi thu tiền (Tuyền 24/09/2026)."""
    return await ServiceRoutingService(pool).dat_phong_du_kien(
        order_id=str(order_id),
        room_id=str(body.room_id) if body.room_id else None,
        identity=identity,
        nguon=body.nguon,
        bac_si_lam_id=_bac_si_gui(body),
    )


@router.post("/luot-kham/orders/{order_id}/routing/chuyen-phong-dang-lam")
async def transfer_in_progress_service(
    order_id: UUID,
    body: ChuyenPhongDangLamBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Trưởng ca chuyển dịch vụ ĐANG LÀM sang phòng khác (Tuyền 29/09/2026).
    Cửa thật là `dispatch.manage` trong ServiceRoutingService."""
    return await ServiceRoutingService(pool).chuyen_phong_dang_lam(
        order_id=str(order_id),
        room_id=body.room_id,
        expected_routing_revision=body.expected_routing_revision,
        ly_do=body.ly_do,
        identity=identity,
        idempotency_key=idempotency_key,
    )


class NhanTaiPhongBody(BaseModel):
    # Any: kiểm UUID ở service để trả mã lỗi ổn định.
    room_id: Any = None
    #: Nhận chéo: khách đang ở phòng khác — bấm xác nhận (không bắt lý do).
    xac_nhan: bool = False
    #: Phòng nhiều bác sĩ: như lệnh xếp phòng (không gửi = giữ / tự gán).
    bac_si_lam_id: Any = None
    #: Nút Nhả: phòng hướng dẫn mới (tuỳ chọn).
    huong_dan_room_id: Any = None


# Nhận khách tại phòng (dây `nhan_tai_phong`, 07/10/2026) — id là LƯỢT KHÁM.
# Cửa thật (quyền điều phối, khoá lượt, dây) ở NhanTaiPhongService.
@router.post("/luot-kham/visits/{visit_id}/nhan-vao-phong")
async def receive_at_room(
    visit_id: UUID,
    body: NhanTaiPhongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await NhanTaiPhongService(pool).nhan(
        visit_id=str(visit_id),
        room_id=body.room_id,
        identity=identity,
        xac_nhan=body.xac_nhan,
        bac_si_lam_id=_bac_si_gui(body),
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/visits/{visit_id}/hoan-tac-nhan")
async def undo_receive_at_room(
    visit_id: UUID,
    body: NhanTaiPhongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await NhanTaiPhongService(pool).hoan_tac_nhan(
        visit_id=str(visit_id), room_id=body.room_id, identity=identity
    )


@router.post("/luot-kham/visits/{visit_id}/nha-khoi-phong")
async def release_from_room(
    visit_id: UUID,
    body: NhanTaiPhongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await NhanTaiPhongService(pool).nha(
        visit_id=str(visit_id),
        room_id=body.room_id,
        identity=identity,
        huong_dan_room_id=body.huong_dan_room_id,
    )


@router.post("/luot-kham/visits/{visit_id}/hoan-tac-nha")
async def undo_release_from_room(
    visit_id: UUID,
    body: NhanTaiPhongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await NhanTaiPhongService(pool).hoan_tac_nha(
        visit_id=str(visit_id), room_id=body.room_id, identity=identity
    )


@router.post("/luot-kham/orders/{order_id}/routing/invalidate")
async def invalidate_service_routing(
    order_id: UUID,
    body: InvalidateRoutingBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceRoutingService(pool).invalidate(
        order_id=str(order_id),
        expected_routing_revision=body.expected_routing_revision,
        reason_code=body.reason_code,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.get("/luot-kham/orders/{order_id}/routing/recommendation")
async def recommend_service_room(
    order_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await ServiceRoutingService(pool).recommend(
        order_id=str(order_id), identity=identity
    )


@router.post("/luot-kham/orders/{order_id}/dispatch")
async def dispatch_order(
    order_id: UUID,
    body: DispatchBody,
    identity: StaffIdentity = Depends(_DISPATCH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await LuotKhamService(pool).dispatch_order(
        order_id=str(order_id),
        room_id=str(body.room_id),
        expected_version=body.expected_version,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/orders/{order_id}/start")
async def start_service(
    order_id: UUID,
    identity: StaffIdentity = Depends(_PERFORMER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    _tat_loi_cu(
        identity,
        "POST /luot-kham/orders/{id}/start",
        "phòng bấm [Bắt đầu] (execution/bat-dau).",
    )
    return await LuotKhamService(pool).start_service(
        order_id=str(order_id), identity=identity
    )


@router.post("/luot-kham/orders/{order_id}/complete")
async def complete_service(
    order_id: UUID,
    body: CompleteServiceBody,
    identity: StaffIdentity = Depends(_PERFORMER_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    _tat_loi_cu(
        identity,
        "POST /luot-kham/orders/{id}/complete",
        "phòng bấm [Xong] (execution/xong).",
    )
    return await LuotKhamService(pool).complete_service(
        order_id=str(order_id),
        performed=body.performed,
        reason=body.reason,
        result_note=body.result_note,
        identity=identity,
    )


# ── Thực hiện dịch vụ (Lifecycle v1 Slice 5) ────────────────────────────────
# Cửa là capability, không phải vai: ai được cấp khối "Thực hiện dịch vụ" thì
# bấm được. Hai endpoint cũ `/orders/{id}/start` và `/complete` vẫn sống cho tới
# khi màn hình chuyển hết sang đây.


class BatDauBody(BaseModel):
    expected_execution_revision: int = Field(ge=0)
    expected_routing_revision: int = Field(ge=0)
    #: V4 (30/09/2026): khách đang làm ở phòng khác → người bấm đã đồng ý
    #: "chuyển sang đây" (dừng lần làm ở phòng kia trong cùng giao dịch).
    giai_phong: bool = False


class HuyBatDauBody(BaseModel):
    attempt_id: UUID
    expected_execution_revision: int = Field(ge=0)


class XongBody(BaseModel):
    attempt_id: UUID
    expected_execution_revision: int = Field(ge=0)
    #: Ghi chú của lần làm (lấy mẫu / phòng bấm Xong) — tuỳ chọn, 24/09/2026.
    ghi_chu: str | None = Field(default=None, max_length=2000)


class KhongLamBody(BaseModel):
    expected_execution_revision: int = Field(ge=0)
    ly_do: str = Field(min_length=1, max_length=64)
    ghi_chu: str | None = Field(default=None, max_length=2000)


class GianDoanBody(BaseModel):
    attempt_id: UUID
    expected_execution_revision: int = Field(ge=0)
    ly_do: str = Field(min_length=1, max_length=64)
    ghi_chu: str | None = Field(default=None, max_length=2000)


class LamLaiBody(BaseModel):
    interrupted_attempt_id: UUID
    expected_execution_revision: int = Field(ge=0)
    ghi_chu: str | None = Field(default=None, max_length=2000)


@router.get("/luot-kham/orders/{order_id}/execution")
async def execution_xem(
    order_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Trạng thái thực hiện + hai số revision + mẫu kết quả gắn cho dịch vụ."""
    return await ServiceExecutionService(pool).xem(
        order_id=str(order_id), identity=identity
    )


@router.post("/luot-kham/orders/{order_id}/execution/bat-dau")
async def execution_bat_dau(
    order_id: UUID,
    body: BatDauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceExecutionService(pool).bat_dau(
        order_id=str(order_id),
        expected_execution_revision=body.expected_execution_revision,
        expected_routing_revision=body.expected_routing_revision,
        identity=identity,
        idempotency_key=idempotency_key,
        giai_phong=body.giai_phong,
    )


@router.post("/luot-kham/orders/{order_id}/execution/huy-bat-dau")
async def execution_huy_bat_dau(
    order_id: UUID,
    body: HuyBatDauBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Huỷ lần Bắt đầu bấm nhầm (V4) — chỉ khi chưa điền phiếu kết quả."""
    return await ServiceExecutionService(pool).huy_bat_dau(
        order_id=str(order_id),
        attempt_id=str(body.attempt_id),
        expected_execution_revision=body.expected_execution_revision,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/orders/{order_id}/execution/xong")
async def execution_xong(
    order_id: UUID,
    body: XongBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """`attempt_id` bắt buộc: request cũ không được đóng lần làm mới."""
    return await ServiceExecutionService(pool).xong(
        order_id=str(order_id),
        attempt_id=str(body.attempt_id),
        expected_execution_revision=body.expected_execution_revision,
        identity=identity,
        idempotency_key=idempotency_key,
        ghi_chu=body.ghi_chu,
    )


@router.post("/luot-kham/orders/{order_id}/execution/khong-lam")
async def execution_khong_lam(
    order_id: UUID,
    body: KhongLamBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceExecutionService(pool).khong_lam(
        order_id=str(order_id),
        expected_execution_revision=body.expected_execution_revision,
        ly_do=body.ly_do,
        ghi_chu=body.ghi_chu,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/orders/{order_id}/execution/gian-doan")
async def execution_gian_doan(
    order_id: UUID,
    body: GianDoanBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    return await ServiceExecutionService(pool).gian_doan(
        order_id=str(order_id),
        attempt_id=str(body.attempt_id),
        expected_execution_revision=body.expected_execution_revision,
        ly_do=body.ly_do,
        ghi_chu=body.ghi_chu,
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/orders/{order_id}/execution/lam-lai")
async def execution_lam_lai(
    order_id: UUID,
    body: LamLaiBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Làm lại là QUYẾT ĐỊNH riêng, không phải hệ quả tự động của gián đoạn."""
    return await ServiceExecutionService(pool).chuan_bi_lam_lai(
        order_id=str(order_id),
        interrupted_attempt_id=str(body.interrupted_attempt_id),
        expected_execution_revision=body.expected_execution_revision,
        ghi_chu=body.ghi_chu,
        identity=identity,
        idempotency_key=idempotency_key,
    )
