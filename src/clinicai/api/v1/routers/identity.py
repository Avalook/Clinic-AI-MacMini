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

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import (
    StaffIdentity,
    get_current_identity,
    get_display_identity,
)
from clinicai.core.database import get_db_pool

router = APIRouter()


@router.get("/me")
async def me(
    identity: StaffIdentity = Depends(get_display_identity),
) -> dict[str, object]:
    """Return the verified staff identity + derived role for the bearer token.

    Nhận cả vai DISPLAY (tài khoản màn hình TV). Bắt buộc, không phải nới lỏng:
    layout của trình duyệt hỏi chính đường này để biết mình là ai, rồi mới đưa
    tài khoản màn hình sang /display. Chặn ở đây thì cái tivi đăng nhập xong bị
    đá ngược về trang đăng nhập — đăng nhập được nhưng không vào được đâu cả.

    An toàn vì phản hồi CHỈ mô tả CHÍNH người gọi: tên tài khoản, vai, phòng
    khám, cơ sở. Không một dòng dữ liệu bệnh nhân nào.
    """
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


@router.get("/me/vi-tri-hom-nay")
async def vi_tri_hom_nay(
    # CỬA THƯỜNG, KHÔNG PHẢI `get_display_identity`. Cửa kia cố tình dễ dãi nên
    # phải hiếm (`test_chi_dung_mot_duong_mo_cho_man_hinh`), và ở đây không cần:
    # tài khoản TV và đối tác bị layout đẩy sang màn riêng TRƯỚC khi thanh bên
    # kịp hỏi đường này.
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, object]:
    """Hôm nay người gọi đứng những VỊ TRÍ nào — để thanh bên đi theo việc thật.

    Tuyền chốt 16/09/2026: *"các node bên sidebar phải là theo vị trí chứ không
    ấn định"*. Hai tuần lịch Kim Ngưu cho thấy một điều dưỡng đứng tới tám vị
    trí ở ba tầng; thanh bên theo VAI cố định thì hôm cô ấy đứng quầy thuốc,
    menu vẫn mời cô ấy vào màn siêu âm.

    CHỈ TRẢ MÃ VỊ TRÍ, KHÔNG TRẢ MÀN HÌNH. Vị trí nào mở màn nào là chuyện trình
    bày, nằm ở `nav-items.ts`. Đây là dữ kiện: "hôm nay bạn đứng đâu".

    KHÔNG PHẢI CỬA KHOÁ. Quyền vẫn ở chỗ cũ (và đang mở tạm, xem
    `identity.mo_quyen_tam_thoi`). Rỗng — không có ca hôm nay — thì thanh bên
    rơi về menu theo vai như trước, chứ không trống trơn.
    """
    rows = await pool.fetch(
        """
        SELECT DISTINCT station, shift
          FROM public.work_roster
         WHERE clinic_id = $1::uuid
           AND staff_id = $2::uuid
           AND work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           AND status <> 'REJECTED'
         ORDER BY station
        """,
        identity.clinic_id,
        identity.staff_id,
    )
    return {
        "vi_tri": [r["station"] for r in rows],
        "ca": sorted({r["shift"] for r in rows}),
    }
