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
    # Quản lý gỡ ca trực khám của một bác sĩ ⇒ lịch hẹn ngày ấy bỏ bác sĩ, rơi
    # về hàng "Chờ xếp bác sĩ" (14/08/2026). Không phải người bấm vào lịch hẹn,
    # nên nhãn nói RÕ nguyên nhân — đọc lại sáu tháng sau vẫn hiểu vì sao một
    # lịch tự nhiên mất bác sĩ.
    "patient.phone_added": "Thêm số điện thoại cho khách",
    "patient.phone_removed": "Xoá số điện thoại của khách",
    "appointment.doctor_removed": "Gỡ bác sĩ khỏi lịch (ca trực bị xoá)",
    "roster.shift_removed": "Gỡ ca trực",
    "roster.shift_reassigned": "Đổi người trong ca",
    "roster.shift_added_cho_xep": "Ca mới có lịch đang chờ xếp bác sĩ",
    "appointment.doctor_restored": "Gắn lại bác sĩ (ca trực xếp lại)",
    "appointment.cancelled": "Huỷ lịch hẹn",
    "roster.week_applied": "Áp dụng lịch trực cả tuần",
    "roster.tu_xep_theo_lich_hen": "Tự xếp bác sĩ vào ca theo lịch hẹn",
    "booking.doctor_rule_saved": "Đặt luật bắt buộc bác sĩ",
    "appointment.declined": "Từ chối lịch hẹn",
    "appointment.no_show": "Khách không đến",
    "appointment.reassigned": "Đổi bác sĩ phụ trách",
    "appointment.reminder": "Nhắc lịch hẹn",
    "appointment.checked_in": "Tiếp nhận (check-in)",
    # Sổ sự kiện nghiệp vụ, nhóm 3 (24/09/2026).
    "visit.checked_out": "Khách đã về (check-out)",
    "visit.left_early": "Khách bỏ về giữa chừng",
    "patient.contacted": "CSKH đã liên hệ khách",
    # Khối chỉnh dây (nhóm 5, 24/09/2026).
    "config.wiring_changed": "Đổi dây nối nghiệp vụ",
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
    "thong_bao.xung_dot_suc_chua": "Báo Trưởng ca khung vượt trần khi công bố",
    "pharmacy.counter_changed": "Quầy thuốc chỉnh đơn bán (tích / số lượng / thêm)",
    "thong_bao.lich_mat_bac_si": "Báo CSKH và Trưởng ca lịch mất bác sĩ khi công bố",
    "thong_bao.ket_qua_ve": "Báo CSKH và bác sĩ kết quả vừa về",
    "thong_bao.hen_goi_lai": "Đặt nhắc gọi lại đúng giờ",
    "nhac_tai_kham.hen_doi": "Bác sĩ đặt / đổi / bỏ ngày tái khám (việc CSKH theo)",
    # ── Nhà thuốc ───────────────────────────────────────────────────────────
    "pharmacy.dispensed": "Cấp thuốc",
    "pharmacy.lot_assigned": "Gán lô cho thuốc đã giao",
    "visit.surcharge_set": "Tick / sửa giá món kèm dịch vụ (đầu dò)",
    "visit.exam_fee_selected": "Chọn dịch vụ khám (tiền khám)",
    "pharmacy.refused": "Khách không lấy thuốc",
    "pharmacy.line_closed": "Chốt dòng thuốc",
    "pharmacy.adjusted": "Điều chỉnh tồn kho",
    "pharmacy.discarded": "Huỷ thuốc",
    "pharmacy.drug_mapped": "Xác định thuốc kho cho dòng đơn",
    "pharmacy.purchase_qty_set": "Khai số lượng khách mua",
    "pharmacy.allocated": "Chọn lô cho dòng thuốc",
    "pharmacy.allocation_released": "Bỏ lô đã chọn",
    "pharmacy.allocation_moved": "Đổi lô đang giữ cho lần chờ xác minh",
    "pharmacy.undelivered_cancelled": "Huỷ phần thuốc đã bán chưa giao",
    "pharmacy.drug_returned": "Khách trả thuốc (chưa quyết xử lý)",
    # ── Hồ sơ bệnh nhân ─────────────────────────────────────────────────────
    "patient.created": "Tạo hồ sơ bệnh nhân",
    "patient.uu_tien_changed": "Đổi dấu khách ưu tiên",
    "patient.updated": "Sửa hồ sơ khách",
    "clinic_config.service_form": "Quản lý đổi phiếu khám của dịch vụ",
    "clinic_config.room_floor": "Quản lý đổi tầng phòng",
    "clinic_config.room_created": "Quản lý thêm phòng",
    "clinic_config.room_renamed": "Quản lý đổi tên phòng",
    "clinic_config.room_active": "Quản lý bật/tắt phòng",
    "clinic_config.room_flags": "Quản lý đổi phòng đối tác / tạm ngừng nhận khách",
    "clinic_config.location_created": "Quản lý thêm cơ sở",
    "clinic_config.location_updated": "Quản lý sửa cơ sở",
    "clinic_config.service_type_created": "Quản lý thêm loại khám",
    "clinic_config.service_type_updated": "Quản lý sửa loại khám",
    "clinic_config.room_nodes": "Quản lý đổi bước phòng phục vụ",
    "clinic_config.staff_nodes": "Quản lý đổi bước nhân sự làm được",
    "clinic_config.thu_ky_bac_si": "Quản lý phân thư ký theo bác sĩ",
    "queue.reordered": "Lễ tân đổi thứ tự khám",
    "visit.doctor_reassigned": "Trưởng ca chuyển bác sĩ giữa lượt",
    "visit.theo_doi_thu_thuat": "Bác sĩ quyết theo dõi sau thủ thuật",
    "service_order.removed": "Bác sĩ bỏ tích dịch vụ khỏi chỉ định",
    "ultrasound.assigned": "Giao bác sĩ thực hiện siêu âm",
    "staff.account_tao": "Tạo tài khoản đăng nhập nhân sự",
    "staff.account_doi_mat_khau": "Đặt lại mật khẩu nhân sự",
    "staff.account_doi_ten_dang_nhap": "Đổi tên đăng nhập nhân sự",
    "staff.account_thu_hoi": "Thu hồi tài khoản đăng nhập nhân sự",
    "patient_link.created": "Liên kết hai bệnh nhân",
    "clinical_data_consent.granted": "Đồng ý chia sẻ hồ sơ",
    "clinical_data_consent.revoked": "Thu hồi đồng ý chia sẻ",
    # ── Khám & bệnh án ──────────────────────────────────────────────────────
    "clinical_record.saved": "Lưu bệnh án",
    "clinical_record.opened": "Mở hồ sơ y khoa",
    "prescription.draft_approved": "Bác sĩ duyệt đơn thuốc thư ký nhập",
    "prescription.corrected": "Bác sĩ đính chính đơn thuốc",
    # Lát CD-01 (23/09): một lệnh thay hai bước; bác sĩ và thư ký y khoa ngang
    # quyền. Ba mã draft_* bên dưới là đường cũ, còn sống tới khi hết bản nháp.
    "service_order.placed": "Chỉ định dịch vụ",
    "service_order.draft_saved": "Thư ký nhập chỉ định nháp",
    "service_order.draft_approved": "Bác sĩ duyệt chỉ định thư ký nhập",
    "service_order.draft_discarded": "Bỏ chỉ định nháp",
    "tep_ket_qua.cho_phep_gui": "Bác sĩ cho phép gửi tệp kết quả",
    "clinical_record.vitals_saved": "Ghi sinh hiệu",
    "clinical_form.saved": "Lưu phiếu khám chuyên khoa",
    "clinical.signed": "Ký bệnh án (cách cũ, trước 23/09/2026)",
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
    # Tên cũ (trước 22/09/2026) — giữ để đọc lịch sử.
    "payment.recorded": "Ghi nhận thanh toán",
    "payment.confirmed": "Đã nhận tiền",
    "payment.pending_verification": "Ghi chuyển khoản/QR chờ xác minh",
    "payment.pending_cancelled": "Huỷ lần chuyển khoản/QR chờ xác minh",
    "payment.reconciliation_needed": "Đã nhận tiền nhưng hoá đơn đổi — cần đối soát",
    "payment.sale_not_applied": "Đã nhận tiền nhưng chưa ghi bán thuốc — cần đối soát",
    "payment.drug_return_needed": (
        "Huỷ phiếu sau khi đã giao thuốc — cần xử lý trả thuốc"
    ),
    "payment.voided": "Huỷ phiếu thanh toán",
    "payment.refunded": "Hoàn tiền cho khách",
    "payment.refund_pending": "Hoàn tiền chuyển khoản — chờ xác nhận",
    "payment.refund_failed": "Hoàn tiền không thành",
    "payment.refund_cancelled": "Huỷ yêu cầu hoàn tiền",
    # ── CSKH ────────────────────────────────────────────────────────────────
    "cskh_action.created": "Tạo việc chăm sóc khách",
    "cskh_log.followup_call": "Gọi chăm sóc khách",
    "cskh.tuong_tac": "Ghi lần liên hệ với khách",
    # Rút lại một lần chạm bấm nhầm. Dòng sổ KHÔNG bị xoá — nó chỉ thôi được
    # tính (`tuong_tac_cskh.huy_luc`), nên nhãn phải nói "rút lại", không phải
    # "xoá": người đọc Lịch sử thao tác cần biết bản ghi vẫn còn đó.
    "cskh.tuong_tac_hoan_tac": "Rút lại một lần liên hệ đã ghi",
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
    "staff.capability_granted": "Cấp quyền năng lực nhân sự",
    "staff.capability_revoked": "Thu hồi quyền năng lực nhân sự",
    # ── Luồng khám lát 1 (20260911000001) ────────────────────────────────
    "vitals.recorded": "Đo sinh hiệu trước khám",
    "visit.routed": "Xác định bước tiếp theo của lượt khám",
    "consult.started": "Bác sĩ nhận khách vào phiên khám",
    "consult.note_saved": "Ghi chú phiên khám",
    "orders.drafted": "Thư ký ghi nháp chỉ định",
    "orders.authorized": "Bác sĩ duyệt chỉ định",
    "consult.completed": "Kết thúc phiên khám",
    "dispatch.assigned": "Xếp phòng cho chỉ định",
    # Lifecycle v1 (Slice 4): điều phối chính thức theo routing_revision.
    "service.routed": "Xếp phòng chính thức cho dịch vụ",
    "service.routing_invalidated": "Phân phòng mất hiệu lực — cần điều phối lại",
    "service.room_transferred": "Trưởng ca chuyển phòng khi dịch vụ đang làm",
    "service.started": "Người thực hiện nhận khách làm dịch vụ",
    "service.performed": "Làm xong dịch vụ",
    "service.not_performed": "Không làm được dịch vụ",
    "service_selection.confirmed": "Khách chốt làm / không làm chỉ định",
    "result.approved": "Bác sĩ duyệt kết quả, cho phép gửi khách",
    "queue.called": "Gọi khách vào phòng",
    "vitals.called": "Điều dưỡng gọi khách vào đo sinh hiệu",
    "vitals.started": "Điều dưỡng bắt đầu đo sinh hiệu",
    "partner.awaiting_documents": "Đối tác đã nhận mẫu — việc đối tác xong",
    "partner.sample_noted_again": "Bấm lại “Đã lấy mẫu” — chỉ ghi lại (đã ghi nhận)",
    "review.ready": "Đủ điều kiện quay lại bác sĩ đọc kết quả",
    # Slice 1 (18/09/2026): kết quả / theo dõi trên rail mới.
    "review.skipped": "Không cần đọc lại (bác sĩ đã miễn hoặc chuyển theo dõi hết)",
    "requirement.waived": "Bác sĩ miễn một yêu cầu trước khi đọc kết quả",
    "requirement.follow_up": "Bác sĩ chuyển kết quả sang theo dõi, khách về trước",
    "follow_up.opened": "Mở việc theo dõi kết quả",
    "pregnancy.created": "Bác sĩ tạo thai kỳ",
    "pregnancy.updated": "Bác sĩ cập nhật thai kỳ",
    "pregnancy.outcome_set": "Bác sĩ ghi kết cục thai kỳ",
    "review.not_ready": "Chưa đủ điều kiện đọc kết quả",
    "tep_ket_qua.xac_nhan": "Xác nhận tệp kết quả",
    "tep_ket_qua.thu_hoi": "Thu hồi tệp kết quả",
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
    "api:tu-van": "Bàn khám tư vấn — nội dung tư vấn",
    "api:phu-thu": "Quầy thu dịch vụ — món kèm (đầu dò)",
    "api:phi-kham": "Bàn khám / quầy thu — chọn dịch vụ khám",
    "api:quay-thuoc": "Quầy thu tiền thuốc — chỉnh đơn bán",
    "api:queue-reorder": "Hàng chờ tiếp nhận — đổi thứ tự khám",
    "api:theo-doi-thu-thuat": "Bác sĩ — theo dõi sau thủ thuật",
    "api:ket-qua": "Kết quả xét nghiệm về",
    "api:staff-account": "Quản lý tài khoản nhân sự",
    "api:clinic-config": "Cấu hình phòng khám",
    "api:patient-edit": "Sửa hồ sơ khách",
    "api:reception": "Quầy tiếp nhận",
    "api:pharmacy": "Nhà thuốc",
    "api:staff": "Quản lý nhân sự",
    "api:staff-capability": "Quản lý nhân sự — Phân quyền",
    "api:roster": "Lịch làm việc",
    "api:clinic-settings": "Cấu hình phòng khám",
    "api:luot-kham": "Màn lượt khám",
    "api:chi-dinh": "Bàn khám — chỉ định dịch vụ",
    "api:day-noi": "Cài đặt — dây nối nghiệp vụ",
    "api:thai-ky": "Bàn khám — Thai kỳ",
    # Thai kỳ ghi theo hai ô kinh cuối / dự kiến sinh của phiếu Sản khoa v5.
    "api:phieu-kham": "Bàn khám — Phiếu khám",
    "api:tep-ket-qua:xac-nhan": "Xác nhận tệp kết quả",
    "api:tep-ket-qua:thu-hoi": "Thu hồi tệp kết quả",
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
    "tep_ket_qua": "Tệp kết quả",
    "appointment": "Lịch hẹn",
    "patient": "Khách hàng",
    "clinic_patient": "Khách hàng",
    "patient_link": "Liên kết hồ sơ",
    "slot_hold": "Giữ chỗ khung giờ",
    "visit": "Lượt khám",
    "consultation": "Phiên khám",
    # Lifecycle v1 (Slice 4): sự kiện điều phối gắn vào chính chỉ định.
    "service_order": "Chỉ định dịch vụ",
    # Phiếu kết quả là đối tượng riêng (Form Template Engine, 23/09) — không
    # phải một mặt của chỉ định, nên nó có tên riêng trên màn nhật ký.
    "form_instance": "Phiếu kết quả",
    # KẾT QUẢ tách khỏi PHIẾU: phiếu là tờ giấy người ta điền, kết quả là thứ
    # bác sĩ đọc và có thể được sửa lại về sau. Hai vòng đời, hai chuỗi số —
    # nên trên nhật ký cũng phải là hai tên khác nhau.
    "ket_qua": "Kết quả cận lâm sàng",
    "pregnancy": "Thai kỳ",
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
    "payment_cycle": "Lần thu tiền",
    "payment_refund": "Hoàn tiền",
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
        EVENT_LABELS.get(event_type)
        or WORK_ITEM_LABELS.get(event_type)
        or _nhan_danh_muc(event_type)
        or event_type
    )


def _nhan_danh_muc(event_type: str) -> str | None:
    """Nhãn trong danh mục sự kiện nền (`events/catalogue.DANH_MUC[ma].nhan`) —
    sự kiện phát qua `emit_event` đã có tên ở đó, không cần chép tay sang đây."""
    from clinicai.events.catalogue import DANH_MUC

    su_kien = DANH_MUC.get(event_type)
    return su_kien.nhan if su_kien is not None and su_kien.nhan else None


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
