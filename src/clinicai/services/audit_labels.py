"""Tên tiếng Việt của mỗi loại sự kiện — MỘT bảng, không phải ba.

VÌ SAO CHUYỂN RA KHỎI TRÌNH DUYỆT. Bảng nhãn đang có HAI bản rời nhau:
``AuditLogBoard.tsx`` (20 mã) và ``HistoryClient.tsx`` (4 mã dispatch). Hai bảng
cho cùng một khái niệm thì hai màn sẽ nói hai kiểu về cùng một sự kiện, và
không có gì báo khi chúng lệch.

CHÚNG ĐÃ LỆCH RỒI, và lệch theo cả hai chiều — bằng chứng rằng bảng cũ được
viết theo hình dung chứ không theo hệ thống thật:

    thiếu 15 mã đang chạy hằng ngày   slot_hold.created (13 dòng),
                                      clinic_settings.booking_policy_updated (11),
                                      booking_override.* (16), lab_result.*, …
                                      → 61/200 dòng hiện mã thô cho người dùng
    thừa 8 mã chưa từng phát sinh      appointment.updated, patient.updated,
                                      cskh_action.*, visit.*, work_item.skip …

Thêm 15 nhãn chỉ vá hiện trạng. Thứ chặn nó lệch lại là bài kiểm ở
``src/tests/test_audit_labels_drift.py``: nó quét mọi mã trong mã nguồn và bắt
mỗi mã phải có nhãn ở đây.

CÂU CHỮ. Nhãn là thứ người vận hành đọc để hiểu chuyện gì đã xảy ra, nên viết
theo việc chứ không theo bảng: "Giữ chỗ khi đang chọn" chứ không "Tạo slot_hold".
"""

from __future__ import annotations

