"""Mọi câu SQL viết tay trong service phải đúng cú pháp.

VÌ SAO CÓ BÀI NÀY. Ngày 08/08/2026 tôi sửa hai câu SQL trong
`booking_service` và `capacity_service` bằng cách nối chuỗi, và nối hụt:
`AND AND status = 'APPROVED'`. Bốn chỗ.

Không lớp kiểm nào bắt được. ruff và mypy nhìn nó là một chuỗi Python hợp lệ.
Các bài canh SQL chạy trên database thật nhưng không chạy mã Python. Các bài
pytest chạy mã Python nhưng câu SQL này chỉ nổ khi có kết nối database, mà
những bài ấy bị bỏ qua trên CI (`-m "not db"`).

Nên nó vào tới bản thật, và **mọi lượt đặt lịch có bác sĩ trả về 500** — đúng
việc chính của phòng khám. Phát hiện tình cờ khi thử một tính năng khác.

CÁCH BẮT: đọc mọi chuỗi SQL trong `src/clinicai/services`, thay tham số
`$1, $2…` bằng NULL rồi đưa cho `sqlparse`… không — dự án không có bộ phân tích
SQL. Thay vào đó dùng phép kiểm rẻ mà đủ mạnh cho đúng lớp lỗi này: những cặp
từ khoá không bao giờ đứng cạnh nhau trong SQL hợp lệ.

Phép kiểm này KHÔNG thay thế được việc chạy thật. Nó chỉ chặn đúng cái bẫy đã
sập một lần — nối chuỗi hụt — và chặn rẻ, ở mọi lần chạy CI.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_THU_MUC = Path(__file__).resolve().parents[3] / "src" / "clinicai"

#: Cặp từ khoá không bao giờ hợp lệ khi đứng liền nhau. Danh sách ngắn và chắc
#: chắn, không cố bắt mọi lỗi cú pháp — bắt nhầm một câu SQL đúng sẽ khiến người
#: sau nới lỏng bài kiểm thay vì đọc nó.
_CAP_SAI = (
    r"\bAND\s+AND\b",
    r"\bOR\s+OR\b",
    r"\bWHERE\s+AND\b",
    r"\bWHERE\s+OR\b",
    r"\bSELECT\s+FROM\b",
    r"\bFROM\s+WHERE\b",
    r"\bAND\s+\)",
    r",\s*FROM\b",
    r",\s*\)",
)


def _moi_file_python() -> list[Path]:
    return sorted(_THU_MUC.rglob("*.py"))


@pytest.mark.parametrize("mau", _CAP_SAI)
def test_khong_co_cap_tu_khoa_sai(mau: str) -> None:
    # PHÂN BIỆT HOA THƯỜNG. SQL trong dự án này viết từ khoá bằng chữ hoa, còn
    # chú thích tiếng Anh thì không — bản đầu của bài kiểm dùng IGNORECASE và
    # bắt nhầm dòng "recent failures, from the API process's ring buffer".
    # Một bài kiểm hay báo động nhầm là một bài kiểm sẽ bị nới cho im.
    bat = re.compile(mau)
    loi: list[str] = []
    for f in _moi_file_python():
        noi_dung = f.read_text(encoding="utf-8")
        for so_dong, dong in enumerate(noi_dung.splitlines(), 1):
            if bat.search(dong):
                ten = f.relative_to(_THU_MUC.parent.parent)
                loi.append(f"{ten}:{so_dong}: {dong.strip()}")
    assert not loi, (
        f"Câu SQL viết tay có cặp từ khoá không hợp lệ ({mau}). Đây gần như luôn "
        "là nối chuỗi hụt, và nó chỉ nổ khi có kết nối database — tức là trên "
        "bản thật.\n  " + "\n  ".join(loi)
    )
