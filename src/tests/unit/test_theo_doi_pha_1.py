"""Theo dõi lỗi Pha 1 (27/09/2026): kho lỗi, canh gác, nhật ký — phần THUẦN."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from clinicai.services import canh_gac, kho_loi
from clinicai.services import nhat_ky_van_hanh as nk


def _loi(msg: str) -> Exception:
    try:
        raise ValueError(msg)
    except ValueError as e:
        return e


def test_thong_diep_che_sdt_gia_tri_pg_va_uuid() -> None:
    e = _loi(
        "duplicate key: Key (full_name)=(Nguyễn Văn A) phone 0901234567 "
        "visit 5a8cb1fd-fb54-41ae-94a2-280127d468da"
    )
    chu = kho_loi.thong_diep_sach(e)
    assert "Nguyễn" not in chu and "0901234567" not in chu
    assert "5a8cb1fd" not in chu and "=(…)" in chu and ":id" in chu
    assert len(kho_loi.thong_diep_sach(_loi("x" * 5000))) <= kho_loi.DAI_TOI_DA


def test_dau_van_cung_kieu_thi_trung_khac_vi_tri_thi_khac() -> None:
    a = kho_loi.dau_van("api", "GET /x", _loi("một"))
    b = kho_loi.dau_van("api", "GET /x", _loi("hai — chữ khác, cùng kiểu"))
    c = kho_loi.dau_van("api", "GET /y", _loi("một"))
    assert a == b and a != c


def _so(**kw: int) -> dict[str, object]:
    su_kien = {
        "dang_cho": 0,
        "tre_giao": 0,
        "ton_lau": 0,
        "chet_24h": 0,
        "hen_gio_tre": 0,
        "hen_gio_chet_24h": 0,
    }
    so: dict[str, object] = {
        "su_kien": su_kien,
        "loi_moi_15p": 0,
        "lan_loi_15p": 0,
        "kieu_loi_5p": 0,
        "hang_cho_ma": 0,
        "luot_treo": 0,
    }
    for k, v in kw.items():
        if k in su_kien:
            su_kien[k] = v
        else:
            so[k] = v
    return so


def test_canh_gac_on_het_thi_khong_co_chuyen() -> None:
    assert not any(k.co_chuyen for k in canh_gac.danh_gia(_so()))


@pytest.mark.parametrize(
    ("kw", "ma"),
    [
        ({"tre_giao": 1}, "SU_KIEN"),
        ({"loi_moi_15p": 2}, "LOI_MOI"),
        ({"kieu_loi_5p": canh_gac.NGUONG_KIEU_LOI_5P}, "LOI_DANG_DIEN"),
        ({"hang_cho_ma": 1}, "HANG_CHO_MA"),
        ({"luot_treo": 3}, "LUOT_TREO"),
    ],
)
def test_moi_chuyen_mo_dung_ma(kw: dict[str, int], ma: str) -> None:
    co = [k.ma for k in canh_gac.danh_gia(_so(**kw)) if k.co_chuyen]
    assert co == [ma]


def test_chi_so_luot_va_trung_vi() -> None:
    t0 = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
    moc = {
        "visit.checked_in": t0,
        "vitals.started": t0 + timedelta(minutes=4),
        "vitals.recorded": t0 + timedelta(minutes=7),
        "consultation.started": t0 + timedelta(minutes=20),
    }
    cs = nk.chi_so_luot(moc)
    assert cs["cho_do"] == 4.0 and cs["do"] == 3.0 and cs["cho_kham"] == 20.0
    assert cs["tong"] is None, "chưa về thì không có tổng"
    tv = nk.trung_vi([cs, {**cs, "cho_do": 10.0}, {k: None for k in cs}])
    assert tv["cho_do"] == 7.0 and tv["tong"] is None


@pytest.mark.parametrize("rac", ["", "abc", "2026-02-31", None, "27/09/2026"])
def test_ngay_rac_tra_rong(rac: str | None) -> None:
    assert nk.doc_ngay(rac) is None
