"""Luồng khám lát 1 — màn `/luot-kham` của sáu vai.

Router mỏng: đọc thân, gác vai, chuyển cho ``LuotKhamService``. Mọi luật nằm ở
service và ``luot_kham_rules``. Service tự gác vai lần nữa — gọi thẳng service
từ chỗ khác cũng không vượt quyền được.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    require_role,
    require_role_co_the_mo,
)
from clinicai.core.database import get_db_pool
from clinicai.services.luot_kham_service import LuotKhamService

router = APIRouter()

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
_CHECKIN_GUARD = require_role_co_the_mo(ClinicRole.RECEPTION, ClinicRole.MANAGEMENT)
_VITALS_GUARD = require_role_co_the_mo(
    ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION, ClinicRole.DOCTOR
)
_DISPATCH_GUARD = require_role_co_the_mo(ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT)
_PERFORMER_GUARD = require_role_co_the_mo(
    ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.NURSE_ULTRASOUND, ClinicRole.DOCTOR
)

# BA CỬA NÀY KHÔNG MỞ, kể cả khi công tắc bật. Khám, ghi bệnh án, duyệt chỉ
# định là việc của bác sĩ — ranh giới ấy có luật hành nghề đứng sau, không
# phải một quy ước nội bộ để nới cho tiện.
_DOCTOR_GUARD = require_role(ClinicRole.DOCTOR)
_NOTE_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.TKYK)
_TKYK_GUARD = require_role(ClinicRole.TKYK)
#: Bắt đầu / kết thúc phiên khám: bác sĩ hoặc thư ký đi kèm (Tuyền 16/09/2026).
#: Cũng KHÔNG mở theo công tắc — vẫn là cửa của ê-kíp bác sĩ.
_CONSULT_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.TKYK)


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
    return await LuotKhamService(pool).bang(identity=identity)


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
    return await LuotKhamService(pool).record_vitals(
        visit_id=str(visit_id),
        raw=body.model_dump(),
        identity=identity,
        idempotency_key=idempotency_key,
    )


@router.post("/luot-kham/visits/{visit_id}/goi-do")
async def goi_do_sinh_hieu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_VITALS_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Điều dưỡng gọi khách vào đo sinh hiệu."""
    return await LuotKhamService(pool).goi_do_sinh_hieu(
        visit_id=str(visit_id), identity=identity
    )


@router.get("/luot-kham/phong-hom-nay")
async def phong_hom_nay(
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Phòng người gọi đứng hôm nay (theo lịch) + danh sách mọi phòng."""
    return await LuotKhamService(pool).phong_hom_nay(identity=identity)


@router.get("/luot-kham/hang-cho")
async def hang_cho(
    phong: UUID | None = None,
    identity: StaffIdentity = Depends(_BANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hàng chờ một phòng: đang chờ · đang trong phòng · đã xong hôm nay."""
    return await LuotKhamService(pool).hang_cho(
        identity=identity, room_id=str(phong) if phong else None
    )


class DuyetKetQuaBody(BaseModel):
    danh_gia: str | None = Field(default=None, max_length=5000)


#: Duyệt kết quả là quyết định chuyên môn — không mở theo công tắc.
_REVIEW_GUARD = require_role(ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR)


@router.get("/luot-kham/ket-qua-cho-duyet")
async def ket_qua_cho_duyet(
    identity: StaffIdentity = Depends(_REVIEW_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chỉ định đã có kết quả, chờ bác sĩ đánh giá và cho phép gửi."""
    return await LuotKhamService(pool).ket_qua_cho_duyet(identity=identity)


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


@router.post("/luot-kham/consultations/{consultation_id}/notes")
async def save_note(
    consultation_id: UUID,
    body: NoteBody,
    identity: StaffIdentity = Depends(_NOTE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LuotKhamService(pool).save_note(
        consultation_id=str(consultation_id), body=body.body, identity=identity
    )


@router.post("/luot-kham/consultations/{consultation_id}/draft-orders")
async def propose_orders(
    consultation_id: UUID,
    body: DraftBody,
    identity: StaffIdentity = Depends(_TKYK_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
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


@router.post("/luot-kham/consultations/{consultation_id}/complete")
async def complete_consultation(
    consultation_id: UUID,
    body: CompleteConsultationBody,
    identity: StaffIdentity = Depends(_CONSULT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
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
    return await LuotKhamService(pool).complete_service(
        order_id=str(order_id),
        performed=body.performed,
        reason=body.reason,
        result_note=body.result_note,
        identity=identity,
    )
