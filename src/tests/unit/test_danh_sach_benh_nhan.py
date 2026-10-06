"""Danh sách bệnh nhân — đếm lượt khám một chỗ (16/09/2026).

Lỗi gốc: màn cũ đếm "COMPLETED hoặc CHECKED_IN trong HÔM NAY" nên qua nửa đêm
mọi lượt check-in hôm qua chưa đóng biến mất (46/46 "Chưa khám").

06/10/2026: phân trang + tìm phía máy chủ — tham số rác về mặc định, không ném.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from clinicai.api.identity import ClinicRole
from clinicai.services.danh_sach_benh_nhan_service import (
    DanhSachBenhNhanService,
    chuoi_tim,
    dang_mo,
    doc_loc,
    doc_sap,
    doc_trang,
    ghep,
    ma_khach,
    mau_so,
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


def test_ghep_giu_thu_tu_hoat_dong_cua_sql() -> None:
    # Hồ sơ đến đã xếp theo HOẠT ĐỘNG GẦN NHẤT (27/09 đợt 3): Chi mới tạo hôm
    # nay (chưa khám) đứng TRƯỚC An khám từ tháng trước. Bản cũ xếp lại ở đây
    # và dồn mọi khách "Chưa khám" xuống đáy.
    ho_so = [_hs("c", "Chi"), _hs("b", "Bình"), _hs("a", "An")]
    luot = [  # đã xếp mới → cũ như câu SQL
        _l("b", "2026-09-15", "CHECKED_IN"),
        _l("a", "2026-09-10", "COMPLETED"),
        _l("a", "2026-08-01", "COMPLETED"),
    ]
    dong = ghep(ho_so, luot)
    assert [d["ho_so"]["full_name"] for d in dong] == ["Chi", "Bình", "An"]
    assert [d["phan_loai"] for d in dong] == ["Chưa khám", "Khám lần đầu", "Tái khám"]
    assert [d["dang_mo"] for d in dong] == [False, True, False]
    assert dong[2]["so_luot"] == 2


def test_ghep_rong_khong_nem() -> None:
    assert ghep([], []) == []
    # Lượt của khách không có trong trang → bỏ qua, không ném.
    assert ghep([], [_l("x", "2026-09-15", "COMPLETED")]) == []


@pytest.mark.parametrize(
    ("vao", "ra"),
    [
        (None, 1),
        ("", 1),
        ("abc", 1),
        ("-1", 1),
        ("0", 1),
        ("2.5", 1),
        (" 3 ", 3),
        ("12", 12),
        (7, 7),
    ],
)
def test_doc_trang_rac_ve_trang_1(vao: Any, ra: int) -> None:
    assert doc_trang(vao) == ra


def test_doc_loc_va_sap_rac_ve_mac_dinh() -> None:
    assert doc_loc("lan-dau") == "lan-dau"
    assert doc_loc("tai-kham") == "tai-kham"
    assert doc_loc("chua-kham") == "chua-kham"
    assert (
        doc_loc("all") is None and doc_loc(None) is None and doc_loc("'; drop") is None
    )
    assert doc_sap("xa") == "xa"
    assert doc_sap(None) == "gan" and doc_sap("rác") == "gan"


def test_chuoi_tim_va_mau_so() -> None:
    # Ký tự đặc biệt của ILIKE thành khoảng trắng; khoảng trắng gộp lại.
    assert chuoi_tim("  Nguyễn%_  (Lan) ") == "Nguyễn Lan"
    assert chuoi_tim(None) == ""
    # Ô tìm chỉ có số → bỏ dấu ngăn, tìm một phần số.
    assert mau_so("0912 345") == "%0912345%"
    assert mau_so("0912.345-678") == "%0912345678%"
    assert mau_so("345") == "%345%"
    assert mau_so("12") is None  # quá ngắn — khớp gần như mọi số
    assert mau_so("Lan 0912") is None  # có chữ → không phải SĐT
    assert mau_so("") is None


def test_ma_khach_hong_ve_none() -> None:
    assert ma_khach("rác") is None and ma_khach(None) is None
    u = "6f1e1f2c-3a4b-4c5d-8e9f-0a1b2c3d4e5f"
    assert ma_khach(f" {u.upper()} ") == u


_DEM = {
    "ho_so": 1,
    "dang_mo": 0,
    "lan_dau": 0,
    "tai_kham": 0,
    "chua_kham": 1,
    "khop": 1,
}


@pytest.mark.asyncio
async def test_thu_ky_chi_nhan_khach_cua_bac_si_minh() -> None:
    p = pool(
        ("FROM public.thu_ky_bac_si", [BS1]),
        ("AS id FROM public.appointment a", [{"id": "k1"}]),
        ("AS khop FROM co_so", _DEM),
        (
            "FROM t JOIN patient p",
            [
                {
                    "clinic_patient_id": "k1",
                    "full_name": "K",
                    "date_of_birth": None,
                    "patient_sdt_them": '[{"so_dien_thoai": "090", "loai": "CHINH"}]',
                }
            ],
        ),
        ("a.queue_number", []),
    )
    out = await DanhSachBenhNhanService(p).lay(identity=who(ClinicRole.TKYK))
    # Mã khách được xem đi xuống câu ĐẾM lẫn câu TRANG — lọc ở database; lượt
    # chỉ nạp cho đúng khách trong trang.
    assert p.da_goi("AS khop FROM co_so")[0][1] == ["k1"]
    assert p.da_goi("FROM t JOIN patient p")[0][1] == ["k1"]
    assert p.da_goi("a.queue_number")[0][1] == ["k1"]
    assert out["dong"][0]["ho_so"]["patient_sdt_them"][0]["loai"] == "CHINH"
    assert out["tong"]["ho_so"] == 1 and out["so_khop"] == 1 and out["trang"] == 1

    khong_loc = pool(("AS khop FROM co_so", _DEM))
    await DanhSachBenhNhanService(khong_loc).lay(identity=who(ClinicRole.CSKH))
    assert khong_loc.da_goi("AS khop FROM co_so")[0][1] is None


@pytest.mark.asyncio
async def test_trang_vuot_qua_ve_trang_cuoi_tham_so_rac_khong_nem() -> None:
    p = pool(("AS khop FROM co_so", {**_DEM, "khop": 120}))
    out = await DanhSachBenhNhanService(p).lay(
        identity=who(ClinicRole.CSKH), trang="999", loc="rác", sap="rác", chon="hỏng"
    )
    # 120 dòng / 50 = 3 trang → trang 999 về trang 3 (offset 100, limit 50).
    assert (out["trang"], out["so_trang"], out["so_khop"]) == (3, 3, 120)
    [args] = p.da_goi("FROM t JOIN patient p")
    assert args[-2:] == (100, 50)
    assert args[5:7] == (0, None)  # tab rác → tất cả
    assert out["chon"] is None and out["dong"] == []
    # Không có dòng nào → không hỏi lượt.
    assert p.da_goi("a.queue_number") == []

    am = pool(("AS khop FROM co_so", {**_DEM, "khop": 0}))
    out = await DanhSachBenhNhanService(am).lay(
        identity=who(ClinicRole.CSKH), trang="-1"
    )
    assert (out["trang"], out["so_trang"]) == (1, 1)


@pytest.mark.asyncio
async def test_luot_chi_nap_cho_khach_trong_trang_va_khach_dang_chon() -> None:
    """06/10/2026: lượt cũ Notion thành ~14.000 lượt THẬT — không gửi hết về
    trình duyệt. Câu lượt chỉ nhận mã khách của TRANG + khách đang chọn."""
    chon = "6f1e1f2c-3a4b-4c5d-8e9f-0a1b2c3d4e5f"

    def _r(pid: str) -> dict[str, Any]:
        return {
            "clinic_patient_id": pid,
            "full_name": pid,
            "date_of_birth": None,
            "patient_sdt_them": "[]",
        }

    luot = {
        "id": "l1",
        "clinic_patient_id": chon,
        "status": "COMPLETED",
        "slot_start": datetime(2026, 1, 2, tzinfo=UTC),
        "closed_at": None,
    }
    p = pool(
        ("AS khop FROM co_so", {**_DEM, "khop": 2}),
        ("= $8::uuid", _r(chon)),
        ("FROM t JOIN patient p", [_r("a"), _r("b")]),
        ("a.queue_number", [luot]),
    )
    out = await DanhSachBenhNhanService(p).lay(identity=who(ClinicRole.CSKH), chon=chon)
    [args] = p.da_goi("a.queue_number")
    assert args[1] == ["a", "b", chon]
    assert [d["ho_so"]["clinic_patient_id"] for d in out["dong"]] == ["a", "b"]
    assert all(d["luot"] == [] for d in out["dong"])
    assert out["chon"]["so_luot"] == 1 and out["chon"]["phan_loai"] == "Khám lần đầu"
