"""Luật "đổi dịch vụ khám được không" (V5, 30/09/2026) — hàm thuần."""

from __future__ import annotations

from typing import Any

import pytest

from clinicai.services.doi_dich_vu_kham import TRUOC_CHECK_IN, ly_do_khong_doi


def _hoi(**ghi_de: Any) -> str | None:
    mac_dinh: dict[str, Any] = {
        "trang_thai_lich": "CHECKED_IN",
        "trang_thai_luot": "OPEN",
        "phien_da_bat_dau": False,
        "co_phieu_kham": False,
        "da_thu_tien_kham": False,
        "da_chon_dich_vu_con": False,
    }
    return ly_do_khong_doi(**{**mac_dinh, **ghi_de})


@pytest.mark.parametrize("tt", sorted(TRUOC_CHECK_IN))
def test_truoc_check_in_luon_doi_duoc(tt: str) -> None:
    # Chưa có lượt: cờ của lượt không liên quan.
    assert _hoi(trang_thai_lich=tt, trang_thai_luot=None, phien_da_bat_dau=True) is None


def test_sau_check_in_chua_vuong_gi_thi_doi_duoc() -> None:
    assert _hoi() is None
    assert _hoi(trang_thai_luot="IN_PROGRESS") is None


@pytest.mark.parametrize(
    ("ghi_de", "cau"),
    [
        ({"phien_da_bat_dau": True}, "bắt đầu khám"),
        ({"co_phieu_kham": True}, "phiếu khám"),
        ({"da_thu_tien_kham": True}, "huỷ phiếu thu"),
        ({"da_chon_dich_vu_con": True}, "dịch vụ khám con"),
        ({"trang_thai_luot": "FINALIZED"}, "Lượt khám đã đóng"),
        ({"trang_thai_luot": "INCOMPLETE"}, "về giữa chừng"),
        ({"trang_thai_luot": None}, "chưa thấy lượt khám"),
        ({"trang_thai_lich": "COMPLETED"}, "khám xong"),
        ({"trang_thai_lich": "CANCELLED"}, "đã huỷ"),
        ({"trang_thai_lich": "NO_SHOW"}, "không đến"),
        ({"trang_thai_lich": "LA_LUNG"}, "không còn hiệu lực"),
    ],
)
def test_vuong_thi_noi_ro_ly_do(ghi_de: dict[str, Any], cau: str) -> None:
    ly_do = _hoi(**ghi_de)
    assert ly_do is not None and cau in ly_do
