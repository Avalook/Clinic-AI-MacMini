"""Quyền theo lịch, nửa "mở" (28/09/2026): "khách của tôi" ở Bàn khám khi không
chọn phòng — luật thuần `permissions.lich.khach_cua_toi`."""

from __future__ import annotations

from clinicai.permissions.lich import khach_cua_toi

TOI, BS1, BS2 = "toi", "bs1", "bs2"


def test_cung_phong_thay_khach_bac_si_phong_ay() -> None:
    # Thư ký / điều dưỡng xếp cùng phòng hai bác sĩ → khách của cả hai.
    assert khach_cua_toi(
        toi=TOI, la_bac_si=False, cung_phong=[BS2, BS1], kham_duoc=True
    ) == ([BS1, BS2], False)


def test_bac_si_cung_phong_thay_ca_khach_minh() -> None:
    assert khach_cua_toi(toi=TOI, la_bac_si=True, cung_phong=[BS1], kham_duoc=True) == (
        [BS1, TOI],
        False,
    )


def test_bac_si_khong_lich_thay_khach_cua_minh() -> None:
    assert khach_cua_toi(toi=TOI, la_bac_si=True, cung_phong=[], kham_duoc=True) == (
        [TOI],
        False,
    )


def test_chua_xep_lich_thi_mo_moi_bac_si() -> None:
    # Mở, không khoá: người chưa được xếp lịch vẫn làm được việc. Bản trước trả
    # "khách của chính tôi" = RỖNG cho thư ký có quyền Hoàn tất khám.
    assert khach_cua_toi(toi=TOI, la_bac_si=False, cung_phong=[], kham_duoc=True) == (
        [],
        True,
    )


def test_khong_lego_kham_khong_lich_thi_khong_ai() -> None:
    assert khach_cua_toi(toi=TOI, la_bac_si=False, cung_phong=[], kham_duoc=False) == (
        [],
        False,
    )
