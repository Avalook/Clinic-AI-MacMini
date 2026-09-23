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


MODULE: dict[str, Module] = {
    m.ma: m
    for m in (
        Module(
            ma="service_order",
            ten="Chỉ định dịch vụ",
            # CarryOverUnfinishedOrders: khối Hành trình gọi lúc check-in (H2) —
            # chỉ định chưa làm ĐI THEO KHÁCH sang lượt mới.
            lenh=["PlaceServiceOrders", "CarryOverUnfinishedOrders"],
            phat=["service_order.placed", "service_order.carried_over"],
            bang=["service_order"],
            quyen=["clinical.order.place"],
        ),
        Module(
            ma="service_selection",
            ten="Khách chọn dịch vụ",
            lenh=["ConfirmServiceSelection"],
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
            ],
            # Huỷ xếp phòng là sự thật nghiệp vụ, không chỉ là dòng nhật ký:
            # phòng mất thì phải có người xếp lại, và người ấy nhận việc qua
            # sự kiện này (ChatGPT tin 112).
            phat=["service.routed", "service.routing_invalidated"],
            bang=["queue_entry"],
            quyen=[
                "service.routing.view",
                "service.routing.assign",
                "service.routing.invalidate",
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
            ],
            phat=[
                "service.started",
                "service.completed",
                "service.not_performed",
                "service.interrupted",
                "service.retry_prepared",
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
            lenh=["OpenForm", "SaveFormDraft", "CompleteForm", "ReopenForm"],
            # BA sự kiện, MỘT nút bấm (ChatGPT tin 156, Tuyền tin 157). Kết quả
            # là vòng đời riêng của phiếu: ready → corrected → (sau này)
            # reviewed, released. Thêm bước mới vào chuỗi ấy không đụng module
            # nào khác — đó là chỗ để cắm miếng lego tiếp theo.
            phat=[
                "result_form.completed",
                "result.ready",
                "result.corrected",
            ],
            bang=["form_instance"],
            # Xác nhận tệp kết quả (B2) và bác sĩ duyệt kết quả (B3) cũng là
            # vòng đời kết quả — cùng module, không mở module mới cho hai lệnh.
            quyen=["result.form.fill", "result.file.confirm", "result.review.approve"],
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
            ],
            phat=["capability.granted", "capability.revoked"],
            bang=["capability_grant", "quyen_preset"],
            quyen=["permission.manage"],
        ),
        Module(
            ma="journey",
            ten="Hành trình lượt khám",
            # Không có lệnh: đây là module CHỈ NGHE. Thêm nó không đụng ai.
            nghe=[
                "visit.checked_in",
                "vitals.started",
                "vitals.recorded",
                "service_order.placed",
                "service.started",
                "service.completed",
                "service.not_performed",
                "service.interrupted",
                "service.retry_prepared",
                "service.routing_invalidated",
                "result_form.completed",
                "result.ready",
                "result.corrected",
                "visit.routed",
                "consultation.started",
                "consultation.handed_over",
                "consultation.completed",
                "service.routed",
                "service_order.carried_over",
                "payment.service_collected",
            ],
            ben_nhan=["dong_thoi_gian_luot"],
            projection=["luot_dong_thoi_gian"],
        ),
        Module(
            ma="trach_nhiem",
            ten="Trách nhiệm không được rơi",
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
            lenh=["CheckInPatient"],
            phat=["visit.checked_in"],
            quyen=["reception.checkin.perform"],
        ),
        Module(
            ma="vitals",
            ten="Sinh hiệu",
            lenh=["StartVitals", "RecordVitals"],
            phat=["vitals.started", "vitals.recorded"],
            quyen=["vitals.measure"],
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
            ],
            ben_nhan=["hanh_trinh_luot_kham"],
            goi_dong_bo=[
                "consultation.RouteAfterCheckIn",
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
                # Lệnh nội bộ khối Hành trình gọi (xếp hàng theo đường đi).
                "RouteAfterCheckIn",
                "OpenIntakeQueue",
                "HandToPrimaryDoctor",
            ],
            phat=[
                "consultation.started",
                "consultation.handed_over",
                "consultation.completed",
            ],
            quyen=[
                "clinical.intake.perform",
                "clinical.consult.perform",
                "clinical.record.write",
                "clinical.consult.finalize",
            ],
        ),
        Module(
            ma="payment",
            ten="Thu tiền dịch vụ",
            lenh=["CollectServicePayment"],
            # Tiền thật đã nhận (tiền mặt, hoặc chuyển khoản đã xác minh) —
            # khối Hành trình nghe để xếp phòng (H4).
            phat=["payment.service_collected"],
            bang=["payment_cycle", "payment_bill_line"],
            quyen=["payment.service.collect"],
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


__all__ = ["MODULE", "Module", "module_cua_ben_nhan", "module_phat"]
