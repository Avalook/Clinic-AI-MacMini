"""Ca trực đổi thành khoảng phút — nửa mở, kẹp vào giờ mở cửa.

VIẾT LẠI 21/08/2026 (Luật 12.5: đổi luật thì viết lại kiểm KÈM LÝ DO).

Bản cũ khoá mô hình HAI ca chia bằng một mốc 12:00, và khoá đúng như thế là
đúng ở thời điểm ấy. Nay phòng khám dùng BA ca có nghỉ trưa:

    sáng 08:00–13:00 · chiều 14:00–17:30 · tối 17:30–21:30

Một mốc chia không tạo ra được khoảng trống giữa 13:00 và 14:00, nên
``shift_window()`` (trả MỘT khoảng) đổi thành ``shift_windows()`` (trả danh
sách). Các bài dưới đây giữ nguyên MỌI tính chất mà bản cũ canh — nửa mở, gộp
ca, kẹp giờ mở cửa, nhãn lạ không được biến mất, câu chữ đọc như đồng hồ — chỉ
thay con số và chữ ký hàm.

Giờ ca cụ thể của Dr4Women được canh riêng ở ``test_ba_ca_lam_viec.py``; ở đây
chỉ canh HÀNH VI của mô hình, dùng cấu hình tự đặt để bài kiểm không đổ vỡ khi
phòng khám đổi giờ.
"""

from __future__ import annotations

import pytest

from clinicai.core.shifts import (
    covers,
    describe,
    merge_windows,
    shift_windows,
)

OPEN, CLOSE = 8 * 60, 23 * 60

#: Cấu hình dùng riêng cho tệp này: ba ca LIỀN NHAU, không nghỉ trưa. Chọn vậy
#: để tách bạch hai chuyện — "gộp ca kề nhau" (canh ở đây) và "nghỉ trưa tạo
#: khoảng trống" (canh ở tệp kia).
CA_LIEN = {
    "SANG": (8 * 60, 12 * 60),
    "CHIEU": (12 * 60, 18 * 60),
    "TOI": (18 * 60, 23 * 60),
}
TRUA = 12 * 60


class TestMotCaThanhKhoangPhut:
    def test_ca_ngay_phu_tron_gio_mo_cua_khi_cac_ca_lien_nhau(self) -> None:
        assert shift_windows("FULL", OPEN, CLOSE, CA_LIEN) == [(OPEN, CLOSE)]

    def test_ca_sang_dung_o_moc_chuyen_ca(self) -> None:
        assert shift_windows("SANG", OPEN, CLOSE, CA_LIEN) == [(OPEN, TRUA)]

    def test_ca_chieu_bat_dau_o_moc_chuyen_ca(self) -> None:
        assert shift_windows("CHIEU", OPEN, CLOSE, CA_LIEN) == [(TRUA, 18 * 60)]

    def test_moc_chuyen_ca_thuoc_ca_sau_nua_mo(self) -> None:
        """``[lo, hi)`` — một khung bắt đầu đúng 12:00 là ca CHIỀU.

        Cùng quy ước với mọi khoảng phút khác trong hệ thống. Sai một đầu là
        một khung mỗi ngày rơi vào khe giữa hai ca, hoặc bị đếm hai lần.
        """
        sang = shift_windows("SANG", OPEN, CLOSE, CA_LIEN)
        chieu = shift_windows("CHIEU", OPEN, CLOSE, CA_LIEN)
        assert not covers(sang, TRUA)
        assert covers(chieu, TRUA)

    def test_ca_khong_con_phut_nao_thi_tra_rong(self) -> None:
        """Ngày chỉ mở từ 17:00 thì ca sáng là một khoảng rỗng.

        Nói ra điều đó đúng hơn là lặng lẽ cho phép đặt lúc 8 giờ sáng.
        """
        assert shift_windows("SANG", 17 * 60, 23 * 60, CA_LIEN) == []

    def test_nhan_la_coi_nhu_ca_ngay_chu_khong_bien_mat(self) -> None:
        """Một ca không đọc được mà biến mất sẽ khoá lịch của một bác sĩ đang
        thật sự đi làm — sai theo hướng đó tệ hơn hẳn."""
        assert shift_windows("KHONG_BIET", OPEN, CLOSE, CA_LIEN) == [(OPEN, CLOSE)]


class TestBacSiLaHopCacCaCuaMinh:
    def test_sang_o_tram_nay_chieu_o_tram_kia_la_mot_khoang_lien(self) -> None:
        """Có thật trong dữ liệu: BS Thành 09/08 có cả SANG lẫn CHIEU."""
        windows = merge_windows(
            [
                w
                for s in ("SANG", "CHIEU")
                for w in shift_windows(s, OPEN, CLOSE, CA_LIEN)
            ]
        )
        # Hai ca kề nhau đúng mốc chuyển ca ⇒ phải gộp thành MỘT khoảng liền,
        # nếu không thì đúng khung ấy rơi vào khe giữa hai khoảng.
        assert windows == [(OPEN, 18 * 60)]
        assert covers(windows, TRUA)

    def test_ca_trung_lap_khong_nhan_len(self) -> None:
        """Bác sĩ có ba dòng FULL (ba trạm) vẫn chỉ là một khoảng."""
        full = shift_windows("FULL", OPEN, CLOSE, CA_LIEN)
        assert merge_windows(full * 3) == [(OPEN, CLOSE)]

    def test_khong_ca_nao_thi_khong_khoang_nao(self) -> None:
        assert merge_windows([]) == []


class TestCauChuHienChoNguoiDung:
    @pytest.mark.parametrize(
        "shift,mong_doi",
        [("SANG", "08:00–12:00"), ("CHIEU", "12:00–18:00"), ("TOI", "18:00–23:00")],
    )
    def test_mot_khoang_doc_nhu_dong_ho(self, shift: str, mong_doi: str) -> None:
        assert describe(shift_windows(shift, OPEN, CLOSE, CA_LIEN)) == mong_doi

    def test_hai_khoang_roi_nhau_doc_thanh_hai_ve(self) -> None:
        """Ca cả ngày của phòng khám CÓ nghỉ trưa phải nói ra cả hai vế —
        in một khoảng 08:00–21:30 là nói dối người đọc."""
        ca_nghi_trua = {
            "SANG": (8 * 60, 13 * 60),
            "CHIEU": (14 * 60, 17 * 60 + 30),
            "TOI": (17 * 60 + 30, 21 * 60 + 30),
        }
        assert (
            describe(shift_windows("FULL", OPEN, CLOSE, ca_nghi_trua))
            == "08:00–13:00, 14:00–21:30"
        )
