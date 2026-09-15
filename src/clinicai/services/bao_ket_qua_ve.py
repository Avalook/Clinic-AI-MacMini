"""Kết quả về → báo CSKH và bác sĩ của khách (Tuyền chốt 15/09/2026).

Kết quả xét nghiệm nhiều khi do đối tác làm. Khi kết quả được nhập / tệp kết
quả được tải lên: CSKH (theo vai) và BÁC SĨ CỦA KHÁCH (đích danh) nhận thông báo
chuông; bác sĩ bấm cho phép gửi thì CSKH gửi (luật 20260915000011).

Chạy SAU khi giao dịch ghi kết quả đã commit và NUỐT LỖI: kết quả đã lưu, một
thông báo hỏng không được làm hỏng việc đã xong (cùng mẫu booking_service).
"""

from __future__ import annotations

import asyncpg
import structlog

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.thong_bao_service import ThongBaoService

logger = structlog.get_logger()


async def bao_ket_qua_ve(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    loai: str,
    ref_id: str,
    clinic_patient_id: str | None,
    appointment_id: str | None,
    visit_id: str | None,
) -> None:
    try:
        row = await pool.fetchrow(
            """
            SELECT p.full_name, p.patient_code,
                   coalesce(v.attending_doctor_id, a.doctor_id)::text AS bac_si_id
              FROM patient p
              LEFT JOIN visit v
                ON v.clinic_id = p.clinic_id
               AND (v.visit_id = $3::uuid OR v.appointment_id = $4::uuid)
              LEFT JOIN appointment a
                ON a.clinic_id = p.clinic_id AND a.id = $4::uuid
             WHERE p.clinic_id = $1::uuid AND p.clinic_patient_id = $2::uuid
             ORDER BY v.checked_in_at DESC NULLS LAST
             LIMIT 1
            """,
            identity.clinic_id,
            clinic_patient_id,
            visit_id,
            appointment_id,
        )
        if row is None:
            return
        ten = f"{row['full_name']} ({row['patient_code']})"
        nhan = "Tệp kết quả" if loai == "tep" else "Kết quả xét nghiệm"
        tieu_de = f"{nhan} của {ten} đã về"
        tb = ThongBaoService(pool)
        await tb.goi(
            identity=identity,
            vai_nhan=ClinicRole.CSKH.value,
            nguon="ket_qua_ve",
            nguon_id=f"{loai}:{ref_id}",
            muc_do="THUONG",
            tieu_de=tieu_de,
            noi_dung="Chờ bác sĩ cho phép rồi gửi cho khách.",
            duong_dan=f"/customers?selected={clinic_patient_id}",
        )
        noi_dung_bs = "Xem và bấm cho phép gửi để CSKH gửi cho khách."
        if row["bac_si_id"]:
            await tb.goi_nguoi(
                identity=identity,
                nguoi_nhan_staff_id=row["bac_si_id"],
                nguon="ket_qua_ve",
                nguon_id=f"{loai}:{ref_id}",
                tieu_de=tieu_de,
                noi_dung=noi_dung_bs,
                duong_dan="/result-review",
            )
        else:
            # Chưa biết bác sĩ của khách → báo cả vai bác sĩ, không bỏ rơi kết quả.
            await tb.goi(
                identity=identity,
                vai_nhan=ClinicRole.DOCTOR.value,
                nguon="ket_qua_ve",
                nguon_id=f"{loai}:{ref_id}",
                muc_do="THUONG",
                tieu_de=tieu_de,
                noi_dung=noi_dung_bs,
                duong_dan="/result-review",
            )
    except Exception:  # noqa: BLE001 — xem docstring module
        logger.warning(
            "bao_ket_qua_ve_that_bai", loai=loai, ref_id=ref_id, exc_info=True
        )
