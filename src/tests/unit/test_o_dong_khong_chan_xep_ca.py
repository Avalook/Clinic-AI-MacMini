"""Ô ĐEN (DONG) không còn chặn xếp ca — Tuyền 28/09/2026: "xoá ô đen, mở lại
quyền đặt ca, đừng block nữa".

Máy chủ chỉ trả khối NGHỈ cho bảng lịch (màn Lịch làm việc + Trang chủ); giao
diện vẽ ô DONG lọt ra như ô thường (có nút +). Khoá cả hai đầu để bản sau
không lặng lẽ trả ô đen về.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from clinicai.services import config_service, man_trang_chu_service

GOC = Path(__file__).resolve().parents[3]


def test_may_chu_chi_tra_khoi_nghi() -> None:
    for mod in (config_service, man_trang_chu_service):
        src = inspect.getsource(mod)
        i = src.index("FROM vi_tri_dong_ca")
        assert "ly_do = 'NGHI'" in src[i : i + 200], mod.__name__


def test_luoi_lich_khong_con_nhanh_o_den() -> None:
    luoi = (GOC / "src/dashboard/app/(dashboard)/RosterGrid.tsx").read_text()
    assert "bg-lich-dong" not in luoi
    assert 'aria-label="Không làm ca này"' not in luoi
