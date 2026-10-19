"""Input gates for manual pharmacy inventory writes."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.pharmacy import (
    DieuChinhRequest,
    HuyRequest,
    NhapLoRequest,
)
from clinicai.services.pharmacy_service import PharmacyService, _kiem_don_vi_cung_lo


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="d0000000-0000-4000-8000-000000000001",
        auth_user_id="u1",
        full_name="Dược sĩ kiểm thử",
        department=ClinicRole.PHARMACIST.value,
        role=ClinicRole.PHARMACIST,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def test_cung_ma_lo_kiem_don_vi_o_tat_ca_noi_chua() -> None:
    hang = [
        {"noi_chua": "KHO", "unit": "hộp"},
        {"noi_chua": "QUAY", "unit": "viên"},
    ]
    with pytest.raises(ConflictError, match="đơn vị viên"):
        _kiem_don_vi_cung_lo(hang, batch_code="LO-1", unit="hộp")

    _kiem_don_vi_cung_lo(
        [{"noi_chua": "KHO", "unit": " HỘP "}, {"noi_chua": "QUAY", "unit": "hộp"}],
        batch_code="LO-1",
        unit="hộp",
    )


class _PoolKhongDuocMo:
    def acquire(self) -> Any:  # pragma: no cover - reaching the pool is the bug
        raise AssertionError("Đầu vào không hữu hạn đã chạm database")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_api_tu_choi_so_luong_khong_huu_han(value: float) -> None:
    chung = {
        "drug_batch_id": "b0000000-0000-4000-8000-000000000001",
        "so_luong": value,
        "ly_do": "Kiểm kê",
    }
    for model in (DieuChinhRequest, HuyRequest):
        with pytest.raises(PydanticValidationError):
            model.model_validate(chung)

    with pytest.raises(PydanticValidationError):
        NhapLoRequest.model_validate(
            {
                "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
                "so_luong": value,
                "batch_code": "LO-1",
                "expiry_date": "2099-12-31",
                "unit": "viên",
            }
        )

    with pytest.raises(PydanticValidationError):
        NhapLoRequest.model_validate(
            {
                "drug_catalog_id": "c0000000-0000-4000-8000-000000000001",
                "so_luong": 1,
                "batch_code": "LO-1",
                "expiry_date": "2099-12-31",
                "unit": "viên",
                "cost_price": value,
            }
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_service_dieu_chinh_tu_choi_so_luong_khong_huu_han(
    value: float,
) -> None:
    with pytest.raises(ValidationError, match="một con số"):
        await PharmacyService(_PoolKhongDuocMo()).dieu_chinh(
            identity=_identity(),
            drug_batch_id="b0000000-0000-4000-8000-000000000001",
            so_luong=value,
            ly_do="Kiểm kê",
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_service_huy_tu_choi_so_luong_khong_huu_han(value: float) -> None:
    with pytest.raises(ValidationError, match="một con số"):
        await PharmacyService(_PoolKhongDuocMo()).huy(
            identity=_identity(),
            drug_batch_id="b0000000-0000-4000-8000-000000000001",
            so_luong=value,
            ly_do="Huỷ lô hỏng",
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.asyncio
async def test_service_nhap_lo_tu_choi_gia_nhap_khong_huu_han(value: float) -> None:
    with pytest.raises(ValidationError, match="Giá nhập"):
        await PharmacyService(_PoolKhongDuocMo()).nhap_lo(
            identity=_identity(),
            drug_catalog_id="c0000000-0000-4000-8000-000000000001",
            so_luong=1,
            batch_code="LO-1",
            expiry_date=None,
            unit="viên",
            cost_price=value,
        )
