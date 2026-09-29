"""Đổi lịch tại chỗ — phần hàm thuần: ô giờ, "ngay bây giờ", lý do."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.booking_service import KHUNG_BAY_GIO_PHUT, la_khung_bay_gio
from clinicai.services.doi_lich_nhanh import LY_DO_DOI_LICH, dung_hang, trang_thai_o


def test_la_khung_bay_gio() -> None:
    now = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
    assert la_khung_bay_gio(now, now)
    assert la_khung_bay_gio(now + timedelta(minutes=KHUNG_BAY_GIO_PHUT), now)
    assert not la_khung_bay_gio(now + timedelta(minutes=KHUNG_BAY_GIO_PHUT + 1), now)
    assert not la_khung_bay_gio(now - timedelta(hours=2), now)


def test_trang_thai_o() -> None:
    assert trang_thai_o(cap=3, used=0, chan=True) == "TRONG"
    assert trang_thai_o(cap=3, used=2, chan=True) == "IT"
    assert trang_thai_o(cap=3, used=3, chan=True) == "DAY"
    # Tuần chưa công bố lịch trực: trần không chặn → không bao giờ "đầy".
    assert trang_thai_o(cap=1, used=5, chan=False) == "TRONG"


def _q(*phut: int, closed: bool = False) -> dict[str, Any]:
    return {
        "closed": closed,
        "regular_chan": True,
        "walkin_chan": True,
        "slots": [
            {
                "minute_of_day": m,
                "slot_minutes": 15,
                "regular_cap": 2,
                "regular_used": 0,
                "walkin_cap": 1,
                "walkin_used": 1,
            }
            for m in phut
        ],
    }


def test_dung_hang_hom_nay_bo_khung_da_qua_va_co_o_ngay_bay_gio() -> None:
    ngay = date(2026, 9, 29)
    bay_gio = datetime(2026, 9, 29, 9, 7, tzinfo=CLINIC_TZ)
    o, nbg = dung_hang(
        _q(8 * 60 + 45, 9 * 60, 9 * 60 + 15),
        ngay=ngay,
        bay_gio=bay_gio,
        thoi_luong=timedelta(minutes=20),
        walkin=False,
        lich_hien_tai=None,
    )
    assert [x["gio"] for x in o] == ["09:00", "09:15"], "khung 08:45 đã qua"
    assert o[0]["dang_chay"] and not o[1]["dang_chay"]
    assert nbg is not None and nbg["gio"] == "09:07" and nbg["ngoai_ca"] is False
    bd = datetime.fromisoformat(nbg["slot_start"])
    assert datetime.fromisoformat(nbg["slot_end"]) - bd == timedelta(minutes=20)


def test_dung_hang_ngoai_ca_va_vang_lai() -> None:
    ngay = date(2026, 9, 29)
    bay_gio = datetime(2026, 9, 29, 7, 30, tzinfo=CLINIC_TZ)
    o, nbg = dung_hang(
        _q(14 * 60),
        ngay=ngay,
        bay_gio=bay_gio,
        thoi_luong=timedelta(minutes=15),
        walkin=True,
        lich_hien_tai=None,
    )
    assert nbg is not None and nbg["ngoai_ca"] is True
    assert o[0]["trang_thai"] == "DAY", "vãng lai đếm ghế vãng lai"


def test_dung_hang_ngay_khac_khong_co_ngay_bay_gio_va_danh_dau_lich_hien_tai() -> None:
    ngay = date(2026, 9, 30)
    bay_gio = datetime(2026, 9, 29, 9, 0, tzinfo=CLINIC_TZ)
    hien_tai = datetime(2026, 9, 30, 8, 30, tzinfo=CLINIC_TZ)
    o, nbg = dung_hang(
        _q(8 * 60 + 30, 8 * 60 + 45),
        ngay=ngay,
        bay_gio=bay_gio,
        thoi_luong=timedelta(minutes=15),
        walkin=False,
        lich_hien_tai=hien_tai,
    )
    assert nbg is None
    assert [x["la_lich_hien_tai"] for x in o] == [True, False]


def test_ly_do_mac_dinh_la_khach_den_som() -> None:
    assert LY_DO_DOI_LICH[0] == "Khách đến sớm"
