"""HOÀN TẤT PHIẾU KẾT QUẢ Ở ĐÂU CŨNG LÀ DỊCH VỤ XONG (chốt 29/10/2026).

Ca thật 28/10 (Hào Nam): trợ lý điền phiếu HPV ở bàn khám rồi Hoàn tất khi chưa
ai bấm Bắt đầu. Đường cũ chỉ đóng dịch vụ "đang làm", nên bỏ qua im lặng: phiếu
chốt, dịch vụ nằm "chờ làm"; tối đó phòng bấm Bắt đầu rồi Xong thì bị chặn "bấm
Xong trong phiếu" (phiếu đã chốt, không còn nút) — việc đối tác không sinh ra.
Từ 13/10 có 34 phiếu chốt trước khi dịch vụ bắt đầu, 13 dịch vụ kẹt "đang làm".

Hai nửa, một luật:

* TRƯỚC khi chốt (`chan_hoan_tat`): dịch vụ còn phải bắt đầu / đóng mà không
  làm được (chưa thu tiền, khách đã bỏ ở quầy, thiếu quyền) thì KHÔNG chốt —
  nháp giữ nguyên, nói rõ vì sao. Không còn trạng thái "phiếu đã chốt mà dịch
  vụ chưa xong".
* SAU khi chốt (`dong_sau_hoan_tat`): chưa bắt đầu → bắt đầu + xong; đang làm
  → xong. Bằng LỆNH CÓ SẴN của module Thực hiện (cùng khoá lượt, quyền, sự
  kiện — dịch vụ thu hộ tự lên bàn đối tác qua `service.completed`). Chỉ định
  đã xếp phòng thì làm theo phòng; không (hay không có quyền ở phòng ấy) thì
  làm tại bàn khám — lệnh bàn khám tự xếp vào phòng bàn khám.

Làm thêm tại quầy (`nguon_lam_them`) giữ đường riêng của nó
(`lam_them_dong_dich_vu`) — có nút [Đóng dịch vụ] khi chưa xếp phòng.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can_o_phong_nao_do
from clinicai.permissions.doc_bang import co_mot_quyen
from clinicai.services import finance_gate
from clinicai.services.service_execution_service import (
    CAU_CHUA_BIET_PHONG_BAN_KHAM,
    NOI_BAN_KHAM,
    QUYEN_BAT_DAU,
    QUYEN_LAM_TAI_BAN_KHAM,
    QUYEN_XONG,
    ServiceExecutionService,
    cua_tien_chot_ho,
    phong_ban_kham,
)

logger = structlog.get_logger()

CAU_KHACH_DA_BO = (
    "Khách đã bỏ dịch vụ này ở quầy thu — chọn lại dịch vụ rồi mới Hoàn tất."
    " Nội dung phiếu vẫn giữ."
)
#: Chưa thu tiền mà bấm Hoàn tất (Tuyền 29/10/2026: "đừng đỏ, báo là vui lòng
#: thu tiền hoặc bấm làm trước thu sau") — lời nhắc, không phải lỗi. Lệnh từ
#: chối bằng ``ChuaThuTienError`` (mã ``CHUA_THU_TIEN``) để màn vẽ màu nhắc.
CAU_CHUA_THU_HOAN_TAT = "Vui lòng thu tiền hoặc bấm Làm trước – thu sau."
CAU_THIEU_QUYEN = (
    "Bạn chưa có quyền làm dịch vụ này nên phiếu CHƯA hoàn tất — nhờ bác sĩ hoặc"
    " người có quyền bấm Hoàn tất. Nội dung phiếu vẫn giữ."
)

#: Chỉ định bác sĩ đã duyệt, chưa xong (cột cũ `exec_status`): mới có việc để
#: bắt đầu / đóng. Nháp chưa duyệt, đã làm, đã huỷ → không đụng.
_DA_DUYET = frozenset({"authorized", "assigned", "in_progress"})

_SQL_DON = (
    "SELECT o.visit_id::text AS visit_id, o.selection_status, o.exec_status,"
    "       o.execution_status, o.execution_revision,"
    "       o.routing_status, o.routing_revision, o.nguon_lam_them,"
    "       (SELECT a.noi_lam FROM service_execution_attempt a"
    "         WHERE a.clinic_id = o.clinic_id AND a.service_order_id = o.id"
    "           AND a.status = 'IN_PROGRESS' LIMIT 1) AS noi_lam,"
    "       (SELECT a.id::text FROM service_execution_attempt a"
    "         WHERE a.clinic_id = o.clinic_id AND a.service_order_id = o.id"
    "           AND a.status = 'IN_PROGRESS' LIMIT 1) AS lan_dang_chay"
    "  FROM service_order o"
    " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
)


def viec_can_lam(
    *,
    execution_status: str | None,
    exec_status: str | None,
    nguon_lam_them: bool,
    co_lan_dang_chay: bool,
) -> str | None:
    """Hoàn tất phiếu thì dịch vụ phải làm gì — hàm THUẦN.

    ``"bat_dau_va_xong"`` (chưa ai bắt đầu) · ``"xong"`` (đang làm) · None (đã
    xong / không làm / đã huỷ / dừng giữa chừng / chỉ định nháp chưa duyệt /
    làm thêm tại quầy — đường riêng; phiếu chốt như cũ, không đụng dịch vụ).
    """
    if nguon_lam_them or exec_status not in _DA_DUYET:
        return None
    tt = execution_status or "PENDING"
    if tt == "PENDING":
        return "bat_dau_va_xong"
    if tt == "IN_PROGRESS" and co_lan_dang_chay:
        return "xong"
    return None


async def chan_hoan_tat(
    conn: asyncpg.Connection, identity: StaffIdentity, order_id: str | None
) -> str | None:
    """Vì sao CHƯA được Hoàn tất (câu cho người) — None = được.

    Chỉ hỏi cửa có thể chặn trước mà không ghi gì: khách bỏ, tiền, quyền, phòng
    bàn khám. Tranh chấp lúc ghi (người khác vừa bấm) vẫn do lệnh tự từ chối.
    """
    if order_id is None:
        return None
    cid = identity.clinic_id
    don = await conn.fetchrow(_SQL_DON, cid, order_id)
    if don is None:
        return None
    viec = viec_can_lam(
        execution_status=don["execution_status"],
        exec_status=don["exec_status"],
        nguon_lam_them=bool(don["nguon_lam_them"]),
        co_lan_dang_chay=don["lan_dang_chay"] is not None,
    )
    if viec is None:
        return None
    co_ban_kham = await co_mot_quyen(conn, identity, QUYEN_LAM_TAI_BAN_KHAM)
    if viec == "xong":
        if don["noi_lam"] == NOI_BAN_KHAM:
            return None if co_ban_kham else CAU_THIEU_QUYEN
        return (
            None
            if await can_o_phong_nao_do(conn, identity, QUYEN_XONG)
            else CAU_THIEU_QUYEN
        )
    if don["selection_status"] == "NOT_SELECTED":
        return CAU_KHACH_DA_BO
    # ĐÚNG cửa tiền của lệnh Bắt đầu (phòng và bàn khám): tính như thể khách
    # đã chốt làm — chỉ định còn chờ khách quyết mà cửa mở thì lệnh tự chốt hộ.
    neu_chot = (
        await finance_gate.states_for_orders(conn, cid, [order_id], gia_su_chon=True)
    ).get(str(order_id))
    duoc, cau_tien, _ = cua_tien_chot_ho(
        neu_chot, selection_status=don["selection_status"]
    )
    if not duoc:
        if not cau_tien or cau_tien == finance_gate.CAU_CHUA_THU:
            return CAU_CHUA_THU_HOAN_TAT
        return f"{cau_tien} Nội dung phiếu vẫn giữ."
    co_phong = (
        don["routing_status"] == "ASSIGNED"
        and await can_o_phong_nao_do(conn, identity, QUYEN_BAT_DAU)
        and await can_o_phong_nao_do(conn, identity, QUYEN_XONG)
    )
    if co_phong:
        return None
    if not co_ban_kham:
        return CAU_THIEU_QUYEN
    if don["routing_status"] != "ASSIGNED" and (
        await phong_ban_kham(conn, cid, don["visit_id"], identity.staff_id) is None
    ):
        return CAU_CHUA_BIET_PHONG_BAN_KHAM
    return None


async def _bat_dau_va_xong(
    svc: ServiceExecutionService,
    *,
    order_id: str,
    don: asyncpg.Record,
    identity: StaffIdentity,
) -> None:
    rev = int(don["execution_revision"] or 0)
    if don["routing_status"] == "ASSIGNED":
        try:
            bd = await svc.bat_dau(
                order_id=order_id,
                expected_execution_revision=rev,
                expected_routing_revision=int(don["routing_revision"] or 0),
                identity=identity,
                idempotency_key=f"phieu-bat-dau-{order_id}-{rev}",
            )
        except SafetyGateError:
            # Không có ca / quyền ở phòng đã xếp (vd trợ lý bàn khám) → làm tại
            # bàn khám, dưới đây.
            bd = None
        if bd is not None:
            await svc.xong(
                order_id=order_id,
                attempt_id=bd["attempt_id"],
                expected_execution_revision=int(bd["execution_revision"]),
                identity=identity,
                idempotency_key=f"phieu-xong-{order_id}-{bd['attempt_id']}",
            )
            return
    bd = await svc.bat_dau_tai_ban_kham(
        order_id=order_id,
        expected_execution_revision=rev,
        identity=identity,
        idempotency_key=f"phieu-ban-kham-{order_id}-{rev}",
    )
    await svc.xong_tai_ban_kham(
        order_id=order_id,
        attempt_id=bd["attempt_id"],
        expected_execution_revision=int(bd["execution_revision"]),
        identity=identity,
        idempotency_key=f"phieu-xong-ban-kham-{order_id}-{bd['attempt_id']}",
    )


async def dong_sau_hoan_tat(
    pool: asyncpg.Pool, *, order_id: str, identity: StaffIdentity
) -> dict[str, Any]:
    """Phiếu vừa chốt → dịch vụ xong. Trả ``{da_dong, vi_sao, cau}``.

    Không ném lỗi nghiệp vụ: phiếu đã chốt là sự thật độc lập. `chan_hoan_tat`
    đã chặn các cửa biết trước, nên lỗi ở đây chỉ còn tranh chấp lúc ghi — vẫn
    nói rõ (màn phòng hiện [Xong] cho phiếu đã chốt mà dịch vụ còn đang làm).
    """
    async with pool.acquire() as conn:
        don = await conn.fetchrow(_SQL_DON, identity.clinic_id, order_id)
    if don is None:
        return {"da_dong": False, "vi_sao": "khong_dang_lam"}
    if don["nguon_lam_them"] and (don["execution_status"] or "PENDING") == "PENDING":
        # SAU khi trả kết nối: `dong_tai_quay` tự mượn kết nối (14/10/2026).
        from clinicai.services.lam_them_dong_dich_vu import dong_tai_quay

        return await dong_tai_quay(pool, order_id=order_id, identity=identity)
    viec = viec_can_lam(
        execution_status=don["execution_status"],
        exec_status=don["exec_status"],
        nguon_lam_them=bool(don["nguon_lam_them"]),
        co_lan_dang_chay=don["lan_dang_chay"] is not None,
    )
    if viec is None:
        return {"da_dong": False, "vi_sao": "khong_dang_lam"}
    svc = ServiceExecutionService(pool)
    try:
        if viec == "bat_dau_va_xong":
            await _bat_dau_va_xong(svc, order_id=order_id, don=don, identity=identity)
        elif don["noi_lam"] == NOI_BAN_KHAM:
            await svc.xong_tai_ban_kham(
                order_id=order_id,
                attempt_id=don["lan_dang_chay"],
                expected_execution_revision=int(don["execution_revision"] or 0),
                identity=identity,
                idempotency_key=f"form-{order_id}-{don['lan_dang_chay']}",
            )
        else:
            await svc.xong(
                order_id=order_id,
                attempt_id=don["lan_dang_chay"],
                expected_execution_revision=int(don["execution_revision"] or 0),
                identity=identity,
                idempotency_key=f"form-{order_id}-{don['lan_dang_chay']}",
            )
    except Exception as loi:  # noqa: BLE001 — không làm hỏng phiếu đã chốt
        # Câu của lệnh (lệch phiên bản, khách đang ở phòng khác…) là câu tiếng
        # Việt cho người — trả nguyên, đừng thay bằng mã thô.
        cau = str(getattr(loi, "message", "") or loi)[:200]
        vi_sao = "khong_du_quyen" if isinstance(loi, SafetyGateError) else "loi"
        logger.warning(
            "phieu_xong_khong_dong_duoc_dich_vu",
            service_order_id=order_id,
            vi_sao=vi_sao,
            loi=cau,
        )
        return {
            "da_dong": False,
            "vi_sao": vi_sao,
            "chi_tiet": cau,
            "cau": f"Phiếu đã lưu nhưng dịch vụ CHƯA đóng: {cau}",
        }
    return {"da_dong": True}


__all__ = [
    "CAU_KHACH_DA_BO",
    "CAU_THIEU_QUYEN",
    "chan_hoan_tat",
    "dong_sau_hoan_tat",
    "viec_can_lam",
]
