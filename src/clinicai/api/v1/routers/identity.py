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
    doc_vi_tri_hien_hanh,
    get_current_identity,
    get_display_identity,
    vai_theo_thu_tu,
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
    # CÙNG BỘ LỌC VỚI CỬA GÁC (S0-7, 18/09/2026): chỉ ca ĐÃ DUYỆT và ĐANG
    # TRONG GIỜ CA. Trước đó thanh bên lấy cả ngày và cả dòng chưa duyệt.
    hien_hanh = await doc_vi_tri_hien_hanh(pool, identity.clinic_id, identity.staff_id)
    vi_tri = list(dict.fromkeys(tram for tram, _ca in hien_hanh))
    # DANH MỤC VỊ TRÍ + PHÒNG CỦA TỪNG VỊ TRÍ (CORE-C, 23/09/2026) — dữ kiện,
    # đọc từ `vi_tri_lam_viec`, không còn viết cứng trong giao diện:
    #   * `phong`: thanh bên dựng `/phong/<room_id>` và ghi TÊN phòng hiện tại.
    #     Đổi tên phòng là thanh bên đổi theo.
    #   * `danh_muc`: bảng lịch làm việc, màn phạm vi vị trí, thông báo ca trực
    #     đọc tên/tầng/phòng của vị trí từ đây (C4).
    # Trả MỌI vị trí đang dùng (~35 dòng), không chỉ vị trí hôm nay: giao diện
    # còn đổi mã vị trí đời cũ (`MA_VI_TRI_CU`) rồi mới tra. Đi chung lời gọi
    # này vì layout vốn đã gọi nó ở mọi trang — không thêm một vòng mạng.
    rows = await pool.fetch(
        """
        SELECT v.code, v.ten, v.ten_ngan, v.tang, v.phong, v.nhom_nghe,
               r.id::text AS room_id, r.name AS ten_phong
          FROM public.vi_tri_lam_viec v
          LEFT JOIN public.clinic_room r
            ON r.id = v.room_id AND r.clinic_id = v.clinic_id AND r.is_active
         WHERE v.clinic_id = $1::uuid AND v.is_active
         ORDER BY v.sort, v.code
        """,
        identity.clinic_id,
    )
    phong = {
        r["code"]: {"room_id": r["room_id"], "ten": r["ten_phong"]}
        for r in rows
        if r["room_id"]
    }
    danh_muc = [
        {
            "code": r["code"],
            "ten": r["ten"],
            "ten_ngan": r["ten_ngan"] or r["ten"],
            "tang": r["tang"] or "",
            "phong": r["phong"] or "",
            "nhom": r["nhom_nghe"],
        }
        for r in rows
    ]
    return {
        "vi_tri": vi_tri,
        "phong": phong,
        "danh_muc": danh_muc,
        "ca": sorted({ca for _tram, ca in hien_hanh}),
        # Vai vận hành lịch hôm nay cấp thêm — cùng luật cửa gác dùng
        # (`identity.vai_tu_vi_tri`), để giao diện không tự suy lại.
        "vai": vai_theo_thu_tu(vi_tri, identity.role),
        # MỌI vai hiệu lực — gồm vai lego đang bật mang lại, và KHÔNG gồm vai
        # tài khoản mà lego đã tắt (Tuyền chốt 26/09/2026). Giao diện dựng cửa
        # trang và nút Bàn khám từ tập này, cùng luật với cửa gác máy chủ.
        "vai_hieu_luc": identity.ds_vai(),
    }
