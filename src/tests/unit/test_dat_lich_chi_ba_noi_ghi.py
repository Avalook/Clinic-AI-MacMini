"""Bài canh: chỉ có ĐÚNG ba nơi ghi `appointment` (Tuyền chốt 15/10/2026).

Việc "Gọi xác nhận lịch" (`v_viec_cskh`, nhánh CHO_XAC_NHAN, migration
20261015110000) coi MỌI lịch trừ kênh `WALK_IN` là lịch do nhân viên đặt hộ — vì
bảng `appointment` không có cột người đặt và hiện chưa có cổng khách tự đặt. Giả
định ấy chỉ đúng chừng nào mọi đường ghi lịch còn là nhân viên đăng nhập.

Thêm một đường ghi lịch mới (nhất là cổng khách tự đặt, bot Zalo, nhập từ ngoài)
thì bài này đỏ: cần quyết có cột nguồn đặt (phương án B) không, rồi lọc view theo
cột ấy — đừng chỉ thêm tên tệp vào danh sách.
"""

from __future__ import annotations

import re
from pathlib import Path

GOC = Path(__file__).resolve().parents[2] / "clinicai"

#: Ba nơi ghi lịch được duyệt: nhân viên đặt (booking_service), tự xếp/đổi lịch
#: (scheduling_service), chuyển lượt thật từ nhập Notion (chuyen_luot_that).
NOI_DUOC_GHI = {
    "services/booking_service.py",
    "services/scheduling_service.py",
    "services/chuyen_luot_that.py",
}

#: `appointment` đứng riêng (không phải appointment_doi_lich, appointment_xxx).
_GHI_LICH = re.compile(r"\binsert\s+into\s+(?:public\.)?appointment\b", re.IGNORECASE)


def _noi_ghi_lich() -> set[str]:
    return {
        str(p.relative_to(GOC))
        for p in GOC.rglob("*.py")
        if _GHI_LICH.search(p.read_text(encoding="utf-8"))
    }


def test_chi_ba_noi_ghi_appointment() -> None:
    thuc_te = _noi_ghi_lich()
    them = thuc_te - NOI_DUOC_GHI
    assert not them, (
        f"Có đường ghi lịch MỚI ở {sorted(them)}: cần quyết có cột nguồn đặt "
        "(phương án B: người đặt/nguồn đặt trên bảng appointment) không. Việc "
        "CHO_XAC_NHAN đang coi mọi lịch trừ kênh WALK_IN là đặt hộ — xem "
        "migration 20261015110000 và docs/BAN-DO-SUA.md §12."
    )
    mat = NOI_DUOC_GHI - thuc_te
    assert not mat, (
        f"{sorted(mat)} không còn ghi appointment — cập nhật NOI_DUOC_GHI (và "
        "kiểm lại giả định 'mọi lịch là nhân viên đặt') rồi mới sửa bài này."
    )
