"""FastAPI endpoints for Patient CRUD operations."""

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role_co_the_mo,
)
from clinicai.core.database import get_db_pool
from clinicai.core.exceptions import ResourceNotFoundError, ValidationError
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.schemas.patient import (
    PatientCreateDTO,
    PatientDTO,
    PatientUpdateDTO,
    PhoneCheckResult,
    PhoneDuplicateMatch,
)
from clinicai.services.patient_service import PatientService

router = APIRouter()

# Tạo và sửa hồ sơ hành chính là thao tác VẬN HÀNH, không phải việc lâm sàng —
# nên hai cửa này nới được theo công tắc mở quyền tạm thời.
_INTAKE_GUARD = require_role_co_the_mo(
    ClinicRole.CSKH,
    ClinicRole.RECEPTION,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)
# Lego 11 "Thêm bệnh nhân" (25/09/2026): tạo hồ sơ hỏi QUYỀN. Cửa phụ (thêm số
# điện thoại, ưu tiên) còn theo vai — NỢ chuyển dần.
_TAO_BENH_NHAN_GUARD = cua_quyen("patient.create", "booking.create", "crm.manage")
_PATIENT_EDIT_GUARD = require_role_co_the_mo(
    ClinicRole.CSKH,
    ClinicRole.RECEPTION,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
    ClinicRole.DOCTOR,
    ClinicRole.ULTRASOUND_DOCTOR,
    ClinicRole.TKYK,
)


@router.post(
    "/patients",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
)
async def create_patient(
    data: PatientCreateDTO,
    identity: StaffIdentity = Depends(_TAO_BENH_NHAN_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO | JSONResponse:
    """Register a patient with MPI dedup. Three outcomes:

    * created      → 201, the PatientDTO.
    * phone dup    → 200 ``{"duplicate": true, "matches": [...]}`` (no insert).
    * CCCD dup     → 200 ``{"duplicate": true, "cccd_trung": true, ...}``;
      gửi lại kèm ``ly_do_trung_cccd`` để tạo.
    """
    service = PatientService(pool)
    result = await service.create_patient(data, identity)
    if result.patient is None:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "duplicate": True,
                "cccd_trung": result.cccd_trung,
                "matches": jsonable_encoder(result.matches),
            },
        )
    return result.patient


