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
                # Hoàn tác bỏ chỉ định (Khối 2, 06/10/2026).
                "service_order.restored",
            ],
            bang=[
                "service_order",
                "lam_them_tai_quay",
                "lam_them_tai_quay_revision",
                "luot_phu_thu",
                "so_sua_chi_dinh",
            ],
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
            # Người duyệt hàng cần duyệt (G8b, 14/10/2026) — lego, không theo vai.
            quyen=["vat_tu.approve"],
        ),
        Module(
            ma="lieu_trinh",
            ten="Liệu trình điều trị nhiều buổi",
            # 08/10/2026: kế hoạch số buổi + đơn giá chốt; mỗi buổi vẫn là một
            # chỉ định thường — gắn / gỡ buổi bằng trigger Postgres trên
            # service_order (một chỗ cho mọi đường tạo chỉ định).
            lenh=[
                "ProposeTreatmentPlan",
                "AdjustTreatmentPlan",
                "RegisterTreatmentPlan",
                "StopTreatmentPlan",
                "ReopenTreatmentPlan",
                "UndoTreatmentPlanChange",
                "LinkPlanSession",
                "UnlinkPlanSession",
                "SetPlanPrepayment",
                "RemovePlanPrepayment",
            ],
            phat=[
                "lieu_trinh.created",
                "lieu_trinh.revised",
                "lieu_trinh.session_relinked",
                "lieu_trinh.prepay_set",
            ],
            # Buổi làm xong mà liệu trình sắp hết → chuông CSKH (08/10/2026).
            nghe=["service.completed"],
            ben_nhan=["lieu_trinh_sap_het"],
            bang=[
                "lieu_trinh",
                "lieu_trinh_lich_su",
                "lieu_trinh_buoi",
                "lieu_trinh_tra_truoc",
            ],
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
                "service.room_release_undone",
                "service.room_guided",
            ],
            bang=[
                "queue_entry",
                "visit_route",
                "visit_gate_override",
                "dispatch_threshold",
            ],
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
                # LÀM TẠI BÀN KHÁM (07/10/2026): bác sĩ làm chỉ định điều trị
                # ngay ở bàn khám — lần làm `noi_lam = BAN_KHAM`, cùng cửa tiền.
                "StartServiceAtDesk",
                "CompleteServiceAtDesk",
                "CancelDeskStart",
                "UndoDeskCompletion",
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
            bang=[
                "form_instance",
                "ultrasound_record",
                "clinical_form_response",
                "result_correction",
            ],
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
            bang=[
                "ket_qua_mau",
                "dich_vu_mau_ket_qua",
                "form_definition",
                "service_price",
                "service_type",
                "drug_catalog",
            ],
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
                "staff",
                "staff_node",
                "clinic_membership",
                "app_credential",
                "vai_duoc_vao_tram",
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
                "prescription.consultant_marked",
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
                "service_order.restored",
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
                "service.room_release_undone",
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
                "medicine.returned",
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
                "partner.sample_receipt_undone",
                "partner.result_returned",
                "partner.result_return_undone",
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
            bang=[
                "work_item",
                "work_item_event",
                "follow_up_case",
                "nhac_viec_ca_nhan",
            ],
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
            # Lượt khám là của Tiếp đón (mở / đóng lượt). Nhiều khối còn tự ghi
            # cột trạng thái của nó — sổ nợ ghi chéo trong test_luat_cam_ghi_cheo.
            bang=["visit"],
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
                "service_order.restored",
                "visit.defer_payment_set",
                "visit.checked_out",
                "visit.left_early",
                "service.completed",
                "partner.sample_collected",
                "appointment.service_switched",
            ],
            ben_nhan=["hanh_trinh_luot_kham"],
            # State riêng của Process Manager: lượt đang ở bước nào của đường đi.
            bang=["encounter_flow"],
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
                "prescription.consultant_marked",
            ],
            quyen=[
                "clinical.intake.perform",
                "clinical.consult.perform",
                "clinical.record.write",
                "clinical.consult.finalize",
            ],
            bang=[
                "clinical_record",
                "patient_medical_profile",
                "prescription",
                "consultation",
                "consultation_note",
                "phieu_kham_luot",
                "clinical_release",
                "visit_amendment",
            ],
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
                "payment",
                "payment_refund",
                "payment_refund_line",
                "tien_thua_giu_lai",
                "chot_so_ca",
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
            bang=["review_round", "round_requirement"],
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
                "partner.result_returned",
                "pharmacy.expiry_checked",
                "pharmacy.stocktake_mismatch",
            ],
            ben_nhan=["chuong_thong_bao"],
            bang=["day_nhan_thong_bao", "thong_bao", "thong_bao_an_cua_toi"],
        ),
        Module(
            ma="chuong_nhan_cheo",
            ten="Chuông nhận chéo (phòng quên Xong)",
            # CHỈ NGHE (07/10/2026): khách được phòng khác nhận lúc phòng cũ
            # còn đang làm → réo phòng cũ; lần làm đóng → chuông tự đóng.
            nghe=[
                "service.room_released",
                "service.completed",
                "service.interrupted",
                "service.start_cancelled",
                "service.room_release_undone",
            ],
            ben_nhan=["chuong_nhan_cheo"],
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
            bang=[
                "appointment",
                "appointment_doi_lich",
                "care_episode",
                "doctor_booking_override",
                "slot_booking_override",
                "luat_bac_si_bat_buoc",
            ],
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
                # Luồng chung với Phòng đối tác (16/10/2026).
                "ReturnPartnerResult",
                "UndoPartnerResult",
                "UndoSampleReceipt",
            ],
            phat=[
                "partner.sample_collected",
                "partner.sample_received",
                "partner.sample_receipt_undone",
                "partner.result_returned",
                "partner.result_return_undone",
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
                "partner.sample_collected",
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
            bang=[
                "tuong_tac_cskh",
                "ghi_chu_khach",
                "cskh_action",
                "cskh_log",
                "hen_goi_lai",
                "nhac_tai_kham",
                "phan_hoi_khach",
            ],
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
            phat=[
                "medicine.dispensed",
                "medicine.counter_changed",
                "pharmacy.expiry_checked",
                "medicine.returned",
                "pharmacy.stocktake_mismatch",
            ],
            bang=[
                "prescription_allocation",
                "inventory_txn",
                "drug_batch",
                "drug_ma_vach",
                "drug_return",
                "thuoc_quy_doi",
                "thuoc_giao_chua_gan_lo",
                "prescription_correction",
                "phieu_kho",
                "phieu_kho_dong",
                "kiem_ke_ca",
                "kiem_ke_ca_dong",
            ],
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
        # SỔ NỢ HAI CHIỀU (14/10/2026): một chỗ ghi duy nhất cho "khách nợ phòng
        # khám" / "phòng khám nợ khách" của lượt đã về. Chỉ ĐỌC luật của các khối
        # khác (no_khi_ve, tiền thừa), không có lệnh của riêng mình.
        Module(
            ma="so_no",
            ten="Sổ nợ hai chiều (phải thu / phải trả theo lượt)",
            nghe=[
                "visit.checked_out",
                "visit.left_early",
                "visit.reopened",
                "cong_no.ghi",
                "cong_no.huy",
                "payment.service_collected",
                "payment.medicine_collected",
                "payment.collection_undone",
                "payment.refunded",
                "service_order.cancelled",
                "service_order.restored",
                "service_order.carried_over",
                "service.started",
                "service.completed",
                "service.not_performed",
                "service.start_cancelled",
                "service.completion_undone",
                "visit.supply_changed",
                "visit.exam_service_changed",
                "medicine.dispensed",
                # G4d · R3: khách trả thuốc (thường SAU check-out) + đính chính
                # dòng đơn đã thu.
                "medicine.returned",
                "prescription.saved",
            ],
            ben_nhan=["so_no"],
            bang=["so_no", "so_no_moc"],
            projection=["so_no_hai_chieu"],
        ),
        # Kho VẬT TƯ (14/10/2026): sổ riêng, không dùng bảng thuốc. Tồn do trigger
        # cộng trong chính giao dịch ghi sổ nên không cần bên nhận sự kiện.
        Module(
            ma="kho_vat_tu",
            ten="Kho vật tư (phiếu kho, tồn theo nơi chứa, mức tối thiểu)",
            lenh=[
                "LapPhieuVatTu",
                "HoanPhieuVatTu",
                "DatMucToiThieuVatTu",
                # G8b: phiếu nhập hàng "cần duyệt nhập" → yêu cầu chờ duyệt.
                "DuyetPhieuNhapVatTu",
                "TuChoiPhieuNhapVatTu",
                "RutLaiPhieuNhapVatTu",
            ],
            phat=["vat_tu.nhap_cho_duyet", "vat_tu.nhap_da_quyet"],
            bang=["vat_tu_phieu", "vat_tu_ton", "vat_tu_txn", "vat_tu_nhap_cho_duyet"],
            quyen=["vat_tu.manage"],
        ),
        # Lịch ĐIỀU TRỊ (07/10/2026): khách vào hàng → chỉ định sẵn đúng dịch vụ
        # đã đặt (một service_order bình thường).
        Module(
            ma="dieu_tri",
            ten="Điều trị theo lịch đặt + đổi dịch vụ trong hồ sơ",
            lenh=["DoiDichVuTrongHoSo"],
            nghe=["visit.routed"],
            ben_nhan=["dieu_tri_sinh_chi_dinh"],
            # Ô chữ tự do của hồ sơ lượt "Khác" (mỗi lần lưu một phiên bản).
            bang=["luot_ghi_chu"],
            # Thẻ chỉ định điều trị ở hồ sơ khám: [Làm tại bàn khám] → [Xong].
            goi_dong_bo=[
                "execution.StartServiceAtDesk",
                "execution.CompleteServiceAtDesk",
                "execution.CancelDeskStart",
                "execution.UndoDeskCompletion",
            ],
        ),
        Module(
            ma="van_hanh",
            ten="Vận hành, báo cáo, lịch sử thao tác",
            quyen=["report.view", "ops.view", "audit.view", "giamsat.view"],
            bang=["agent_cau_hinh"],
        ),
        Module(
            ma="ke_toan",
            ten="Kế toán — xem tài chính đầy đủ, hoá đơn, theo hàng hoá",
            quyen=["accounting.finance.full", "accounting.tax.manage"],
            bang=[
                "hoa_don_cong_ty",
                "hoa_don_cong_ty_lich_su",
                "hoa_don_misa_xuat",
                "hoa_don_misa_xuat_dong",
                "khach_cong_ty",
                "thue_suat_nhom",
            ],
        ),
        Module(
            ma="lich_truc",
            ten="Lịch làm việc",
            # + đổi người trong ca (29/09/2026) và xếp lịch (01/10/2026), khối
            # trưởng ca.
            quyen=["roster.view", "roster.shift.swap", "roster.manage"],
            bang=[
                "work_roster",
                "work_roster_thay_nguoi",
                "roster_week",
                "vi_tri_lam_viec",
                "thu_ky_bac_si",
            ],
        ),
        # Hai khối có từ 21/10/2026: bảng cấu hình cơ sở và hồ sơ khách trước đó
        # không ai khai giữ (docs/kiem-tra-su-kien-lego-2110).
        Module(
            ma="co_so",
            ten="Cấu hình cơ sở (phòng khám, cơ sở, tầng, phòng, dây nối)",
            bang=[
                "clinic",
                "clinic_location",
                "clinic_floor",
                "clinic_room",
                "clinic_room_node",
                "clinic_room_service",
                "day_nghiep_vu",
            ],
        ),
        Module(
            ma="ho_so_khach",
            ten="Hồ sơ khách (thông tin, số điện thoại, đồng ý dữ liệu)",
            bang=[
                "patient",
                "patient_sdt_them",
                "patient_link",
                "clinical_data_consent",
            ],
        ),
    )
}


