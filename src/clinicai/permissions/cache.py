"""Nhớ tạm quyền của một người — và nhớ cách quên cho đúng.

VÌ SAO CẦN. `can(...)` chạy ở MỌI lệnh. Một ca sáng bận có vài nghìn lượt gọi, và
mỗi lượt là một vòng tới database chỉ để hỏi lại đúng một câu không đổi mấy tháng.

VÌ SAO NGUY HIỂM. Cache quyền là cache một QUYẾT ĐỊNH AN NINH. Quản lý vừa thu
quyền của một người mà hệ thống còn nhớ bản cũ thì người ấy vẫn bấm được — và
không ai nhìn thấy gì bất thường. Nên ở đây chỉ có hai cách quên, và cả hai đều
phải có:

    1. QUÊN NGAY khi chính tiến trình này cấp hoặc thu quyền.
    2. QUÊN THEO GIỜ (mặc định 5 giây) cho mọi thay đổi đến từ nơi khác —
       tiến trình API thứ hai, worker, hay ai đó sửa thẳng database.

Năm giây là thoả hiệp có chủ ý: đủ ngắn để quản lý bấm xong, quay sang bảo nhân
viên thử lại là đã đúng; đủ dài để bỏ gần hết số lượt hỏi lặp. KHÔNG kéo dài
thêm nếu chưa có cách báo tin giữa các tiến trình.

KHÔNG CACHE CÂU TRẢ LỜI "KHÔNG". Một người vừa được cấp quyền phải làm được NGAY,
không chờ hết hạn cache. Chỉ nhớ những quyền người ta ĐANG CÓ; hỏi một quyền
không nằm trong đó thì vẫn xuống database. Vì vậy cache này chỉ tăng tốc đường
"được phép" — đúng đường chạy nhiều nhất — và không bao giờ giữ một lời từ chối.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

#: Bao lâu thì quên một bản ghi nhớ đến từ nơi khác.
HAN_GIAY = float(os.environ.get("QUYEN_CACHE_GIAY", "5"))


@dataclass(frozen=True)
class _Ban:
    quyen: frozenset[str]
    het_han: float


_BO_NHO: dict[tuple[str, str], _Ban] = {}


def doc(clinic_id: str, staff_id: str) -> frozenset[str] | None:
    """Quyền đang nhớ của người này, hoặc None nếu chưa nhớ / đã hết hạn."""
    ban = _BO_NHO.get((clinic_id, staff_id))
    if ban is None:
        return None
    if ban.het_han <= time.monotonic():
        _BO_NHO.pop((clinic_id, staff_id), None)
        return None
    return ban.quyen


def ghi(clinic_id: str, staff_id: str, quyen: frozenset[str]) -> None:
    _BO_NHO[(clinic_id, staff_id)] = _Ban(
        quyen=quyen, het_han=time.monotonic() + HAN_GIAY
    )


def quen(clinic_id: str, staff_id: str | None = None) -> None:
    """Quên ngay — gọi sau mỗi lần cấp hoặc thu quyền.

    Thu quyền mà còn nhớ bản cũ là lỗ hổng, nên chỗ nào đổi quyền cũng phải gọi
    hàm này TRONG cùng luồng, đừng trông vào hạn giờ.
    """
    if staff_id is not None:
        _BO_NHO.pop((clinic_id, staff_id), None)
        return
    for khoa in [k for k in _BO_NHO if k[0] == clinic_id]:
        _BO_NHO.pop(khoa, None)


def quen_het() -> None:
    """Dọn sạch — dùng trong test."""
    _BO_NHO.clear()


__all__ = ["HAN_GIAY", "doc", "ghi", "quen", "quen_het"]
