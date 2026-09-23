"""Khối HÀNH TRÌNH — Journey Process Manager (thesis §9; docs/CHUAN-CAM-LEGO.md mục 5).

Giữ luật THỨ TỰ khách đi. Nghe sự thật đã xảy ra, rồi gửi LỆNH của khối Khám
(không ghi bảng của ai). Dây nối (docs/BAN-DO-DAY-NOI-LEGO.md, "Bản chốt 24/09"):

    H1  visit.checked_in          → xếp đường đi: qua tư vấn hay thẳng bác sĩ chính
        vitals.recorded           → hàng tư vấn: "chờ đo sinh hiệu" → "chờ tư vấn"
                                    (lượt chưa có đường đi thì xếp luôn — tự chữa)
    H3  consultation.handed_over  → hàng chờ khám thật của bác sĩ chính

Loại khám nào qua tư vấn là DỮ LIỆU (`service_type.qua_tu_van`), quản lý chỉnh
được — không viết cứng ở đây.

CHẠY LẠI ĐƯỢC: người đưa tin giao "ít nhất một lần"; mỗi lệnh tự bỏ qua nếu đã
làm. PHÁT LẠI (`la_phat_lai`) thì KHÔNG làm gì — đây là node TÁC VỤ, không phải
projection (xếp lại hàng cho khách hôm qua là sai).
"""

from __future__ import annotations

import asyncpg

from clinicai.events.catalogue import HANH_TRINH
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.luot_kham_service import LuotKhamService


async def xu_ly_hanh_trinh(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    visit_id = str(su_kien.payload.get("visit_id") or "")
    if not visit_id:
        return
    # Lệnh chạy trên CHÍNH giao dịch đánh dấu DONE (luật 3 của người đưa tin):
    # hỏng giữa chừng thì cả hai cùng cuộn lại, lần sau làm lại từ đầu.
    luot = LuotKhamService(pool=None)
    if su_kien.event_type == "visit.checked_in":
        await luot.xep_sau_check_in(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )
    elif su_kien.event_type == "vitals.recorded":
        # TỰ CHỮA: lượt chưa có đường đi (lỡ mất sự kiện check-in, hay lượt mở
        # theo đường cũ không phát sự kiện) thì xếp luôn ở đây. Lệnh tự bỏ qua
        # nếu đã xếp — chạy thừa không sao, thiếu mới là khách kẹt.
        await luot.xep_sau_check_in(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )
        await LuotKhamService.mo_hang_tu_van(
            conn, clinic_id=su_kien.clinic_id, visit_id=visit_id
        )
    elif su_kien.event_type == "consultation.handed_over":
        await luot.chuyen_bac_si_chinh(
            conn,
            clinic_id=su_kien.clinic_id,
            visit_id=visit_id,
            causation_id=su_kien.event_id,
        )


dang_ky(HANH_TRINH, xu_ly_hanh_trinh)

__all__ = ["xu_ly_hanh_trinh"]
