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
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
    require_role_co_the_mo,
)
from clinicai.core.database import get_db_pool
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_execution_service import ServiceExecutionService
from clinicai.services.service_routing_service import ServiceRoutingService
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


# NĂM CỬA DƯỚI ĐÂY MỞ THEO CÔNG TẮC (Tuyền 16/09/2026: "tất cả các tài khoản
# đều có thể thao tác đã… trừ bác sĩ ra thui"). Khi `MO_QUYEN_TAM_THOI` bật,
# chúng nhận MỌI vai làm việc trong phòng khám; tắt đi là về đúng danh sách
# đang viết ở đây. Xem `identity.mo_quyen_tam_thoi`.
_BANG_GUARD = require_role_co_the_mo(
    ClinicRole.RECEPTION,
    ClinicRole.NURSE_ULTRASOUND,
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
    ClinicRole.TRUONG_CA,
    ClinicRole.MANAGEMENT,
)
# ĐƯỜNG KHÁM CHÍNH HỎI QUYỀN (CORE-B3, 23/09/2026): check-in, sinh hiệu, khám,
# ghi chú, duyệt kết quả — cửa ở router chỉ còn "đã đăng nhập"; quyền thật
# (`capability_grant`) do hàm dịch vụ hỏi trong chính giao dịch. Để lại cửa
# vai ở đây là còn hai hệ quyền: người được cấp quyền vẫn ăn 403 ở cửa ngoài.
# Công tắc mở quyền tạm thời KHÔNG nới các việc này nữa — quản lý cấp quyền.
_CHECKIN_GUARD = get_current_identity
_VITALS_GUARD = get_current_identity
_DISPATCH_GUARD = require_role_co_the_mo(ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT)
_PERFORMER_GUARD = require_role_co_the_mo(
    ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.NURSE_ULTRASOUND, ClinicRole.DOCTOR
)

# BA CỬA NÀY KHÔNG MỞ, kể cả khi công tắc bật. Khám, ghi bệnh án, duyệt chỉ
# định là việc của bác sĩ — ranh giới ấy có luật hành nghề đứng sau, không
# phải một quy ước nội bộ để nới cho tiện.
_DOCTOR_GUARD = require_role(ClinicRole.DOCTOR)
_NOTE_GUARD = get_current_identity
_TKYK_GUARD = require_role(ClinicRole.TKYK)
#: Bắt đầu / kết thúc phiên khám: bác sĩ hoặc thư ký đi kèm (Tuyền 16/09/2026).
#: Cũng KHÔNG mở theo công tắc — vẫn là cửa của ê-kíp bác sĩ.
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
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bảng làm việc hôm nay, đủ cho mọi vai; màn hình lọc theo vai."""
    return await BangLuotKham(pool).bang(identity=identity)


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
        raw=body.model_dump(),
        identity=identity,
        idempotency_key=idempotency_key,
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
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hàng chờ một phòng: đang chờ · đang trong phòng · đã xong hôm nay.

    `tu_van=true`: hàng CHUNG của bác sĩ tư vấn (dây H1, 24/09/2026)."""
    return await BangLuotKham(pool).hang_cho(
        identity=identity, room_id=str(phong) if phong else None, tu_van=tu_van
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
    identity: StaffIdentity = Depends(_DOCTOR_GUARD),
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
#: Đây là cửa của lệnh MỚI; hai endpoint draft/authorize bên dưới là đường cũ,
#: giữ nguyên cho tới khi mọi màn đã chuyển sang lệnh này.
_CHI_DINH_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.TKYK)


class ChiDinhBody(BaseModel):
    service_codes: list[str] = Field(min_length=1, max_length=30)


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


class XongBody(BaseModel):
    attempt_id: UUID
    expected_execution_revision: int = Field(ge=0)


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
