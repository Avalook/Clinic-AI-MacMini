"""Danh sách bệnh nhân — đếm lượt khám một chỗ (16/09/2026).

Lỗi gốc: màn cũ đếm "COMPLETED hoặc CHECKED_IN trong HÔM NAY" nên qua nửa đêm
mọi lượt check-in hôm qua chưa đóng biến mất (46/46 "Chưa khám").
"""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.danh_sach_benh_nhan_service import (
    DanhSachBenhNhanService,
    dang_mo,
    gop,
    phan_loai,
)
from tests.services.fake_sql import pool
from tests.services.test_luat_1509_thu_ky_va_dieu_phoi import BS1, who


def _hs(pid: str, ten: str) -> dict[str, Any]:
    return {"clinic_patient_id": pid, "full_name": ten}


def _l(pid: str, ngay: str, status: str, closed: str | None = None) -> dict[str, Any]:
    return {
        "id": f"{pid}-{ngay}",
        "clinic_patient_id": pid,
        "slot_start": f"{ngay}T02:00:00+00:00",
        "status": status,
        "closed_at": closed,
    }


def test_phan_loai_theo_so_luot() -> None:
    assert [phan_loai(n) for n in (0, 1, 2, 7)] == [
        "Chưa khám",
        "Khám lần đầu",
        "Tái khám",
        "Tái khám",
    ]


def test_luot_hom_qua_chua_dong_van_dang_mo() -> None:
    # Check-in HÔM QUA, quầy chưa đóng → vẫn là lượt đang mở hôm nay.
    assert dang_mo(_l("a", "2026-09-15", "CHECKED_IN")) is True
    assert dang_mo(_l("a", "2026-09-15", "CHECKED_IN", closed="x")) is False
    assert dang_mo(_l("a", "2026-09-15", "COMPLETED")) is False


def test_gop_dem_tong_va_giu_thu_tu_hoat_dong_cua_sql() -> None:
    # Hồ sơ đến đã xếp theo HOẠT ĐỘNG GẦN NHẤT (KHOA_XEP, 27/09 đợt 3): Chi mới
    # tạo hôm nay (chưa khám) đứng TRƯỚC An khám từ tháng trước. Bản cũ xếp lại
    # ở đây và dồn mọi khách "Chưa khám" xuống đáy.
    ho_so = [_hs("c", "Chi"), _hs("b", "Bình"), _hs("a", "An")]
    luot = [  # đã xếp mới → cũ như câu SQL
        _l("b", "2026-09-15", "CHECKED_IN"),
        _l("a", "2026-09-10", "COMPLETED"),
        _l("a", "2026-08-01", "COMPLETED"),
    ]
    out = gop(ho_so, luot)
    assert out["tong"] == {
        "ho_so": 3,
        "dang_mo": 1,
        "lan_dau": 1,
        "tai_kham": 1,
        "chua_kham": 1,
    }
    assert [d["ho_so"]["full_name"] for d in out["dong"]] == ["Chi", "Bình", "An"]
    assert out["dong"][2]["so_luot"] == 2 and out["dong"][2]["phan_loai"] == "Tái khám"
    assert out["dong"][0]["phan_loai"] == "Chưa khám"


def test_gop_rong_khong_nem() -> None:
    assert gop([], [])["dong"] == []
    # Lượt của khách không có trong hồ sơ (ngoài trần) → bỏ qua, không ném.
    assert gop([], [_l("x", "2026-09-15", "COMPLETED")])["tong"]["ho_so"] == 0


@pytest.mark.asyncio
async def test_thu_ky_chi_nhan_khach_cua_bac_si_minh() -> None:
    p = pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        ("AS id FROM public.appointment a", [{"id": "k1"}]),
        (
            "FROM patient p",
            [
                {
                    "clinic_patient_id": "k1",
                    "full_name": "K",
                    "date_of_birth": None,
                    "patient_sdt_them": '[{"so_dien_thoai": "090", "loai": "CHINH"}]',
                }
            ],
        ),
    )
    out = await DanhSachBenhNhanService(p).lay(identity=who(ClinicRole.TKYK))
    # Mã khách được xem đi xuống CẢ HAI câu (hồ sơ + lượt) — lọc ở database.
    assert p.da_goi("FROM patient p")[0][1] == ["k1"]
    assert p.da_goi("FROM appointment a")[0][1] == ["k1"]
    assert out["dong"][0]["ho_so"]["patient_sdt_them"][0]["loai"] == "CHINH"

    khong_loc = pool()
    await DanhSachBenhNhanService(khong_loc).lay(identity=who(ClinicRole.CSKH))
    assert khong_loc.da_goi("FROM patient p")[0][1] is None
