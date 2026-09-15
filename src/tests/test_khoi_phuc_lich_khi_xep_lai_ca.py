"""Gỡ ca trực: GIỮ lịch, gỡ bác sĩ, đưa về hàng chờ xếp — và vì sao đảo lại.

LỊCH SỬ (Luật 12.5: quyết định đảo thì viết lại bài kiểm kèm lý do):

  · #103 (14/08/2026) gỡ ca → gỡ bác sĩ, lịch về "Chờ xếp bác sĩ".
  · #115 dạy `add_shift` tự gắn lại lịch bị gỡ — sống nửa ngày, bỏ vì đụng
    ghế đã bị lịch khác chiếm.
  · #117 (15/08) đổi sang HUỶ HẲN: lịch sống không bác sĩ chặn việc ĐẶT LỊCH
    MỚI cùng khung cho cùng khách (`_patient_conflict`).
  · CONTEXT v1.0 (12/09, Tuyền chốt): *đổi/gỡ lịch trực không bao giờ huỷ
    lịch hẹn* — giữ hết, hiện xung đột kèm người xử lý.

Cái chặn của #117 có thật, nhưng đường đúng là SỬA CHÍNH LỊCH ĐÓ ở hàng chờ
(gán bác sĩ khác, đổi giờ) — không tạo lịch thứ hai. Nên luật hiện hành quay
về cơ chế #103 (giữ khung-giờ của 17/08) và KHÔNG mang lại tự-gắn của #115.
"""

from __future__ import annotations

import inspect

from clinicai.services.config_service import RosterService


def _cau_update_lich() -> str:
    ma = inspect.getsource(RosterService.remove)
    dau = ma.index("UPDATE public.appointment")
    return ma[dau : ma.index('"""', dau)]


class TestGoCaGiuLich:
    def test_go_ca_khong_huy_lich(self) -> None:
        """Câu UPDATE chỉ gỡ bác sĩ — không một cột huỷ nào được chạm."""
        khoi = _cau_update_lich()
        assert "doctor_id = NULL" in khoi
        for cot in ("status =", "cancelled_at", "ly_do_huy_ma", "cancelled_by"):
            assert cot not in khoi, f"gỡ ca đang ghi '{cot}' — tức là huỷ lịch"
        assert "BAC_SI_DOI_LICH" not in inspect.getsource(RosterService.remove)

    def test_giu_vet_doi_tu_ai(self) -> None:
        """CSKH gọi khách cần nói được "đổi từ bác sĩ nào"."""
        assert "bac_si_da_go_id = doctor_id" in _cau_update_lich()

    def test_chi_lich_con_song_va_dung_bac_si(self) -> None:
        """Chưa tới giờ, còn sống — và câu UPDATE tự kiểm lại trạng thái + bác
        sĩ, để lượt check-in/gán lại chen giữa không bị gỡ nhầm."""
        ma = inspect.getsource(RosterService.remove)
        assert "slot_start > now()" in ma
        khoi = _cau_update_lich()
        assert "'SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED'" in khoi
        assert "AND doctor_id = $3::uuid" in khoi

    def test_go_ca_de_lai_dau_vet(self) -> None:
        """Dòng ca bị xoá khỏi bảng — event là dấu vết duy nhất còn lại."""
        assert "'roster.shift_removed'" in inspect.getsource(RosterService.remove)

    def test_co_che_tu_gan_lai_cua_115_khong_quay_lai(self) -> None:
        """`add_shift` không tự gắn lại bác sĩ và không đụng lịch đã huỷ:
        gán lại là việc của người trực ở hàng chờ (cờ `bs_go_co_ca_lai`)."""
        ma = inspect.getsource(RosterService)
        assert "_khoi_phuc_lich_bi_go" not in ma
        them_ca = inspect.getsource(RosterService.add_shift)
        assert "CANCELLED" not in them_ca
