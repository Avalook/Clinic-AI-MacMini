"""Bảng điều phối của Trưởng ca (Notion §4).

Đọc mở cho các vai vận hành — Lễ tân và Điều dưỡng cũng cần biết bệnh nhân đang
ở đâu để gọi đúng người. GHI thì chỉ Trưởng ca và Quản lý: chuyển phòng hay đổi
tuyến là quyết định điều phối, không phải thao tác của người trực trạm.

Màn TV phòng chờ có đường riêng, KHÔNG có dữ liệu bệnh nhân: yêu cầu khách hàng
nói rõ *"TV công cộng chỉ hiển thị số thứ tự và thông tin đã được che bớt"* và
*"tài khoản dùng cho TV chỉ có quyền xem hàng đợi"*. Nên nó trả về số thứ tự,
không trả tên.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    require_role,
)
from clinicai.core.database import get_db_pool
from clinicai.services.dispatch_service import DispatchService

router = APIRouter()

# Điều phối là quyết định của ca trực.
_DISPATCH_WRITE = require_role(ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT)
# Quầy tiếp nhận: Lễ tân là người bấm, Trưởng ca/Quản lý bấm hộ được.
_RECEPTION_GUARD = require_role(
    ClinicRole.RECEPTION, ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT
)


# ── Đọc ────────────────────────────────────────────────────────────────────


@router.get("/dispatch/overview")
async def overview(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Toàn cảnh: mỗi bệnh nhân đang trong phòng khám là một dòng."""
    svc = DispatchService(pool)
    return {
        "ok": True,
        "patients": await svc.overview(clinic_id=identity.clinic_id),
        # Chỉ phòng của CƠ SỞ người đang đứng — xem ghi chú ở _STATIONS_SQL.
        "rooms": await svc.stations(
            clinic_id=identity.clinic_id, location_id=identity.location_id
        ),
    }


