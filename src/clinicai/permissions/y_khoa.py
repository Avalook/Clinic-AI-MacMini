"""Ai làm việc với NỘI DUNG Y KHOA (bệnh án, phiếu khám, kết quả) — theo QUYỀN.

Trước 24/09/2026 cửa này là danh sách VAI (`CLINICAL_WRITE_ROLES`: bác sĩ, bác
sĩ siêu âm, thư ký y khoa, điều dưỡng siêu âm) và quản lý bị chặn cứng (ROLE-02
đời role-picker). Tuyền chốt 24/09: "quản lý quyền cao nhất — có module đó thì
mọi quyền của nó có cả", không tách đọc với sửa.

Luật bây giờ: có BẤT KỲ khối nào của module khám / kết quả (tư vấn, khám, ghi
bệnh án, hoàn tất khám, điền kết quả, duyệt kết quả) là đọc được nội dung y
khoa. Ai không có khối nào (lễ tân, thu ngân, CSKH, dược sĩ… theo nhóm mẫu) thì
không — tinh thần ROLE-02 "không MẶC ĐỊNH, phải được cấp" giữ nguyên, chỉ đổi từ
"vai" sang "được cấp". Quản lý cấp thêm được cho ai cần trên màn Phân quyền.

Hai quyền ký chuyên môn (hoàn tất khám, duyệt kết quả) vẫn cần chứng chỉ hành
nghề: hệ thống từ chối CẤP chúng cho người không phải vai lâm sàng
(`permission_service`), nên "mọi quyền" của quản lý dừng trước hàng rào luật.
"""

from __future__ import annotations

import asyncpg
import structlog

from clinicai.api.identity import CLINICAL_WRITE_ROLES, StaffIdentity
from clinicai.permissions.can import can
from clinicai.permissions.cua_quyen import cua_quyen

logger = structlog.get_logger()

QUYEN_Y_KHOA: tuple[str, ...] = (
    "clinical.intake.perform",
    "clinical.consult.perform",
    "clinical.record.write",
    "clinical.consult.finalize",
    "result.form.fill",
    "result.review.approve",
)

#: Quyền GHI nội dung y khoa (bệnh án, phiếu cũ, đọc giọng nói, kết quả).
QUYEN_GHI_Y_KHOA: tuple[str, ...] = ("clinical.record.write", "result.form.fill")

_CAU = "Bạn chưa được cấp khối khám / kết quả nên chưa mở được nội dung y khoa."

cua_y_khoa = cua_quyen(*QUYEN_Y_KHOA, cau=_CAU)
cua_ghi_y_khoa = cua_quyen(
    *QUYEN_GHI_Y_KHOA,
    cau="Bạn chưa được cấp khối ghi bệnh án / điền kết quả.",
)


async def doc_duoc_y_khoa(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_Y_KHOA:
        if await can(conn, identity, q):
            return True
    return False


async def ghi_mo_ho_so(
    pool: asyncpg.Pool,
    identity: StaffIdentity,
    *,
    noi: str,
    khach: str | None = None,
    visit_id: str | None = None,
) -> None:
    """NHẬT KÝ MỞ HỒ SƠ Y KHOA — ai mở hồ sơ của khách nào, lúc nào, ở màn nào.

    Tuyền duyệt 24/09/2026 cùng lúc mở quyền đọc y khoa cho quản lý: mở rộng
    quyền nhưng phải truy được dấu vết. CHỈ ghi cho người KHÔNG thuộc vai lâm
    sàng (bác sĩ, bác sĩ siêu âm, thư ký y khoa, điều dưỡng siêu âm) — đây là
    câu hỏi "ai ngoài đội chuyên môn đã xem", không phải hàng rào quyền; ghi cả
    bác sĩ thì mỗi ca vài trăm dòng, nhật ký thành nhiễu và không ai đọc.

    Chỉ ghi MÃ khách + tên màn (`services/audit.py`: không bao giờ ghi nội dung).
    Không làm hỏng lượt đọc: ghi lỗi thì chỉ log cảnh báo.
    """
    if identity.co_vai(CLINICAL_WRITE_ROLES):
        return
    from clinicai.services.audit import record_event

    try:
        async with pool.acquire() as conn:
            if khach is None and visit_id:
                khach = await conn.fetchval(
                    "SELECT clinic_patient_id::text FROM visit"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                    identity.clinic_id,
                    visit_id,
                )
            if not khach:
                return
            await record_event(
                conn,
                event_type="clinical_record.opened",
                aggregate_type="patient",
                aggregate_id=khach,
                identity=identity,
                origin=f"api:{noi}",
                payload={"man": noi, "visit_id": visit_id},
            )
    except Exception:  # noqa: BLE001 — nhật ký hỏng không được chặn người đọc
        logger.warning("ghi_mo_ho_so_loi", noi=noi, exc_info=True)


__all__ = [
    "QUYEN_GHI_Y_KHOA",
    "QUYEN_Y_KHOA",
    "cua_ghi_y_khoa",
    "cua_y_khoa",
    "doc_duoc_y_khoa",
    "ghi_mo_ho_so",
]