# Thứ tự khai KHÔNG còn là thứ giữ hai đường này khỏi nuốt nhau — "/patients/{id}"
# bên dưới nay dùng bộ chuyển đổi `{id:uuid}`, nên "check-phone" và
# "check-duplicate" không thể khớp vào nó nữa. Ràng buộc dựa vào thứ tự vài dòng
# ở một chỗ khác chính là thứ đã làm /appointments/policy trả 422 rất lâu mà
# không ai thấy.
@router.get("/patients/check-phone", response_model=PhoneCheckResult)
async def check_phone_duplicate(
    phone: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PhoneCheckResult:
    """Read-only early warning: is this phone already on file (feedback #9)?

    Returns minimal identifying fields so reception can spot a relative sharing
    a number (e.g. a mother registering for her child). NEVER blocks creation —
    the warning is advisory; the operator decides.
    """
    if not phone.strip():
        raise ValidationError("phone query parameter must not be blank")
    service = PatientService(pool)
    matches = await service.find_phone_duplicates(phone, identity.clinic_id)
    return PhoneCheckResult(
        exists=bool(matches),
        matches=[PhoneDuplicateMatch(**m) for m in matches],
    )


@router.get("/patients/check-duplicate")
async def check_duplicate(
    phone: str | None = None,
    full_name: str | None = None,
    birth_year: int | None = Query(default=None, ge=1900, le=2100),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cảnh báo SỚM hồ sơ có thể trùng — CÙNG MỘT LUẬT với lúc lưu.

    Trước đây màn hình tạo bệnh nhân tự viết truy vấn trùng của riêng nó (chỉ
    SĐT), còn lúc lưu thì ``MPIService.find_candidates`` lại so cả CCCD và —
    từ nay — họ tên + năm sinh. Hai luật khác nhau cho cùng một câu hỏi nghĩa
    là Lễ tân được báo "không trùng", bấm lưu, rồi hồ sơ vào hàng chờ gộp.

    Endpoint này gọi ĐÚNG hàm mà đường lưu gọi, nên hai bên không thể lệch.

    CHỈ CẢNH BÁO, không chặn: mẹ đăng ký bằng số của mình cho con là hợp lệ, và
    Notion nói rõ *"chỉ cảnh báo để người có quyền xử lý, không tự động gộp"*.
    """
    from datetime import date as _date

    from clinicai.services.mpi_service import MPIService

    # TÊN ĐƠN THUẦN cũng đáng một câu trả lời (Tuyền 15/08/2026): khách cũ
    # gọi từ số MỚI, người trực mới chỉ kịp gõ tên — chưa hỏi năm sinh. Bản
    # trước đòi (tên VÀ năm) hoặc số, nên đúng ca hay gặp nhất lại im lặng.
    # Khớp MẠNH (matches) vẫn giữ nguyên luật của đường lưu — tên đơn thuần
    # chỉ đổ vào `trung_ten`, tín hiệu yếu, ô xám.
    if not any([phone, full_name]):
        return {"exists": False, "matches": []}

    probe = PatientCreateDTO(
        location_id=UUID(identity.location_id),
        full_name=(full_name or "").strip() or "—",
        phone_primary=(phone or "").strip() or None,
        # Ngày 1/1 chỉ để mang NĂM xuống; luật chỉ so năm (xem mpi_service).
        date_of_birth=_date(birth_year, 1, 1) if birth_year else None,
    )
    found = await MPIService.find_candidates(pool, probe, identity.clinic_id)

    # TRÙNG TÊN ĐƠN THUẦN — TÍN HIỆU YẾU, TÁCH RIÊNG.
    #
    # Luật khớp mạnh ở trên đòi tên VÀ năm sinh cùng khớp, nên "Lương Thị Như"
    # sinh 1990 gõ vào khi hệ thống đã có "Lương Thị Như" sinh 2026 thì không
    # có gì báo. Tuyền gặp đúng ca ấy 14/08/2026.
    #
    # KHÔNG gộp vào `matches`: danh sách ấy phải khớp ĐÚNG những gì đường lưu
    # coi là trùng (MPIService.find_candidates) — đó là lý do endpoint này tồn
    # tại. Nhét thêm tín hiệu yếu vào là hai bên lệch nhau trở lại, đúng thứ nó
    # sinh ra để chống.
    #
    # Và trùng tên ở Việt Nam là chuyện thường, nên đây chỉ là một câu nhắc để
    # người trực tự nhìn — không phải một cái khoá.
    trung_ten: list[dict[str, Any]] = []
    if full_name and (ten := full_name.strip()):
        da_co = {p.patient_code for p in found}
        rows = await pool.fetch(
            """
            SELECT clinic_patient_id, full_name, patient_code,
                   date_of_birth, birth_year
              FROM public.patient
             WHERE clinic_id = $1::uuid
               AND is_active
               AND full_name_unaccent = lower(replace(replace(
                     f_unaccent($2), 'đ', 'd'), 'Đ', 'D'))
             ORDER BY created_at DESC
             LIMIT 6
            """,
            identity.clinic_id,
            ten,
        )
        trung_ten = [
            {
                "clinic_patient_id": str(r["clinic_patient_id"]),
                "full_name": r["full_name"],
                "patient_code": r["patient_code"],
                "birth_year": r["birth_year"]
                or (r["date_of_birth"].year if r["date_of_birth"] else None),
            }
            for r in rows
            if r["patient_code"] not in da_co
        ][:5]

    return {
        "exists": bool(found),
        "trung_ten": trung_ten,
        # Tối thiểu đủ để nhận ra người: KHÔNG trả CCCD, địa chỉ hay số điện
        # thoại đầy đủ — màn này chỉ cần trả lời "có phải người này không".
        "matches": [
            {
                # `clinic_patient_id` để nút "thêm số cho khách này" ở màn tạo
                # BN biết gắn số vào AI — mã hồ sơ là chữ cho người, máy cần khoá.
                "clinic_patient_id": str(p.clinic_patient_id),
                "full_name": p.full_name,
                "patient_code": p.patient_code,
                "birth_year": p.date_of_birth.year if p.date_of_birth else None,
            }
            for p in found[:5]
        ],
    }


class SdtThemDTO(BaseModel):
    """Một số điện thoại gắn thêm vào hồ sơ có sẵn."""

    clinic_patient_id: UUID
    so_dien_thoai: str
    loai: Literal["CHINH", "NGUOI_NHA"] = "CHINH"


@router.post("/patients/sdt-them", status_code=status.HTTP_201_CREATED)
async def them_so_dien_thoai(
    data: SdtThemDTO,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thêm số cho khách CÓ SẴN — lối thứ ba của ô cảnh báo trùng.

    Khách dùng 2–3 số là bình thường; trước đây ô cảnh báo "số/tên này đã có
    trong hệ thống" chỉ có hai lối ra: vẫn tạo hồ sơ mới (tách đôi bệnh án)
    hoặc bỏ dở. Nay người trực xác nhận "đúng là khách cũ" và gắn số mới vào
    hồ sơ cũ; từ đó tra số nào cũng ra đúng một người.
    """
    return await PatientService(pool).them_so_dien_thoai(
        clinic_patient_id=str(data.clinic_patient_id),
        so_dien_thoai=data.so_dien_thoai,
        loai=data.loai,
        identity=identity,
    )


@router.delete("/patients/sdt-them")
async def xoa_so_dien_thoai(
    clinic_patient_id: UUID,
    so_dien_thoai: str,
    identity: StaffIdentity = Depends(_PATIENT_EDIT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ một số THÊM — cùng gác vai với sửa hồ sơ (xoá số là sửa hồ sơ)."""
    return await PatientService(pool).xoa_so_dien_thoai(
        clinic_patient_id=str(clinic_patient_id),
        so_dien_thoai=so_dien_thoai,
        identity=identity,
    )


@router.get("/patients/{id:uuid}", response_model=PatientDTO)
async def get_patient_by_id(
    id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO:
    """Retrieve a single patient by ID. Raises ResourceNotFoundError if not found."""
    service = PatientService(pool)
    patient = await service.get_by_id(id, identity.clinic_id)
    if patient is None:
        raise ResourceNotFoundError(f"Patient {id} not found")
    return patient


# Danh sách bệnh nhân (tra cứu) — cùng tập vai với route "/patient-list" ở
# dashboard (lib/roles.ts). Trưởng ca / dược sĩ / TV không có màn này.
# TRƯỞNG CA thiếu ở đây là SÓT, không phải luật: danh sách này có đủ mười vai
# làm việc còn lại, và trưởng ca thì đã được tạo lẫn sửa hồ sơ bệnh nhân qua hai
# cửa ngay phía trên. Hệ quả đo được 16/09/2026: bấm "Quản lý khách hàng" từ màn
# Toàn cảnh điều phối thì màn báo "Không đọc được dữ liệu chăm sóc".
# Lego 13 "Danh sách bệnh nhân" (Tuyền 25/09/2026): hỏi QUYỀN, không hỏi vai.
# Migration 20260925000015 cấp lego này cho đúng 11 vai trước đây vào được.
_DANH_SACH_GUARD = cua_quyen("patient.list.view")


@router.get("/patients/danh-sach")
async def danh_sach_benh_nhan(
    identity: StaffIdentity = Depends(_DANH_SACH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hồ sơ + các lượt khám (khách ĐÃ TỚI, bất kể ngày) + số tổng.

    Thay truy vấn Supabase của màn Danh sách bệnh nhân — bản cũ chỉ đếm lượt
    COMPLETED hoặc CHECKED_IN trong HÔM NAY nên qua nửa đêm mất hết lượt đang mở
    (16/09/2026). Thư ký y khoa chỉ nhận khách của bác sĩ mình.
    """
    from clinicai.services.danh_sach_benh_nhan_service import DanhSachBenhNhanService

    return await DanhSachBenhNhanService(pool).lay(identity=identity)


@router.get("/patients", response_model=list[PatientDTO])
async def get_patients_by_phone(
    phone: str,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[PatientDTO]:
    """Retrieve all patients matching a primary or secondary phone number."""
    if not phone.strip():
        raise ValidationError("phone query parameter must not be blank")
    service = PatientService(pool)
    return await service.get_by_phone(phone, identity.clinic_id)


@router.patch("/patients/{id:uuid}", response_model=PatientDTO)
async def update_patient(
    id: UUID,
    data: PatientUpdateDTO,
    identity: StaffIdentity = Depends(_PATIENT_EDIT_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> PatientDTO:
    """Partially update demographic details for a patient."""
    service = PatientService(pool)
    return await service.update_patient(id, data, identity)


class UuTienRequest(BaseModel):
    uu_tien: bool
    ly_do: str | None = Field(default=None, max_length=500)


@router.put("/patients/{id:uuid}/uu-tien")
async def dat_khach_uu_tien(
    id: UUID,
    body: UuTienRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Đánh dấu / bỏ dấu khách ưu tiên (VIP) kèm lý do — Tuyền chốt 15/09/2026.

    Chỉ là dấu cho lễ tân; không tự đổi thứ tự khám (lễ tân kéo tay).
    """
    from clinicai.services.thu_tu_kham_service import ThuTuKhamService

    return await ThuTuKhamService(pool).dat_uu_tien(
        identity=identity,
        clinic_patient_id=str(id),
        uu_tien=body.uu_tien,
        ly_do=body.ly_do,
    )
