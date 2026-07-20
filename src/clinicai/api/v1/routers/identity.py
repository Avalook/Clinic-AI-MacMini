"""Identity endpoint — the frontend reads the caller's role/identity from HERE
(server-authoritative), instead of a self-chosen cookie."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, get_current_identity

router = APIRouter()


@router.get("/me")
async def me(
    identity: StaffIdentity = Depends(get_current_identity),
) -> dict[str, object]:
    """Return the verified staff identity + derived role for the bearer token."""
    return {
        "staff_id": identity.staff_id,
        "full_name": identity.full_name,
        "department": identity.department,
        "role": identity.role.value,
        "can_write_clinical": identity.can_write_clinical(),
        "is_doctor": identity.is_doctor(),
        "is_cashier": identity.is_cashier(),
    }
