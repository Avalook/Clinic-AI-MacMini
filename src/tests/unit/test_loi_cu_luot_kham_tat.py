"""Lối cũ của khối Khám đã TẮT (24/09/2026, đợt bóc lõi bước 2).

Cũ thì OFF, không xoá (luật Tuyền): cửa cũ trả 410 kèm câu chỉ đường mới, và
ghi log người gọi để biết còn ai dùng. Bật lại bằng `LOI_CU_MO = True`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

import clinicai.api.v1.routers.luot_kham as r


def _ai() -> Any:
    return SimpleNamespace(staff_id="s", role=SimpleNamespace(value="DOCTOR"))


def test_cua_cu_tra_410_co_cau_chi_duong() -> None:
    assert r.LOI_CU_MO is False
    with pytest.raises(HTTPException) as loi:
        r._tat_loi_cu(_ai(), "POST /x", "phòng bấm [Xong].")
    assert loi.value.status_code == 410
    chi_tiet: Any = loi.value.detail
    assert chi_tiet["error"] == "ENDPOINT_RETIRED"
    assert "phòng bấm [Xong]." in chi_tiet["message"]


def test_bat_co_thi_cua_cu_chay_lai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(r, "LOI_CU_MO", True)
    r._tat_loi_cu(_ai(), "POST /x", "…")


@pytest.mark.parametrize(
    "ten",
    [
        "goi_do_sinh_hieu",
        "goi_khach",
        "save_note",
        "propose_orders",
        "complete_consultation",
        "start_service",
        "complete_service",
    ],
)
def test_bay_cua_cu_deu_goi_tat(ten: str) -> None:
    import inspect

    assert "_tat_loi_cu(" in inspect.getsource(getattr(r, ten))
