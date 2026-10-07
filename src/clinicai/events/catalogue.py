"""Danh mục sự kiện — mỗi sự kiện khai đúng MỘT chỗ.

VÌ SAO CÓ FILE NÀY. Trong `event_log` hiện có khoảng 120 mã sự kiện, sinh rải rác
ở 40 file: chuỗi viết thẳng, f-string, hằng số, bảng ánh xạ, tham số hàm SQL.
Không có chỗ nào trả lời được câu "hệ thống này phát ra những sự kiện nào, mỗi
sự kiện chứa gì, ai nghe". Bài kiểm nhãn cũ (`test_audit_labels_drift`) không bắt
được mã đi qua hằng số, nên nhãn đã lệch cả hai chiều: có nhãn cho mã không còn
phát, và có mã phát ra mà không nhãn.

Từ nay: sự kiện nào không khai ở đây thì `emit_event` từ chối phát.

MỖI MỤC KHAI GÌ
    `payload`      khuôn dữ liệu (pydantic) — CI kiểm, không phải người kiểm.
    `consumers`    ai nghe. Thêm bên nghe mới = thêm một dòng ở đây, KHÔNG sửa
                   module phát. Đó là toàn bộ ý nghĩa của "LEGO".
    `is_public`    True = AI/Zalo/đối tác được nghe, và payload thành hợp đồng
                   phải giữ. False = nội bộ, đổi tự do.
    `nhan`         nhãn tiếng Việt cho màn nhật ký.

LUẬT ĐỔI PHIÊN BẢN (mượn luật FULL_TRANSITIVE của Confluent Schema Registry, bỏ
phần hạ tầng Kafka). Sổ sự kiện giữ vĩnh viễn và có thể đọc lại, nên một bản ghi
cũ phải đọc được bằng mọi bản mới:
    * THÊM hoặc BỎ một trường không bắt buộc  → giữ nguyên tên, tăng `version`.
    * Đổi kiểu, đổi nghĩa, thêm trường bắt buộc → PHẢI đặt tên sự kiện mới.
Payload đóng kín (`extra="forbid"`): trường lạ bị từ chối ngay lúc phát, chứ
không chờ tới lúc một consumer nào đó đọc phải.

PAYLOAD CHỨA GÌ. Đủ để bên nghe RA QUYẾT ĐỊNH, không chép cả bảng. Cần thêm thì
hỏi lại bằng `aggregate_id`. Không bao giờ có nội dung lâm sàng, tên khách, số
điện thoại — dữ liệu cá nhân nằm ở bảng hiện trạng, nơi xoá được; sổ này thì
không xoá được.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, ConfigDict


class PayloadSuKien(BaseModel):
    """Gốc chung: payload đóng kín, không cho trường lạ."""

    model_config = ConfigDict(extra="forbid", frozen=True)


# ── Bên nhận (consumer) ─────────────────────────────────────────────────────
# Tên ở đây là khoá trong `event_delivery.consumer`. Đặt tên theo VIỆC nó làm,
# không theo công nghệ: "dong_thoi_gian_luot" chứ không phải "worker_2".
DONG_THOI_GIAN_LUOT = "dong_thoi_gian_luot"
#: Mở việc cho trách nhiệm không được rơi (tiền đã thu, dịch vụ dừng giữa chừng).
TRACH_NHIEM_DICH_VU = "trach_nhiem_dich_vu"
#: Khối HÀNH TRÌNH (Journey Process Manager, thesis §9): giữ luật THỨ TỰ khách
#: đi — nghe sự thật rồi gửi LỆNH xếp hàng. Dây H1…H8 ở docs/BAN-DO-DAY-NOI-LEGO.md.
HANH_TRINH = "hanh_trinh_luot_kham"
#: Khối CHUÔNG: sự kiện nào báo cho ai — người nhận là DỮ LIỆU
#: (`day_nhan_thong_bao`), quản lý chỉnh trên màn.
CHUONG = "chuong_thong_bao"
#: Chuông NHẬN CHÉO (07/10/2026): phòng khác nhận khách lúc phòng A còn ĐANG
#: LÀM (quên Xong) → réo A; lần làm ấy Xong / Gián đoạn / huỷ Bắt đầu → tự đóng
#: (`events/consumers/chuong_nhan_cheo.py`).
CHUONG_NHAN_CHEO = "chuong_nhan_cheo"
#: Khối VÒNG ĐỌC: kết quả/dịch vụ vừa xong → mở vòng đọc cho bác sĩ chính và
#: khép lượt khi không còn gì phải chờ (phát `visit.exam_completed`).
VONG_DOC = "vong_doc_luot_kham"
#: Khối ĐỐI TÁC nhận việc (Tuyền 24/09/2026: "bác sĩ chỉ định sinh event đối tác
#: nhận chưa"): nghe "khách chốt làm" / "đã thu tiền dịch vụ" (đối tác tự lấy
#: mẫu) và "dịch vụ đã làm xong" (mẫu điều dưỡng lấy) → việc sang bàn đối tác +
#: réo chuông đối tác.
DOI_TAC_NHAN_VIEC = "doi_tac_nhan_viec"
#: Khối CÔNG NỢ (01/10/2026): nghe "đã thu tiền" → lượt có khoản ghi nợ mà nay
#: hết nợ thì khoản ấy chuyển ĐÃ THU (`events/consumers/cong_no.py`).
CONG_NO = "cong_no"
#: Lịch ĐIỀU TRỊ (07/10/2026): khách đã vào hàng → sinh sẵn chỉ định đúng dịch vụ
#: đã đặt (`events/consumers/dieu_tri.py`). Không xếp phòng, không thu tiền khám.
DIEU_TRI_SINH_CHI_DINH = "dieu_tri_sinh_chi_dinh"


@dataclass(frozen=True)
class SuKien:
    """Một mục trong danh mục."""

    ten: str
    version: int
    aggregate_type: str
    source_module: str
    payload: type[PayloadSuKien]
    nhan: str
    # Sequence chứ không phải tuple: tuple một phần tử phải viết kèm dấu phẩy
    # cuối, và bài kiểm cú pháp SQL quét mọi dòng Python sẽ báo nhầm.
    consumers: Sequence[str] = ()
    is_public: bool = True
    # True khi sự kiện mang thông tin phải xử lý đúng thứ tự trong cùng một
    # aggregate (ví dụ: xếp phòng rồi mới bắt đầu làm).
    theo_thu_tu: bool = False


# ── service_order ───────────────────────────────────────────────────────────


class ChiDinhDoiBatBuoc(PayloadSuKien):
    """`service_order.required_changed` — người chỉ định bật / tắt "Bắt buộc"
    (Tuyền 25/09/2026). Chỉ khi dịch vụ CHƯA thu tiền."""

    visit_id: str
    service_order_id: str
    bat_buoc: bool


class ChiDinhDaDat(PayloadSuKien):
    """`service_order.placed` — bác sĩ/thư ký y khoa đã chốt một chỉ định."""

    order_id: str
    service_code: str
    service_name: str
    consultation_id: str
    visit_id: str
    # Trạng thái ngay sau khi đặt, để bên nghe khỏi phải tự suy.
    selection_status: str
    billing_status: str


class LamThemDaThem(PayloadSuKien):
    """`service_order.desk_added` — lễ tân / người đo sinh hiệu tick "+ dịch vụ"
    (làm thêm tại quầy, Tuyền 01/10/2026): chỉ định ĐÃ CHỐT làm, không qua bác
    sĩ. `nguon` = 'tiep_don' | 'sinh_hieu'."""

    visit_id: str
    service_order_id: str
    service_code: str
    service_name: str
    nguon: str


class LamThemDaBo(PayloadSuKien):
    """`service_order.desk_removed` — bỏ tick "+ dịch vụ" khi chưa làm, chưa
    thu: chỉ định huỷ (không xoá — vẫn đọc được là đã có lần tick). `nguon` =
    nơi bấm bỏ."""

    visit_id: str
    service_order_id: str
    service_code: str
    nguon: str


class VatTuDaDoi(PayloadSuKien):
    """`visit.supply_changed` — thêm / đổi số lượng / bỏ một vật tư khách mua thêm
    ở quầy Thu tiền dịch vụ (Tuyền 01/10/2026, C13). Tiền vật tư là tiền DỊCH VỤ:
    quầy thu và các màn nghe `luot_vat_tu` đọc lại hoá đơn. `hanh_dong` = 'them'
    | 'sua' | 'bo'. Không có tên khách — chỉ mã lượt + mặt hàng."""

    visit_id: str
    luot_vat_tu_id: str
    service_price_id: str
    ten: str
    hanh_dong: str
    so_luong: int
    don_gia: int
    #: Hàng phải có quản lý duyệt (vòng Mirena thứ 2…).
    can_ql_duyet: bool = False


class DichVuKhamDaDoi(PayloadSuKien):
    """`visit.exam_service_changed` — tick / bỏ tick DỊCH VỤ KHÁM CON của lượt
    (bảng `luot_phi_kham`, C18 02/10/2026). Trước đây chỉ ghi nhật ký thao tác,
    nên Hành trình khách không thấy khách đã khám dịch vụ gì. `them` / `bo` là
    danh sách `{id, ten, gia}` (đồng; gia None = chưa có giá); `loai_kham` =
    tên loại khám đặt lịch. Không có tên khách."""

    visit_id: str
    loai_kham: str | None = None
    them: list[dict[str, str | int | None]] = []
    bo: list[dict[str, str | int | None]] = []


class ChiDinhMangSang(PayloadSuKien):
    """`service_order.carried_over` — chỉ định chưa làm ở lượt trước được mang
    sang lượt này (dây H2). Đã trả tiền thì không thu lại."""

    visit_id: str
    service_order_id: str
    tu_visit_id: str
    service_code: str
    da_thu_tien: bool


# ── payment ─────────────────────────────────────────────────────────────────


class TienDichVuDaThu(PayloadSuKien):
    """`payment.service_collected` — tiền DỊCH VỤ đã thật sự nhận đủ.

    Tiền mặt: lúc bấm "Đã nhận đủ". Chuyển khoản/QR: lúc xác minh, KHÔNG phải
    lúc khách quét mã. Đây là mốc khối Hành trình nghe để tự xếp phòng (H4).
    """

    visit_id: str
    payment_cycle_id: str
    so_tien: int
    phuong_thuc: str
    #: Chỉ định phòng khám thu trong lần thu này (không có tên, không có giá).
    order_ids: list[str] = []


class TienThuocDaThu(PayloadSuKien):
    """`payment.medicine_collected` — tiền THUỐC đã thật sự nhận (không cần
    bác sĩ bấm Khám xong — Tuyền 24/09/2026)."""

    visit_id: str
    payment_cycle_id: str
    so_tien: int
    phuong_thuc: str


class HinhThucThuDaDoi(PayloadSuKien):
    """`payment.method_changed` — phiếu đã thu được ghi lại hình thức (TM/CK/QR)
    sau khi thu (V7, 30/09/2026). Không phải huỷ: số tiền và phiếu giữ nguyên.

    ``tu`` rỗng = phiếu cũ trước CP2 không biết hình thức lúc thu. Không mang
    mã giao dịch (thông tin ngân hàng ở bảng, không ở sổ sự kiện).
    """

    visit_id: str
    payment_cycle_id: str
    kind: str
    so_tien: int
    tu: str | None = None
    sang: str


class LanThuDaHoanTac(PayloadSuKien):
    """`payment.collection_undone` — một LẦN THU được hoàn tác (Tuyền 01/10/2026:
    "nhân viên làm lại thao tác bị sai"): thu nhầm → trả lại ngay, lượt về CHƯA
    THU (dịch vụ đã làm thì thành còn nợ). Khác `payment.refunded` (khách đã trả
    đúng, giờ trả lại một phần — tiền thật đi ra).

    ``truoc``: trạng thái lần thu trước khi hoàn tác — ``PAID`` (huỷ phiếu đã
    thu) hay ``PENDING_VERIFICATION`` (bỏ lần chuyển khoản chờ xác minh).
    ``ly_do`` là chữ vận hành người bấm gõ (tuỳ chọn) — không chữ lâm sàng.
    """

    visit_id: str
    payment_cycle_id: str
    kind: str
    so_tien: int
    truoc: str
    ly_do: str | None = None


class ThuocDaGiao(PayloadSuKien):
    """`medicine.dispensed` — quầy thuốc giao thuốc cho khách (một dòng đơn).

    Mang BA con số để đối chiếu "đơn bác sĩ kê" với "đơn khách chốt" (Tuyền
    24/09: quầy thuốc lưu 2 bản): số kê, số khách mua, số đã giao tới giờ.
    Không mang tên thuốc — sổ này không xoá được, hỏi bảng đơn khi cần.
    """

    visit_id: str
    prescription_id: str
    so_ke: str | None = None
    so_mua: str | None = None
    so_da_giao: str


# ── kết quả: tệp, xem, duyệt, gửi khách (nhóm 3) ──────────────────────────


class TepKetQuaDaVe(PayloadSuKien):
    """`result_file.uploaded` — một tệp kết quả vừa vào hồ sơ khách.

    Tệp của ĐỐI TÁC phải có người xác nhận đúng người/đúng chỉ định trước khi
    dùng (`cho_xac_nhan`); tệp nội bộ dùng được ngay.
    """

    tep_id: str
    visit_id: str | None = None
    service_order_id: str | None = None
    cho_xac_nhan: bool = False


class TepKetQuaDaXacNhan(PayloadSuKien):
    """`result_file.confirmed` — xác nhận tệp đối tác: HOP_LE / TU_CHOI."""

    tep_id: str
    visit_id: str | None = None
    service_order_id: str | None = None
    trang_thai: str


class TepKetQuaDaThuHoi(PayloadSuKien):
    """`result_file.revoked` — tệp bị thu hồi (tải nhầm khách / nhầm chỉ định)."""

    tep_id: str
    visit_id: str | None = None
    service_order_id: str | None = None


class TepKetQuaDaXoa(PayloadSuKien):
    """`result_file.deleted` — tệp bị xoá mềm (V9 30/09/2026): ẩn khỏi mọi chỗ
    đọc, khôi phục được 30 ngày. `loai` = XOA | DINH_CHINH (gỡ tệp đã gửi khách
    / phiên đọc đã đóng). Lý do là chữ vận hành người xoá gõ."""

    tep_id: str
    visit_id: str | None = None
    service_order_id: str | None = None
    loai: str
    ly_do: str


class TepKetQuaDaKhoiPhuc(PayloadSuKien):
    """`result_file.restored` — tệp đã xoá mềm được khôi phục (trong 30 ngày)."""

    tep_id: str
    visit_id: str | None = None
    service_order_id: str | None = None


class TepKetQuaDaXem(PayloadSuKien):
    """`result_file.viewed` — lần ĐẦU người làm chuyên môn mở tệp (tự ghi).

    Duyệt kết quả không bắt buộc (Tuyền 24/09): "đã xem" thay cho "đã duyệt" để
    biết kết quả nào chưa ai xem.
    """

    tep_id: str
    visit_id: str | None = None


class KetQuaDaGuiKhach(PayloadSuKien):
    """`result_file.sent_to_patient` — CSKH đánh dấu đã gửi kết quả cho khách."""

    tep_id: str
    visit_id: str | None = None
    kenh: str


class KetQuaXetNghiemVe(PayloadSuKien):
    """`lab_result.arrived` — kết quả xét nghiệm NHẬP TAY vừa về LẦN ĐẦU (sửa
    lại không phát lần nữa). Trước 24/09 lệnh nhập gọi thẳng chuông."""

    lab_result_id: str
    visit_id: str | None = None


class PhieuKetQuaDaXem(PayloadSuKien):
    """`result.viewed` — lần ĐẦU người làm chuyên môn mở PHIẾU kết quả (tự ghi)."""

    service_order_id: str
    visit_id: str | None = None


class KetQuaDaDuyet(PayloadSuKien):
    """`result.reviewed` — bác sĩ bấm duyệt (không bắt buộc) một chỉ định."""

    service_order_id: str
    visit_id: str | None = None


# ── lịch hẹn + rời phòng khám (nhóm 3) ──────────────────────────────────────


class LichDaDat(PayloadSuKien):
    """`appointment.booked` — CSKH / lễ tân đặt một lịch hẹn."""

    appointment_id: str
    bat_dau: str
    kenh: str | None = None


class LichDaDoi(PayloadSuKien):
    """`appointment.rescheduled` — đổi giờ và/hoặc bác sĩ. Lịch sử đầy đủ ở
    `appointment_doi_lich` (từ → đến, ai đổi, lý do)."""

    appointment_id: str
    tu_bat_dau: str | None = None
    den_bat_dau: str | None = None
    doi_bac_si: bool = False


class LichDaHuy(PayloadSuKien):
    """`appointment.cancelled` — huỷ lịch (mã lý do, không phải lời khách nói)."""

    appointment_id: str
    ly_do_ma: str | None = None


class LichDaDoiDichVu(PayloadSuKien):
    """`appointment.service_switched` — đổi DỊCH VỤ KHÁM của lịch (menu ⋯ dòng
    lịch hẹn, V5 30/09/2026). Có ``visit_id`` = đổi SAU check-in (lượt khám đổi
    theo) → khối Hành trình tính lại hàng chờ đầu tiên của lượt."""

    appointment_id: str
    visit_id: str | None = None
    tu_dich_vu_id: str | None = None
    den_dich_vu_id: str
    tu_ten: str | None = None
    den_ten: str | None = None
    #: Đổi ngay TRONG HỒ SƠ KHÁM (bác sĩ / ĐD / thư ký / trưởng ca / QL, 07/10/2026)
    #: — đã có phiếu / đã thu / đã tick vẫn đổi được; phiếu cũ giữ nguyên.
    trong_ho_so: bool = False


class KhachKhongDen(PayloadSuKien):
    """`appointment.no_show` — tới giờ mà khách không đến."""

    appointment_id: str


class CskhDaGoiXacNhan(PayloadSuKien):
    """`appointment.confirmed_by_call` — CSKH gọi khách xác nhận lịch."""

    appointment_id: str


class KhachDaVe(PayloadSuKien):
    """`visit.checked_out` — lễ tân đóng lượt, khách rời phòng khám."""

    visit_id: str
    con_vuong: int = 0


class KhachBoVeGiuaChung(PayloadSuKien):
    """`visit.left_early` — khách về giữa chừng (lượt INCOMPLETE, có lý do)."""

    visit_id: str


class DaHoanTien(PayloadSuKien):
    """`payment.refunded` — một khoản hoàn tiền đã xong."""

    visit_id: str
    refund_id: str
    so_tien: int


class DaHenTaiKham(PayloadSuKien):
    """`followup.scheduled` — bác sĩ hẹn tái khám (ghi lúc bấm Khám xong)."""

    visit_id: str
    ngay: str


class DoiTacDaLayMau(PayloadSuKien):
    """`partner.sample_collected` — đối tác tự lấy mẫu, bấm "Đã lấy mẫu"."""

    visit_id: str
    service_order_id: str


class DoiTacDaNhanMau(PayloadSuKien):
    """`partner.sample_received` — đối tác bấm "Nhận mẫu": việc đối tác XONG
    (Tuyền 29/09/2026). Kết quả về sau là mốc tuỳ chọn, không giữ vòng / lượt."""

    visit_id: str
    service_order_id: str


class DoiTacNhanViec(PayloadSuKien):
    """`partner.order_received` — một chỉ định làm bên ngoài vừa sang bàn đối tác.

    `ly_do`: DA_THU_TIEN (đối tác tự lấy mẫu, khách đã trả phòng khám) ·
    KHACH_DA_CHON (đối tác tự lấy mẫu VÀ tự thu tiền — khách vừa chốt làm ở
    quầy, 27/09/2026) · DA_LAY_MAU (điều dưỡng lấy mẫu xong ở phòng) ·
    MAU_GUI_DOI_TAC (dịch vụ thu hộ đối tác làm ở phòng CỦA phòng khám — vd Giải
    phẫu bệnh ở phòng Thủ thuật — vừa xong, mẫu gửi đối tác; 29/09/2026).

    `thu_sau` (V10, 30/09/2026 — làm trước, thu sau): KHACH_DA_CHON của dịch vụ
    PHÒNG KHÁM thu hộ mà quầy chưa thu — đối tác đến lấy mẫu, KHÔNG thu tiền
    khách (quầy thu cuối buổi)."""

    visit_id: str
    service_order_id: str
    service_name: str | None = None
    ly_do: str
    thu_sau: bool = False


class DoiTacDaThuTien(PayloadSuKien):
    """`partner.payment_recorded` — đối tác ghi nhận ĐÃ THU tiền khách cho một
    việc (Tuyền 27/09/2026, Q1: khách trả trực tiếp cho đối tác). Không phải
    tiền phòng khám."""

    visit_id: str
    service_order_id: str
    so_tien: int
    hinh_thuc: str


class DoiTacHuyThuTien(PayloadSuKien):
    """`partner.payment_voided` — đối tác huỷ một ghi nhận đã thu (ghi nhầm /
    sửa số). Lý do nằm ở bảng `doi_tac_thanh_toan`, không vào sổ sự kiện."""

    visit_id: str
    service_order_id: str
    so_tien: int


class CskhDaLienHe(PayloadSuKien):
    """`patient.contacted` — CSKH đã liên hệ khách (gọi / nhắn), kèm kết quả."""

    clinic_patient_id: str
    loai: str
    ket_qua: str | None = None


# ── permission ──────────────────────────────────────────────────────────────


class KhoiQuyenDaCap(PayloadSuKien):
    """`capability.granted` — quản lý bật một khối công việc cho một người."""

    staff_id: str
    work_pack: str
    capabilities: list[str]
    scope_type: str
    scope_id: str | None = None


class KhoiQuyenDaThu(PayloadSuKien):
    """`capability.revoked` — quản lý tắt một khối."""

    staff_id: str
    work_pack: str
    capabilities: list[str]


class NgoaiLeCaTruc(PayloadSuKien):
    """Mở/huỷ quyền làm thay bác sĩ ngoài ca, không chứa dữ liệu người bệnh."""

    staff_id: str
    bac_si_id: str | None = None
    ngay: date
    ly_do: str


# ── result (biểu mẫu kết quả) ───────────────────────────────────────────────


class PhieuDaHoanTat(PayloadSuKien):
    """`result_form.completed` — người làm xác nhận toàn bộ nội dung phiếu."""

    service_order_id: str
    # Thuộc lượt khám nào. Thiếu trường này thì màn hành trình không biết xếp
    # phiếu vào chỗ nào — đúng lỗi đã bắt được lúc chạy thử.
    visit_id: str | None = None
    form_id: str
    form_version: int
    # Người GÕ khác người THỰC HIỆN: điều dưỡng nhập thay bác sĩ là chuyện thường.
    nhap_boi: str | None = None
    thuc_hien_boi: str | None = None
    # Điền thiếu vẫn hoàn tất được; con số này để CSKH và quản lý nhìn, không chặn.
    so_o_con_trong: int = 0


class KetQuaSanSang(PayloadSuKien):
    """`result.ready` — đã có kết quả để ĐỌC, không chỉ là dịch vụ đã làm xong.

    Vì sao tách khỏi `service.completed` (ChatGPT #64, #156): lấy mẫu xét
    nghiệm gửi ra ngoài thì dịch vụ xong hôm nay, kết quả hai ngày sau mới về.
    Một hệ gộp hai thứ này sẽ báo "có kết quả" khi chưa ai đọc được gì.

    Đây là sự kiện làm bàn bác sĩ chính nổi lên "🔔 Có kết quả mới" — nên nó
    không được phát sớm một phút nào.
    """

    service_order_id: str
    visit_id: str | None = None
    form_id: str
    form_version: int
    result_mode: str
    #: Bản kết quả thứ mấy. Lần [Hoàn tất] đầu tiên LUÔN là 1 — không bao giờ
    #: lấy `form_instance.revision`, vì số ấy tăng cả khi tự lưu nháp.
    ban_thu: int = 1
    thuc_hien_boi: str | None = None


class KetQuaDaSua(PayloadSuKien):
    """`result.corrected` — kết quả đã công bố nay được sửa lại.

    Không phải lỗi hệ thống, là chuyện bình thường của phòng khám: hệ thống
    không khoá người dùng, nó GHI LẠI (cùng luật với sinh hiệu sửa sau khi
    hoàn tất). Ai đang mở kết quả cũ phải biết là nó vừa đổi.
    """

    service_order_id: str
    visit_id: str | None = None
    form_id: str
    form_version: int
    #: Bản thứ mấy của kết quả này. Bản 1 là bản `result.ready` đầu tiên.
    ban_thu: int
    sua_boi: str | None = None


# ── hành trình khách (tiếp đón, sinh hiệu) ─────────────────────────────────


class KhachDaToi(PayloadSuKien):
    """`visit.checked_in` — khách đã tới và lượt khám mở ra."""

    visit_id: str
    appointment_id: str | None = None
    # Số thứ tự để gọi tên ở phòng chờ. KHÔNG có tên, tuổi, số điện thoại.
    so_thu_tu: int | None = None


class LuotDaKhamXong(PayloadSuKien):
    """`visit.exam_completed` — phần KHÁM của lượt đã khép hẳn: mọi phiên khám
    xong, không vòng đọc nào mở, không chỉ định nào còn chờ làm.

    Khác `consultation.completed` (một lần bấm Hoàn tất): bác sĩ có thể Hoàn
    tất khi khách còn đi làm dịch vụ; mốc này chỉ tới khi thật sự hết việc.
    Quầy thu tiền / nhà thuốc / nhắc check-out nghe mốc này thay vì tự dò.
    """

    visit_id: str


class DaXepDuongDi(PayloadSuKien):
    """`visit.routed` — khối Hành trình đã quyết khách đi đâu tiếp.

    `dich`: TU_VAN (hàng bác sĩ tư vấn) · PRIMARY (hàng bác sĩ chính) ·
    SERVICES (lịch đi thẳng phòng — làm chỉ định mang sang, dây H2).
    """

    visit_id: str
    dich: str
    ly_do: str


class PhienKhamBatDau(PayloadSuKien):
    """`consultation.started` — người khám bấm Bắt đầu (tư vấn / khám / đọc KQ)."""

    visit_id: str
    consultation_id: str
    loai: str


class PhienKhamTiepTuc(PayloadSuKien):
    """`consultation.resumed` — khách quay lại, bác sĩ bấm "Bắt đầu khám" lần
    nữa (07/10/2026). Cột `serving_at` của chỗ chờ là giá trị HIỆN TẠI; mốc lần
    trước nằm ở đây để không mất. `lan` = lần bắt đầu thứ mấy (lần đầu là
    `consultation.started`)."""

    visit_id: str
    consultation_id: str
    loai: str
    lan: int
    quay_ve_hang_luc: str | None = None
    bat_dau_lan_truoc_luc: str | None = None


class TuVanXong(PayloadSuKien):
    """`consultation.handed_over` — bác sĩ tư vấn xong, chuyển bác sĩ chính."""

    visit_id: str
    consultation_id: str


class KhamXong(PayloadSuKien):
    """`consultation.completed` — bấm Hoàn tất / Khám xong (một nút).

    Bệnh án lưu liên tục KHÔNG phát sự kiện; chỉ mốc này (Tuyền chốt 24/09).
    """

    visit_id: str
    consultation_id: str
    loai: str
    ket_qua: str


class SinhHieuBatDau(PayloadSuKien):
    """`vitals.started` — điều dưỡng bấm [Bắt đầu] đo cho khách này.

    Mốc để đo THỜI GIAN CHỜ ĐO, không phải cửa khoá: lưu sinh hiệu mà chưa ai
    bấm [Bắt đầu] vẫn được. Không mang chỉ số — chưa đo gì cả.
    """

    visit_id: str


class SinhHieuDaDo(PayloadSuKien):
    """`vitals.recorded` — điều dưỡng đã đo xong.

    KHÔNG mang chỉ số. Huyết áp là dữ liệu lâm sàng, mà sổ sự kiện thì không xoá
    được; ai cần số thì hỏi bảng sinh hiệu, nơi có quyền đọc riêng.
    """

    visit_id: str
    qua_duong: str = "man_do_sinh_hieu"
    # Điều dưỡng tick "Bỏ qua bác sĩ tư vấn" lúc bấm [Đo xong] (Tuyền 25/09/2026)
    # → Hành trình xếp khách thẳng hàng bác sĩ chính. Mặc định False: sự kiện
    # cũ (không có trường này) đọc lại vẫn đúng nghĩa.
    bo_qua_tu_van: bool = False


# ── execution (thực hiện dịch vụ) ───────────────────────────────────────────


class DichVuDaBatDau(PayloadSuKien):
    """`service.started` — một LẦN LÀM bắt đầu (không phải chỉ định bắt đầu)."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    room_id: str | None = None
    execution_revision: int
    #: Nơi làm khi KHÔNG phải phòng của chỉ định: "BAN_KHAM" (07/10/2026).
    noi_lam: str | None = None
    #: Làm tại bàn khám đã CHỐT HỘ lựa chọn của khách cho đúng chỉ định này
    #: (bác sĩ làm = khách đồng ý) — hoàn tác Bắt đầu trả lại (07/10/2026).
    chot_lua_chon: bool = False


class ThuocQuayDaChinh(PayloadSuKien):
    """`medicine.counter_changed` — quầy thuốc vừa chỉnh đơn BÁN trước khi thu
    (Tuyền 24/09/2026): bỏ tick / tích lại / đổi số lượng / thêm / sửa / bỏ
    dòng quầy thêm. Chỉ hành động + mã dòng — không tên thuốc, không liều."""

    visit_id: str
    prescription_id: str
    #: BO_CHON | CHON_LAI | SO_LUONG | THEM | SUA | BO_DONG_THEM
    #: | DIEN_SO_LUONG (C14: quầy điền / sửa số lượng bác sĩ để trống)
    #: | SUA_SO_LUONG (C19: quầy đặt số khác số bác sĩ đã kê, tăng hay giảm)
    hanh_dong: str
    nguon: str
    so_luong: str | None = None
    #: Số trước khi quầy điền / sửa (None = bác sĩ để trống).
    so_luong_cu: str | None = None


class ThuocBiBo(PayloadSuKien):
    """`medicine.declined` — ở BẢN CUỐI CÙNG THANH TOÁN, dòng thuốc này khách
    không lấy (so_mua = 0) hoặc lấy bớt (so_mua < so_ke). Phát đúng lúc tiền
    thuốc thật sự nhận, so đơn với ảnh chụp hoá đơn của lần thu ấy."""

    visit_id: str
    prescription_id: str
    payment_cycle_id: str
    nguon: str
    so_ke: str | None = None
    so_mua: str


class DonThuocDaLuu(PayloadSuKien):
    """`prescription.saved` — bác sĩ vừa kê / sửa đơn thuốc của lượt (đơn chưa
    ký, bản đang dùng). Chỉ số dòng — không tên thuốc, không liều."""

    visit_id: str
    so_dong: int
    so_dong_them: int = 0
    so_dong_thay: int = 0
    so_dong_bo: int = 0


class KhachDaChonDichVu(PayloadSuKien):
    """`service_selection.confirmed` — lễ tân chốt khách làm / không làm những
    chỉ định nào (SELECTION v1). Vòng đọc nghe: chỉ định khách bỏ thành việc
    bác sĩ quyết, không treo vòng đọc."""

    visit_id: str
    selection_revision: int
    selected_order_ids: list[str] = []
    not_selected_order_ids: list[str] = []


class LamTruocThuSauDaBat(PayloadSuKien):
    """`visit.defer_payment_set` — tick "Làm trước – thu sau" cho lượt (Tuyền
    30/09/2026 tối). Dây ``thu_truoc_khi_lam`` BẬT: từ lúc này chỉ định của lượt
    xếp phòng / bắt đầu làm được khi chưa thu. Hành trình nghe để xếp phòng
    ngay; Đối tác nghe để nhận việc."""

    visit_id: str
    #: Số chỉ định còn chờ khách quyết được chốt "làm" cùng lúc tick.
    so_chi_dinh_chot: int = 0


class LamTruocThuSauDaBo(PayloadSuKien):
    """`visit.defer_payment_cleared` — bỏ tick "Làm trước – thu sau" (hoàn tác,
    01/10/2026: được cả khi đã có dịch vụ bắt đầu làm — khi ấy khoản đã làm vẫn
    còn nợ, dịch vụ chưa làm quay về luật thu trước)."""

    visit_id: str
    #: Lúc bỏ tick đã có chỉ định bắt đầu / làm xong chưa.
    da_bat_dau: bool = False


class DichVuDaXong(PayloadSuKien):
    """`service.completed` — lần làm ấy xong. KHÁC `result.ready`."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    execution_revision: int
    noi_lam: str | None = None


class DichVuKhongLam(PayloadSuKien):
    """`service.not_performed` — tới lượt rồi nhưng cuối cùng không làm."""

    visit_id: str
    service_order_id: str
    ly_do: str
    execution_revision: int
    # Đã thu tiền mà không làm thì có người phải xử lý; nói thẳng trong sự kiện.
    da_thu_tien: bool = False


class DichVuGianDoan(PayloadSuKien):
    """`service.interrupted` — đang làm thì phải dừng."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    ly_do: str
    execution_revision: int


class DaXepPhong(PayloadSuKien):
    """`service.routed` — chỉ định đã có phòng (xếp lần đầu, hoặc đổi phòng).

    `tu_dong` = khối Hành trình xếp thay người vừa thu tiền (H4); False = người
    bấm. Lần sau đè lần trước — ai có quyền điều phối đổi lại được.
    """

    visit_id: str
    service_order_id: str
    room_id: str
    from_room_id: str | None = None
    routing_revision: int
    ly_do: str
    tu_dong: bool = False
    #: Nguồn lần xếp (25/09/2026): quay_thu · truong_ca · tu_dong · khac — để
    #: Lịch sử điều phối hiện "ai đổi, từ màn nào". Sự kiện cũ không có → None.
    nguon: str | None = None
    #: Dây H4 xếp đúng PHÒNG DỰ KIẾN ai đặt trước (quay_thu · truong_ca) — lịch
    #: sử nói "tự động theo phòng trưởng ca chọn trước" (29/09/2026).
    du_kien_nguon: str | None = None
    #: NHẬN TẠI PHÒNG (nguon='tai_phong', 07/10/2026) — đối chiếu hướng dẫn ↔
    #: thực tế: phòng quầy hướng dẫn, có đúng không, thứ tự trên phiếu hướng dẫn
    #: và thứ tự phòng khách thật sự đi; phòng khách vừa rời nếu là nhận chéo.
    huong_dan_room_id: str | None = None
    dung_huong_dan: bool | None = None
    thu_tu_huong_dan: int | None = None
    thu_tu_thuc_te: int | None = None
    nhan_cheo_tu_room_id: str | None = None
    #: Mã MỘT lần bấm Nhận tại phòng (cùng mã ở `service.room_released` của
    #: lần ấy) — để hoàn tác dựng lại đúng chỗ ở phòng cũ.
    lan_nhan_id: str | None = None


class KhachRoiPhong(PayloadSuKien):
    """`service.room_released` — khách rời hàng một phòng mà chỉ định chưa làm
    xong, CHỈ do thao tác thật của người bấm (Tuyền 07/10/2026 — không có nút
    Nhả, không tự nhả). `ly_do`: NHAN_CHEO (phòng khác bấm Nhận) · BO_DICH_VU
    (quầy bỏ dịch vụ). Bấm Xong đóng đúng chỉ định ấy — mốc là `service.completed`.
    `trang_thai_truoc` = 'cho' / 'lam': khách đang làm thì lần làm GIỮ mở
    (`attempt_id`), phòng tự bấm Xong / Gián đoạn."""

    visit_id: str
    service_order_id: str
    room_id: str
    ly_do: str
    trang_thai_truoc: str
    sang_room_id: str | None = None
    attempt_id: str | None = None
    routing_revision: int | None = None
    huong_dan_room_id: str | None = None
    #: Mã MỘT lần bấm Nhận (cùng mã ở `service.routed` của lần ấy) — hoàn tác
    #: Nhận biết chỗ nào ở phòng cũ do chính lần ấy đóng để dựng lại.
    lan_nhan_id: str | None = None


class NhanVaoPhongDaHoanTac(PayloadSuKien):
    """`service.room_receive_undone` — hoàn tác Nhận: chỉ định về "Sắp đến"
    (không như huỷ xếp phòng — không đẻ việc cho trưởng ca). Lần Nhận ấy là
    NHẬN CHÉO (chỉ định đang chờ ở phòng khác) → chỉ định về lại đúng hàng phòng
    cũ (`tra_ve_room_id`), giờ vào hàng cũ — không về "Sắp đến"."""

    visit_id: str
    service_order_id: str
    room_id: str
    hoan_tac_event_id: str | None = None
    routing_revision: int
    tra_ve_room_id: str | None = None


class NhaPhongDaHoanTac(PayloadSuKien):
    """`service.room_release_undone` — hoàn tác lần Nhận chéo dựng lại chỗ của
    khách ở phòng cũ (chỗ ấy đóng vì phòng khác Nhận). `trang_thai` = trạng thái
    chỗ chờ được dựng lại ('waiting' / 'serving'); không dựng lại được nguyên
    trạng (khách đang được làm ở chỗ khác) thì 'waiting' kèm `ghi_chu`."""

    visit_id: str
    service_order_id: str
    room_id: str
    trang_thai: str
    hoan_tac_event_id: str | None = None
    routing_revision: int | None = None
    ghi_chu: str | None = None
    #: Lần làm ở phòng cũ còn mở (khách đang LÀM lúc bị nhận chéo) — chuông
    #: nhận chéo của lần ấy tự đóng.
    attempt_id: str | None = None
    #: Lựa chọn bác sĩ ở phòng cũ được dựng lại (đổi phòng đã xoá nó).
    bac_si_id: str | None = None


class HuongDanPhong(PayloadSuKien):
    """`service.room_guided` — đặt / đổi / bỏ PHÒNG HƯỚNG DẪN của chỉ định
    (`phong_du_kien_id`). Mỗi lần đổi một sự kiện — người đặt sau không xoá dấu
    người đặt trước. `room_id` None = bỏ chọn."""

    visit_id: str
    service_order_id: str
    room_id: str | None = None
    tu_room_id: str | None = None
    nguon: str | None = None


class DichVuDaChuyenPhong(PayloadSuKien):
    """`service.room_transferred` — dịch vụ ĐANG LÀM, trưởng ca chuyển sang
    phòng khác (Tuyền 29/09/2026). Lần làm cũ dừng (có lý do), chỉ định về chờ
    làm ở phòng mới. `ly_do` là chữ trưởng ca gõ — bắt buộc."""

    visit_id: str
    service_order_id: str
    from_room_id: str | None = None
    room_id: str
    attempt_id: str | None = None
    attempt_no: int | None = None
    routing_revision: int
    execution_revision: int
    ly_do: str
    nguon: str = "truong_ca"


class DaChonBacSiLam(PayloadSuKien):
    """`service.doctor_chosen` — chọn / đổi / bỏ BÁC SĨ làm trong phòng nhiều
    bác sĩ (Tuyền chốt 30/09/2026: "phòng siêu âm 2 máy … thêm cả lựa chọn các
    bác sĩ ở ngày đó"). Chỉ là lựa chọn — không khoá ai bắt đầu làm.

    `bac_si_id` None = bỏ chọn ("bác sĩ nào rảnh cũng được"). `tu_dong` = phòng
    chỉ có một bác sĩ trực nên máy tự gán. `du_kien` = phòng còn là phòng dự
    kiến (khách chưa chốt), chưa xếp chính thức."""

    visit_id: str
    service_order_id: str
    room_id: str
    bac_si_id: str | None = None
    tu_bac_si_id: str | None = None
    lan: int | None = None
    tu_dong: bool = False
    du_kien: bool = False
    nguon: str | None = None


class XepPhongDaHuy(PayloadSuKien):
    """`service.routing_invalidated` — phòng cũ không dùng được nữa.

    Huỷ xếp phòng KHÔNG tự chọn phòng khác (ChatGPT tin 112): đó là một quyết
    định của người, và phải có người nhận. Sự kiện này mở việc
    `OPS-ROUTING-REASSIGN`, chứ không âm thầm đẩy khách sang phòng kế bên.
    """

    visit_id: str
    service_order_id: str
    from_room_id: str | None = None
    routing_revision: int
    ly_do: str


class DichVuSanSangLamLai(PayloadSuKien):
    """`service.retry_prepared` — người quyết định làm lại sau khi dừng."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    execution_revision: int


class KhachDaChuyenPhong(PayloadSuKien):
    """`service.patient_moved` — khách đang làm dịch vụ này ở một phòng thì
    phòng khác bấm Bắt đầu và chọn "chuyển sang đây" (V4, Tuyền 30/09/2026 —
    làm không theo thứ tự). Đối tượng là chỉ định BỊ DỪNG: lần làm của nó đóng
    với lý do PATIENT_MOVED, chỉ định về chờ làm, khách còn chờ ở hàng phòng
    cũ. `to_service_order_id` là chỉ định vừa bắt đầu ở phòng mới."""

    visit_id: str
    service_order_id: str
    attempt_id: str | None = None
    attempt_no: int | None = None
    from_room_id: str | None = None
    to_room_id: str | None = None
    to_service_order_id: str
    execution_revision: int


class DichVuDaHuyBatDau(PayloadSuKien):
    """`service.start_cancelled` — bấm Bắt đầu nhầm khách / nhầm dịch vụ, huỷ
    ngay khi chưa điền gì (V4, 30/09/2026). Lần làm đóng với lý do
    STARTED_IN_ERROR (không xoá — vẫn đọc được là đã có lần bấm), chỉ định về
    chờ làm, khách về lại hàng chờ phòng."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    room_id: str | None = None
    execution_revision: int
    noi_lam: str | None = None
    #: Lần làm đã chốt hộ lựa chọn của khách → hoàn tác trả lựa chọn về giá trị
    #: này (vd "PENDING"). None = không trả (không chốt hộ, hoặc quầy đã chốt
    #: lại lượt sau đó — lựa chọn người sau giữ nguyên).
    tra_lua_chon_ve: str | None = None


# ── cong_no ─────────────────────────────────────────────────────────────────


class CongNoDaGhi(PayloadSuKien):
    """`cong_no.ghi` — khách về khi còn nợ, quầy ghi nợ kèm lý do (01/10/2026).
    Ghi lại khi nợ đổi = cùng `cong_no_id`, số tiền mới."""

    visit_id: str
    cong_no_id: str
    so_tien: int
    so_khoan: int
    ly_do: str


class CongNoDaHuy(PayloadSuKien):
    """`cong_no.huy` — huỷ lần ghi nợ bấm nhầm (chỉ khi khách chưa check-out)."""

    visit_id: str
    cong_no_id: str
    so_tien: int
    ly_do: str


class CongNoDaThu(PayloadSuKien):
    """`cong_no.da_thu` — lượt có khoản ghi nợ nay đã hết nợ (thu ở quầy)."""

    visit_id: str
    cong_no_id: str
    so_tien: int


# ── HOÀN TÁC (Tuyền 01/10/2026: "không được để bất kể cái gì khoá hẳn") ──────
# Mỗi hoàn tác là một SỰ THẬT riêng: sổ không xoá dòng cũ, chỉ ghi thêm "đã
# rút lại". `ly_do` là chữ vận hành người bấm gõ (bắt buộc khi máy chủ hỏi xác
# nhận) — hiện ở lịch sử Hành trình khách. `mo_lai_kham_xong` = lượt đang "khám
# xong hẳn" thì mở lại (quầy thu / nhà thuốc thôi coi là khám xong).


class PhienKhamMoLai(PayloadSuKien):
    """`consultation.reopened` — hoàn tác "Khám xong" / "Xong tư vấn": phiên
    khám về lại đang khám, sửa đơn thuốc / chỉ định rồi bấm khám xong lại."""

    visit_id: str
    consultation_id: str
    loai: str
    ket_qua_cu: str | None = None
    mo_lai_kham_xong: bool = False
    ly_do: str | None = None


class ChiDinhDaHuy(PayloadSuKien):
    """`service_order.cancelled` — bỏ chỉ định (chỉ định sai chỗ). Chưa thu thì
    hoá đơn quầy tự bớt; ĐÃ thu thì khoản ấy thành tiền thừa ở quầy thu."""

    visit_id: str
    service_order_id: str
    service_code: str
    service_name: str
    da_thu_tien: bool = False
    tien_thua: int | None = None
    ly_do: str | None = None


class ChiDinhDatLai(PayloadSuKien):
    """`service_order.restored` — HOÀN TÁC một lần bỏ chỉ định (Khối 2,
    06/10/2026): chỉ định quay lại "chưa xếp phòng", khoản đã thu (nếu có) thôi
    là tiền thừa. Thường do bác sĩ chính bấm ở thông báo "chỉ định bị bỏ"."""

    visit_id: str
    service_order_id: str
    service_code: str
    service_name: str
    so_sua_id: str
    ly_do: str | None = None


class DichVuHoanTacXong(PayloadSuKien):
    """`service.completion_undone` — hoàn tác "Xong" của một dịch vụ: lần làm
    về lại đang làm, khách về lại phòng (kết quả đã gõ giữ nguyên)."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    execution_revision: int
    mo_lai_kham_xong: bool = False
    ly_do: str | None = None
    noi_lam: str | None = None


class KetQuaThuHoiDuyet(PayloadSuKien):
    """`result.approval_revoked` — thu hồi lần bác sĩ duyệt kết quả: chỉ định
    về "chờ bác sĩ duyệt" (đánh giá, tệp, phiếu giữ nguyên)."""

    visit_id: str
    service_order_id: str
    tep_da_gui: int = 0
    ly_do: str | None = None


class LuotMoLai(PayloadSuKien):
    """`visit.reopened` — hoàn tác check-out / "về giữa chừng": lượt mở lại,
    khách về lại các hàng chờ còn dở."""

    visit_id: str
    tu_ve_giua_chung: bool = False
    ly_do: str | None = None


DANH_MUC: dict[str, SuKien] = {
    su_kien.ten: su_kien
    for su_kien in (
        SuKien(
            ten="service_order.required_changed",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhDoiBatBuoc,
            nhan="Đổi dịch vụ bắt buộc",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="service_order.desk_added",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=LamThemDaThem,
            nhan="Làm thêm tại quầy",
            # Hành trình nghe để xếp phòng qua CỬA LÀM như khách vừa chốt ở
            # quầy thu (dây H4, ``thu_truoc_khi_lam``).
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="service_order.desk_removed",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=LamThemDaBo,
            nhan="Bỏ làm thêm tại quầy",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="visit.supply_changed",
            version=1,
            aggregate_type="visit",
            source_module="vat_tu",
            payload=VatTuDaDoi,
            nhan="Bán thêm vật tư",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="visit.exam_service_changed",
            version=1,
            aggregate_type="visit",
            source_module="phi_kham",
            payload=DichVuKhamDaDoi,
            nhan="Chọn dịch vụ khám",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="service_order.placed",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhDaDat,
            nhan="Đã chỉ định dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=True,
            theo_thu_tu=True,
        ),
        # Quyền đổi là chuyện phải kể lại được: ai cho ai quyền gì, lúc nào.
        # Không công khai — AI hay đối tác không có việc gì phải nghe.
        SuKien(
            ten="visit.checked_in",
            version=1,
            aggregate_type="visit",
            source_module="reception",
            payload=KhachDaToi,
            nhan="Khách đã tới (check-in)",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="visit.routed",
            version=1,
            aggregate_type="visit",
            source_module="hanh_trinh",
            payload=DaXepDuongDi,
            nhan="Xếp khách vào hàng",
            consumers=[DONG_THOI_GIAN_LUOT, DIEU_TRI_SINH_CHI_DINH],
        ),
        SuKien(
            ten="visit.exam_completed",
            version=1,
            aggregate_type="visit",
            source_module="vong_doc",
            payload=LuotDaKhamXong,
            nhan="Khám xong hẳn (hết việc chờ)",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="consultation.started",
            version=1,
            aggregate_type="consultation",
            source_module="consultation",
            payload=PhienKhamBatDau,
            nhan="Bắt đầu khám",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="consultation.resumed",
            version=1,
            aggregate_type="consultation",
            source_module="consultation",
            payload=PhienKhamTiepTuc,
            nhan="Khách quay lại — tiếp tục khám",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="consultation.handed_over",
            version=1,
            aggregate_type="consultation",
            source_module="consultation",
            payload=TuVanXong,
            nhan="Tư vấn xong — chuyển bác sĩ chính",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="consultation.completed",
            version=1,
            aggregate_type="consultation",
            source_module="consultation",
            payload=KhamXong,
            nhan="Khám xong",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            # Phát ĐÚNG MỘT LẦN cho một lượt: bấm hai lần, hay người khác bấm
            # sau, đều không sinh sự kiện thứ hai.
            ten="vitals.started",
            version=1,
            aggregate_type="visit",
            source_module="vitals",
            payload=SinhHieuBatDau,
            nhan="Bắt đầu đo sinh hiệu",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="vitals.recorded",
            version=1,
            aggregate_type="visit",
            source_module="vitals",
            payload=SinhHieuDaDo,
            nhan="Đã đo sinh hiệu",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="service.started",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuDaBatDau,
            nhan="Bắt đầu làm dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="medicine.counter_changed",
            version=1,
            aggregate_type="visit",
            source_module="pharmacy",
            payload=ThuocQuayDaChinh,
            nhan="Quầy thuốc chỉnh đơn bán",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="medicine.declined",
            version=1,
            aggregate_type="visit",
            source_module="payment",
            payload=ThuocBiBo,
            nhan="Khách bỏ / lấy bớt thuốc (bản thanh toán cuối)",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="prescription.saved",
            version=1,
            aggregate_type="visit",
            source_module="consultation",
            payload=DonThuocDaLuu,
            nhan="Bác sĩ kê / sửa đơn thuốc",
            # Kê đơn từng KHÔNG phát sự kiện nào (bộ mô phỏng ngày khám,
            # 24/09/2026): kho thuốc, dòng thời gian không có dây để nghe.
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="service_selection.confirmed",
            version=1,
            aggregate_type="visit",
            source_module="service_selection",
            payload=KhachDaChonDichVu,
            nhan="Khách chốt làm / không làm chỉ định",
            # Không cần giao theo thứ tự: bên nhận chạy lại vòng đọc từ trạng
            # thái hiện tại (chạy lại bao lần cũng ra một kết quả). Khối Đối tác
            # nghe để nhận việc đối tác TỰ THU (27/09/2026): khách chốt làm là
            # đủ, không chờ phòng khám thu tiền. Hành trình nghe để tự xếp phòng
            # khi hoá đơn 0đ — không có lần thu nào để chờ (V2, 30/09/2026).
            consumers=[DONG_THOI_GIAN_LUOT, VONG_DOC, DOI_TAC_NHAN_VIEC, HANH_TRINH],
        ),
        SuKien(
            ten="visit.defer_payment_set",
            version=1,
            aggregate_type="visit",
            source_module="service_selection",
            payload=LamTruocThuSauDaBat,
            nhan="Bật Làm trước – thu sau",
            # Hành trình xếp phòng ngay (chỉ định đã chốt mà chưa thu, trước đó
            # bị dây thu trước giữ lại); Đối tác nhận việc tự lấy mẫu.
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH, DOI_TAC_NHAN_VIEC],
            is_public=False,
        ),
        SuKien(
            ten="visit.defer_payment_cleared",
            version=1,
            aggregate_type="visit",
            source_module="service_selection",
            payload=LamTruocThuSauDaBo,
            nhan="Bỏ Làm trước – thu sau",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="service.completed",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuDaXong,
            nhan="Đã làm xong dịch vụ",
            consumers=[
                DONG_THOI_GIAN_LUOT,
                HANH_TRINH,
                VONG_DOC,
                DOI_TAC_NHAN_VIEC,
                CHUONG_NHAN_CHEO,
            ],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.not_performed",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuKhongLam,
            nhan="Không làm dịch vụ",
            # Hai bên nghe, độc lập nhau: một bên vẽ hành trình, một bên mở việc
            # đối soát tiền. Bên này hỏng không chặn bên kia.
            consumers=[DONG_THOI_GIAN_LUOT, TRACH_NHIEM_DICH_VU, VONG_DOC],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.interrupted",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuGianDoan,
            nhan="Dừng giữa chừng",
            consumers=[DONG_THOI_GIAN_LUOT, TRACH_NHIEM_DICH_VU, CHUONG_NHAN_CHEO],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.retry_prepared",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuSanSangLamLai,
            nhan="Chuẩn bị làm lại",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            # V4 (30/09/2026): không mở việc trách nhiệm — chỉ định bị dừng đã
            # về chờ làm và khách vẫn nằm trong hàng phòng cũ, không rơi đâu.
            ten="service.patient_moved",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=KhachDaChuyenPhong,
            nhan="Khách chuyển sang phòng khác khi đang làm",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.start_cancelled",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuDaHuyBatDau,
            nhan="Huỷ bắt đầu nhầm",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG_NHAN_CHEO],
            theo_thu_tu=True,
        ),
        # ── Hoàn tác (01/10/2026) — chỉ lên dòng thời gian: mỗi lệnh hoàn tác
        # tự đưa mọi bảng về đúng chỗ trong CHÍNH giao dịch của nó, các màn tự
        # tải lại qua NOTIFY của bảng (không cần bên nghe nào làm thêm việc).
        SuKien(
            ten="service.completion_undone",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuHoanTacXong,
            nhan="Hoàn tác “Xong” dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="result.approval_revoked",
            version=1,
            aggregate_type="service_order",
            source_module="result",
            payload=KetQuaThuHoiDuyet,
            nhan="Thu hồi duyệt kết quả",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service_order.cancelled",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhDaHuy,
            nhan="Bỏ chỉ định",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="service_order.restored",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhDatLai,
            nhan="Hoàn tác bỏ chỉ định",
            # HÀNH TRÌNH: chỉ định vừa quay lại đi đúng cửa làm như lúc khách
            # vừa chốt (đã thu → xếp phòng ngay).
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="consultation.reopened",
            version=1,
            aggregate_type="consultation",
            source_module="consultation",
            payload=PhienKhamMoLai,
            nhan="Hoàn tác khám xong — mở lại khám",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="visit.reopened",
            version=1,
            aggregate_type="visit",
            source_module="reception",
            payload=LuotMoLai,
            nhan="Hoàn tác check-out — mở lại lượt",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            # Đối tượng là PHIẾU, không phải chỉ định. Hai module cùng đánh số
            # phiên bản trên một đối tượng thì số đụng nhau — Postgres chặn, và
            # chặn đúng: "phiên bản thứ 3 của chỉ định này" phải có đúng một
            # nghĩa, không phải hai module hiểu hai kiểu.
            ten="result_form.completed",
            version=1,
            aggregate_type="form_instance",
            source_module="result",
            payload=PhieuDaHoanTat,
            nhan="Đã hoàn tất phiếu kết quả",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=True,
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.routed",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=DaXepPhong,
            nhan="Đã xếp phòng",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=True,
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.room_transferred",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=DichVuDaChuyenPhong,
            nhan="Trưởng ca chuyển phòng khi đang làm",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.doctor_chosen",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=DaChonBacSiLam,
            nhan="Chọn bác sĩ làm trong phòng",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        # Nhận khách tại phòng (07/10/2026) — Nhận = `service.routed` nguồn
        # 'tai_phong'; ba sự kiện dưới là rời phòng, hoàn tác Nhận, hướng dẫn.
        SuKien(
            ten="service.room_released",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=KhachRoiPhong,
            nhan="Khách rời phòng (nhả)",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG_NHAN_CHEO],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.room_receive_undone",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=NhanVaoPhongDaHoanTac,
            nhan="Hoàn tác nhận khách vào phòng",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.room_release_undone",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=NhaPhongDaHoanTac,
            nhan="Hoàn tác khách rời phòng (về lại phòng cũ)",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG_NHAN_CHEO],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.room_guided",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=HuongDanPhong,
            nhan="Hướng dẫn phòng làm dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service_order.carried_over",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhMangSang,
            nhan="Mang chỉ định từ lượt trước sang",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        # ── nhóm 3: kết quả ──
        SuKien(
            ten="result_file.uploaded",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaVe,
            nhan="Tệp kết quả đã về",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG, VONG_DOC],
        ),
        SuKien(
            ten="result_file.confirmed",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaXacNhan,
            nhan="Đã xác nhận tệp kết quả",
            # Chuông (23/09 khuya): tệp đối tác HỢP LỆ = kết quả chính thức về
            # → báo bác sĩ chính + CSKH. Trước đó chỉ có chuông lúc TẢI LÊN.
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG, VONG_DOC],
        ),
        SuKien(
            ten="result_file.revoked",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaThuHoi,
            nhan="Đã thu hồi tệp kết quả",
            # Vòng đọc nghe để rút chỗ chờ "có kết quả" khi tệp duy nhất bị gỡ.
            consumers=[DONG_THOI_GIAN_LUOT, VONG_DOC],
        ),
        # V9 (30/09/2026): xoá mềm / khôi phục. Vòng đọc nghe như thu hồi — tệp
        # duy nhất bị xoá thì rút chỗ chờ "có kết quả"; khôi phục thì mở lại.
        SuKien(
            ten="result_file.deleted",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaXoa,
            nhan="Đã xoá tệp kết quả",
            consumers=[DONG_THOI_GIAN_LUOT, VONG_DOC],
        ),
        SuKien(
            ten="result_file.restored",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaKhoiPhuc,
            nhan="Đã khôi phục tệp kết quả",
            consumers=[DONG_THOI_GIAN_LUOT, VONG_DOC],
        ),
        SuKien(
            ten="result_file.viewed",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=TepKetQuaDaXem,
            nhan="Bác sĩ đã xem kết quả",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="result_file.sent_to_patient",
            version=1,
            aggregate_type="tep_ket_qua",
            source_module="result_file",
            payload=KetQuaDaGuiKhach,
            nhan="Đã gửi kết quả cho khách",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="lab_result.arrived",
            version=1,
            aggregate_type="lab_result",
            source_module="lab",
            payload=KetQuaXetNghiemVe,
            nhan="Kết quả xét nghiệm đã về",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG],
        ),
        SuKien(
            ten="result.viewed",
            version=1,
            aggregate_type="service_order",
            source_module="result",
            payload=PhieuKetQuaDaXem,
            nhan="Bác sĩ đã xem phiếu kết quả",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="result.reviewed",
            version=1,
            aggregate_type="service_order",
            source_module="result",
            payload=KetQuaDaDuyet,
            nhan="Bác sĩ đã duyệt kết quả",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        # ── nhóm 3: lịch hẹn, rời phòng khám, tiền, CSKH ──
        SuKien(
            ten="appointment.booked",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=LichDaDat,
            nhan="Đã đặt lịch",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="appointment.rescheduled",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=LichDaDoi,
            nhan="Đã đổi lịch",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="appointment.cancelled",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=LichDaHuy,
            nhan="Đã huỷ lịch",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="appointment.service_switched",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=LichDaDoiDichVu,
            nhan="Đổi dịch vụ khám",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="appointment.no_show",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=KhachKhongDen,
            nhan="Khách không đến",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="appointment.confirmed_by_call",
            version=1,
            aggregate_type="appointment",
            source_module="booking",
            payload=CskhDaGoiXacNhan,
            nhan="CSKH đã gọi xác nhận lịch",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="visit.checked_out",
            version=1,
            aggregate_type="visit",
            source_module="reception",
            payload=KhachDaVe,
            nhan="Khách đã về (check-out)",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="visit.left_early",
            version=1,
            aggregate_type="visit",
            source_module="reception",
            payload=KhachBoVeGiuaChung,
            nhan="Khách bỏ về giữa chừng",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
        ),
        SuKien(
            ten="payment.refunded",
            version=1,
            aggregate_type="payment_refund",
            source_module="payment",
            payload=DaHoanTien,
            nhan="Đã hoàn tiền",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="followup.scheduled",
            version=1,
            aggregate_type="visit",
            source_module="consultation",
            payload=DaHenTaiKham,
            nhan="Bác sĩ hẹn tái khám",
            consumers=[DONG_THOI_GIAN_LUOT],
        ),
        SuKien(
            ten="partner.order_received",
            version=1,
            aggregate_type="service_order",
            source_module="doi_tac",
            payload=DoiTacNhanViec,
            nhan="Đối tác đã nhận việc",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG],
            is_public=True,
        ),
        SuKien(
            ten="partner.payment_recorded",
            version=1,
            aggregate_type="service_order",
            source_module="doi_tac",
            payload=DoiTacDaThuTien,
            nhan="Đã thu hộ cho đối tác",
            consumers=[DONG_THOI_GIAN_LUOT],
            # Tiền là chuyện nội bộ (như payment.*): AI/Zalo không nghe.
            is_public=False,
        ),
        SuKien(
            ten="partner.payment_voided",
            version=1,
            aggregate_type="service_order",
            source_module="doi_tac",
            payload=DoiTacHuyThuTien,
            nhan="Huỷ ghi nhận đã thu hộ cho đối tác",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="partner.sample_collected",
            version=1,
            aggregate_type="service_order",
            source_module="doi_tac",
            payload=DoiTacDaLayMau,
            nhan="Đối tác đã lấy mẫu",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH, VONG_DOC],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="partner.sample_received",
            version=1,
            aggregate_type="service_order",
            source_module="doi_tac",
            payload=DoiTacDaNhanMau,
            nhan="Đối tác đã nhận mẫu — việc đối tác xong",
            consumers=[DONG_THOI_GIAN_LUOT, VONG_DOC],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="patient.contacted",
            version=1,
            aggregate_type="clinic_patient",
            source_module="cskh",
            payload=CskhDaLienHe,
            nhan="CSKH đã liên hệ khách",
            is_public=False,
        ),
        SuKien(
            ten="payment.medicine_collected",
            version=1,
            aggregate_type="payment_cycle",
            source_module="payment",
            payload=TienThuocDaThu,
            nhan="Đã thu tiền thuốc",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH, CONG_NO],
            is_public=False,
        ),
        SuKien(
            ten="payment.method_changed",
            version=1,
            aggregate_type="payment_cycle",
            source_module="payment",
            payload=HinhThucThuDaDoi,
            nhan="Đổi hình thức thu",
            consumers=[DONG_THOI_GIAN_LUOT],
            # Tiền là chuyện nội bộ (như payment.*): AI/Zalo không nghe.
            is_public=False,
        ),
        SuKien(
            ten="payment.collection_undone",
            version=1,
            aggregate_type="payment_cycle",
            source_module="payment",
            payload=LanThuDaHoanTac,
            nhan="Hoàn tác lần thu",
            consumers=[DONG_THOI_GIAN_LUOT],
            # Tiền là chuyện nội bộ (như payment.*): AI/Zalo không nghe.
            is_public=False,
        ),
        SuKien(
            ten="medicine.dispensed",
            version=1,
            aggregate_type="prescription",
            source_module="pharmacy",
            payload=ThuocDaGiao,
            nhan="Đã giao thuốc",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            # Tiền là chuyện nội bộ: AI/Zalo/đối tác không nghe sự kiện này.
            ten="payment.service_collected",
            version=1,
            aggregate_type="payment_cycle",
            source_module="payment",
            payload=TienDichVuDaThu,
            nhan="Đã thu tiền dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH, DOI_TAC_NHAN_VIEC, CONG_NO],
            is_public=False,
        ),
        SuKien(
            ten="cong_no.ghi",
            version=1,
            aggregate_type="cong_no",
            source_module="cong_no",
            payload=CongNoDaGhi,
            nhan="Ghi nợ khi khách về",
            consumers=[DONG_THOI_GIAN_LUOT],
            # Tiền là chuyện nội bộ (như payment.*).
            is_public=False,
        ),
        SuKien(
            ten="cong_no.huy",
            version=1,
            aggregate_type="cong_no",
            source_module="cong_no",
            payload=CongNoDaHuy,
            nhan="Huỷ ghi nợ",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="cong_no.da_thu",
            version=1,
            aggregate_type="cong_no",
            source_module="cong_no",
            payload=CongNoDaThu,
            nhan="Đã thu hết nợ",
            consumers=[DONG_THOI_GIAN_LUOT],
            is_public=False,
        ),
        SuKien(
            ten="service.routing_invalidated",
            version=1,
            aggregate_type="service_order",
            source_module="service_routing",
            payload=XepPhongDaHuy,
            nhan="Đã huỷ xếp phòng",
            consumers=[DONG_THOI_GIAN_LUOT, TRACH_NHIEM_DICH_VU],
            is_public=True,
            theo_thu_tu=True,
        ),
        SuKien(
            # Đối tượng là KẾT QUẢ, một vòng đời riêng của phiếu sinh ra nó:
            # ready → corrected → (sau này) reviewed, released. Tách khỏi
            # `form_instance` để hai chuỗi số không giẫm chân nhau.
            ten="result.ready",
            version=1,
            aggregate_type="ket_qua",
            source_module="result",
            payload=KetQuaSanSang,
            nhan="Đã có kết quả",
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG, VONG_DOC],
            is_public=True,
            theo_thu_tu=True,
        ),
        SuKien(
            ten="result.corrected",
            version=1,
            aggregate_type="ket_qua",
            source_module="result",
            payload=KetQuaDaSua,
            nhan="Đã sửa kết quả",
            # 28/09/2026: kết quả SỬA LẠI cũng phải réo bác sĩ chính và chạy
            # lại vòng đọc — trước đây chỉ vào dòng thời gian, bác sĩ không biết.
            consumers=[DONG_THOI_GIAN_LUOT, CHUONG, VONG_DOC],
            is_public=True,
            theo_thu_tu=True,
        ),
        SuKien(
            ten="capability.granted",
            version=1,
            aggregate_type="staff",
            source_module="permission",
            payload=KhoiQuyenDaCap,
            nhan="Đã cấp khối quyền",
            is_public=False,
        ),
        SuKien(
            ten="capability.revoked",
            version=1,
            aggregate_type="staff",
            source_module="permission",
            payload=KhoiQuyenDaThu,
            nhan="Đã thu khối quyền",
            is_public=False,
        ),
        SuKien(
            ten="clinical_shift.exception_opened",
            version=1,
            aggregate_type="clinical_shift_exception",
            source_module="permission",
            payload=NgoaiLeCaTruc,
            nhan="Đã mở ngoại lệ ca trực lâm sàng",
            is_public=False,
        ),
        SuKien(
            ten="clinical_shift.exception_cancelled",
            version=1,
            aggregate_type="clinical_shift_exception",
            source_module="permission",
            payload=NgoaiLeCaTruc,
            nhan="Đã huỷ ngoại lệ ca trực lâm sàng",
            is_public=False,
        ),
    )
}


# ── Luật đặt tên ────────────────────────────────────────────────────────────
# `danh_từ.việc_đã_xảy_ra`, tiếng Anh, chữ thường. Cấm tên kiểu mệnh lệnh
# (`service.route_needed`) vì đó là VIỆC CẦN LÀM, phải thành work_item chứ không
# phải sự kiện; và cấm tên vô nghĩa (`visit.updated`).
DONG_TU_CAM: frozenset[str] = frozenset(
    {"needed", "required", "todo", "request", "updated", "changed", "refresh"}
)


def tra(ten: str) -> SuKien:
    """Tra một sự kiện; chưa khai thì hỏng ngay tại chỗ phát, không phát bừa."""
    try:
        return DANH_MUC[ten]
    except KeyError:
        raise ValueError(
            f"Sự kiện '{ten}' chưa khai trong danh mục "
            f"(src/clinicai/events/catalogue.py). Khai trước, phát sau."
        ) from None


def moi_consumer() -> frozenset[str]:
    """Tập bên nhận đang được khai ở bất kỳ sự kiện nào."""
    return frozenset(
        consumer for su_kien in DANH_MUC.values() for consumer in su_kien.consumers
    )


__all__ = [
    "CONG_NO",
    "DIEU_TRI_SINH_CHI_DINH",
    "CongNoDaGhi",
    "CongNoDaHuy",
    "CongNoDaThu",
    "DANH_MUC",
    "HANH_TRINH",
    "ChiDinhDaHuy",
    "ChiDinhDatLai",
    "DichVuHoanTacXong",
    "KetQuaThuHoiDuyet",
    "LuotMoLai",
    "PhienKhamMoLai",
    "ChiDinhMangSang",
    "DaXepDuongDi",
    "DaChonBacSiLam",
    "DaXepPhong",
    "DichVuDaChuyenPhong",
    "HuongDanPhong",
    "KhachRoiPhong",
    "NhaPhongDaHoanTac",
    "NhanVaoPhongDaHoanTac",
    "PhienKhamTiepTuc",
    "TienDichVuDaThu",
    "TienThuocDaThu",
    "CHUONG",
    "CHUONG_NHAN_CHEO",
    "TepKetQuaDaVe",
    "TepKetQuaDaXacNhan",
    "TepKetQuaDaXem",
    "KetQuaDaGuiKhach",
    "KetQuaDaDuyet",
    "PhieuKetQuaDaXem",
    "KetQuaXetNghiemVe",
    "LichDaDat",
    "LichDaDoi",
    "LichDaHuy",
    "KhachKhongDen",
    "LichDaDoiDichVu",
    "CskhDaGoiXacNhan",
    "KhachDaVe",
    "LamTruocThuSauDaBat",
    "LamTruocThuSauDaBo",
    "KhachBoVeGiuaChung",
    "DaHoanTien",
    "HinhThucThuDaDoi",
    "DaHenTaiKham",
    "CskhDaLienHe",
    "DoiTacDaLayMau",
    "DoiTacDaNhanMau",
    "ThuocDaGiao",
    "KhamXong",
    "PhienKhamBatDau",
    "TuVanXong",
    "KetQuaDaSua",
    "SinhHieuBatDau",
    "XepPhongDaHuy",
    "KetQuaSanSang",
    "DONG_THOI_GIAN_LUOT",
    "TRACH_NHIEM_DICH_VU",
    "DONG_TU_CAM",
    "LuotDaKhamXong",
    "TepKetQuaDaThuHoi",
    "VONG_DOC",
    "ChiDinhDaDat",
    "KhachDaToi",
    "SinhHieuDaDo",
    "DichVuDaBatDau",
    "DichVuDaXong",
    "DichVuGianDoan",
    "DichVuKhongLam",
    "DichVuSanSangLamLai",
    "KhachDaChuyenPhong",
    "DichVuDaHuyBatDau",
    "KhoiQuyenDaCap",
    "PhieuDaHoanTat",
    "KhoiQuyenDaThu",
    "NgoaiLeCaTruc",
    "PayloadSuKien",
    "SuKien",
    "moi_consumer",
    "tra",
]
