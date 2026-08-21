"""Quản lý tự sửa giờ ca — cấu hình sai phải bị chặn NGAY, kèm lý do đọc được.

Trước đây giờ ca chỉ đổi được bằng lệnh SQL, tức là phải gọi người viết code.
Khi mở cho quản lý tự nhập thì mọi kiểu sai đều sẽ tới: thiếu một ca, gõ ngược
giờ, hai ca chồng nhau, ca tràn ra ngoài giờ mở cửa.

Kiểu sai nguy hiểm nhất là kiểu KHÔNG báo gì: ca tràn ngoài giờ mở cửa vẫn lưu
được, nhưng lúc đọc bị cắt — màn cấu hình hiện 22:00 còn hệ chỉ nhận lịch tới
21:00. Không ai lần ra được, vì con số trên màn hình vẫn đúng như đã nhập.
"""

from __future__ import annotations

from clinicai.core.shifts import CA_MAC_DINH, kiem_cau_hinh_ca

# Giờ mở cửa hiện tại của Dr4Women: 07:00–22:00 mọi ngày.
MO_CUA = {str(t): ("07:00", "22:00") for t in range(7)}


class TestCauHinhDung:
    def test_ba_ca_mac_dinh_khong_co_loi(self) -> None:
        assert kiem_cau_hinh_ca(CA_MAC_DINH, MO_CUA) == []

    def test_ca_sat_nhau_khong_phai_la_chong_nhau(self) -> None:
        """Chiều kết thúc 17:30, tối bắt đầu 17:30 — liền nhau, không chồng."""
        assert kiem_cau_hinh_ca(CA_MAC_DINH, MO_CUA) == []

    def test_khong_truyen_gio_mo_cua_thi_bo_qua_phep_kiem_do(self) -> None:
        assert kiem_cau_hinh_ca(CA_MAC_DINH) == []


class TestThieuCa:
    def test_thieu_mot_ca_thi_bao(self) -> None:
        thieu = {k: v for k, v in CA_MAC_DINH.items() if k != "TOI"}
        loi = kiem_cau_hinh_ca(thieu, MO_CUA)
        assert any("Thiếu ca" in x and "Tối" in x for x in loi), loi

    def test_cau_bao_noi_ro_vi_sao_thieu_la_nguy_hiem(self) -> None:
        """Thiếu ca KHÔNG phải là bỏ ca — bản đọc lấy giờ mặc định cho nó."""
        loi = kiem_cau_hinh_ca({"SANG": (480, 780)}, MO_CUA)
        assert any("mặc định" in x for x in loi), loi


class TestGioNguoc:
    def test_ket_thuc_truoc_bat_dau(self) -> None:
        xau = dict(CA_MAC_DINH)
        xau["CHIEU"] = (1050, 840)
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("kết thúc" in x and "Chiều" in x for x in loi), loi

    def test_ca_dai_khong_phut_nao(self) -> None:
        xau = dict(CA_MAC_DINH)
        xau["SANG"] = (480, 480)
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("Sáng" in x for x in loi), loi


class TestChongNhau:
    def test_hai_ca_chong_len_nhau(self) -> None:
        xau = dict(CA_MAC_DINH)
        xau["CHIEU"] = (720, 1050)  # 12:00, trong khi ca sáng tới 13:00
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("chồng" in x for x in loi), loi

    def test_cau_bao_giai_thich_hau_qua_that(self) -> None:
        """Không chỉ nói "sai" — nói vì sao nó hỏng thứ quản lý đang cần."""
        xau = dict(CA_MAC_DINH)
        xau["TOI"] = (1020, 1290)  # 17:00, trong khi ca chiều tới 17:30
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("đếm đôi" in x for x in loi), loi


