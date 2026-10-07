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
    # Làm thêm tại quầy (01/10/2026): dịch vụ + nơi tick.
    "service_order.desk_added": ["service_code", "service_name", "nguon"],
    "service_order.desk_removed": ["service_code", "nguon"],
    # Số dòng đơn — không tên thuốc (tên thuốc nói ra bệnh).
    "prescription.saved": ["so_dong"],
    "medicine.counter_changed": ["hanh_dong", "so_luong", "so_luong_cu"],
    "medicine.declined": ["so_ke", "so_mua"],
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
    # V4 (30/09/2026): khách chuyển phòng giữa chừng / huỷ bắt đầu nhầm — chỉ
    # mã phòng + số lần làm, không chữ lâm sàng.
    "service.patient_moved": ["attempt_no", "from_room_id", "to_room_id"],
    "service.start_cancelled": ["attempt_no", "room_id"],
    "service.routing_invalidated": ["ly_do"],
    "service.routed": [
        "room_id",
        "ly_do",
        "tu_dong",
        "nguon",
        "huong_dan_room_id",
        "dung_huong_dan",
        "nhan_cheo_tu_room_id",
    ],
    # Nhận khách tại phòng (07/10/2026): chỉ mã phòng + mã lý do.
    "service.room_released": ["room_id", "ly_do", "trang_thai_truoc", "sang_room_id"],
    "service.room_receive_undone": ["room_id"],
    "service.room_guided": ["room_id", "tu_room_id", "nguon"],
    "consultation.resumed": ["loai", "lan"],
    # Trưởng ca chuyển phòng khi đang làm (29/09/2026): lý do là chữ vận hành
    # trưởng ca gõ, Tuyền cần nó hiện ở lịch sử lượt.
    "service.room_transferred": ["from_room_id", "room_id", "ly_do", "nguon"],
    # Chọn bác sĩ trong phòng nhiều bác sĩ (30/09/2026): chỉ mã, không chữ.
    "service.doctor_chosen": ["room_id", "bac_si_id", "lan", "tu_dong", "nguon"],
    "service_order.required_changed": ["bat_buoc"],
    "service_order.carried_over": ["service_code", "da_thu_tien"],
    # Số tiền là thông tin vận hành của quầy, không phải chữ lâm sàng.
    "payment.service_collected": ["so_tien", "phuong_thuc"],
    "payment.medicine_collected": ["so_tien", "phuong_thuc"],
    "cong_no.ghi": ["so_tien", "ly_do"],
    "cong_no.huy": ["so_tien", "ly_do"],
    "cong_no.da_thu": ["so_tien"],
    # Kê ↔ mua ↔ giao: đối chiếu hai bản đơn (Tuyền 24/09).
    "medicine.dispensed": ["so_ke", "so_mua", "so_da_giao"],
    # Nhóm 3 (24/09/2026).
    "result_file.uploaded": ["cho_xac_nhan"],
    "partner.order_received": ["service_name", "ly_do"],
    # Đối tác tự thu (27/09/2026) — số tiền là thông tin vận hành.
    "partner.payment_recorded": ["so_tien", "hinh_thuc"],
    "partner.payment_voided": ["so_tien"],
    "result_file.confirmed": ["trang_thai"],
    # V9 (30/09/2026): lý do xoá là chữ vận hành người xoá gõ — hiện ở lịch sử.
    "result_file.deleted": ["loai", "ly_do"],
    "result_file.restored": [],
    "result_file.viewed": [],
    "result_file.sent_to_patient": ["kenh"],
    "result.reviewed": [],
    "result.viewed": [],
    "lab_result.arrived": [],
    "visit.checked_out": ["con_vuong"],
    "visit.left_early": [],
    "payment.refunded": ["so_tien"],
    # Đổi TM/CK/QR sau khi thu (V7) — thông tin vận hành của quầy.
    "payment.method_changed": ["tu", "sang", "so_tien"],
    # Hoàn tác lần thu (01/10/2026) — lý do là chữ vận hành người bấm gõ.
    "payment.collection_undone": ["kind", "so_tien", "truoc", "ly_do"],
    "followup.scheduled": ["ngay"],
    "partner.sample_collected": [],
    "partner.sample_received": [],
    # Đổi dịch vụ khám sau check-in (V5, 30/09/2026) — tên loại khám là danh
    # mục, không phải thông tin khách.
    "appointment.service_switched": ["tu_ten", "den_ten"],
    "visit.checked_in": ["so_thu_tu"],
    "visit.routed": ["dich", "ly_do"],
    "consultation.started": ["loai"],
    "consultation.handed_over": [],
    "consultation.completed": ["loai", "ket_qua"],
    "vitals.started": [],
    "vitals.recorded": ["qua_duong", "bo_qua_tu_van"],
    # Tick "Làm trước – thu sau" (30/09/2026 tối) — ai / lúc nào nằm ở cột
    # người + giờ của dòng; chi tiết chỉ là số chỉ định chốt cùng lúc.
    "visit.defer_payment_set": ["so_chi_dinh_chot"],
    "visit.defer_payment_cleared": [],
    # Bán thêm vật tư (C13, 01/10/2026): tên hàng + số lượng là thông tin vận
    # hành của quầy, không phải chữ lâm sàng.
    "visit.supply_changed": ["ten", "hanh_dong", "so_luong"],
    # Dịch vụ khám con (C18, 02/10/2026): tên + giá là danh mục, không phải
    # chữ lâm sàng — Hành trình khách hiện "Dịch vụ khám: <tên> · <giá>".
    "visit.exam_service_changed": ["loai_kham", "them", "bo"],
    # HOÀN TÁC (01/10/2026): lý do là chữ vận hành người bấm gõ khi máy chủ hỏi
    # xác nhận — Tuyền cần thấy ai rút lại gì, vì sao, ở lịch sử lượt.
    "consultation.reopened": ["loai", "ket_qua_cu", "mo_lai_kham_xong", "ly_do"],
    "service_order.cancelled": [
        "service_code",
        "service_name",
        "da_thu_tien",
        "tien_thua",
        "ly_do",
    ],
    # Khối 2 (06/10/2026): hoàn tác bỏ chỉ định — tên dịch vụ + lý do.
    "service_order.restored": ["service_code", "service_name", "ly_do"],
    "service.completion_undone": ["attempt_no", "mo_lai_kham_xong", "ly_do"],
    "visit.reopened": ["tu_ve_giua_chung", "ly_do"],
    "result.approval_revoked": ["tep_da_gui", "ly_do"],
}


