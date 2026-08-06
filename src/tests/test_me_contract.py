"""GET /api/v1/me trả về đúng bộ trường mà dashboard dựng phiên làm việc từ đó.

VÌ SAO CÓ FILE NÀY. Dashboard bỏ truy vấn danh tính của riêng nó và nay hỏi
``/api/v1/me`` — nghĩa là hình dạng phản hồi ấy đã thành GIAO KÈO giữa hai ngôn
ngữ, và không bên nào biên dịch bên kia. Bỏ một khoá ở Python không làm gãy gì
cả: TypeScript vẫn biên dịch sạch, trang vẫn dựng, chỉ có thanh đầu trang mất
tên phòng khám và không ai để ý cho tới khi lễ tân đặt lịch nhầm cơ sở.

Cùng loại chốt với ``test_dashboard_backend_paths.py``, chỉ khác chỗ nó canh
ĐƯỜNG DẪN còn file này canh CÁC TRƯỜNG.

GIỚI HẠN, nói rõ thay vì để người sau tự phát hiện: chỉ so TÊN trường, không so
kiểu. ``clinic_id`` đổi từ chuỗi sang object thì test này vẫn xanh.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.identity import me

# src/tests/ -> src/ -> src/dashboard
DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard"
CURRENT_STAFF = DASHBOARD / "lib" / "current-staff.ts"

EXPECTED_KEYS = {
    "staff_id",
    "auth_user_id",
    "full_name",
    "short_name",
    "department",
    "role",
    "clinic_id",
    "clinic_name",
    "location_id",
    "location_name",
    "can_write_clinical",
    "is_doctor",
    "is_cashier",
}


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="staff-9",
        auth_user_id="u-1",
        full_name="TS.BS. Phan Chí Thành",
        department="DOCTOR",
        role=ClinicRole.DOCTOR,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
        short_name="BS Thành",
        clinic_name="Phòng khám Dr4Women",
    )


def test_me_returns_the_whole_session_the_dashboard_renders_from() -> None:
    payload = asyncio.run(me(_identity()))

    assert set(payload) == EXPECTED_KEYS
    # Vai đi ra dạng chuỗi mã, không phải đối tượng Enum — phía kia là JSON.
    assert payload["role"] == "DOCTOR"
    assert payload["can_write_clinical"] is True
    assert payload["is_cashier"] is False
    # Tên phòng khám + cơ sở là MỘT sự thật hai nửa; thiếu nửa nào thì thanh đầu
    # trang cũng không nói được người dùng đang đứng ở đâu.
    assert payload["clinic_name"] == "Phòng khám Dr4Women"
    assert payload["location_name"] == "Kim Ngưu"


def test_dashboard_me_interface_matches_the_endpoint() -> None:
    """Khai báo MeResponse bên TypeScript phải trùng khít bộ khoá trên."""
    src = CURRENT_STAFF.read_text(encoding="utf-8")
    block = re.search(r"interface MeResponse \{(.*?)\n\}", src, re.S)
    assert block is not None, (
        f"không tìm thấy `interface MeResponse` trong {CURRENT_STAFF} — "
        "dashboard đã đổi cách khai báo và chốt này đang gác rỗng."
    )

    fields = set(re.findall(r"^\s*(\w+)\??:", block.group(1), re.M))
    assert fields == EXPECTED_KEYS, (
        "MeResponse (TypeScript) lệch với phản hồi /api/v1/me (Python).\n"
        f"  chỉ có ở TypeScript: {sorted(fields - EXPECTED_KEYS)}\n"
        f"  chỉ có ở Python    : {sorted(EXPECTED_KEYS - fields)}"
    )
