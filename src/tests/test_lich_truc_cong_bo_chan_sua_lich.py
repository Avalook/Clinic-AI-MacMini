"""Tuần lịch trực ĐÃ CÔNG BỐ chặn cả ba đường SỬA lịch, không chỉ đặt mới.

15/09/2026. Trước đó `_roster_warning` chỉ được gọi ở create(): assign_doctor,
reassign, reschedule đưa được khách vào tay bác sĩ không trực trong tuần đã
công bố, và assign_doctor còn tự chèn ca (gỡ ca rồi gán lại là ca mọc lại).

Hành vi đã chạy thật trên Postgres (smoke 15/09); các bài dưới canh QUAN HỆ để
CI bắt được nếu ai đó gỡ chốt:
  · chốt nằm trong `_guard_slot` — chỗ chung của cả ba đường;
  · tự xếp ca (quyết định Quang 09/08) chỉ chạy khi tuần CHƯA công bố, và câu
    hỏi công bố đứng TRƯỚC câu INSERT.
"""

from __future__ import annotations

import inspect

from clinicai.services.booking_service import BookingService


def test_guard_slot_hoi_lich_truc_va_ton_trong_require_roster() -> None:
    ma = inspect.getsource(BookingService._guard_slot)
    assert "_roster_warning(" in ma
    assert "_roster_is_required(" in ma


def test_ca_ba_duong_sua_lich_deu_di_qua_guard_slot() -> None:
    ma = inspect.getsource(BookingService._build_patch)
    for nhanh in (
        'action == "reassign"',
        'action == "assign_doctor"',
        'action == "reschedule"',
    ):
        dau = ma.index(nhanh)
        sau = ma.find("elif action ==", dau + len(nhanh))
        khoi = ma[dau : sau if sau != -1 else len(ma)]
        assert "_guard_slot(" in khoi, f"nhánh {nhanh} bỏ qua chốt lịch trực"


def test_tu_xep_ca_chi_khi_tuan_chua_cong_bo() -> None:
    ma = inspect.getsource(BookingService._xep_vao_lich_truc)
    hoi = ma.index("tuan_lich_truc_da_cong_bo")
    assert hoi < ma.index("INSERT INTO public.work_roster"), (
        "phải hỏi tuần đã công bố chưa TRƯỚC khi chèn ca"
    )
