"""LUẬT CHẶN BẰNG CODE — chạy TRƯỚC khi gọi model, không phụ thuộc model nào.

Prompt bảo model "đừng tư vấn y khoa" là lớp thứ hai; model đổi, prompt đổi,
model nhỏ lờ đi — lớp này thì không. Tin khẩn mà để model quyết là đặt an toàn
của khách vào xác suất. Thà chuyển nhầm một tin cho người đọc còn hơn bỏ sót.

So khớp trên chữ ĐÃ BỎ DẤU, vì khách nhắn Zalo phần lớn không dấu.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

LoaiChan = Literal["khan_cap", "y_khoa"]


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", s).strip()


#: Triệu chứng phải có người gọi lại NGAY. Phụ khoa/sản: "ra máu" bất kỳ cũng
#: chuyển người — AI không phân biệt được rong kinh với dọa sảy.
_KHAN_CAP = (
    "ra mau",
    "chay mau",
    "bang huyet",
    "mat mau",
    "dau bung du doi",
    "dau du doi",
    "dau qua troi",
    "dau khong chiu",
    # "xiu" trần KHÔNG được: bỏ dấu thì "chờ em xíu" cũng khớp.
    "ngat",
    "ngat xiu",
    "bi xiu",
    "bat tinh",
    "choang",
    "kho tho",
    "sot cao",
    "co giat",
    "vo oi",
    "ri oi",
    "thai ngoai tu cung",
    "thai khong may",
    # "tu tu" trần = "từ từ" khi bỏ dấu — phải đi kèm động từ.
    "muon tu tu",
    "tu sat",
    "muon chet",
)

#: Câu hỏi cần bác sĩ: chẩn đoán, thuốc, liều, đọc kết quả. Không có "có sao
#: không" (đến trễ có sao không…) hay "chi so" (= "chị số điện thoại") — quá
#: đời thường, để lớp prompt lo.
_Y_KHOA = (
    "uong thuoc gi",
    "dung thuoc gi",
    "thuoc gi",
    "lieu dung",
    "lieu luong",
    "uong may vien",
    "uong bao nhieu vien",
    "co nguy hiem",
    "bi benh gi",
    "bi lam sao",
    "chan doan",
    "ket qua xet nghiem",
    "ket qua sieu am",
    "doc ket qua",
    "co thai khong",
    "co bau khong",
    "bi ung thu",
    "khang sinh",
    "thuoc tranh thai",
    "thuoc phu khoa",
)


def _mau(cum: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(re.escape(c) for c in cum) + r")\b")


_MAU_KHAN = _mau(_KHAN_CAP)
_MAU_Y_KHOA = _mau(_Y_KHOA)

CAU_KHAN_CAP = (
    "Dạ, triệu chứng chị kể cần được bác sĩ xem ngay ạ. Em đã báo nhân viên gọi lại "
    "cho chị liền. Nếu chị đang ra máu nhiều, đau dữ dội, khó thở hay choáng ngất, "
    "chị gọi 115 hoặc tới cơ sở y tế gần nhất ngay nhé."
)
CAU_Y_KHOA = (
    "Dạ, câu này cần bác sĩ trả lời mới chính xác ạ. Em chuyển cho nhân viên để "
    "sắp xếp bác sĩ tư vấn cho chị nhé."
)


@dataclass(frozen=True)
class Chan:
    loai: LoaiChan
    tu_khoa: str
    cau_tra_loi: str


def kiem_tra(tin: str) -> Chan | None:
    """Khẩn xét trước y khoa: "ra máu có sao không" là KHẨN, không phải hỏi."""
    chu = bo_dau(tin)
    if m := _MAU_KHAN.search(chu):
        return Chan("khan_cap", m.group(0), CAU_KHAN_CAP)
    if m := _MAU_Y_KHOA.search(chu):
        return Chan("y_khoa", m.group(0), CAU_Y_KHOA)
    return None


__all__ = ["CAU_KHAN_CAP", "CAU_Y_KHOA", "Chan", "bo_dau", "kiem_tra"]
