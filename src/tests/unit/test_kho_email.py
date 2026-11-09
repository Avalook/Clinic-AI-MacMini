"""Gmail G2b — hàm thuần của Kho email: đọc bộ lọc (rác ⇒ bỏ lọc, không ném) và chữ
thanh trên (màn chỉ hiện, không tự suy)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from clinicai.services.xet_nghiem import kho_email


def test_doc_loc_rac_khong_nem() -> None:
    loc = kho_email.doc_loc(
        {"tu_ngay": "2026-13-40", "trang_thai": "X", "trang": "0", "co": "9999"}
    )
    assert loc["tu_ngay"] is None and loc["trang_thai"] is None
    assert (loc["trang"], loc["co"]) == (1, kho_email.CO_TOI_DA)
    assert kho_email.doc_loc({"q": "0912 345 678"})["so"] == "0912345678"
    assert kho_email.doc_loc({"q": "Vũ Thị A"})["chu"] == "vu thi a"
    assert kho_email.doc_loc({"q": "   "})["chu"] is None
    assert kho_email.doc_loc({"trang": "abc", "co": "-5"})["co"] == 1


@pytest.mark.parametrize(
    ("da_nap", "con", "tre", "so_loi", "so_dt", "mau", "co_chu"),
    [
        (0, 0, None, 0, 0, "neutral", "chưa nối email"),
        (5, 0, None, 0, 2, "danger", "chưa đọc được"),
        (1240, 660, 10, 0, 2, "success", "Đã nạp 1.240 / ~1.900 thư · Email ổn"),
        (5, 0, 90, 0, 2, "danger", "Email lỗi"),
        (5, 0, 10, 1, 2, "danger", "Email lỗi"),
    ],
)
def test_den_kho(
    da_nap: int,
    con: int,
    tre: int | None,
    so_loi: int,
    so_dt: int,
    mau: str,
    co_chu: str,
) -> None:
    bay_gio = datetime(2026, 11, 9, 10, tzinfo=UTC)
    ok = None if tre is None else bay_gio - timedelta(minutes=tre)
    d = kho_email.den_kho(da_nap, con, ok, so_loi, so_dt, bay_gio)
    assert d["mau"] == mau and co_chu in d["nhan"]
