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
  * (khối `checkin` cho Quản lý đã gỡ 18/09/2026 — check-in chỉ còn ở màn
    Tiếp đón khách; xem docs/SITEMAP.md).
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
from clinicai.services.nhan_vai import gan_nhan_vai
from clinicai.services.visit_progress_service import VisitProgressService
from clinicai.services.week_appointments_service import WeekAppointmentsService

_VN = ZoneInfo("Asia/Ho_Chi_Minh")

# Trần giữ nguyên từ bản PostgREST của trang (limit 300 ở bảng trạng thái).
_TRAN_TRANG_THAI = 300

# Lịch đã chết — không tính vào tải bác sĩ (cùng bộ với week_appointments_service).
_TRANG_THAI_CHET = ("CANCELLED", "NO_SHOW", "DOCTOR_DECLINED")

# Quá giờ hẹn bao nhiêu phút mà chưa check-in thì coi là "khách trễ".
_PHUT_TRE = 15


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
            # LỊCH CẦN XỬ LÝ (Tuyền chốt 16/09/2026) — thay "Lịch chờ xác nhận"
            # (đếm status SCHEDULED, luôn 0 từ khi đặt xong là CONFIRMED). Đếm
            # KHÁCH đang có khung báo ở màn Quản lý khách hàng: vượt sức chứa,
            # cần xác nhận / nhắc lịch, kết quả được phép gửi hoặc về muộn quá
            # hạn, và lịch sắp tới bị gỡ bác sĩ.
            so_lich_can_xu_ly = await conn.fetchval(
                """
                SELECT count(DISTINCT x.pid) FROM (
                    SELECT v.clinic_patient_id AS pid
                      FROM v_viec_cskh v
                     WHERE v.clinic_id = $1::uuid
                       AND (v.trang_thai IN ('VUOT_SUC_CHUA', 'CHO_XAC_NHAN',
                                             'NHAC_HEN_MAI', 'KQ_CHUA_GUI')
                            OR (v.trang_thai = 'CHO_KQ_XN' AND v.qua_han))
                    UNION
                    SELECT a.clinic_patient_id
                      FROM appointment a
                     WHERE a.clinic_id = $1::uuid
                       AND a.bac_si_da_go_id IS NOT NULL
                       AND a.slot_start >= $2
                       AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                ) x
                """,
                clinic_id,
                dau_ngay,
            )
            # XU HƯỚNG 7 NGÀY cho ô số (Tuyền chốt kiểu "bảng A + thống kê B",
            # 27/09/2026). Chỉ hai ô có lịch sử dựng lại được từ dữ liệu:
            #  * khách mới — đếm `patient.created_at` theo ngày;
            #  * việc đang chờ — việc đã tạo trước cuối ngày d và lúc ấy CHƯA
            #    đóng (còn mở tới giờ, hoặc đóng sau cuối ngày d). Điểm cuối
            #    (hôm nay) vì thế trùng đúng `so_viec` ở trên.
            # "Lịch cần xử lý" là ảnh chụp của v_viec_cskh — không có lịch sử,
            # nên KHÔNG bịa đường xu hướng cho nó.
            xu_huong_khach_moi = await conn.fetch(
                """
                SELECT n.ngay, count(p.clinic_patient_id) AS so
                  FROM (SELECT d::date AS ngay,
                               d::date::timestamp
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh' AS dau,
                               (d::date + 1)::timestamp
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh' AS het
                          FROM generate_series($2::date, $3::date,
                                               interval '1 day') d) n
                  LEFT JOIN patient p
                         ON p.clinic_id = $1::uuid
                        AND p.created_at >= n.dau AND p.created_at < n.het
                 GROUP BY n.ngay ORDER BY n.ngay
                """,
                clinic_id,
                hom_nay - timedelta(days=6),
                hom_nay,
            )
            xu_huong_viec = await conn.fetch(
                """
                SELECT n.ngay, count(w.id) AS so
                  FROM (SELECT d::date AS ngay,
                               d::date::timestamp
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh' AS dau,
                               (d::date + 1)::timestamp
                                 AT TIME ZONE 'Asia/Ho_Chi_Minh' AS het
                          FROM generate_series($2::date, $3::date,
                                               interval '1 day') d) n
                  LEFT JOIN work_item w
                         ON w.clinic_id = $1::uuid
                        AND w.created_at < n.het
                        AND (w.status IN ('PENDING', 'IN_PROGRESS')
                             OR coalesce(w.finished_at, w.updated_at) >= n.het)
                 GROUP BY n.ngay ORDER BY n.ngay
                """,
                clinic_id,
                hom_nay - timedelta(days=6),
                hom_nay,
            )
            # TẢI BÁC SĨ HÔM NAY — số lịch còn sống của từng bác sĩ, kèm số đã
            # đến. Lịch chưa xếp ai gom một dòng (`doctor_id` rỗng).
            tai_bac_si = await conn.fetch(
                """
                SELECT a.doctor_id::text AS doctor_id, s.full_name AS ten,
                       count(*) AS so_lich,
                       count(*) FILTER (WHERE a.status IN ('CHECKED_IN', 'COMPLETED'))
                         AS da_den
                  FROM appointment a
                  LEFT JOIN staff s ON s.id = a.doctor_id
                 WHERE a.clinic_id = $1::uuid
                   AND a.slot_start >= $2 AND a.slot_start < $3
                   AND a.status <> ALL($4::text[])
                 GROUP BY a.doctor_id, s.full_name
                 ORDER BY (a.doctor_id IS NULL), count(*) DESC, s.full_name
                """,
                clinic_id,
                dau_ngay,
                cuoi_ngay,
                list(_TRANG_THAI_CHET),
            )
            # CẦN XỬ LÝ — việc tồn của ca, mỗi dòng một câu hỏi "ai phải làm
            # gì ngay". Không lặp "Lịch cần xử lý" (việc CSKH) đã có ở ô số.
            so_khach_tre = await conn.fetchval(
                """
                SELECT count(*) FROM appointment
                 WHERE clinic_id = $1::uuid
                   AND slot_start >= $2
                   AND slot_start < now() - make_interval(mins => $3)
                   AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                """,
                clinic_id,
                dau_ngay,
                _PHUT_TRE,
            )
            so_chua_xep_bac_si = await conn.fetchval(
                """
                SELECT count(*) FROM appointment
                 WHERE clinic_id = $1::uuid
                   AND doctor_id IS NULL
                   AND slot_start >= now()
                   AND status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                """,
                clinic_id,
            )
            so_viec_qua_han = await conn.fetchval(
                """
                SELECT count(*) FROM work_item
                 WHERE clinic_id = $1::uuid
                   AND status IN ('PENDING', 'IN_PROGRESS')
                   AND due_at < now()
                """,
                clinic_id,
            )
            # Lịch làm việc tuần — kèm staff.full_name để frontend đồng bộ tên
            # (thay truy vấn `staff` phụ của dongBoTenTrucNhat), và VAI của
            # người đứng (27/09/2026 đợt 3, A9: "tên nhân sự kèm vai trò").
            # Một người một membership đang bật mỗi phòng khám — cửa đăng nhập
            # từ chối nếu hai — nên LIMIT 1 theo đúng thứ tự cửa ấy dùng.
            roster = await conn.fetch(
                """
                SELECT w.work_date, w.station, w.staff_id, w.staff_name,
                       w.shift, s.full_name AS ten_staff,
                       (SELECT m.role FROM clinic_membership m
                         WHERE m.staff_id = w.staff_id
                           AND m.clinic_id = w.clinic_id AND m.is_active
                         ORDER BY m.created_at, m.id LIMIT 1) AS vai_ma
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
            # Khối NGHỈ của tuần lịch — bảng lịch trang chủ vẽ y hệt file Excel
            # (Tuyền 16/09/2026). Ô ĐEN (DONG) thôi trả từ 28/09/2026 (Tuyền:
            # "xoá ô đen, mở lại quyền đặt ca, đừng block nữa").
            dong_ca = await conn.fetch(
                """
                SELECT work_date, shift, station, ly_do
                  FROM vi_tri_dong_ca
                 WHERE clinic_id = $1::uuid AND ly_do = 'NGHI'
                   AND work_date >= $2::date
                   AND work_date < $2::date + 7
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
                   AND public.la_ca_kham_bac_si(clinic_id, station)
                   AND status = 'APPROVED'
                   AND staff_id IS NOT NULL
                """,
                clinic_id,
                ngay_tuan_hen,
            )
            trang_thai_kham: list[dict[str, Any]] = []
            if identity.co_vai({ClinicRole.RECEPTION}):
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
        tien_trinh = await VisitProgressService(self._pool).for_range(
            date_from=ngay_tuan_hen[0],
            date_to=ngay_tuan_hen[-1],
            clinic_id=clinic_id,
        )

        return {
            "so_lieu": {
                "viec_dang_cho": so_viec,
                "khach_moi_hom_nay": so_khach_moi,
                "lich_can_xu_ly": so_lich_can_xu_ly,
            },
            "xu_huong": {
                "ngay": [r["ngay"].isoformat() for r in xu_huong_khach_moi],
                "viec_dang_cho": [r["so"] for r in xu_huong_viec],
                "khach_moi_hom_nay": [r["so"] for r in xu_huong_khach_moi],
            },
            "tai_bac_si": [dict(r) for r in tai_bac_si],
            "can_xu_ly": [
                {"ma": "khach_tre", "so": so_khach_tre, "phut": _PHUT_TRE},
                {"ma": "chua_xep_bac_si", "so": so_chua_xep_bac_si},
                {"ma": "viec_qua_han", "so": so_viec_qua_han},
            ],
            "roster": [gan_nhan_vai(dict(r)) for r in roster],
            "dong_ca": [dict(r) for r in dong_ca],
            "truc_ca": [dict(r) for r in truc_ca],
            "trang_thai_kham": trang_thai_kham,
            "tuan_hen": tuan_hen,
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