#: Bảng KHÔNG thuộc khối nào — sổ ghi, hàng đợi kỹ thuật, bảng dựng từ sự kiện.
#: Bảng bị code ghi mà không có chủ và không nằm ở đây = CI đỏ
#: (`test_luat_cam_ghi_cheo`): bảng mới phải khai chủ ngay lúc thêm.
BANG_KY_THUAT: dict[str, str] = {
    "domain_event": "sổ sự kiện chung — mọi khối ghi qua emit_event",
    "event_delivery": "dòng giao sự kiện — emit_event ghi cùng giao dịch",
    "event_log": "sổ cũ (record_event)",
    "loi_nhom": "kho lỗi",
    "canh_bao": "bộ canh gác",
    "nhat_ky_van_hanh": "nhật ký vận hành",
    "llm_lan_goi": "sổ lượt gọi model",
    "command_receipt": "biên nhận lệnh (idempotency)",
    "idempotency_key": "khoá chống bấm hai lần",
    "hen_gio": "hẹn giờ của bên nghe",
    "slot_hold": "giữ chỗ tạm lúc đặt lịch",
    "pos_outbox": "hộp thư đi sang máy POS",
    "luot_dong_thoi_gian": "dòng thời gian lượt — khối journey dựng từ sự kiện",
    "agent_nhan_dinh": "agent giám sát (shadow)",
    "agent_tom_tat": "agent giám sát (shadow)",
    "owner_feedback": "góp ý của chủ phòng khám",
    "lan_don_du_lieu_thu": "sổ các lần dọn dữ liệu thử",
    # Kiểm 21/10/2026: màn đã tắt / chỉ ghi không ai đọc — CHỜ BỎ (Mức 3).
    "service_log": "CHỜ BỎ — /api/service-log tắt từ 24/09",
    "service_order_draft": "CHỜ BỎ — đường nháp chỉ định tắt từ 24/09",
    "mpi_merge_queue": "CHỜ BỎ — chỉ ghi, không ai đọc",
    "work_session": "CHỜ BỎ — lịch thật đã sang work_roster",
    "work_session_staff": "CHỜ BỎ — lịch thật đã sang work_roster",
    "staff_task": "CHỜ BỎ — còn triage xét nghiệm ghi, gỡ chỗ ấy trước",
}