def _visit_id(payload: dict[str, Any]) -> str | None:
    """Sự kiện nào gắn với một lượt khám thì mang `visit_id` trong payload."""
    visit_id = payload.get("visit_id")
    return str(visit_id) if visit_id else None


def _nhan_rieng(event_type: str, payload: dict[str, Any]) -> str | None:
    """Nhãn riêng khi nhãn cố định của danh mục không đủ nói chuyện gì xảy ra.

    Thuần hàm của payload (phát lại ra đúng nhãn cũ). Không có tên thuốc — tên
    thuốc nói ra bệnh; dòng nào do mã dòng, màn kê đơn của bác sĩ chỉ ra.
    """
    if (
        event_type == "medicine.counter_changed"
        and payload.get("hanh_dong") == "SUA_SO_LUONG"
    ):
        return (
            "Quầy thu thuốc sửa số lượng thuốc bác sĩ kê: "
            f"{payload.get('so_luong_cu')} → {payload.get('so_luong')}"
        )
    if (
        event_type == "medicine.counter_changed"
        and payload.get("hanh_dong") == "DIEN_SO_LUONG"
    ):
        moi = payload.get("so_luong")
        cu = payload.get("so_luong_cu")
        if cu is None:
            return f"Quầy thu thuốc điền số lượng thuốc (bác sĩ để trống): {moi}"
        return f"Quầy thu thuốc sửa số lượng thuốc đã điền: {cu} → {moi}"
    if event_type == "visit.exam_service_changed":

        def _ds(x: Any) -> str:
            gia = x.get("gia")
            tien = (
                f"{int(gia):,}".replace(",", ".") + "đ"
                if isinstance(gia, int)
                else "chưa có giá"
            )
            return f"{x.get('ten') or 'dịch vụ khám'} · {tien}"

        them = [_ds(x) for x in payload.get("them") or []]
        bo = [_ds(x) for x in payload.get("bo") or []]
        cau = []
        if them:
            cau.append("Chọn dịch vụ khám: " + " + ".join(them))
        if bo:
            cau.append("Bỏ chọn dịch vụ khám: " + " + ".join(bo))
        return "; ".join(cau) or None
    return None


async def ghi_dong_thoi_gian(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    visit_id = _visit_id(su_kien.payload)
    if visit_id is None:
        # Sự kiện không thuộc một lượt khám nào: không phải việc của màn này.
        return

    truong = CHI_TIET_HIEN.get(su_kien.event_type, ())
    chi_tiet = {k: su_kien.payload[k] for k in truong if k in su_kien.payload}
    nhan = _nhan_rieng(su_kien.event_type, su_kien.payload) or (
        DANH_MUC[su_kien.event_type].nhan if su_kien.event_type in DANH_MUC else ""
    )

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
