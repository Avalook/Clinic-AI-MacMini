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
    "roster.week_applied": "Áp dụng lịch trực cả tuần",
    "roster.tu_xep_theo_lich_hen": "Tự xếp bác sĩ vào ca theo lịch hẹn",
    "booking.doctor_rule_saved": "Đặt luật bắt buộc bác sĩ",
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
    # Hai mã dưới đi vào event_log như THAM SỐ của thong_bao_service (bảng
    # `NGUON` bên đó), không phải chuỗi hằng cạnh câu INSERT — nên bộ quét ở
    # test_audit_labels_drift.py KHÔNG thấy chúng. Thêm nhãn bằng tay ở đây là
    # bắt buộc; sửa bảng `NGUON` thì sửa cả chỗ này.
    "thong_bao.bac_si_da_xep": "Báo CSKH lịch đã có bác sĩ",
    "thong_bao.tuan_lich_truc": "Báo CSKH tuần đã chốt lịch trực",
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
    # Hai mã này GHÉP LÚC CHẠY ở service_log.py:
    # `f"service_log.{'started' if action == 'start' else 'finished'}"`.
    # Bài kiểm chống lệch chỉ soi chuỗi hằng nên chúng lọt từ lúc được viết —
    # nay bài kiểm đọc được cả f-string, xem `_FSTRING` bên đó.
    "service_log.started": "Bắt đầu làm dịch vụ",
    "service_log.finished": "Xong dịch vụ",
    "payment.recorded": "Ghi nhận thanh toán",
    "payment.voided": "Huỷ phiếu thanh toán",
    # ── CSKH ────────────────────────────────────────────────────────────────
    "cskh_action.created": "Tạo việc chăm sóc khách",
    "cskh_log.followup_call": "Gọi chăm sóc khách",
    "cskh.tuong_tac": "Ghi lần liên hệ với khách",
    "cskh.phan_hoi_ghi": "Ghi phản hồi của khách",
    "cskh.phan_hoi_xu_ly": "Xử lý phản hồi của khách",
    # `cskh.customers` là NGUỒN (cột source), không phải loại sự kiện — nó nói
    # dòng nhật ký này sinh ra từ màn Quản lý khách hàng. Bài kiểm chống lệch
    # gom cả hai vào một danh sách nên nó phải có nhãn, nếu không màn Lịch sử
    # thao tác hiện đúng chuỗi "cskh.customers".
    "cskh.customers": "Màn Quản lý khách hàng",
    # ── Nhân sự ─────────────────────────────────────────────────────────────
    "staff.created": "Tạo nhân sự",
    "staff.updated": "Sửa thông tin nhân sự",
    "staff.deactivated": "Ngưng hoạt động nhân sự",
}

#: Lệnh của workflow kernel (bảng `work_item_event`), gộp chung vào một dòng
#: nhật ký với tiền tố `work_item.`.
#:
#: DANH SÁCH NÀY PHẢI ĐÚNG BẰNG ràng buộc `work_item_event_command_check`
#: (20260730000005_workflow_kernel.sql) — không hơn không kém. Bản trước sai cả
#: hai chiều, đúng kiểu "viết theo hình dung" mà chính file này lên án:
#:
#:     thiếu `create`   — lệnh DUY NHẤT đang có dữ liệu thật. Người vận hành mở
#:                        Lịch sử thao tác thấy nguyên chuỗi `work_item.create`.
#:     thừa  4 lệnh     — claim/release/block/unblock: ràng buộc CHECK không cho
#:                        ghi, nên chúng chưa từng và không thể xảy ra.
#:
#: Bài kiểm chống lệch nay ĐỌC THẲNG ràng buộc ấy ra từ file migration và soi cả
#: hai chiều, nên bảng này không tự trôi khỏi hệ thống được nữa.
WORK_ITEM_LABELS: dict[str, str] = {
    "work_item.create": "Mở bước trong quy trình",
    "work_item.start": "Bắt đầu công việc",
    "work_item.complete": "Hoàn thành công việc",
    "work_item.skip": "Bỏ qua bước",
    "work_item.cancel": "Huỷ công việc",
    "work_item.reassign": "Giao lại công việc",
}


