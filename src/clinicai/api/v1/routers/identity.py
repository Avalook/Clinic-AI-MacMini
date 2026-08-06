"""Identity endpoint — the frontend reads the caller's role/identity from HERE
(server-authoritative), instead of deriving it a second time for itself.

WHAT CHANGED, AND WHY IT IS MORE THAN COSMETIC. The dashboard used to answer
"who is this" with its own Supabase query (``lib/current-staff.ts``): staff row
by ``auth_user_id``, embed the active ``clinic_membership``, read the role off
it. That is the same rule as ``get_current_identity`` — written twice, in two
languages, and the two copies had already drifted at the edge that matters. An
unknown role code lands on ``CSKH`` here (least privilege, but still a working
session) and on ``null`` there (no session at all, bounced to /login). Same
database row, two different answers about who you are.

So this response carries the WHOLE session the dashboard renders from, not just
the role: names and places included. Anything left out is a field the frontend
would have to go fetch on its own, which is how the second copy grew the first
time.
"""

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
        "auth_user_id": identity.auth_user_id,
        "full_name": identity.full_name,
        "short_name": identity.short_name,
        "department": identity.department,
        "role": identity.role.value,
        "clinic_id": identity.clinic_id,
        "clinic_name": identity.clinic_name,
        "location_id": identity.location_id,
        "location_name": identity.location_name,
        # Ba câu trả lời SẴN, không phải ba luật để frontend chép lại. Đây đúng
        # là chỗ hai bản từng lệch nhau: trình duyệt hỏi "có phải bác sĩ không"
        # bằng tập RỘNG (gồm cả TKYK) rồi vẽ nút "Chỉ định XN", còn lab.py gác
        # bằng tập HẸP — thư ký y khoa bấm vào và ăn 403.
        "can_write_clinical": identity.can_write_clinical(),
        "is_doctor": identity.is_doctor(),
        "is_cashier": identity.is_cashier(),
    }
