"""`can(...)` — câu hỏi duy nhất mà lệnh được phép hỏi về quyền.

Lệnh hỏi "người này có được chỉ định dịch vụ không?", KHÔNG hỏi "vai của người
này có nằm trong tập DOCTOR_ROLES không?". Khác biệt ấy là toàn bộ lý do tồn tại
của file này: hôm nay muốn cho điều dưỡng điều phối khách thì quản lý tick một ô,
không phải chờ người sửa code ở năm cửa.

PHẠM VI. Một dòng cấp quyền có thể hẹp lại theo phòng hoặc theo ca. Khi lệnh biết
mình đang làm ở phòng nào thì truyền `phong_id` vào; quyền toàn phòng khám luôn
đủ, quyền hẹp chỉ đủ khi đúng phòng ấy.

KHÔNG CÓ ĐƯỜNG VÒNG. Không có "quản lý thì được tất" viết cứng ở đây: quản lý
mạnh vì preset của họ có mọi khối, và vì họ giữ `permission.manage` để tự cấp
thêm — chứ không phải vì code có một câu `if role == MANAGEMENT`. Viết cứng như
vậy là thứ làm cho mô hình quyền trở nên vô nghĩa ngay ngày đầu.
"""

from __future__ import annotations

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions import cache
from clinicai.permissions.catalogue import tra_quyen

_CAU_HOI = """
SELECT EXISTS (
    SELECT 1 FROM v_quyen_hieu_luc q
     WHERE q.clinic_id = $1::uuid
       AND q.staff_id = $2::uuid
       AND q.capability = $3
       AND (q.scope_type = 'CLINIC'
            OR ($4::uuid IS NOT NULL AND q.scope_id = $4::uuid))
)
"""


async def can(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
) -> bool:
    """Người này có quyền ấy trong phòng khám này (và phòng này) không?

    Quyền phạm vi TOÀN PHÒNG KHÁM được nhớ tạm vài giây (`permissions/cache.py`)
    vì câu này chạy ở mọi lệnh. Hỏi có kèm phòng thì luôn xuống database: quyền
    hẹp theo phòng/ca ít gặp hơn nhiều, và nhớ nhầm nó thì đắt.

    Chỉ nhớ câu trả lời "CÓ". Ai vừa được cấp quyền phải làm được ngay, không
    phải chờ hết hạn nhớ.
    """
    tra_quyen(quyen)  # tên sai thì hỏng ngay, không âm thầm trả False

    if phong_id is None:
        da_nho = cache.doc(identity.clinic_id, identity.staff_id)
        if da_nho is not None and quyen in da_nho:
            return True

    co = await conn.fetchval(
        _CAU_HOI, identity.clinic_id, identity.staff_id, quyen, phong_id
    )
    if co and phong_id is None:
        # Nạp cả bộ một lần: lệnh sau của cùng người thường hỏi quyền khác.
        cache.ghi(
            identity.clinic_id,
            identity.staff_id,
            frozenset(await _quyen_toan_phong_kham(conn, identity)),
        )
    return bool(co)


async def _quyen_toan_phong_kham(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT capability FROM v_quyen_hieu_luc"
        " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid"
        "   AND scope_type = 'CLINIC'",
        identity.clinic_id,
        identity.staff_id,
    )
    return [r["capability"] for r in rows]


async def doi_quyen(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    quyen: str,
    *,
    phong_id: str | None = None,
    cau: str | None = None,
) -> None:
    """Như `can`, nhưng không có quyền thì chặn lệnh."""
    if not await can(conn, identity, quyen, phong_id=phong_id):
        ten = tra_quyen(quyen).ten
        raise SafetyGateError(cau or f"Bạn chưa được cấp quyền “{ten}”.")


async def quyen_hieu_luc(
    conn: asyncpg.Connection, identity: StaffIdentity
) -> list[str]:
    """Mọi quyền người này đang có — để màn hình vẽ thanh bên và ẩn nút.

    Ẩn nút KHÔNG phải bảo mật: lệnh vẫn kiểm lại bằng `doi_quyen`.
    """
    rows = await conn.fetch(
        "SELECT DISTINCT capability FROM v_quyen_hieu_luc"
        " WHERE clinic_id = $1::uuid AND staff_id = $2::uuid ORDER BY capability",
        identity.clinic_id,
        identity.staff_id,
    )
    return [r["capability"] for r in rows]


__all__ = ["can", "doi_quyen", "quyen_hieu_luc"]
