"""Chạm ổ lưu tệp KHÔNG BAO GIỜ trên vòng sự kiện (29/09/2026).

Sự cố 29/09 20:00: ổ Viettel File Storage (CIFS gắn ở ``/mnt/viettel-cfs``)
chậm/treo. ``path.exists()`` gọi thẳng trong hàm ``async`` đứng chờ ổ mạng →
cả vòng sự kiện đứng theo: MỌI màn quay, health quá hạn, tới khi khởi động lại
API. Một tệp chậm không được phép làm treo cả phòng khám.

Luật: mọi thao tác chạm ổ tệp trong đường xử lý request đi qua
``chay_tren_kho`` — chạy ở LUỒNG PHỤ, có HẠN GIỜ. Quá hạn thì trả lỗi ngay
(502, câu nói rõ "kho tệp chậm") và NGẮT MẠCH một lúc: các yêu cầu tệp sau
trả lỗi luôn, không đẻ thêm luồng treo chờ ổ mạng (luồng đã treo không huỷ
được — chỉ có thể không tạo thêm). Việc khác của phòng khám chạy bình thường.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import TypeVar

import structlog

from clinicai.core.exceptions import ExternalServiceError

logger = structlog.get_logger()

T = TypeVar("T")

#: Một thao tác trên ổ (stat, mở, đọc ảnh nhỏ) bình thường mất vài chục ms.
HAN_GIAY = 4.0
#: Sau một lần quá hạn, bao lâu thì thử chạm ổ lại.
NGAT_GIAY = 30.0
CAU_KHO_CHAM = (
    "Kho lưu tệp (Viettel File Storage) đang chậm — chưa mở được tệp. Thử lại "
    "sau ít phút; các việc khác vẫn dùng bình thường."
)

_ngat_den = 0.0


def dang_ngat() -> bool:
    return time.monotonic() < _ngat_den


def mo_lai() -> None:
    """Dùng trong test: bỏ trạng thái ngắt mạch."""
    global _ngat_den
    _ngat_den = 0.0


async def chay_tren_kho(ham: Callable[[], T], *, han: float = HAN_GIAY) -> T:
    """Chạy ``ham`` (đồng bộ, chạm ổ tệp) ở luồng phụ, tối đa ``han`` giây."""
    global _ngat_den
    if dang_ngat():
        raise ExternalServiceError(CAU_KHO_CHAM)
    try:
        return await asyncio.wait_for(asyncio.to_thread(ham), timeout=han)
    except TimeoutError:
        _ngat_den = time.monotonic() + NGAT_GIAY
        logger.error("kho_tep_qua_han", han_giay=han, ngat_giay=NGAT_GIAY)
        raise ExternalServiceError(CAU_KHO_CHAM) from None
