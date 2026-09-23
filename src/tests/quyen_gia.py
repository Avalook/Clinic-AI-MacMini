"""Cửa quyền GIẢ cho bài kiểm dùng connection mock (CORE-B3, 23/09/2026).

Bài kiểm mock đếm từng lần fetch/fetchval, nên cửa quyền thật (`can` đọc
`v_quyen_hieu_luc`) không chạy được ở đó. Thay vì cho qua tất (mất nghĩa của
những bài "vai này bị chặn"), cửa giả này trả lời theo NHÓM MẪU của vai — đúng
bộ quyền một người mới vào vai ấy nhận (`cap_quyen_theo_preset`). Cửa thật có
bài kiểm riêng trên Postgres: `services/test_duong_kham_hoi_quyen_db.py`.
"""

from __future__ import annotations

from typing import Any

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.catalogue import quyen_cua_preset, tra_quyen


async def doi_quyen_theo_nhom_mau(
    _conn: Any,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
    cau: str | None = None,
) -> None:
    if quyen not in quyen_cua_preset(identity.role.value):
        ten = tra_quyen(quyen).ten
        raise SafetyGateError(cau or f"Bạn chưa được cấp quyền “{ten}”.")


async def can_theo_nhom_mau(
    _conn: Any,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
) -> bool:
    """Như `can` thật, trả lời theo nhóm mẫu của vai (xem đầu file)."""
    tra_quyen(quyen)
    return quyen in quyen_cua_preset(identity.role.value)
