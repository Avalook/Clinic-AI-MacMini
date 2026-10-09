"""Công tắc chọn cơ sở khi đăng nhập + cơ sở mặc định (`clinic.settings`).

Tuyền 08/10/2026: Kim Ngưu tạm đóng — tắt màn hỏi, mọi người vào thẳng cơ sở
mặc định (Hào Nam); Kim Ngưu mở lại thì bật. Thuần, không đọc database: đầu vào
rác (chuỗi JSON hỏng, UUID sai) trả giá trị an toàn thay vì ném.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

KHOA_HOI = "hoi_chon_co_so"
KHOA_MAC_DINH = "co_so_mac_dinh"


def doc_chon_co_so(settings: Any) -> tuple[bool, str | None]:
    """(có hỏi chọn cơ sở không — mặc định CÓ, cơ sở mặc định hoặc None)."""
    doc: Any = settings
    if isinstance(doc, (str, bytes)):
        try:
            doc = json.loads(doc)
        except ValueError:
            doc = None
    if not isinstance(doc, dict):
        return True, None
    hoi = doc.get(KHOA_HOI) is not False
    raw = doc.get(KHOA_MAC_DINH)
    try:
        mac_dinh = str(UUID(str(raw))) if raw else None
    except ValueError:
        mac_dinh = None
    return hoi, mac_dinh
