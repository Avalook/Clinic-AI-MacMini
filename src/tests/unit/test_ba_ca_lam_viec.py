"""Ba ca làm việc, giờ ca do phòng khám khai, và nghỉ trưa là khoảng TRỐNG.

Tuyền chốt 21/08/2026: sáng 08:00–13:00 · chiều 14:00–17:30 · tối 17:30–21:30.
Giữa sáng và chiều có một tiếng nghỉ — thứ mà mô hình "một mốc chia" của bản cũ
không diễn tả nổi, và là lý do `shift_window()` (một khoảng) đổi thành
`shift_windows()` (danh sách).
"""

from __future__ import annotations

import json

from clinicai.core.shifts import (
    CA_MAC_DINH,
    CAC_CA,
    NHAN_CA,
    ca_cua_phut,
    covers,
    doc_cau_hinh_ca,
    gio_lam_viec,
    merge_windows,
    shift_windows,
)

MO, DONG = 7 * 60, 22 * 60


def test_ba_ca_dung_gio_dr4women() -> None:
    assert shift_windows("SANG", MO, DONG) == [(8 * 60, 13 * 60)]
    assert shift_windows("CHIEU", MO, DONG) == [(14 * 60, 17 * 60 + 30)]
    assert shift_windows("TOI", MO, DONG) == [(17 * 60 + 30, 21 * 60 + 30)]


def test_ca_ca_ngay_la_hai_khoang_roi_nhau_vi_nghi_trua() -> None:
    """Đây là thay đổi cốt lõi — và là lý do chữ ký hàm phải đổi.

    Trả về một khoảng duy nhất (08:00–21:30) nghĩa là nói dối: bác sĩ trực cả
    ngày KHÔNG khám lúc 13:30.
    """
    assert shift_windows("FULL", MO, DONG) == [
        (8 * 60, 13 * 60),
        (14 * 60, 21 * 60 + 30),
    ]


def test_nghi_trua_khong_ai_truc_va_ngoai_ba_ca_cung_vay() -> None:
    lam_viec = gio_lam_viec(MO, DONG)
    assert covers(lam_viec, 12 * 60), "12:00 vẫn là giờ khám (ca sáng tới 13:00)"
    assert not covers(lam_viec, 13 * 60 + 30), "13:30 là nghỉ trưa"
    assert not covers(lam_viec, 7 * 60 + 30), "07:30 cửa mở nhưng chưa có ca"
    assert not covers(lam_viec, 21 * 60 + 30), "21:30 là hết ca tối (nửa mở)"
    assert covers(lam_viec, 21 * 60 + 29)


def test_ranh_gioi_1730_thuoc_ca_toi_khong_thuoc_chieu() -> None:
    """Nửa mở [lo, hi) — cùng quy ước với mọi khoảng phút khác trong hệ."""
    assert not covers(shift_windows("CHIEU", MO, DONG), 17 * 60 + 30)
    assert covers(shift_windows("TOI", MO, DONG), 17 * 60 + 30)


def test_gio_ca_doc_duoc_tu_cau_hinh_phong_kham() -> None:
    """Phòng khám khác mở 9h thì khai được, không phải sửa code."""
    ca = doc_cau_hinh_ca(
        {
            "ca_lam_viec": {
                "SANG": {"bat_dau": "09:00", "ket_thuc": "12:00"},
                "CHIEU": {"bat_dau": "13:00", "ket_thuc": "17:00"},
                "TOI": {"bat_dau": "18:00", "ket_thuc": "20:00"},
            }
        }
    )
    assert shift_windows("SANG", MO, DONG, ca) == [(9 * 60, 12 * 60)]
    assert shift_windows("FULL", MO, DONG, ca) == [
        (9 * 60, 12 * 60),
        (13 * 60, 17 * 60),
        (18 * 60, 20 * 60),
    ]


def test_cau_hinh_hong_thi_lui_ve_mac_dinh_chu_khong_no() -> None:
    """Một ô đánh máy sai không được làm sập màn đặt lịch của cả phòng khám.

    Và chỉ ca HỎNG mới lùi về mặc định — các ca khai đúng vẫn giữ nguyên, vì
    mỗi ca độc lập với nhau.
    """
    ca = doc_cau_hinh_ca(
        {
            "ca_lam_viec": {
                "SANG": {"bat_dau": "chín giờ", "ket_thuc": "12:00"},
                "CHIEU": {"bat_dau": "17:00", "ket_thuc": "13:00"},  # ngược
                "TOI": {"bat_dau": "18:00", "ket_thuc": "20:00"},
            }
        }
    )
    assert ca["SANG"] == CA_MAC_DINH["SANG"]
    assert ca["CHIEU"] == CA_MAC_DINH["CHIEU"]
    assert ca["TOI"] == (18 * 60, 20 * 60), "ca khai đúng phải được giữ"
    assert doc_cau_hinh_ca(None) == CA_MAC_DINH
    assert doc_cau_hinh_ca({"ca_lam_viec": "hỏng"}) == CA_MAC_DINH


def test_gio_mo_cua_van_la_chot_ngoai_cung() -> None:
    """Cửa đóng lúc 20:00 thì ca tối bị cắt, không phải kéo dài tới 21:30."""
    assert shift_windows("TOI", MO, 20 * 60) == [(17 * 60 + 30, 20 * 60)]
    # Ngày chỉ mở từ 18:00: ca sáng là một khoảng rỗng — nói ra điều đó đúng
    # hơn là lặng lẽ cho phép đặt lúc 8 giờ sáng.
    assert shift_windows("SANG", 18 * 60, DONG) == []


