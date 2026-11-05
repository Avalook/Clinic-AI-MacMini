"""Trạng thái một việc xét nghiệm đối tác — MỘT hàm (kế hoạch mục 4.6, luật 3).

Trạng thái không lưu thành cột. Mọi màn, mọi đếm, mọi lọc gọi `trang_thai_xet_nghiem()`
trên các SỰ VIỆC đã đọc từ DB (thu, mẫu, tệp, gửi, đóng). Python thuần, không I/O.
Chuỗi mã trạng thái chỉ được xuất hiện ở module này và test (test đếm canh).

Thứ tự ưu tiên (Tuyền chốt 05/11): DA_HUY > DA_GUI > DA_DONG > CO_KET_QUA >
CHO_KET_QUA > CHO_LAY_MAU > CHO_THU. "Đã gửi" thắng "Đối tác đã tự trả khách": đã
gửi khách thì lệnh đóng bị chặn ở lệnh, và nếu sự việc vẫn chồng nhau (gửi sau khi
đóng) thì mốc gửi là sự thật mạnh hơn.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from typing import Final, Literal

TrangThaiMa = Literal[
    "DA_HUY",
    "DA_GUI",
    "DA_DONG",
    "CO_KET_QUA",
    "CHO_KET_QUA",
    "CHO_LAY_MAU",
    "CHO_THU",
]

#: Chữ cho người đọc — màn chỉ hiển thị, không tự đặt chữ.
NHAN: Final[dict[str, str]] = {
    "DA_HUY": "Đã huỷ chỉ định",
    "DA_GUI": "Đã gửi kết quả",
    "DA_DONG": "Đối tác đã tự trả khách",
    "CO_KET_QUA": "Có kết quả",
    "CHO_KET_QUA": "Chờ kết quả",
    "CHO_LAY_MAU": "Chờ lấy mẫu",
    "CHO_THU": "Chờ thu",
}

#: Thứ tự trên bàn (việc cần làm trước lên đầu).
THU_TU: Final[tuple[str, ...]] = (
    "CHO_THU",
    "CHO_LAY_MAU",
    "CO_KET_QUA",
    "CHO_KET_QUA",
    "DA_GUI",
    "DA_DONG",
    "DA_HUY",
)

#: Mặc định "đã thu, chưa lấy mẫu" bao nhiêu ngày thì vàng (câu F, 05/11).
NGUONG_LAY_MAU_MAC_DINH: Final = 2


@dataclass(frozen=True)
class SuViecXN:
    """Sự việc của một việc — đọc từ DB, không suy luận gì ở đây."""

    hom_nay: date
    da_huy_chi_dinh: bool = False
    #: ngày (giờ VN) của ghi nhận thu còn hiệu lực; None = chưa có.
    ngay_thu: date | None = None
    duoc_cho_qua: bool = False
    #: có mẫu còn hiệu lực chứa việc này.
    co_mau: bool = False
    hen_tra: date | None = None
    #: có tệp còn hiệu lực (không TU_CHOI/THU_HOI/xoá).
    co_tep: bool = False
    #: tệp còn hiệu lực MỚI NHẤT đã gửi khách.
    tep_moi_nhat_da_gui: bool = False
    #: từng gửi một tệp nào đó (để biết bản mới là "bản 2 chưa gửi").
    tung_gui: bool = False
    #: lệnh "Đối tác đã tự trả khách" còn hiệu lực (chưa mở lại).
    da_dong: bool = False
    da_hoan_tien: bool = False
    nguong_lay_mau_ngay: int = NGUONG_LAY_MAU_MAC_DINH


@dataclass(frozen=True)
class TrangThaiXN:
    ma: TrangThaiMa
    nhan: str
    #: chỉ có nghĩa ở CHO_KET_QUA: hôm nay > hẹn trả.
    qua_hen: bool = False
    #: số ngày quá hẹn (0 nếu chưa quá) — > 1 là đỏ, 1 là vàng (câu F).
    so_ngay_qua_hen: int = 0
    #: CHO_LAY_MAU mà đã thu từ ≥ ngưỡng ngày.
    qua_han_lay_mau: bool = False
    co_ban_moi_chua_gui: bool = False
    da_hoan_tien: bool = False
    co_the_lay_mau: bool = False
    #: vì sao chưa lấy mẫu được (hiện khi rê chuột nút Lấy mẫu mờ).
    ly_do_khong_lay_mau: str | None = None


def _tao(ma: TrangThaiMa, sv: SuViecXN) -> TrangThaiXN:
    return TrangThaiXN(ma=ma, nhan=NHAN[ma], da_hoan_tien=sv.da_hoan_tien)


def trang_thai_xet_nghiem(sv: SuViecXN) -> TrangThaiXN:
    """Một câu hỏi — một hàm: việc này đang ở đâu."""
    if sv.da_huy_chi_dinh:
        return replace(_tao("DA_HUY", sv), ly_do_khong_lay_mau="Chỉ định đã huỷ")
    if sv.co_tep and sv.tep_moi_nhat_da_gui:
        return replace(_tao("DA_GUI", sv), ly_do_khong_lay_mau="Đã có kết quả")
    if sv.da_dong:
        # Đã đóng mà vẫn có tệp còn hiệu lực chưa gửi (đối tác gửi muộn) — giữ
        # DA_DONG nhưng bật cờ để bàn hiện "có kết quả mới" cho CSKH gửi (soát #600).
        return replace(
            _tao("DA_DONG", sv),
            co_ban_moi_chua_gui=sv.co_tep,
            ly_do_khong_lay_mau="Việc đã đóng",
        )
    if sv.co_tep:
        return replace(
            _tao("CO_KET_QUA", sv),
            co_ban_moi_chua_gui=sv.tung_gui,
            ly_do_khong_lay_mau="Đã có kết quả",
        )
    if sv.co_mau:
        tre = (sv.hom_nay - sv.hen_tra).days if sv.hen_tra is not None else 0
        return replace(
            _tao("CHO_KET_QUA", sv),
            qua_hen=tre > 0,
            so_ngay_qua_hen=max(tre, 0),
            ly_do_khong_lay_mau="Đã lấy mẫu",
        )
    if sv.ngay_thu is not None or sv.duoc_cho_qua:
        tre_lay = (sv.hom_nay - sv.ngay_thu).days if sv.ngay_thu is not None else 0
        return replace(
            _tao("CHO_LAY_MAU", sv),
            qua_han_lay_mau=tre_lay >= sv.nguong_lay_mau_ngay,
            co_the_lay_mau=True,
        )
    return replace(_tao("CHO_THU", sv), ly_do_khong_lay_mau="Chưa ghi nhận thu hộ")


def nut_cua(
    tt: TrangThaiXN,
    *,
    co_thu: bool,
    con_hoan: int,
    co_mau: bool,
    co_tep: bool,
    tep_moi_nhat_da_gui: bool,
) -> dict[str, object]:
    """Nút nào bấm được + "Hoàn tác bước trước" gọi ĐÚNG lệnh bù nào (kế hoạch 5).

    Một câu hỏi ("ai bấm được gì") — một hàm, cạnh hàm trạng thái; màn chỉ đọc cờ."""
    hoan_tac = {
        "DA_DONG": {"lenh": "mo_lai", "nhan": "Mở lại việc"},
        "DA_GUI": {"lenh": "thu_hoi", "nhan": "Thu hồi kết quả đã gửi"},
        "CO_KET_QUA": {"lenh": "thu_hoi", "nhan": "Thu hồi tệp kết quả"},
        "CHO_KET_QUA": {"lenh": "huy_mau", "nhan": "Huỷ mẫu (khoản thu giữ nguyên)"},
    }.get(tt.ma)
    if tt.ma == "CHO_LAY_MAU" and co_thu:
        hoan_tac = {"lenh": "huy_thu", "nhan": "Huỷ ghi nhận thu (ghi sai)"}
    return {
        "ghi_thu": not co_thu and tt.ma in ("CHO_THU", "CHO_LAY_MAU"),
        "huy_thu": co_thu and not co_mau,
        "hoan_tien": co_thu and con_hoan > 0,
        "con_hoan_duoc": max(con_hoan, 0),
        "cho_qua": tt.ma == "CHO_THU",
        "lay_mau": tt.co_the_lay_mau,
        "huy_mau": co_mau and not co_tep,
        "tai_ket_qua": co_mau and tt.ma not in ("DA_HUY", "DA_DONG"),
        "gui": co_tep and not tep_moi_nhat_da_gui,
        "thu_hoi": co_tep,
        "dong": tt.ma not in ("DA_HUY", "DA_GUI", "DA_DONG"),
        "mo_lai": tt.ma == "DA_DONG",
        "hoan_tac": hoan_tac,
    }
