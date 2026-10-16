"""Quan sát bể kết nối trên Postgres thật (14/10/2026).

Hai việc:
  1. `gan_do_pool` đo ĐÚNG thời gian chờ mượn trên asyncpg thật (bắt việc nâng
     asyncpg làm mất `Pool._acquire`).
  2. KHÔNG mượn kết nối thứ hai khi đang giữ kết nối thứ nhất (`doi_lich_phong`):
     bể một kết nối mà code lồng thì treo mãi — đúng cách bể kín thành sự cố.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core import quan_sat as qs
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import lich

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CLINIC = "a0000000-0000-4000-8000-000000000001"


def _dsn() -> str:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture
async def pool_2() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=2)
    try:
        yield p
    finally:
        await p.close()


@pytest_asyncio.fixture
async def pool_1() -> AsyncIterator[asyncpg.Pool]:
    p = await asyncpg.create_pool(dsn=_dsn(), min_size=1, max_size=1)
    try:
        yield p
    finally:
        await p.close()


async def test_do_cho_muon_tren_asyncpg_that(
    pool_2: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    moi = qs.QuanSat()
    monkeypatch.setattr(qs, "quan_sat", moi)
    assert qs.gan_do_pool(pool_2) is True
    # 4 request, bể 2 kết nối, mỗi request giữ 0,4s → hai request phải chờ ~0,4s.
    await asyncio.gather(*(pool_2.fetchval("SELECT pg_sleep(0.4)") for _ in range(4)))
    p = moi.chot_phut()["pool"]
    assert p["toi_da"] == 2 and p["so_muon"] >= 4
    assert p["so_muon_phai_cho"] >= 2
    assert p["cho_max_ms"] >= 300
    assert p["dang_cho_max"] >= 3
    assert moi.dang_cho() == 0
    t = moi.tuc_thoi()
    assert t["toi_da"] == 2 and t["ban"] == 0 and t["dang_cho"] == 0


async def test_doi_lich_phong_khong_muon_ket_noi_thu_hai(
    pool_1: asyncpg.Pool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bể 1 kết nối + đang giữ nó: nếu `doi_lich_phong` mượn thêm một cái nữa
    (như bản trước 14/10: `pool.fetch` trong `doc_vi_tri_hien_hanh`) thì treo."""

    async def _bat(*_a: Any, **_k: Any) -> bool:
        return True

    async def _tat(*_a: Any, **_k: Any) -> bool:
        return False

    monkeypatch.setattr(lich, "doc_day", _bat)  # công tắc quyền theo lịch: BẬT
    monkeypatch.setattr(lich, "can", _tat)  # không phải người điều phối
    nguoi = StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Test lịch",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id=CLINIC,
        location_id=str(uuid.uuid4()),
        location_name="Cơ sở test",
    )
    async with pool_1.acquire() as conn:
        with pytest.raises(SafetyGateError):  # chưa có ca → bị chặn, KHÔNG treo
            await asyncio.wait_for(
                lich.doi_lich_phong(conn, pool_1, nguoi, str(uuid.uuid4())),
                timeout=5,
            )
