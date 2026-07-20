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

from clinicai.core.database import get_db_pool

router = APIRouter(tags=["catalog"])

# 1 hour cache — ward list and service types change extremely rarely.
CACHE_MAX_AGE = 3600


def _cached_json(data: list[dict[str, Any]]) -> JSONResponse:
    """Return JSON with cache headers for static reference data."""
    return JSONResponse(
        content=data,
        headers={
            "Cache-Control": f"public, max-age={CACHE_MAX_AGE}",
            "Vary": "Accept",
        },
    )


@router.get("/catalog/wards")
async def list_wards(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """List all wards (tỉnh/thành phố). Cached for 1 hour."""
    rows = await pool.fetch("SELECT id, name, parent_id FROM ward ORDER BY name")
    return _cached_json([dict(r) for r in rows])


@router.get("/catalog/service-types")
async def list_service_types(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """List all service types. Cached for 1 hour."""
    rows = await pool.fetch(
        """
        SELECT id, name, aliases, category, base_price_vnd,
               is_active, sort_order
        FROM service_type
        WHERE is_active IS NOT FALSE
        ORDER BY sort_order, name
        """
    )
    return _cached_json([dict(r) for r in rows])


@router.get("/catalog/booking-channels")
async def list_booking_channels(
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> JSONResponse:
    """List all booking channels. Cached for 1 hour."""
    rows = await pool.fetch(
        "SELECT id, name, is_active FROM booking_channel ORDER BY name"
    )
    return _cached_json([dict(r) for r in rows])
