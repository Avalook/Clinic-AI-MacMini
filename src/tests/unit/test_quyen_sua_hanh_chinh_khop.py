"""Nút "Sửa thông tin" hiện đúng người mà máy chủ cho Lưu.

Lỗi thật (11/11/2026): `/customers` hiện khối sửa hồ sơ cho cả người chỉ có
`booking.create`, trong khi `PATCH /patients` (`_PATIENT_EDIT_GUARD`) không nhận
quyền đó → bấm Lưu bị 403. Giờ giao diện dùng MỘT danh sách
`QUYEN_SUA_HANH_CHINH` (lib/quyen-cua-toi.ts); test này canh nó không lệch máy
chủ và hai màn có khối sửa đều gác bằng nó.
"""

from __future__ import annotations

import re
from pathlib import Path

from clinicai.api.v1.patients import _PATIENT_EDIT_GUARD

DASH = Path(__file__).resolve().parents[2] / "dashboard"
QUYEN_TS = DASH / "lib" / "quyen-cua-toi.ts"
KHACH = DASH / "app" / "(dashboard)" / "customers"
DS_BN = DASH / "app" / "(dashboard)" / "patient-list" / "page.tsx"


def _quyen_giao_dien() -> set[str]:
    nguon = QUYEN_TS.read_text(encoding="utf-8")
    khoi = re.search(r"QUYEN_SUA_HANH_CHINH = \[(.*?)\] as const", nguon, re.S)
    assert khoi, "không thấy QUYEN_SUA_HANH_CHINH trong lib/quyen-cua-toi.ts"
    return set(re.findall(r'"([^"]+)"', khoi.group(1)))


def test_danh_sach_giao_dien_khop_cua_may_chu() -> None:
    assert _quyen_giao_dien() == set(getattr(_PATIENT_EDIT_GUARD, "quyen"))


def test_quyen_dat_lich_khong_mo_khoi_sua() -> None:
    assert "booking.create" not in _quyen_giao_dien()


def test_customers_gac_khoi_sua_bang_quyen_sua_hanh_chinh() -> None:
    trang = (KHACH / "page.tsx").read_text(encoding="utf-8")
    assert "coMotQuyen(quyen, QUYEN_SUA_HANH_CHINH)" in trang
    assert "canSuaHanhChinh={canSuaHanhChinh}" in trang

    view = (KHACH / "CustomersView.tsx").read_text(encoding="utf-8")
    dau = view.index('tieuDe="Thông tin hành chính"')
    khoi = view[dau : view.index("<PatientAdminEditor", dau)]
    assert "{canSuaHanhChinh ? (" in khoi
    # canEdit gồm cả quyền đặt lịch — gác khối sửa bằng nó là 403 khi Lưu.
    assert "canEdit" not in khoi


def test_danh_sach_benh_nhan_dung_chung_danh_sach() -> None:
    trang = DS_BN.read_text(encoding="utf-8")
    assert "theoQuyen(QUYEN_SUA_HANH_CHINH" in trang
