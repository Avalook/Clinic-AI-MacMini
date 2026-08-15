"""Bia mộ của cơ chế "xếp lại ca thì lịch tự quay về" — và luật thay nó.

SỐNG NỬA NGÀY (15/08/2026). PR #115 dạy `add_shift` tự gắn lại những lịch mà
`remove()` đã gỡ. Cùng chiều hôm ấy Tuyền gặp mặt còn lại của vấn đề: lịch bị
gỡ là một lịch CÒN SỐNG không bác sĩ, đứng nguyên ở khung giờ cũ, và
`_patient_conflict` ("khách đã có lịch giờ này") chặn chính con đường sửa nó —
đặt lại cùng khung cho cùng khách với bác sĩ khác. Tuyền chốt luật mới: *"khi
bác sĩ xoá lịch cũ thì… slot đó thực sự bị xoá đi, nút huỷ lịch đó vô hiệu vì
đã xoá rồi, chỉ có đặt lịch slot mới"* — một sự kiện phải có KẾT THÚC.

Nên `remove()` nay HUỶ HẲN lịch (CANCELLED, mã BAC_SI_DOI_LICH, giữ vết
`bac_si_da_go_id` để màn hình nói được "đổi từ ai"), và cơ chế khôi phục bị gỡ
theo: không còn lịch-sống-chờ-xếp để mà quay về, và làm sống lại một lịch ĐÃ
HUỶ là viết lại quá khứ — khách có thể đã được gọi báo huỷ rồi.

Các bài dưới đây khoá luật MỚI, và khoá luôn việc cơ chế cũ không lặng lẽ quay
lại (Luật 12.5: quyết định đảo thì viết lại bài kiểm kèm lý do, không xoá).
"""

from __future__ import annotations

import inspect

from clinicai.services.config_service import RosterService


class TestXoaCaThiHuyHanLich:
    def test_go_bac_si_la_huy_han_kem_ma_ly_do(self) -> None:
        """Lịch bị gỡ phải KẾT THÚC ngay trong cùng câu UPDATE — không có
        khoảnh khắc "còn sống mà không bác sĩ" chặn khách đặt lại."""
        ma = inspect.getsource(RosterService.remove)
        dau = ma.index("UPDATE public.appointment")
        khoi = ma[dau : ma.index("RETURNING", dau)]
        assert "status = 'CANCELLED'" in khoi, "gỡ mà không huỷ là bỏ lửng"
        assert "'BAC_SI_DOI_LICH'" in khoi, "huỷ phải mang mã lý do riêng"
        assert "cancelled_by_staff_id" in khoi, "huỷ nhầm phải truy được về ai"
        assert "bac_si_da_go_id = doctor_id" in khoi, (
            "vết 'đổi từ ai' phải giữ — câu gọi khách cần cái tên"
        )

    def test_chi_huy_lich_con_cuu_duoc(self) -> None:
        """Cùng ba chốt cũ: chưa tới giờ, trạng thái còn sống — không viết
        lại quá khứ của lịch đã khám/đã đến."""
        ma = inspect.getsource(RosterService.remove)
        assert "slot_start > now()" in ma
        assert "'SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED'" in ma

    def test_co_che_khoi_phuc_da_go_khong_duoc_quay_lai(self) -> None:
        """`add_shift` không được làm sống lại lịch ĐÃ HUỶ. Muốn "hoàn tác
        xoá nhầm ca" thì đường đúng là ĐẶT LỊCH MỚI (cùng khung, cùng bác sĩ
        nếu còn ghế) — không phải lật trạng thái CANCELLED."""
        ma = inspect.getsource(RosterService)
        assert "_khoi_phuc_lich_bi_go" not in ma
        them_ca = inspect.getsource(RosterService.add_shift)
        assert "CANCELLED" not in them_ca, (
            "add_shift mà đụng tới lịch đã huỷ là làm sống lại quá khứ"
        )
