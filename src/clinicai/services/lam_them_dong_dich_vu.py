"""ĐÓNG DỊCH VỤ LÀM THÊM NGAY TẠI QUẦY khi Hoàn tất kết quả (Tuyền 01/10/2026).

Khách được tick "+ Nước tiểu" ở Tiếp đón / Đo sinh hiệu, người đứng bàn thử que
rồi ghi kết quả ngay tại đó. Quy ước Tuyền chốt (phương án A): **Hoàn tất phiếu
kết quả ở quầy = dịch vụ làm xong** — chỉ định rời hàng chờ phòng, Hành trình
ghi "xong" kèm người bấm; Sửa lại / Hoàn tác kết quả thì dịch vụ trở về chờ làm.

KHÔNG GHI TRẠNG THÁI TRỰC TIẾP. Đóng = lệnh `StartService` rồi `CompleteService`
CÓ SẴN của module Thực hiện (cùng quyền, cùng khoá lượt, cùng sự kiện
`service.started` / `service.completed`), mở lại = lệnh `hoan_tac_xong_tai_quay`
của chính module ấy. Phần ở đây chỉ QUYẾT ĐỊNH có đóng được không và nói lý do:

  * cửa tiền (FinanceGate) — dây ``thu_truoc_khi_lam`` BẬT mà chưa thu và lượt
    không tick "Làm trước – thu sau" thì KHÔNG đóng, báo đúng câu của phòng;
  * chưa xếp phòng (tự xếp chạy sau khi đủ điều kiện) — báo rõ, có nút đóng lại;
  * khách đang làm dịch vụ khác / người bấm thiếu quyền — báo rõ, phiếu vẫn
    hoàn tất bình thường (kết quả là sự thật độc lập, không cuộn lại).

Chỉ chỉ định LÀM THÊM TẠI QUẦY (`service_order.nguon_lam_them`); chỉ định của bác
sĩ vẫn đi đường phòng.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can_o_phong_nao_do
from clinicai.services import finance_gate
from clinicai.services.finance_gate import can_start
from clinicai.services.service_execution_service import (
    GHI_CHU_TAI_QUAY,
    QUYEN_BAT_DAU,
    QUYEN_XONG,
    ServiceExecutionService,
)

CAU_CHUA_XEP_PHONG = (
    "Dịch vụ chưa được xếp phòng nên CHƯA đóng. Khi đã xếp phòng, bấm"
    " [Đóng dịch vụ] ở khung này."
)
CAU_THIEU_QUYEN = (
    "Bạn chưa có quyền bắt đầu / đóng dịch vụ nên dịch vụ CHƯA đóng — nhờ người"
    " có quyền bấm [Đóng dịch vụ] hoặc Xong ở phòng. Kết quả đã lưu."
)

_SQL_DON = (
    "SELECT o.nguon_lam_them, o.selection_status, o.routing_status,"
    "       o.routing_revision, o.execution_status, o.execution_revision,"
    "       o.visit_id::text AS visit_id"
    "  FROM service_order o"
    " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
)


async def _chan_dong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    order_id: str,
    don: asyncpg.Record,
) -> dict[str, str] | None:
    """Vì sao CHƯA đóng được — None = đóng được. Hàm đọc, dùng chung cho nút
    [Đóng dịch vụ] hiện ở màn và cho lệnh đóng (một luật, hai nơi dùng)."""
    if not don["nguon_lam_them"]:
        return {"vi_sao": "khong_phai_lam_them", "cau": "Không phải dịch vụ làm thêm."}
    if don["selection_status"] != "SELECTED":
        return {"vi_sao": "chua_chon", "cau": "Khách chưa chọn làm dịch vụ này."}
    if (don["execution_status"] or "PENDING") != "PENDING":
        return {
            "vi_sao": "khong_cho_lam",
            "cau": "Dịch vụ không ở trạng thái chờ làm.",
        }
    # CỬA TIỀN trước cửa phòng: chưa thu thì tự xếp phòng cũng chưa chạy — nói
    # "chưa thu tiền" mới là câu đúng, "chưa xếp phòng" là câu lạc đề.
    tien = await can_start(conn, identity.clinic_id, order_id)
    if tien is None or not tien.duoc_lam:
        return {"vi_sao": "chua_thu", "cau": finance_gate.cau_chan_lam(tien)}
    if don["routing_status"] != "ASSIGNED":
        return {"vi_sao": "chua_xep_phong", "cau": CAU_CHUA_XEP_PHONG}
    if not (
        await can_o_phong_nao_do(conn, identity, QUYEN_BAT_DAU)
        and await can_o_phong_nao_do(conn, identity, QUYEN_XONG)
    ):
        return {"vi_sao": "khong_du_quyen", "cau": CAU_THIEU_QUYEN}
    return None


async def chan_dong_neu_co(
    conn: asyncpg.Connection, identity: StaffIdentity, order_id: str
) -> dict[str, str] | None:
    """Cho màn: chỉ định quầy chờ làm mà CHƯA đóng được thì vì sao (else None)."""
    don = await conn.fetchrow(_SQL_DON, identity.clinic_id, order_id)
    if don is None:
        return {"vi_sao": "khong_co", "cau": "Không tìm thấy chỉ định."}
    return await _chan_dong(conn, identity, order_id, don)


async def dong_tai_quay(
    pool: asyncpg.Pool, *, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """Đóng dịch vụ làm thêm vì kết quả đã Hoàn tất ở quầy.

    Trả ``{da_dong, vi_sao, cau}`` (cùng khuôn với đường đóng của phòng). Không
    ném lỗi nghiệp vụ: phiếu đã hoàn tất là sự thật độc lập.
    """
    async with pool.acquire() as conn:
        don = await conn.fetchrow(_SQL_DON, identity.clinic_id, order_id)
        if don is None or not don["nguon_lam_them"]:
            return {"da_dong": False, "vi_sao": "khong_phai_lam_them", "cau": None}
        if don["execution_status"] == "COMPLETED":
            return {"da_dong": True, "da_xong_san": True}
        chan = await _chan_dong(conn, identity, order_id, don)
    if chan is not None:
        return {"da_dong": False, **chan}
    svc = ServiceExecutionService(pool)
    rev = int(don["execution_revision"] or 0)
    try:
        bd = await svc.bat_dau(
            order_id=order_id,
            expected_execution_revision=rev,
            expected_routing_revision=int(don["routing_revision"] or 0),
            identity=identity,
            idempotency_key=f"quay-bat-dau-{order_id}-{rev}",
        )
        await svc.xong(
            order_id=order_id,
            attempt_id=bd["attempt_id"],
            expected_execution_revision=int(bd["execution_revision"]),
            identity=identity,
            idempotency_key=f"quay-xong-{order_id}-{bd['attempt_id']}",
            ghi_chu=GHI_CHU_TAI_QUAY,
        )
    except SafetyGateError:
        return {"da_dong": False, "vi_sao": "khong_du_quyen", "cau": CAU_THIEU_QUYEN}
    except ConflictError as loi:
        return {"da_dong": False, "vi_sao": "xung_dot", "cau": str(loi)}
    return {"da_dong": True}


async def hoan_tac_tai_quay(
    pool: asyncpg.Pool,
    *,
    order_id: str,
    identity: StaffIdentity,
    nguon: str = "hoan_tac",
) -> dict[str, Any]:
    """Mở lại dịch vụ quầy đã đóng (lệnh của module Thực hiện). Ném lỗi nghiệp
    vụ như mọi lệnh — nút [Hoàn tác] cần biết vì sao không được."""
    async with pool.acquire() as conn:
        don = await conn.fetchrow(_SQL_DON, identity.clinic_id, order_id)
    if don is None:
        from clinicai.core.exceptions import ValidationError

        raise ValidationError("Không tìm thấy chỉ định này.")
    return await ServiceExecutionService(pool).hoan_tac_xong_tai_quay(
        order_id=order_id,
        expected_execution_revision=int(don["execution_revision"] or 0),
        identity=identity,
        idempotency_key=f"quay-mo-lai-{order_id}-{don['execution_revision']}",
        nguon=nguon,
    )


async def mo_lai_neu_quay_da_dong(
    pool: asyncpg.Pool, *, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """Sửa lại kết quả: nếu dịch vụ do QUẦY đóng thì mở lại (None-op nếu không).

    Không ném: Sửa lại vẫn mở được phiếu dù người bấm thiếu quyền đóng/mở dịch vụ
    (khi đó dịch vụ giữ nguyên "xong" và màn nói rõ)."""
    async with pool.acquire() as conn:
        don = await conn.fetchrow(_SQL_DON, identity.clinic_id, order_id)
        da_quay = don is not None and bool(
            don["nguon_lam_them"] and don["execution_status"] == "COMPLETED"
        )
        lan = (
            await conn.fetchval(
                "SELECT ghi_chu FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY attempt_no DESC LIMIT 1",
                identity.clinic_id,
                order_id,
            )
            if da_quay
            else None
        )
    if not da_quay or lan != GHI_CHU_TAI_QUAY:
        return {"da_mo_lai": False}
    try:
        await hoan_tac_tai_quay(
            pool, order_id=order_id, identity=identity, nguon="sua_lai"
        )
    except (SafetyGateError, ConflictError) as loi:
        return {"da_mo_lai": False, "cau": str(loi)}
    return {"da_mo_lai": True}


async def dong_lai_sau_huy_sua(
    pool: asyncpg.Pool, *, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """[Huỷ sửa]: đóng lại dịch vụ CHỈ KHI chính lần Sửa lại đã mở nó (không đóng
    lại thứ người ta vừa [Hoàn tác] tường minh)."""
    async with pool.acquire() as conn:
        la_sua = await conn.fetchval(
            "SELECT o.execution_status = 'PENDING'"
            "   AND a.status = 'INTERRUPTED'"
            "   AND a.interruption_reason_code = 'RESULT_UNDONE'"
            "   AND a.interruption_reason_note = 'sua_lai'"
            "  FROM service_order o"
            "  JOIN LATERAL (SELECT status, interruption_reason_code,"
            "                       interruption_reason_note"
            "                  FROM service_execution_attempt"
            "                 WHERE clinic_id = o.clinic_id"
            "                   AND service_order_id = o.id"
            "                 ORDER BY attempt_no DESC LIMIT 1) a ON true"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid",
            identity.clinic_id,
            order_id,
        )
    if not la_sua:
        return {"da_dong": False, "vi_sao": "khong_do_sua_lai", "cau": None}
    return await dong_tai_quay(pool, order_id=order_id, identity=identity)


__all__ = [
    "dong_lai_sau_huy_sua",
    "chan_dong_neu_co",
    "dong_tai_quay",
    "hoan_tac_tai_quay",
    "mo_lai_neu_quay_da_dong",
]
