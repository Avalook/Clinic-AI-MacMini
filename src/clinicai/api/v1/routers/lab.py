"""Lab triage API (T-P9.4).
API phân loại xét nghiệm (T-P9.4).

POST /lab/triage/{lab_result_id} → runs the lab_triage sub-graph and
enforces the API-layer safety gate:
POST /lab/triage/{lab_result_id} → chạy sub-graph lab_triage và
thực thi cổng an toàn ở tầng API:

    triage_group == 'GROUP_C' AND reviewed_at IS NULL
        → raise SafetyGateError (HTTP 403)
    triage_group == 'GROUP_C' VÀ reviewed_at IS NULL
        → ném SafetyGateError (HTTP 403)

The graph itself remains graceful (no raise) — it always terminates and
records the GROUP_C state on `escalation_note` + creates a LAB_REVIEW
URGENT task. This router enforces the hard medical safety gate at the
boundary: a patient-facing caller must not receive any answer until BS
has reviewed. Once reviewed_at is populated the gate releases.
Bản thân graph vẫn hoạt động nhẹ nhàng (không ném lỗi) — nó luôn kết thúc và
ghi trạng thái GROUP_C vào `escalation_note` + tạo task LAB_REVIEW URGENT.
Router này thực thi cổng an toàn y khoa cứng ở ranh giới: người gọi hướng
bệnh nhân không được nhận bất kỳ câu trả lời nào cho đến khi BS đã review.
Khi reviewed_at được điền thì cổng mở ra.
"""

# Cho phép sử dụng cú pháp type hint hiện đại (Python 3.10+)
from __future__ import annotations

# Nhập lớp datetime từ module datetime
from datetime import datetime
# Nhập Annotated, Any, cast từ typing
from typing import Annotated, Any, cast
# Nhập kiểu UUID từ module uuid
from uuid import UUID

# Nhập thư viện asyncpg để kết nối PostgreSQL bất đồng bộ
import asyncpg
# Nhập thư viện structlog để ghi log có cấu trúc
import structlog
# Nhập APIRouter, Depends, Request từ FastAPI
from fastapi import APIRouter, Depends, Request
# Nhập BaseModel và Field từ Pydantic
from pydantic import BaseModel, Field

# Nhập các hằng số và lớp xác thực danh tính
from clinicai.api.identity import (
    CLINICAL_WRITE_ROLES, # Các vai trò được phép ghi dữ liệu lâm sàng
    PHYSICIAN_ROLES, # Các vai trò bác sĩ
    StaffIdentity, # Kiểu dữ liệu danh tính nhân viên
    require_role, # Hàm yêu cầu vai trò cụ thể
)
# Nhập InMemoryRateLimiter để giới hạn tốc độ request
from clinicai.api.rate_limit import InMemoryRateLimiter
# Nhập hàm lấy connection pool từ database
from clinicai.core.database import get_db_pool
# Nhập SafetyGateError từ exceptions
from clinicai.core.exceptions import SafetyGateError
# Nhập hàm build_lab_triage_subgraph để xây dựng sub-graph phân loại
from clinicai.graphs.lab_triage import build_lab_triage_subgraph
# Nhập LabTriageState từ state
from clinicai.graphs.lab_triage.state import LabTriageState
# Nhập AnthropicClient để gọi LLM
from clinicai.llm.anthropic_client import AnthropicClient
# Nhập LabOrderService để xử lý đặt xét nghiệm
from clinicai.services.lab_order_service import LabOrderService
# Nhập LabReviewOutcome và LabSafetyService
from clinicai.services.lab_safety_service import LabReviewOutcome, LabSafetyService

# Tạo logger structlog cho module này
logger = structlog.get_logger(__name__)

# Tạo router FastAPI với prefix /lab và tag "lab"
router = APIRouter(prefix="/lab", tags=["lab"])

