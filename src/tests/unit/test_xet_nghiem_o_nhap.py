"""Ô nhập bàn xét nghiệm đối tác: rác → 422, không 500 (luật backend)."""

from __future__ import annotations

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.xet_nghiem.o_nhap import doc_drive, doc_so_ngay, doc_tien


# ── Ô nhập rác → 422, không 500 ────────────────────────────────────────────
@pytest.mark.parametrize("rac", ["abc", "-1", "91", "1.5", "  x "])
def test_so_ngay_rac(rac: str) -> None:
    with pytest.raises(ValidationError):
        doc_so_ngay(rac)


@pytest.mark.parametrize("rong", [None, "", "  "])
def test_so_ngay_rong(rong: object) -> None:
    assert doc_so_ngay(rong) is None


@pytest.mark.parametrize(("vao", "ra"), [("550.000", 550000), (0, 0), ("", None)])
def test_doc_tien(vao: object, ra: int | None) -> None:
    assert doc_tien(vao) == ra


@pytest.mark.parametrize("rac", ["abc", "-5", "1e9"])
def test_doc_tien_rac(rac: str) -> None:
    with pytest.raises(ValidationError):
        doc_tien(rac)


def test_doc_drive() -> None:
    link = "https://drive.google.com/drive/folders/1AbCdEfGhIjK_lmn-op?usp=sharing"
    assert doc_drive(link) == "1AbCdEfGhIjK_lmn-op"
    assert doc_drive("") is None
    with pytest.raises(ValidationError):
        doc_drive("https://example.com/x")
