"""Customer-care endpoints (W5, ADR-0012)."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from clinicai.api.identity import ClinicRole, StaffIdentity, require_role
from clinicai.core.database import get_db_pool
from clinicai.services.cskh_service import (
    INTAKE_ROLES,
    CskhService,
    clinic_today,
)
from clinicai.services.recall_job_service import RecallJobService
from clinicai.services.recall_service import RecallService
from clinicai.services.tuong_tac_cskh_service import (
    HenGoiLaiService,
    TuongTacCskhService,
)

router = APIRouter()

_INTAKE_GUARD = require_role(*INTAKE_ROLES)
_RECALL_GUARD = require_role(
    ClinicRole.CSKH,
    ClinicRole.MANAGEMENT,
    ClinicRole.TRUONG_CA,
)


class CskhActionRequest(BaseModel):
    """One manually entered piece of care work."""

    category: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=4000)
    status: str | None = Field(default=None, max_length=120)
    # Optional, but a code that matches nothing is an error rather than a
    # record filed against no patient.
    patient_code: str | None = Field(default=None, max_length=64)


class CskhFollowupRequest(BaseModel):
    """A recall reminder call that was actually made."""

    clinic_patient_id: UUID
    note: str | None = Field(default=None, max_length=2000)
    # KẾT QUẢ, không phải "đã bấm nút". Giao diện gửi trường này từ lâu; trước
    # 20260807000002 nó bị vứt ở cửa và cả ba nút ghi ra một dòng như nhau.
    ket_qua: Literal["DA_LIEN_HE", "CHUA_NGHE_MAY", "CAN_BAC_SI", "TU_CHOI"] | None = (
        None
    )
    # 1 = gọi trước hẹn 5–7 ngày, 2 = gọi sáng ngày hẹn.
    luot_goi: int | None = Field(default=None, ge=1, le=9)


class RecallFollowupRead(BaseModel):
    clinic_patient_id: str
    full_name: str
    phone_primary: str | None
    due_date: date
    repeat_tests: list[str]
    instruction: str
    # Ngày gọi nhắc gần nhất (từ cskh_log), None nếu chưa gọi lần nào.
    last_called_date: date | None = None


@router.get("/cskh/recalls", response_model=list[RecallFollowupRead])
async def read_due_recalls(
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> list[RecallFollowupRead]:
    """Return the minimum recall projection, never the underlying SOAP note."""
    rows = await RecallService(pool).due_followups(
        clinic_id=identity.clinic_id,
        today=date.fromisoformat(clinic_today()),
    )
    return [RecallFollowupRead(**vars(row)) for row in rows]


# ── Việc gọi nhắc tái khám — hai lượt ──────────────────────────────────────
#
# Khác `/cskh/recalls` ngay trên: đường kia trả về một PHÉP CHIẾU tính lại mỗi
# lần gọi, còn đây là VIỆC CÓ THẬT trong bảng `nhac_tai_kham` — có hạn, có
# người gọi, có kết quả, đối soát được cuối ngày.


@router.get("/cskh/recall-jobs")
async def read_recall_jobs(
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Việc còn phải gọi hôm nay, tách theo lượt 1 và lượt 2.

    Sinh việc của hôm nay trước khi đọc. Dự án chưa có bộ hẹn giờ nào, nên mở
    màn hình là đường chắc chắn nhất; hàm sinh idempotent nên không đẻ bản sao.
    """
    return await RecallJobService(pool).danh_sach(identity=identity)


@router.post("/cskh/recall-jobs/generate", status_code=201)
async def generate_recall_jobs(
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, int]:
    """Sinh việc gọi cho hôm nay. Để cắm cron vào sau mà không đổi gì."""
    return await RecallJobService(pool).sinh(identity=identity)


class RecallCallResult(BaseModel):
    ket_qua: Literal["DA_LIEN_HE", "CHUA_NGHE_MAY", "CAN_BAC_SI", "TU_CHOI"]
    ghi_chu: str | None = Field(default=None, max_length=2000)


