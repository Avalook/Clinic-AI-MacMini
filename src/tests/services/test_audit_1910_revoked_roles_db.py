"""Audit: revoking the final capability must not restore legacy access."""

# ruff: noqa: F811 -- imported fixture follows the repository convention.

from __future__ import annotations

from dataclasses import replace

import asyncpg
import pytest

from clinicai.api.identity import doc_vai_theo_lego
from clinicai.permissions.can import can
from clinicai.services.tep_ket_qua_service import doc_duoc_tep_ket_qua
from tests.services.test_phieu_kham_db import _nguoi, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_revoking_all_capabilities_does_not_restore_result_access(
    pool: asyncpg.Pool,
) -> None:
    async with pool.acquire() as conn:
        doctor = await _nguoi(conn, "DOCTOR")
        await conn.execute(
            "UPDATE capability_grant SET revoked_at=now(),revoked_by=$1::uuid,"
            " ly_do='Synthetic audit: revoke all work packs'"
            " WHERE staff_id=$1::uuid AND revoked_at IS NULL", doctor.staff_id
        )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM v_quyen_thuc_te WHERE clinic_id=$1::uuid"
            " AND staff_id=$2::uuid",
            doctor.clinic_id,
            doctor.staff_id,
        )
        == 0
    )
    roles = await doc_vai_theo_lego(
        pool, doctor.clinic_id, doctor.staff_id, doctor.role
    )
    identity = replace(doctor, vai_theo_lego=roles)
    async with pool.acquire() as conn:
        assert not await can(conn, identity, "clinical.consult.perform")
        allowed = await doc_duoc_tep_ket_qua(conn, identity)
    assert allowed is False, "Legacy role restored result access after final revoke"