#: Mã sự kiện → tên việc, bằng tiếng Việt.
#:
#: Nhóm theo luồng để người thêm mã mới biết đặt vào đâu. Mã nào có trong
#: `event_log` của prod đều phải có mặt ở đây; xem bài kiểm chống lệch.
EVENT_LABELS: dict[str, str] = {
    # ── Đặt lịch ────────────────────────────────────────────────────────────
    "appointment.created": "Tạo lịch hẹn",
    "appointment.confirmed": "Xác nhận lịch hẹn",
    "appointment.cskh_confirmed": "CSKH xác nhận lịch",
    "appointment.rescheduled": "Dời lịch hẹn",
    "appointment.cancelled": "Huỷ lịch hẹn",
    "appointment.declined": "Từ chối lịch hẹn",
    "appointment.no_show": "Khách không đến",
    "appointment.reassigned": "Đổi bác sĩ phụ trách",
    "appointment.reminder": "Nhắc lịch hẹn",
    "appointment.checked_in": "Tiếp nhận (check-in)",
    "appointment.checkin_undone": "Huỷ tiếp nhận",
    "appointment.completed": "Khám xong",
    # Giữ chỗ tồn tại trong lúc CSKH đang chọn khung giờ, để hai người không
    # chọn trùng nhau. Nói rõ "khi đang chọn" vì nó KHÔNG phải một lịch hẹn.
    "slot_hold.created": "Giữ chỗ khi đang chọn",
    "slot_hold.released": "Thả chỗ đang giữ",
    "interaction.walkin": "Khách đến trực tiếp",
    # ── Luật đặt lịch & cấu hình ────────────────────────────────────────────
    "clinic_settings.booking_policy_updated": "Sửa luật đặt lịch",
    "clinic_settings.feature_mode_updated": "Đổi chế độ phòng khám",
    "booking_override.doctor_created": "Thêm luật cho bác sĩ",
    "booking_override.doctor_deleted": "Xoá luật của bác sĩ",
    "booking_override.slot_created": "Thêm luật khung giờ",
    "booking_override.slot_deleted": "Xoá luật khung giờ",
    "booking_override.slot_superseded": "Luật khung giờ bị luật mới cắt",
    # ── Điều phối trong ngày ────────────────────────────────────────────────
    "dispatch.checkin": "Tiếp nhận tại quầy",
    "dispatch.checkout": "Ra về",
    "dispatch.moved": "Chuyển sang bước khác",
    "dispatch.transfer_room": "Đổi phòng",
    "dispatch.route_applied": "Áp tuyến khám",
    # `visit.closed_incomplete` THIẾU NHÃN TỪ LÚC ĐƯỢC THÊM. Bài kiểm chống
    # lệch ở cạnh không bắt được vì mã này đi vào event_log như một BIỂU THỨC
    # ba ngôi ở cuối lời gọi, ngoài tầm quét. Người vận hành mở Lịch sử thao
    # tác thấy chuỗi thô — đúng cái vòng lặp bài kiểm ấy được viết ra để chặn.
    "visit.closed_incomplete": "Đóng lượt khi chưa khám xong",
    "dispatch.alert_called": "Trưởng ca gọi bộ phận",
    # ── Nhà thuốc ───────────────────────────────────────────────────────────
    "pharmacy.dispensed": "Cấp thuốc",
    "pharmacy.refused": "Khách không lấy thuốc",
    "pharmacy.line_closed": "Chốt dòng thuốc",
    "pharmacy.adjusted": "Điều chỉnh tồn kho",
    "pharmacy.discarded": "Huỷ thuốc",
    # ── Hồ sơ bệnh nhân ─────────────────────────────────────────────────────
    "patient.created": "Tạo hồ sơ bệnh nhân",
    "patient_link.created": "Liên kết hai bệnh nhân",
    "clinical_data_consent.granted": "Đồng ý chia sẻ hồ sơ",
    "clinical_data_consent.revoked": "Thu hồi đồng ý chia sẻ",
    # ── Khám & bệnh án ──────────────────────────────────────────────────────
    "clinical_record.saved": "Lưu bệnh án",
    "clinical_record.vitals_saved": "Ghi sinh hiệu",
    "clinical_form.saved": "Lưu phiếu khám chuyên khoa",
    "clinical.signed": "Ký bệnh án",
    "clinical.released": "Cho phép gửi kết quả",
    "clinical.amended": "Đính chính bệnh án",
    "episode.closed": "Đóng đợt điều trị",
    "episode.reopened": "Mở lại đợt điều trị",
    # ── Xét nghiệm ──────────────────────────────────────────────────────────
    "lab_result.ordered": "Chỉ định xét nghiệm",
    "lab_result.entered": "Nhập kết quả xét nghiệm",
    "lab_result.finalized": "Chốt kết quả xét nghiệm",
    # ── Dịch vụ & thu ngân ──────────────────────────────────────────────────
    "service_log.created": "Thêm dịch vụ đã dùng",
    "service_log.removed": "Bỏ dịch vụ đã ghi",
    "payment.recorded": "Ghi nhận thanh toán",
    "payment.voided": "Huỷ phiếu thanh toán",
    # ── CSKH ────────────────────────────────────────────────────────────────
    "cskh_action.created": "Tạo việc chăm sóc khách",
    "cskh_log.followup_call": "Gọi chăm sóc khách",
    # ── Nhân sự ─────────────────────────────────────────────────────────────
    "staff.created": "Tạo nhân sự",
    "staff.updated": "Sửa thông tin nhân sự",
    "staff.deactivated": "Ngưng hoạt động nhân sự",
}

#: Lệnh của workflow kernel (bảng `work_item_event`), gộp chung vào một dòng
#: nhật ký với tiền tố `work_item.`.
WORK_ITEM_LABELS: dict[str, str] = {
    "work_item.start": "Bắt đầu công việc",
    "work_item.complete": "Hoàn thành công việc",
    "work_item.claim": "Nhận công việc",
    "work_item.release": "Trả lại công việc",
    "work_item.skip": "Bỏ qua bước",
    "work_item.cancel": "Huỷ công việc",
    "work_item.reassign": "Giao lại công việc",
    "work_item.block": "Tạm dừng công việc",
    "work_item.unblock": "Bỏ tạm dừng",
}


def action_label(event_type: str) -> str:
    """Tên việc, hoặc chính mã nếu chưa đặt tên.

    TRẢ VỀ MÃ THÔ khi thiếu nhãn, KHÔNG trả chuỗi rỗng và không trả "Không rõ".
    Một ô trống trong nhật ký đọc thành "không có gì xảy ra"; còn `slot_hold.
    created` tuy xấu nhưng vẫn tra cứu được, và nó tự tố cáo rằng bảng nhãn
    đang thiếu.
    """
    return (
        EVENT_LABELS.get(event_type) or WORK_ITEM_LABELS.get(event_type) or event_type
    )
