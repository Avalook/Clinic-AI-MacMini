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


# ── execution (thực hiện dịch vụ) ───────────────────────────────────────────


class DichVuDaBatDau(PayloadSuKien):
    """`service.started` — một LẦN LÀM bắt đầu (không phải chỉ định bắt đầu)."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    room_id: str | None = None
    execution_revision: int


class DichVuDaXong(PayloadSuKien):
    """`service.completed` — lần làm ấy xong. KHÁC `result.ready`."""

    visit_id: str
    service_order_id: str
    attempt_id: str
    attempt_no: int
    execution_revision: int


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


DANH_MUC: dict[str, SuKien] = {
    su_kien.ten: su_kien
    for su_kien in (
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
            ten="service.completed",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuDaXong,
            nhan="Đã làm xong dịch vụ",
            consumers=[DONG_THOI_GIAN_LUOT],
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
            consumers=[DONG_THOI_GIAN_LUOT, TRACH_NHIEM_DICH_VU],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="service.interrupted",
            version=1,
            aggregate_type="service_order",
            source_module="execution",
            payload=DichVuGianDoan,
            nhan="Dừng giữa chừng",
            consumers=[DONG_THOI_GIAN_LUOT, TRACH_NHIEM_DICH_VU],
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
            ten="service_order.carried_over",
            version=1,
            aggregate_type="service_order",
            source_module="service_order",
            payload=ChiDinhMangSang,
            nhan="Mang chỉ định từ lượt trước sang",
            consumers=[DONG_THOI_GIAN_LUOT],
            theo_thu_tu=True,
        ),
        SuKien(
            ten="payment.medicine_collected",
            version=1,
            aggregate_type="payment_cycle",
            source_module="payment",
            payload=TienThuocDaThu,
            nhan="Đã thu tiền thuốc",
            consumers=[DONG_THOI_GIAN_LUOT],
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
            consumers=[DONG_THOI_GIAN_LUOT, HANH_TRINH],
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
            consumers=[DONG_THOI_GIAN_LUOT],
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
            consumers=[DONG_THOI_GIAN_LUOT],
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
    "DANH_MUC",
    "HANH_TRINH",
    "ChiDinhMangSang",
    "DaXepDuongDi",
    "DaXepPhong",
    "TienDichVuDaThu",
    "TienThuocDaThu",
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
    "ChiDinhDaDat",
    "KhachDaToi",
    "SinhHieuDaDo",
    "DichVuDaBatDau",
    "DichVuDaXong",
    "DichVuGianDoan",
    "DichVuKhongLam",
    "DichVuSanSangLamLai",
    "KhoiQuyenDaCap",
    "PhieuDaHoanTat",
    "KhoiQuyenDaThu",
    "PayloadSuKien",
    "SuKien",
    "moi_consumer",
    "tra",
]
