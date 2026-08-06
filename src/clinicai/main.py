"""ClinicAI FastAPI application entry point."""

import os
from contextlib import AsyncExitStack, asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

import asyncpg.exceptions
import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse

from clinicai.api.auth import api_key_middleware
from clinicai.api.middleware import (
    DbErrorMiddleware,
    RequestIdMiddleware,
    TimingMiddleware,
)
from clinicai.api.runaway_guard import (
    runaway_guard,
    runaway_guard_cho_ca_man_hinh,
)
from clinicai.api.v1.health import router as health_router
from clinicai.api.v1.patients import router as patients_router
from clinicai.api.v1.routers.audit_log import router as audit_log_router
from clinicai.api.v1.routers.auth import router as auth_router
from clinicai.api.v1.routers.booking import router as booking_router
from clinicai.api.v1.routers.brief import router as brief_router
from clinicai.api.v1.routers.cashier import router as cashier_router
from clinicai.api.v1.routers.catalog import router as catalog_router
from clinicai.api.v1.routers.clinic_config import router as clinic_config_router
from clinicai.api.v1.routers.clinical_forms import router as clinical_forms_router
from clinicai.api.v1.routers.clinical_records import (
    router as clinical_records_router,
)
from clinicai.api.v1.routers.clinical_sign import router as clinical_sign_router
from clinicai.api.v1.routers.config import router as config_router
from clinicai.api.v1.routers.consent import router as consent_router
from clinicai.api.v1.routers.console import router as console_router
from clinicai.api.v1.routers.cskh import router as cskh_router
from clinicai.api.v1.routers.dispatch import router as dispatch_router
from clinicai.api.v1.routers.display import router as display_router
from clinicai.api.v1.routers.episodes import router as episodes_router
from clinicai.api.v1.routers.events import router as events_router
from clinicai.api.v1.routers.identity import router as identity_router
from clinicai.api.v1.routers.lab import router as lab_router
from clinicai.api.v1.routers.ops import router as ops_router
from clinicai.api.v1.routers.orchestrator import router as orchestrator_router
from clinicai.api.v1.routers.payment import router as payment_router
from clinicai.api.v1.routers.pharmacy import router as pharmacy_router
from clinicai.api.v1.routers.queue import router as queue_router
from clinicai.api.v1.routers.reports import router as reports_router
from clinicai.api.v1.routers.scheduling import router as scheduling_router
from clinicai.api.v1.routers.service_log import router as service_log_router
from clinicai.api.v1.routers.staff import router as staff_router
from clinicai.api.v1.routers.tools import router as tools_router
from clinicai.api.v1.routers.ultrasound import router as ultrasound_router
from clinicai.api.v1.routers.visit_progress import (
    router as visit_progress_router,
)
from clinicai.api.v1.routers.voice import router as voice_router
from clinicai.api.v1.routers.work_items import router as work_items_router
from clinicai.core.change_broker import ChangeBroker
from clinicai.core.database import close_pool, create_pool
from clinicai.core.exceptions import ClinicAIBaseException
from clinicai.core.logging import setup_logging
from clinicai.core.sentry import init_sentry
from clinicai.llm.anthropic_client import AnthropicClient
from clinicai.orchestrator.checkpointer import make_checkpointer
from clinicai.orchestrator.service import OrchestratorService
from clinicai.voice.transcribe import PhoWhisperTranscriber

