"""Bản khai module "Liên thông đơn thuốc quốc gia" (24/11/2026).

Tách khỏi `modules.py` vì tệp ấy đã quá trần kích thước (chỉ được giảm —
`scripts/tran-kich-thuoc.json`); `modules.py` chỉ giữ một dòng gọi.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clinicai.modules import Module


def khai_module_don_thuoc_quoc_gia() -> Module:
    """TT 26/2025: gửi đơn lên Hệ thống đơn thuốc quốc gia. Chỉ ĐỌC đơn của
    module khám; công tắc DTQG_BAT, mặc định tắt."""
    # Nạp muộn: `modules.py` gọi hàm này lúc dựng MODULE (lớp Module đã có).
    from clinicai.modules import Module

    return Module(
        ma="don_thuoc_quoc_gia",
        ten="Liên thông đơn thuốc quốc gia",
        bang=["dtqg_gui"],
    )


__all__ = ["khai_module_don_thuoc_quoc_gia"]
