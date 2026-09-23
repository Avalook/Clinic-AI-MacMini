"""Khối CHUÔNG — sự kiện nào báo cho ai (nhóm 3, Tuyền chốt 23–24/09/2026).

"Tệp kết quả phát cho bác sĩ, thư ký, điều dưỡng, CSKH — người nhận chỉnh được."

Trước đây lệnh tải tệp GỌI THẲNG `bao_ket_qua_ve` (CSKH + bác sĩ, cứng trong
code). Nay lệnh chỉ phát `result_file.uploaded`; khối này nghe rồi báo. Người
nhận là DỮ LIỆU: bảng `day_nhan_thong_bao` (vai + bác sĩ chính đích danh + bật/
tắt), quản lý chỉnh trên màn. Chưa có dòng → `MAC_DINH` bên dưới (khớp migration
20260924000004).

Chuông ghi `thong_bao` trong CHÍNH giao dịch đánh dấu DONE của người đưa tin:
chạy lại không nhân đôi (chốt "một việc đang mở một lần" của `thong_bao`).
PHÁT LẠI (`la_phat_lai`) thì im — không réo chuông cho chuyện hôm qua.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import asyncpg

from clinicai.events.catalogue import CHUONG
from clinicai.events.worker import SuKienDaNhan, dang_ky


@dataclass(frozen=True)
class DayNhan:
    vai: Sequence[str]
    bac_si_chinh: bool
    bat: bool = True


#: Mặc định khi phòng khám chưa chỉnh (cùng giá trị migration đã gieo).
MAC_DINH: dict[str, DayNhan] = {
    "result_file.uploaded": DayNhan(["CSKH", "TKYK", "NURSE_ULTRASOUND"], True),
    "result.ready": DayNhan(["TKYK"], True),
}

#: Màn mở ra khi bấm chuông, theo vai nhận.
_DUONG_DAN: dict[str, str] = {
    "CSKH": "/customers",
    "TKYK": "/ban-kham",
    "DOCTOR": "/ban-kham",
    "NURSE_ULTRASOUND": "/xac-nhan-ket-qua",
}


async def day_nhan(
    conn: asyncpg.Connection, clinic_id: str, su_kien: str
) -> DayNhan | None:
    """Ai nhận chuông của sự kiện này ở phòng khám này (None = sự kiện không réo)."""
    row = await conn.fetchrow(
        "SELECT vai, bac_si_chinh, bat FROM day_nhan_thong_bao"
        " WHERE clinic_id = $1::uuid AND su_kien = $2",
        clinic_id,
        su_kien,
    )
    if row is not None:
        return DayNhan(
            list(row["vai"] or []), bool(row["bac_si_chinh"]), bool(row["bat"])
        )
    return MAC_DINH.get(su_kien)


async def _khach_va_bac_si(
    conn: asyncpg.Connection, su_kien: SuKienDaNhan
) -> asyncpg.Record | None:
    """Tên khách (cho tiêu đề chuông — nằm ở bảng hiện trạng, không ở sổ) + bác
    sĩ chính của lượt. Tệp chưa gắn lượt thì đi qua chính tệp."""
    visit_id = su_kien.payload.get("visit_id")
    tep_id = su_kien.payload.get("tep_id")
    return await conn.fetchrow(
        """
        SELECT p.clinic_patient_id::text AS pid, p.full_name, p.patient_code,
               coalesce(v.attending_doctor_id, a.doctor_id)::text AS bac_si_id
          FROM (SELECT $2::uuid AS visit_id, $3::uuid AS tep_id) k
          LEFT JOIN visit v
            ON v.clinic_id = $1::uuid AND v.visit_id = k.visit_id
          LEFT JOIN tep_ket_qua t
            ON t.clinic_id = $1::uuid AND t.id = k.tep_id
          LEFT JOIN appointment a
            ON a.clinic_id = $1::uuid
           AND a.id = coalesce(v.appointment_id, t.appointment_id)
          JOIN patient p
            ON p.clinic_id = $1::uuid
           AND p.clinic_patient_id = coalesce(v.clinic_patient_id, t.clinic_patient_id)
        """,
        su_kien.clinic_id,
        visit_id,
        tep_id,
    )


async def bao_chuong(conn: asyncpg.Connection, su_kien: SuKienDaNhan) -> None:
    if su_kien.la_phat_lai:
        return
    day = await day_nhan(conn, su_kien.clinic_id, su_kien.event_type)
    if day is None or not day.bat:
        return
    # `thong_bao.nguoi_goi_staff_id` bắt buộc: người gây ra sự kiện (người tải
    # tệp, người hoàn tất phiếu). Sự kiện hệ thống không réo chuông.
    if not su_kien.actor_staff_id:
        return
    k = await _khach_va_bac_si(conn, su_kien)
    if k is None:
        return
    ten = f"{k['full_name']} ({k['patient_code']})"
    if su_kien.event_type == "result_file.uploaded":
        tieu_de = f"Tệp kết quả của {ten} đã về"
        noi_dung = (
            "Tệp của đối tác — cần xác nhận đúng người, đúng chỉ định."
            if su_kien.payload.get("cho_xac_nhan")
            else "Kết quả đã vào hồ sơ khách — mở là tự ghi đã xem."
        )
    else:
        tieu_de = f"Có kết quả mới của {ten}"
        noi_dung = "Phòng đã hoàn tất phiếu kết quả."
    nguon_id = f"{su_kien.event_type}:{su_kien.aggregate_id}"
    for vai in day.vai:
        duong = _DUONG_DAN.get(vai, "/home")
        if vai == "CSKH":
            duong = f"/customers?selected={k['pid']}"
        await conn.execute(
            """
            INSERT INTO thong_bao
                (clinic_id, vai_nhan, muc_do, tieu_de, noi_dung, nguon, nguon_id,
                 duong_dan, nguoi_goi_staff_id)
            VALUES ($1::uuid, $2, 'THUONG', $3, $4, 'ket_qua_ve', $5, $6, $7::uuid)
            ON CONFLICT (clinic_id, nguon, nguon_id, vai_nhan)
                WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL
                  AND vai_nhan IS NOT NULL
            DO NOTHING
            """,
            su_kien.clinic_id,
            vai,
            tieu_de,
            noi_dung,
            nguon_id,
            duong,
            su_kien.actor_staff_id,
        )
    if day.bac_si_chinh and k["bac_si_id"]:
        await conn.execute(
            """
            INSERT INTO thong_bao
                (clinic_id, nguoi_nhan_staff_id, muc_do, tieu_de, noi_dung, nguon,
                 nguon_id, duong_dan, nguoi_goi_staff_id)
            VALUES ($1::uuid, $2::uuid, 'THUONG', $3, $4, 'ket_qua_ve', $5,
                    '/ban-kham', $6::uuid)
            ON CONFLICT (clinic_id, nguon, nguon_id, nguoi_nhan_staff_id)
                WHERE da_xu_ly_luc IS NULL AND nguon_id IS NOT NULL
                  AND vai_nhan IS NULL
            DO NOTHING
            """,
            su_kien.clinic_id,
            k["bac_si_id"],
            tieu_de,
            noi_dung,
            nguon_id,
            su_kien.actor_staff_id,
        )


dang_ky(CHUONG, bao_chuong)

__all__ = ["MAC_DINH", "DayNhan", "bao_chuong", "day_nhan"]
