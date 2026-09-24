"""Chế độ của một phiếu khám — NHẬN từ clinical shell, gói này không tự quyết.

Khi nào hồ sơ khám được coi là chốt, và chốt thì đính chính theo đường nào, là
luật của clinical shell (Bàn khám và lõi hồ sơ). Gói phiếu khám không đọc trạng
thái lượt, không biết mốc chốt nằm ở đâu. Nó chỉ nhận MỘT trong ba giá trị:

    editable          đang khám — gõ, tự lưu bình thường
    finalized_locked  hồ sơ đã chốt — chỉ đọc, không mở phiếu mới
    amendment_mode    hồ sơ đã chốt và đang được đính chính — gõ được; lý do,
                      người duyệt, dấu vết là việc của shell

Giá trị lạ hoặc thiếu → CHẶN (đóng khi nghi ngờ). Một phiếu mở ra ghi được chỉ
vì shell quên truyền chế độ là đúng loại lỗi không ai thấy cho tới ngày có
chuyện.
"""

from __future__ import annotations

from typing import Literal, get_args

from clinicai.core.exceptions import ValidationError

CheDo = Literal["editable", "finalized_locked", "amendment_mode"]
CHE_DO: frozenset[str] = frozenset(get_args(CheDo))

_GHI_DUOC: frozenset[str] = frozenset({"editable", "amendment_mode"})


def kiem_che_do(che_do: object) -> CheDo:
    if not isinstance(che_do, str) or che_do not in CHE_DO:
        raise ValidationError(
            f"Chế độ phiếu {che_do!r} không hợp lệ — clinical shell phải truyền"
            " editable / finalized_locked / amendment_mode."
        )
    return che_do  # type: ignore[return-value]


def ghi_duoc(che_do: object) -> bool:
    return kiem_che_do(che_do) in _GHI_DUOC


def doi_ghi_duoc(che_do: object) -> None:
    if not ghi_duoc(che_do):
        raise ValidationError("Hồ sơ đã chốt — phiếu chỉ còn đọc.")


__all__ = ["CHE_DO", "CheDo", "doi_ghi_duoc", "ghi_duoc", "kiem_che_do"]
