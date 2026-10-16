"""Chốt hạn dùng của Postgres trả xung đột 409 có hướng xử lý."""

from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest
from starlette.requests import Request

from clinicai.api.v1.routers.pharmacy import NhapLoRequest, nhap_lo
from clinicai.main import exclusion_violation_handler


async def test_sql_chan_han_lo_tra_409_tieng_viet() -> None:
    exc = asyncpg.ExclusionViolationError.new(
        {"C": "23P01", "M": "Lô hết hạn", "n": "lo_het_han"}
    )
    response = await exclusion_violation_handler(Request({"type": "http"}), exc)
    assert response.status_code == 409
    body = json.loads(bytes(response.body))
    assert "hết hạn" in str(body)
    assert "đổi lô" in str(body)
    assert "hoàn" in str(body)


@pytest.mark.parametrize("han", [None, "", "ngày rác", "2026-02-30", 123, {}])
def test_nhap_lo_han_rong_hoac_rac_tra_none(han: object) -> None:
    body = NhapLoRequest.model_validate(
        {
            "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
            "so_luong": 10,
            "batch_code": "LO-1",
            "unit": "viên",
            "expiry_date": han,
        }
    )
    assert body.expiry_date is None


async def test_nhap_lo_bo_han_truyen_none_vao_service() -> None:
    body = NhapLoRequest.model_validate(
        {
            "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
            "so_luong": 10,
            "batch_code": "LO-1",
            "unit": "viên",
        }
    )
    service = AsyncMock(return_value={"id": "lo-moi"})
    with patch("clinicai.api.v1.routers.pharmacy.PharmacyService.nhap_lo", service):
        result = await nhap_lo(
            body, identity=AsyncMock(clinic_id="clinic"), pool=AsyncMock()
        )
    assert result == {"id": "lo-moi"}
    assert service.await_args is not None
    assert service.await_args.kwargs["expiry_date"] is None


@pytest.mark.parametrize("han", ["2019-01-01", "2026-10-14", date(2026, 10, 14)])
def test_nhap_lo_giu_han_hop_le(han: object) -> None:
    body = NhapLoRequest.model_validate(
        {
            "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
            "so_luong": 10,
            "batch_code": "LO-1",
            "unit": "viên",
            "expiry_date": han,
        }
    )
    assert body.expiry_date == (
        date.fromisoformat(han) if isinstance(han, str) else han
    )


@pytest.mark.parametrize(
    ("ten", "cau"),
    [
        ("lo_o_kho", "đang ở KHO"),
        ("lo_het_han_quay", "không chuyển ra quầy"),
    ],
)
async def test_sql_chan_kho_quay_tra_409_dung_cau(ten: str, cau: str) -> None:
    exc = asyncpg.ExclusionViolationError.new({"C": "23P01", "M": "x", "n": ten})
    response = await exclusion_violation_handler(Request({"type": "http"}), exc)
    assert response.status_code == 409
    assert cau in str(json.loads(bytes(response.body)))
