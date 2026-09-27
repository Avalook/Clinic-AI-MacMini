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


__all__ = ["CAU_CHAN", "co_ca_o_phong", "doi_lich_phong"]