def test_suy_ca_tu_gio_mot_lich_hen() -> None:
    assert ca_cua_phut(8 * 60) == "SANG"
    assert ca_cua_phut(12 * 60 + 59) == "SANG"
    assert ca_cua_phut(14 * 60) == "CHIEU"
    assert ca_cua_phut(18 * 60) == "TOI"
    # Rơi vào nghỉ trưa → ca gần nhất phía trước, KHÔNG trả None: nơi gọi duy
    # nhất là lúc tự xếp lịch trực, và không ca nào nghĩa là bác sĩ có tên
    # trong lịch hẹn mà vắng trong lịch trực.
    assert ca_cua_phut(13 * 60 + 30) == "SANG"
    # Sớm hơn cả ca đầu → ca đầu.
    assert ca_cua_phut(6 * 60) == "SANG"


def test_nhan_tieng_viet_phu_du_bon_ca() -> None:
    """Thiếu một nhãn thì tin Telegram gửi đi mất chữ ca."""
    for ma in (*CAC_CA, "FULL"):
        assert NHAN_CA.get(ma), f"thiếu nhãn cho {ma}"


def test_bac_si_truc_hai_ca_roi_nhau_thi_gop_dung() -> None:
    """Sáng ở trạm này, tối ở trạm kia — có mặt trong HỢP hai ca."""
    windows = merge_windows(
        [w for s in ("SANG", "TOI") for w in shift_windows(s, MO, DONG)]
    )
    assert windows == [(8 * 60, 13 * 60), (17 * 60 + 30, 21 * 60 + 30)]
    assert covers(windows, 9 * 60)
    assert covers(windows, 18 * 60)
    assert not covers(windows, 15 * 60), "chiều không trực thì không phủ"


def test_settings_tho_tu_database_doc_duoc_ca_hai_dang() -> None:
    """Cột JSONB về tay Python có thể là dict HOẶC chuỗi JSON.

    Tuỳ codec của asyncpg, và đó là kiểu lệch chỉ lộ ra khi deploy: hàm chạy
    đúng trên máy dev rồi trả cấu hình rỗng trên máy chủ. Chịu được cả hai dạng
    là cách duy nhất không phải nhớ mình đang ở đâu.
    """
    from clinicai.core.shifts import ca_tu_settings

    mong_doi = (9 * 60, 11 * 60)
    dang_dict = {"ca_lam_viec": {"SANG": {"bat_dau": "09:00", "ket_thuc": "11:00"}}}
    assert ca_tu_settings(dang_dict)["SANG"] == mong_doi
    assert ca_tu_settings(json.dumps(dang_dict))["SANG"] == mong_doi
    assert ca_tu_settings(json.dumps(dang_dict).encode())["SANG"] == mong_doi


def test_settings_hong_hoac_thieu_thi_lui_ve_mac_dinh() -> None:
    """Không ném lỗi: một cấu hình hỏng không được làm sập màn đặt lịch."""
    from clinicai.core.shifts import ca_tu_settings

    hong: tuple[object, ...] = (None, "", "khong-phai-json", b"{[", 42, [], {"khac": 1})
    for xau in hong:
        assert ca_tu_settings(xau) == CA_MAC_DINH, f"hỏng ở {xau!r}"


class TestKhungTheoThu:
    """Giờ mở cửa từng thứ → khung nhận lịch từng thứ.

    Trình duyệt lọc ô giờ theo bảng này. Sai ở đây nghĩa là lưới mời một giờ mà
    máy chủ sẽ từ chối — mời rồi mới mắng.
    """

    def test_ba_ca_cat_ngay_lam_hai_khoang_vi_nghi_trua(self) -> None:
        from clinicai.core.shifts import khung_theo_thu

        ket = khung_theo_thu({"1": ("07:00", "22:00")})
        # 08:00–13:00 rồi 14:00–21:30; chiều với tối liền nhau nên nhập một.
        assert ket == {"1": [[480, 780], [840, 1290]]}

    def test_gio_mo_cua_hep_thi_cat_bot_ca(self) -> None:
        from clinicai.core.shifts import khung_theo_thu

        ket = khung_theo_thu({"3": ("09:00", "16:00")})
        assert ket == {"3": [[540, 780], [840, 960]]}

    def test_moi_thu_tinh_rieng(self) -> None:
        from clinicai.core.shifts import khung_theo_thu

        ket = khung_theo_thu({"0": ("07:00", "22:00"), "6": ("08:00", "12:00")})
        assert set(ket) == {"0", "6"}
        assert ket["6"] == [[480, 720]], "thứ Bảy đóng lúc 12:00"

    def test_thu_khai_gio_hong_thi_bo_qua_thu_do_thoi(self) -> None:
        """Một ô đánh máy sai không được làm hỏng cả bảng."""
        from clinicai.core.shifts import khung_theo_thu

        ket = khung_theo_thu(
            {"1": ("07:00", "22:00"), "2": ("bay gio", "22:00"), "3": ("07:00", "")}
        )
        assert set(ket) == {"1"}, "chỉ thứ khai đúng mới có mặt"

    def test_doc_gio_ca_cua_phong_kham_chu_khong_viet_cung(self) -> None:
        from clinicai.core.shifts import khung_theo_thu

        rieng = {
            "SANG": (540, 750),
            "CHIEU": (810, 1020),
            "TOI": (1080, 1320),
        }
        ket = khung_theo_thu({"1": ("07:00", "23:00")}, rieng)
        assert ket == {"1": [[540, 750], [810, 1020], [1080, 1320]]}
