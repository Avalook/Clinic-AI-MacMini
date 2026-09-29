"""Quyền theo lịch (Tuyền duyệt 27/09/2026 tối).

"Gắn vào phòng nào thì làm việc ở phòng ấy": làm việc TẠI một phòng dịch vụ
(bắt đầu / xong / không làm / gián đoạn / làm lại một chỉ định) cần HAI điều —
lego cho phép (`can`, trần quyền) VÀ hôm nay đang có ca ở một vị trí thuộc
chính phòng ấy (lịch làm việc). Ngoài lịch thì chặn, kèm câu nói rõ vì sao.

* Công tắc dây nối `quyen_theo_lich` — mặc định TẮT: bật khi lịch tuần đã xếp
  đủ, để không khoá nhầm ai.
* Miễn: người có quyền điều phối (`dispatch.manage` — trưởng ca / quản lý) để
  còn chữa cháy. Hỏi QUYỀN, không hỏi vai (xem `can.py`).
* "Đang có ca" dùng đúng `doc_vi_tri_hien_hanh` của cửa gác vai S0-7 — ca đã
  duyệt + giờ ca theo công tắc `luat_ca_dang_bat` — một luật, không bản thứ hai.
* Chỉ định chưa có phòng (đối tác, chưa xếp) → không có gì để đối chiếu, cho qua.
"""

from __future__ import annotations

from collections.abc import Iterable

import asyncpg

from clinicai.api.identity import StaffIdentity, doc_vi_tri_hien_hanh
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.services.bac_si_phu_trach import (
    bac_si_cung_phong_hom_nay as _cung_phong,
)
from clinicai.services.day_noi import doc_day

CAU_CHAN = (
    "Hôm nay bạn chưa được xếp lịch ở phòng này (hoặc đang ngoài giờ ca). "
    "Nhờ trưởng ca xếp lịch cho bạn ở Cấu trúc phòng khám rồi thử lại."
)


def co_ca_o_phong(
    tram_dang_dung: Iterable[str], ma_vi_tri_cua_phong: Iterable[str]
) -> bool:
    """Thuần: một trong các vị trí đang đứng có thuộc phòng này không."""
    return bool(set(tram_dang_dung) & set(ma_vi_tri_cua_phong))


async def doi_lich_phong(
    conn: asyncpg.Connection,
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    phong_id: str | None,
) -> None:
    """Chặn nếu công tắc bật mà người này không có ca ở phòng `phong_id` lúc này."""
    if not phong_id:
        return
    if not await doc_day(conn, identity.clinic_id, "quyen_theo_lich"):
        return
    if await can(conn, identity, "dispatch.manage"):
        return
    dang_dung = await doc_vi_tri_hien_hanh(pool, identity.clinic_id, identity.staff_id)
    ma_phong = [
        r["code"]
        for r in await conn.fetch(
            "SELECT code FROM vi_tri_lam_viec"
            " WHERE clinic_id = $1::uuid AND room_id = $2::uuid AND is_active",
            identity.clinic_id,
            str(phong_id),
        )
    ]
    if not co_ca_o_phong((tram for tram, _ca in dang_dung), ma_phong):
        raise SafetyGateError(CAU_CHAN)


# ── NỬA "MỞ": CÙNG PHÒNG TRONG LỊCH = CÙNG LUỒNG KHÁCH (28/09/2026) ─────────
#
# Tuyền: bác sĩ, thư ký, điều dưỡng được xếp vào CÙNG MỘT PHÒNG trong lịch làm
# việc thì ngoài đời làm cùng nhau; bác sĩ hầu như không gõ máy, thư ký và điều
# dưỡng thao tác thay trên tài khoản của chính mình — nên luồng khách bác sĩ
# nhận thì hai người kia cũng phải thấy, KHÔNG cần chọn phòng tay.
#
# Trước bản này Bàn khám (không chọn phòng) hiện "khách của chính tôi" cho mọi
# ai có quyền Hoàn tất khám — thư ký / điều dưỡng đã có quyền ấy từ 28/09 nên
# thấy danh sách RỖNG. Đo prod 28/09: 12/12 người kỹ năng TKYK / Phụ BS có quyền.


async def bac_si_cung_phong_hom_nay(
    conn: asyncpg.Connection, clinic_id: str, staff_id: str
) -> list[str]:
    """Bác sĩ đứng CÙNG PHÒNG với người này trong lịch hôm nay (cả chính họ nếu
    họ là bác sĩ).

    29/09/2026: theo CA đang diễn ra (không chỉ ngày) và tính cả bác sĩ siêu âm
    — một luật với "bác sĩ của phòng" ở hàng chờ; ngoài giờ ca rơi về cả ngày
    để Bàn khám không bỗng rỗng. Luật nằm ở `bac_si_phu_trach`."""
    return await _cung_phong(conn, clinic_id, staff_id)


def khach_cua_toi(
    *, toi: str, la_bac_si: bool, cung_phong: list[str], kham_duoc: bool
) -> tuple[list[str], bool]:
    """Thuần: "khách của tôi" ở Bàn khám khi KHÔNG chọn phòng.

    Trả (bác sĩ có lượt hiện ra, có hiện MỌI bác sĩ không):
      * có người cùng phòng trong lịch hôm nay → khách của các bác sĩ phòng ấy
        (và của chính mình nếu mình là bác sĩ);
      * không có lịch mà là bác sĩ → khách của chính mình;
      * không có lịch, không là bác sĩ, có lego Khám → MỌI bác sĩ (mở, không
        khoá — người chưa được xếp lịch vẫn làm được việc);
      * còn lại → không ai.
    """
    ds = set(cung_phong)
    if la_bac_si:
        ds.add(toi)
    if ds:
        return sorted(ds), False
    return [], kham_duoc


__all__ = [
    "CAU_CHAN",
    "bac_si_cung_phong_hom_nay",
    "co_ca_o_phong",
    "doi_lich_phong",
    "khach_cua_toi",
]
