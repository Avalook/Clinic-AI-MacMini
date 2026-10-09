"""Danh mục quyền — capability, khối công việc, preset.

NĂM LỚP (chốt trong chat ChatGPT #124, #132, #133, #134):

    TÀI KHOẢN          một con người. Hương vẫn là Hương, dù hôm nay lễ tân,
                       mai kiêm điều dưỡng. Tài khoản KHÔNG mang quyền.
    THUỘC PHÒNG KHÁM   `clinic_membership` — người này làm ở phòng khám nào.
    PRESET (vai)       gói mẫu để cấp cho nhanh. **Không phải hàng rào an ninh.**
                       Thêm preset = CHÉP một loạt quyền vào người ấy, không
                       phải thừa kế sống. Đổi preset sau này không tự đổi quyền
                       của người đã cấp.
    CA / VỊ TRÍ        đứng phòng SA hôm nay ≠ có mọi quyền siêu âm.
    CAPABILITY + SCOPE quyền thật. Scope = toàn phòng khám / một phòng / một ca.

Câu hỏi của lệnh luôn là `can(identity, "clinical.order.place")`, KHÔNG BAO GIỜ
là `if role in {DOCTOR, TKYK}`. Đó là lý do "điều dưỡng cũng được điều phối" hôm
nay phải sửa năm cửa, còn sau này chỉ là quản lý tick một ô.

KHỐI CÔNG VIỆC (work-pack) — Tuyền chốt ở #133/#134. Quản lý KHÔNG tick từng
quyền lắt nhắt: màn quản lý bật/tắt **cả khối** ("Tiếp đón", "Sinh hiệu", "Chỉ
định"...), bấm "▾ Chi tiết" mới bung quyền con. Quyền con vẫn tồn tại ở tầng kỹ
thuật để chỗ nào cần chặt thì chặt được, nhưng mặc định bật cả khối.

QUẢN LÝ CHỈNH ĐƯỢC CAO NHẤT. Ai có `permission.manage` thì cấp hay thu được mọi
khối cho bất kỳ ai trong phòng khám, kể cả quyền không nằm trong preset của vai
họ. `default_presets` chỉ là GỢI Ý, không phải trần.

KHÔNG CÒN HÀNG RÀO CHỨNG CHỈ (Tuyền bỏ 24/09/2026). Cột `chung_chi_lam_sang` giữ
lại (mọi quyền đều False) để sau này phòng khám cần thì bật lại — hiện không lệnh
nào đọc nó để chặn. Ai được làm gì = khối được cấp, hết.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum


class MucRuiRo(str, Enum):
    """Nặng nhẹ của một quyền — dùng để cảnh báo trên màn quản lý."""

    VAN_HANH = "operational"
    TIEN = "financial"
    LAM_SANG = "clinical"
    QUAN_TRI = "admin"


class PhamVi(str, Enum):
    """Quyền có hiệu lực tới đâu (#132: scope tối thiểu)."""

    PHONG_KHAM = "CLINIC"
    PHONG = "ROOM"
    CA = "SHIFT"


@dataclass(frozen=True)
class KhoiCongViec:
    """Một khối bật/tắt trên màn quản lý."""

    ma: str
    ten: str
    module: str
    mo_ta: str


@dataclass(frozen=True)
class Quyen:
    """Một capability — đơn vị mà LỆNH hỏi tới."""

    ma: str
    ten: str
    khoi: str
    module: str
    rui_ro: MucRuiRo
    chung_chi_lam_sang: bool = False
    # Sequence + default_factory: tuple một phần tử phải viết kèm dấu phẩy
    # cuối, và bài kiểm cú pháp SQL quét mọi dòng Python sẽ báo nhầm.
    pham_vi_ho_tro: Sequence[PhamVi] = field(
        default_factory=lambda: [PhamVi.PHONG_KHAM]
    )


# ── Khối công việc ──────────────────────────────────────────────────────────
KHOI: dict[str, KhoiCongViec] = {
    k.ma: k
    for k in (
        KhoiCongViec(
            "tiep_don", "Tiếp đón", "reception", "Đón khách, check-in, khách vãng lai"
        ),
        KhoiCongViec("sinh_hieu", "Sinh hiệu", "vitals", "Đo và ghi sinh hiệu"),
        KhoiCongViec(
            "chi_dinh",
            "Chỉ định dịch vụ",
            "service_order",
            "Chốt dịch vụ cho khách làm",
        ),
        KhoiCongViec(
            "chon_dich_vu",
            "Khách chọn dịch vụ",
            "service_selection",
            "Xác nhận khách đồng ý làm dịch vụ nào",
        ),
        KhoiCongViec(
            "dieu_phoi",
            "Điều phối khách",
            "service_routing",
            "Xem tải phòng, xếp phòng",
        ),
        KhoiCongViec(
            "thu_tien_dv", "Thu tiền dịch vụ", "payment", "Thu và huỷ phiếu dịch vụ"
        ),
        KhoiCongViec(
            "danh_muc",
            "Danh mục & biểu mẫu",
            "catalogue",
            "Sửa danh mục dịch vụ, mẫu kết quả, gắn mẫu cho dịch vụ",
        ),
        KhoiCongViec(
            "thuc_hien",
            "Thực hiện dịch vụ",
            "execution",
            "Bắt đầu, hoàn thành, dừng giữa chừng, đánh dấu không làm được",
        ),
        KhoiCongViec(
            "ket_qua",
            "Kết quả cận lâm sàng",
            "result",
            "Điền và hoàn tất biểu mẫu kết quả cho dịch vụ đã làm",
        ),
        # Khối RIÊNG, không gộp vào `ket_qua`: gộp là mọi người có preset
        # `ket_qua` (bác sĩ, thư ký, điều dưỡng) tự nhiên xác nhận được tệp của
        # đối tác. Trước 23/09 quyền này chỉ có ai được tick tay ở /nhan-su.
        KhoiCongViec(
            "xac_nhan_ket_qua",
            "Xác nhận tệp kết quả",
            "result",
            "Xác nhận hoặc từ chối tệp kết quả đối tác gửi về",
        ),
        # ── Đường khám (CORE-B3, 23/09/2026) — tách khối theo đúng ranh giới
        # vai đang có, để chuyển sang quyền mà không ai được/mất việc gì:
        # gọi-bắt đầu-khám xong là bác sĩ + thư ký; ghi bệnh án thêm bác sĩ siêu
        # âm; HOÀN TẤT (khoá hồ sơ) và DUYỆT kết quả là quyết định chuyên môn.
        KhoiCongViec(
            "tu_van",
            "Khám tư vấn",
            "consultation",
            "Nhận khách ở hàng tư vấn, hỏi bệnh ban đầu, chuyển bác sĩ chính",
        ),
        KhoiCongViec(
            "kham",
            "Khám bệnh",
            "consultation",
            "Gọi khách vào, bắt đầu khám, khám xong chuyển bước",
        ),
        KhoiCongViec(
            "ghi_benh_an",
            "Ghi bệnh án",
            "consultation",
            "Ghi ghi chú khám và bệnh án",
        ),
        KhoiCongViec(
            "hoan_tat_kham",
            "Hoàn tất khám",
            "consultation",
            "Hoàn tất lượt khám — khoá hồ sơ; sửa sau đó phải đính chính",
        ),
        KhoiCongViec(
            "duyet_ket_qua",
            "Duyệt kết quả",
            "result",
            "Bác sĩ duyệt kết quả cận lâm sàng",
        ),
        KhoiCongViec(
            "quan_tri_quyen",
            "Phân quyền",
            "permission",
            "Cấp và thu quyền cho nhân sự",
        ),
        # 24/09/2026 — thu tiền thuốc, nhà thuốc, lịch hẹn thôi hỏi vai
        # (migration 20260924000013).
        KhoiCongViec(
            "thu_tien_thuoc", "Thu tiền thuốc", "payment", "Thu và huỷ phiếu tiền thuốc"
        ),
        KhoiCongViec(
            "nha_thuoc",
            "Nhà thuốc",
            "pharmacy",
            "Giao thuốc, từ chối, nhập / điều chỉnh / huỷ lô, khách trả thuốc",
        ),
        KhoiCongViec(
            "xem_nha_thuoc",
            "Xem nhà thuốc",
            "pharmacy",
            "Xem hàng chờ quầy thuốc, đơn bán, tồn kho",
        ),
        KhoiCongViec(
            "dat_lich", "Đặt lịch", "booking", "Đặt lịch, giữ chỗ, xác nhận lịch cũ"
        ),
        KhoiCongViec(
            "quan_ly_lich",
            "Quản lý lịch hẹn",
            "booking",
            "Huỷ lịch, dời lịch, gán / đổi bác sĩ cho lịch",
        ),
        # ── 21 lego theo thanh bên (Tuyền 25/09/2026) — khối cho những màn trước
        # đây còn gác theo VAI (migration 20260925000015).
        KhoiCongViec(
            "viec_can_xu_ly",
            "Việc cần xử lý",
            "worklist",
            "Xem và xử lý việc được giao",
        ),
        KhoiCongViec(
            "truong_ca",
            "Điều phối ca",
            "dispatch",
            "Điều phối ca, chuyển khách, đổi bác sĩ, ngưỡng cảnh báo — xếp phòng"
            " cao nhất",
        ),
        KhoiCongViec(
            "them_benh_nhan",
            "Thêm bệnh nhân",
            "patient",
            "Thêm hồ sơ bệnh nhân mới, không cần đặt lịch",
        ),
        KhoiCongViec(
            "cham_soc_khach",
            "Chăm sóc khách hàng",
            "crm",
            "Quản lý khách hàng, nhắc tái khám",
        ),
        KhoiCongViec(
            "ds_benh_nhan", "Danh sách bệnh nhân", "patient", "Xem danh sách bệnh nhân"
        ),
        KhoiCongViec(
            "lich_lam_viec", "Lịch làm việc", "roster", "Xem lịch làm việc, ca trực"
        ),
        KhoiCongViec("bang_gia", "Bảng giá dịch vụ", "catalogue", "Sửa giá dịch vụ"),
        KhoiCongViec("bao_cao", "Báo cáo", "report", "Báo cáo, lịch đổ về"),
        KhoiCongViec(
            "cai_dat",
            "Cài đặt phòng khám",
            "config",
            "Luật đặt lịch, cấu trúc phòng khám, xếp lịch trực",
        ),
        KhoiCongViec(
            "nhan_su",
            "Nhân sự & tài khoản",
            "staff",
            "Thêm nhân sự, tạo tài khoản đăng nhập, đặt lại mật khẩu",
        ),
        KhoiCongViec(
            "van_hanh", "Vận hành hệ thống", "ops", "Theo dõi tình trạng hệ thống"
        ),
        KhoiCongViec(
            "lich_su_thao_tac", "Lịch sử thao tác", "ops", "Xem nhật ký thao tác"
        ),
        KhoiCongViec(
            "doi_tac",
            "Đối tác",
            "partner",
            "Khách được phân cho mình, điền thông tin, gửi tài liệu",
        ),
        # NỘI BỘ (09/10/2026): trung tâm giám sát AI ở giamsat.dr4women.io.vn —
        # chỉ đội vận hành ClinicAI. KHÔNG nằm trong preset nào, không bày trên
        # màn Phân quyền, API cấp/thu/nhóm từ chối, trigger DB chặn cấp lậu.
        # Cấp bằng SQL có cờ phiên (xem migration 20261009880000).
        KhoiCongViec(
            "noi_bo_giam_sat",
            "Giám sát AI (nội bộ)",
            "ops",
            "Trung tâm giám sát agent — chỉ đội vận hành ClinicAI",
        ),
    )
}

#: Khối nội bộ của đội vận hành ClinicAI — quản lý phòng khám (kể cả có
#: `permission.manage`) KHÔNG cấp / thu / gom vào nhóm được.
KHOI_NOI_BO: frozenset[str] = frozenset({"noi_bo_giam_sat"})


# ── Quyền ───────────────────────────────────────────────────────────────────
QUYEN: dict[str, Quyen] = {
    q.ma: q
    for q in (
        Quyen(
            "reception.checkin.perform",
            "Check-in khách",
            "tiep_don",
            "reception",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "vitals.measure",
            "Đo sinh hiệu",
            "sinh_hieu",
            "vitals",
            MucRuiRo.VAN_HANH,
            pham_vi_ho_tro=[PhamVi.PHONG_KHAM, PhamVi.PHONG, PhamVi.CA],
        ),
        Quyen(
            "clinical.order.place",
            "Chỉ định dịch vụ cho khách",
            "chi_dinh",
            "service_order",
            MucRuiRo.LAM_SANG,
            # Tuyền #149: thư ký y khoa ngang bác sĩ ở việc này, nên KHÔNG đòi
            # chứng chỉ. Duyệt kết quả và ký bệnh án thì khác.
            chung_chi_lam_sang=False,
        ),
        Quyen(
            "service_selection.confirm",
            "Xác nhận khách chọn dịch vụ",
            "chon_dich_vu",
            "service_selection",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "service.routing.view",
            "Xem phòng phù hợp và tải phòng",
            "dieu_phoi",
            "service_routing",
            MucRuiRo.VAN_HANH,
            pham_vi_ho_tro=[PhamVi.PHONG_KHAM, PhamVi.PHONG],
        ),
        Quyen(
            "service.routing.assign",
            "Xếp phòng cho khách",
            "dieu_phoi",
            "service_routing",
            MucRuiRo.VAN_HANH,
            pham_vi_ho_tro=[PhamVi.PHONG_KHAM, PhamVi.PHONG],
        ),
        Quyen(
            "service.routing.invalidate",
            "Huỷ xếp phòng khi phòng hỏng",
            "dieu_phoi",
            "service_routing",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "payment.service.collect",
            "Thu tiền dịch vụ",
            "thu_tien_dv",
            "payment",
            MucRuiRo.TIEN,
        ),
        Quyen(
            "catalogue.result_template.manage",
            "Gắn mẫu kết quả cho dịch vụ",
            "danh_muc",
            "catalogue",
            # Gắn nhầm mẫu là chuyện lâm sàng: bác sĩ điền vào mẫu sai thì kết
            # quả sai chỗ, nên xếp mức lâm sàng dù không cần chứng chỉ.
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "catalogue.form_template.edit",
            "Sửa nội dung biểu mẫu",
            "danh_muc",
            "catalogue",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "catalogue.form_template.publish",
            "Xuất bản phiên bản biểu mẫu",
            "danh_muc",
            "catalogue",
            MucRuiRo.LAM_SANG,
        ),
        # Khối chỉnh dây (nhóm 5, 24/09/2026): loại khám qua tư vấn / đi thẳng
        # phòng, bật tắt tự xếp phòng, thời hạn nhắc, người nhận chuông, vị trí.
        Quyen(
            "config.wiring.manage",
            "Chỉnh dây nối nghiệp vụ (tư vấn, tự xếp phòng, chuông, vị trí)",
            "danh_muc",
            "catalogue",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "service.execute.start",
            "Bắt đầu làm dịch vụ",
            "thuc_hien",
            "execution",
            MucRuiRo.VAN_HANH,
            pham_vi_ho_tro=[PhamVi.PHONG_KHAM, PhamVi.PHONG, PhamVi.CA],
        ),
        Quyen(
            "service.execute.complete",
            "Đánh dấu đã làm xong",
            "thuc_hien",
            "execution",
            MucRuiRo.VAN_HANH,
            pham_vi_ho_tro=[PhamVi.PHONG_KHAM, PhamVi.PHONG, PhamVi.CA],
        ),
        Quyen(
            # Đụng tiền đã thu: khách trả rồi mà không làm thì phải có người
            # đối soát, nên đây không phải thao tác thường ngày.
            "service.execute.not_performed",
            "Đánh dấu không làm được",
            "thuc_hien",
            "execution",
            MucRuiRo.TIEN,
        ),
        Quyen(
            "service.execute.interrupt",
            "Dừng giữa chừng",
            "thuc_hien",
            "execution",
            MucRuiRo.TIEN,
        ),
        Quyen(
            "service.execute.retry",
            "Quyết định làm lại sau khi dừng",
            "thuc_hien",
            "execution",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "result.form.fill",
            "Điền và hoàn tất biểu mẫu kết quả",
            "ket_qua",
            "result",
            MucRuiRo.LAM_SANG,
        ),
        # V9 (30/09/2026): xoá mềm tệp kết quả, hoàn tác 30 ngày. Cùng khối
        # `ket_qua` — hướng "MỞ HẾT": ai có lego kết quả thì xoá được. Tệp đã gửi
        # khách / phiên đọc đã đóng thì chỉ "Đính chính – gỡ tệp" (cần duyệt KQ).
        Quyen(
            "result.file.delete",
            "Xoá / khôi phục tệp kết quả (xoá mềm, hoàn tác 30 ngày)",
            "ket_qua",
            "result",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "clinical.intake.perform",
            "Khám tư vấn — nhận khách, chuyển bác sĩ chính",
            "tu_van",
            "consultation",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "clinical.consult.perform",
            "Gọi khách, bắt đầu khám, khám xong",
            "kham",
            "consultation",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "clinical.record.write",
            "Ghi ghi chú khám và bệnh án",
            "ghi_benh_an",
            "consultation",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "clinical.consult.finalize",
            "Hoàn tất khám (khoá hồ sơ)",
            "hoan_tat_kham",
            "consultation",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "result.review.approve",
            "Duyệt kết quả cận lâm sàng",
            "duyet_ket_qua",
            "result",
            MucRuiRo.LAM_SANG,
        ),
        # Chuyển từ `staff_capability` (`ket_qua.xac_nhan`) sang đây 23/09/2026:
        # chỉ còn MỘT hệ quyền.
        Quyen(
            "result.file.confirm",
            "Xác nhận / từ chối / thu hồi tệp kết quả",
            "xac_nhan_ket_qua",
            "result",
            MucRuiRo.LAM_SANG,
        ),
        Quyen(
            "permission.manage",
            "Cấp và thu quyền",
            "quan_tri_quyen",
            "permission",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "payment.medicine.collect",
            "Thu tiền thuốc",
            "thu_tien_thuoc",
            "payment",
            MucRuiRo.TIEN,
        ),
        Quyen(
            "pharmacy.dispense",
            "Giao thuốc và quản lý lô thuốc",
            "nha_thuoc",
            "pharmacy",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "pharmacy.view",
            "Xem quầy thuốc và tồn kho",
            "xem_nha_thuoc",
            "pharmacy",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "booking.create",
            "Đặt lịch và giữ chỗ",
            "dat_lich",
            "booking",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "booking.manage",
            "Huỷ / dời lịch, gán bác sĩ cho lịch",
            "quan_ly_lich",
            "booking",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "worklist.handle",
            "Xem và xử lý việc cần xử lý",
            "viec_can_xu_ly",
            "worklist",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "dispatch.manage",
            "Điều phối ca — chuyển khách, đổi bác sĩ, xếp phòng cao nhất",
            "truong_ca",
            "dispatch",
            MucRuiRo.VAN_HANH,
        ),
        # 29/09/2026: trưởng ca thay người giữa ca (Hà về, B vào) mà không cần
        # cả lego "Cài đặt phòng khám". Chỉ hôm nay và các ngày tới.
        Quyen(
            "roster.shift.swap",
            "Đổi người trong ca (hôm nay và các ngày tới)",
            "truong_ca",
            "roster",
            MucRuiRo.VAN_HANH,
        ),
        # 01/10/2026 (Tuyền): trưởng ca XẾP lịch làm việc (xếp ca, áp dụng tuần)
        # — trước chỉ người có lego "Cài đặt phòng khám". Phạm vi vị trí vẫn ở
        # lego Cài đặt.
        Quyen(
            "roster.manage",
            "Xếp lịch làm việc (xếp ca, áp dụng tuần)",
            "truong_ca",
            "roster",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "patient.create",
            "Thêm bệnh nhân mới",
            "them_benh_nhan",
            "patient",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "crm.manage",
            "Quản lý khách hàng và nhắc tái khám",
            "cham_soc_khach",
            "crm",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "patient.list.view",
            "Xem danh sách bệnh nhân",
            "ds_benh_nhan",
            "patient",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "roster.view",
            "Xem lịch làm việc",
            "lich_lam_viec",
            "roster",
            MucRuiRo.VAN_HANH,
        ),
        Quyen(
            "price.service.manage",
            "Sửa bảng giá dịch vụ",
            "bang_gia",
            "catalogue",
            MucRuiRo.TIEN,
        ),
        Quyen(
            "report.view",
            "Xem báo cáo",
            "bao_cao",
            "report",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "config.clinic.manage",
            "Cài đặt phòng khám (luật đặt lịch, cấu trúc, lịch trực)",
            "cai_dat",
            "config",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "staff.manage",
            "Thêm / sửa / nghỉ việc nhân sự",
            "nhan_su",
            "staff",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "account.manage",
            "Tạo tài khoản đăng nhập, đặt lại mật khẩu",
            "nhan_su",
            "staff",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "ops.view",
            "Xem vận hành hệ thống",
            "van_hanh",
            "ops",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "giamsat.view",
            "Xem trung tâm giám sát AI (nội bộ đội vận hành)",
            "noi_bo_giam_sat",
            "ops",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "audit.view",
            "Xem lịch sử thao tác",
            "lich_su_thao_tac",
            "ops",
            MucRuiRo.QUAN_TRI,
        ),
        Quyen(
            "partner.work",
            "Làm việc đối tác (khách được phân, gửi tài liệu)",
            "doi_tac",
            "partner",
            MucRuiRo.VAN_HANH,
        ),
    )
}


# ── Preset theo vai — GỢI Ý, không phải trần quyền ──────────────────────────
# Quản lý tick gì thì người đó có nấy; preset chỉ để cấp cho nhanh (#133).
PRESET: dict[str, Sequence[str]] = {
    "DOCTOR": [
        "tu_van",
        "chi_dinh",
        "dieu_phoi",
        "ket_qua",
        "thuc_hien",
        "kham",
        "ghi_benh_an",
        "hoan_tat_kham",
        "duyet_ket_qua",
    ],
    "TKYK": [
        # 29/09/2026: ĐD/TKYK trọn quyền ở mọi phòng (Tuyền) — migration
        # 20260929900000 cấp bù cho tài khoản hiện có.
        "sinh_hieu",
        "chi_dinh",
        "dieu_phoi",
        "kham",
        "ghi_benh_an",
        "hoan_tat_kham",
        "thuc_hien",
        "ket_qua",
        "duyet_ket_qua",
        "doi_tac",
    ],
    # Lễ tân kiêm thu ngân + quầy thuốc ở Kim Ngưu (16/09) và đặt lịch khách
    # vãng lai — khớp `allowed_kinds` / VAI_GHI_NHA_THUOC / INTAKE_ROLES cũ.
    "RECEPTION": [
        "tiep_don",
        "chon_dich_vu",
        "thu_tien_dv",
        "dieu_phoi",
        "thu_tien_thuoc",
        "nha_thuoc",
        "xem_nha_thuoc",
        "dat_lich",
        # Màn Quản lý khách hàng đủ quyền (Tuyền 24/09/2026): đổi / huỷ lịch.
        "quan_ly_lich",
    ],
    # ĐIỀU DƯỠNG CÓ `chi_dinh` (Tuyền chốt 23/09/2026). Trong nghiệp vụ tạo chỉ
    # định và phát sinh dịch vụ tại phòng, bác sĩ = thư ký y khoa = điều dưỡng;
    # khác nhau chỉ ở chỗ AI THỰC SỰ BẤM, và chuyện đó là việc của nhật ký, không
    # phải của hàng rào quyền. Không có nhánh "điều dưỡng nhập nháp rồi bác sĩ
    # duyệt" — nó chưa từng tồn tại ngoài đời ở phòng khám này.
    #
    # KHÔNG SUY RỘNG: đây là quyền ĐẶT CHỈ ĐỊNH. Ký bệnh án và duyệt/phát hành
    # kết quả là những quyền khác, nằm ở khối khác, và không đi kèm.
    "NURSE_ULTRASOUND": [
        # 29/09/2026: ĐD/TKYK trọn quyền ở mọi phòng (Tuyền) — migration
        # 20260929900000 cấp bù cho tài khoản hiện có.
        "sinh_hieu",
        "chi_dinh",
        "dieu_phoi",
        "kham",
        "ghi_benh_an",
        "hoan_tat_kham",
        "thuc_hien",
        "ket_qua",
        "duyet_ket_qua",
        "doi_tac",
    ],
    # Thu ngân có `dieu_phoi` (Tuyền chốt 24/09/2026): thu tiền xong khách tự
    # được xếp phòng như khi lễ tân thu (dây H4 hỏi quyền người thu) — thu ngân
    # là một nút của quầy lễ tân, quyền đi theo khối, không theo tên vai.
    "CASHIER": ["thu_tien_dv", "chon_dich_vu", "dieu_phoi", "thu_tien_thuoc"],
    "CASHIER_DV": ["thu_tien_dv", "chon_dich_vu", "dieu_phoi"],
    # Thu ngân nhà thuốc KHÔNG thu tiền dịch vụ (`allowed_kinds`: chỉ "thuoc").
    # Preset cũ có `thu_tien_dv` là lệch — sửa 23/09 khi thu tiền dịch vụ
    # chuyển sang quyền, kẻo vai này tự dưng thu được tiền dịch vụ.
    "CASHIER_THUOC": ["thu_tien_thuoc", "xem_nha_thuoc"],
    "TRUONG_CA": [
        "dieu_phoi",
        "tiep_don",
        "chon_dich_vu",
        "thuc_hien",
        "xem_nha_thuoc",
        "dat_lich",
        "quan_ly_lich",
    ],
    "PHARMACIST": ["thu_tien_thuoc", "nha_thuoc", "xem_nha_thuoc"],
    "CSKH": ["dat_lich", "quan_ly_lich"],
    "ULTRASOUND_DOCTOR": [
        "dieu_phoi",
        "ket_qua",
        "thuc_hien",
        "ghi_benh_an",
        "duyet_ket_qua",
    ],
}


# 21 LEGO (Tuyền 25/09/2026): khối mới vào nhóm mẫu theo ĐÚNG tập vai hôm nay
# đang được vào màn ấy (NAV_ROLES + cửa backend) — không ai mất việc khi chuyển
# sang quyền. Migration 20260925000015 thêm y hệt vào `quyen_preset`.
_THEM_THEO_LEGO: dict[str, list[str]] = {
    "DOCTOR": ["viec_can_xu_ly", "ds_benh_nhan", "lich_lam_viec"],
    # "Việc cần xử lý": ai có khối Điều phối (quyền xem điều phối) vốn THẤY màn
    # này trên thanh bên từ 24/09 — giữ nguyên, không ai mất việc.
    "TKYK": ["viec_can_xu_ly", "ds_benh_nhan", "lich_lam_viec"],
    "RECEPTION": [
        "viec_can_xu_ly",
        "them_benh_nhan",
        "cham_soc_khach",
        "ds_benh_nhan",
        "lich_lam_viec",
        "bang_gia",
    ],
    "NURSE_ULTRASOUND": ["viec_can_xu_ly", "ds_benh_nhan", "lich_lam_viec"],
    "CASHIER": [
        "viec_can_xu_ly",
        "cham_soc_khach",
        "ds_benh_nhan",
        "lich_lam_viec",
        "bang_gia",
    ],
    "CASHIER_DV": [
        "viec_can_xu_ly",
        "cham_soc_khach",
        "ds_benh_nhan",
        "lich_lam_viec",
        "bang_gia",
    ],
    "CASHIER_THUOC": ["cham_soc_khach", "ds_benh_nhan", "lich_lam_viec", "bang_gia"],
    "TRUONG_CA": [
        "viec_can_xu_ly",
        "truong_ca",
        "them_benh_nhan",
        "cham_soc_khach",
        "ds_benh_nhan",
        "lich_lam_viec",
        "bang_gia",
        "bao_cao",
        "lich_su_thao_tac",
    ],
    "PHARMACIST": ["lich_lam_viec"],
    # CSKH có Lịch làm việc (Tuyền 25/09: "cả CSKH cũng phải có") — XEM lịch;
    # xếp lịch trực là lego Cài đặt.
    "CSKH": [
        "them_benh_nhan",
        "cham_soc_khach",
        "ds_benh_nhan",
        "lich_lam_viec",
        "lich_su_thao_tac",
    ],
    "ULTRASOUND_DOCTOR": ["viec_can_xu_ly", "ds_benh_nhan", "lich_lam_viec"],
}
for _vai, _them in _THEM_THEO_LEGO.items():
    PRESET[_vai] = [*PRESET[_vai], *(k for k in _them if k not in PRESET[_vai])]
# Tài khoản đối tác CHỈ có lego Đối tác (backend vẫn chặn PARTNER ở mọi cửa khác).
PRESET["PARTNER"] = ["doi_tac"]


# Quản lý có TẤT CẢ các khối — mặc định, không liệt kê, không loại trừ. Tuyền
# chốt 24/09/2026: "quản lý quyền cao nhất — có module đó thì mọi quyền của nó
# có cả". Khối mới thêm sau này tự vào (migration thêm khối phải thêm cả vào
# nhóm này — `test_danh_muc_quyen_db` so hai bên).
# Trừ khối NỘI BỘ của đội vận hành ClinicAI (09/10/2026) — đó không phải quyền
# của phòng khám.
PRESET["MANAGEMENT"] = [k for k in KHOI if k not in KHOI_NOI_BO]
# `doi_tac` là việc của người ngoài; quản lý vẫn có (xem hộ đối tác) như trước.


# ── MỞ FULL LEGO (Tuyền 30/09/2026) ─────────────────────────────────────────
# "Phòng khám chả có quy trình nào, lúc nào, ai thu cũng được… open hết ra, nhân
# sự có các node gần full để thao tác cho lẹ." Mọi vai nội bộ có MỌI khối, trừ
# bốn khối của hai lego chỉ Quản lý giữ (Cài đặt phòng khám, Nhân sự & phân
# quyền) để khỏi loạn. Migration 20260930900000 cấp bù cho tài khoản hiện có và
# thêm y hệt vào `quyen_preset`.
#
# Hệ quả đã chấp nhận: ai đủ lego Bàn khám được suy ra vai DOCTOR ở các cửa cũ
# (`VAI_THEO_LEGO`). Tên KÝ trên giấy và "bác sĩ của phiên" KHÔNG đi theo lego —
# chúng đọc `clinic_membership.role` (`services/bac_si_phu_trach.py`,
# `services/bac_si_ky.py`).

#: Gói mẫu NGAY TRƯỚC khi mở full — giữ để thu lại theo vai nếu cần (không dùng
#: để cấp).
PRESET_TRUOC_MO_FULL: dict[str, tuple[str, ...]] = {
    _vai: tuple(_khoi) for _vai, _khoi in PRESET.items()
}

#: Khối CHỈ Quản lý có (không mở cho mọi người).
KHOI_CHI_QUAN_LY: frozenset[str] = frozenset(
    {"quan_tri_quyen", "nhan_su", "cai_dat", "danh_muc"}
)

#: Khối mở cho MỌI nhân sự nội bộ.
KHOI_MO_FULL: list[str] = [
    k for k in KHOI if k not in KHOI_CHI_QUAN_LY and k not in KHOI_NOI_BO
]

for _vai in PRESET:
    if _vai not in ("PARTNER", "MANAGEMENT"):
        PRESET[_vai] = list(KHOI_MO_FULL)


# ── QUYỀN THEO MÀN (Tuyền chốt 23/09/2026) ───────────────────────────────
# "Quyền đi theo MÀN (màn = khối lego; xem/sửa/xoá đi theo màn, không chi tiết
# hơn). Ô quản lý quyền: chọn vai → các màn MẶC ĐỊNH hiện ra, thêm/sửa/xoá thoải
# mái." Một màn = những khối công việc cần để làm việc trên màn ấy; bật màn cho
# một nhóm = thêm các khối ấy vào nhóm. Bảng "màn mặc định cho vai" ở ghi chú.


@dataclass(frozen=True)
class Man:
    """Một LEGO = một node thanh bên (Tuyền 25/09/2026). Bật lego = có đủ mọi
    khối của nó; một khối có thể nằm trong nhiều lego (Ghi bệnh án ở Tư vấn, Bàn
    khám, Phòng dịch vụ)."""

    ma: str
    ten: str
    duong: str
    khoi: Sequence[str]
    mac_dinh_cho: str
    #: Mọi màn (đường dẫn thanh bên) thuộc lego này.
    cac_duong: Sequence[str] = field(default_factory=list)
    #: Lego to / lego nhỏ: bật rồi chọn PHÒNG (phạm vi ROOM của khối này).
    khoi_theo_phong: str | None = None


def _lego(
    ma: str,
    ten: str,
    cac_duong: Sequence[str],
    khoi: Sequence[str],
    mac_dinh_cho: str,
    khoi_theo_phong: str | None = None,
) -> Man:
    return Man(ma, ten, cac_duong[0], khoi, mac_dinh_cho, cac_duong, khoi_theo_phong)


# THỨ TỰ = thứ tự thanh bên. Màn quản lý hiện 21 dòng, mỗi dòng một công tắc.
MAN: dict[str, Man] = {
    m.ma: m
    for m in (
        _lego(
            "tiep_don",
            "Tiếp đón khách",
            ["/reception/queue", "/reception/checkout"],
            ["tiep_don"],
            "Lễ tân",
        ),
        _lego(
            "do_sinh_hieu",
            "Đo sinh hiệu",
            ["/do-sinh-hieu"],
            ["sinh_hieu"],
            "Điều dưỡng",
        ),
        _lego(
            "tu_van",
            "Khám tư vấn",
            ["/tu-van"],
            ["tu_van", "ghi_benh_an"],
            "Bác sĩ tư vấn",
        ),
        _lego(
            "ban_kham",
            "Bàn khám",
            ["/ban-kham"],
            # + duyet_ket_qua (28/09/2026): thư ký / bác sĩ cùng phòng "thao tác
            # như nhau" — duyệt kết quả, cho gửi kết quả không còn riêng bác sĩ.
            [
                "kham",
                "chi_dinh",
                "ghi_benh_an",
                "hoan_tat_kham",
                "ket_qua",
                "duyet_ket_qua",
            ],
            "Bác sĩ chính + Thư ký y khoa",
        ),
        _lego(
            "phong",
            "Phòng dịch vụ",
            ["/phong"],
            # + duyet_ket_qua (28/09/2026): ai làm ở phòng ấy ký được phiếu CỦA MÌNH.
            ["thuc_hien", "ket_qua", "ghi_benh_an", "duyet_ket_qua"],
            "BS siêu âm / thủ thuật + Điều dưỡng",
            khoi_theo_phong="thuc_hien",
        ),
        _lego(
            "thu_tien_dv",
            "Thanh toán dịch vụ",
            ["/thu-ngan/dich-vu"],
            ["thu_tien_dv", "chon_dich_vu", "dieu_phoi"],
            "Lễ tân, thu ngân",
        ),
        _lego(
            "thu_tien_thuoc",
            "Thu tiền thuốc",
            ["/thu-ngan/thuoc"],
            ["thu_tien_thuoc"],
            "Lễ tân, thu ngân, dược sĩ",
        ),
        _lego(
            "viec_can_xu_ly",
            "Việc cần xử lý",
            ["/viec-can-xu-ly"],
            ["viec_can_xu_ly"],
            "Quản lý, trưởng ca",
        ),
        _lego(
            "dieu_phoi",
            "Điều phối khách",
            [
                "/truong-ca",
                "/truong-ca/lich-su",
                "/truong-ca/tv",
            ],
            ["truong_ca", "dieu_phoi"],
            "Trưởng ca",
        ),
        _lego(
            "dat_lich",
            "Đặt lịch",
            ["/appointments"],
            ["dat_lich", "quan_ly_lich"],
            "CSKH, lễ tân",
        ),
        _lego(
            "them_benh_nhan",
            "Thêm bệnh nhân",
            ["/patients/new"],
            ["them_benh_nhan"],
            "Lễ tân, CSKH",
        ),
        _lego(
            "cham_soc_khach",
            "Chăm sóc khách hàng",
            ["/customers", "/nhac-tai-kham"],
            ["cham_soc_khach"],
            "CSKH",
        ),
        _lego(
            "ds_benh_nhan",
            "Danh sách bệnh nhân",
            ["/patient-list"],
            ["ds_benh_nhan"],
            "CSKH, lễ tân",
        ),
        _lego(
            "kho_thuoc",
            "Kho thuốc",
            [
                "/pharmacy",
                "/pharmacy/inventory",
                "/pharmacy/history",
                "/pharmacy/consult",
            ],
            ["nha_thuoc", "xem_nha_thuoc"],
            "Dược sĩ (+ lễ tân)",
        ),
        _lego(
            "lich_lam_viec",
            "Lịch làm việc",
            ["/schedule"],
            ["lich_lam_viec"],
            "Mọi người",
        ),
        # Giá THUỐC sửa ở Kho thuốc (một nguồn giá, 25/09) — lego này chỉ còn
        # bảng giá dịch vụ.
        _lego(
            "bang_gia", "Bảng giá", ["/cashier/dich-vu"], ["bang_gia"], "Thu ngân, QL"
        ),
        _lego(
            "bao_cao", "Báo cáo", ["/reports", "/lich-do-ve"], ["bao_cao"], "Quản lý"
        ),
        _lego(
            "cai_dat",
            "Cài đặt phòng khám",
            [
                "/settings",
                "/settings/booking-policy",
                "/settings/clinic-config",
                "/settings/day-noi",
                # Mẫu kết quả (27/09/2026): gắn mẫu cho dịch vụ, sửa / tạo mẫu.
                "/settings/mau-ket-qua",
            ],
            ["cai_dat", "danh_muc"],
            "Quản lý",
        ),
        _lego(
            "nhan_su",
            "Nhân sự & phân quyền",
            [
                "/nhan-su",
                "/settings/tai-khoan",
                "/settings/new-user",
                "/phan-quyen",
                # Dọn dữ liệu khách thử (30/09/2026) — cửa `permission.manage`.
                "/settings/don-du-lieu-thu",
            ],
            ["nhan_su", "quan_tri_quyen"],
            "Quản lý",
        ),
        _lego(
            "van_hanh",
            "Vận hành hệ thống",
            ["/ops", "/audit-log"],
            ["van_hanh", "lich_su_thao_tac"],
            "Quản lý",
        ),
        _lego("doi_tac", "Đối tác", ["/doi-tac"], ["doi_tac"], "Đối tác"),
    )
}

#: Luôn bật — không gắn khối nào, vẫn HIỆN trên màn Phân quyền (hàng khoá) để
#: quản lý theo dõi; sau này có thể cho tắt.
LUON_BAT: list[tuple[str, str]] = [
    ("Trang chủ", "/home"),
    ("Hành trình khách hôm nay", "/hanh-trinh"),
]

#: (Cũ — thay bằng lego 11–13, 21 và LUON_BAT từ 25/09/2026.) Giữ tên để màn
#: "Theo màn" cũ không vỡ; không còn màn nào đi theo vai.
MAN_THEO_VAI: list[tuple[str, str]] = []

#: Khối KHÔNG bày trên màn Phân quyền (Tuyền 25/09): Duyệt kết quả, Xác nhận tệp
#: (OFF 23–24/09, giữ code sau cờ). Ghi bệnh án đi kèm lego có ô ghi (3, 4, 5).
KHOI_AN: frozenset[str] = frozenset({"duyet_ket_qua", "xac_nhan_ket_qua", *KHOI_NOI_BO})


def man_dang_bat(khoi: Sequence[str]) -> list[str]:
    """Màn nào đang bật với một tập khối: đủ MỌI khối của màn ấy."""
    co = set(khoi)
    return [m.ma for m in MAN.values() if set(m.khoi) <= co]


#: VAI CŨ DO LEGO QUYẾT (Tuyền chốt 26/09/2026: khám, chỉ định, kê đơn "chỉ cần
#: lego"). Còn ~100 chỗ trong mã hỏi VAI (`require_role`, `co_vai`) — sửa từng
#: chỗ là dễ sót. Thay vào đó vai của các chỗ ấy SUY TỪ LEGO ĐANG BẬT ĐỦ: bật
#: Bàn khám thì qua mọi cửa của vai Bác sĩ; tắt thì mất, dù tài khoản là bác sĩ.
#:
#: "Bật đủ", không phải "có một khối": thư ký có khối Khám nhưng không có Hoàn
#: tất — tính theo một khối là thư ký thành bác sĩ.
#:
#: Vai KHÔNG có ở đây (Quản lý, Thư ký, BS siêu âm, Đối tác, TV) vẫn theo tài
#: khoản: chưa lego nào nói trọn việc của chúng.
VAI_THEO_LEGO: dict[str, str] = {
    "ban_kham": "DOCTOR",
    "do_sinh_hieu": "NURSE_ULTRASOUND",
    "tiep_don": "RECEPTION",
    "thu_tien_dv": "CASHIER_DV",
    "thu_tien_thuoc": "CASHIER_THUOC",
    "dieu_phoi": "TRUONG_CA",
    "kho_thuoc": "PHARMACIST",
    "cham_soc_khach": "CSKH",
    # 28/09/2026: lego Phòng dịch vụ (hoặc được xếp vào phòng dịch vụ hôm nay)
    # mang vai người làm dịch vụ — các cửa cũ hỏi vai siêu âm / điều dưỡng dịch
    # vụ đi theo lego, không theo vai tài khoản.
    "phong": "NURSE_ULTRASOUND",
}

#: Vai tài khoản mà lego quyết — tài khoản mang vai này mà lego tắt thì KHÔNG
#: còn vai ấy. Thu ngân gộp = bật đủ cả hai lego thu tiền.
VAI_DO_LEGO: frozenset[str] = frozenset({*VAI_THEO_LEGO.values(), "CASHIER"})


def vai_tu_lego(khoi: Sequence[str]) -> frozenset[str]:
    """Vai (mã chuỗi) mà tập khối của một người mang lại."""
    bat = set(man_dang_bat(khoi))
    vai = {VAI_THEO_LEGO[m] for m in bat if m in VAI_THEO_LEGO}
    if {"thu_tien_dv", "thu_tien_thuoc"} <= bat:
        vai.add("CASHIER")
    return frozenset(vai)


def khoi_sau_khi_doi_man(khoi: Sequence[str], ma_man: str, bat: bool) -> list[str]:
    """Tập khối mới khi bật/tắt một màn. Tắt thì chỉ gỡ khối KHÔNG còn màn nào
    khác đang bật cần tới — tắt "Phòng dịch vụ" không được lấy mất khối mà
    "Bàn khám" còn dùng."""
    man = MAN[ma_man]
    co = set(khoi)
    if bat:
        return sorted(co | set(man.khoi))
    con_can: set[str] = set()
    for khac in man_dang_bat(khoi):
        if khac != ma_man:
            con_can |= set(MAN[khac].khoi)
    return sorted(co - (set(man.khoi) - con_can))


def quyen_cua_khoi(ma_khoi: str) -> list[str]:
    """Mọi quyền con nằm trong một khối."""
    return [q.ma for q in QUYEN.values() if q.khoi == ma_khoi]


def quyen_cua_preset(vai: str) -> list[str]:
    """Mọi quyền mà preset của một vai cấp — dùng khi quản lý bấm thêm preset."""
    return [ma for khoi in PRESET.get(vai, []) for ma in quyen_cua_khoi(khoi)]


def tra_quyen(ma: str) -> Quyen:
    try:
        return QUYEN[ma]
    except KeyError:
        raise ValueError(
            f"Quyền '{ma}' chưa khai trong danh mục "
            "(src/clinicai/permissions/catalogue.py)."
        ) from None


__all__ = [
    "KHOI",
    "KHOI_AN",
    "KHOI_CHI_QUAN_LY",
    "KHOI_MO_FULL",
    "LUON_BAT",
    "MAN",
    "PRESET",
    "PRESET_TRUOC_MO_FULL",
    "QUYEN",
    "VAI_DO_LEGO",
    "VAI_THEO_LEGO",
    "KhoiCongViec",
    "MucRuiRo",
    "PhamVi",
    "Quyen",
    "quyen_cua_khoi",
    "quyen_cua_preset",
    "tra_quyen",
    "vai_tu_lego",
]
