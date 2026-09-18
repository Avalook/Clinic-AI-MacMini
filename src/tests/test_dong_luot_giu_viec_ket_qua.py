"""Đóng lượt KHÔNG huỷ việc kết quả (CONTEXT v1.0, [CHỐT-TUYỀN] 15/09/2026).

"Đóng lượt không xóa nhiệm vụ trả kết quả muộn." Trước bản này CheckoutService.
close huỷ MỌI work_item còn treo của lượt, kể cả nhập/duyệt kết quả xét nghiệm.
Hành vi mới đã chạy thật trên Postgres (smoke 15/09: KETQUA-XETNGHIEM và
DUYET-KETQUA còn PENDING, LAYMAU-MAU bị huỷ). Bài dưới canh quan hệ cho CI.
"""

from __future__ import annotations

import inspect

from clinicai.services.checkout_service import CheckoutService


def test_cau_huy_viec_treo_tru_nhom_ket_qua() -> None:
    ma = inspect.getsource(CheckoutService.close)
    dau = ma.index("SET status = 'CANCELLED'")
    khoi = ma[dau : ma.index('"""', dau)]
    assert "NOT EXISTS" in khoi and "flow_group = 'ket_qua'" in khoi, (
        "đóng lượt đang huỷ cả việc kết quả"
    )


def test_ghi_lai_so_viec_ket_qua_giu_lai() -> None:
    ma = inspect.getsource(CheckoutService.close)
    assert ma.count('"viec_ket_qua_giu_lai"') >= 2, "event và câu trả lời phải nói"
