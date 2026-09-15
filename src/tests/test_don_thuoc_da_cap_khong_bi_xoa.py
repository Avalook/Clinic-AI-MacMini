"""Lưu lại bệnh án không được xoá dòng đơn thuốc nhà thuốc đã cấp (15/09/2026).

Bản cũ `_replace_prescriptions` DELETE toàn bộ đơn rồi INSERT lại → mất số đã
cấp, sổ kho trỏ vào dòng không còn, dòng mới cấp lại được (trừ kho hai lần). Và
không đường ghi nào điền `quantity_num`, nên chốt "không cấp quá số kê" chưa từng
chạy với đơn mới. Hành vi mới đã chạy thật trên Postgres (smoke 15/09); các bài
dưới canh quan hệ cho CI.
"""

from __future__ import annotations

import inspect

from clinicai.services.clinical_prescription_service import (
    _locked_prescription_matches,
)
from clinicai.services.clinical_record_service import (
    ClinicalRecordService,
)


def _ma() -> str:
    return inspect.getsource(ClinicalRecordService._replace_prescriptions)


def test_chi_xoa_dong_chua_cap_chua_chot() -> None:
    ma = _ma()
    dau = ma.index("DELETE FROM prescription")
    khoi = ma[dau : ma.index('"""', dau)]
    assert "dispensed_qty = 0" in khoi and "closed_at IS NULL" in khoi


def test_dong_da_khoa_phai_con_trong_ban_gui_len() -> None:
    ma = _ma()
    assert "raise ConflictError" in inspect.getsource(_locked_prescription_matches)
    assert "_locked_prescription_matches(" in ma
    assert "FOR UPDATE" in ma, "đọc dòng cũ phải khoá, không thì dược sĩ cấp chen giữa"


def test_dong_moi_ghi_so_luong_ke_dang_so() -> None:
    ma = _ma()
    assert "so_luong_tu_van_ban(" in ma and "don_vi_tu_van_ban(" in ma


def test_source_ref_khong_theo_vi_tri() -> None:
    assert "enumerate(" not in _ma(), "đánh số theo vị trí sẽ đụng UNIQUE source_ref"
