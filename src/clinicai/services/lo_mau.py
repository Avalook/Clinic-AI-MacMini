"""Lô MẪU — một câu hỏi "lô này có phải lô thật không?" trả lời ở đúng một chỗ.

Lô `DEMO1709-*` nạp 17/09/2026 để thử màn (nhân bản 08/10), không có thật; prod đưa
về 0 ngày 20/11 (`scripts/huy-lo-demo.py`). Còn hay hết tồn, chúng KHÔNG được:
- tự giao chọn (`pharmacy_service.khoa_lo_de_giao` — hạn gần, FEFO sẽ trừ nhầm);
- vào báo cáo kho, khối kho của báo cáo hàng hoá, tab Thuốc trong kho (đơn vị
  "hộp" khác lô thật "hộp 30 viên" → mỗi thuốc hai dòng).
Theo dõi thuốc vẫn thấy chúng: đó là màn truy vết chuyện đã xảy ra.
"""

from __future__ import annotations

#: Tiền tố số lô của lô mẫu.
LO_MAU_TIEN_TO = "DEMO1709-"


def khong_phai_lo_mau(bang: str = "b") -> str:
    """Điều kiện SQL: dòng `drug_batch` (bí danh `bang`) không phải lô mẫu.

    Tiền tố là hằng của code, không phải dữ liệu người gõ → ghép thẳng an toàn."""
    return f"NOT starts_with({bang}.batch_code, '{LO_MAU_TIEN_TO}')"
