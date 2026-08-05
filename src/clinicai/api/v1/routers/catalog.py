"""Read-only catalog endpoints — static reference data with caching.

Phase 4 of the System Design completion plan (Bài 6 — Caching, right-sized).

These endpoints serve rarely-changing lookup data (wards, service types) with
``Cache-Control`` headers so browsers and proxies cache them instead of
hitting the DB on every page load.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool

router = APIRouter(tags=["catalog"])

# 1 hour cache — ward list and service types change extremely rarely.
CACHE_MAX_AGE = 3600


def _cached_json(data: list[dict[str, Any]]) -> JSONResponse:
    """JSON with cache headers for reference data shared by every clinic."""
    return JSONResponse(
        content=data,
        headers={
            "Cache-Control": f"public, max-age={CACHE_MAX_AGE}",
            "Vary": "Accept",
        },
    )


def _private_json(data: list[dict[str, Any]]) -> JSONResponse:
    """JSON for a PER-CLINIC response.

    These used to be `Cache-Control: public`, which was accurate while the
    catalogue was global. Now that the rows are the caller's clinic's, a shared
    cache in front of the API could hand one clinic's price list to another —
    so they are private and revalidated.
    """
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "private, no-store", "Vary": "Authorization"},
    )


@router.get("/catalog/wards")
async def list_wards(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """Danh mục phường/xã. Cached for 1 hour.

    ``ward`` khoá theo ``code``, KHÔNG có ``id`` và không có ``parent_id``: quan
    hệ lên trên là ``province_code``. Câu cũ chọn cả ba cột không tồn tại nên
    endpoint này trả 500 mọi lần được gọi — không ai thấy vì chưa màn hình nào
    gọi tới. ``src/tests/migrations/test_sql_columns_exist.py`` canh chỗ này.

    Docstring cũ ghi "tỉnh/thành phố" cũng sai: cấp tỉnh là bảng ``province``.
    """
    rows = await pool.fetch(
        "SELECT code, name, full_name, province_code FROM ward ORDER BY name"
    )
    return _cached_json([dict(r) for r in rows])


@router.get("/catalog/service-types")
async def list_service_types(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """The caller's clinic's service types.

    Bốn cột câu cũ chọn — ``aliases``, ``category``, ``base_price_vnd``,
    ``sort_order`` — không tồn tại trong bất kỳ migration nào, nên endpoint này
    cũng trả 500 mọi lần được gọi. Giá dịch vụ nằm ở bảng riêng
    (``/api/v1/service-prices``), không phải một cột của ``service_type``.
    """
    rows = await pool.fetch(
        """
        SELECT id, code, name, default_duration_minutes, is_active
        FROM service_type
        WHERE is_active IS NOT FALSE AND clinic_id = $1::uuid
        ORDER BY name
        """,
        identity.clinic_id,
    )
    return _private_json([dict(r) for r in rows])


@router.get("/catalog/booking-channels")
async def list_booking_channels(
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """The caller's clinic's booking channels."""
    rows = await pool.fetch(
        "SELECT id, name, is_active FROM booking_channel "
        "WHERE clinic_id = $1::uuid ORDER BY name",
        identity.clinic_id,
    )
    return _private_json([dict(r) for r in rows])