# Ordering a test is a doctor's decision (W5, ADR-0012).
# Đặt xét nghiệm là quyết định của bác sĩ (W5, ADR-0012).
# Guard yêu cầu vai trò bác sĩ để đặt xét nghiệm
_ORDER_GUARD = require_role(*PHYSICIAN_ROLES)
# Entering a result is clinical work: doctors, nurses and the medical secretary.
# Reception and management are deliberately excluded.
# Nhập kết quả là công việc lâm sàng: bác sĩ, điều dưỡng và thư ký y khoa.
# Lễ tân và quản lý bị loại trừ có chủ đích.
# Guard yêu cầu vai trò lâm sàng để nhập kết quả
_RESULT_GUARD = require_role(*CLINICAL_WRITE_ROLES)
# Guard yêu cầu vai trò lâm sàng để phân loại
_TRIAGE_GUARD = require_role(*CLINICAL_WRITE_ROLES)
# Bộ giới hạn tốc độ cho endpoint phân loại xét nghiệm
LAB_TRIAGE_RATE_LIMIT = InMemoryRateLimiter(
    scope="lab-triage", # Phạm vi giới hạn
    limit=30, # Tối đa 30 request
    window_seconds=60, # Trong 60 giây
)
# Guard yêu cầu vai trò bác sĩ để review kết quả
_REVIEW_GUARD = require_role(*PHYSICIAN_ROLES)


# Định nghĩa schema dữ liệu cho request đặt xét nghiệm
class LabOrderRequest(BaseModel):
    """Order a lab test for a patient.
    Đặt xét nghiệm cho bệnh nhân."""

    clinic_patient_id: UUID  # ID bệnh nhân phòng khám
    test_name: str = Field(min_length=1, max_length=200)  # Tên xét nghiệm, từ 1-200 ký tự
    appointment_id: UUID | None = None  # ID lịch hẹn, tùy chọn


# Định nghĩa schema dữ liệu cho request nhập kết quả xét nghiệm
class LabResultEntryRequest(BaseModel):
    """Attach a summary and/or the provider's document to a pending result.
    Gắn tóm tắt và/hoặc tài liệu của nhà cung cấp vào kết quả đang chờ."""

    result_value: str | None = Field(default=None, max_length=4000)  # Giá trị kết quả, tối đa 4000 ký tự
    result_link: str | None = Field(default=None, max_length=2000)  # Liên kết kết quả, tối đa 2000 ký tự
    lab_provider: str | None = Field(default=None, max_length=200)  # Nhà cung cấp xét nghiệm, tối đa 200 ký tự


# Định nghĩa schema dữ liệu cho request review kết quả
class LabReviewRequest(BaseModel):
    """Bind the reviewed result to the patient chart visible to the doctor.
    Gắn kết quả đã review vào hồ sơ bệnh nhân hiển thị cho bác sĩ."""

    clinic_patient_id: UUID  # ID bệnh nhân phòng khám


# Định nghĩa schema dữ liệu cho response review kết quả
class LabReviewResponse(BaseModel):
    """Durable audit state after a doctor finalises the result.
    Trạng thái audit bền vững sau khi bác sĩ chốt kết quả."""

    lab_result_id: UUID  # ID kết quả xét nghiệm
    clinic_patient_id: UUID  # ID bệnh nhân phòng khám
    triage_group: str  # Nhóm phân loại
    is_finalized: bool  # Đã chốt kết quả chưa
    reviewed_by_staff_id: UUID  # ID nhân viên đã review
    reviewed_at: datetime  # Thời gian review
    already_finalized: bool  # Đã chốt trước đó chưa


