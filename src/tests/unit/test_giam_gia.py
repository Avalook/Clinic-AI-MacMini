from dataclasses import replace
from decimal import Decimal

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.bill_service import DongHoaDon, GiamGia, HoaDon, ap_giam_gia
from clinicai.services.giam_gia_service import doc_gia_tri


def hd() -> HoaDon:
    return HoaDon(
        "visit",
        "dich_vu",
        [
            DongHoaDon(
                "service_order",
                "one",
                "Một",
                Decimal(1),
                "lần",
                Decimal(101),
                Decimal(101),
                "CLINIC",
                tien_goc=Decimal(101),
            ),
            DongHoaDon(
                "service_order",
                "two",
                "Hai",
                Decimal(1),
                "lần",
                Decimal(200),
                Decimal(200),
                "CLINIC",
                tien_goc=Decimal(200),
            ),
        ],
    )


def gg(pham_vi: str, kieu: str, value: str, sid: str | None = None) -> GiamGia:
    return GiamGia(
        value + pham_vi,
        pham_vi,
        kieu,
        Decimal(value),
        "service_order" if sid else None,
        sid,
    )


def test_dong_truoc_hoa_don_sau_chia_dung_va_immutable() -> None:
    before = hd()
    after = ap_giam_gia(
        before, [gg("DONG", "PHAN_TRAM", "50", "one"), gg("HOA_DON", "PHAN_TRAM", "10")]
    )
    assert after.tong == 225
    assert after.tong_giam == 76
    assert [int(d.giam) for d in after.dong] == [56, 20]
    assert before.tong == 301


def test_so_tien_hoa_don_du_don_dong_lon_nhat() -> None:
    after = ap_giam_gia(hd(), [gg("HOA_DON", "SO_TIEN", "100")])
    assert [int(d.giam) for d in after.dong] == [33, 67]
    assert after.tong == 201


def test_khong_giam_giu_nguyen_revision() -> None:
    before = hd()
    assert ap_giam_gia(before, []) is before
    old = replace(
        before, dong=[replace(d, tien_goc=None, giam=Decimal(0)) for d in before.dong]
    )
    assert old.revision == before.revision


def test_100_phan_tram_va_revision_doi() -> None:
    before = hd()
    after = ap_giam_gia(before, [gg("HOA_DON", "PHAN_TRAM", "100")])
    assert after.tong == 0 and after.tong_giam == 301
    assert after.revision != before.revision


def test_lon_hon_tien_bi_tu_choi() -> None:
    assert ap_giam_gia(hd(), [gg("DONG", "SO_TIEN", "102", "one")]).van_de


def test_khong_giam_doi_tac_lieu_trinh_va_dong_loi() -> None:
    before = hd()
    before.dong = [
        replace(before.dong[0], ben_thu="EXTERNAL_PARTNER"),
        replace(before.dong[1], source_type="lieu_trinh"),
    ]
    after = ap_giam_gia(before, [gg("HOA_DON", "PHAN_TRAM", "100")])
    assert after.tong_giam == 0


@pytest.mark.parametrize(
    "kind,value",
    [
        (None, 10),
        ([], 10),
        ("SO_TIEN", "NaN"),
        ("SO_TIEN", "Infinity"),
        ("SO_TIEN", -1),
        ("PHAN_TRAM", 150),
        ("SO_TIEN", "1.5"),
        ("PHAN_TRAM", "1.123"),
        ("SO_TIEN", "1e99"),
        ("SO_TIEN", {}),
    ],
)
def test_rac(kind: object, value: object) -> None:
    with pytest.raises(ValidationError):
        doc_gia_tri(kind, value)