#: Tệp code (tính từ src/clinicai/) thuộc khối nào — để biết chỗ ghi bảng là của
#: khối nào. Tệp ghi database mà không nằm ở đây = CI đỏ. Tệp to làm việc của
#: nhiều khối được xếp vào khối chính; phần ghi bảng khối khác nằm trong sổ nợ
#: `NO_GHI_CHEO` của test_luat_cam_ghi_cheo (chỉ được ngắn đi).
TEP_CUA_KHOI: dict[str, Sequence[str]] = {
    "booking": [
        "services/booking_override_service.py",
        "services/booking_service.py",
        "services/episode_service.py",
        "services/luat_bac_si_service.py",
        "services/scheduling_service.py",
    ],
    "catalogue": [
        "phieu_kham/nap.py",
        "services/mau_ket_qua_service.py",
        "services/vat_tu_danh_muc_service.py",
    ],
    "chuong": [
        "events/consumers/chuong.py",
        "events/consumers/chuong_nhan_cheo.py",
        # Hạ tầng sự kiện: bên nghe chết → chuông cho người (bảng thong_bao).
        "events/hen_gio.py",
        "events/worker.py",
        "services/thong_bao_service.py",
    ],
    "co_so": [
        # Router có SQL viết thẳng (giờ ca) — trái luật "router mỏng", để dời sau.
        "api/v1/routers/config.py",
        "services/clinic_config_service.py",
        "services/clinic_floor_service.py",
        "services/clinic_settings_service.py",
        "services/config_service.py",
        "services/day_noi_service.py",
        "services/report_access_service.py",
    ],
    "cong_no": [
        "events/consumers/cong_no.py",
        "services/cong_no_service.py",
    ],
    "consultation": [
        "services/clinical_record_service.py",
        "services/clinical_sign_service.py",
        "services/dinh_chinh_don.py",
        "services/lenh_kham_core.py",
        "services/luot_kham_service.py",
        "services/phieu_kham_service.py",
    ],
    "cskh": [
        "services/cskh_service.py",
        "services/ghi_chu_khach_service.py",
        "services/hen_tai_kham_service.py",
        "services/phan_hoi_khach_service.py",
        "services/phan_hoi_thuoc_service.py",
        "services/recall_job_service.py",
        "services/tuong_tac_cskh_service.py",
    ],
    "dieu_tri": ["services/ghi_chu_luot.py"],
    "doi_tac": [
        "events/consumers/doi_tac.py",
        "services/doi_tac_service.py",
    ],
    "execution": ["services/service_execution_service.py"],
    "ho_so_khach": [
        "services/consent_service.py",
        "services/patient_service.py",
    ],
    "ke_toan": [
        "services/hoa_don_cong_ty_service.py",
        "services/hoa_don_misa_service.py",
        "services/thue_suat_service.py",
    ],
    "kho_vat_tu": [
        "services/vat_tu_kho_man_service.py",
        "services/vat_tu_kho_service.py",
        "services/vat_tu_nhap_duyet_service.py",
    ],
    "lab": [
        "services/lab_order_service.py",
        "services/lab_safety_service.py",
    ],
    "lich_truc": ["services/thu_ky_bac_si.py"],
    "lieu_trinh": [
        "services/lieu_trinh_service.py",
        "services/lieu_trinh_tien.py",
    ],
    "payment": [
        "services/anh_chuyen_khoan_service.py",
        "services/chot_so_ca_service.py",
        "services/doi_hinh_thuc_service.py",
        "services/hoan_tien_service.py",
        "services/payment_service.py",
        "services/tien_thua_service.py",
    ],
    "permission": [
        "services/auth_service.py",
        "services/ky_nang_service.py",
        "services/ngoai_le_ca_truc_service.py",
        "services/permission_service.py",
        "services/staff_service.py",
        "services/tai_khoan_service.py",
    ],
    "pharmacy": [
        "services/ban_le_service.py",
        "services/ban_theo_don_service.py",
        "services/kho_thuoc_service.py",
        "services/kiem_ke_ca_service.py",
        "services/lo_thuoc_service.py",
        "services/ma_vach_service.py",
        "services/phan_lo_service.py",
        "services/pharmacy_service.py",
        "services/quay_thuoc_service.py",
    ],
    "phi_kham": ["services/phi_kham_service.py"],
    "reception": [
        "services/checkout_service.py",
        "services/theo_doi_thu_thuat_service.py",
        "services/thu_tu_kham_service.py",
    ],
    "result": [
        "services/clinical_form_service.py",
        "services/form_engine_service.py",
        "services/media_service.py",
        "services/ultrasound_service.py",
    ],
    "result_file": [
        "services/don_tep_ket_qua.py",
        "services/tep_ket_qua_service.py",
    ],
    "service_order": [
        "services/chi_dinh_service.py",
        "services/ho_so_dich_vu.py",
        "services/lam_them_tai_quay_config.py",
        "services/lam_them_tai_quay_service.py",
        "services/service_order_service.py",
        "services/so_sua_chi_dinh_service.py",
    ],
    "service_routing": [
        "services/dispatch_service.py",
        "services/doi_bac_si_service.py",
        "services/gate_rule_service.py",
        "services/hang_cho.py",
        # Hoàn tác đụng nhiều khối trong MỘT giao dịch — xếp vào Điều phối.
        "services/hoan_tac_service.py",
        "services/nhan_tai_phong.py",
        "services/service_routing_service.py",
    ],
    "service_selection": [
        "services/lam_truoc_thu_sau.py",
        "services/service_selection_service.py",
    ],
    "so_no": ["services/so_no_service.py"],
    "thai_ky": ["services/thai_ky_service.py"],
    "trach_nhiem": [
        "events/consumers/trach_nhiem.py",
        "services/nhac_viec_service.py",
        "services/ultrasound_board_service.py",
        "services/work_item_service.py",
    ],
    "van_hanh": [
        "services/agent_giam_sat.py",
        # Hai script nạp / chuyển dữ liệu chạy một lần (Notion, lượt thật).
        "services/chuyen_luot_that.py",
        "services/nhap_lich_su_notion.py",
    ],
    "vat_tu": [
        "services/bio_chi_dinh_service.py",
        "services/vat_tu_service.py",
    ],
    "vitals": ["services/sinh_hieu_service.py"],
}


def khoi_cua_tep(tep: str) -> str | None:
    """Khối giữ tệp này (`tep` tính từ src/clinicai/)."""
    for ma, ds in TEP_CUA_KHOI.items():
        if tep in ds:
            return ma
    return None


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


__all__ = [
    "BANG_KY_THUAT",
    "MODULE",
    "TEP_CUA_KHOI",
    "CongDoc",
    "Module",
    "khoi_cua_tep",
    "module_cua_ben_nhan",
    "module_phat",
]
