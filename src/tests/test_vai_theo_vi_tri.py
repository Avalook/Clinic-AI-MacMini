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


# ── S0-7 (18/09/2026): vai theo lịch chỉ khi ca ĐÃ DUYỆT và ĐANG TRONG GIỜ CA ──
#
# Trước đó mọi dòng lịch hôm nay trừ REJECTED đều cấp vai, CẢ NGÀY: điều dưỡng
# xếp ca SÁNG ở Lễ tân vẫn cầm vai lễ tân lúc 20:00, và một dòng PENDING chưa ai
# duyệt cũng cấp quyền. Cửa gác và thanh bên phải dùng CHUNG một bộ lọc.

from clinicai.api.identity import (  # noqa: E402
    an_han_ca_tu_settings,
    doc_vi_tri_hien_hanh,
    vi_tri_dang_trong_ca,
)

_9H, _13H, _14H30, _20H = 9 * 60, 13 * 60, 14 * 60 + 30, 20 * 60

#: Luật theo ca BẬT. Mặc định TẮT (HOLD_FOR_PROD 18/09/2026): lịch prod ngày
#: thường chỉ có ca tối trong khi phòng khám mở 07–22, chưa đủ chắc để bật.
_BAT = {"vai_lich_theo_ca": True}


def test_mac_dinh_tat_giu_nguyen_hanh_vi_cu() -> None:
    """Tắt: mọi dòng trừ REJECTED cấp vai CẢ NGÀY — y như trước S0-7."""
    dong = [
        ("T1_LETAN", "SANG", "APPROVED"),
        ("T1_THUNGAN", "TOI", "PENDING"),
        ("DIEU_PHOI", "CHIEU", "REJECTED"),
    ]
    for settings in (None, {}, {"vai_lich_theo_ca": False}):
        assert vi_tri_dang_trong_ca(dong, _20H, settings) == [
            ("T1_LETAN", "SANG"),
            ("T1_THUNGAN", "TOI"),
        ]


@pytest.mark.parametrize("rac", ["true", 1, "1", None, [True]])
def test_cong_tac_chi_bat_khi_dung_true(rac: object) -> None:
    dong = [("T1_LETAN", "SANG", "APPROVED")]
    assert vi_tri_dang_trong_ca(dong, _20H, {"vai_lich_theo_ca": rac}) == [
        ("T1_LETAN", "SANG")
    ]
    assert vi_tri_dang_trong_ca(dong, _20H, '{"vai_lich_theo_ca": true}') == []


def test_chi_dong_da_duyet_moi_cap_vi_tri() -> None:
    dong = [("T1_LETAN", "SANG", "PENDING"), ("T1_THUNGAN", "SANG", "APPROVED")]
    assert vi_tri_dang_trong_ca(dong, _9H, _BAT) == [("T1_THUNGAN", "SANG")]


def test_het_ca_la_het_vai() -> None:
    dong = [("T1_LETAN", "SANG", "APPROVED")]
    assert vi_tri_dang_trong_ca(dong, _9H, _BAT) == [("T1_LETAN", "SANG")]
    assert vi_tri_dang_trong_ca(dong, _14H30, _BAT) == []
    assert vi_tri_dang_trong_ca(dong, _20H, _BAT) == []
    # Nửa mở [lo, hi): đúng 13:00 là đã hết ca sáng — ân hạn mặc định 0.
    assert vi_tri_dang_trong_ca(dong, _13H, _BAT) == []


def test_nhieu_ca_trong_ngay_chi_ca_dang_dien_ra() -> None:
    dong = [
        ("T1_LETAN", "SANG", "APPROVED"),
        ("T4_SAN_DD", "CHIEU", "APPROVED"),
        ("DIEU_PHOI", "FULL", "APPROVED"),
    ]
    assert vi_tri_dang_trong_ca(dong, _14H30, _BAT) == [
        ("T4_SAN_DD", "CHIEU"),
        ("DIEU_PHOI", "FULL"),
    ]


def test_an_han_cau_hinh_duoc_hai_dau_ca() -> None:
    settings = {**_BAT, "vai_lich_an_han_phut": 15}
    dong = [("T1_LETAN", "SANG", "APPROVED")]
    assert vi_tri_dang_trong_ca(dong, _13H + 10, settings) == [("T1_LETAN", "SANG")]
    assert vi_tri_dang_trong_ca(dong, _13H + 15, settings) == []
    assert vi_tri_dang_trong_ca(dong, 8 * 60 - 10, settings) == [("T1_LETAN", "SANG")]


def test_gio_ca_theo_cau_hinh_phong_kham() -> None:
    settings = {
        **_BAT,
        "ca_lam_viec": {"SANG": {"bat_dau": "07:00", "ket_thuc": "12:00"}},
    }
    dong = [("T1_LETAN", "SANG", "APPROVED")]
    assert vi_tri_dang_trong_ca(dong, 7 * 60 + 5, settings) == [("T1_LETAN", "SANG")]
    assert vi_tri_dang_trong_ca(dong, 12 * 60 + 30, settings) == []


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "abc",
        {},
        {"vai_lich_an_han_phut": "x"},
        {"vai_lich_an_han_phut": -5},
        {"vai_lich_an_han_phut": 1000},
        {"vai_lich_an_han_phut": True},
        '{"hong"',
    ],
)
def test_an_han_rac_ve_0_khong_nem(raw: object) -> None:
    assert an_han_ca_tu_settings(raw) == 0


def test_an_han_doc_duoc_ca_chuoi_json() -> None:
    assert an_han_ca_tu_settings('{"vai_lich_an_han_phut": 10}') == 10


def test_doc_vi_tri_hien_hanh_loc_trong_sql_va_theo_gio() -> None:
    from datetime import date

    from tests.services.fake_pool import FakePool

    settings = {**_BAT, "vai_lich_an_han_phut": 0}
    pool = FakePool(
        [
            {
                "station": "T1_LETAN",
                "shift": "SANG",
                "status": "APPROVED",
                "settings": settings,
            },
            {
                "station": "T4_SAN_DD",
                "shift": "CHIEU",
                "status": "APPROVED",
                "settings": settings,
            },
        ]
    )
    ket = asyncio.run(
        doc_vi_tri_hien_hanh(pool, "c1", "s1", hom_nay=date(2026, 9, 18), phut=_9H)
    )
    assert ket == [("T1_LETAN", "SANG")]
    sql = pool.queries("fetch")[0]
    assert "w.status <> 'REJECTED'" in sql and "w.clinic_id = $1::uuid" in sql


def test_cua_gac_va_thanh_ben_dung_chung_mot_bo_loc() -> None:
    """Hai bản lọc là hai cơ hội lệch nhau: thanh bên mời vào màn mà cửa gác 403."""
    import inspect

    from clinicai.api import identity as id_mod
    from clinicai.api.v1.routers import identity as router_mod

    assert "doc_vi_tri_hien_hanh(" in inspect.getsource(id_mod._resolve_identity)
    assert "doc_vi_tri_hien_hanh(" in inspect.getsource(router_mod.vi_tri_hom_nay)
    assert "work_roster" not in inspect.getsource(router_mod.vi_tri_hom_nay)
    assert "work_roster" not in inspect.getsource(id_mod._resolve_identity)
