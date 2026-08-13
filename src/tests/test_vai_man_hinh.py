"""Vai DISPLAY — tài khoản của cái tivi phòng chờ — phải bị chặn ở khắp nơi.

Cái tivi đăng nhập một lần rồi bỏ đó cả ngày, ở nơi công cộng, không ai trông.
Nếu nó mang quyền của một nhân viên thì bất kỳ ai đứng cạnh chỉ cần mở một tab
mới là đọc được hồ sơ bệnh nhân.

Chốt được đặt ở `get_current_identity` chứ không phải ở một danh sách endpoint,
và bài kiểm này khẳng định đúng TÍNH CHẤT đó: chặn theo mặc định, mở theo ngoại
lệ — chứ không phải ngược lại.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    get_current_identity,
    get_display_identity,
)


def _ai_do(role: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="11111111-1111-4111-8111-111111111111",
        auth_user_id="22222222-2222-4222-8222-222222222222",
        full_name="Ai Đó",
        department=role.value,
        role=role,
        clinic_id="33333333-3333-4333-8333-333333333333",
        location_id="44444444-4444-4444-8444-444444444444",
        location_name="Kim Ngưu",
    )


def test_man_hinh_bi_tu_choi_o_cua_chung() -> None:
    """`get_current_identity` là cửa mà MỌI endpoint đi qua — có RoleGuard hay
    không. Chặn ở đây nghĩa là chặn ở khắp nơi mà không phải liệt kê chỗ nào.

    Bản kiểm kê 06/08 đếm được 26/119 endpoint chưa có RoleGuard; một danh sách
    cho phép sẽ bỏ sót đúng những chỗ ấy.
    """
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_identity(_ai_do(ClinicRole.DISPLAY)))
    assert e.value.status_code == 403


@pytest.mark.parametrize("role", [r for r in ClinicRole if r is not ClinicRole.DISPLAY])
def test_moi_vai_cua_nguoi_deu_qua_duoc_cua_chung(role: ClinicRole) -> None:
    """Chống xanh giả: nếu cửa chung từ chối tất cả thì bài trên vẫn xanh."""
    assert asyncio.run(get_current_identity(_ai_do(role))).role is role


def test_bang_goi_so_nhan_ca_man_hinh_lan_nhan_vien() -> None:
    for role in (ClinicRole.DISPLAY, ClinicRole.RECEPTION):
        assert asyncio.run(get_display_identity(_ai_do(role))).role is role


# Mỗi đường mở cho vai DISPLAY phải có lý do vì sao nó KHÔNG lộ dữ liệu người
# bệnh. Danh sách này cố ý ngắn và cố ý khó thêm.
DUONG_MO_CHO_MAN_HINH = {
    "/api/v1/display/queue": (
        "Bảng gọi số: chỉ số thứ tự, khu vực, thứ tự gọi. Không tên, không mã "
        "bệnh nhân, không số điện thoại, không cả tên bác sĩ."
    ),
    "/api/v1/me": (
        "Chỉ mô tả CHÍNH người gọi. Layout hỏi đường này để biết mình là ai rồi "
        "mới đưa tài khoản màn hình sang /display — chặn ở đây thì cái tivi "
        "đăng nhập xong bị đá ngược về trang đăng nhập."
    ),
}


def test_chi_dung_mot_duong_mo_cho_man_hinh() -> None:
    """`get_display_identity` cố tình dễ dãi, nên phải hiếm.

    Gắn nó vào một endpoint có trả dữ liệu bệnh nhân là mở toang chính cái cửa
    vừa khoá — bài này bắt lỗi ấy ngay lúc thêm, không phải lúc rò.
    """
    from clinicai.main import app

    duong = []
    for route in app.routes:
        deps = getattr(getattr(route, "dependant", None), "dependencies", [])
        ten = [getattr(d.call, "__name__", "") for d in deps]
        if "get_display_identity" in ten:
            duong.append(getattr(route, "path", "?"))

    assert sorted(duong) == sorted(DUONG_MO_CHO_MAN_HINH), (
        "Có đường mới dùng get_display_identity. Đường đó KHÔNG được trả về bất "
        "kỳ mẩu dữ liệu nào của NGƯỜI BỆNH — nếu đúng vậy thì thêm nó vào "
        f"DUONG_MO_CHO_MAN_HINH kèm lý do. Hiện có: {sorted(duong)}"
    )