#: Đường ghi (`event_log.source`) → tên MÀN, bằng tiếng Việt.
#:
#: Trước đây bảng này nằm trong `AuditLogBoard.tsx` với 7 mục, trong khi hệ
#: thống phát ra hơn 30 đường ghi — nên ô "Làm ở màn" in thẳng địa chỉ mã nguồn:
#: "api:booking-override", "api:appointment-checkin". Chuyển về đây cho cùng chỗ
#: với ba bảng nhãn kia, đúng nguyên tắc dự án: không có luật nghiệp vụ trong TSX.
SOURCE_LABELS: dict[str, str] = {
    "workflow-kernel": "Quy trình khám",
    "dashboard": "Màn hình quản trị",
    "system": "Hệ thống",
    "api:dispatch": "Điều phối trong ngày",
    "api:reception": "Quầy tiếp nhận",
    "api:pharmacy": "Nhà thuốc",
    "api:staff": "Quản lý nhân sự",
    "api:clinic-settings": "Cấu hình phòng khám",
}

#: Khớp theo TIỀN TỐ khi không có mục khớp đúng — và đây mới là phần quan trọng.
#:
#: Một màn đẻ ra rất nhiều đường ghi: `api:appointment-{action}` ghép lúc chạy
#: (booking_service.py:775) cho ra 11 chuỗi — confirm, decline, complete,
#: checkin, undo_checkin, cskh_confirm, cancel, no_show, reassign,
#: assign_doctor, reschedule — và `api:service-{action}` thêm hai chuỗi nữa.
#: Liệt kê từng chuỗi một là quay lại đúng cái bảng-viết-theo-hình-dung: thêm
#: một hành động mới là lại lòi một dòng chữ máy ra màn hình.
#:
#: Người trực ca không cần biết route nào; họ cần biết MÀN nào. Khớp theo họ
#: đường ghi trả lời đúng câu đó, và tự đúng với route chưa tồn tại.
#:
#: THỨ TỰ CÓ NGHĨA — khớp từ trên xuống, cái hẹp phải đứng trước cái rộng
#: (`api:booking-override` trước `api:booking`).
SOURCE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("api:booking-override", "Luật đặt lịch"),
    ("api:booking", "Màn Đặt lịch"),
    ("api:appointment", "Màn Đặt lịch"),
    ("api:patient", "Hồ sơ khách hàng"),
    ("api:clinical", "Màn Khám bệnh"),
    ("api:lab", "Màn Xét nghiệm"),
    ("api:sono", "Màn Siêu âm"),
    ("api:ultrasound", "Màn Siêu âm"),
    ("api:service", "Danh sách dịch vụ"),
    ("api:cskh", "Quản lý khách hàng"),
    ("cskh.", "Quản lý khách hàng"),
    ("config.", "Cấu hình phòng khám"),
)


#: Loại đối tượng (`aggregate_type`) → tên tiếng Việt. Cái chip ở đầu ô chi tiết
#: đang in tên BẢNG trong database: "roster tuần" hiện ra là "roster_week".
AGGREGATE_LABELS: dict[str, str] = {
    "appointment": "Lịch hẹn",
    "patient": "Khách hàng",
    "clinic_patient": "Khách hàng",
    "patient_link": "Liên kết hồ sơ",
    "slot_hold": "Giữ chỗ khung giờ",
    "visit": "Lượt khám",
    "episode": "Đợt điều trị",
    "work_item": "Bước trong quy trình",
    "cskh_action": "Việc chăm sóc",
    "cskh_log": "Nhật ký chăm sóc",
    "staff_task": "Việc của nhân viên",
    "booking_override": "Luật đặt lịch",
    "roster_week": "Tuần lịch trực",
    "clinic": "Cấu hình phòng khám",
    "staff": "Nhân sự",
    "lab_result": "Kết quả xét nghiệm",
    "payment": "Thanh toán",
    "service_log": "Dịch vụ đã dùng",
    "clinical_record": "Bệnh án",
    "clinical_form_response": "Phiếu khám chuyên khoa",
    "clinical_data_consent": "Đồng ý chia sẻ hồ sơ",
    "drug_batch": "Lô thuốc",
    "prescription": "Đơn thuốc",
    "ultrasound_record": "Phiếu siêu âm",
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


def source_label(source: str | None) -> str:
    """Thao tác này đi vào từ MÀN nào.

    `None` = không có đường ghi, tức chính hệ thống sinh ra (migration, seed,
    worker) — cùng cách đọc như `actor_name` rỗng ở audit_log_service.
    """
    if not source:
        return "Hệ thống"
    if source in SOURCE_LABELS:
        return SOURCE_LABELS[source]
    for tien_to, nhan in SOURCE_PREFIXES:
        if source.startswith(tien_to):
            return nhan
    return source


def aggregate_label(aggregate_type: str) -> str:
    """Loại đối tượng. Rơi về chính mã khi chưa đặt tên — cùng lý do như
    `action_label`: mã thô xấu nhưng tra được, còn ô trống thì không."""
    return AGGREGATE_LABELS.get(aggregate_type, aggregate_type)