# Initialize structured JSON logging
setup_logging()
# Initialize Sentry APM (reads SENTRY_DSN; no-op if unset)
init_sentry()

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the asyncpg pool + LangGraph checkpointer over the app lifetime."""
    app.state.db_pool = await create_pool()
    # Bộ nhận thay đổi cho màn hình (thay Supabase Realtime). Nó tự nối lại khi
    # rớt và KHÔNG được phép làm chết app khi database chưa sẵn sàng — mất nó
    # thì màn hình rơi về nhịp làm mới dự phòng, chứ không ai đăng nhập hỏng.
    app.state.change_broker = ChangeBroker(os.environ["DATABASE_URL"])
    await app.state.change_broker.start()
    try:
        async with AsyncExitStack() as stack:
            checkpointer = await stack.enter_async_context(make_checkpointer())

            llm_client = AnthropicClient()
            stack.push_async_callback(llm_client.close)
            app.state.llm_client = llm_client

            # Voice transcriber (on-prem PhoWhisper). Construction nhẹ — model nạp
            # lazy ở lần transcribe đầu, nên app boot được kể cả khi chưa cài model.
            app.state.voice_transcriber = PhoWhisperTranscriber()

            default_location_id_env = os.environ.get("DEFAULT_LOCATION_ID")
            scheduling_location_id: UUID | None = (
                UUID(default_location_id_env) if default_location_id_env else None
            )

            app.state.orchestrator_service = OrchestratorService(
                checkpointer=checkpointer,
                llm_client=llm_client,
                scheduling_pool=app.state.db_pool,
                scheduling_location_id=scheduling_location_id,
                lab_triage_pool=app.state.db_pool,
                task_manager_pool=app.state.db_pool,
            )

            logger.info("app_startup_complete")
            yield
            logger.info("app_shutdown_starting")
    finally:
        await app.state.change_broker.stop()
        await close_pool(app.state.db_pool)


app = FastAPI(
    title="ClinicAI",
    description="AI-powered clinic management for Dr4women",
    version="0.1.0",
    lifespan=lifespan,
)

# --- Middleware stack ---
#
# REGISTERED IN REVERSE, ON PURPOSE. Starlette's add_middleware does
# `user_middleware.insert(0, …)`, so the LAST call ends up OUTERMOST. Written in
# the intuitive order, this block produced the exact opposite stack at runtime:
# Timing ran *inside* the API-key gate (blind to the rejected floods it exists to
# show) and Request-ID ran innermost (so no 401/403/503 ever carried the header).
# See api/middleware.py for the full account; test_middleware_order pins it.
#
# Resulting stack, outermost → innermost:
#   RequestIdMiddleware → TimingMiddleware → api_key_middleware → DbErrorMiddleware
app.add_middleware(DbErrorMiddleware)  # innermost: DB error → 503, still timed
app.middleware("http")(api_key_middleware)  # gate anonymous callers (api.auth)
app.add_middleware(TimingMiddleware)  # outside the gate: rejections are data too
app.add_middleware(RequestIdMiddleware)  # outermost: every response gets an id

# --- Runaway-client guard -----------------------------------------------------
#
# Applied to every AUTHENTICATED router below, and to none of the three that are
# deliberately open (health probes, the national ward list, the waiting-room TV
# config). It counts requests per staff member, warns at 60/minute and refuses
# past 120 — see api/runaway_guard.py for why the ceiling is set so far above
# human use rather than close to it.
#
# One list, in one file, because the thing it measures is per PERSON: scattering
# `Depends(runaway_guard)` across endpoints would work, but the next endpoint
# somebody adds would silently sit outside the count.
_GUARDED = [Depends(runaway_guard)]

app.include_router(health_router)
# ĐĂNG NHẬP: endpoint DUY NHẤT không đòi token, vì nó là nơi cấp token.
# Cũng vì thế nó là endpoint duy nhất người lạ gọi được — chống dò mật khẩu
# nằm trong auth_service (đếm lần sai + khoá tạm, lưu ở database).
#
# KHÔNG gắn _GUARDED: runaway_guard đếm theo NHÂN VIÊN, mà ở đây chưa biết
# người gọi là ai — đó chính là việc endpoint này đang làm.
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(
    identity_router,
    prefix="/api/v1",
    tags=["identity"],
    # Bộ đếm bản KHÔNG chặn vai DISPLAY: `/api/v1/me` phải trả lời được cho tài
    # khoản màn hình TV, nếu không nó đăng nhập xong bị đá về trang đăng nhập.
    dependencies=[Depends(runaway_guard_cho_ca_man_hinh)],
)
# Dòng sự kiện cho màn hình (thay Supabase Realtime).
#
# Trình duyệt KHÔNG gọi thẳng vào đây. `EventSource` không đặt được header, nên
# nó gọi route Next `/api/events/stream`, và route ấy — chạy trên máy chủ — gắn
# Bearer token cùng X-API-Key rồi truyền dòng về. Nhờ vậy cửa gác ở đây y hệt
# mọi endpoint khác, không phải mở một lối riêng.
#
# ĐÃ CÂN NHẮC VÀ BỎ: cho token đi qua query string. Làm thế là ghi token vào
# log truy cập của mọi proxy trên đường — một thứ đọc được, sống lâu, và đủ để
# đóng giả người dùng.
app.include_router(
    events_router, prefix="/api/v1", tags=["events"], dependencies=_GUARDED
)
app.include_router(
    queue_router, prefix="/api/v1", tags=["queue"], dependencies=_GUARDED
)
# Bảng điều khiển chủ sản phẩm — router tự từ chối khi APP_ENV=production.
app.include_router(
    console_router, prefix="/api/v1", tags=["console"], dependencies=_GUARDED
)
# TRƯỚC patients_router. `patients.py` dùng `{id:uuid}` nên literal không bị
# nuốt, nhưng lần trước /appointments/policy đã biến mất đúng theo kiểu này —
# đăng ký đường dẫn cụ thể trước đường dẫn có tham số không tốn gì.
app.include_router(
    consent_router, prefix="/api/v1", tags=["consent"], dependencies=_GUARDED
)
app.include_router(patients_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(
    staff_router, prefix="/api/v1", tags=["staff"], dependencies=_GUARDED
)
app.include_router(
    scheduling_router, prefix="/api/v1", tags=["scheduling"], dependencies=_GUARDED
)
app.include_router(
    payment_router, prefix="/api/v1", tags=["payment"], dependencies=_GUARDED
)
app.include_router(
    cashier_router, prefix="/api/v1", tags=["cashier"], dependencies=_GUARDED
)
app.include_router(
    reports_router, prefix="/api/v1", tags=["reports"], dependencies=_GUARDED
)
app.include_router(
    audit_log_router, prefix="/api/v1", tags=["audit-log"], dependencies=_GUARDED
)
app.include_router(
    clinic_config_router,
    prefix="/api/v1",
    tags=["clinic-config"],
    dependencies=_GUARDED,
)
app.include_router(
    episodes_router, prefix="/api/v1", tags=["episodes"], dependencies=_GUARDED
)
app.include_router(
    work_items_router, prefix="/api/v1", tags=["work-items"], dependencies=_GUARDED
)
app.include_router(tools_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(orchestrator_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(brief_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(catalog_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1", tags=["ops"], dependencies=_GUARDED)
app.include_router(lab_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(
    ultrasound_router, prefix="/api/v1", tags=["ultrasound"], dependencies=_GUARDED
)
app.include_router(
    clinical_forms_router,
    prefix="/api/v1",
    tags=["clinical-forms"],
    dependencies=_GUARDED,
)
app.include_router(
    clinical_records_router,
    prefix="/api/v1",
    tags=["clinical-records"],
    dependencies=_GUARDED,
)
app.include_router(cskh_router, prefix="/api/v1", tags=["cskh"], dependencies=_GUARDED)
app.include_router(
    pharmacy_router, prefix="/api/v1", tags=["pharmacy"], dependencies=_GUARDED
)
app.include_router(
    booking_router, prefix="/api/v1", tags=["booking"], dependencies=_GUARDED
)
app.include_router(
    config_router, prefix="/api/v1", tags=["config"], dependencies=_GUARDED
)
app.include_router(
    dispatch_router, prefix="/api/v1", tags=["dispatch"], dependencies=_GUARDED
)
app.include_router(
    clinical_sign_router, prefix="/api/v1", tags=["clinical"], dependencies=_GUARDED
)
app.include_router(
    service_log_router, prefix="/api/v1", tags=["service-log"], dependencies=_GUARDED
)
app.include_router(
    visit_progress_router,
    prefix="/api/v1",
    tags=["visit-progress"],
    dependencies=_GUARDED,
)
app.include_router(voice_router, prefix="/api/v1", dependencies=_GUARDED)
app.include_router(display_router, prefix="/api/v1", tags=["display"])


@app.exception_handler(asyncpg.exceptions.ExclusionViolationError)
async def exclusion_violation_handler(
    request: Request, exc: asyncpg.exceptions.ExclusionViolationError
) -> JSONResponse:
    """Global handler for database exclusion violation errors (HTTP 409).

    MỘT CÂU CHO MỌI RÀNG BUỘC LÀ MỘT CÂU SAI CHO GẦN HẾT SỐ ĐÓ.

    Handler này từng luôn trả "Lịch hẹn xung đột khung giờ với appointment
    khác". Đúng cho `appointment_no_doctor_overlap`, và sai cho ba ràng buộc
    EXCLUDE còn lại — trong đó có hai ràng buộc LUẬT ĐẶT LỊCH. Trưởng ca lưu một
    luật cho BS Thành nhận về một câu nói về LỊCH HẸN, rồi đi tìm một lịch hẹn
    không tồn tại. Chúng tôi mất một buổi vì đúng câu này.

    Tên ràng buộc là thứ duy nhất phân biệt được, nên nó quyết định câu trả lời.
    Ràng buộc lạ thì nói thẳng là không nhận ra, kèm tên — mơ hồ mà đúng còn hơn
    cụ thể mà bịa.
    """
    constraint = getattr(exc, "constraint_name", None) or ""
    # `appointment_no_doctor_overlap` KHÔNG còn trong danh sách này.
    #
    # Nó bị DROP ở một migration cũ và chưa ai dựng lại — kiểm bằng pg_constraint
    # ngày 05/08: chỉ còn hai ràng buộc EXCLUDE, cả hai trên bảng override. Giữ
    # một mục cho ràng buộc không tồn tại làm người đọc tin rằng có lưới ở đó.
    #
    # Và nó KHÔNG nên được dựng lại: EXCLUDE cấm MỌI cặp chồng lấn, tức trần
    # bằng 1, trong khi luật của phòng khám là 2 chỗ đặt + 1 vãng lai mỗi bác sĩ
    # mỗi khung (clinic_policy.py:31-32) — ba lịch cùng bác sĩ cùng giờ là hợp
    # lệ. Trần theo số đếm phải là trigger, và nó đã có: enforce_slot_capacity.
    known = {
        "slot_override_no_overlap": (
            "Đã có một điều chỉnh khác phủ khung giờ này — sửa hoặc xoá nó trước."
        ),
        "doctor_override_no_overlap": (
            "Đã có một luật khác phủ khung giờ này — sửa hoặc xoá nó trước."
        ),
    }
    message = known.get(
        constraint,
        "Bản ghi xung đột với một bản ghi khác"
        + (f" (ràng buộc {constraint})" if constraint else "")
        + ".",
    )
    # `reason`, not `message`: core.logging treats a structured `message` field
    # as patient content and replaces it with [REDACTED]. That is right for a
    # field that can carry a note, and wrong here — it blanked the one sentence
    # that says which rule fired, so every domain error logged as
    # {"error_code": …, "message": "[REDACTED]"} and told an operator nothing.
    logger.warning(
        "exclusion_violation",
        reason=message,
        constraint=constraint,
    )
    return JSONResponse(
        status_code=409,
        content={"error": "CONFLICT_ERROR", "message": message},
    )


@app.exception_handler(asyncpg.exceptions.UniqueViolationError)
async def unique_violation_handler(
    request: Request, exc: asyncpg.exceptions.UniqueViolationError
) -> JSONResponse:
    """Global handler for database unique constraint violations (HTTP 409).

    MẶC ĐỊNH VẪN MƠ HỒ, CÓ CHỦ Ý. Tên một ràng buộc UNIQUE thường lộ cấu trúc
    bảng và đôi khi cả cách định danh (``staff_phone_key`` nói rằng nhân viên
    được phân biệt bằng số điện thoại). Khác với ràng buộc chồng lấn — nơi chi
    tiết giúp người dùng xử lý được — ở đây chi tiết không giúp thêm gì.

    NGOẠI LỆ: ràng buộc nào mà người dùng CÓ THỂ tự xử lý thì được một câu riêng.
    ``uq_appointment_patient_slot_live`` chỉ bắn khi hai request thật sự đồng
    thời cùng đặt một bệnh nhân vào một giờ — tức là cú bấm hai lần đã lọt qua
    cả chốt ở trình duyệt lẫn Idempotency-Key. Người bấm cần biết lịch ĐÃ có,
    không cần biết tên chỉ mục.
    """
    constraint = getattr(exc, "constraint_name", None) or ""
    known = {
        "uq_appointment_patient_slot_live": (
            "Bệnh nhân này đã có lịch hẹn vào đúng giờ đó. Lần bấm trước đã "
            "thành công — không cần đặt lại. Muốn đổi giờ thì vào Quản lý "
            "khách hàng → Lịch hẹn sắp tới."
        ),
    }
    message = known.get(constraint, "Resource already exists")
    logger.warning(
        "unique_violation",
        reason=message,
        constraint=constraint,
    )
    return JSONResponse(
        status_code=409,
        content={
            "error": "CONFLICT_ERROR",
            "message": message,
        },
    )


@app.exception_handler(ClinicAIBaseException)
async def clinicai_exception_handler(
    request: Request, exc: ClinicAIBaseException
) -> JSONResponse:
    """Global handler for all custom ClinicAI exceptions."""
    # Free text still goes through the text-level scrubber (phones, emails,
    # bearer tokens), so a message that did pick up a phone number stays safe.
    logger.warning(
        "clinicai_exception",
        error_code=exc.error_code,
        reason=exc.message,
        status_code=exc.status_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.message},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global handler for all unhandled exceptions."""
    # Capture full stack trace in structured JSON logs without leaking it to clients
    logger.exception(
        "unhandled_exception",
        reason=str(exc),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred.",
        },
    )
