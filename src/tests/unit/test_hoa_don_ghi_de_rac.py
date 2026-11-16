"""`ghi_de` (thuế suất sửa tay trên URL màn Xuất hoá đơn): rác → rỗng, không 500."""

import pytest

from clinicai.api.v1.routers.hoa_don import _doc_ghi_de


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "{",
        "không phải json",
        "[]",
        '"chuoi"',
        "123",
        "null",
        # Lồng rất sâu: json.loads ném RecursionError (không phải ValueError) —
        # trước đây lọt ra thành 500.
        "[" * 100_000,
        '{"a":' * 100_000,
    ],
    ids=[
        "none",
        "rong",
        "json-hong",
        "chu",
        "mang",
        "chuoi",
        "so",
        "null",
        "mang-long-sau",
        "dict-long-sau",
    ],
)
def test_rac_thanh_rong(raw: str | None) -> None:
    assert _doc_ghi_de(raw) == {}


def test_dung_dang_giu_va_cat_do_dai() -> None:
    assert _doc_ghi_de('{"dong-1": "8"}') == {"dong-1": "8"}
    assert _doc_ghi_de('{"dong-1": [[1]]}') == {"dong-1": "[[1]]"}
    dai = _doc_ghi_de('{"' + "k" * 100 + '": "' + "9" * 100 + '"}')
    assert dai == {"k" * 64: "9" * 20}
