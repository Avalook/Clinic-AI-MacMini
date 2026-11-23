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
from fastapi import Depends, Request

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
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


class GhiXemHoSo:
    """NHẬT KÝ XEM HỒ SƠ cho MỘT lượt gọi API — ai mở hồ sơ khách nào, qua cửa nào.

    Lấy bằng `Depends(ghi_xem_ho_so)`, gọi một dòng sau khi đã đọc xong:
    `await xem("phieu_kham", visit_id=...)`. Ghi MỌI vai (kể cả bác sĩ — NĐ
    356/2025 hỏi "ai đã truy cập", không hỏi "ai ngoài đội chuyên môn"; từ
    24/11/2026 thay cho luật 24/09 chỉ ghi người ngoài vai lâm sàng); chống nhiễu
    bằng gộp khung 5 phút ở `services/nhat_ky_xem_ho_so.py`.

    Không bao giờ ném: lỗi ghi → kho lỗi (/ops "Lỗi & cảnh báo"), lượt đọc vẫn trả.
    """

    def __init__(self, pool: asyncpg.Pool, identity: StaffIdentity, cua: str) -> None:
        self._pool = pool
        self._identity = identity
        self.cua = cua

    async def __call__(
        self,
        loai: str,
        *,
        khach: str | None = None,
        doi_tuong_id: str | None = None,
        **tra: str | None,
    ) -> None:
        """`khach` biết sẵn thì truyền; không thì một khoá tra (`visit_id`,
        `appointment_id`, `service_order_id`, `tep_id`, `xn_cu_id`, `anh_sieu_am`
        — `services/nhat_ky_xem_ho_so._SQL_TRA_KHACH`)."""
        from clinicai.services import kho_loi, nhat_ky_xem_ho_so

        try:
            await nhat_ky_xem_ho_so.ghi(
                self._pool,
                clinic_id=self._identity.clinic_id,
                staff_id=self._identity.staff_id,
                vai=self._identity.vai_goc.value,
                loai=loai,
                cua=self.cua,
                khach=khach,
                tra=tra,
                doi_tuong_id=doi_tuong_id,
            )
        except Exception as exc:  # noqa: BLE001 — nhật ký hỏng không chặn người đọc
            logger.error("nhat_ky_xem_ho_so_loi", cua=self.cua, loai=loai)
            await kho_loi.ghi_loi(
                self._pool, nguon="api", vi_tri=f"nhat-ky-xem {self.cua}", exc=exc
            )


async def ghi_xem_ho_so(
    request: Request,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> GhiXemHoSo:
    """Dependency FastAPI. Cửa = MẪU đường dẫn ("GET /api/v1/patients/{id}"),
    không đường thật — đường thật có thể mang tham số tìm kiếm."""
    route = request.scope.get("route")
    cua = f"{request.method} {getattr(route, 'path', None) or request.url.path}"
    return GhiXemHoSo(pool, identity, cua)


__all__ = [
    "QUYEN_GHI_Y_KHOA",
    "QUYEN_Y_KHOA",
    "GhiXemHoSo",
    "cua_ghi_y_khoa",
    "cua_y_khoa",
    "doc_duoc_y_khoa",
    "ghi_xem_ho_so",
]
