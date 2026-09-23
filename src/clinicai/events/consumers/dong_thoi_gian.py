"""Bên nhận đầu tiên: vẽ dòng thời gian của một lượt khám.

CHỌN BÊN NHẬN NÀY TRƯỚC VÌ NÓ VÔ HẠI. Hỏng thì màn thiếu một dòng; không ai bị
chặn, không đồng nào sai, không tin nhắn nào gửi đi. Đúng thứ cần cho bước 3 của
đường chuyển đổi: bật hạ tầng mới trên đường thật, nhưng chưa giao cho nó việc gì
có thể làm đau.

NÓ CÒN LÀ PHÉP THỬ CHO CẢ THIẾT KẾ. Projection này chỉ đọc `domain_event`. Xoá
sạch bảng rồi chạy lại sổ sự kiện phải ra đúng như cũ. Ngày nào không dựng lại
được, ngày đó câu "state-first + event đầy đủ" là nói suông.

`ON CONFLICT DO NOTHING`: giao tin là "ít nhất một lần", nên cùng một sự kiện có
thể tới hai lần sau một lần thử lại. Khoá chính là `event_id`, nên lần thứ hai
không tạo dòng thứ hai — chống trùng ép ở Postgres, không bằng việc nhớ kiểm tra.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import asyncpg

from clinicai.events.catalogue import DANH_MUC, DONG_THOI_GIAN_LUOT
from clinicai.events.phat_lai import Projection, dang_ky_projection
from clinicai.events.worker import SuKienDaNhan, dang_ky

# Trường nào của payload được đưa lên màn. Whitelist, không phải blacklist: thêm
# một trường vào payload không tự động làm nó hiện trên màn — và không vô tình
# đẩy dữ liệu cá nhân ra một màn có nhiều người xem hơn.
CHI_TIET_HIEN: dict[str, Sequence[str]] = {
    "service_order.placed": ["service_code", "service_name"],
    # Số ô còn trống là thông tin vận hành, không phải chữ lâm sàng.
    "result_form.completed": ["form_id", "so_o_con_trong"],
    # "Đã có kết quả" là mốc khách và bác sĩ chờ — nó phải nằm trên dòng thời
    # gian, tách bạch với "dịch vụ đã làm xong".
    "result.ready": ["form_id", "result_mode"],
    "result.corrected": ["form_id", "ban_thu"],
    "service.started": ["attempt_no", "room_id"],
    "service.completed": ["attempt_no"],
    "service.not_performed": ["ly_do", "da_thu_tien"],
    "service.interrupted": ["attempt_no", "ly_do"],
    "service.retry_prepared": [],
    "service.routing_invalidated": ["ly_do"],
    "service.routed": ["room_id", "ly_do", "tu_dong"],
    "service_order.carried_over": ["service_code", "da_thu_tien"],
    # Số tiền là thông tin vận hành của quầy, không phải chữ lâm sàng.
    "payment.service_collected": ["so_tien", "phuong_thuc"],
    "payment.medicine_collected": ["so_tien", "phuong_thuc"],
    # Kê ↔ mua ↔ giao: đối chiếu hai bản đơn (Tuyền 24/09).
    "medicine.dispensed": ["so_ke", "so_mua", "so_da_giao"],
    # Nhóm 3 (24/09/2026).
    "result_file.uploaded": ["cho_xac_nhan"],
    "result_file.confirmed": ["trang_thai"],
    "result_file.viewed": [],
    "result_file.sent_to_patient": ["kenh"],
    "result.reviewed": [],
    "result.viewed": [],
    "lab_result.arrived": [],
    "visit.checked_out": ["con_vuong"],
    "visit.left_early": [],
    "payment.refunded": ["so_tien"],
    "followup.scheduled": ["ngay"],
    "partner.sample_collected": [],
    "visit.checked_in": ["so_thu_tu"],
    "visit.routed": ["dich", "ly_do"],
    "consultation.started": ["loai"],
    "consultation.handed_over": [],
    "consultation.completed": ["loai", "ket_qua"],
    "vitals.started": [],
    "vitals.recorded": ["qua_duong"],
}


def _visit_id(payload: dict[str, Any]) -> str | None:
    """Sự kiện nào gắn với một lượt khám thì mang `visit_id` trong payload."""
    visit_id = payload.get("visit_id")
    return str(visit_id) if visit_id else None


async def ghi_dong_thoi_gian(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    visit_id = _visit_id(su_kien.payload)
    if visit_id is None:
        # Sự kiện không thuộc một lượt khám nào: không phải việc của màn này.
        return

    truong = CHI_TIET_HIEN.get(su_kien.event_type, ())
    chi_tiet = {k: su_kien.payload[k] for k in truong if k in su_kien.payload}
    nhan = DANH_MUC[su_kien.event_type].nhan if su_kien.event_type in DANH_MUC else ""

    await conn.execute(
        """
        INSERT INTO luot_dong_thoi_gian
            (event_id, clinic_id, visit_id, occurred_at, event_type, nhan,
             chi_tiet, actor_type, actor_staff_id, thu_tu)
        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7::jsonb, $8, $9::uuid,
                $10)
        ON CONFLICT (event_id) DO NOTHING
        """,
        su_kien.event_id,
        su_kien.clinic_id,
        visit_id,
        su_kien.occurred_at,
        su_kien.event_type,
        nhan,
        json.dumps(chi_tiet, ensure_ascii=False),
        su_kien.actor_type,
        su_kien.actor_staff_id,
        su_kien.seq,
    )


dang_ky(DONG_THOI_GIAN_LUOT, ghi_dong_thoi_gian)
# Là PROJECTION: xoá đi dựng lại từ sổ được (events/phat_lai.py).
dang_ky_projection(DONG_THOI_GIAN_LUOT, Projection(bang="luot_dong_thoi_gian"))

__all__ = ["ghi_dong_thoi_gian"]
