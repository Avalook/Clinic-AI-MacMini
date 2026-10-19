"""Danh mục vật tư không được làm đổi dịch vụ và không nuốt số rác."""

from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.v1.routers.config import PriceUpdateRequest
from clinicai.services.config_service import PriceListService
from clinicai.services.danh_muc_dich_vu_service import doc_vat_tu
from tests.services.test_vat_tu_kho_db import _bo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_sua_va_doc_du_cot(pool: asyncpg.Pool) -> None:
    identity, vt, _ = await _bo(pool)
    patch: dict[str, Any] = {
        "loai_vat_tu": "VPP",
        "gia_nhap": "2500",
        "don_vi": " hộp ",
        "ma_vach": "0123456789",
        "can_duyet_nhap": True,
        "can_ql_duyet": True,
        "chon_nhanh": True,
        "kinh_doanh": False,
    }
    body = PriceUpdateRequest(**patch)
    assert body.model_dump(include=set(patch)) == patch
    await PriceListService(pool).update(price_id=vt, identity=identity, vat_tu=patch)
    async with pool.acquire() as conn:
        row = next(
            r for r in await doc_vat_tu(conn, identity.clinic_id) if r["id"] == vt
        )
    for field, value in patch.items():
        assert row[field] == (
            "hộp" if field == "don_vi" else 2500 if field == "gia_nhap" else value
        )
    assert row["unit_price"] is None  # giá nhập không trở thành giá bán
    await PriceListService(pool).update(
        price_id=vt,
        identity=identity,
        vat_tu={"gia_nhap": None, "ma_vach": "", "can_ql_duyet": False},
    )
    raw = await pool.fetchrow(
        "SELECT gia_nhap_vat_tu,ma_vach_vat_tu,can_ql_duyet"
        " FROM service_price WHERE id=$1::uuid",
        vt,
    )
    assert tuple(raw.values()) == (None, None, False)


@pytest.mark.parametrize("rac", ["rác", "NaN", "Infinity", -1, True, "1.5", "1e99"])
async def test_gia_nhap_rac_khong_ghi(pool: asyncpg.Pool, rac: Any) -> None:
    identity, vt, _ = await _bo(pool)
    await PriceListService(pool).update(
        price_id=vt, identity=identity, vat_tu={"gia_nhap": 2500}
    )
    with pytest.raises(ValidationError):
        await PriceListService(pool).update(
            price_id=vt, identity=identity, vat_tu={"gia_nhap": rac}
        )
    assert await pool.fetchval(
        "SELECT gia_nhap_vat_tu FROM service_price WHERE id=$1::uuid", vt
    ) == Decimal(2500)


async def test_cot_vat_tu_khong_sua_dich_vu(pool: asyncpg.Pool) -> None:
    identity, vt, _ = await _bo(pool)
    await pool.execute(
        "UPDATE service_price SET \"group\"='dich_vu' WHERE id=$1::uuid", vt
    )
    try:
        with pytest.raises(ValidationError):
            await PriceListService(pool).update(
                price_id=vt, identity=identity, vat_tu={"chon_nhanh": True}
            )
    finally:
        await pool.execute(
            "UPDATE service_price SET \"group\"='vat_tu' WHERE id=$1::uuid", vt
        )


async def test_khong_kinh_doanh_khong_duoc_ban(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_service import VatTuService
    from tests.services.test_tien_thuoc_cp1_db import tao_quay
    from tests.services.test_vat_tu_ban_them_db import _vt

    q = await tao_quay(pool)
    vt = await _vt(q, "Vật tư phân loại", 300000)
    await PriceListService(pool).update(
        price_id=vt, identity=q.thu_ngan, vat_tu={"kinh_doanh": False}
    )
    with pytest.raises(ValidationError):
        await VatTuService(pool).them(
            visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan, so_luong=1
        )


@pytest.mark.parametrize(
    "patch",
    [
        {"loai_vat_tu": "sai"},
        {"chon_nhanh": "false"},
        {"can_ql_duyet": None},
        {"ma_vach": "x" * 121},
        {"don_vi": "x" * 41},
        {"thue": 10},
    ],
)
async def test_patch_rac(pool: asyncpg.Pool, patch: dict[str, Any]) -> None:
    identity, vt, _ = await _bo(pool)
    with pytest.raises(ValidationError):
        await PriceListService(pool).update(
            price_id=vt, identity=identity, vat_tu=patch
        )
