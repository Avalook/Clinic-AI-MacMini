"""Router /api/v1/tro-ly: cờ bật/tắt, danh sách model, mã rác trên URL."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from clinicai.api.v1.routers import tro_ly


@pytest.mark.parametrize(
    ("bat", "mo_hinh", "mong"),
    [
        ("true", "anthropic:claude-haiku-5-5", True),
        ("TRUE ", "anthropic:a, ollama:b", True),
        ("true", "", False),  # bật mà không có model nào = tắt
        ("false", "anthropic:a", False),
        ("", "anthropic:a", False),
    ],
)
def test_da_bat(
    monkeypatch: pytest.MonkeyPatch, bat: str, mo_hinh: str, mong: bool
) -> None:
    monkeypatch.setenv("TRO_LY_BAT", bat)
    monkeypatch.setenv("TRO_LY_MO_HINH", mo_hinh)
    assert tro_ly.da_bat() is mong


def test_danh_sach_mo_hinh_bo_khoang_trang(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRO_LY_MO_HINH", " anthropic:a ,, ollama:b ")
    assert tro_ly.danh_sach_mo_hinh() == ["anthropic:a", "ollama:b"]


def test_tat_thi_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRO_LY_BAT", "false")
    with pytest.raises(HTTPException) as e:
        tro_ly.require_bat()
    assert e.value.status_code == 503


@pytest.mark.parametrize("rac", ["", "abc", "1; drop table x", "a0000000-0000"])
def test_ma_rac_tren_url_thi_404(rac: str) -> None:
    with pytest.raises(HTTPException) as e:
        tro_ly._uuid(rac)
    assert e.value.status_code == 404
