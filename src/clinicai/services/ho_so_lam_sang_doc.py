"""Đọc HỒ SƠ LÂM SÀNG của một khách cho màn bệnh án (24/09/2026).

Route giao diện `/api/clinical-record` (GET) từng tự đọc bảy bảng bằng Supabase
(hồ sơ y tế, thai kỳ, xét nghiệm, lượt khám + bệnh án, lịch sử, đơn thuốc, số đo)
và tự quyết thư ký được xem khách nào. Luật "frontend chỉ là giao diện" (SO-LUAT
Phần 3): đọc gì, của phòng khám nào, ai được xem — ở đây. Trang chỉ còn dựng ô.

Trả DỮ LIỆU THÔ; việc ghép ô hiển thị (sinh hiệu theo khoá phiếu, gộp chữ chẩn
đoán) vẫn ở giao diện vì đó là trình bày.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.lenh_kham_core import ma_uuid

#: Vai được thấy đơn thuốc nháp của thư ký (đường cũ, OFF từ 23/09 — còn đọc
#: được cho lượt cũ). Khớp hàm SQL `read_prescription_draft`.
_VAI_THAY_DON_NHAP = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)


#: Cột jsonb (asyncpg trả chuỗi) — CHỈ những cột này được giải JSON; giải mọi
#: chuỗi thì ô chữ như tên xét nghiệm "123" thành số.
_COT_JSON = frozenset(
    {
        "soap_subjective",
        "soap_objective",
        "soap_assessment",
        "soap_plan",
        "prescription_draft",
    }
)


def _gia_tri(cot: str, v: Any) -> Any:
    if cot in _COT_JSON and isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    if isinstance(v, datetime):
        return v.isoformat()
    return v


def _dong(r: asyncpg.Record | None) -> dict[str, Any] | None:
    return {k: _gia_tri(k, v) for k, v in dict(r).items()} if r is not None else None


async def doc_ho_so(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    patient_id: str,
    appointment_id: str | None = None,
    visit_id: str | None = None,
) -> dict[str, Any]:
    cid = identity.clinic_id
    pid = ma_uuid(patient_id, "Mã bệnh nhân không hợp lệ.")
    appt = (
        ma_uuid(appointment_id, "Mã lịch hẹn không hợp lệ.") if appointment_id else None
    )
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.") if visit_id else None

    if identity.co_vai({ClinicRole.TKYK}):
        # Thư ký chỉ xem khách của bác sĩ mình được phân (20260915000020).
        from clinicai.services.thu_ky_bac_si import khach_duoc_xem

        duoc = await khach_duoc_xem(pool, identity)
        if duoc is not None and pid not in duoc:
            raise SafetyGateError(
                "Khách này của bác sĩ khác — thư ký chỉ xem khách của bác sĩ"
                " mình được phân."
            )

    async with pool.acquire() as conn:
        co_khach = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM patient WHERE clinic_patient_id = $1::uuid"
            " AND clinic_id = $2::uuid)",
            pid,
            cid,
        )
        if not co_khach:
            raise ValidationError("Không tìm thấy bệnh nhân này.")

        ho_so = await conn.fetchrow(
            """
            SELECT blood_type, allergies, chronic_diseases, current_medications,
                   surgical_history, family_history, notes
              FROM patient_medical_profile
             WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid
            """,
            pid,
            cid,
        )
        thai = await conn.fetchrow(
            """
            SELECT edd_date, gestational_age_at_registration, is_high_risk,
                   high_risk_reason, outcome
              FROM pregnancy
             WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at DESC LIMIT 1
            """,
            pid,
            cid,
        )
        xet_nghiem = await conn.fetch(
            """
            SELECT test_name, result_value, result_numeric, result_unit, flag,
                   external_ref, triage_group, result_received_at
              FROM lab_result
             WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY result_received_at DESC NULLS LAST LIMIT 20
            """,
            pid,
            cid,
        )
        canh_bao_neu_day("ho_so.xet_nghiem", len(xet_nghiem), 20, clinic_id=cid)
        cot_luot = """
            SELECT v.visit_id::text, v.status, v.created_at,
                   r.revision, r.chief_complaint_at_visit, r.soap_subjective,
                   r.soap_objective, r.soap_assessment, r.soap_plan,
                   r.prescription_draft
              FROM visit v
              LEFT JOIN clinical_record r
                ON r.visit_id = v.visit_id AND r.clinic_id = v.clinic_id
        """
        if vid:
            luot = await conn.fetchrow(
                cot_luot
                + " WHERE v.visit_id = $1::uuid AND v.clinic_patient_id = $2::uuid"
                " AND v.clinic_id = $3::uuid",
                vid,
                pid,
                cid,
            )
        elif appt:
            luot = await conn.fetchrow(
                cot_luot
                + " WHERE v.appointment_id = $1::uuid AND v.clinic_id = $2::uuid"
                " ORDER BY v.created_at DESC LIMIT 1",
                appt,
                cid,
            )
        else:
            luot = None
        lich_su = await conn.fetch(
            """
            SELECT v.visit_id::text, v.status, v.created_at,
                   v.appointment_id::text, st.name AS service, s.full_name AS doctor,
                   r.chief_complaint_at_visit, r.soap_assessment
              FROM visit v
              LEFT JOIN service_type st ON st.id = v.service_type_id
              LEFT JOIN staff s ON s.id = v.attending_doctor_id
              LEFT JOIN clinical_record r
                ON r.visit_id = v.visit_id AND r.clinic_id = v.clinic_id
             WHERE v.clinic_patient_id = $1::uuid AND v.clinic_id = $2::uuid
             ORDER BY v.created_at DESC LIMIT 8
            """,
            pid,
            cid,
        )
        don: list[asyncpg.Record] = []
        sinh_hieu = None
        if luot is not None:
            don = await conn.fetch(
                """
                SELECT id::text, drug_catalog_id::text, drug_name_raw, quantity,
                       dosage_instructions, caution
                  FROM prescription
                 WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
                   AND removed_at IS NULL
                 ORDER BY created_at
                """,
                luot["visit_id"],
                cid,
            )
            sinh_hieu = await conn.fetchrow(
                """
                SELECT systolic, diastolic, pulse, temperature, weight_kg, height_cm,
                       respiratory_rate, spo2, bmi, pain_score, created_at
                  FROM vital_measurement
                 WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
                 ORDER BY created_at DESC LIMIT 1
                """,
                luot["visit_id"],
                cid,
            )

    lt = _dong(luot)
    return {
        "revision": (lt or {}).get("revision") or 0,
        "prescription_draft": (
            (lt or {}).get("prescription_draft")
            if identity.co_vai(_VAI_THAY_DON_NHAP)
            else None
        ),
        "profile": _dong(ho_so),
        "pregnancy": _dong(thai),
        "labs": [_dong(r) for r in xet_nghiem],
        "history_raw": [
            _dong(r) for r in lich_su if appt is None or r["appointment_id"] != appt
        ],
        "prescriptions": [_dong(r) for r in don],
        "vital_latest": _dong(sinh_hieu),
        "visit": (
            {
                "visit_id": lt["visit_id"],
                "status": lt["status"],
                "created_at": lt["created_at"],
            }
            if lt
            else None
        ),
        "draft": {
            "chief_complaint": (lt or {}).get("chief_complaint_at_visit") or "",
            "subjective": (lt or {}).get("soap_subjective"),
            "objective": (lt or {}).get("soap_objective"),
            "assessment": (lt or {}).get("soap_assessment"),
            "plan": (lt or {}).get("soap_plan"),
        },
    }


async def phieu_in_theo_lich(
    pool: asyncpg.Pool, *, identity: StaffIdentity, appointment_id: str
) -> dict[str, Any] | None:
    """Dữ liệu phiếu TÓM TẮT KHÁM để in theo một lịch hẹn (/print/[appointmentId]).

    24/09/2026: trang in từng đọc thẳng 4 bảng bằng Supabase. Trả thô — dàn
    trang in ở giao diện. None = không có lịch này ở phòng khám người gọi.
    """
    cid = identity.clinic_id
    appt = ma_uuid(appointment_id, "Mã lịch hẹn không hợp lệ.")
    async with pool.acquire() as conn:
        lich = await conn.fetchrow(
            """
            SELECT a.id::text, a.slot_start, a.status,
                   p.clinic_patient_id::text, p.patient_code, p.full_name,
                   p.date_of_birth, p.gender, p.ethnicity, p.nationality,
                   p.occupation, p.patient_objection, p.address, p.guardian_name,
                   p.phone_primary,
                   s.full_name AS doctor_name, st.name AS service_name,
                   l.name AS location_name
              FROM appointment a
              JOIN patient p
                ON p.clinic_patient_id = a.clinic_patient_id
               AND p.clinic_id = a.clinic_id
              LEFT JOIN staff s ON s.id = a.doctor_id
              LEFT JOIN service_type st ON st.id = a.service_type_id
              LEFT JOIN clinic_location l ON l.id = a.location_id
             WHERE a.clinic_id = $1::uuid AND a.id = $2::uuid
            """,
            cid,
            appt,
        )
        if lich is None:
            return None
        pid = lich["clinic_patient_id"]
        luot = await conn.fetchrow(
            """
            SELECT v.visit_id::text, v.status, v.created_at,
                   r.chief_complaint_at_visit, r.soap_subjective, r.soap_objective,
                   r.soap_assessment, r.soap_plan
              FROM visit v
              LEFT JOIN clinical_record r
                ON r.visit_id = v.visit_id AND r.clinic_id = v.clinic_id
             WHERE v.clinic_id = $1::uuid AND v.appointment_id = $2::uuid
             ORDER BY v.created_at DESC LIMIT 1
            """,
            cid,
            appt,
        )
        ho_so = await conn.fetchrow(
            """
            SELECT allergies, chronic_diseases, current_medications,
                   surgical_history, family_history, notes
              FROM patient_medical_profile
             WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
            """,
            cid,
            pid,
        )
        xn = await conn.fetch(
            """
            SELECT test_name, result_value, result_numeric, result_unit, flag
              FROM lab_result
             WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
               AND appointment_id = $3::uuid
             ORDER BY result_received_at DESC NULLS LAST LIMIT 20
            """,
            cid,
            pid,
            appt,
        )
    return {
        "appointment": _dong(lich),
        "visit": _dong(luot),
        "profile": _dong(ho_so),
        "labs": [_dong(r) for r in xn],
    }


__all__ = ["doc_ho_so", "phieu_in_theo_lich"]
