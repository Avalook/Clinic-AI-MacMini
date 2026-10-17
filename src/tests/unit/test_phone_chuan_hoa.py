"""The approved phone table, garbage input, and compatibility contracts."""

from uuid import UUID

import pytest

from clinicai.core.phone import (
    che_sdt,
    chuan_hoa_sdt,
    dinh_dang_hien_thi,
    mau_tim_sdt,
    normalize_vn_phone,
    phone_variants,
    sang_e164,
)
from clinicai.schemas.patient import PatientCreateDTO, PatientUpdateDTO
from clinicai.schemas.staff import StaffUpdateDTO
from clinicai.services.providers.zalo import chuan_hoa_sdt as zalo_phone


@pytest.mark.parametrize(
    "raw",
    [
        "0912 345 678",
        "0912.345.678",
        "0912-345-678",
        "+84 912 345 678",
        "(+84) 912345678",
        "84912345678",
        "0084912345678",
        "912345678",
        "0912345678",
        " 0912345678 ",
        "0912\u00a0345\u00a0678",
    ],
)
def test_approved_vietnamese_table(raw: str) -> None:
    phone = chuan_hoa_sdt(raw)
    assert phone is not None
    assert (phone.so, phone.loai) == ("0912345678", "DI_DONG")
    assert not phone.so.startswith("+84")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+1 415 555 2671", "+14155552671"),
        ("001 415 555 2671", "+14155552671"),
        ("(+1) 415.555.2671", "+14155552671"),
        ("+82 10 1234 5678", "+821012345678"),
        ("+82 10-1234-5678", "+821012345678"),
    ],
)
def test_approved_foreign_table(raw: str, expected: str) -> None:
    phone = chuan_hoa_sdt(raw)
    assert phone is not None
    assert (phone.so, phone.loai) == (expected, "QUOC_TE")
    assert phone_variants(raw) == [expected]
    assert normalize_vn_phone(raw) is None


@pytest.mark.parametrize(
    "raw",
    [
        "091234567",
        "0912345678 9",
        "0123456789",
        "0912345678 gặp chị Hoa",
        "abc",
        "",
        None,
        "12345",
        "9" * 5000,
        "０９１２３４５６７８",
        "0912\u200b345678",
        "0912\ufeff345678",
        "++84912345678",
        "84+912345678",
        "+",
        "00",
        "...",
        " ",
        912345678,
        [],
        {},
        True,
        1.2,
        "+123",
        "+999123456789",
        "+1415555267100000",
        "0412345678",
        "0612345678",
        "001234",
        "0912345678 ext 2",
        "☎0912345678",
        "+840912345678",
        "00840912345678",
    ],
)
def test_garbage_never_throws(raw: object) -> None:
    assert chuan_hoa_sdt(raw) is None


@pytest.mark.parametrize("prefix", ["03", "05", "07", "08", "09"])
def test_vietnamese_prefixes(prefix: str) -> None:
    assert normalize_vn_phone(prefix + "12345678") == prefix + "12345678"


def test_landline_and_compatibility() -> None:
    phone = chuan_hoa_sdt("0281234567")
    assert phone is not None and phone.loai == "CO_DINH"
    assert phone.so == "0281234567"
    assert normalize_vn_phone(phone.so) is None
    assert zalo_phone(phone.so) is None
    assert phone_variants("+84912345678") == [
        "0912345678",
        "84912345678",
        "+84912345678",
    ]


def test_country_selector() -> None:
    phone = chuan_hoa_sdt("415 555 2671", "US")
    assert phone is not None and phone.so == "+14155552671"
    assert chuan_hoa_sdt("415 555 2671") is None
    assert chuan_hoa_sdt("415 555 2671", "INVALID") is None
    assert chuan_hoa_sdt("+84912345678", "US") == chuan_hoa_sdt("0912345678")


def test_helpers() -> None:
    assert sang_e164("0912345678") == "+84912345678"
    assert sang_e164("+14155552671") == "+14155552671"
    assert sang_e164("bad") is None
    assert dinh_dang_hien_thi("0912345678") == "0912 345 678"
    assert dinh_dang_hien_thi("0912") == "0912"
    assert dinh_dang_hien_thi("+14155552671") == "+1 415 555 2671"
    assert che_sdt("0334567897") == "0334***897"
    assert che_sdt(None) == ""
    assert che_sdt("0912") == "0912"
    assert mau_tim_sdt("+84 912") == "0912"
    assert mau_tim_sdt("0084912") == "0912"
    assert mau_tim_sdt("001415") == "1415"
    assert mau_tim_sdt("bad") is None


@pytest.mark.parametrize("raw", ["+1 415 555 2671", "0912 345 678", "0281234567"])
def test_schema_paths_share_normalizer(raw: str) -> None:
    expected = chuan_hoa_sdt(raw)
    assert expected is not None
    assert (
        PatientCreateDTO(
            full_name="DEMO Phone",
            phone_primary=raw,
            location_id=UUID("00000000-0000-0000-0000-000000000001"),
        ).phone_primary
        == expected.so
    )
    assert PatientUpdateDTO(phone_secondary=raw).phone_secondary == expected.so
    assert StaffUpdateDTO(phone=raw).phone == expected.so


def test_zns_only_mobile_vietnam() -> None:
    assert zalo_phone("(+84) 912345678") == "84912345678"
    assert zalo_phone("+14155552671") is None
    assert zalo_phone("0100000000") is None


def test_vietnamese_validation_does_not_call_library(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("VN must use the existing local rules")

    monkeypatch.setattr("clinicai.core.phone.phonenumbers.parse", forbidden)
    assert chuan_hoa_sdt("0912345678") is not None
    assert chuan_hoa_sdt("0281234567") is not None
