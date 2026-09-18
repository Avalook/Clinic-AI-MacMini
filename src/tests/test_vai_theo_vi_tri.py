"""Vai theo vị trí hôm nay (Tuyền chốt 16/09/2026).

Lịch cấp quyền VẬN HÀNH cho người đứng vị trí, không bao giờ cấp quyền bác sĩ.
Đo thật trên final cloud trước khi sửa: tài khoản Điều dưỡng đứng Lễ tân + Thu
ngân bị 403 ở thu ngân, check-out, đặt lịch, kho thuốc, bảng giá.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from clinicai.api.identity import (
    VAI_KHONG_CAP_QUA_LICH,
    VAI_THEO_VI_TRI,
    ClinicRole,
    StaffIdentity,
    require_role,
    require_role_co_the_mo,
    vai_tu_vi_tri,
)


def _nguoi(role: ClinicRole, vai: frozenset[ClinicRole] = frozenset()) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="a1",
        full_name="Phùng Thị Minh Thư",
        department=role.value,
        role=role,
        clinic_id="c1",
        location_id="l1",
        location_name="Kim Ngưu",
        vai_theo_vi_tri=vai,
    )


def test_dieu_duong_dung_le_tan_duoc_vai_le_tan() -> None:
    assert vai_tu_vi_tri(["T1_LETAN", "T1_THUNGAN"], ClinicRole.NURSE_ULTRASOUND) == {
        ClinicRole.RECEPTION
    }


def test_lich_khong_bao_gio_cap_vai_bac_si() -> None:
    assert not (set(VAI_THEO_VI_TRI.values()) & VAI_KHONG_CAP_QUA_LICH)
    # Kể cả vị trí bác sĩ, thư ký — không có trong bảng nên không cấp gì.
    assert (
        vai_tu_vi_tri(
            ["T1_BS_NOITIET", "T1_SA_BS", "T1_TKYK", "T4_SAN_BS"], ClinicRole.RECEPTION
        )
        == frozenset()
    )


def test_doi_tac_va_tivi_khong_duoc_cap_gi() -> None:
    for vai in (ClinicRole.PARTNER, ClinicRole.DISPLAY):
        assert vai_tu_vi_tri(["T1_LETAN"], vai) == frozenset()


def test_cua_gac_cho_qua_duoi_vai_cua_vi_tri() -> None:
    guard = require_role(ClinicRole.RECEPTION, ClinicRole.MANAGEMENT)
    ra = asyncio.run(
        guard(_nguoi(ClinicRole.NURSE_ULTRASOUND, frozenset({ClinicRole.RECEPTION})))
    )
    # Vai được THAY để kiểm tra phía sau (loại thanh toán…) đọc đúng.
    assert ra.role is ClinicRole.RECEPTION


def test_khong_co_vi_tri_thi_van_403() -> None:
    guard = require_role(ClinicRole.RECEPTION)
    with pytest.raises(HTTPException) as e:
        asyncio.run(guard(_nguoi(ClinicRole.NURSE_ULTRASOUND)))
    assert e.value.status_code == 403


def test_cua_bac_si_khong_mo_qua_lich() -> None:
    guard = require_role(ClinicRole.DOCTOR)
    with pytest.raises(HTTPException):
        asyncio.run(
            guard(
                _nguoi(ClinicRole.RECEPTION, frozenset({ClinicRole.NURSE_ULTRASOUND}))
            )
        )


def test_cua_co_the_mo_cung_uu_tien_vai_theo_vi_tri() -> None:
    guard = require_role_co_the_mo(ClinicRole.RECEPTION)
    ra = asyncio.run(
        guard(_nguoi(ClinicRole.NURSE_ULTRASOUND, frozenset({ClinicRole.RECEPTION})))
    )
    assert ra.role is ClinicRole.RECEPTION


def test_thay_vai_thi_giu_vai_tai_khoan_de_ghi_nhat_ky() -> None:
    guard = require_role(ClinicRole.RECEPTION)
    ra = asyncio.run(
        guard(_nguoi(ClinicRole.NURSE_ULTRASOUND, frozenset({ClinicRole.RECEPTION})))
    )
    assert ra.role is ClinicRole.RECEPTION
    assert ra.vai_tai_khoan is ClinicRole.NURSE_ULTRASOUND


def test_vai_theo_thu_tu_le_tan_tren_dieu_duong_duoi() -> None:
    """Tuyền 17/09/2026: một người hai vai → Lễ tân ở trên, Điều dưỡng ở dưới —
    kể cả khi vai Lễ tân trùng vai tài khoản, và khi lịch ghi mã đời cũ."""
    from clinicai.api.identity import vai_theo_thu_tu

    assert vai_theo_thu_tu(
        ["T1_LAYMAU", "T1_LETAN", "T1_DOCHISO"], ClinicRole.CSKH
    ) == ["RECEPTION", "NURSE_ULTRASOUND"]
    # Phương Anh 17/09: tài khoản Lễ tân, lịch Lấy mẫu (mã mới) + LE_TAN (mã cũ).
    assert vai_theo_thu_tu(["T1_LAYMAU", "LE_TAN"], ClinicRole.RECEPTION) == [
        "RECEPTION",
        "NURSE_ULTRASOUND",
    ]
    assert vai_theo_thu_tu(["LE_TAN"], ClinicRole.PARTNER) == []


def test_dieu_duong_dung_le_tan_check_in_duoc_o_tang_nghiep_vu() -> None:
    """Lỗi thật 16/09: cửa gác để tài khoản điều dưỡng đi qua (công tắc mở quyền)
    nên không đổi vai, rồi booking_service so `identity.role` và từ chối
    'checkin'. Nghiệp vụ phải hỏi `co_vai`, không so vai tài khoản."""
    from clinicai.services.booking_service import CHECKIN_ROLES

    minh_thu = _nguoi(ClinicRole.NURSE_ULTRASOUND, frozenset({ClinicRole.RECEPTION}))
    assert minh_thu.co_vai(CHECKIN_ROLES)
    assert not _nguoi(ClinicRole.NURSE_ULTRASOUND).co_vai(CHECKIN_ROLES)


def test_nghiep_vu_khong_so_vai_tai_khoan_truc_tiep() -> None:
    """Cấm `identity.role in/==/!=` trong services và routers — dùng `co_vai`."""
    import re
    from pathlib import Path

    goc = Path(__file__).resolve().parents[1] / "clinicai"
    mau = re.compile(r"identity\.role\s+(?:not\s+in|in|==|!=|is\s+not|is)\b")
    vi_pham = [
        f"{p.relative_to(goc)}:{i}"
        for p in [*goc.glob("services/*.py"), *goc.glob("api/v1/routers/*.py")]
        for i, dong in enumerate(p.read_text().splitlines(), 1)
        if mau.search(dong)
    ]
    assert vi_pham == [], "so vai tài khoản trực tiếp: " + ", ".join(vi_pham)