# Endpoint POST để đặt xét nghiệm, trả về status 201 (Created)
@router.post("/orders", status_code=201)
async def order_lab_test(
    body: LabOrderRequest,  # Dữ liệu request đặt xét nghiệm
    identity: StaffIdentity = Depends(_ORDER_GUARD),  # Danh tính nhân viên (yêu cầu vai trò bác sĩ)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, object]:
    """Create a PENDING lab_result — the doctor has asked for a test.
    Tạo lab_result PENDING — bác sĩ đã yêu cầu xét nghiệm."""
    # Gọi LabOrderService để đặt xét nghiệm
    lab_result_id = await LabOrderService(pool).order_test(
        clinic_patient_id=str(body.clinic_patient_id),  # ID bệnh nhân (chuyển sang chuỗi)
        test_name=body.test_name,  # Tên xét nghiệm
        appointment_id=str(body.appointment_id) if body.appointment_id else None,  # ID lịch hẹn hoặc None
        identity=identity,  # Danh tính nhân viên
    )
    return {"ok": True, "lab_result_id": lab_result_id}  # Trả về ID kết quả xét nghiệm


# Endpoint PATCH để nhập kết quả xét nghiệm
@router.patch("/results/{lab_result_id}")
async def enter_lab_result(
    lab_result_id: UUID,  # ID kết quả xét nghiệm
    body: LabResultEntryRequest,  # Dữ liệu request nhập kết quả
    identity: StaffIdentity = Depends(_RESULT_GUARD),  # Danh tính nhân viên (yêu cầu vai trò lâm sàng)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> dict[str, object]:
    """Record what came back. Never finalises — that is a separate gate.
    Ghi lại kết quả nhận được. Không bao giờ chốt — đó là cổng riêng."""
    # Gọi LabOrderService để nhập kết quả
    await LabOrderService(pool).enter_result(
        lab_result_id=str(lab_result_id),  # ID kết quả (chuyển sang chuỗi)
        result_value=body.result_value,  # Giá trị kết quả
        result_link=body.result_link,  # Liên kết kết quả
        lab_provider=body.lab_provider,  # Nhà cung cấp xét nghiệm
        identity=identity,  # Danh tính nhân viên
    )
    return {"ok": True}  # Trả về trạng thái thành công


# Endpoint POST để review và chốt kết quả xét nghiệm
@router.post(
    "/results/{lab_result_id}/review",
    response_model=LabReviewResponse,  # Kiểu dữ liệu response
)
async def review_and_finalize_lab_result(
    lab_result_id: UUID,  # ID kết quả xét nghiệm
    body: LabReviewRequest,  # Dữ liệu request review
    identity: StaffIdentity = Depends(_REVIEW_GUARD),  # Danh tính nhân viên (yêu cầu vai trò bác sĩ)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> LabReviewResponse:
    """Doctor-only review/finalise gate, scoped to clinic and patient.
    Cổng review/chốt chỉ dành cho bác sĩ, giới hạn theo phòng khám và bệnh nhân."""
    # Gọi LabSafetyService để chốt review
    outcome: LabReviewOutcome = await LabSafetyService(pool).finalize_review(
        lab_result_id=lab_result_id,  # ID kết quả xét nghiệm
        clinic_patient_id=body.clinic_patient_id,  # ID bệnh nhân
        identity=identity,  # Danh tính nhân viên
    )
    # Trả về response với dữ liệu từ outcome
    return LabReviewResponse(
        lab_result_id=outcome.lab_result_id,  # ID kết quả
        clinic_patient_id=outcome.clinic_patient_id,  # ID bệnh nhân
        triage_group=outcome.triage_group,  # Nhóm phân loại
        is_finalized=outcome.is_finalized,  # Đã chốt chưa
        reviewed_by_staff_id=outcome.reviewed_by_staff_id,  # ID người review
        reviewed_at=outcome.reviewed_at,  # Thời gian review
        already_finalized=outcome.already_finalized,  # Đã chốt trước đó chưa
    )


# Hàm dependency lấy client LLM từ app state
def get_llm_client(request: Request) -> AnthropicClient:
    """FastAPI dependency: yields the application's AnthropicClient singleton.
    Dependency FastAPI: trả về singleton AnthropicClient của ứng dụng."""
    return cast(AnthropicClient, request.app.state.llm_client)  # Ép kiểu và trả về client


# Định nghĩa schema dữ liệu cho response phân loại xét nghiệm
class LabTriageResponse(BaseModel):
    """Patient-facing safe response surface for a triaged lab result.
    Bề mặt response an toàn hướng bệnh nhân cho kết quả xét nghiệm đã phân loại."""

    lab_result_id: UUID  # ID kết quả xét nghiệm
    triage_group: str | None  # Nhóm phân loại, có thể null
    requires_doctor_review: bool  # Có cần bác sĩ review không
    response_to_patient: str | None  # Phản hồi cho bệnh nhân, có thể null
    escalation_note: str | None  # Ghi chú leo thang, có thể null
    task_ids: list[UUID]  # Danh sách ID task
    error: str | None  # Lỗi, có thể null


# Hàm trích xuất reviewed_at từ kết quả graph
def _reviewed_at_of(result: dict[str, Any]) -> Any:
    """Pull `reviewed_at` off the LabResultRow inside graph output, if any.
    Lấy `reviewed_at` từ LabResultRow bên trong output của graph, nếu có."""
    row = result.get("lab_result_row")  # Lấy dòng kết quả từ output
    return getattr(row, "reviewed_at", None) if row is not None else None  # Trả về reviewed_at hoặc None


# Endpoint POST để phân loại kết quả xét nghiệm
@router.post("/triage/{lab_result_id}", response_model=LabTriageResponse)
async def triage_lab_result(
    lab_result_id: UUID,  # ID kết quả xét nghiệm
    pool: Annotated[asyncpg.Pool, Depends(get_db_pool)],  # Connection pool database
    identity: Annotated[StaffIdentity, Depends(_TRIAGE_GUARD)],  # Danh tính nhân viên (yêu cầu vai trò lâm sàng)
    llm_client: Annotated[AnthropicClient, Depends(get_llm_client)],  # Client LLM
    _rate_limit: Annotated[None, Depends(LAB_TRIAGE_RATE_LIMIT)],  # Giới hạn tốc độ
) -> LabTriageResponse:
    """Run lab_triage on a single lab_result_id, enforcing the GROUP_C gate.
    Chạy lab_triage trên một lab_result_id, thực thi cổng GROUP_C.

    Returns the triage outcome. Raises SafetyGateError (HTTP 403) when
    the result is GROUP_C and not yet reviewed by a doctor.
    Trả về kết quả phân loại. Ném SafetyGateError (HTTP 403) khi
    kết quả là GROUP_C và chưa được bác sĩ review.
    """
    # Xây dựng sub-graph phân loại xét nghiệm
    graph = build_lab_triage_subgraph(pool=pool, llm_client=llm_client)
    # Tạo state ban đầu cho graph
    state = LabTriageState(
        lab_result_id=lab_result_id,  # ID kết quả xét nghiệm
        clinic_id=UUID(identity.clinic_id),  # ID phòng khám (chuyển sang UUID)
    )
    # Chạy graph bất đồng bộ
    result = await graph.ainvoke(state)

    # Lấy nhóm phân loại từ kết quả
    triage_group = result.get("triage_group")
    # Lấy thời gian review từ kết quả
    reviewed_at = _reviewed_at_of(result)

    # Nếu là GROUP_C và chưa được review
    if triage_group == "GROUP_C" and reviewed_at is None:
        # Ghi log cảnh báo
        logger.warning(
            "api.lab.triage.safety_gate_blocked",  # Tên sự kiện log
            lab_result_id=str(lab_result_id),  # ID kết quả
            triage_group=triage_group,  # Nhóm phân loại
        )
        # Ném lỗi an toàn y khoa
        raise SafetyGateError(
            f"GROUP_C lab_result {lab_result_id} chưa được BS review — "
            "không thể trả kết quả cho BN."
        )

    # Trả về response phân loại
    return LabTriageResponse(
        lab_result_id=lab_result_id,  # ID kết quả
        triage_group=triage_group,  # Nhóm phân loại
        requires_doctor_review=bool(result.get("requires_doctor_review", False)),  # Có cần review không
        response_to_patient=result.get("response_to_patient"),  # Phản hồi cho bệnh nhân
        escalation_note=result.get("escalation_note"),  # Ghi chú leo thang
        task_ids=list(result.get("task_ids") or []),  # Danh sách task
        error=result.get("error"),  # Lỗi
    )


# ─── Lab release decision (Phase 4, cluster #4) ──────────────────────────────
# ─── Quyết định phát hành kết quả xét nghiệm (Phase 4, cụm #4) ───────────────
# Ported from src/dashboard/lib/lab-release.ts. Patient notification is a
# clinical safety boundary, not presentation logic. Only a finalized GROUP_A
# result may cross it; every unknown value fails closed per
# docs/lab_triage_spec_v1.md.
# Chuyển từ src/dashboard/lib/lab-release.ts. Thông báo cho bệnh nhân là
# ranh giới an toàn lâm sàng, không phải logic hiển thị. Chỉ kết quả GROUP_A
# đã chốt mới được vượt qua; mọi giá trị không xác định đều fail closed theo
# docs/lab_triage_spec_v1.md.


# Định nghĩa schema dữ liệu cho quyết định phát hành kết quả
class LabReleaseDecision(BaseModel):
    """Whether a lab result may be released to the patient, and why.
    Kết quả xét nghiệm có được phát hành cho bệnh nhân không, và tại sao."""

    allowed: bool  # Có được phép phát hành không
    label: str  # Nhãn giải thích


# Endpoint GET để kiểm tra quyết định phát hành kết quả
@router.get(
    "/results/{lab_result_id}/release",
    response_model=LabReleaseDecision,  # Kiểu dữ liệu response
)
async def lab_release_decision(
    lab_result_id: UUID,  # ID kết quả xét nghiệm
    identity: StaffIdentity = Depends(_RESULT_GUARD),  # Danh tính nhân viên (yêu cầu vai trò lâm sàng)
    pool: asyncpg.Pool = Depends(get_db_pool),  # Connection pool database
) -> LabReleaseDecision:
    """Can this lab result be told to the patient?
    Kết quả xét nghiệm này có thể được báo cho bệnh nhân không?

    Only GROUP_A + finalized → allowed=True. Everything else fails closed.
    Chỉ GROUP_A + đã chốt → allowed=True. Mọi trường hợp khác đều fail closed.
    """
    # Truy vấn nhóm phân loại và trạng thái chốt của kết quả
    row = await pool.fetchrow(
        """
        SELECT triage_group, is_finalized
          FROM lab_result
         WHERE lab_result_id = $1
           AND clinic_id = $2::uuid
        """,
        lab_result_id,  # ID kết quả xét nghiệm
        identity.clinic_id,  # ID phòng khám
    )
    # Nếu không tìm thấy kết quả
    if row is None:
        return LabReleaseDecision(
            allowed=False, label="Không tìm thấy kết quả xét nghiệm"  # Không được phép, không tìm thấy
        )

    # Lấy nhóm phân loại
    triage = row["triage_group"]
    # Lấy trạng thái đã chốt
    finalized = bool(row["is_finalized"])

    # Nếu là GROUP_A và đã chốt
    if triage == "GROUP_A" and finalized:
        return LabReleaseDecision(allowed=True, label="Được báo BN")  # Được phép báo bệnh nhân
    # Nếu là GROUP_C
    if triage == "GROUP_C":
        return LabReleaseDecision(allowed=False, label="Khẩn cấp — KHÔNG báo BN")  # Khẩn cấp, không báo
    # Nếu là GROUP_B
    if triage == "GROUP_B":
        return LabReleaseDecision(allowed=False, label="Chờ BS duyệt — KHÔNG báo BN")  # Chờ bác sĩ duyệt
    # Nếu là GROUP_A nhưng chưa chốt
    if triage == "GROUP_A":
        return LabReleaseDecision(allowed=False, label="Chưa hoàn tất — KHÔNG báo BN")  # Chưa hoàn tất
    # Mọi trường hợp khác
    return LabReleaseDecision(allowed=False, label="Chưa phân loại — KHÔNG báo BN")  # Chưa phân loại