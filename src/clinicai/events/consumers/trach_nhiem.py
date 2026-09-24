"""Mở việc cho những trách nhiệm không được rơi.

KHÁCH LÀ TRÊN HẾT, và đây là chỗ câu ấy thành code. Khách trả tiền siêu âm, máy
hỏng, dịch vụ không làm — tiền của khách đang nằm ở phòng khám. Nếu hệ thống chỉ
ghi một dòng sự kiện rồi thôi thì trách nhiệm ấy **rơi**: không chủ, không hạn,
không màn nào hiện, và người nhớ ra là khách.

Module này nghe hai chuyện và mở một việc có người chịu trách nhiệm:

    service.not_performed (đã thu tiền) → Đối soát tiền
    service.interrupted                 → Quyết định làm lại

CẮM THÊM, KHÔNG SỬA AI. Module Thực hiện dịch vụ không biết file này tồn tại.
Bỏ file này đi thì Thực hiện vẫn chạy y nguyên; thêm bên nghe thứ ba (nhắc trưởng
ca sau 20 phút, báo CSKH gọi khách) cũng không đụng nó. Đó là LEGO.

KHÔNG MỞ HAI VIỆC CHO MỘT CHUYỆN. Giao tin là "ít nhất một lần", nên sự kiện có
thể tới hai lần. Chỉ mục duy nhất trên `(clinic, service_order, node_code)` khi
việc còn mở lo việc ấy — Postgres, không phải trí nhớ của người viết code.

KHÔNG TỰ QUYẾT THAY NGƯỜI. Việc mở ra chỉ nói "có chuyện này cần xử lý", không
tự hoàn tiền, không tự xếp lại phòng. Hoàn tiền là quyết định của người, và có
lệnh riêng của module Tài chính.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import asyncpg

from clinicai.events.hen_gio import HenDenHan, dang_ky_loai, hen
from clinicai.events.worker import SuKienDaNhan, dang_ky

#: Tên bên nhận — khoá trong `event_delivery.consumer`.
TRACH_NHIEM = "trach_nhiem_dich_vu"

#: Loại hẹn: tới giờ thì kiểm lại xem việc còn mở không.
HEN_KIEM_LAI = "trach_nhiem.kiem_lai"

#: Bao lâu thì kiểm lại. Đối soát tiền là chuyện của khách nên gắt hơn.
HAN_KIEM_LAI: dict[str, timedelta] = {
    "OPS-FINANCIAL-RESOLUTION": timedelta(hours=4),
    "OPS-SERVICE-INTERRUPTED": timedelta(hours=8),
}

#: Sự kiện nào mở loại việc nào. Thêm một dòng ở đây là thêm một trách nhiệm
#: được canh; không phải sửa module phát sự kiện.
VIEC_THEO_SU_KIEN: dict[str, str] = {
    "service.not_performed": "OPS-FINANCIAL-RESOLUTION",
    "service.interrupted": "OPS-SERVICE-INTERRUPTED",
    # Xếp phòng bị huỷ thì phải có người xếp lại — node đầu tiên của Slice 4.5
    # trong thiết kế đã chốt (ChatGPT tin 112).
    "service.routing_invalidated": "OPS-ROUTING-REASSIGN",
}


def _can_mo_viec(su_kien: SuKienDaNhan) -> str | None:
    """Chuyện này có cần một người chịu trách nhiệm không?"""
    node = VIEC_THEO_SU_KIEN.get(su_kien.event_type)
    if node is None:
        return None
    if su_kien.event_type == "service.not_performed":
        # Không thu tiền mà không làm thì không có gì để đối soát. Mở việc cho
        # mọi trường hợp là cách nhanh nhất để người trực học cách bỏ qua việc.
        if not su_kien.payload.get("da_thu_tien"):
            return None
    return node


async def mo_viec_khi_can(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    node = _can_mo_viec(su_kien)
    if node is None:
        return
    # Phát lại lịch sử thì KHÔNG mở lại việc cũ: người ta đã xử lý xong từ lâu.
    if su_kien.la_phat_lai:
        return

    visit_id = su_kien.payload.get("visit_id")
    ban = await conn.fetchrow(
        "SELECT v.id::text AS version_id FROM node_definition d"
        "  JOIN node_definition_version v ON v.node_definition_id = d.id"
        "   AND v.version = d.current_version"
        " WHERE d.clinic_id = $1::uuid AND d.code = $2",
        su_kien.clinic_id,
        node,
    )
    if ban is None:
        # Loại việc chưa được khai ở phòng khám này: dừng có tiếng, để dòng giao
        # vào hộp chết và có người nhìn — im lặng bỏ qua mới là mất trách nhiệm.
        raise RuntimeError(f"Chưa khai loại việc '{node}' cho phòng khám này.")

    chi_tiet: dict[str, Any] = {
        "vi": su_kien.event_type,
        "ly_do": su_kien.payload.get("ly_do"),
        "event_id": su_kien.event_id,
    }
    han = HAN_KIEM_LAI.get(node, timedelta(hours=8))
    viec_id = await conn.fetchval(
        """
        INSERT INTO work_item
            (clinic_id, node_code, node_version_id, visit_id, service_order_id,
             status, priority, payload, due_at)
        VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5::uuid, 'PENDING', 'P1',
                $6::jsonb, now() + $7::interval)
        ON CONFLICT DO NOTHING
        RETURNING id::text
        """,
        su_kien.clinic_id,
        node,
        ban["version_id"],
        visit_id,
        su_kien.aggregate_id,
        json.dumps(chi_tiet, ensure_ascii=False),
        han,
    )
    if viec_id is None:
        # Việc đã có sẵn (sự kiện tới lần hai) — không hẹn thêm lần nhắc nữa.
        return

    # Hẹn kiểm lại, CÙNG giao dịch với việc vừa mở. Tách ra hai giao dịch là có
    # ngày việc mở mà lời nhắc không bao giờ tới.
    await hen(
        conn,
        clinic_id=su_kien.clinic_id,
        loai=HEN_KIEM_LAI,
        sau=han,
        ve_cai_gi=viec_id,
        correlation_id=visit_id,
        chi_tiet={"node_code": node, "service_order_id": su_kien.aggregate_id},
    )


async def kiem_lai_viec_con_mo(conn: asyncpg.Connection, cai_hen: HenDenHan) -> bool:
    """Tới hạn: việc còn mở thì nâng mức ưu tiên; xong rồi thì thôi.

    ĐÂY LÀ CHỖ TRÁNH LỜI NHẮC SAI. Lời nhắc đặt lúc mở việc không biết chuyện
    người ta đã xử lý xong hai tiếng trước. Kiểm lại rồi mới làm, và "hết cần"
    cũng là một kết thúc bình thường.
    """
    con_mo = await conn.fetchval(
        "SELECT status FROM work_item WHERE clinic_id = $1::uuid AND id = $2::uuid"
        "   AND status IN ('PENDING', 'IN_PROGRESS')",
        cai_hen.clinic_id,
        cai_hen.ve_cai_gi,
    )
    if con_mo is None:
        return False

    # Nâng ưu tiên: việc quá hạn phải nổi lên đầu bảng, không chìm theo giờ mở.
    await conn.execute(
        "UPDATE work_item SET priority = 'P0', version = version + 1,"
        "       updated_at = now()"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid AND priority <> 'P0'",
        cai_hen.clinic_id,
        cai_hen.ve_cai_gi,
    )
    return True


dang_ky(TRACH_NHIEM, mo_viec_khi_can)
dang_ky_loai(HEN_KIEM_LAI, kiem_lai_viec_con_mo)

__all__ = [
    "HAN_KIEM_LAI",
    "HEN_KIEM_LAI",
    "TRACH_NHIEM",
    "VIEC_THEO_SU_KIEN",
    "kiem_lai_viec_con_mo",
    "mo_viec_khi_can",
]
