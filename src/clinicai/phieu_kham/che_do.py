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

Cuối tệp: `che_do_khoi1` — khối 1 vẽ gì theo loại khám của lượt.
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


# ---------------------------------------------------------------------------
# KHỐI 1 theo loại lượt (Tuyền chốt 09/10/2026). Khác ba chế độ trên: đây là
# LOẠI KHÁM của lượt quyết khối 1 "Thông tin cơ bản" vẽ gì; khối 2–4 không đổi.
#   DIEU_TRI   lượt Điều trị (6 loại DT_*): phiếu cảm nhận + liệu trình + làm
#              tại bàn khám thay mục A/B.
#   THU_THUAT  lượt Thủ thuật: chọn thủ thuật đã làm (làm luôn tại bàn khám)
#              trên đầu; mục B (ô chữ tự do của phiếu thủ thuật) vẫn ở dưới.
#   None       sáu loại khám có phiếu riêng, Sàn chậu, Khác — như cũ.
# ---------------------------------------------------------------------------

Khoi1 = Literal["DIEU_TRI", "THU_THUAT"]
KHOI1_DIEU_TRI: Khoi1 = "DIEU_TRI"
KHOI1_THU_THUAT: Khoi1 = "THU_THUAT"


def che_do_khoi1(nhom: object, form_code: object) -> Khoi1 | None:
    """Khối 1 của hồ sơ khám theo loại khám của lượt — hàm thuần, không ném.

    ``nhom`` = ``service_type.nhom``; ``form_code`` = phiếu gắn với loại khám.
    Điều trị thắng (nhóm là nguồn chuẩn); giá trị lạ / thiếu → None (như cũ)."""
    if nhom == "DIEU_TRI":
        return KHOI1_DIEU_TRI
    if form_code == "THU_THUAT":
        return KHOI1_THU_THUAT
    return None


__all__ = [
    "CHE_DO",
    "KHOI1_DIEU_TRI",
    "KHOI1_THU_THUAT",
    "CheDo",
    "Khoi1",
    "che_do_khoi1",
    "doi_ghi_duoc",
    "ghi_duoc",
    "kiem_che_do",
]
