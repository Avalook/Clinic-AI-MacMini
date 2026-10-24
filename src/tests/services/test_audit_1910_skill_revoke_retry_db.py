"""Read-only audit probe: skill revoke retries after a partial capability revoke."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import can
from clinicai.services.ky_nang_service import KyNangService
from clinicai.services.permission_service import PermissionService
from tests.services.test_permission_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
    quan_ly,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_skill_retry_returns_already_without_reconciling_partial_revoke(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with pool.acquire() as conn:
        staff = await _nguoi(conn, "RECEPTION")
        skill = "audit_" + uuid.uuid4().hex[:16]
        await conn.execute(
            "INSERT INTO ky_nang (clinic_id, ma, ten, lego, phong_ids)"
            " VALUES ($1::uuid, $2, 'Audit skill', $3::text[], '{}')",
            CLINIC,
            skill,
            ["bao_cao", "nhan_su"],
        )
        await conn.execute(
            "INSERT INTO nhan_su_ky_nang (clinic_id, staff_id, ky_nang_ma, gan_boi)"
            " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
            CLINIC,
            staff.staff_id,
            skill,
            quan_ly.staff_id,
        )

    permission = PermissionService(pool)
    for ma in ("bao_cao", "nhan_su"):
        await permission.doi_lego(
            staff_id=staff.staff_id, ma=ma, bat=True, identity=quan_ly
        )

    original = PermissionService.doi_lego
    revoked = 0

    async def fail_after_one_revoke(self, **kwargs):
        nonlocal revoked
        if kwargs.get("bat") is False:
            if revoked == 1:
                raise RuntimeError("synthetic failure between capability revokes")
            revoked += 1
        return await original(self, **kwargs)

    monkeypatch.setattr(PermissionService, "doi_lego", fail_after_one_revoke)
    service = KyNangService(pool)
    with pytest.raises(RuntimeError, match="between capability revokes"):
        await service.doi(staff_id=staff.staff_id, ma=skill, bat=False, identity=quan_ly)

    async with pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT count(*) FROM nhan_su_ky_nang"
            " WHERE clinic_id=$1::uuid AND staff_id=$2::uuid AND ky_nang_ma=$3",
            CLINIC,
            staff.staff_id,
            skill,
        ) == 0
        after_failure = {
            ma: await can(conn, staff, capability)
            for ma, capability in (
                ("bao_cao", "report.view"),
                ("nhan_su", "account.manage"),
            )
        }
    assert any(after_failure.values()), "the injected failure should leave a grant active"

    retry = await service.doi(staff_id=staff.staff_id, ma=skill, bat=False, identity=quan_ly)
    assert retry["already"] is True
    async with pool.acquire() as conn:
        after_retry = {
            ma: await can(conn, staff, capability)
            for ma, capability in (
                ("bao_cao", "report.view"),
                ("nhan_su", "account.manage"),
            )
        }
    assert after_retry == after_failure
