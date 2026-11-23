"""Ai làm việc với NỘI DUNG Y KHOA (bệnh án, phiếu khám, kết quả) — theo QUYỀN.

Trước 24/09/2026 cửa này là danh sách VAI (`CLINICAL_WRITE_ROLES`: bác sĩ, bác
sĩ siêu âm, thư ký y khoa, điều dưỡng siêu âm) và quản lý bị chặn cứng (ROLE-02
đời role-picker). Tuyền chốt 24/09: "quản lý quyền cao nhất — có module đó thì
mọi quyền của nó có cả", không tách đọc với sửa.

Luật bây giờ: có BẤT KỲ khối nào của module khám / kết quả (tư vấn, khám, ghi
bệnh án, hoàn tất khám, điền kết quả, duyệt kết quả) là đọc được nội dung y
khoa. Vai chỉ là TÊN của nhóm mẫu (gói khối chép cho người mới); nhóm mẫu nào
không có khối y khoa thì người đó chưa mở được — cho tới khi quản lý bật khối
cho họ trên màn Phân quyền. Quản lý có tất cả khối. Không còn hàng rào chứng chỉ
(Tuyền bỏ 24/09/2026).
"""

from __future__ import annotations

import asyncpg
import structlog

from clinicai.api.identity import StaffIdentity
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

#: IN PHIẾU KHÁM CHO KHÁCH ở quầy (Tuyền 27/09/2026: "in ở mọi khâu — mở đi"):
#: tiếp đón, thu tiền dịch vụ, thu tiền thuốc, giao thuốc được ĐỌC phiếu khám +
#: kết quả + ảnh của lượt để IN (không ghi). Là quyền của lego đang có, không
#: phải khối mới — thêm khối vào lego sẽ làm lego của mọi tài khoản đang bật
#: thành "bật một phần".
QUYEN_IN_PHIEU: tuple[str, ...] = (
    "reception.checkin.perform",
    "payment.service.collect",
    "payment.medicine.collect",
    "pharmacy.dispense",
    # CSKH in hồ sơ khám / kết quả / đơn thuốc trả khách theo từng ngày khám
    # (Tuyền 28/09/2026). Chỉ ĐỌC để in, như các khâu quầy.
    "crm.manage",
)

_CAU = "Bạn không có quyền xem nội dung y khoa (khám / kết quả)."

cua_y_khoa = cua_quyen(*QUYEN_Y_KHOA, cau=_CAU)
cua_ghi_y_khoa = cua_quyen(
    *QUYEN_GHI_Y_KHOA,
    cau="Bạn không có quyền ghi bệnh án / điền kết quả.",
)


async def doc_duoc_y_khoa(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_Y_KHOA:
        if await can(conn, identity, q):
            return True
    return False


async def doc_duoc_in_phieu(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    """Được in phiếu khám: đọc được y khoa, HOẶC làm một khâu quầy."""
    if await doc_duoc_y_khoa(conn, identity):
        return True
    for q in QUYEN_IN_PHIEU:
        if await can(conn, identity, q):
            return True
    return False


# Nhật ký AI MỞ HỒ SƠ (24/11/2026): không còn ở đây — `api/xem_ho_so.py` ghi
# mọi vai, sau khi cửa đọc thành công, vào bảng `nhat_ky_xem_ho_so`.

__all__ = [
    "QUYEN_GHI_Y_KHOA",
    "QUYEN_Y_KHOA",
    "cua_ghi_y_khoa",
    "cua_y_khoa",
    "doc_duoc_y_khoa",
]
