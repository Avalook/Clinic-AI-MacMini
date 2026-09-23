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

MỘT HÀNG RÀO KHÔNG MỞ BẰNG TICK. Quyền có `chung_chi_lam_sang = True` (duyệt kết
quả, ký bệnh án, duyệt đơn thuốc, chốt chẩn đoán) đụng luật hành nghề, không phải
quy ước nội bộ. Hệ thống KHÔNG tự chốt ai đủ tư cách: lệnh cấp quyền từ chối cấp
những quyền này cho người không có vai lâm sàng, và chỗ này còn để MỞ chờ phòng
khám quyết (xem `docs/slices/`).
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
        KhoiCongViec(
            "quan_tri_quyen",
            "Phân quyền",
            "permission",
            "Cấp và thu quyền cho nhân sự",
        ),
    )
}


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
        Quyen(
            "permission.manage",
            "Cấp và thu quyền",
            "quan_tri_quyen",
            "permission",
            MucRuiRo.QUAN_TRI,
        ),
    )
}


# ── Preset theo vai — GỢI Ý, không phải trần quyền ──────────────────────────
# Quản lý tick gì thì người đó có nấy; preset chỉ để cấp cho nhanh (#133).
PRESET: dict[str, Sequence[str]] = {
    "DOCTOR": ["chi_dinh", "dieu_phoi", "ket_qua", "thuc_hien"],
    "TKYK": ["chi_dinh", "dieu_phoi", "ket_qua", "thuc_hien"],
    "RECEPTION": ["tiep_don", "chon_dich_vu", "thu_tien_dv", "dieu_phoi"],
    "NURSE_ULTRASOUND": ["sinh_hieu", "dieu_phoi", "ket_qua", "thuc_hien"],
    "CASHIER": ["thu_tien_dv", "chon_dich_vu"],
    "CASHIER_DV": ["thu_tien_dv", "chon_dich_vu"],
    "CASHIER_THUOC": ["thu_tien_dv"],
    "TRUONG_CA": ["dieu_phoi", "tiep_don", "chon_dich_vu", "thuc_hien"],
    "ULTRASOUND_DOCTOR": ["dieu_phoi", "ket_qua", "thuc_hien"],
    # Quản lý là người chỉnh cao nhất: có phân quyền và mọi khối vận hành.
    "MANAGEMENT": list(KHOI),
}


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
    "PRESET",
    "QUYEN",
    "KhoiCongViec",
    "MucRuiRo",
    "PhamVi",
    "Quyen",
    "quyen_cua_khoi",
    "quyen_cua_preset",
    "tra_quyen",
]
