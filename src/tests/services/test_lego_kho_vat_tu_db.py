"""Lego "Kho vật tư" (14/10/2026): quyền riêng, không suy từ Kho thuốc."""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import KHOI_MO_FULL, MAN, PRESET
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.permission_service import PermissionService
from tests.services.test_permission_db import (  # noqa: F401
    _nguoi,
    pool,
    quan_ly,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def test_lego_kho_vat_tu_trong_catalogue() -> None:
    assert MAN["kho_vat_tu"].khoi == ["kho_vat_tu"]
    assert MAN["kho_vat_tu"].duong == "/kho-vat-tu"
    assert "kho_vat_tu" in KHOI_MO_FULL
    # Đối tác tuyệt đối không có; mọi vai nội bộ khác theo khối mở full.
    assert PRESET["PARTNER"] == ["doi_tac"]
    assert all("kho_vat_tu" in ks for v, ks in PRESET.items() if v != "PARTNER")


async def test_bat_tat_lego_kho_vat_tu_co_hieu_luc_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "RECEPTION")
    cua = cua_quyen("vat_tu.manage")
    with pytest.raises(SafetyGateError):
        await cua(identity=x, pool=pool)
    svc = PermissionService(pool)
    await svc.doi_lego(staff_id=x.staff_id, ma="kho_vat_tu", bat=True, identity=quan_ly)
    assert await cua(identity=x, pool=pool) is x
    await svc.doi_lego(
        staff_id=x.staff_id, ma="kho_vat_tu", bat=False, identity=quan_ly
    )
    with pytest.raises(SafetyGateError):
        await cua(identity=x, pool=pool)


async def test_kho_thuoc_khong_mo_kho_vat_tu_va_nguoc_lai(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "PHARMACIST")
    svc = PermissionService(pool)
    await svc.doi_lego(staff_id=x.staff_id, ma="kho_thuoc", bat=True, identity=quan_ly)
    async with pool.acquire() as conn:
        assert await can(conn, x, "pharmacy.dispense")
        assert not await can(conn, x, "vat_tu.manage")
    await svc.doi_lego(staff_id=x.staff_id, ma="kho_vat_tu", bat=True, identity=quan_ly)
    await svc.doi_lego(staff_id=x.staff_id, ma="kho_thuoc", bat=False, identity=quan_ly)
    async with pool.acquire() as conn:
        assert await can(conn, x, "vat_tu.manage")
        assert not await can(conn, x, "pharmacy.dispense")
