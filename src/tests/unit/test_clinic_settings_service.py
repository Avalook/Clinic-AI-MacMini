"""ClinicSettingsService — write path for the booking policy (C.3).

The read side (clinic_policy.py) is already covered. What this service adds is
the UPDATE: it must write to the caller's OWN clinic only, validate before
touching the DB, and leave an audit trail. The CHECK constraint in the database
is the real gate; these tests prove the service does not bypass it and does not
leak across tenants.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.clinic_policy import ClinicPolicyError
from clinicai.services.clinic_settings_service import ClinicSettingsService


def _identity(clinic_id: str | None = None) -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(uuid4()),
        auth_user_id=str(uuid4()),
        full_name="Test User",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=clinic_id or str(uuid4()),
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _mock_pool_and_conn() -> tuple[MagicMock, AsyncMock]:
    """Return (pool, conn) with pool.acquire() wired as async ctx mgr."""
    pool = MagicMock()
    acquire_ctx = AsyncMock()
    conn = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    transaction_ctx = AsyncMock()
    transaction_ctx.__aenter__.return_value = conn
    conn.transaction = MagicMock(return_value=transaction_ctx)
    return pool, conn


class TestUpdateBookingPolicy:
    @pytest.mark.asyncio
    async def test_writes_to_the_callers_own_clinic(self) -> None:
        pool, conn = _mock_pool_and_conn()
        conn.fetchval.return_value = uuid4()  # UPDATE ... RETURNING id
        svc = ClinicSettingsService(pool)
        identity = _identity()

        result = await svc.update_booking_policy(
            identity=identity,
            slot_minutes=30,
            regular_cap=3,
            walkin_cap=2,
        )

        assert result == {"slot_minutes": 30, "regular_cap": 3, "walkin_cap": 2}
        # The UPDATE must filter by identity.clinic_id — never a body value.
        update_sql = conn.fetchval.await_args.args[0]
        assert "WHERE id = $1::uuid" in update_sql
        assert conn.fetchval.await_args.args[1] == identity.clinic_id

    @pytest.mark.asyncio
    async def test_invalid_values_are_rejected_before_the_database(self) -> None:
        pool, conn = _mock_pool_and_conn()
        svc = ClinicSettingsService(pool)

        with pytest.raises(ClinicPolicyError):
            await svc.update_booking_policy(
                identity=_identity(),
                slot_minutes=45,  # does not divide 60
                regular_cap=2,
                walkin_cap=1,
            )
        # No SQL should have been issued for a rejected policy.
        conn.fetchval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_a_missing_clinic_row_is_a_validation_error(self) -> None:
        pool, conn = _mock_pool_and_conn()
        conn.fetchval.return_value = None  # UPDATE matched no row
        svc = ClinicSettingsService(pool)

        with pytest.raises(ValidationError, match="Phòng khám không tồn tại"):
            await svc.update_booking_policy(
                identity=_identity(),
                slot_minutes=15,
                regular_cap=2,
                walkin_cap=1,
            )

    @pytest.mark.asyncio
    async def test_audit_event_is_written_in_the_same_transaction(self) -> None:
        pool, conn = _mock_pool_and_conn()
        conn.fetchval.return_value = uuid4()
        svc = ClinicSettingsService(pool)

        await svc.update_booking_policy(
            identity=_identity(),
            slot_minutes=15,
            regular_cap=2,
            walkin_cap=1,
        )

        # Two SQL calls: UPDATE clinic + INSERT event_log.
        assert conn.fetchval.await_count == 1
        assert conn.execute.await_count == 1
        insert_sql = conn.execute.await_args.args[0]
        assert "INSERT INTO event_log" in insert_sql
        assert "clinic_settings.booking_policy_updated" in insert_sql
