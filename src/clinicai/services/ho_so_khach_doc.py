"""Đọc HỒ SƠ KHÁCH cho trang /patients/[id] (24/09/2026).

Ba khối của trang (thông tin hành chính + lịch hẹn, lịch sử lâm sàng, nhật ký
CSKH) từng tự đọc bảng bằng Supabase. Nay đọc ở đây, lọc đúng phòng khám của
người gọi, và qua MỘT luật "được mở hồ sơ này không" (`duoc_mo`) — bác sĩ chỉ
khách có lịch với mình, thư ký chỉ khách của bác sĩ mình.

Dữ liệu trả về giữ nguyên DẠNG các component đang vẽ (`doctor: {full_name}`,
`clinical_record: {...}`) để không phải sửa phần trình bày.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.thu_ky_bac_si import khach_duoc_xem

_COT_JSON = frozenset(
    {"soap_subjective", "soap_objective", "soap_assessment", "soap_plan"}
)


def _gia(cot: str, v: Any) -> Any:
    if cot in _COT_JSON and isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _dong(r: asyncpg.Record) -> dict[str, Any]:
    return {k: _gia(k, v) for k, v in dict(r).items()}


async def duoc_mo(pool: asyncpg.Pool, identity: StaffIdentity, khach: str) -> bool:
    """Luật GIẤY PHÉP mở hồ sơ: thư ký → khách của bác sĩ mình; bác sĩ (khám /
    siêu âm) → khách có lịch với chính mình; vai khác → được."""
    if identity.co_vai({ClinicRole.TKYK}):
        ids = await khach_duoc_xem(pool, identity)
        return ids is None or khach in ids
    if identity.co_vai({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR}):
        return bool(
            await pool.fetchval(
                """
                SELECT EXISTS (SELECT 1 FROM appointment
                                WHERE clinic_id = $1::uuid
                                  AND clinic_patient_id = $2::uuid
                                  AND doctor_id = $3::uuid)
                """,
                identity.clinic_id,
                khach,
                identity.staff_id,
            )
        )
    return True


async def _chan_neu_khong_duoc(
    pool: asyncpg.Pool, identity: StaffIdentity, khach: str
) -> None:
    if not await duoc_mo(pool, identity, khach):
        raise SafetyGateError("Bạn không được mở hồ sơ khách này.")


async def hanh_chinh(
    pool: asyncpg.Pool, *, identity: StaffIdentity, khach: str
) -> dict[str, Any]:
    """Thông tin hành chính (mục I) + 20 lịch hẹn gần nhất."""
    await _chan_neu_khong_duoc(pool, identity, khach)
    cid = identity.clinic_id
    p = await pool.fetchrow(
        """
        SELECT clinic_patient_id::text, patient_code, full_name, date_of_birth,
               birth_year, gender, phone_primary, phone_secondary, ethnicity,
               nationality, occupation, patient_objection, address, guardian_name,
               van_de_di_kham, linh_vuc, created_at
          FROM patient
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
        """,
        cid,
        khach,
    )
    lich = await pool.fetch(
        """
        SELECT a.id::text, a.slot_start, a.status, a.booking_channel,
               s.full_name AS doctor_name, st.name AS service_name
          FROM appointment a
          LEFT JOIN staff s ON s.id = a.doctor_id
          LEFT JOIN service_type st ON st.id = a.service_type_id
         WHERE a.clinic_id = $1::uuid AND a.clinic_patient_id = $2::uuid
         ORDER BY a.slot_start DESC
         LIMIT 20
        """,
        cid,
        khach,
    )
    return {
        "patient": _dong(p) if p else None,
        "appointments": [
            {
                **{
                    k: v
                    for k, v in _dong(r).items()
                    if k not in ("doctor_name", "service_name")
                },
                "doctor": {"full_name": r["doctor_name"]} if r["doctor_name"] else None,
                "service": {"name": r["service_name"]} if r["service_name"] else None,
            }
            for r in lich
        ],
    }


async def lich_su_lam_sang(
    pool: asyncpg.Pool, *, identity: StaffIdentity, khach: str
) -> dict[str, Any]:
    """Lượt khám (+ SOAP), xét nghiệm, thai kỳ — nội dung y khoa (cửa ROLE-02
    ở router)."""
    await _chan_neu_khong_duoc(pool, identity, khach)
    cid = identity.clinic_id
    luot = await pool.fetch(
        """
        SELECT v.visit_id::text, v.status, v.created_at,
               s.full_name AS doctor_name, st.name AS service_name,
               r.chief_complaint_at_visit, r.soap_subjective, r.soap_objective,
               r.soap_assessment, r.soap_plan, (r.visit_id IS NOT NULL) AS co_ho_so
          FROM visit v
          LEFT JOIN staff s ON s.id = v.attending_doctor_id
          LEFT JOIN service_type st ON st.id = v.service_type_id
          LEFT JOIN clinical_record r
            ON r.visit_id = v.visit_id AND r.clinic_id = v.clinic_id
         WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
         ORDER BY v.created_at DESC
         LIMIT 50
        """,
        cid,
        khach,
    )
    xn = await pool.fetch(
        """
        SELECT lab_result_id::text, test_name, result_value, result_numeric,
               result_unit, flag, triage_group, is_finalized, result_received_at
          FROM lab_result
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
         ORDER BY result_received_at DESC NULLS LAST
         LIMIT 50
        """,
        cid,
        khach,
    )
    thai = await pool.fetch(
        """
        SELECT id::text, lmp_date, edd_date, gestational_age_at_registration,
               outcome, is_high_risk, high_risk_reason
          FROM pregnancy
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
         ORDER BY created_at DESC
        """,
        cid,
        khach,
    )

    def _luot(r: asyncpg.Record) -> dict[str, Any]:
        d = _dong(r)
        return {
            "visit_id": d["visit_id"],
            "status": d["status"],
            "created_at": d["created_at"],
            "doctor": {"full_name": d["doctor_name"]} if d["doctor_name"] else None,
            "service": {"name": d["service_name"]} if d["service_name"] else None,
            "clinical_record": (
                {
                    "chief_complaint_at_visit": d["chief_complaint_at_visit"],
                    "soap_subjective": d["soap_subjective"],
                    "soap_objective": d["soap_objective"],
                    "soap_assessment": d["soap_assessment"],
                    "soap_plan": d["soap_plan"],
                }
                if d["co_ho_so"]
                else None
            ),
        }

    canh_bao_neu_day("ho_so_khach.luot", len(luot), 50, clinic_id=cid)
    canh_bao_neu_day("ho_so_khach.xet_nghiem", len(xn), 50, clinic_id=cid)
    return {
        "visits": [_luot(r) for r in luot],
        "labs": [_dong(r) for r in xn],
        "pregnancies": [_dong(r) for r in thai],
    }


async def nhat_ky_cskh(
    pool: asyncpg.Pool, *, identity: StaffIdentity, khach: str
) -> list[dict[str, Any]]:
    """Nhật ký CSKH (bảng nhập từ Notion) của một khách — 30 dòng mới nhất."""
    await _chan_neu_khong_duoc(pool, identity, khach)
    rows = await pool.fetch(
        """
        SELECT id::text, work_date, slot_time, visit_type, arrived, has_test,
               tests, result_group, cskh_status, cskh_followup, last_cskh_date,
               cskh_by, note
          FROM cskh_log
         WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
         ORDER BY work_date DESC
         LIMIT 30
        """,
        identity.clinic_id,
        khach,
    )
    return [_dong(r) for r in rows]


__all__ = ["duoc_mo", "hanh_chinh", "lich_su_lam_sang", "nhat_ky_cskh"]
