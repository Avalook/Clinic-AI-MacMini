"""AI ĐỌC ĐƯỢC BẢNG LƯỢT KHÁM / HÀNG CHỜ — theo QUYỀN của lego (đợt 3, 27/09/2026).

Trước đợt này ba đường đọc `/luot-kham/bang`, `/hang-cho`, `/phong-hom-nay` gác
bằng danh sách VAI (`_BANG_GUARD`, `BOARD_ROLES`), trong khi lệnh ghi đã hỏi
capability. Hai hệ gác song song: tài khoản chỉ bật lego "Khám tư vấn" (vai tài
khoản Bác sĩ nhưng TẮT Bàn khám → mất vai Bác sĩ theo lego) nhận khách được mà
hàng chờ tư vấn thì 403 — màn đứng "Đang tải hàng chờ…" mãi.

Luật bây giờ (Tuyền 26/09: "khám, chỉ định, kê đơn CHỈ CẦN LEGO"):

  * Bảng lượt khám: có quyền của MỘT lego dùng bảng ấy (tiếp đón, đo sinh hiệu,
    tư vấn, bàn khám, phòng dịch vụ, điều phối).
  * Hàng chờ TƯ VẤN: quyền "Khám tư vấn".
  * Hàng chờ KHÁM (khách của tôi): quyền "Khám bệnh".
  * Hàng chờ một PHÒNG: quyền thực hiện dịch vụ (kể cả cấp theo đúng phòng ấy)
    hoặc quyền "Khám bệnh" (bàn khám theo phòng).
  * Điều phối (trưởng ca) đọc được mọi hàng — như trước, không ai mất việc.

Ẩn/hiện nút vẫn là việc của màn; lệnh ghi vẫn tự hỏi quyền của nó.
"""

from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import tra_quyen

#: Quyền của mọi lego có màn đọc bảng lượt khám (`GET /luot-kham/bang`).
QUYEN_BANG_LUOT: tuple[str, ...] = (
    "reception.checkin.perform",  # 1 Tiếp đón khách
    "vitals.measure",  # 2 Đo sinh hiệu
    "clinical.intake.perform",  # 3 Khám tư vấn
    "clinical.consult.perform",  # 4 Bàn khám
    "service.execute.start",  # 5 Phòng dịch vụ
    "service.execute.complete",
    "dispatch.manage",  # 9 Điều phối khách
)

QUYEN_HANG_TU_VAN: tuple[str, ...] = ("clinical.intake.perform", "dispatch.manage")
QUYEN_HANG_KHAM: tuple[str, ...] = ("clinical.consult.perform", "dispatch.manage")
QUYEN_HANG_PHONG: tuple[str, ...] = (
    "service.execute.start",
    "service.execute.complete",
    "clinical.consult.perform",
    "dispatch.manage",
)

for _q in (*QUYEN_BANG_LUOT, *QUYEN_HANG_PHONG):
    tra_quyen(_q)  # tên sai thì hỏng lúc nạp module, không lúc có người bấm


def quyen_doc_hang_cho(*, tu_van: bool, co_phong: bool) -> tuple[str, ...]:
    """Hàng chờ nào cần quyền nào. Thuần — kiểm được không cần database.

    Tư vấn đứng trước phòng: `?tu_van=true` là hàng CHUNG, không theo phòng.
    """
    if tu_van:
        return QUYEN_HANG_TU_VAN
    if co_phong:
        return QUYEN_HANG_PHONG
    return QUYEN_HANG_KHAM


async def co_mot_quyen(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    quyen: Sequence[str],
    *,
    phong_id: str | None = None,
) -> bool:
    """Có ÍT NHẤT một quyền trong số (toàn phòng khám, hoặc đúng phòng này)."""
    for q in quyen:
        if await can(conn, identity, q, phong_id=phong_id):
            return True
    return False


async def doi_mot_quyen(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    quyen: Sequence[str],
    *,
    cau: str,
    phong_id: str | None = None,
) -> None:
    """Như `co_mot_quyen`, nhưng không có quyền nào thì chặn bằng câu dễ hiểu."""
    if not await co_mot_quyen(conn, identity, quyen, phong_id=phong_id):
        raise SafetyGateError(cau)


__all__ = [
    "QUYEN_BANG_LUOT",
    "QUYEN_HANG_KHAM",
    "QUYEN_HANG_PHONG",
    "QUYEN_HANG_TU_VAN",
    "co_mot_quyen",
    "doi_mot_quyen",
    "quyen_doc_hang_cho",
]
