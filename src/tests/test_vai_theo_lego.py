"""Vai theo lego đang bật (Tuyền chốt 26/09/2026 — "chỉ cần lego").

Các cửa còn hỏi VAI (require_role, co_vai) đọc vai suy từ lego bật ĐỦ: bật Bàn
khám là qua cửa bác sĩ; tắt thì mất, dù tài khoản là bác sĩ. Danh tính chưa tính
lego (None) giữ nguyên luật cũ.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from clinicai.api.identity import ClinicRole, StaffIdentity, dung_vai, require_role
from clinicai.permissions.catalogue import PRESET, VAI_DO_LEGO, vai_tu_lego

D = ClinicRole


def _nguoi(
    role: ClinicRole,
    lego: frozenset[ClinicRole] | None,
    vi_tri: frozenset[ClinicRole] = frozenset(),
) -> StaffIdentity:
    return StaffIdentity(
        staff_id="s1",
        auth_user_id="a1",
        full_name="Người thử",
        department=role.value,
        role=role,
        clinic_id="c1",
        location_id="l1",
        location_name="Kim Ngưu",
        vai_theo_vi_tri=vi_tri,
        vai_theo_lego=lego,
    )


@pytest.mark.parametrize(
    ("vai", "phai_co"),
    [
        ("DOCTOR", {"DOCTOR"}),
        ("RECEPTION", {"RECEPTION", "CSKH", "CASHIER", "CASHIER_DV", "CASHIER_THUOC"}),
        ("NURSE_ULTRASOUND", {"NURSE_ULTRASOUND"}),
        ("CASHIER", {"CASHIER", "CASHIER_DV", "CASHIER_THUOC", "CSKH"}),
        ("TRUONG_CA", {"TRUONG_CA", "RECEPTION", "CSKH"}),
        ("PHARMACIST", {"PHARMACIST", "CASHIER_THUOC"}),
        ("CSKH", {"CSKH"}),
    ],
)
def test_goi_mau_giu_vai_tai_khoan(vai: str, phai_co: set[str]) -> None:
    """Gói mẫu của mỗi vai do lego quyết phải bật đủ lego của CHÍNH vai ấy —
    không thì deploy xong người đó mất vai của mình."""
    ra = vai_tu_lego(PRESET[vai])
    assert vai in ra
    assert phai_co <= ra


def test_thu_ky_tron_quyen_qua_cua_bac_si() -> None:
    # 29/09/2026: ĐD/TKYK trọn quyền như bác sĩ (Tuyền) — gói mẫu có đủ Bàn khám.
    # "Ai là bác sĩ thật" (hai bác sĩ giành lượt, người ký) đọc membership.role,
    # không đọc vai suy từ lego (`services/bac_si_phu_trach.py`).
    assert "DOCTOR" in vai_tu_lego(PRESET["TKYK"])


def test_quan_ly_bat_ban_kham_la_qua_cua_bac_si() -> None:
    ra = vai_tu_lego(PRESET["MANAGEMENT"])
    assert "DOCTOR" in ra
    ql = _nguoi(D.MANAGEMENT, frozenset(D(v) for v in ra))
    assert ql.co_vai({D.DOCTOR}) and ql.co_vai({D.MANAGEMENT})
    qua = asyncio.run(require_role(D.DOCTOR)(ql))
    assert qua.role is D.DOCTOR and qua.vai_goc is D.MANAGEMENT


def test_bac_si_tat_lego_ban_kham_mat_cua_bac_si() -> None:
    bs = _nguoi(D.DOCTOR, frozenset())
    assert not bs.co_vai({D.DOCTOR})
    assert not bs.is_doctor()
    with pytest.raises(HTTPException) as loi:
        asyncio.run(require_role(D.DOCTOR)(bs))
    assert loi.value.status_code == 403


def test_vai_ngoai_lego_van_theo_tai_khoan() -> None:
    """Quản lý / Thư ký / BS siêu âm: chưa lego nào nói trọn việc — giữ vai."""
    for vai in (D.MANAGEMENT, D.TKYK, D.ULTRASOUND_DOCTOR):
        assert vai.value not in VAI_DO_LEGO
        assert _nguoi(vai, frozenset()).co_vai({vai})


def test_chua_tinh_lego_giu_luat_cu() -> None:
    bs = _nguoi(D.DOCTOR, None)
    assert bs.co_vai({D.DOCTOR})
    assert asyncio.run(require_role(D.DOCTOR)(bs)) is bs


def test_vi_tri_hom_nay_van_cap_vai_khi_lego_tat() -> None:
    """Lịch trực (đứng Lễ tân hôm nay) vẫn mở cửa Lễ tân — hai nguồn độc lập."""
    dd = _nguoi(D.NURSE_ULTRASOUND, frozenset(), vi_tri=frozenset({D.RECEPTION}))
    assert dd.co_vai({D.RECEPTION})
    assert not dd.co_vai({D.NURSE_ULTRASOUND})
    assert dung_vai(dd, {D.RECEPTION}).role is D.RECEPTION


def test_quan_ly_co_lego_ban_kham_mo_ho_so_van_ghi_nhat_ky() -> None:
    """Nhật ký "ai ngoài đội chuyên môn xem hồ sơ" xét VAI TÀI KHOẢN: quản lý
    bật lego Bàn khám vẫn bị ghi (mô phỏng K14, công tắc tắt, 26/09)."""
    from clinicai.api.identity import CLINICAL_WRITE_ROLES

    ql = _nguoi(D.MANAGEMENT, frozenset({D.DOCTOR}))
    assert ql.co_vai(CLINICAL_WRITE_ROLES), "qua cửa lâm sàng nhờ lego"
    assert ql.vai_goc not in CLINICAL_WRITE_ROLES, "nhưng vẫn ghi nhật ký mở hồ sơ"


def test_gia_bang_gia_khong_hien_kieu_khoa_hoc() -> None:
    """asyncpg trả Decimal('9.0E+5') — Bảng giá hiện nguyên "9.0E+5" (26/09)."""
    from decimal import Decimal

    from clinicai.services.config_service import _gia_thuong

    assert str(_gia_thuong(Decimal("9.0E+5"))) == "900000"
    assert str(_gia_thuong(Decimal("2.0E+5"))) == "200000"
    assert _gia_thuong(None) is None
