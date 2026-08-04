"""Cắt khoảng phút khi một luật đặt lịch mới đè lên luật cũ.

VÌ SAO CÓ FILE NÀY. Trưởng ca lưu "BS Thành 18:00–18:15, 9 ca" và nhận về *"Lịch
hẹn xung đột khung giờ với appointment khác"* — vì bản cũ chỉ INSERT, nên lần lưu
thứ hai đụng ràng buộc EXCLUDE, và handler toàn cục kể một câu chuyện về lịch hẹn.
Cấu hình phòng khám trở thành thứ chỉ ghi được đúng một lần.

Phép cắt là chỗ dễ sai nhất trong cách sửa: bốn nhánh, mỗi nhánh lệch một phút là
một khoảng giờ không luật nào phủ, và khoảng hở đó không báo lỗi — nó chỉ âm thầm
rơi về số chỗ mặc định.
"""

from __future__ import annotations

import pytest

from clinicai.services.booking_override_service import plan_window_trim

H = 60  # phút mỗi giờ, để các mốc bên dưới đọc được như đồng hồ


def test_luat_cu_nam_tron_trong_khung_moi_thi_bien_mat() -> None:
    p = plan_window_trim(18 * H, 18 * H + 15, 18 * H, 19 * H)
    assert p.action == "deleted"
    assert p.keep is None


def test_khung_moi_nam_giua_thi_luat_cu_cat_doi() -> None:
    # cũ 18:00–19:00 (4 ca), mới 18:15–18:30 (9 ca)
    # ⇒ 18:00–18:15 (4)   18:15–18:30 (9, luật mới)   18:30–19:00 (4)
    p = plan_window_trim(18 * H, 19 * H, 18 * H + 15, 18 * H + 30)
    assert p.action == "split"
    assert p.keep == (18 * H, 18 * H + 15)
    assert p.keep_extra == (18 * H + 30, 19 * H)


def test_luat_cu_tho_dau_ben_trai_thi_bi_cat_ngan_lai() -> None:
    p = plan_window_trim(17 * H, 18 * H + 30, 18 * H, 19 * H)
    assert p.action == "trimmed"
    assert p.keep == (17 * H, 18 * H)


def test_luat_cu_tho_duoi_ben_phai_thi_bi_day_ve_sau() -> None:
    p = plan_window_trim(18 * H + 30, 20 * H, 18 * H, 19 * H)
    assert p.action == "trimmed"
    assert p.keep == (19 * H, 20 * H)


def test_luat_ca_ngay_bi_khung_moi_khoet_mot_lo() -> None:
    """Luật cả ngày là NULL/NULL, service quy về [0, 1440) trước khi gọi."""
    p = plan_window_trim(0, 1440, 18 * H, 18 * H + 15)
    assert p.action == "split"
    assert p.keep == (0, 18 * H)
    assert p.keep_extra == (18 * H + 15, 1440)


def test_luu_de_dung_khung_cu_la_mot_lan_cap_nhat() -> None:
    """Sửa 9 ca thành 10 ca cho cùng khung: luật cũ đi hẳn, không cắt xén."""
    p = plan_window_trim(18 * H, 18 * H + 15, 18 * H, 18 * H + 15)
    assert p.action == "deleted"


@pytest.mark.parametrize(
    "old_start,old_end,new_start,new_end",
    [
        (18 * H, 19 * H, 17 * H, 18 * H),  # cũ bắt đầu đúng lúc mới kết thúc
        (17 * H, 18 * H, 18 * H, 19 * H),  # và chiều ngược lại
    ],
)
def test_hai_khung_lien_ke_khong_dung_nhau(
    old_start: int, old_end: int, new_start: int, new_end: int
) -> None:
    """Nửa mở: 18:00–19:00 và 19:00–20:00 là hai khung rời nhau.

    Nếu quy ước là nửa ĐÓNG thì hai luật liền kề chồng nhau ở đúng một mốc, và
    lưu cái thứ hai sẽ cắt cụt cái thứ nhất — người dùng đặt hai khung cạnh nhau
    và mất một khung mà không hiểu tại sao. Ràng buộc EXCLUDE dùng int4range
    (nửa mở), nên hai luật này thậm chí không tới được phép cắt; kiểm ở đây để
    nếu ai đó đổi quy ước, chỗ hỏng lộ ra ngay.
    """
    p = plan_window_trim(old_start, old_end, new_start, new_end)
    # Không giao nhau ⇒ phần giữ lại phải đúng bằng khoảng ban đầu.
    assert p.action == "trimmed"
    assert p.keep == (old_start, old_end)
