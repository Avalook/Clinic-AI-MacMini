"""Khối VÒNG ĐỌC — kết quả/dịch vụ vừa xong thì mở vòng đọc và khép lượt.

Vì sao có khối này (24/09/2026): trước đây chỉ vài lối GỌI THẲNG hàm chạy lại
vòng đọc (tải tệp, lối phòng cũ, đối tác lấy mẫu). Đường làm dịch vụ MỚI (phòng
bấm [Xong] / [Không làm được], phiếu kết quả Hoàn tất) không gọi — nên yêu cầu
"cần kết quả" đứng im, bác sĩ chính không thấy "có kết quả mới cần đọc", và
lượt không bao giờ tự khép khi dịch vụ cuối làm xong sau khi bác sĩ Hoàn tất.

Nay mọi lối chỉ việc PHÁT sự kiện (vốn đã phát); khối này nghe và làm một việc:

    service.completed / service.not_performed / partner.sample_collected
    partner.sample_received (đối tác nhận mẫu = việc đối tác XONG, 29/09/2026)
    result.ready / result.corrected
    result_file.uploaded / result_file.confirmed / result_file.revoked
        → chạy lại vòng đọc (mở / rút chỗ chờ REVIEW của bác sĩ chính)
        → khép phần khám của lượt nếu hết việc (phát `visit.exam_completed`)
        → cập nhật "khách đang ở đâu"

Thêm một lối sinh kết quả mới về sau = phát sự kiện + khai VONG_DOC trong danh
mục; KHÔNG sửa khối này, KHÔNG sửa khối Khám.

CHẠY LẠI ĐƯỢC: cả ba việc đều tự bỏ qua khi đã làm. PHÁT LẠI thì bỏ (node tác
vụ, không phải projection).
"""

from __future__ import annotations

import asyncpg

from clinicai.api.identity import danh_tinh_nhan_vien
from clinicai.events.catalogue import VONG_DOC
from clinicai.events.worker import SuKienDaNhan, dang_ky
from clinicai.services.hang_cho import cap_nhat_vi_tri
from clinicai.services.luot_kham_service import LuotKhamService


async def _luot_cua(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> str | None:
    visit_id = su_kien.payload.get("visit_id")
    if visit_id:
        return str(visit_id)
    so_id = su_kien.payload.get("service_order_id")
    if not so_id:
        return None
    v = await conn.fetchval(
        "SELECT visit_id::text FROM service_order"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        su_kien.clinic_id,
        str(so_id),
    )
    return str(v) if v else None


async def xu_ly_vong_doc(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    # Tệp đối tác còn chờ xác nhận chưa phải kết quả dùng được.
    if su_kien.event_type == "result_file.uploaded" and su_kien.payload.get(
        "cho_xac_nhan"
    ):
        return
    visit_id = await _luot_cua(conn, su_kien)
    if not visit_id:
        return
    luot = await conn.fetchrow(
        "SELECT status, closed_at FROM visit WHERE clinic_id = $1::uuid"
        " AND visit_id = $2::uuid FOR UPDATE",
        su_kien.clinic_id,
        visit_id,
    )
    # Lượt đã đóng (FINALIZED / AMENDED) hay khách bỏ về giữa chừng
    # (INCOMPLETE): kết quả muộn thuộc việc theo dõi, không mở lại hàng chờ.
    # ĐÃ CHECK-OUT (`closed_at`, trạng thái vẫn IN_PROGRESS — check-out không
    # khoá bệnh án) cũng vậy: staging 07/10/2026, dịch vụ xong 5 phút SAU
    # check-out mở vòng đọc → khách đã về lại nằm "Kết quả cần đọc" ở bàn khám.
    # Mở lại lượt (`mo_lai_luot`) thì sự kiện kế tiếp chạy vòng đọc như thường.
    if luot is None or luot["status"] not in ("OPEN", "IN_PROGRESS"):
        return
    if luot["closed_at"] is not None:
        return
    # Nhật ký (event_log) ghi tên người gây ra sự kiện; không có người (hệ
    # thống) thì ghi dưới tên bác sĩ chính của lượt.
    nguoi_id = su_kien.actor_staff_id or await conn.fetchval(
        "SELECT attending_doctor_id::text FROM visit"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        su_kien.clinic_id,
        visit_id,
    )
    if not nguoi_id:
        return
    nguoi = await danh_tinh_nhan_vien(
        conn, clinic_id=su_kien.clinic_id, staff_id=str(nguoi_id)
    )
    if nguoi is None:
        return
    luot = LuotKhamService(pool=None)
    await luot._evaluate_rounds(conn, nguoi, visit_id)
    await luot._ket_thuc_neu_xong(conn, nguoi, visit_id, causation_id=su_kien.event_id)
    await cap_nhat_vi_tri(conn, su_kien.clinic_id, visit_id)


dang_ky(VONG_DOC, xu_ly_vong_doc)