class TestTranNgoaiGioMoCua:
    """Kiểu sai KHÔNG báo gì — nếu không kiểm ở đây thì không ai thấy."""

    def test_ca_toi_keo_qua_gio_dong_cua(self) -> None:
        xau = dict(CA_MAC_DINH)
        xau["TOI"] = (1050, 23 * 60)  # tới 23:00 nhưng cửa đóng 22:00
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("mở cửa" in x and "Tối" in x for x in loi), loi
        assert any("cắt" in x for x in loi), "phải nói rõ hậu quả là bị cắt"

    def test_ca_sang_bat_dau_truoc_gio_mo_cua(self) -> None:
        xau = dict(CA_MAC_DINH)
        xau["SANG"] = (6 * 60, 780)  # 06:00 nhưng cửa mở 07:00
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("mở cửa" in x and "Sáng" in x for x in loi), loi

    def test_bao_dung_ngay_bi_hep(self) -> None:
        """Chỉ thứ Bảy đóng sớm thì câu báo phải gọi tên thứ Bảy."""
        gio = dict(MO_CUA)
        gio["6"] = ("07:00", "18:00")
        loi = kiem_cau_hinh_ca(CA_MAC_DINH, gio)
        assert loi, "ca tối 17:30–21:30 không lọt vào ngày đóng lúc 18:00"
        assert all("Thứ Bảy" in x for x in loi), loi
        assert len(loi) == 1, "một lỗi thì một dòng"

    def test_ca_tuan_hep_giong_nhau_thi_gop_lam_mot_dong(self) -> None:
        """Luật đổi 21/08/2026 sau khi đo trên staging: bản đầu in BẢY dòng.

        Phòng khám mở giống nhau cả tuần, ca tối tràn giờ đóng cửa — bản đầu
        sinh một dòng cho MỖI thứ, bảy dòng gần y hệt cho một lỗi duy nhất. Bảy
        dòng na ná nhau là thứ người ta lướt qua, và lướt qua thì câu thứ tám
        nói thật cũng bị bỏ lỡ.
        """
        xau = dict(CA_MAC_DINH)
        xau["TOI"] = (1050, 23 * 60)
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert len(loi) == 1, f"phải gộp làm một dòng, đang có {len(loi)}: {loi}"
        assert "Mọi ngày" in loi[0], loi[0]
        assert "Tối" in loi[0] and "07:00–22:00" in loi[0]

    def test_hai_nhom_gio_khac_nhau_thi_hai_dong(self) -> None:
        """Gộp KHÔNG được gộp nhầm hai nhóm giờ khác nhau làm một."""
        gio = {**MO_CUA, "0": ("07:00", "19:00"), "6": ("07:00", "19:00")}
        xau = dict(CA_MAC_DINH)
        xau["TOI"] = (1050, 23 * 60)
        loi = kiem_cau_hinh_ca(xau, gio)
        assert len(loi) == 2, f"hai khung giờ khác nhau ⇒ hai dòng: {loi}"
        assert any("07:00–19:00" in x for x in loi)
        assert any("07:00–22:00" in x for x in loi)
        cn_t7 = next(x for x in loi if "07:00–19:00" in x)
        assert "Chủ nhật" in cn_t7 and "Thứ Bảy" in cn_t7, cn_t7

    def test_ngay_khai_gio_hong_thi_bo_qua_ngay_do(self) -> None:
        gio = dict(MO_CUA)
        gio["3"] = ("khong-phai-gio", "22:00")
        assert kiem_cau_hinh_ca(CA_MAC_DINH, gio) == []


class TestBaoDuMoiLoiMotLan:
    def test_hai_o_sai_thi_bao_ca_hai(self) -> None:
        """Sửa một ô rồi bấm lưu để biết ô thứ hai là cách làm người ta nản."""
        xau = dict(CA_MAC_DINH)
        xau["SANG"] = (780, 480)  # ngược
        xau["TOI"] = (1050, 23 * 60)  # tràn giờ đóng cửa
        loi = kiem_cau_hinh_ca(xau, MO_CUA)
        assert any("Sáng" in x for x in loi), loi
        assert any("Tối" in x for x in loi), loi
