"""Đọc một cột KHÔNG được SELECT thì hỏng lúc chạy, không phải lúc kiểm.

Ngày 21/08/2026 `capacity_service.quote()` đọc ``duty["settings"]`` trong khi
câu truy vấn chỉ chọn bốn cột khác. Cả bộ kiểm vẫn xanh và bản vá lên tới
staging, vì mọi bài kiểm đều dựng dòng giả bằng ``dict`` — mà ``dict`` thì có
đủ khoá do chính bài kiểm cho vào. ``asyncpg.Record`` thì không: nó ném
``KeyError`` ngay lần đầu có một bác sĩ đã được duyệt lịch trực, tức là đường
đi thường nhất của màn đặt lịch.

Cùng họ với cái bẫy ``response_model`` lặng lẽ bỏ khoá lạ: bài kiểm mô phỏng
hình dạng dữ liệu thì chỉ kiểm được hình dạng mà nó tự vẽ.
"""

from __future__ import annotations

import inspect
import re

from clinicai.services.booking_service import BookingService
from clinicai.services.capacity_service import CapacityService


def _cot_duoc_chon(nguon: str) -> set[str]:
    """Tên cột sau ``AS`` trong mọi câu SQL của đoạn mã này."""
    return {m.lower() for m in re.findall(r"\bAS\s+([a-z_][a-z0-9_]*)", nguon)}


def _cot_duoc_doc(nguon: str, bien: str) -> set[str]:
    """Mọi khoá được đọc kiểu ``bien["ten_cot"]``."""
    return set(re.findall(rf'{bien}\["([a-z_][a-z0-9_]*)"\]', nguon))


def test_capacity_quote_chi_doc_cot_da_chon() -> None:
    nguon = inspect.getsource(CapacityService.quote)
    doc = _cot_duoc_doc(nguon, "duty")
    chon = _cot_duoc_chon(nguon)
    thieu = doc - chon
    assert not thieu, (
        f"đọc cột chưa được SELECT: {sorted(thieu)} — asyncpg sẽ ném KeyError "
        f"lúc chạy. Cột đang chọn: {sorted(chon)}"
    )
    # Chốt chặn ngược: nếu phép đo trên không tìm thấy gì để đối chiếu thì nó
    # đang xanh một cách rỗng tuếch.
    assert doc, "không đọc cột nào — phép đo này đã mất tác dụng, xem lại regex"
    assert "settings" in doc and "settings" in chon


def test_roster_warning_chi_doc_cot_da_chon() -> None:
    """Cùng phép đo cho hàm anh em — nó đọc `row[...]` từ một truy vấn tương tự."""
    nguon = inspect.getsource(BookingService._roster_warning)
    doc = _cot_duoc_doc(nguon, "row")
    chon = _cot_duoc_chon(nguon)
    thieu = doc - chon
    assert not thieu, f"đọc cột chưa được SELECT: {sorted(thieu)}"
    assert doc


def test_chot_gio_ca_chi_doc_cot_da_chon() -> None:
    nguon = inspect.getsource(BookingService._chan_dat_ngoai_khung_ca)
    doc = _cot_duoc_doc(nguon, "row")
    chon = _cot_duoc_chon(nguon)
    assert not (doc - chon), f"đọc cột chưa được SELECT: {sorted(doc - chon)}"
    assert doc
