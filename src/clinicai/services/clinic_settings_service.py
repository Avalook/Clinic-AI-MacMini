"""Clinic settings maintenance (booking policy, per-tenant).

C.3 made the slot length and the two seat counts live in
``clinic.settings->booking``, and every writer already reads the same row —
``clinic_policy.py`` for the sentence, ``enforce_slot_capacity`` for the net.
What was missing was a *write path*: today the only way to change these numbers
is an UPDATE by hand in the Supabase SQL editor. This service is that write
path, and it is deliberately small because the CHECK constraint
``clinic_booking_policy_valid`` is the real gate. A bad value is rejected at
write time with a comprehensible constraint error, not discovered at 8am when
no appointment can be booked.

A clinic that changes its numbers changes both the sentence the receptionist
sees and the guarantee behind it in one UPDATE — and because the read always
filters by ``clinic_id``, the change never leaks into another clinic.
"""

from __future__ import annotations

import json

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.clinic_policy import ClinicPolicy

logger = structlog.get_logger()


class ClinicSettingsService:
    """One clinic's operational settings."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def update_booking_policy(
        self,
        *,
        identity: StaffIdentity,
        slot_minutes: int,
        regular_cap: int,
        walkin_cap: int,
    ) -> dict[str, int]:
        """Write this clinic's booking policy, then return the saved values.

        The clinic is taken from ``identity.clinic_id`` — never from the body.
        Besides being a safety rule, that makes the call naturally scoped: this
        can only ever update the caller's own clinic, so a booking-policy edit
        at clinic A structurally cannot change clinic B.

        The ``clinic_booking_policy_valid`` CHECK constraint is the hard gate;
        constructing a ``ClinicPolicy`` first turns a database error into a
        422 with the same message, which the UI can show directly.
        """
        # Validate before touching the DB so a bad number is a 422, not a
        # CheckViolationError that the middleware maps to 500/409.
        policy = ClinicPolicy(
            slot_minutes=slot_minutes,
            regular_cap=regular_cap,
            walkin_cap=walkin_cap,
        )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.fetchval(
                    """
                    UPDATE clinic
                       SET settings = jsonb_set(
                               settings,
                               '{booking}',
                               $2::jsonb,
                               true
                           ),
                           updated_at = now()
                     WHERE id = $1::uuid
                    RETURNING id
                    """,
                    identity.clinic_id,
                    json.dumps(
                        {
                            "slot_minutes": policy.slot_minutes,
                            "regular_cap": policy.regular_cap,
                            "walkin_cap": policy.walkin_cap,
                        }
                    ),
                )
                if updated is None:
                    # The identity middleware guarantees an active membership,
                    # so the clinic row exists. This is a defensive check.
                    raise ValidationError("Phòng khám không tồn tại")

                await conn.execute(
                    """
                    INSERT INTO event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'clinic_settings.booking_policy_updated',
                            'clinic', $1::uuid, $2, $3,
                            'api:clinic-settings', FALSE)
                    """,
                    identity.clinic_id,
                    json.dumps(
                        {
                            "slot_minutes": policy.slot_minutes,
                            "regular_cap": policy.regular_cap,
                            "walkin_cap": policy.walkin_cap,
                        }
                    ),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "clinic_staff_id": identity.staff_id,
                            "actor_auth_user_id": identity.auth_user_id,
                            "origin": "api:clinic-settings",
                        }
                    ),
                )

        logger.info(
            "booking_policy_updated",
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            slot_minutes=policy.slot_minutes,
            regular_cap=policy.regular_cap,
            walkin_cap=policy.walkin_cap,
        )
        return {
            "slot_minutes": policy.slot_minutes,
            "regular_cap": policy.regular_cap,
            "walkin_cap": policy.walkin_cap,
        }

    # ── Feature Mode ──────────────────────────────────────────────────────

    VALID_MODES = ("CSKH_ONLY", "FULL_CLINIC")

    async def get_feature_mode(
        self, *, clinic_id: str
    ) -> str:
        """Read the feature_mode for a clinic. Defaults to FULL_CLINIC."""
        async with self._pool.acquire() as conn:
            raw = await conn.fetchval(
                "SELECT settings->'feature_mode' FROM clinic WHERE id = $1::uuid",
                clinic_id,
            )
        if raw is None:
            return "FULL_CLINIC"
        # JSONB text comes back with quotes → strip them.
        mode = raw.strip('"') if isinstance(raw, str) else str(raw)
        return mode if mode in self.VALID_MODES else "FULL_CLINIC"

    async def update_feature_mode(
        self,
        *,
        identity: StaffIdentity,
        mode: str,
    ) -> dict[str, str]:
        """Set the feature_mode for the caller's clinic. MANAGEMENT only."""
        if mode not in self.VALID_MODES:
            valid = ", ".join(self.VALID_MODES)
            raise ValidationError(
                f"Chế độ không hợp lệ: {mode}. Chấp nhận: {valid}"
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                updated = await conn.fetchval(
                    """
                    UPDATE clinic
                       SET settings = jsonb_set(
                               settings,
                               '{feature_mode}',
                               to_jsonb($2::text),
                               true
                           ),
                           updated_at = now()
                     WHERE id = $1::uuid
                    RETURNING id
                    """,
                    identity.clinic_id,
                    mode,
                )
                if updated is None:
                    raise ValidationError("Phòng khám không tồn tại")

                await conn.execute(
                    """
                    INSERT INTO event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'clinic_settings.feature_mode_updated',
                            'clinic', $1::uuid, $2, $3,
                            'api:clinic-settings', FALSE)
                    """,
                    identity.clinic_id,
                    json.dumps({"feature_mode": mode}),
                    json.dumps(
                        {
                            "clinic_role": identity.role.value,
                            "clinic_staff_id": identity.staff_id,
                            "actor_auth_user_id": identity.auth_user_id,
                            "origin": "api:clinic-settings",
                        }
                    ),
                )

        logger.info(
            "feature_mode_updated",
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            mode=mode,
        )
        return {"mode": mode}
