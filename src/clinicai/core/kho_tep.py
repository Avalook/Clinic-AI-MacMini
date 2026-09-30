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

HAI Ổ, HAI NGẮT MẠCH (01/10/2026). Tệp mới nằm ở ổ VPS (``kho="vps"``) trước khi
được đẩy sang Viettel CFS (``kho="cfs"``, mặc định). CFS treo không được làm
tắt đường đọc tệp đang nằm ở ổ VPS, nên mỗi ổ một mạch ngắt riêng.
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
#: Ghi MỘT khối (tới ~4MB) của một lượt tải lên: ổ bình thường xong dưới 1 giây.
#: Không bọc cả vòng ghi video nhiều trăm MB bằng một hạn — hạn tính TỪNG KHỐI.
HAN_GHI_KHOI = 10.0
#: Sau một lần quá hạn, bao lâu thì thử chạm ổ lại.
NGAT_GIAY = 30.0
CAU_KHO_CHAM = (
    "Kho lưu tệp (Viettel File Storage) đang chậm — chưa mở được tệp. Thử lại "
    "sau ít phút; các việc khác vẫn dùng bình thường."
)

#: Ổ mặc định: Viettel CFS (ổ mạng hay chậm). ``"vps"`` = ổ của chính máy chủ.
KHO_CFS = "cfs"
KHO_VPS = "vps"
CAU_O_VPS_CHAM = (
    "Ổ lưu tạm trên máy chủ đang chậm — chưa xử lý được tệp. Thử lại sau ít "
    "phút; các việc khác vẫn dùng bình thường."
)

_ngat_den: dict[str, float] = {}


def dang_ngat(kho: str = KHO_CFS) -> bool:
    return time.monotonic() < _ngat_den.get(kho, 0.0)


def mo_lai() -> None:
    """Dùng trong test: bỏ trạng thái ngắt mạch của mọi ổ."""
    _ngat_den.clear()


def _cau(kho: str) -> str:
    return CAU_O_VPS_CHAM if kho == KHO_VPS else CAU_KHO_CHAM


def han_theo_co(so_byte: int) -> float:
    """Hạn cho một lần chép/ghi TRỌN ``so_byte`` byte: ``HAN_GIAY`` + 1 giây mỗi MB
    (ổ chậm hơn 1MB/s coi như đang hỏng)."""
    return HAN_GIAY + so_byte / (1024 * 1024)


async def chay_tren_kho(
    ham: Callable[[], T], *, han: float | None = None, kho: str = KHO_CFS
) -> T:
    """Chạy ``ham`` (đồng bộ, chạm ổ tệp) ở luồng phụ, tối đa ``han`` giây
    (mặc định ``HAN_GIAY``, đọc lúc gọi). ``kho``: ổ nào — quá hạn thì chỉ
    ngắt mạch của ổ ấy."""
    if dang_ngat(kho):
        raise ExternalServiceError(_cau(kho))
    if han is None:
        han = HAN_GIAY
    try:
        return await asyncio.wait_for(asyncio.to_thread(ham), timeout=han)
    except TimeoutError:
        _ngat_den[kho] = time.monotonic() + NGAT_GIAY
        logger.error("kho_tep_qua_han", kho=kho, han_giay=han, ngat_giay=NGAT_GIAY)
        raise ExternalServiceError(_cau(kho)) from None


async def don_tren_kho(
    ham: Callable[[], object], *, viec: str, kho: str = KHO_CFS
) -> None:
    """Dọn dẹp trên ổ (xoá tệp dở, đóng tệp) — cố hết sức, KHÔNG BAO GIỜ ném.

    Dọn dẹp chạy trong nhánh lỗi: ném ở đây sẽ che mất lỗi gốc (người dùng thấy
    "kho chậm" thay vì "tệp không phải ảnh"). Đang ngắt mạch thì bỏ qua luôn —
    không đẻ thêm luồng treo chờ ổ chỉ để xoá một tệp tạm; tệp sót lại có tên
    trong log để dọn tay.
    """
    if dang_ngat(kho):
        logger.warning("kho_tep_bo_qua_don", viec=viec, ly_do="dang_ngat_mach")
        return
    try:
        await chay_tren_kho(ham, kho=kho)
    except Exception as loi:  # noqa: BLE001 — dọn dẹp không được che lỗi gốc
        logger.warning("kho_tep_don_loi", viec=viec, loi=repr(loi))