@router.post("/cskh/recall-jobs/{viec_id}/ket-qua", status_code=201)
async def record_recall_call(
    viec_id: UUID,
    body: RecallCallResult,
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đã gọi xong. Kết quả bắt buộc — kể cả khi không ai bắt máy."""
    return await RecallJobService(pool).ghi_ket_qua(
        identity=identity,
        viec_id=str(viec_id),
        ket_qua=body.ket_qua,
        ghi_chu=body.ghi_chu,
    )


class RecallSkip(BaseModel):
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/cskh/recall-jobs/{viec_id}/bo-qua", status_code=201)
async def skip_recall_job(
    viec_id: UUID,
    body: RecallSkip,
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Không cần gọi nữa — khách đã tự đặt lịch, đã tới, hay đã báo huỷ."""
    return await RecallJobService(pool).bo_qua(
        identity=identity, viec_id=str(viec_id), ly_do=body.ly_do
    )


@router.post("/cskh/actions", status_code=201)
async def record_cskh_action(
    body: CskhActionRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Log care work that was done by hand rather than captured automatically."""
    action_id = await CskhService(pool).record_action(
        category=body.category,
        description=body.description,
        status=body.status,
        patient_code=body.patient_code,
        identity=identity,
    )
    return {"ok": True, "id": action_id}


@router.post("/cskh/followup-calls", status_code=201)
async def record_followup_call(
    body: CskhFollowupRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Record that an overdue patient was called about coming back."""
    log_id = await CskhService(pool).record_followup_call(
        clinic_patient_id=str(body.clinic_patient_id),
        note=body.note,
        identity=identity,
        ket_qua=body.ket_qua,
        luot_goi=body.luot_goi,
    )
    return {"ok": True, "id": log_id}


# ── Sổ tương tác ────────────────────────────────────────────────────────────
#
# Cùng gác với phần nhập liệu chăm sóc (INTAKE_ROLES): ai ghi được hồ sơ hành
# chính của khách thì ghi được "đã gọi cho khách". Mở rộng hơn thế là mở cho
# người không gọi điện bao giờ khai rằng mình đã gọi.


class TuongTacRequest(BaseModel):
    clinic_patient_id: UUID
    appointment_id: UUID | None = None
    loai: Literal[
        "XAC_NHAN_LICH",
        "NHAC_HEN",
        "CHECK_XN",
        "TRA_KQ",
        "HOI_LY_DO_HUY",
        "HOI_THAM",
        "KHAC",
        # Mốc tại quầy — check-in/check-out còn đổi trạng thái lịch hẹn thật.
        "CHECK_IN",
        "CHECK_OUT",
        "THANH_TOAN",
        "MUA_THUOC",
    ]
    kenh: Literal["GOI", "ZALO", "SMS", "TRUC_TIEP", "KHONG_LIEN_HE"]
    # DANH SÁCH NÀY PHẢI KHỚP KET_QUA_HOP_LE trong tuong_tac_cskh_service —
    # bài kiểm test_router_literal_khop_service canh. Hai lần mở rộng trước
    # (KLLD/Hẹn GLS rồi GHI_NHAN) chỉ sửa service mà trượt chỗ này trong im
    # lặng, nên suốt một buổi CSKH chọn "không liên lạc được" trên màn là ăn
    # 422 — service nhận mà cửa Pydantic đã đóng.
    ket_qua: Literal[
        "DA_LIEN_HE",
        "CHUA_NGHE_MAY",
        "KHONG_LIEN_LAC_DUOC",
        "HEN_GOI_LAI",
        "CAN_BAC_SI",
        "TU_CHOI",
        "BO_QUA",
        "GHI_NHAN",
    ]
    khach_xac_nhan: bool | None = None
    noi_dung: str | None = Field(default=None, max_length=2000)


@router.post("/cskh/tuong-tac", status_code=201)
async def ghi_tuong_tac(
    body: TuongTacRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ghi một lần chạm tới khách (gọi điện, nhắn Zalo, gặp trực tiếp)."""
    return await TuongTacCskhService(pool).ghi(
        identity=identity,
        clinic_patient_id=str(body.clinic_patient_id),
        appointment_id=str(body.appointment_id) if body.appointment_id else None,
        loai=body.loai,
        kenh=body.kenh,
        ket_qua=body.ket_qua,
        khach_xac_nhan=body.khach_xac_nhan,
        noi_dung=body.noi_dung,
    )


@router.get("/cskh/tuong-tac/{clinic_patient_id}")
async def lich_su_tuong_tac(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dòng thời gian của một khách — gộp sổ tương tác và các lượt nhắc tái khám."""
    return {
        "items": await TuongTacCskhService(pool).lich_su(
            identity=identity, clinic_patient_id=str(clinic_patient_id)
        )
    }


class HenGoiLaiRequest(BaseModel):
    clinic_patient_id: UUID
    ngay_goi: date
    ly_do: str = Field(min_length=1, max_length=500)


@router.post("/cskh/hen-goi-lai", status_code=201)
async def tao_hen_goi_lai(
    body: HenGoiLaiRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tự hẹn một việc gọi lại — chỗ đựng việc hệ thống chưa suy được."""
    return await HenGoiLaiService(pool).tao(
        identity=identity,
        clinic_patient_id=str(body.clinic_patient_id),
        ngay_goi=body.ngay_goi,
        ly_do=body.ly_do,
    )


@router.patch("/cskh/hen-goi-lai/{hen_id}")
async def dong_hen_goi_lai(
    hen_id: UUID,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đóng việc đã gọi xong."""
    return await HenGoiLaiService(pool).dong(identity=identity, hen_id=str(hen_id))


# ── Phản hồi / khiếu nại của khách (DoD mục 3) ─────────────────────────────


class PhanHoiRequest(BaseModel):
    clinic_patient_id: UUID
    loai: Literal["KHEN", "GOP_Y", "KHIEU_NAI"]
    noi_dung: str = Field(min_length=1, max_length=4000)


class PhanHoiCapNhatRequest(BaseModel):
    trang_thai: Literal["MOI", "DANG_XU_LY", "DA_XU_LY"]
    huong_xu_ly: str | None = Field(default=None, max_length=2000)


@router.post("/cskh/phan-hoi", status_code=201)
async def ghi_phan_hoi(
    body: PhanHoiRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ghi một phản hồi / khiếu nại của khách."""
    from clinicai.services.phan_hoi_khach_service import PhanHoiKhachService

    return await PhanHoiKhachService(pool).ghi(
        identity=identity,
        clinic_patient_id=str(body.clinic_patient_id),
        loai=body.loai,
        noi_dung=body.noi_dung,
    )


@router.patch("/cskh/phan-hoi/{phan_hoi_id}")
async def cap_nhat_phan_hoi(
    phan_hoi_id: UUID,
    body: PhanHoiCapNhatRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chuyển trạng thái xử lý — đóng thì phải ghi đã xử lý thế nào."""
    from clinicai.services.phan_hoi_khach_service import PhanHoiKhachService

    return await PhanHoiKhachService(pool).cap_nhat(
        identity=identity,
        phan_hoi_id=str(phan_hoi_id),
        trang_thai=body.trang_thai,
        huong_xu_ly=body.huong_xu_ly,
    )
