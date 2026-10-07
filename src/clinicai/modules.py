"""Bản khai của từng module — "ổ cắm" của LEGO.

VÌ SAO CÓ FILE NÀY. "Mọi thứ là LEGO" chỉ là khẩu hiệu nếu không ai kiểm được.
Một viên LEGO cắm được vì nó có **chuẩn chân cắm**; ở đây chuẩn ấy là: mỗi module
khai ra ĐÚNG những gì nó nhận vào và nhả ra.

    NHẬN VÀO   lệnh (commands) · sự kiện nó nghe (nghe)
    NHẢ RA     sự kiện nó phát (phat) · việc có người chịu trách nhiệm (viec)
               · màn/bảng đọc nó dựng (projection)
    GIỮ RIÊNG  bảng state của chính nó (bang)
    QUYỀN      capability mà lệnh của nó đòi

Bài kiểm CI đọc bản khai này và so với thực tế trong code: sự kiện nào phát ra mà
không module nào nhận là của mình, bên nghe nào chưa ai khai, quyền nào mồ côi —
đỏ ngay. Không có bài kiểm ấy thì sau ba tháng bản khai thành một tờ giấy đẹp
treo tường, còn code đi đường khác.

LUẬT CẮM (chat #128)
    * Module A không UPDATE bảng state của module B.
    * Muốn B đổi thì gửi LỆNH của B, hoặc phát sự kiện để B tự nghe.
    * Thêm bên nghe mới = thêm một dòng ở đây, KHÔNG sửa module phát.
    * Thêm tính năng mà phải sửa xuyên nhiều module không liên quan
      = thiết kế LEGO đang thủng, dừng lại và xem lại đường cắm.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CongDoc:
    """Một CỔNG ĐỌC góp vào hồ sơ khám (cách B, 24/09/2026 — `ho_so/cong_doc.py`).

    `ham` = "goi.module:ten_ham", hàm `async (conn, NguCanhHoSo) -> dict` chỉ đọc
    bảng của CHÍNH module này và chỉ điền đúng các khoá trong `khoa`."""

    ten: str
    ham: str
    khoa: Sequence[str]


@dataclass(frozen=True)
class Module:
    ma: str
    ten: str
    #: Lệnh module nhận (tên nghiệp vụ, không phải đường HTTP).
    lenh: Sequence[str] = field(default_factory=list)
    #: Sự kiện module PHÁT. Phải khớp `source_module` trong danh mục sự kiện.
    phat: Sequence[str] = field(default_factory=list)
    #: Sự kiện module NGHE, kèm tên bên nhận đã đăng ký.
    nghe: Sequence[str] = field(default_factory=list)
    #: Tên bên nhận (consumer) mà module này sở hữu.
    ben_nhan: Sequence[str] = field(default_factory=list)
    #: Bảng state module tự giữ. Module khác KHÔNG ghi vào đây.
    bang: Sequence[str] = field(default_factory=list)
    #: Màn/bảng đọc module dựng ra từ sự kiện.
    projection: Sequence[str] = field(default_factory=list)
    #: Loại việc không được rơi mà module mở ra.
    viec: Sequence[str] = field(default_factory=list)
    #: Quyền mà lệnh của module đòi.
    quyen: Sequence[str] = field(default_factory=list)
    #: Lệnh của module KHÁC mà module này được phép gọi thẳng, dạng
    #: "module.Lenh". Gọi thẳng KHÔNG bị cấm — nhưng phải khai ra, để đọc bản
    #: khai là biết hết đường dây, không phải đi dò trong code.
    goi_dong_bo: Sequence[str] = field(default_factory=list)
    #: Cổng đọc góp phần của module vào HỒ SƠ KHÁM. Thêm module có dữ liệu y
    #: khoa = khai thêm cổng ở đây; hàm ráp hồ sơ không phải sửa.
    cong_doc: Sequence[CongDoc] = field(default_factory=list)


MODULE: dict[str, Module] = {
    m.ma: m
    for m in (
        Module(
            ma="service_order",
            ten="Chỉ định dịch vụ",
            # CarryOverUnfinishedOrders: khối Hành trình gọi lúc check-in (H2) —
            # chỉ định chưa làm ĐI THEO KHÁCH sang lượt mới.
            lenh=[
                "PlaceServiceOrders",
                "CarryOverUnfinishedOrders",
                "SetServiceOrderRequired",
                # Làm thêm tại quầy (01/10/2026): lễ tân / người đo sinh hiệu
                # tick "+ dịch vụ" theo danh sách quản lý quản.
                "AddDeskService",
                "RemoveDeskService",
                "ConfigureDeskServices",
                # Hoàn tác (01/10/2026): bỏ chỉ định sai chỗ — chưa thu thì hoá
                # đơn quầy tự bớt, đã thu thì thành tiền thừa ở quầy.
                "CancelServiceOrder",
            ],
            phat=[
                "service_order.placed",
                "service_order.carried_over",
                "service_order.required_changed",
                "service_order.required_changed",
                "service_order.desk_added",
                "service_order.desk_removed",
                "service_order.cancelled",
            ],
            bang=["service_order", "lam_them_tai_quay"],
            quyen=["clinical.order.place"],
        ),
        Module(
            ma="vat_tu",
            ten="Bán thêm vật tư",
            # Quầy Thu tiền dịch vụ (C13, 01/10/2026): vật tư khách mua thêm vào
            # hoá đơn DỊCH VỤ; hàng cần quản lý duyệt (Mirena) ghi người duyệt.
            lenh=["AddSupplyToBill", "SetSupplyQuantity", "RemoveSupply"],
            phat=["visit.supply_changed"],
            bang=["luot_vat_tu", "vat_tu_goi_y"],
        ),
        Module(
            ma="phi_kham",
            ten="Dịch vụ khám (tiền khám)",
            # Tick dịch vụ khám con theo mã KiotViet (28/09/2026); từ C18
            # (02/10/2026) mỗi lần tick / bỏ tick là một sự kiện lên Hành trình.
            lenh=["ChonDichVuKham"],
            phat=["visit.exam_service_changed"],
            bang=["luot_phi_kham"],
        ),
        Module(
            ma="service_selection",
            ten="Khách chọn dịch vụ",
            # SetDeferPayment (30/09/2026 tối): tick / bỏ tick "Làm trước – thu
            # sau" của lượt — bật thì chốt luôn chỉ định chờ quyết (cùng phần ghi
            # của ConfirmServiceSelection).
            lenh=["ConfirmServiceSelection", "SetDeferPayment"],
            phat=[
                "service_selection.confirmed",
                "visit.defer_payment_set",
                "visit.defer_payment_cleared",
            ],
            bang=["service_selection_state"],
            # Từ 23/09: hỏi capability trong chính giao dịch của lệnh, không
            # còn mượn ánh xạ vai của người thu tiền.
            quyen=["service_selection.confirm"],
        ),
        Module(
            ma="service_routing",
            ten="Điều phối khách",
            # AutoAssignPaidOrders: khối Hành trình gọi sau khi thu tiền (H4) —
            # cùng lõi với AssignServiceRoom, bằng quyền của người vừa thu.
            lenh=[
                "AssignServiceRoom",
                "InvalidateServiceRouting",
                "AutoAssignPaidOrders",
                # Phòng khách chọn ở quầy trước khi thu (24/09/2026) — H4 dùng.
                "PlanServiceRoom",
                # Trưởng ca chuyển phòng khi dịch vụ đang làm (29/09/2026).
                "TransferInProgressService",
                # Nhận khách tại phòng (07/10/2026): Nhận + hoàn tác Nhận.
                "ReceiveAtRoom",
                "UndoReceiveAtRoom",
            ],
            # Huỷ xếp phòng là sự thật nghiệp vụ, không chỉ là dòng nhật ký:
            # phòng mất thì phải có người xếp lại, và người ấy nhận việc qua
            # sự kiện này (ChatGPT tin 112).
            phat=[
                "service.routed",
                "service.routing_invalidated",
                "service.room_transferred",
                "service.doctor_chosen",
                "service.room_released",
                "service.room_receive_undone",
                "service.room_guided",
            ],
            bang=["queue_entry"],
            quyen=[
                "service.routing.view",
                "service.routing.assign",
                "service.routing.invalidate",
                "dispatch.manage",
            ],
        ),
        Module(
            ma="execution",
            ten="Thực hiện dịch vụ",
            lenh=[
                "StartService",
                "CompleteService",
                "MarkServiceNotPerformed",
                "InterruptService",
                "PrepareServiceRetry",
                # V4 (30/09/2026): làm không theo thứ tự. "Chuyển khách sang
                # đây" là StartService kèm giai_phong (cùng giao dịch dừng lần
                # làm ở phòng kia); huỷ lần Bắt đầu bấm nhầm là lệnh riêng.
                "CancelMistakenStart",
                # Hoàn tác "Xong" (01/10/2026) — lần làm về lại đang làm.
                "UndoServiceCompletion",
            ],
            phat=[
                "service.started",
                "service.completed",
                "service.not_performed",
                "service.interrupted",
                "service.retry_prepared",
                "service.patient_moved",
                "service.start_cancelled",
                "service.completion_undone",
            ],
            bang=["service_execution_attempt"],
            quyen=[
                "service.execute.start",
                "service.execute.complete",
                "service.execute.not_performed",
                "service.execute.interrupt",
                "service.execute.retry",
            ],
        ),
        Module(
            ma="result",
            ten="Biểu mẫu kết quả",
            lenh=[
                "OpenForm",
                "SaveFormDraft",
                "CompleteForm",
                "ReopenForm",
                # Hoàn tác (01/10/2026) — thu hồi lần bác sĩ duyệt kết quả.
                "RevokeResultApproval",
            ],
            # BA sự kiện, MỘT nút bấm (ChatGPT tin 156, Tuyền tin 157). Kết quả
            # là vòng đời riêng của phiếu: ready → corrected → (sau này)
            # reviewed, released. Thêm bước mới vào chuỗi ấy không đụng module
            # nào khác — đó là chỗ để cắm miếng lego tiếp theo.
            phat=[
                "result_form.completed",
                "result.ready",
                "result.corrected",
                "result.reviewed",
                "result.viewed",
                "result.approval_revoked",
            ],
            bang=["form_instance"],
            # Xác nhận tệp kết quả (B2) và bác sĩ duyệt kết quả (B3) cũng là
            # vòng đời kết quả — cùng module, không mở module mới cho hai lệnh.
            quyen=[
                "result.form.fill",
                "result.file.confirm",
                "result.review.approve",
                "result.file.delete",
            ],
            # Điền xong phiếu mà dịch vụ còn đang làm dở thì đóng hộ — nhưng
            # bằng LỆNH của module Thực hiện, không thò tay vào bảng của nó.
            goi_dong_bo=["execution.CompleteService"],
        ),
        Module(
            ma="catalogue",
            ten="Danh mục & biểu mẫu",
            lenh=[
                "BindResultTemplate",
                "UnbindResultTemplate",
                "PublishFormVersion",
            ],
            bang=["ket_qua_mau", "dich_vu_mau_ket_qua", "form_definition"],
            quyen=[
                "catalogue.result_template.manage",
                "catalogue.form_template.edit",
                "catalogue.form_template.publish",
                "config.wiring.manage",
                "price.service.manage",
                "config.clinic.manage",
            ],
        ),
        Module(
            ma="permission",
            ten="Phân quyền",
            lenh=[
                "GrantWorkPack",
                "RevokeWorkPack",
                "ApplyRolePreset",
                # Nhóm quyền mẫu là DỮ LIỆU, quản lý sửa được mà không cần
                # deploy. Nhóm KHÔNG phải quyền — quyền thật ở capability_grant.
                "SaveRolePreset",
                "RemoveRolePreset",
                # Phân quyền theo KỸ NĂNG (28/09/2026): tick kỹ năng cho người =
                # bật/tắt các lego của kỹ năng ấy qua GrantWorkPack/RevokeWorkPack.
                "SetStaffSkill",
                "OpenClinicalShiftException",
                "CancelClinicalShiftException",
            ],
            phat=[
                "capability.granted",
                "capability.revoked",
                "clinical_shift.exception_opened",
                "clinical_shift.exception_cancelled",
            ],
            bang=[
                "capability_grant",
                "quyen_preset",
                "ky_nang",
                "nhan_su_ky_nang",
                "ngoai_le_ca_truc",
            ],
            quyen=["permission.manage", "staff.manage", "account.manage"],
        ),
        Module(
            ma="journey",
            ten="Hành trình lượt khám",
            # Không có lệnh: đây là module CHỈ NGHE. Thêm nó không đụng ai.
            nghe=[
                "partner.order_received",
                "partner.payment_recorded",
                "partner.payment_voided",
                "visit.checked_in",
                "vitals.started",
                "vitals.recorded",
                "prescription.saved",
                "medicine.counter_changed",
                "medicine.declined",
                "service_selection.confirmed",
                "service_order.placed",
                "service_order.desk_added",
                "service_order.desk_removed",
                "service.started",
                "service.completed",
                "service.not_performed",
                "service.interrupted",
                "service.retry_prepared",
                "service.patient_moved",
                "service.start_cancelled",
                # Hoàn tác (01/10/2026) — lên dòng thời gian của lượt.
                "service.completion_undone",
                "service_order.cancelled",
                "consultation.reopened",
                "visit.reopened",
                "result.approval_revoked",
                "service.routing_invalidated",
                "result_form.completed",
                "result.ready",
                "result.corrected",
                "visit.routed",
                "visit.exam_completed",
                "consultation.started",
                "consultation.handed_over",
                "consultation.completed",
                "service.routed",
                "service.room_transferred",
                "service.doctor_chosen",
                "service.room_released",
                "service.room_receive_undone",
                "service.room_guided",
                "consultation.resumed",
                "service_order.carried_over",
                "service_order.required_changed",
                "payment.service_collected",
                "payment.medicine_collected",
                # Công nợ khi khách về (01/10/2026).
                "cong_no.ghi",
                "cong_no.huy",
                "cong_no.da_thu",
                "medicine.dispensed",
                "result_file.uploaded",
                "result_file.confirmed",
                "result_file.revoked",
                "result_file.deleted",
                "result_file.restored",
                "result_file.viewed",
                "result_file.sent_to_patient",
                "result.reviewed",
                "result.viewed",
                "lab_result.arrived",
                "appointment.booked",
                "appointment.rescheduled",
                "appointment.service_switched",
                "appointment.cancelled",
                "appointment.no_show",
                "appointment.confirmed_by_call",
                "visit.checked_out",
                "visit.left_early",
                "payment.refunded",
                "payment.method_changed",
                "payment.collection_undone",
                "followup.scheduled",
                "partner.sample_collected",
                "partner.sample_received",
                "visit.defer_payment_set",
                "visit.defer_payment_cleared",
                # Bán thêm vật tư ở quầy thu dịch vụ (C13, 01/10/2026).
                "visit.supply_changed",
                # Dịch vụ khám con tick / bỏ tick (C18, 02/10/2026).
                "visit.exam_service_changed",
            ],
            ben_nhan=["dong_thoi_gian_luot"],
            projection=["luot_dong_thoi_gian"],
        ),
        Module(
            ma="trach_nhiem",
            ten="Trách nhiệm không được rơi",
            quyen=["worklist.handle"],
            # Module CHỈ NGHE. Không lệnh, không state riêng ngoài việc nó mở.
            # Có dùng hẹn giờ (`hen_gio`) để kiểm lại khi tới hạn — hẹn ghi
            # trong CÙNG giao dịch với việc.
            nghe=[
                "service.not_performed",
                "service.interrupted",
                "service.routing_invalidated",
            ],
            ben_nhan=["trach_nhiem_dich_vu"],
            viec=[
                "OPS-ROUTING-REASSIGN",
                "OPS-SERVICE-INTERRUPTED",
                "OPS-FINANCIAL-RESOLUTION",
            ],
        ),
        Module(
            ma="reception",
            ten="Tiếp đón",
            # ReopenVisit (01/10/2026): hoàn tác check-out / về giữa chừng.
            lenh=["CheckInPatient", "CheckOutPatient", "ReopenVisit"],
            phat=[
                "visit.checked_in",
                "visit.checked_out",
                "visit.left_early",
                "visit.reopened",
            ],
            quyen=["reception.checkin.perform"],
        ),
        Module(
            ma="vitals",
            ten="Sinh hiệu",
            lenh=["StartVitals", "RecordVitals"],
            phat=["vitals.started", "vitals.recorded"],
            quyen=["vitals.measure"],
            bang=["vital_measurement"],
            cong_doc=[
                CongDoc(
                    "Sinh hiệu mới nhất của lượt",
                    "clinicai.services.sinh_hieu_service:sinh_hieu_cho_ho_so",
                    ["vital_latest"],
                ),
            ],
        ),
        Module(
            ma="hanh_trinh",
            ten="Hành trình lượt khám (Process Manager)",
            # Giữ luật THỨ TỰ khách đi (thesis §9): nghe sự thật, gửi LỆNH của
            # module khác. Không ghi bảng của ai. Dây H1…H8 —
            # docs/BAN-DO-DAY-NOI-LEGO.md.
            phat=["visit.routed"],
            nghe=[
                "visit.checked_in",
                "vitals.recorded",
                "consultation.handed_over",
                "payment.service_collected",
                "payment.medicine_collected",
                "service_selection.confirmed",
                "service_order.desk_added",
                "visit.defer_payment_set",
                "visit.checked_out",
                "visit.left_early",
                "service.completed",
                "partner.sample_collected",
                "appointment.service_switched",
            ],
            ben_nhan=["hanh_trinh_luot_kham"],
            goi_dong_bo=[
                "consultation.RouteAfterCheckIn",
                "consultation.RerouteAfterServiceSwitch",
                "consultation.OpenIntakeQueue",
                "consultation.HandToPrimaryDoctor",
                "service_order.CarryOverUnfinishedOrders",
                "service_routing.AutoAssignPaidOrders",
            ],
        ),
        Module(
            ma="consultation",
            ten="Khám bệnh",
            # Đường khám chính hỏi QUYỀN, không hỏi vai (CORE-B3, 23/09/2026).
            # Hoàn tất KHÔNG khoá hồ sơ (Tuyền chốt 23/09) — finalize chỉ là
            # mốc "khám xong", mở "Cho phép CSKH gửi".
            lenh=[
                "StartConsultation",
                "CompleteConsultation",
                "SaveConsultationNote",
                "SaveClinicalRecord",
                "ReleaseRecord",
                "StartIntake",
                "CompleteIntake",
                # Ô chữ tự do của bác sĩ tư vấn (24/09/2026) → mục "mang sang".
                "RecordIntakeNote",
                # Lệnh nội bộ khối Hành trình gọi (xếp hàng theo đường đi).
                "RouteAfterCheckIn",
                # Đổi dịch vụ khám sau check-in → xếp lại hàng đầu tiên (V5).
                "RerouteAfterServiceSwitch",
                "OpenIntakeQueue",
                "HandToPrimaryDoctor",
                # Hoàn tác Khám xong / Xong tư vấn (01/10/2026).
                "ReopenConsultation",
            ],
            phat=[
                "consultation.started",
                "consultation.resumed",
                "consultation.handed_over",
                "consultation.completed",
                "consultation.reopened",
                "followup.scheduled",
                "prescription.saved",
            ],
            quyen=[
                "clinical.intake.perform",
                "clinical.consult.perform",
                "clinical.record.write",
                "clinical.consult.finalize",
            ],
            bang=["clinical_record", "patient_medical_profile", "prescription"],
            cong_doc=[
                CongDoc(
                    "Tiền sử & hồ sơ y tế",
                    "clinicai.services.clinical_record_service:ho_so_y_te_cho_ho_so",
                    ["profile"],
                ),
                CongDoc(
                    "Bệnh án của lượt",
                    "clinicai.services.clinical_record_service:benh_an_cho_ho_so",
                    ["visit", "draft", "revision", "prescription_draft"],
                ),
                CongDoc(
                    "Các lượt khám trước",
                    "clinicai.services.clinical_record_service:lich_su_cho_ho_so",
                    ["history_raw"],
                ),
                CongDoc(
                    "Đơn thuốc của lượt",
                    "clinicai.services.clinical_prescription_service:don_thuoc_cho_ho_so",
                    ["prescriptions"],
                ),
            ],
        ),
        Module(
            ma="payment",
            ten="Thu tiền dịch vụ",
            lenh=["CollectServicePayment"],
            # Tiền thật đã nhận (tiền mặt, hoặc chuyển khoản đã xác minh) —
            # khối Hành trình nghe để xếp phòng (H4). Tiền thuốc: dòng thời gian.
            phat=[
                "payment.service_collected",
                "payment.medicine_collected",
                "payment.refunded",
                # Đổi hình thức sau khi thu (V7) — không phải huỷ.
                "payment.method_changed",
                # Hoàn tác lần thu (01/10/2026) — thu nhầm, lượt về chưa thu.
                "payment.collection_undone",
                # Bản thanh toán cuối: dòng thuốc khách bỏ / lấy bớt.
                "medicine.declined",
            ],
            bang=[
                "payment_cycle",
                "payment_bill_line",
                "payment_cycle_doi_hinh_thuc",
                "payment_cycle_phan",
                "anh_chuyen_khoan",
            ],
            quyen=["payment.service.collect", "payment.medicine.collect"],
        ),
        Module(
            ma="result_file",
            ten="Tệp kết quả",
            # Nhóm 3 (24/09/2026): tải / xác nhận / mở (tự ghi đã xem) / đánh dấu
            # đã gửi khách. Chuông KHÔNG còn gọi thẳng — khối Chuông nghe.
            lenh=[
                "UploadResultFile",
                "ConfirmResultFile",
                "OpenResultFile",
                "MarkSent",
                "RevokeResultFile",
                # V9 (30/09/2026): xoá mềm + khôi phục 30 ngày.
                "DeleteResultFile",
                "RestoreResultFile",
            ],
            phat=[
                "result_file.uploaded",
                "result_file.confirmed",
                "result_file.revoked",
                "result_file.deleted",
                "result_file.restored",
                "result_file.viewed",
                "result_file.sent_to_patient",
            ],
            bang=["tep_ket_qua"],
        ),
        Module(
            ma="vong_doc",
            ten="Vòng đọc kết quả + khép lượt",
            # 24/09/2026: kết quả/dịch vụ xong ở BẤT KỲ lối nào (phòng, phiếu,
            # đối tác, tệp) → mở chỗ chờ "có kết quả" cho bác sĩ chính, khép
            # phần khám khi hết việc. Trước đây chỉ lối gọi thẳng mới chạy.
            # Luật vòng đọc + điều kiện khép vẫn nằm trong khối Khám (đợt bóc
            # sau chuyển hẳn sang đây); khối này là CỬA sự kiện duy nhất.
            phat=["visit.exam_completed"],
            nghe=[
                "service_selection.confirmed",
                "service.completed",
                "service.not_performed",
                "partner.sample_collected",
                "partner.sample_received",
                "result.ready",
                "result.corrected",
                "result_file.uploaded",
                "result_file.confirmed",
                "result_file.revoked",
                "result_file.deleted",
                "result_file.restored",
            ],
            ben_nhan=["vong_doc_luot_kham"],
            bang=["review_round"],
        ),
        Module(
            ma="chuong",
            ten="Chuông thông báo",
            # CHỈ NGHE. Ai nhận chuông cho sự kiện nào là DỮ LIỆU
            # (`day_nhan_thong_bao`) — quản lý chỉnh trên màn (nhóm 5).
            nghe=[
                "result_file.uploaded",
                "result_file.confirmed",
                "result.ready",
                "result.corrected",
                "lab_result.arrived",
                "partner.order_received",
            ],
            ben_nhan=["chuong_thong_bao"],
            bang=["day_nhan_thong_bao"],
        ),
        Module(
            ma="booking",
            ten="Đặt lịch",
            lenh=[
                "BookAppointment",
                "RescheduleAppointment",
                "CancelAppointment",
                "MarkNoShow",
                "ConfirmByCall",
                # Đổi dịch vụ khám ở menu ⋯ dòng lịch hẹn (V5, 30/09/2026).
                "SwitchExamService",
            ],
            phat=[
                "appointment.booked",
                "appointment.rescheduled",
                "appointment.service_switched",
                "appointment.cancelled",
                "appointment.no_show",
                "appointment.confirmed_by_call",
            ],
            bang=["appointment", "appointment_doi_lich"],
            quyen=["booking.create", "booking.manage"],
        ),
        Module(
            ma="doi_tac",
            ten="Đối tác",
            quyen=["partner.work"],
            lenh=[
                "MarkSampleCollected",
                "MarkAwaitingDocuments",
                # Đối tác tự thu (27/09/2026): ghi nhận / huỷ ghi nhận đã thu.
                "RecordPartnerPayment",
                "VoidPartnerPayment",
            ],
            phat=[
                "partner.sample_collected",
                "partner.sample_received",
                "partner.order_received",
                "partner.payment_recorded",
                "partner.payment_voided",
            ],
            # Nhận việc bằng sự kiện (24/09/2026): khách chốt làm (đối tác tự
            # thu — 27/09) / đã thu tiền (đối tác tự lấy mẫu) / dịch vụ lấy mẫu
            # xong (điều dưỡng lấy) → sang bàn đối tác.
            nghe=[
                "service_selection.confirmed",
                "visit.defer_payment_set",
                "payment.service_collected",
                "service.completed",
            ],
            ben_nhan=["doi_tac_nhan_viec"],
            bang=["doi_tac_nhan_viec", "doi_tac_thanh_toan"],
        ),
        Module(
            ma="cskh",
            ten="Chăm sóc khách hàng",
            quyen=["crm.manage", "patient.create", "patient.list.view"],
            lenh=["LogContact"],
            phat=["patient.contacted"],
            # Sổ ghi chú chung về khách (27/09/2026) — khung phải CSKH/Tiếp đón.
            bang=["tuong_tac_cskh", "ghi_chu_khach"],
        ),
        Module(
            ma="lab",
            ten="Xét nghiệm nhập tay",
            lenh=["EnterLabResult"],
            phat=["lab_result.arrived"],
            bang=["lab_result"],
            cong_doc=[
                CongDoc(
                    "Xét nghiệm gần nhất",
                    "clinicai.services.lab_order_service:xet_nghiem_cho_ho_so",
                    ["labs"],
                ),
            ],
        ),
        Module(
            ma="thai_ky",
            ten="Theo dõi thai kỳ",
            bang=["pregnancy"],
            cong_doc=[
                CongDoc(
                    "Thai kỳ gần nhất",
                    "clinicai.services.thai_ky_service:thai_ky_cho_ho_so",
                    ["pregnancy"],
                ),
            ],
        ),
        Module(
            ma="pharmacy",
            ten="Quầy thuốc",
            # Tiền thuốc KHÔNG đợi Khám xong (Tuyền 24/09/2026). Hai bản đơn:
            # số bác sĩ kê (quantity_num) và số khách chốt (purchased_qty).
            lenh=[
                "MapDrug",
                "SetPurchasedQty",
                # Quầy chỉnh đơn bán trước khi thu (24/09/2026).
                "AdjustSaleAtCounter",
                "AllocateLots",
                "DispenseMedicine",
                "RefuseLine",
                "CloseLine",
            ],
            phat=["medicine.dispensed", "medicine.counter_changed"],
            bang=["prescription_allocation", "inventory_txn"],
            quyen=["pharmacy.dispense", "pharmacy.view"],
        ),
        # 21 lego (Tuyền 25/09/2026): hai module chỉ-đọc cho lego Báo cáo /
        # Vận hành hệ thống và lego Lịch làm việc.
        Module(
            ma="cong_no",
            ten="Công nợ khách (chặn check-out còn nợ)",
            # Người đứng quầy ghi nợ / huỷ ghi nợ (cửa `reception.checkin.perform`
            # — quyền của khối Tiếp đón). Check-out chỉ ĐỌC bảng này.
            lenh=["GhiNo", "HuyGhiNo"],
            phat=["cong_no.ghi", "cong_no.huy", "cong_no.da_thu"],
            # Thu ở quầy → lượt hết nợ thì khoản ghi nợ chuyển ĐÃ THU.
            nghe=["payment.service_collected", "payment.medicine_collected"],
            ben_nhan=["cong_no"],
            bang=["cong_no"],
            projection=["khach_con_no"],
        ),
        Module(
            ma="van_hanh",
            ten="Vận hành, báo cáo, lịch sử thao tác",
            quyen=["report.view", "ops.view", "audit.view"],
        ),
        Module(
            ma="lich_truc",
            ten="Lịch làm việc",
            # + đổi người trong ca (29/09/2026) và xếp lịch (01/10/2026), khối
            # trưởng ca.
            quyen=["roster.view", "roster.shift.swap", "roster.manage"],
        ),
    )
}


def module_phat(ten_su_kien: str) -> str | None:
    """Module nào chịu trách nhiệm phát sự kiện này."""
    for m in MODULE.values():
        if ten_su_kien in m.phat:
            return m.ma
    return None


def module_cua_ben_nhan(consumer: str) -> str | None:
    for m in MODULE.values():
        if consumer in m.ben_nhan:
            return m.ma
    return None


__all__ = ["MODULE", "CongDoc", "Module", "module_cua_ben_nhan", "module_phat"]
