"""`kiem_ke_chua_khop.cau_chua_khop` — câu "Chưa khớp" chỉ khẳng định "bán sau lúc
đếm" khi điều đó GIẢI THÍCH ĐỦ phần chưa trừ (soát 20/11/2026). Thuần, không DB."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from clinicai.services.kiem_ke_chua_khop import cau_chua_khop

D = Decimal
# 04:34 UTC = 11:34 giờ Việt Nam.
MOC = datetime(2026, 11, 20, 4, 34, tzinfo=UTC)


def _luc(h: int, m: int) -> datetime:
    return datetime(2026, 11, 20, h, m, tzinfo=UTC)


def _cau(ra_sau: list[tuple[datetime, Decimal]], con_thieu: Decimal) -> str | None:
    return cau_chua_khop(
        don_vi="hộp",
        dem=D(0),
        ton_may=D(1),
        moc=MOC,
        ra_sau=ra_sau,
        con_thieu=con_thieu,
    )


def test_ca_eluna_noi_ro_gio_viet_nam() -> None:
    cau = _cau([(_luc(4, 39), D(1))], D(1))
    assert cau is not None
    assert "đếm 0 hộp lúc 11:34 khi sổ còn 1" in cau
    assert "sau đó bán / giao 1 hộp lúc 11:39" in cau
    assert "Hoàn tác phiếu → Sửa số đếm" in cau


def test_khong_co_lan_giao_nao_thi_giu_cau_chung() -> None:
    assert _cau([], D(1)) is None


def test_giao_khong_du_phan_thieu_thi_khong_khang_dinh_nguyen_nhan() -> None:
    # Thiếu 3 mà chỉ bán 1 sau lúc đếm: 2 còn lại do thứ khác (chuyển, huỷ…).
    assert _cau([(_luc(4, 39), D(1))], D(3)) is None


def test_nhieu_lan_giao_noi_khoang_gio() -> None:
    cau = _cau([(_luc(4, 39), D(1)), (_luc(5, 5), D(2))], D(3))
    assert cau is not None and "sau đó bán / giao 3 hộp từ 11:39 tới 12:05" in cau


def test_hoan_giao_tru_rong_va_khong_lam_lech_khoang_gio() -> None:
    # 11:36 hoàn một lần giao TRƯỚC mốc (âm), 11:39 giao 2 → ròng 1.
    cau = _cau([(_luc(4, 36), D(-1)), (_luc(4, 39), D(2))], D(1))
    assert cau is not None and "sau đó bán / giao 1 hộp lúc 11:39" in cau
    # Chỉ có hoàn giao → không phải do bán.
    assert _cau([(_luc(4, 36), D(-1))], D(1)) is None
