"""Đọc HỒ SƠ LÂM SÀNG của một khách cho màn bệnh án (24/09/2026).

Route giao diện `/api/clinical-record` (GET) từng tự đọc bảy bảng bằng Supabase
(hồ sơ y tế, thai kỳ, xét nghiệm, lượt khám + bệnh án, lịch sử, đơn thuốc, số đo)
và tự quyết thư ký được xem khách nào. Luật "frontend chỉ là giao diện" (SO-LUAT
Phần 3): đọc gì, của phòng khám nào, ai được xem — ở đây. Trang chỉ còn dựng ô.

Trả DỮ LIỆU THÔ; việc ghép ô hiển thị (sinh hiệu theo khoá phiếu, gộp chữ chẩn
đoán) vẫn ở giao diện vì đó là trình bày.

24/09/2026 (cách B): `doc_ho_so` ráp từ CỔNG ĐỌC của các module — xem
`ho_so/cong_doc.py`. `phieu_in_theo_lich` vẫn tự đọc (phiếu in cần lát cắt khác:
xét nghiệm của đúng lịch ấy) — nợ chuyển sang cổng.
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
from clinicai.ho_so.cong_doc import NguCanhHoSo, ghep_ho_so
from clinicai.services.lenh_kham_core import ma_uuid

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
    """Hồ sơ lâm sàng = bản RÁP từ cổng đọc của các module (cách B, 24/09/2026).

    Hàm này chỉ còn quyết BỐI CẢNH (khách nào, lượt nào, thư ký có được xem
    không); nội dung từng phần do module sở hữu dữ liệu tự đọc qua cổng khai ở
    `modules.py` (`ho_so/cong_doc.py`). Thêm module = khai thêm cổng.
    """
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

        # Bối cảnh: LƯỢT nào đang xem — theo mã lượt, hoặc lượt mới nhất của lịch.
        luot: str | None = None
        if vid:
            luot = await conn.fetchval(
                "SELECT visit_id::text FROM visit WHERE visit_id = $1::uuid"
                " AND clinic_patient_id = $2::uuid AND clinic_id = $3::uuid",
                vid,
                pid,
                cid,
            )
        elif appt:
            luot = await conn.fetchval(
                "SELECT visit_id::text FROM visit WHERE appointment_id = $1::uuid"
                " AND clinic_id = $2::uuid ORDER BY created_at DESC LIMIT 1",
                appt,
                cid,
            )
        return await ghep_ho_so(
            conn,
            NguCanhHoSo(
                identity=identity,
                clinic_id=cid,
                khach=pid,
                visit_id=luot,
                appointment_id=appt,
            ),
        )


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
    canh_bao_neu_day("phieu_in.xet_nghiem", len(xn), 20, clinic_id=cid)
    return {
        "appointment": _dong(lich),
        "visit": _dong(luot),
        "profile": _dong(ho_so),
        "labs": [_dong(r) for r in xn],
    }


__all__ = ["doc_ho_so", "phieu_in_theo_lich"]