@router.get("/dispatch/alerts")
async def alerts(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Cảnh báo vận hành, đã xếp theo mức độ."""
    items = await DispatchService(pool).alerts(clinic_id=identity.clinic_id)
    return {"ok": True, "items": items}


@router.get("/dispatch/routes")
async def routes(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Các tuyến điều phối đã cấu hình."""
    items = await DispatchService(pool).routes(clinic_id=identity.clinic_id)
    return {"ok": True, "items": items}


@router.get("/dispatch/history")
async def history(
    limit: int = Query(default=200, ge=1, le=1000),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Nhật ký điều phối: ai chuyển ai, từ đâu sang đâu, vì sao."""
    items = await DispatchService(pool).history(
        clinic_id=identity.clinic_id, limit=limit
    )
    return {"ok": True, "items": items}


@router.get("/dispatch/tv")
async def tv_board(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Dữ liệu TV phòng chờ — CHỈ số thứ tự, không tên, không dịch vụ.

    Che ở BACKEND chứ không ở giao diện: một màn hình công cộng mà dữ liệu nhạy
    cảm vẫn đi qua đường mạng thì chỉ cần mở công cụ nhà phát triển là đọc được.
    """
    svc = DispatchService(pool)
    rooms = await svc.stations(
        clinic_id=identity.clinic_id, location_id=identity.location_id
    )
    patients = await svc.overview(clinic_id=identity.clinic_id)

    board = []
    for r in rooms:
        if not r["show_on_tv"]:
            continue
        here = [p for p in patients if p["room_code"] == r["code"]]
        here.sort(key=lambda p: -p["wait_minutes"])
        board.append(
            {
                "code": r["code"],
                "name": r["name"],
                "serving": r["serving"],
                "waiting": r["waiting"],
                # Số thứ tự thôi. `queue_number` do Lễ tân cấp lúc check-in.
                "queue": [p["queue_number"] for p in here if p["queue_number"]],
            }
        )
    return {"ok": True, "rooms": board}


# ── Ghi ────────────────────────────────────────────────────────────────────


class MoveRequest(BaseModel):
    """Chuyển bệnh nhân sang bước/phòng khác."""

    visit_id: UUID
    node_code: str = Field(min_length=1, max_length=64)
    room_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


@router.post("/dispatch/move", status_code=201)
async def move(
    body: MoveRequest,
    identity: StaffIdentity = Depends(_DISPATCH_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Sang bước khác, hoặc đổi phòng trong cùng một bước."""
    return await DispatchService(pool).move(
        identity=identity,
        visit_id=str(body.visit_id),
        node_code=body.node_code,
        room_id=str(body.room_id) if body.room_id else None,
        reason=body.reason,
    )


class TransferRoomRequest(BaseModel):
    """Đổi phòng trong CÙNG một bước — SA1 sang SA2."""

    visit_id: UUID
    node_code: str = Field(min_length=1, max_length=64)
    room_id: UUID
    # Cân tải là một quyết định, và người nhận ca sau cần biết vì sao.
    reason: str = Field(min_length=1, max_length=500)


@router.post("/dispatch/transfer-room", status_code=201)
async def transfer_room(
    body: TransferRoomRequest,
    identity: StaffIdentity = Depends(_DISPATCH_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chuyển phòng. Đồng hồ chờ KHÔNG được đặt lại — xem move_visit_to_station."""
    return await DispatchService(pool).move(
        identity=identity,
        visit_id=str(body.visit_id),
        node_code=body.node_code,
        room_id=str(body.room_id),
        reason=body.reason,
        event_type="dispatch.transfer_room",
    )


class ApplyRouteRequest(BaseModel):
    visit_id: UUID
    template_code: str = Field(min_length=1, max_length=64)
    is_exception: bool = False
    reason: str | None = Field(default=None, max_length=500)


@router.post("/dispatch/route", status_code=201)
async def apply_route(
    body: ApplyRouteRequest,
    identity: StaffIdentity = Depends(_DISPATCH_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chọn tuyến sau khi bác sĩ khám. Đổi giữa chừng thì bắt buộc lý do."""
    return await DispatchService(pool).apply_route(
        identity=identity,
        visit_id=str(body.visit_id),
        template_code=body.template_code,
        is_exception=body.is_exception,
        reason=body.reason,
    )


# ── Trưởng ca GỌI bộ phận ──────────────────────────────────────────────────
#
# Nửa còn thiếu của màn cảnh báo: nó đã nói được "SA1 đang tắc" nhưng không nói
# được VỚI AI. Xem services/thong_bao_service.py.


class GoiBoPhanRequest(BaseModel):
    # Vai được gọi khai TƯỜNG MINH, không suy từ phòng. Đánh thức nhầm bộ phận
    # lúc đang tắc thì tệ hơn là bắt trưởng ca chọn một lần.
    vai_nhan: str = Field(min_length=1, max_length=40)
    tieu_de: str = Field(min_length=1, max_length=200)
    noi_dung: str = Field(min_length=1, max_length=1000)
    # Khoá chống gọi trùng: cùng nguồn + cùng vai mà cái cũ chưa xử lý thì
    # không tạo thêm. Thường là mã phòng.
    nguon_id: str | None = Field(default=None, max_length=100)
    muc_do: Literal["KHAN", "THUONG"] = "KHAN"
    duong_dan: str | None = Field(default=None, max_length=300)


@router.post("/dispatch/alerts/call", status_code=201)
async def call_department(
    body: GoiBoPhanRequest,
    identity: StaffIdentity = Depends(_DISPATCH_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gọi một bộ phận về một cảnh báo. Bấm lại khi chưa ai xử lý: không nhân đôi."""
    from clinicai.services.thong_bao_service import ThongBaoService

    return await ThongBaoService(pool).goi(
        identity=identity,
        vai_nhan=body.vai_nhan,
        tieu_de=body.tieu_de,
        noi_dung=body.noi_dung,
        nguon_id=body.nguon_id,
        muc_do=body.muc_do,
        duong_dan=body.duong_dan,
    )


@router.get("/thong-bao")
async def my_notifications(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thông báo chưa xử lý dành cho vai của tôi. MỌI vai đều đọc được của mình."""
    from clinicai.services.thong_bao_service import ThongBaoService

    return {"items": await ThongBaoService(pool).cua_toi(identity=identity)}


class DaXuLyRequest(BaseModel):
    ghi_chu: str | None = Field(default=None, max_length=500)


@router.post("/thong-bao/{thong_bao_id:uuid}/da-xu-ly", status_code=201)
async def resolve_notification(
    thong_bao_id: UUID,
    body: DaXuLyRequest,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Bên nhận đóng việc. Trả về thời gian phản hồi tính bằng giây."""
    from clinicai.services.thong_bao_service import ThongBaoService

    return await ThongBaoService(pool).da_xu_ly(
        identity=identity, thong_bao_id=str(thong_bao_id), ghi_chu=body.ghi_chu
    )


# ── Quầy Lễ tân: đối soát và đóng lượt ─────────────────────────────────────
#
# Đọc mở cho Lễ tân (đây là màn của họ); đóng lượt cũng là việc của Lễ tân, nên
# quyền GHI ở đây rộng hơn phần điều phối bên trên.


@router.get("/reception/checkout/ton-dong")
async def checkout_stale(
    identity: StaffIdentity = Depends(_RECEPTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lượt khám còn mở từ những ngày trước — 18 dòng không ai thấy.

    Đường literal đặt TRƯỚC `/reception/checkout/{visit_id:uuid}` không phải vì
    thứ tự khai (bộ chuyển đổi `{visit_id:uuid}` đã chặn chuyện nuốt đường), mà
    để người đọc thấy hai đường này cạnh nhau.
    """
    from clinicai.services.checkout_service import CheckoutService

    return {
        "ok": True,
        "items": await CheckoutService(pool).stale_list(identity=identity),
    }


@router.get("/reception/checkout/chi-tiet/{visit_id:uuid}")
async def checkout_chi_tiet(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_RECEPTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Toàn cảnh một lượt khám để đối soát trước khi đóng.

    Dịch vụ đã làm · các khoản đã thu · hồ sơ sẽ trả · theo dõi sau khám · dòng
    thời gian. Xem `CheckoutService.chi_tiet` để biết mục nào có dữ liệu thật và
    mục nào chưa.
    """
    from clinicai.services.checkout_service import CheckoutService

    return await CheckoutService(pool).chi_tiet(
        identity=identity, visit_id=str(visit_id)
    )


@router.get("/reception/checkout")
async def checkout_list(
    identity: StaffIdentity = Depends(_RECEPTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lượt khám hôm nay chưa đóng, kèm vướng mắc của từng lượt."""
    from clinicai.services.checkout_service import CheckoutService

    items = await CheckoutService(pool).pending_list(identity=identity)
    return {"ok": True, "items": items}


# `{visit_id:uuid}`, KHÔNG phải `{visit_id}` trần: đường literal
# "/reception/checkout" ngay trên sẽ bị nuốt — đúng như /appointments/policy đã
# bị nuốt suốt một thời gian dài mà không ai thấy.
@router.get("/reception/checkout/{visit_id:uuid}")
async def checkout_readiness(
    visit_id: UUID,
    identity: StaffIdentity = Depends(_RECEPTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lượt khám này đóng được chưa, và còn vướng gì."""
    from clinicai.services.checkout_service import CheckoutService

    return await CheckoutService(pool).readiness(
        identity=identity, visit_id=str(visit_id)
    )


class CheckoutRequest(BaseModel):
    visit_id: UUID
    # Khách về giữa chừng. Lý do BẮT BUỘC khi bật — xem checkout_service.close.
    incomplete: bool = False
    incomplete_reason: str | None = Field(default=None, max_length=500)
    # Còn vướng mà vẫn muốn đóng thì phải nói vì sao. Trống = chỉ đóng được khi
    # sạch vướng mắc.
    override_reason: str | None = Field(default=None, max_length=500)


@router.post("/reception/checkout", status_code=201)
async def checkout(
    body: CheckoutRequest,
    identity: StaffIdentity = Depends(_RECEPTION_GUARD),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đóng lượt khám.

    Đóng bình thường KHÔNG đụng `visit.status` — đó là khoá hồ sơ bệnh án, việc
    của bác sĩ. Chỉ nhánh `incomplete=True` (khách về giữa chừng) mới ghi
    `INCOMPLETE`, và đó là trạng thái KHÔNG-CUỐI: bác sĩ vẫn ký lên FINALIZED
    được sau. Xem checkout_service.
    """
    from clinicai.services.checkout_service import CheckoutService

    return await CheckoutService(pool).close(
        identity=identity,
        visit_id=str(body.visit_id),
        override_reason=body.override_reason,
        incomplete=body.incomplete,
        incomplete_reason=body.incomplete_reason,
    )


class ThresholdRequest(BaseModel):
    """``room_id`` để trống = ngưỡng mặc định của phòng khám."""

    room_id: UUID | None = None
    wait_minutes: int = Field(ge=1, le=480)
    max_waiting: int = Field(ge=1, le=200)


@router.put("/dispatch/threshold")
async def set_threshold(
    body: ThresholdRequest,
    identity: StaffIdentity = Depends(_DISPATCH_WRITE),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Ngưỡng cảnh báo, theo từng phòng hoặc mặc định cả phòng khám."""
    return await DispatchService(pool).set_threshold(
        identity=identity,
        room_id=str(body.room_id) if body.room_id else None,
        wait_minutes=body.wait_minutes,
        max_waiting=body.max_waiting,
    )
