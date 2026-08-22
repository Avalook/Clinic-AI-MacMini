"""Gói dữ liệu Trang chủ — MỘT vòng HTTP thay cho 6 vòng PostgREST + 3 vòng api.

Lát 3 của lộ trình chịu tải (Lát 2 xem man_khach_hang_service). Trước đây một
lần mở /home đi: 3 truy vấn đếm + roster tuần + ca trực tuần + (Lễ tân) bảng
trạng thái buổi khám qua PostgREST — kèm một truy vấn `staff` phụ để đồng bộ
tên trực nhật, và một ĐƯỜNG LÙI hai truy vấn nữa khi select join lỗi — cộng ba
lời gọi FastAPI rời (lịch tuần, doctor-board, tiến trình lượt khám). Đông người
thì mỗi vòng trả giá kép: nghi lễ PostgREST + tranh chấp event-loop của Next.

Ở đây: các truy vấn riêng chạy TUẦN TỰ trên MỘT kết nối; ba service sẵn có
(WeekAppointments / DoctorBoard / VisitProgress) được gọi TRONG TIẾN TRÌNH —
đúng những hàm mà ba endpoint rời vẫn gọi, nên hình dữ liệu không đổi một byte.

KHỐI THEO VAI TÍNH Ở BACKEND, không nhận cờ từ client:
  * `trang_thai_kham` chỉ đổ dữ liệu khi vai là RECEPTION (bảng "Trạng thái BN
    buổi khám" là màn của Lễ tân);
  * `checkin` chỉ đổ khi vai là MANAGEMENT (frontend: canCheckin && !RECEPTION
    — Lễ tân đã có cột check-in trong bảng lịch tuần, ô riêng chỉ gây trùng).
  Nhận cờ từ query-string là cho phép client tự cấp thêm dữ liệu vai khác.

Hình trả về bắt chước PostgREST từng trường (lồng patient/doctor/service/
appointment ở bảng trạng thái) — page.tsx giữ nguyên phần dựng. Riêng tên trực
nhật: trả kèm `ten_staff` (staff.full_name) để frontend tự áp `doctorName()` —
luật cắt chức danh sống ở frontend lib, không chép sang đây bản thứ hai.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.doctor_board_service import DoctorBoardService
from clinicai.services.visit_progress_service import VisitProgressService
from clinicai.services.week_appointments_service import WeekAppointmentsService

_VN = ZoneInfo("Asia/Ho_Chi_Minh")

# Trần giữ nguyên từ bản PostgREST của trang (limit 300 ở bảng trạng thái).
_TRAN_TRANG_THAI = 300

# Trạng thái check-in của ô Quản lý — đúng chuỗi query cũ ở page.tsx.
_CHECKIN_STATUSES = [
    "SCHEDULED",
    "CSKH_CONFIRMED",
    "CONFIRMED",
    "CHECKED_IN",
    "COMPLETED",
]


class ManTrangChuService:
    """Đọc một lần mọi dữ liệu của Trang chủ."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi_du_lieu(
        self,
        *,
        identity: StaffIdentity,
        week_appt: date,
        week_roster: date,
    ) -> dict[str, Any]:
        clinic_id = identity.clinic_id
        hom_nay = datetime.now(_VN).date()
        dau_ngay = datetime.combine(hom_nay, time.min, tzinfo=_VN)
        cuoi_ngay = dau_ngay + timedelta(days=1)
        ngay_tuan_hen = [week_appt + timedelta(days=i) for i in range(7)]

        async with self._pool.acquire() as conn:
            so_viec = await conn.fetchval(
                """
                SELECT count(*) FROM work_item
                 WHERE clinic_id = $1::uuid
                   AND status IN ('PENDING', 'IN_PROGRESS')
                """,
                clinic_id,
            )
            so_khach_moi = await conn.fetchval(
                """
                SELECT count(*) FROM patient
                 WHERE clinic_id = $1::uuid
                   AND created_at >= $2 AND created_at < $3
                """,
                clinic_id,
                dau_ngay,
                cuoi_ngay,
            )
            so_lich_cho = await conn.fetchval(
                """
                SELECT count(*) FROM appointment
                 WHERE clinic_id = $1::uuid
                   AND status = 'SCHEDULED'
                   AND slot_start >= $2 AND slot_start < $3
                """,
                clinic_id,
                dau_ngay,
                cuoi_ngay,
            )
            # Lịch làm việc tuần — kèm staff.full_name để frontend đồng bộ tên
            # (thay truy vấn `staff` phụ của dongBoTenTrucNhat).
            roster = await conn.fetch(
                """
                SELECT w.work_date, w.station, w.staff_id, w.staff_name,
                       w.shift, s.full_name AS ten_staff
                  FROM work_roster w
                  LEFT JOIN staff s ON s.id = w.staff_id
                 WHERE w.clinic_id = $1::uuid
                   AND w.week_start = $2::date
                   AND w.status = 'APPROVED'
                 ORDER BY w.sort, w.id
                """,
                clinic_id,
                week_roster,
            )
            # Bác sĩ trực ca từng ngày của TUẦN LỊCH HẸN (khác tuần roster!).
            truc_ca = await conn.fetch(
                """
                SELECT work_date, staff_id, staff_name FROM work_roster
                 WHERE clinic_id = $1::uuid
                   AND work_date = ANY($2::date[])
                   AND station = 'LICH_KHAM'
                   AND status = 'APPROVED'
                   AND staff_id IS NOT NULL
                """,
                clinic_id,
                ngay_tuan_hen,
            )
            trang_thai_kham: list[dict[str, Any]] = []
            if identity.role == ClinicRole.RECEPTION:
                # Join thẳng trong SQL — không còn đường lùi hai truy vấn của
                # bản PostgREST (nó tồn tại vì select join từng lỗi; SQL tay
                # thì cột nào không có là CI đỏ ngay ở test, không đợi prod).
                rows = await conn.fetch(
                    """
                    SELECT v.visit_id, v.status, v.checked_in_at, v.created_at,
                           v.finalized_at,
                           p.full_name AS ten_khach, p.patient_code,
                           bs.full_name AS ten_bac_si,
                           st.name AS ten_dich_vu,
                           a.status AS trang_thai_lich
                      FROM visit v
                      LEFT JOIN patient p
                             ON p.clinic_patient_id = v.clinic_patient_id
                      LEFT JOIN staff bs ON bs.id = v.attending_doctor_id
                      LEFT JOIN service_type st ON st.id = v.service_type_id
                      LEFT JOIN appointment a ON a.id = v.appointment_id
                     WHERE v.clinic_id = $1::uuid
                       AND v.created_at >= $2 AND v.created_at < $3
                     ORDER BY v.created_at
                     LIMIT $4
                    """,
                    clinic_id,
                    dau_ngay,
                    cuoi_ngay,
                    _TRAN_TRANG_THAI,
                )
                trang_thai_kham = [_luot_kham(r) for r in rows]

        # Ba service sẵn có, gọi trong tiến trình — mỗi service tự acquire kết
        # nối NGẮN từ pool (tuần tự, không giữ chồng lên nhau).
        tuan_hen = await WeekAppointmentsService(self._pool).week(
            clinic_id=clinic_id, week_start=week_appt
        )
        checkin: list[dict[str, Any]] = []
        if identity.role == ClinicRole.MANAGEMENT:
            checkin = await DoctorBoardService(self._pool).board(
                clinic_id=clinic_id,
                start=dau_ngay,
                end=cuoi_ngay,
                doctor_id=None,
                statuses=_CHECKIN_STATUSES,
            )
        tien_trinh = await VisitProgressService(self._pool).for_range(
            date_from=ngay_tuan_hen[0],
            date_to=ngay_tuan_hen[-1],
            clinic_id=clinic_id,
        )

        return {
            "so_lieu": {
                "viec_dang_cho": so_viec,
                "khach_moi_hom_nay": so_khach_moi,
                "lich_cho_xac_nhan": so_lich_cho,
            },
            "roster": [dict(r) for r in roster],
            "truc_ca": [dict(r) for r in truc_ca],
            "trang_thai_kham": trang_thai_kham,
            "tuan_hen": tuan_hen,
            "checkin": checkin,
            "tien_trinh": [asdict(p) for p in tien_trinh],
        }


def _luot_kham(r: asyncpg.Record) -> dict[str, Any]:
    """Một dòng bảng trạng thái, LỒNG y như PostgREST embed cũ.

    VisitStatusBoard đọc `patient?.full_name`, `doctor?.full_name`,
    `service?.name`, `appointment?.status` — đổi hình là đổi cả bảng.
    """
    d = dict(r)
    ten_khach = d.pop("ten_khach", None)
    ma_khach = d.pop("patient_code", None)
    ten_bs = d.pop("ten_bac_si", None)
    ten_dv = d.pop("ten_dich_vu", None)
    trang_thai_lich = d.pop("trang_thai_lich", None)
    d["patient"] = (
        {"full_name": ten_khach, "patient_code": ma_khach}
        if (ten_khach or ma_khach)
        else None
    )
    d["doctor"] = {"full_name": ten_bs} if ten_bs else None
    d["service"] = {"name": ten_dv} if ten_dv else None
    d["appointment"] = (
        {"status": trang_thai_lich} if trang_thai_lich is not None else None
    )
    return d
