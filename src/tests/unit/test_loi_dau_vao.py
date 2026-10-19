"""Câu tiếng Việt cho lỗi 422 của pydantic (mục 10 sửa mức 1, 17/10/2026).

Trước đây chỉ có `{"detail": [...]}`: giao diện đọc `message` không thấy nên mọi lỗi
dữ liệu (số lượng âm, ô trống) đều hiện "Máy chủ từ chối." — không nói ô nào sai.
"""

from __future__ import annotations

import json
from typing import Any

import pydantic
import pytest
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from clinicai.api.loi_dau_vao import TOI_DA_LOI, cau_loi_dau_vao
from clinicai.api.v1.routers.pharmacy import HuyRequest, NhapLoRequest
from clinicai.main import validation_exception_handler


def _loi(kieu: str, *loc: Any, **ctx: Any) -> dict[str, Any]:
    return {"type": kieu, "loc": ("body", *loc), "msg": "x", "input": None, "ctx": ctx}


def test_so_luong_phai_lon_hon_0_noi_ro_o_nao() -> None:
    assert cau_loi_dau_vao([_loi("greater_than", "so_luong", gt=0.0)]) == (
        "Số lượng: phải lớn hơn 0."
    )


def test_dong_thu_may_va_o_nao() -> None:
    cau = cau_loi_dau_vao([_loi("string_too_short", "dong", 2, "batch_code")])
    assert cau == "Dòng 3 · Số lô: không được để trống."


@pytest.mark.parametrize(
    ("kieu", "ctx", "mong"),
    [
        ("missing", {}, "chưa nhập"),
        ("string_too_long", {"max_length": 100}, "quá dài (tối đa 100 ký tự)"),
        ("too_short", {"min_length": 1}, "cần có ít nhất một mục"),
        ("too_long", {"max_length": 200}, "quá nhiều mục (tối đa 200)"),
        ("float_parsing", {}, "phải là một con số"),
        ("uuid_parsing", {}, "không hợp lệ"),
        ("kieu_la_hoan_toan", {}, "chưa hợp lệ"),
    ],
)
def test_ly_do_theo_loai_loi(kieu: str, ctx: dict[str, Any], mong: str) -> None:
    assert cau_loi_dau_vao([_loi(kieu, "so_luong", **ctx)]).endswith(f"{mong}.")


def test_ten_o_la_giu_nguyen_va_nhieu_loi_gom_lai() -> None:
    loi = [_loi("missing", f"o_{i}") for i in range(TOI_DA_LOI + 2)]
    cau = cau_loi_dau_vao(loi)
    assert cau.startswith("o_0: chưa nhập; o_1: chưa nhập; o_2: chưa nhập")
    assert cau.endswith("và 2 lỗi khác.")


def test_dau_vao_rac_khong_nem() -> None:
    assert "kiểm tra lại" in cau_loi_dau_vao([])
    rac: dict[str, Any] = {"type": None, "loc": None, "ctx": "không phải dict"}
    assert cau_loi_dau_vao([rac]) == "Dữ liệu: chưa hợp lệ."


def test_mo_hinh_that_so_luong_am_va_o_trong() -> None:
    with pytest.raises(pydantic.ValidationError) as e1:
        NhapLoRequest.model_validate(
            {
                "drug_catalog_id": "7c4b9c3e-0000-4000-8000-000000000001",
                "so_luong": -5,
                "batch_code": "L1",
                "unit": "viên",
            }
        )
    assert cau_loi_dau_vao(e1.value.errors()) == "Số lượng: phải lớn hơn 0."
    with pytest.raises(pydantic.ValidationError) as e2:
        HuyRequest.model_validate(
            {
                "drug_batch_id": "7c4b9c3e-0000-4000-8000-000000000001",
                "so_luong": 1,
                "ly_do": "",
            }
        )
    assert cau_loi_dau_vao(e2.value.errors()) == "Lý do: không được để trống."


@pytest.mark.asyncio
async def test_bo_xu_ly_giu_detail_va_them_message() -> None:
    loi = [_loi("greater_than", "so_luong", gt=0.0)]
    r = await validation_exception_handler(
        Request({"type": "http", "method": "POST", "path": "/", "headers": []}),
        RequestValidationError(loi),
    )
    nd = json.loads(bytes(r.body))
    assert r.status_code == 422
    assert nd["error"] == "VALIDATION_ERROR"
    assert nd["message"] == "Số lượng: phải lớn hơn 0."
    assert nd["detail"][0]["type"] == "greater_than", "máy đọc vẫn có `detail`"
