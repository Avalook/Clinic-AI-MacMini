"""Nối form Nam khoa với bốn phép tính — và những chỗ dễ đọc sai.

Bốn hàm ở `andrology_service` đã có test riêng. Ở đây kiểm phần DỊCH: form phẳng
từ màn hình thành tham số, và ba quyết định trong đó thay đổi kết luận lâm sàng
nếu làm sai.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.andrology_review_service import (
    AndrologyReviewService,
    larger_testis_volume,
    semen_params,
    vas_palpable,
)
from tests.services.fake_pool import FakePool

CLINIC = "a0000000-0000-4000-8000-000000000001"

NGUONG = [
    {
        "parameter": "concentration_m_ml",
        "label": "Nồng độ tinh trùng",
        "lower_limit": Decimal("16"),
        "unit": "triệu/mL",
        "source": "WHO_2021",
    },
    {
        "parameter": "volume_ml",
        "label": "Thể tích",
        "lower_limit": Decimal("1.4"),
        "unit": "mL",
        "source": "WHO_2021",
    },
]


def _who() -> StaffIdentity:
    return StaffIdentity(
        auth_user_id="u-1",
        staff_id="s-1",
        full_name="BS. A",
        department=ClinicRole.DOCTOR.value,
        role=ClinicRole.DOCTOR,
        clinic_id=CLINIC,
        location_id="c1100000-0000-4000-8000-000000000001",
        location_name="Kim Ngưu",
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class TestLanNaoThang:
    def test_co_lan_2_thi_doc_lan_2(self) -> None:
        """AUA yêu cầu làm lại sau ~1 tháng khi kết quả bất thường. Đọc lần 1
        khi đã có lần 2 là đọc một kết quả đã bị thay thế."""
        out = semen_params({"tdd_nong_do_l1": "5", "tdd_nong_do_l2": "30"})
        assert out["concentration_m_ml"] == 30.0

    def test_lan_2_bang_0_van_thang_lan_1(self) -> None:
        """SỐ 0 LÀ FALSY, và đây là chỗ nó cắn.

        `_so(l2) or _so(l1)` bỏ qua lần 2 khi lần 2 bằng 0 — mà 0 ở đây là
        KHÔNG THẤY TINH TRÙNG, kết quả quan trọng nhất của cả phiếu. Lỗi này đã
        xảy ra thật: một ca lần 1 = 3, lần 2 = 0 đọc ra 3, và gợi ý thành
        "thiểu tinh nặng" thay vì "không thấy tinh trùng trong mẫu".
        """
        out = semen_params({"tdd_nong_do_l1": "3", "tdd_nong_do_l2": "0"})
        assert out["concentration_m_ml"] == 0.0

    def test_chua_lam_lan_2_thi_doc_lan_1(self) -> None:
        out = semen_params({"tdd_nong_do_l1": "5", "tdd_nong_do_l2": ""})
        assert out["concentration_m_ml"] == 5.0

    def test_chua_lam_gi_thi_khong_co_tham_so_nao(self) -> None:
        """Không làm xét nghiệm và làm ra kết quả 0 là hai chuyện khác nhau.
        Ô trống thành 0 sẽ gắn cờ "dưới ngưỡng" cho việc chưa làm."""
        assert semen_params({"tdd_nong_do_l1": "", "tdd_nong_do_l2": None}) == {}

    def test_dau_phay_thap_phan(self) -> None:
        """Bàn phím tiếng Việt gõ "1,4" là chuyện thường."""
        assert semen_params({"tdd_the_tich_l1": "1,2"})["volume_ml"] == 1.2

    def test_chu_khong_thanh_so(self) -> None:
        assert semen_params({"tdd_nong_do_l1": "không đếm được"}) == {}


class TestOngDanTinh:
    def test_khong_so_thay_hai_ben_moi_la_khong(self) -> None:
        """Bất sản một bên KHÔNG hướng tới CBAVD. Gợi ý CFTR dựa trên một bên
        là gợi ý sai."""
        assert (
            vas_palpable(
                {
                    "kls_ong_dan_tinh_t": "khong_so_thay",
                    "kls_ong_dan_tinh_p": "khong_so_thay",
                }
            )
            is False
        )

    def test_mot_ben_khong_so_thay_van_tinh_la_co(self) -> None:
        assert (
            vas_palpable(
                {
                    "kls_ong_dan_tinh_t": "khong_so_thay",
                    "kls_ong_dan_tinh_p": "binh_thuong",
                }
            )
            is True
        )

    def test_kham_thieu_mot_ben_thi_khong_ket_luan(self) -> None:
        assert vas_palpable({"kls_ong_dan_tinh_t": "binh_thuong"}) is None

    def test_chua_kham_gi(self) -> None:
        assert vas_palpable({}) is None


class TestTheTichTinhHoan:
    def test_lay_ben_lon_hon_chu_khong_lay_trung_binh(self) -> None:
        """Câu hỏi "sinh tinh có bảo tồn không" hỏi về bên tốt nhất. Trung bình
        sẽ để một bên teo kéo chìm cả hai, và biến một ca hướng tắc nghẽn thành
        hướng suy sinh tinh."""
        assert (
            larger_testis_volume({"kls_th_the_tich_t": "4", "kls_th_the_tich_p": "18"})
            == 18.0
        )

    def test_chi_kham_mot_ben(self) -> None:
        assert larger_testis_volume({"kls_th_the_tich_p": "15"}) == 15.0

    def test_chua_do(self) -> None:
        assert larger_testis_volume({}) is None


class TestReview:
    def test_duoi_nguong_thi_co_co_kem_nguon(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(), form_data={"tdd_nong_do_l1": "12"}
            )
        )
        assert len(out["semen_flags"]) == 1
        co = out["semen_flags"][0]
        assert co["lower_limit"] == 16.0 and co["source"] == "WHO_2021"
        # Câu chữ dừng ở "dưới ngưỡng" — bước sang chẩn đoán là việc của bác sĩ.
        assert "dưới ngưỡng" in co["message"]
        assert out["reference_source"] == "WHO_2021"

    def test_tren_nguong_thi_khong_co_co_nao(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(), form_data={"tdd_nong_do_l1": "40"}
            )
        )
        assert out["semen_flags"] == []

    def test_vo_tinh_o_lan_2_doc_dung_ly_do(self) -> None:
        """Kiểm cả đường: lần 1 có tinh trùng, lần 2 không. Lý do gợi ý phải
        nói "không thấy tinh trùng", không phải "thiểu tinh nặng"."""
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(),
                form_data={"tdd_nong_do_l1": "3", "tdd_nong_do_l2": "0"},
            )
        )
        ly_do = {g["reason"] for g in out["genetic_suggestions"]}
        assert any("không thấy tinh trùng" in r for r in ly_do)
        assert not any("thiểu tinh" in r for r in ly_do)

    def test_vo_tinh_thi_goi_y_karyotype_va_azf_kem_ly_do(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(), form_data={"tdd_nong_do_l1": "0"}
            )
        )
        ma = {g["test"] for g in out["genetic_suggestions"]}
        assert "CLS_KARYOTYPE" in ma and "CLS_Y_MICRODELETION" in ma
        assert all(g["reason"] for g in out["genetic_suggestions"])

    def test_bmi_tinh_o_backend(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(),
                form_data={"kls_chieu_cao": "175", "kls_can_nang": "70"},
            )
        )
        assert out["bmi"] == 22.9

    def test_thieu_so_do_thi_bmi_la_none_chu_khong_phai_0(self) -> None:
        """BMI bằng 0 lọt vào mọi phép so sánh; None thì màn hình hiện dấu gạch
        và không ai đọc nhầm."""
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(), form_data={"kls_chieu_cao": "175"}
            )
        )
        assert out["bmi"] is None

    def test_testosterone_ngoai_sinh_duoc_nhac(self) -> None:
        """Bỏ sót dòng này là chẩn đoán nhầm thành vô tinh không do tắc — một
        chẩn đoán đổi hẳn hướng điều trị."""
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(),
                form_data={"ts_testosterone_ngoai": "dang_dung"},
            )
        )
        assert any("testosterone" in n.lower() for n in out["notes"])

    def test_ngung_lau_roi_thi_khong_nhac(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(),
                form_data={"ts_testosterone_ngoai": "ngung_tren_6"},
            )
        )
        assert not any("testosterone" in n.lower() for n in out["notes"])

    def test_khong_bao_gio_tra_ve_mot_chan_doan(self) -> None:
        """Chốt cuối: không chuỗi nào trả về được đọc thành kết luận."""
        pool = FakePool(NGUONG)
        out = _run(
            AndrologyReviewService(pool).review(
                identity=_who(),
                form_data={
                    "tdd_nong_do_l1": "0",
                    "nt_fsh": "2",
                    "kls_th_the_tich_t": "18",
                },
            )
        )
        chu = " ".join(
            [c["message"] for c in out["semen_flags"]]
            + [g["reason"] for g in out["genetic_suggestions"]]
            + out["notes"]
        ).lower()
        assert "vô sinh" not in chu
        assert "chẩn đoán" not in chu

    def test_form_rong_khong_no(self) -> None:
        pool = FakePool(NGUONG)
        out = _run(AndrologyReviewService(pool).review(identity=_who(), form_data={}))
        assert out["semen_flags"] == []
        assert out["genetic_suggestions"] == []
        assert out["bmi"] is None
