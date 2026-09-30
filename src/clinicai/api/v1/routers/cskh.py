"""Customer-care endpoints (W5, ADR-0012)."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, time
from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

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
from clinicai.services.cskh_service import (
    CskhService,
    clinic_today,
)
from clinicai.services.danh_sach_khach_cskh import danh_sach_khach
from clinicai.services.ghi_chu_khach_service import (
    QUYEN_KHUNG_KHACH,
    GhiChuKhachService,
)
from clinicai.services.man_khach_hang_service import ManKhachHangService
from clinicai.services.recall_job_service import RecallJobService
from clinicai.services.recall_service import RecallService
from clinicai.services.tuong_tac_cskh_service import (
    GuiZaloService,
    HenGoiLaiService,
    TuongTacCskhService,
)

router = APIRouter()

# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_INTAKE_GUARD = cua_quyen("crm.manage", "reception.checkin.perform", "dispatch.manage")
# Lego 12 "Chăm sóc khách hàng" (Tuyền 25/09/2026): hỏi QUYỀN, không hỏi vai.
_RECALL_GUARD = cua_quyen("crm.manage")

# SÁU vai được vào màn Quản lý khách hàng — GƯƠNG của roles.ts "/customers".
# Lễ tân đã rời danh sách 16/09/2026 (Tuyền: *"quản lý khách hàng… vì thừa"*) —
# quầy không gọi điện chăm sóc khách. Quyền GHI vùng CSKH giữ nguyên
# (`cskh_service.INTAKE_ROLES` vẫn có RECEPTION) để Quản lý/Trưởng ca thao tác
# hộ được; bỏ ở đây chỉ là đóng cửa MÀN.
# Hai danh sách này phải khớp nhau: lệch là một vai thấy được màn nhưng màn
# trống dữ liệu (API chặn), hoặc ngược lại. Có test canh ở
# test_man_khach_hang.py; đổi bên nào thì đổi cả hai + test.
# Dữ liệu chăm sóc khách là thông tin VẬN HÀNH — lịch hẹn, trạng thái, sổ gọi
# điện — không phải bệnh án. Nới theo công tắc mở quyền tạm thời.
_MAN_KHACH_HANG_GUARD = cua_quyen("crm.manage")


@router.get("/cskh/danh-sach-khach")
async def danh_sach_khach_cskh(
    q: str | None = None,
    period: str | None = None,
    by: str | None = None,
    trang: int = 1,
    selected: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    identity: StaffIdentity = Depends(_MAN_KHACH_HANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Một trang khách (50) của màn Quản lý khách hàng + tổng số khớp bộ lọc.

    ``tu``/``den`` (yyyy-mm-dd, giờ VN) = khoảng của thanh ngày ngang; có thì
    thắng ``period``. Rác → bỏ qua, không 422 (`cua_so_khoang`)."""
    return await danh_sach_khach(
        pool,
        identity=identity,
        q=q,
        ky=period,
        theo=by,
        trang=trang,
        chon=selected,
        tu=tu,
        den=den,
    )


# ── Khung phải của một khách: ghi chú + tóm tắt (27/09/2026) ──────────────
# Hai màn dùng: Quản lý khách hàng (CSKH) và Tiếp đón (lễ tân) — nên cửa là
# "một trong hai quyền". Service kiểm lại (luật ở service, router mỏng).
_KHUNG_KHACH_GUARD = cua_quyen(*QUYEN_KHUNG_KHACH)


