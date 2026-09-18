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


#: HAI vai bị cửa chung từ chối, vì cùng một lý do: chúng không phải NHÂN VIÊN
#: PHÒNG KHÁM. `DISPLAY` là cái tivi treo tường; `PARTNER` là người ngoài gửi
#: kết quả vào. Cả hai chỉ đi qua đúng một cửa riêng của mình.
BI_TU_CHOI_O_CUA_CHUNG = (ClinicRole.DISPLAY, ClinicRole.PARTNER)


@pytest.mark.parametrize("role", list(BI_TU_CHOI_O_CUA_CHUNG))
def test_vai_ngoai_phong_kham_bi_chan_o_cua_chung(role: ClinicRole) -> None:
    """Chặn ở cửa chung = chặn ở khắp nơi mà không phải liệt kê chỗ nào."""
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_current_identity(_ai_do(role)))
    assert e.value.status_code == 403


@pytest.mark.parametrize(
    "role", [r for r in ClinicRole if r not in BI_TU_CHOI_O_CUA_CHUNG]
)
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


def test_cua_mo_cho_vai_ngoai_luong_khong_nam_sau_bo_dem_chan_vai() -> None:
    """Bộ đếm ở TẦNG ROUTER không được từ chối chính vai mà endpoint mở cho.

    LỖI NÀY ĐÃ CẮN HAI LẦN, và lần thứ hai xảy ra dù chú thích cảnh báo đã nằm
    sẵn trong `runaway_guard.py`:

      • 09/2026 — `/api/v1/me` khai `get_display_identity`, nhưng router gắn
        `runaway_guard`, mà hàm ấy nhận danh tính qua `get_current_identity` —
        chính hàm TỪ CHỐI vai DISPLAY. Cái tivi đăng nhập xong bị đá về
        trang đăng nhập.
      • 16/09/2026 — `/doi-tac/viec` khai `get_partner_identity`, router gắn
        `_GUARDED`, và đối tác ăn 403 ngay tại cửa của chính mình.

    Cả hai lần đều RẤT KHÓ LẦN RA: mã của endpoint trông hoàn toàn đúng, thứ từ
    chối nằm ở tham số mặc định của một dependency khai ở tệp khác. Không bài
    kiểm nào bắt được, vì các bài kiểm khác đều ghi đè `get_current_identity`.

    Nên bài này không gọi HTTP mà đọc thẳng cây phụ thuộc của từng route.
    """
    from fastapi.dependencies.models import Dependant

    from clinicai.main import app

    def moi_ham(d: Dependant) -> set[str]:
        ten = {getattr(d.call, "__name__", "")}
        for con in d.dependencies:
            ten |= moi_ham(con)
        return ten

    mo_cho_vai_ngoai = {"get_display_identity", "get_partner_identity"}
    hong: list[str] = []
    for route in app.routes:
        dep = getattr(route, "dependant", None)
        if dep is None:
            continue
        ten = moi_ham(dep)
        if (ten & mo_cho_vai_ngoai) and "get_current_identity" in ten:
            hong.append(getattr(route, "path", "?"))

    assert not hong, (
        "Những đường sau mở cho vai ngoài luồng (DISPLAY / PARTNER) nhưng vẫn "
        "nằm sau `get_current_identity` — hàm TỪ CHỐI đúng hai vai ấy, nên "
        f"endpoint trả 403 dù mã của nó đúng: {sorted(hong)}. Router của chúng "
        "phải gắn `runaway_guard_khong_chan_vai` thay cho `_GUARDED`."
    )