@router.get("/cskh/khach/{clinic_patient_id}/tom-tat")
async def tom_tat_khach(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(_KHUNG_KHACH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Mọi thứ của một khách trên một khung: lịch sắp tới / đã qua, lượt gần
    nhất, chỉ định chưa làm, tiền đã trả / còn phải thu, hẹn tái khám, số ghi chú."""
    return await GhiChuKhachService(pool).tom_tat(
        identity=identity, clinic_patient_id=str(clinic_patient_id)
    )


@router.get("/cskh/khach/{clinic_patient_id}/ghi-chu")
async def ghi_chu_cua_khach(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(_KHUNG_KHACH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return {
        "items": await GhiChuKhachService(pool).danh_sach(
            identity=identity, clinic_patient_id=str(clinic_patient_id)
        )
    }


class GhiChuKhachBody(BaseModel):
    noi_dung: str = Field(min_length=1, max_length=2000)


@router.post("/cskh/khach/{clinic_patient_id}/ghi-chu", status_code=201)
async def ghi_chu_moi(
    clinic_patient_id: UUID,
    body: GhiChuKhachBody,
    identity: StaffIdentity = Depends(_KHUNG_KHACH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await GhiChuKhachService(pool).ghi(
        identity=identity,
        clinic_patient_id=str(clinic_patient_id),
        noi_dung=body.noi_dung,
    )


@router.post("/cskh/ghi-chu/{ghi_chu_id}/go")
async def go_ghi_chu(
    ghi_chu_id: UUID,
    identity: StaffIdentity = Depends(_KHUNG_KHACH_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await GhiChuKhachService(pool).go(
        identity=identity, ghi_chu_id=str(ghi_chu_id)
    )


@router.get("/cskh/man-khach-hang")
async def man_khach_hang(
    ids: str,
    identity: StaffIdentity = Depends(_MAN_KHACH_HANG_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, list[Any]]:
    """Mười khối dữ liệu làm giàu của màn Quản lý khách hàng, MỘT vòng.

    KIỂU TRẢ VỀ LÀ `list[Any]`, KHÔNG PHẢI `list[dict]`. FastAPI kiểm kiểu trả
    về theo chú thích này, và khối `tuan_cong_bo` là danh sách CHUỖI (mã tuần
    đã công bố) chứ không phải danh sách bản ghi.

    Lỗi ấy ngủ suốt: khi chưa tuần lịch trực nào được công bố thì danh sách
    rỗng, và một danh sách rỗng thì hợp lệ với mọi kiểu phần tử. Đúng ngày
    16/09/2026 dựng lịch trực thật cho phòng khám, cả màn Quản lý khách hàng
    trả 500 cho MỌI vai — CSKH lẫn trưởng ca — và màn chỉ hiện "Không đọc được
    dữ liệu chăm sóc". Nhìn vào đó không ai đoán ra thủ phạm là một chú thích
    kiểu.

    Lát 2 lộ trình chịu tải (22/08/2026): thay mười vòng PostgREST — mỗi vòng
    một giao dịch riêng — bằng một lời gọi; mười câu SQL chạy tuần tự trên MỘT
    kết nối. `ids` là danh sách khách ĐANG HIỂN THỊ (đã phân trang, tối đa ~51
    gồm cả khách được chuông thông báo trỏ thẳng), phẩy ngăn cách.

    KHÔNG `response_model`: nó lặng lẽ bỏ khoá lạ — đã trả giá một lần với
    `call_order` (staging 20/08, mọi dòng hiện "thứ None" mà test vẫn xanh).
    """
    danh_sach = [x for x in (m.strip() for m in ids.split(",")) if x]
    # Trần 60: một trang 50 + khách được trỏ thẳng + dư địa. Gửi cả nghìn id
    # là dấu hiệu caller quên phân trang — chặn sớm cho lỗi nổi lên thay vì
    # âm thầm quét bảng to.
    if len(danh_sach) > 60:
        raise ValidationError(
            "Quá 60 khách một lượt — màn đã phân trang, gửi đúng trang đang xem."
        )
    for x in danh_sach:
        try:
            UUID(x)
        except ValueError as loi:
            raise ValidationError(f"Id khách không hợp lệ: {x!r}") from loi
    return await ManKhachHangService(pool).goi_du_lieu(
        clinic_id=identity.clinic_id, ids=danh_sach
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


class HenTaiKhamTay(BaseModel):
    """CSKH gõ tay ngày tái khám cho một khách."""

    clinic_patient_id: UUID
    ngay_tai_kham: date
    ly_do: str | None = Field(default=None, max_length=500)


@router.post("/cskh/nhac-tai-kham", status_code=201)
async def create_recall_by_hand(
    body: HenTaiKhamTay,
    identity: StaffIdentity = Depends(_RECALL_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hẹn tái khám do CSKH gõ → sinh hai mốc gọi: trước 7 ngày và trước 1 ngày.

    Đường tự sinh chỉ đọc được lời dặn nằm trong phiếu khám đã chốt. Khách nói
    qua điện thoại "tháng sau em quay lại" thì không có phiếu nào để đọc, và
    câu ấy hiện không có chỗ nào ghi xuống.
    """
    return await RecallJobService(pool).tao_thu_cong(
        identity=identity,
        clinic_patient_id=str(body.clinic_patient_id),
        ngay_tai_kham=body.ngay_tai_kham,
        ly_do=body.ly_do,
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
    # MÃ TRẠNG THÁI mà lần chạm này đóng lại (CHO_XAC_NHAN, DA_CHECKIN, …).
    # Không phải Literal: danh sách trạng thái là chuyện của giao diện và còn
    # đổi theo đặc tả nghiệp vụ; khoá cứng ở đây là mỗi lần thêm một trạng thái
    # lại phải deploy backend. Cột chỉ để màn hình tra lại, không có luật nào
    # phía sau nó.
    trang_thai_ma: str | None = Field(default=None, max_length=64)
    khach_xac_nhan: bool | None = None
    noi_dung: str | None = Field(default=None, max_length=2000)
    #: Bắt buộc với mốc CHECK_IN: xác minh khách bằng cách nào (CACH_XAC_MINH).
    xac_minh_cach: str | None = Field(default=None, max_length=32)


@router.post("/cskh/tuong-tac", status_code=201)
async def ghi_tuong_tac(
    body: TuongTacRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Ghi một lần chạm tới khách (gọi điện, nhắn Zalo, gặp trực tiếp).

    CHỐNG GHI TRÙNG, thêm 11/08/2026. Hai phép đo trên staging:

      · Bấm nút hai lần thật nhanh → HAI dòng sổ, cách nhau 0,35ms. Giao diện có
        khoá nút khi đang gửi nên người thật khó bấm trúng, nhưng máy chủ không
        có chốt nào.
      · Ngắt mạng ở mốc 90ms sau khi bấm → màn hình báo LỖI MẠNG trong khi dữ
        liệu ĐÃ VÀO. Người trực sẽ nhập lại, và lần nhập lại tạo dòng thứ hai.

    Ca thứ hai mới là ca thật sự hay xảy ra ở phòng khám, nơi wifi chập chờn.
    Và nó không hỏng ở chỗ dễ thấy: hai dòng "Đã gọi nhắc hẹn" trong lịch sử một
    khách làm người đọc tưởng đã gọi hai lần.

    `IdempotencyGuard` vốn đã che đặt lịch, thanh toán và work-items — tức đúng
    những đường đắt tiền. Sổ chạm CSKH nằm ngoài chỉ vì chưa ai nối vào, không
    phải vì có lý do. Cùng một hình dạng với các lỗi khác tìm được hôm nay.

    Không có `Idempotency-Key` thì guard cho qua, giữ nguyên hành vi cũ — khoá
    bật dần theo từng màn, không làm chết các lời gọi chưa cập nhật.
    """
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        # Lần gửi lại của ĐÚNG một thao tác: trả lại kết quả cũ, không ghi thêm.
        return idem.cached_response  # type: ignore[return-value]

    # Tên `dong_moi` chứ không phải `ket_qua`: ngay dưới có tham số `ket_qua=`
    # (kết quả cuộc gọi). Trùng tên thì chạy vẫn đúng nhưng người đọc sau phải
    # dừng lại một nhịp để chắc mình không nhầm hai thứ.
    #
    # BỌC TRẢ KHOÁ. Service dưới đây từ chối bằng `ValidationError` cho những
    # điều kiện nghiệp vụ có thật ("chưa gửi tệp kết quả cho khách", "mốc tại
    # quầy mới ghi kết quả này"). Không trả khoá thì người trực sửa xong bấm lại
    # vẫn nhận 409 suốt 5 phút, và câu giải thích thật biến mất — đo được trên
    # staging 13/08, xem `IdempotencyGuard.release`.
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        dong_moi = await TuongTacCskhService(pool).ghi(
            identity=identity,
            clinic_patient_id=str(body.clinic_patient_id),
            appointment_id=str(body.appointment_id) if body.appointment_id else None,
            loai=body.loai,
            kenh=body.kenh,
            ket_qua=body.ket_qua,
            khach_xac_nhan=body.khach_xac_nhan,
            noi_dung=body.noi_dung,
            trang_thai_ma=body.trang_thai_ma,
            xac_minh_cach=body.xac_minh_cach,
        )
        await idem.save(pool, dong_moi, status_code=201)
    return dong_moi


@router.post("/cskh/tuong-tac/{tuong_tac_id}/hoan-tac", status_code=201)
async def hoan_tac_tuong_tac(
    tuong_tac_id: UUID,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Rút lại một lần chạm bấm nhầm. KHÔNG xoá dòng sổ — xem service."""
    return await TuongTacCskhService(pool).hoan_tac(
        identity=identity, tuong_tac_id=str(tuong_tac_id)
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
    #: Giờ trong ngày. Bỏ trống = chỉ hẹn tới ngày, KHÔNG phải 00:00 —
    #: xem chú thích cột ở migration 20260810000006.
    gio_goi: time | None = None
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
        gio_goi=body.gio_goi,
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


# ── Tệp kết quả khám (ảnh / video siêu âm, phiếu xét nghiệm) ────────────────
#
# AI TẢI LÊN ĐƯỢC (Tuyền chốt 16/09/2026: *"phải có chỗ up file cho bác sĩ, thư
# ký, điều dưỡng… cả CSKH cũng cần có file để xem và tải xuống"*).
#
# Trước đó chỉ nhóm nhập liệu chăm sóc (CSKH, Lễ tân, Quản lý, Trưởng ca) tải
# lên được — tức chính những người KHÔNG cầm kết quả trên tay. Bác sĩ siêu âm
# chụp xong, kỹ thuật viên có phiếu xét nghiệm, điều dưỡng cầm phim chụp: cả ba
# đều phải nhờ người khác tải hộ, và bản gốc đi qua Zalo trước khi vào hồ sơ.
#
# Giữ nguyên đường siêu âm riêng của kỹ thuật viên (_SONO_GUARD) — nó gắn tệp
# vào phiếu siêu âm, khác với kho tệp kết quả của lượt khám ở đây.
# CHỈ LEGO (28/09/2026): cửa hỏi QUYỀN, không hỏi vai — xem permissions/cua_quyen.py.
_TEP_TAI_LEN_GUARD = cua_quyen(
    "crm.manage",
    "clinical.record.write",
    "result.form.fill",
    "reception.checkin.perform",
    moi_phong=True,
)


async def _cua_tai_len_tep(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> StaffIdentity:
    """Cửa TẢI LÊN tệp kết quả: vai cũ (`_TEP_TAI_LEN_GUARD`, giữ nguyên cách đổi
    vai theo vị trí / lego), HOẶC có khối ghi y khoa theo lego (27/09, đợt 3 —
    "khám CHỈ CẦN LEGO"): người điền phiếu kết quả gửi được ảnh của kết quả ấy.
    Kiểm trước khi đọc byte nào của thân."""
    from clinicai.permissions.can import can, can_o_phong_nao_do
    from clinicai.services.tep_ket_qua_service import tai_len_duoc_tep_ket_qua

    async with pool.acquire() as conn:
        # CHỈ LEGO (28/09/2026): một trong các quyền của `_TEP_TAI_LEN_GUARD`
        # (kể cả theo phòng nhờ xếp lịch), hoặc luật tải tệp kết quả.
        for q in _TEP_TAI_LEN_GUARD.quyen:  # type: ignore[attr-defined]
            if await can(conn, identity, q) or await can_o_phong_nao_do(
                conn, identity, q
            ):
                return identity
        if await tai_len_duoc_tep_ket_qua(conn, identity):
            return identity
    from clinicai.core.exceptions import SafetyGateError

    raise SafetyGateError("Bạn không có quyền tải tệp kết quả.")


def _cach_mo_tep(ten: str | None, tai: bool) -> str:
    """`inline` để xem; `attachment; filename*=…` để tải về đúng tên."""
    if not tai:
        return "inline"
    from urllib.parse import quote

    goc = (ten or "ket-qua").replace("\r", " ").replace("\n", " ").strip() or "ket-qua"
    ascii_ten = goc.encode("ascii", "ignore").decode().replace('"', "") or "ket-qua"
    return f"attachment; filename=\"{ascii_ten}\"; filename*=UTF-8''{quote(goc)}"


def _ben_tep(v: object) -> int | None:
    """Bên của tệp (mẫu hai bên): rỗng → None; "0".."7" → số; rác → 422."""
    s = str(v or "").strip()
    if not s:
        return None
    if s.isdigit() and int(s) <= 7:
        return int(s)
    raise ValidationError("Bên của tệp không hợp lệ.")


@router.post("/cskh/ket-qua/tep", status_code=201)
async def tai_len_ket_qua(
    request: Request,
    identity: StaffIdentity = Depends(_cua_tai_len_tep),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tải một tệp kết quả lên (multipart: file, clinic_patient_id,
    [appointment_id], [service_order_id]).

    Thân request chảy THẲNG vào kho (không giới hạn dung lượng — xem
    `nhan_tep_luong`). Quyền được kiểm trước khi đọc byte nào của thân.
    Tên tệp người dùng gửi CHỈ dùng làm nhãn; tên trên đĩa do hệ thống đặt.
    Kiểu kiểm bằng mấy byte đầu, không bằng đuôi tên.
    """
    from clinicai.services.nhan_tep_luong import nhan_multipart, uuid_hoac_loi
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    truong, tep = await nhan_multipart(request)
    try:
        return await TepKetQuaService(pool).tai_len(
            identity=identity,
            clinic_patient_id=str(
                uuid_hoac_loi(
                    truong.get("clinic_patient_id"), "Mã khách", bat_buoc=True
                )
            ),
            tep_da_nhan=tep,
            ten_hien_thi=tep.ten,
            appointment_id=uuid_hoac_loi(
                truong.get("appointment_id"), "Mã lịch hẹn", bat_buoc=False
            ),
            service_order_id=uuid_hoac_loi(
                truong.get("service_order_id"), "Mã chỉ định", bat_buoc=False
            ),
            ben=_ben_tep(truong.get("ben")),
        )
    finally:
        # Đã đổi tên về chỗ ở thật thì tệp tạm không còn; bị từ chối thì dọn.
        tep.duong.unlink(missing_ok=True)


#: Đọc nội dung tệp: CSKH/Lễ tân như cũ, THÊM bác sĩ — bác sĩ phải xem được
#: tệp mới cho phép gửi (15/09/2026). Từ 16/09 thêm thư ký và điều dưỡng: ai
#: tải lên được thì phải mở lại được thứ mình vừa tải, nếu không thì không có
#: cách nào kiểm tra mình có tải nhầm tệp của người khác hay không.
_KET_QUA_DOC_GUARD = _TEP_TAI_LEN_GUARD
# Duyệt / cho gửi kết quả: QUYỀN, không vai (28/09/2026).
_BAC_SI_GUARD = cua_quyen("result.review.approve")


@router.get("/cskh/ho-so-kham/{appointment_id}")
async def ho_so_kham(
    appointment_id: UUID,
    identity: StaffIdentity = Depends(_KET_QUA_DOC_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hồ sơ một lần khám, bản đọc gộp — để CSKH xem trước và tải PDF.

    Cùng nhóm vai với đọc tệp kết quả: ai đã được mở tệp kết quả của khách thì
    được xem hồ sơ lần khám chứa tệp ấy.
    """
    from clinicai.services.ho_so_kham_service import HoSoKhamService

    return await HoSoKhamService(pool).doc(
        identity=identity, appointment_id=str(appointment_id)
    )


@router.get("/cskh/ket-qua/cho-phep-gui")
async def tep_cho_bac_si_cho_phep(
    identity: StaffIdentity = Depends(_BAC_SI_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tệp kết quả CSKH đã tải lên, đang chờ bác sĩ cho phép gửi khách."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return {
        "items": await TepKetQuaService(pool).cho_bac_si_cho_phep(identity=identity)
    }


@router.post("/cskh/ket-qua/tep/{tep_id}/cho-phep-gui", status_code=201)
async def cho_phep_gui_tep(
    tep_id: UUID,
    identity: StaffIdentity = Depends(_BAC_SI_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bác sĩ đã xem tệp và cho phép CSKH gửi cho khách."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).cho_phep_gui(
        identity=identity, tep_id=str(tep_id)
    )


@router.get("/cskh/ket-qua/cho-xac-nhan")
async def tep_cho_xac_nhan(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh sách tệp kết quả external đang chờ xác nhận (CHO_XAC_NHAN).

    Bắt buộc capability ket_qua.xac_nhan (fail-closed, 403 nếu không có).
    LƯU Ý HIỆN TẠI (CURRENT LIMITATION): SINGLE-PARTNER PILOT ONLY.
    """
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return {"items": await TepKetQuaService(pool).cho_xac_nhan(identity=identity)}


class XacNhanTepDTO(BaseModel):
    trang_thai: str
    ly_do: str | None = None


class ThuHoiTepDTO(BaseModel):
    ly_do: str


@router.post("/cskh/ket-qua/tep/{tep_id}/xac-nhan")
async def xac_nhan_tep_ket_qua(
    tep_id: UUID,
    body: XacNhanTepDTO,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xác nhận tệp kết quả (HOP_LE hoặc TU_CHOI).

    Bắt buộc capability ket_qua.xac_nhan.
    """
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).xac_nhan_tep(
        identity=identity,
        tep_id=str(tep_id),
        trang_thai=body.trang_thai,
        ly_do=body.ly_do,
    )


@router.post("/cskh/ket-qua/tep/{tep_id}/thu-hoi")
async def thu_hoi_tep_ket_qua(
    tep_id: UUID,
    body: ThuHoiTepDTO,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thu hồi tệp kết quả đã từng HOP_LE.

    Bắt buộc capability ket_qua.xac_nhan và lý do.
    """
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).thu_hoi_tep(
        identity=identity,
        tep_id=str(tep_id),
        ly_do=body.ly_do,
    )


class XoaTepDTO(BaseModel):
    ly_do: str | None = None


@router.post("/cskh/ket-qua/tep/{tep_id}/xoa")
async def xoa_tep_ket_qua(
    tep_id: UUID,
    body: XoaTepDTO,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Xoá mềm một tệp kết quả (V9 30/09/2026) — lý do bắt buộc, khôi phục được
    30 ngày. Ai xoá được, theo loại nào (Xoá / Đính chính – gỡ tệp) do service
    quyết (`xoa_duoc`), không do cửa này."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).xoa_tep(
        identity=identity, tep_id=str(tep_id), ly_do=body.ly_do
    )


@router.post("/cskh/ket-qua/tep/{tep_id}/khoi-phuc")
async def khoi_phuc_tep_ket_qua(
    tep_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khôi phục tệp đã xoá mềm (Hoàn tác) — trong 30 ngày, khi tệp vật lý còn."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).khoi_phuc_tep(
        identity=identity, tep_id=str(tep_id)
    )


@router.get("/cskh/ket-qua/chi-dinh-cua-lich/{appointment_id}")
async def chi_dinh_cua_lich(
    appointment_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chỉ định của lượt (theo lịch hẹn) — ô "Kết quả của chỉ định nào" khi tải
    tệp ở màn Khách hàng (27/09, đợt 3). Quyền = quyền đọc tệp kết quả (kiểm
    trong service). Đăng ký TRƯỚC `/cskh/ket-qua/{clinic_patient_id}`."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return {
        "items": await TepKetQuaService(pool).chi_dinh_cua_lich(
            identity=identity, appointment_id=str(appointment_id)
        )
    }


@router.get("/cskh/ket-qua/{clinic_patient_id}")
async def danh_sach_ket_qua(
    clinic_patient_id: UUID,
    # Ai tải lên được thì phải XEM LẠI được danh sách — bản trước chỉ mở cho
    # vai tiếp nhận, nên bác sĩ, điều dưỡng tải xong không thấy tệp mình vừa gửi.
    # Từ 27/09 (đợt 3) luật đọc nằm ở service (`doc_duoc_tep_ket_qua`): vai cũ
    # HOẶC đọc được kết quả theo lego — cùng luật với nội dung tệp.
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tệp kết quả CÒN HIỆU LỰC của một khách, kèm đã gửi hay chưa; `da_xoa` =
    tệp đã xoá mềm trong 30 ngày (dòng "Đã xoá · Hoàn tác", V9)."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    dv = TepKetQuaService(pool)
    return {
        "items": await dv.danh_sach(
            identity=identity, clinic_patient_id=str(clinic_patient_id)
        ),
        "da_xoa": await dv.da_xoa_gan_day(
            identity=identity, clinic_patient_id=str(clinic_patient_id)
        ),
    }


@router.get("/cskh/ket-qua/tep/{tep_id}/noi-dung")
async def doc_tep_ket_qua(
    tep_id: UUID,
    request: Request,
    tai: bool = False,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> Response:
    """Nội dung một tệp — theo LUỒNG, và hiểu HTTP Range.

    Range là điều kiện để xem video, không phải tối ưu để sau: không có nó thì
    trình duyệt phải tải trọn tệp trước khi phát được giây đầu tiên, và thanh
    tua không kéo được. Container API giới hạn 1GB nên cũng không thể nạp cả
    tệp vào RAM cho mỗi người xem.
    """
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    path, mime, so_byte, ten = await TepKetQuaService(pool).duong_dan_de_doc(
        identity=identity, tep_id=str(tep_id)
    )
    # Dữ liệu bệnh nhân không được lưu trong cache trình duyệt hay proxy.
    # `nosniff` ngăn trình duyệt tự đoán kiểu và chạy nội dung như HTML.
    headers = {
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
        "Accept-Ranges": "bytes",
        # `?tai=1` (26/09/2026, nút Tải về): trình duyệt LƯU tệp với đúng tên
        # hiển thị (RFC 5987 giữ dấu tiếng Việt); mặc định vẫn xem tại chỗ.
        "Content-Disposition": _cach_mo_tep(ten, tai),
    }

    from clinicai.services.media_service import phan_tich_range

    khoang = phan_tich_range(request.headers.get("range"), so_byte)
    if khoang is None:
        return FileResponse(path, media_type=mime, headers=headers)
    dau, cuoi = khoang
    if dau > cuoi:
        # Yêu cầu nằm ngoài tệp — trả 416 kèm độ dài thật, để trình phát tự
        # chỉnh lại thay vì treo.
        return Response(
            status_code=416,
            headers={**headers, "Content-Range": f"bytes */{so_byte}"},
        )

    def doc_dan() -> Iterator[bytes]:
        con = cuoi - dau + 1
        with path.open("rb") as f:
            f.seek(dau)
            while con > 0:
                mieng = f.read(min(64 * 1024, con))
                if not mieng:
                    break
                con -= len(mieng)
                yield mieng

    headers["Content-Range"] = f"bytes {dau}-{cuoi}/{so_byte}"
    headers["Content-Length"] = str(cuoi - dau + 1)
    return StreamingResponse(
        doc_dan(), status_code=206, media_type=mime, headers=headers
    )


class DaGuiRequest(BaseModel):
    kenh: Literal["ZALO", "SMS", "TRUC_TIEP", "EMAIL"]


@router.post("/cskh/ket-qua/tep/{tep_id}/da-gui", status_code=201)
async def danh_dau_da_gui(
    tep_id: UUID,
    body: DaGuiRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """CSKH XÁC NHẬN đã gửi tệp này cho khách — hệ thống chưa tự gửi được."""
    from clinicai.services.tep_ket_qua_service import TepKetQuaService

    return await TepKetQuaService(pool).danh_dau_da_gui(
        identity=identity, tep_id=str(tep_id), kenh=body.kenh
    )


# ── Gửi tin Zalo (ZNS) ─────────────────────────────────────────────────────


@router.get("/cskh/zalo/trang-thai")
async def zalo_trang_thai(
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
) -> dict[str, Any]:
    """Zalo đã đủ cấu hình để gửi chưa, và thiếu gì.

    Giao diện hỏi câu này để KHÔNG mời người dùng bấm một nút chắc chắn hỏng.
    Ẩn hẳn nút thì họ không biết tính năng tồn tại; hiện nút mà bấm vào báo lỗi
    thì họ tưởng hệ thống hỏng. Hiện nút + nói thiếu gì là đường thứ ba.
    """
    from clinicai.services.providers import zalo

    thieu = []
    if not zalo.dang_bat():
        thieu.append("ZALO_ZNS_ACCESS_TOKEN")
    for loai in ("NHAC_HEN", "TRA_KET_QUA"):
        if not zalo.template_cho(loai):
            thieu.append(f"template {loai}")
    return {"bat": not thieu, "thieu": thieu}


class GuiZaloRequest(BaseModel):
    clinic_patient_id: UUID
    loai_tin: Literal["NHAC_HEN", "TRA_KET_QUA"]
    appointment_id: UUID | None = None


@router.post("/cskh/zalo/gui", status_code=201)
async def gui_zalo(
    body: GuiZaloRequest,
    identity: StaffIdentity = Depends(_INTAKE_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gửi một tin ZNS. Chỉ ghi sổ khi Zalo thật sự nhận."""
    return await GuiZaloService(pool).gui(
        identity=identity,
        clinic_patient_id=str(body.clinic_patient_id),
        loai_tin=body.loai_tin,
        appointment_id=str(body.appointment_id) if body.appointment_id else None,
    )
