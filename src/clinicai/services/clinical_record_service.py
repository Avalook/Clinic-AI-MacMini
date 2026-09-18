"""Writing the clinical record for a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/clinical-record/route.ts``, the largest
piece of clinical logic that was still living in the frontend. Every rule is
preserved, and each one exists because of something that went wrong or could:

* **Two write modes.** ``vitals_only`` is the nurse/reception path — vitals plus
  the chief complaint, nothing else. The full path is doctors, the medical
  secretary entering on their behalf, and nurses (widened 2026-06-29).
  Reception may only ever write vitals.
* **Vitals need the patient to have arrived.** Reception must have checked them
  in (CHECKED_IN, or COMPLETED so a correction is still possible), otherwise
  vitals could be recorded for somebody who never turned up.
* **A doctor writes on their own appointments** or unassigned walk-ins, never on
  another doctor's. TKYK and nurses are exempt because entering on behalf of a
  doctor is their job.
* **48-hour lock.** After roughly two shifts the record is closed; corrections
  go through the shift lead.
* **Chỉ trạng thái ĐANG SỐNG mới ghi được** — OPEN, IN_PROGRESS và INCOMPLETE
  (khách về giữa chừng). FINALIZED *và* AMENDED bất biến theo Thông tư 13. Đây
  là danh sách TRẮNG chứ không phải phép kiểm `!= FINALIZED`, nên một trạng thái
  CUỐI thêm sau này không lọt qua được.

  INCOMPLETE ghi được vì khách CÒN QUAY LẠI: khoá bút lúc đó là bắt bác sĩ phải
  đính chính một hồ sơ chưa ai ký.
* **Merging, not overwriting.** A doctor may have opened the form before the
  nurse entered vitals; saving blind would wipe them. Existing values are kept
  and only non-empty incoming fields override.

The whole write is one transaction. In the route it was five sequential
statements, so a failure part-way through could leave a visit with a record but
no prescriptions, or a record saved and the medical history lost.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.clinical_prescription_service import (
    _locked_prescription_matches,
    _validated_prescription_items,
    prepare_prescription_write,
)
from clinicai.services.luot_kham_rules import (
    Vitals,
    parse_vitals,
    thieu_sinh_hieu_khi_co_thai,
)
from clinicai.services.thu_ky_bac_si import (
    bac_si_cua_thu_ky,
    kiem_thu_ky_duoc_lam,
)

logger = structlog.get_logger()

PROFILE_COLUMNS: frozenset[str] = frozenset(
    {
        "blood_type",
        "allergies",
        "chronic_diseases",
        "current_medications",
        "surgical_history",
        "family_history",
        "notes",
    }
)


def validated_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Copy only the versioned medical-profile contract; reject unknown keys."""
    unknown = set(profile) - PROFILE_COLUMNS
    if unknown:
        raise ValidationError(
            "Trường tiền sử không hợp lệ: " + ", ".join(sorted(unknown))
        )
    return {key: profile[key] for key in profile if key in PROFILE_COLUMNS}


# Trạng thái lượt khám còn GHI ĐƯỢC hồ sơ.
#
# Danh sách TRẮNG, không phải kiểm `!= FINALIZED`. Cố ý: một trạng thái CUỐI
# thêm sau này sẽ không lọt qua được, còn danh sách đen thì lọt.
#
# INCOMPLETE (khách về giữa chừng) nằm TRONG danh sách này. Nó là trạng thái
# KHÔNG-CUỐI: khách còn quay lại, và khoá bút lúc này là bắt bác sĩ phải đính
# chính một hồ sơ chưa ai ký. FINALIZED và AMENDED thì bất biến theo Thông tư 13.
WRITABLE_VISIT_STATUSES: frozenset[str] = frozenset(
    {"OPEN", "IN_PROGRESS", "INCOMPLETE"}
)
ARRIVED_APPOINTMENT_STATUSES: frozenset[str] = frozenset({"CHECKED_IN", "COMPLETED"})
RECORD_LOCK = timedelta(hours=48)

# Full-record writers. Reception is absent on purpose; it appears only in the
# vitals-only path.
FULL_RECORD_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
    }
)
# ĐIỀU DƯỠNG CHỈ GHI SINH HIỆU (Tuyền chốt 16/09/2026).
#
# Từ 29/6 vai này được mở ghi trọn hồ sơ "như bác sĩ". Sau khi đối chiếu tài
# liệu bàn giao chuyên môn: điều dưỡng đo sinh hiệu, còn bệnh sử — tiền sử —
# khám — chẩn đoán là việc bác sĩ, thư ký nhập hộ thì bác sĩ vẫn phải duyệt.
# Mở rộng hơn thế là để một người không chịu trách nhiệm chuyên môn ghi vào
# phần chịu trách nhiệm chuyên môn.
VITALS_ONLY_EXTRA_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.RECEPTION, ClinicRole.NURSE_ULTRASOUND}
)
# Roles that enter on behalf of a doctor, so the ownership check does not apply.
ON_BEHALF_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.TKYK, ClinicRole.NURSE_ULTRASOUND}
)  # ĐD vẫn ở đây: đo sinh hiệu cho khách của bác sĩ khác là việc bình thường.


def may_write(role: ClinicRole, *, vitals_only: bool) -> bool:
    """Whether this role may write in this mode."""
    if role in FULL_RECORD_ROLES:
        return True
    return vitals_only and role in VITALS_ONLY_EXTRA_ROLES


def as_obj(value: Any) -> dict[str, Any]:
    """A JSON object, or an empty one. Lists and scalars are not partial records."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, dict) else {}


def non_empty(values: dict[str, Any]) -> dict[str, Any]:
    """Drop keys the user left blank, so a merge only overrides with real input."""
    return {
        key: value
        for key, value in values.items()
        if value is not None and not (isinstance(value, str) and value.strip() == "")
    }


def merge_objective(
    previous: Any, incoming: Any, *, incoming_was_sent: bool
) -> dict[str, Any] | None:
    """Merge the doctor's SOAP-objective over what is already recorded.

    The nurse's vitals must survive a doctor saving a form they opened earlier,
    so previous vitals are kept and only non-blank incoming ones override. When
    nothing was sent and nothing is stored, the column stays NULL rather than
    becoming an empty object.
    """
    prev = as_obj(previous)
    incoming_obj = as_obj(incoming)

    if not incoming_was_sent and not prev:
        return None

    merged: dict[str, Any] = {**prev, **incoming_obj}
    merged["vitals"] = {
        **as_obj(prev.get("vitals")),
        **non_empty(as_obj(incoming_obj.get("vitals"))),
    }
    return merged


#: Khoá JSON của hồ sơ khám cũ → trường của `Vitals` (luot_kham_rules).
KHOA_SINH_HIEU_HO_SO: dict[str, str] = {
    "mach": "pulse",
    "nhiet_do": "temperature",
    "can_nang": "weight_kg",
    "chieu_cao": "height_cm",
    # Bốn khoá thêm 16/09/2026. Trước đó chúng có ô nhập trên màn nhưng không
    # được map, nên chỉ nằm lại trong JSONB của hồ sơ: không vào bảng lịch sử
    # chỉ-thêm, không so được giữa các lần đo.
    "nhip_tho": "respiratory_rate",
    "spo2": "spo2",
    # "bmi" không map (S0-3, 18/09/2026): BMI chỉ tính từ cân nặng/chiều cao.
    "muc_do_dau": "pain_score",
}


def sinh_hieu_tu_ho_so(vitals: dict[str, Any], *, co_thai: bool) -> Vitals:
    """Sinh hiệu JSON của hồ sơ khám → `Vitals` đã qua CÙNG luật với luồng khám.

    Luật PM (CONTEXT v1.0): 100% đo huyết áp; có thai thêm chiều cao + cân nặng.
    Huyết áp hồ sơ cũ là chuỗi "120/80": không đoán "120" một mình hay "120-80"
    — một huyết áp đoán sai còn tệ hơn một câu nhắc ghi lại.
    """
    raw: dict[str, Any] = {
        dich: vitals.get(nguon) for nguon, dich in KHOA_SINH_HIEU_HO_SO.items()
    }
    huyet_ap = str(vitals.get("huyet_ap") or "").strip()
    if huyet_ap:
        phan = [x.strip() for x in huyet_ap.split("/")]
        if len(phan) != 2:
            raise ValidationError(
                f"Huyết áp {huyet_ap!r} không đúng dạng — "
                "ghi tâm thu/tâm trương, ví dụ 120/80."
            )
        raw["systolic"], raw["diastolic"] = phan
    parsed, loi = parse_vitals(raw)
    if parsed is None:
        raise ValidationError(loi or "Sinh hiệu không hợp lệ.")
    loi_thai = thieu_sinh_hieu_khi_co_thai(parsed, co_thai=co_thai)
    if loi_thai:
        raise ValidationError(loi_thai)
    return parsed


def merge_vitals_only(previous: Any, incoming: Any) -> dict[str, Any]:
    """The nurse path: replace vitals, leave every other section alone.

    Diagnosis, plan and history belong to the doctor and are not touched.
    """
    return {**as_obj(previous), "vitals": as_obj(incoming).get("vitals") or {}}


class ClinicalRecordService:
    """Create or update the clinical record attached to an appointment's visit."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save(
        self,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        identity: StaffIdentity,
        vitals_only: bool = False,
        expected_revision: int | None = None,
        approve_prescription_draft: bool = False,
        chief_complaint: str | None = None,
        subjective: Any = None,
        objective: Any = None,
        objective_sent: bool = False,
        assessment: Any = None,
        plan: Any = None,
        profile: dict[str, Any] | None = None,
        prescriptions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Write the record. Returns the visit id it was written to."""
        # ĐƯỜNG ĐÓN-KHÁM CŨ ĐÃ BỎ (Tuyền chốt 17/09/2026: "cái nào cũ thì bỏ").
        # Sinh hiệu chỉ đo ở màn Đo sinh hiệu (POST /luot-kham/visits/{id}/vitals):
        # lưu qua đây từng làm khách kẹt ngoài hàng chờ bác sĩ. Bác sĩ/thư ký bổ
        # sung sinh hiệu trong bệnh án đầy đủ vẫn được (đồng bộ luồng khám).
        if vitals_only:
            raise ValidationError(
                "Sinh hiệu đo ở màn Đo sinh hiệu — mở menu Điều dưỡng → Đo sinh hiệu."
            )
        if not any(may_write(v, vitals_only=vitals_only) for v in identity.cac_vai()):
            raise SafetyGateError(
                "Chỉ bác sĩ / điều dưỡng / lễ tân mới ghi sinh hiệu + lý do khám."
                if vitals_only
                else "Chỉ bác sĩ mới ghi hồ sơ khám."
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                appointment = await conn.fetchrow(
                    """
                    SELECT
                        a.status,
                        a.doctor_id,
                        a.clinic_patient_id,
                        p.clinic_patient_id IS NOT NULL AS patient_in_clinic,
                        (
                            a.doctor_id IS NULL
                            OR EXISTS (
                                SELECT 1
                                  FROM staff st
                                  JOIN clinic_membership m
                                    ON m.staff_id = st.id
                                 WHERE st.id = a.doctor_id
                                   AND st.is_active
                                   AND m.clinic_id = a.clinic_id
                                   AND m.is_active
                                   AND m.role IN (
                                       'DOCTOR', 'ULTRASOUND_DOCTOR'
                                   )
                            )
                        ) AS doctor_in_clinic
                      FROM appointment a
                      LEFT JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                     WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
                    """,
                    appointment_id,
                    identity.clinic_id,
                )
                if appointment is None:
                    raise ValidationError("Không tìm thấy lịch hẹn")
                if (
                    not appointment["patient_in_clinic"]
                    or str(appointment["clinic_patient_id"]) != clinic_patient_id
                ):
                    raise ValidationError(
                        "Lịch hẹn không thuộc bệnh nhân này trong phòng khám"
                    )
                if not appointment["doctor_in_clinic"]:
                    raise ValidationError(
                        "Bác sĩ của lịch hẹn không thuộc phòng khám này"
                    )

                if vitals_only and appointment["status"] not in (
                    ARRIVED_APPOINTMENT_STATUSES
                ):
                    raise ConflictError(
                        "Chờ lễ tân check-in bệnh nhân (đã đến) "
                        "trước khi điền sinh hiệu."
                    )

                if (
                    not vitals_only
                    and not identity.co_vai(ON_BEHALF_ROLES)
                    and appointment["doctor_id"] is not None
                    and str(appointment["doctor_id"]) != identity.staff_id
                ):
                    raise SafetyGateError(
                        "Lịch hẹn này thuộc bác sĩ khác — không thể ghi hồ sơ khám."
                    )

                visit_id = await self._writable_visit(
                    conn,
                    appointment_id=appointment_id,
                    clinic_patient_id=clinic_patient_id,
                    appointment_doctor_id=appointment["doctor_id"],
                    identity=identity,
                    vitals_only=vitals_only,
                )

                stored = await conn.fetchrow(
                    "SELECT soap_objective, revision, prescription_draft "
                    "FROM clinical_record "
                    "WHERE visit_id = $1::uuid AND clinic_id = $2::uuid "
                    "FOR UPDATE",
                    visit_id,
                    identity.clinic_id,
                )
                current_revision = stored["revision"] if stored is not None else 0
                if not vitals_only and (
                    expected_revision is None or expected_revision != current_revision
                ):
                    raise ConflictError(
                        "Bệnh án đã thay đổi hoặc thiếu phiên bản đang sửa — "
                        "hãy tải lại và đối chiếu trước khi lưu"
                    )
                # Thư ký chỉ ghi bệnh án cho bác sĩ mình được phân (20260915000020).
                # Kiểm NGAY TRƯỚC lệnh ghi đầu tiên của từng nhánh (sinh hiệu /
                # bệnh án), sau mọi kiểm tra phiên bản và đơn thuốc.
                bac_si_lich = (
                    str(appointment["doctor_id"]) if appointment["doctor_id"] else None
                )
                stored_objective = stored["soap_objective"] if stored else None
                if vitals_only and approve_prescription_draft:
                    raise SafetyGateError(
                        "Chỉ lưu bệnh án đầy đủ mới duyệt được đơn thuốc"
                    )

                # SINH HIỆU LÀ LỊCH SỬ (15/09/2026): lần lưu nào đổi số sinh hiệu
                # thì kiểm luật PM và thêm một dòng `vital_measurement` — cùng
                # bảng, cùng luật với màn luồng khám. Đường điều dưỡng THAY bộ
                # sinh hiệu nên kiểm bộ gửi lên; bác sĩ lưu hồ sơ thì GỘP lên số
                # cũ nên kiểm bộ sau gộp.
                vitals_cu = non_empty(as_obj(as_obj(stored_objective).get("vitals")))
                if vitals_only:
                    vitals_moi = non_empty(as_obj(as_obj(objective).get("vitals")))
                else:
                    vitals_moi = non_empty(
                        {
                            **vitals_cu,
                            **non_empty(as_obj(as_obj(objective).get("vitals"))),
                        }
                    )
                if vitals_only or vitals_moi != vitals_cu:
                    if identity.co_vai({ClinicRole.TKYK}):
                        kiem_thu_ky_duoc_lam(
                            await bac_si_cua_thu_ky(conn, identity), bac_si_lich
                        )
                    await self._ghi_sinh_hieu(
                        conn,
                        identity=identity,
                        visit_id=visit_id,
                        clinic_patient_id=clinic_patient_id,
                        vitals=vitals_moi,
                    )
                    # Đường cũ cũng phải đẩy khách vào hàng chờ bác sĩ/thư ký
                    # như màn Đo sinh hiệu (17/09/2026) — xem
                    # LuotKhamService.dong_bo_sinh_hieu_tu_ho_so.
                    await self._dong_bo_luong_kham(conn, identity, str(visit_id))

                if vitals_only:
                    revision = await self._save_vitals(
                        conn,
                        visit_id=visit_id,
                        stored_objective=stored_objective,
                        objective=objective,
                        chief_complaint=chief_complaint,
                        clinic_id=identity.clinic_id,
                    )
                    # Sinh hiệu là ghi chép lâm sàng, chỉ hẹp hơn về nội dung —
                    # nó vẫn phải để lại dấu vết như phần còn lại của bệnh án.
                    await record_event(
                        conn,
                        event_type="clinical_record.vitals_saved",
                        aggregate_type="visit",
                        aggregate_id=str(visit_id),
                        identity=identity,
                        origin="api:clinical-record",
                        payload={
                            "visit_id": str(visit_id),
                            "appointment_id": appointment_id,
                            "vitals_only": True,
                        },
                    )
                    return {
                        "visit_id": str(visit_id),
                        "vitals_only": True,
                        "revision": revision,
                    }

                prescription_write = await prepare_prescription_write(
                    conn,
                    visit_id=visit_id,
                    identity=identity,
                    draft=as_obj(stored.get("prescription_draft")) or None
                    if stored
                    else None,
                    items=prescriptions,
                    approve=approve_prescription_draft,
                )
                if identity.co_vai({ClinicRole.TKYK}):
                    kiem_thu_ky_duoc_lam(
                        await bac_si_cua_thu_ky(conn, identity), bac_si_lich
                    )
                revision = int(
                    await conn.fetchval(
                        """
                    INSERT INTO clinical_record (
                        clinic_id, visit_id, chief_complaint_at_visit,
                            soap_subjective, soap_objective, soap_assessment, soap_plan,
                            prescription_draft
                    )
                        VALUES ($7::uuid, $1::uuid, $2, $3, $4, $5, $6, $8::jsonb)
                    ON CONFLICT (visit_id) DO UPDATE SET
                        chief_complaint_at_visit = EXCLUDED.chief_complaint_at_visit,
                        soap_subjective          = EXCLUDED.soap_subjective,
                        soap_objective           = EXCLUDED.soap_objective,
                        soap_assessment          = EXCLUDED.soap_assessment,
                            soap_plan                = EXCLUDED.soap_plan,
                            prescription_draft       = EXCLUDED.prescription_draft
                    RETURNING revision
                    """,
                        visit_id,
                        (chief_complaint or "").strip() or None,
                        _json_or_none(subjective),
                        _json_or_none(
                            merge_objective(
                                stored_objective,
                                objective,
                                incoming_was_sent=objective_sent,
                            )
                        ),
                        _json_or_none(assessment),
                        _json_or_none(plan),
                        identity.clinic_id,
                        _json_or_none(prescription_write.draft),
                    )
                )

                if profile:
                    await self._save_profile(
                        conn, clinic_patient_id, profile, identity.clinic_id
                    )

                if prescription_write.items is not None:
                    await self._replace_prescriptions(
                        conn,
                        visit_id=visit_id,
                        clinic_patient_id=clinic_patient_id,
                        prescriptions=prescription_write.items,
                        clinic_id=identity.clinic_id,
                        created_by=identity.staff_id
                        if identity.co_vai(
                            {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR}
                        )
                        else None,
                    )
                if approve_prescription_draft:
                    await record_event(
                        conn,
                        event_type="prescription.draft_approved",
                        aggregate_type="visit",
                        aggregate_id=str(visit_id),
                        identity=identity,
                        origin="api:clinical-record",
                        payload={
                            "recorded_by": prescription_write.recorded_by,
                            "revision": revision,
                        },
                    )

                # TÊN PHẦN ĐÃ GHI, KHÔNG PHẢI NỘI DUNG. "Ai sửa bệnh án nào,
                # lúc nào, đụng những mục nào" trả lời được câu hỏi của quản lý
                # và của thanh tra; nội dung bệnh án thì thuộc màn khác, RLS
                # khác, và một nhóm người khác được đọc (xem services/audit.py).
                await record_event(
                    conn,
                    event_type="clinical_record.saved",
                    aggregate_type="visit",
                    aggregate_id=str(visit_id),
                    identity=identity,
                    origin="api:clinical-record",
                    payload={
                        "visit_id": str(visit_id),
                        "appointment_id": appointment_id,
                        "sections": sorted(
                            name
                            for name, value in (
                                ("chief_complaint", chief_complaint),
                                ("subjective", subjective),
                                ("objective", objective),
                                ("assessment", assessment),
                                ("plan", plan),
                                ("profile", profile),
                            )
                            if value
                        ),
                        "prescription_count": (
                            len(prescriptions) if prescriptions is not None else None
                        ),
                    },
                )

        logger.info(
            "clinical_record_saved",
            visit_id=str(visit_id),
            vitals_only=vitals_only,
            by_staff_id=identity.staff_id,
        )
        return {"visit_id": str(visit_id), "vitals_only": False, "revision": revision}

    async def _writable_visit(
        self,
        conn: asyncpg.Connection,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        appointment_doctor_id: Any,
        identity: StaffIdentity,
        vitals_only: bool,
    ) -> Any:
        """Find the appointment's visit or create a draft, refusing closed ones."""
        existing = await conn.fetchrow(
            """
            SELECT visit_id, status, created_at, clinic_patient_id
              FROM visit
             WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at DESC
             LIMIT 1
             FOR UPDATE
            """,
            appointment_id,
            identity.clinic_id,
        )

        if existing is not None:
            if str(existing["clinic_patient_id"]) != clinic_patient_id:
                raise ValidationError(
                    "Lượt khám không thuộc bệnh nhân của lịch hẹn này"
                )
            created_at = existing["created_at"]
            if created_at is not None:
                age = datetime.now(timezone.utc) - created_at
                if age > RECORD_LOCK:
                    raise SafetyGateError(
                        "Hồ sơ đã khóa sau 48h — không thể chỉnh sửa. "
                        "Liên hệ Trưởng ca nếu cần đính chính."
                    )
            if existing["status"] not in WRITABLE_VISIT_STATUSES:
                raise ConflictError(
                    f"Hồ sơ đã chốt ({existing['status']}) — luật cấm sửa, "
                    "phải đính chính."
                )
            return existing["visit_id"]

        # A nurse or secretary opening the visit does not become the attending
        # doctor — the appointment's doctor does.
        attending = (
            appointment_doctor_id
            if (vitals_only or identity.co_vai(ON_BEHALF_ROLES))
            else identity.staff_id
        )

        visit_id = await conn.fetchval(
            """
            INSERT INTO visit (
                clinic_id, clinic_patient_id, appointment_id,
                attending_doctor_id, status, checked_in_at
            )
            VALUES ($4::uuid, $1::uuid, $2::uuid, $3::uuid,
                    'IN_PROGRESS', now())
            ON CONFLICT (appointment_id) WHERE appointment_id IS NOT NULL
            DO NOTHING
            RETURNING visit_id
            """,
            clinic_patient_id,
            appointment_id,
            str(attending) if attending else None,
            identity.clinic_id,
        )
        if visit_id is not None:
            return visit_id

        # A nurse and doctor can both observe no visit. ON CONFLICT keeps the
        # transaction usable (unlike catching a UniqueViolation after it has
        # aborted PostgreSQL's transaction), then this row lock serializes the
        # objective merge with the winner.
        again = await conn.fetchrow(
            """
            SELECT visit_id, status, clinic_patient_id FROM visit
             WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at DESC LIMIT 1
             FOR UPDATE
            """,
            appointment_id,
            identity.clinic_id,
        )
        if again is None:
            raise ConflictError(
                "Lượt khám vừa được tạo nhưng chưa thể đọc lại, hãy thử lại"
            )
        if str(again["clinic_patient_id"]) != clinic_patient_id:
            raise ValidationError("Lượt khám không thuộc bệnh nhân của lịch hẹn này")
        if again["status"] not in WRITABLE_VISIT_STATUSES:
            raise ConflictError(f"Hồ sơ đã chốt ({again['status']}) — luật cấm sửa.")
        return again["visit_id"]

    async def _dong_bo_luong_kham(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> None:
        """Đẩy lượt khám sang bước kế tiếp sau khi sinh hiệu lưu qua bệnh án."""
        from clinicai.services.luot_kham_service import LuotKhamService

        await LuotKhamService(self._pool).dong_bo_sinh_hieu_tu_ho_so(
            conn, identity, visit_id
        )

    async def _ghi_sinh_hieu(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        visit_id: str,
        clinic_patient_id: str,
        vitals: dict[str, Any],
    ) -> None:
        co_thai = bool(
            await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM pregnancy "
                "WHERE clinic_id = $1::uuid "
                "AND clinic_patient_id = $2::uuid "
                "AND coalesce(outcome, 'ONGOING') = 'ONGOING')",
                identity.clinic_id,
                clinic_patient_id,
            )
        )
        so = sinh_hieu_tu_ho_so(vitals, co_thai=co_thai)
        await conn.execute(
            """
            INSERT INTO vital_measurement
                (clinic_id, visit_id, systolic, diastolic, pulse, temperature,
                 weight_kg, height_cm, respiratory_rate, spo2, bmi,
                 pain_score, recorded_by)
            SELECT $1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                   $12, $13::uuid
            -- SỐ KHÔNG ĐỔI SO VỚI LẦN ĐO GẦN NHẤT THÌ KHÔNG GHI THÊM (17/09/2026).
            -- Ô không gửi (NULL) không tính là đổi:
            -- form bệnh án hiện sẵn số điều dưỡng đo; lưu bệnh án mà không sửa
            -- số vẫn thêm một "lần đo" đứng tên bác sĩ, và hồ sơ in "Đo lúc
            -- 07:27 · BS Thành" cho số ĐD Huế đo lúc 06:50.
             WHERE NOT EXISTS (
                SELECT 1 FROM (
                    SELECT * FROM vital_measurement g
                     WHERE g.clinic_id = $1::uuid AND g.visit_id = $2::uuid
                     ORDER BY g.created_at DESC LIMIT 1) g
                 WHERE ($3::smallint IS NULL OR g.systolic = $3::smallint)
                   AND ($4::smallint IS NULL OR g.diastolic = $4::smallint)
                   AND ($5::smallint IS NULL OR g.pulse = $5::smallint)
                   AND ($6::numeric IS NULL OR g.temperature = $6::numeric)
                   AND ($7::numeric IS NULL OR g.weight_kg = $7::numeric)
                   AND ($8::numeric IS NULL OR g.height_cm = $8::numeric)
                   AND ($9::integer IS NULL OR g.respiratory_rate = $9::integer)
                   AND ($10::integer IS NULL OR g.spo2 = $10::integer)
                   AND ($12::integer IS NULL OR g.pain_score = $12::integer))
            """,
            identity.clinic_id,
            visit_id,
            so.systolic,
            so.diastolic,
            so.pulse,
            so.temperature,
            so.weight_kg,
            so.height_cm,
            so.respiratory_rate,
            so.spo2,
            so.bmi,
            so.pain_score,
            identity.staff_id,
        )
        # KHÔNG đổi encounter_flow.vitals_status ở đây: luồng khám mới quyết
        # tuyến (_decide_route) ngay sau lệnh ghi sinh hiệu của chính nó; đánh
        # dấu "đã đo" từ màn cũ mà không quyết tuyến thì lượt kẹt không ai gọi.

    async def _save_vitals(
        self,
        conn: asyncpg.Connection,
        *,
        visit_id: Any,
        stored_objective: Any,
        objective: Any,
        chief_complaint: str | None,
        clinic_id: str | None,
    ) -> int:
        merged = merge_vitals_only(stored_objective, objective)
        complaint = (chief_complaint or "").strip()

        # The complaint is only written when the nurse typed one; an empty save
        # must not erase what the doctor already recorded.
        revision = await conn.fetchval(
            """
            INSERT INTO clinical_record
                (clinic_id, visit_id, soap_objective, chief_complaint_at_visit)
            VALUES ($4::uuid, $1::uuid, $2, $3)
            ON CONFLICT (visit_id) DO UPDATE SET
                soap_objective = EXCLUDED.soap_objective,
                chief_complaint_at_visit = COALESCE(
                    EXCLUDED.chief_complaint_at_visit,
                    clinical_record.chief_complaint_at_visit
                )
            RETURNING revision
            """,
            visit_id,
            json.dumps(merged),
            complaint or None,
            clinic_id,
        )
        return int(revision)

    async def _save_profile(
        self,
        conn: asyncpg.Connection,
        clinic_patient_id: str,
        profile: dict[str, Any],
        clinic_id: str | None,
    ) -> None:
        safe_profile = validated_profile(profile)
        columns = list(safe_profile)
        if not columns:
            return
        assignments = ", ".join(f"{col} = ${i + 2}" for i, col in enumerate(columns))
        placeholders = ", ".join(f"${i + 2}" for i in range(len(columns)))
        await conn.execute(
            f"""
            INSERT INTO patient_medical_profile
                (clinic_id, clinic_patient_id, {", ".join(columns)})
            VALUES (${len(columns) + 2}::uuid, $1::uuid, {placeholders})
            ON CONFLICT (clinic_patient_id) DO UPDATE SET {assignments}
            """,
            clinic_patient_id,
            *[safe_profile[col] for col in columns],
            clinic_id,
        )

    async def _replace_prescriptions(
        self,
        conn: asyncpg.Connection,
        *,
        visit_id: Any,
        clinic_patient_id: str,
        prescriptions: list[dict[str, Any]],
        clinic_id: str | None,
        created_by: str | None = None,
    ) -> None:
        """Lưu đơn thuốc của lượt — KHÔNG xoá dòng nhà thuốc đã đụng tới.

        Bản cũ xoá TOÀN BỘ đơn rồi chèn lại mỗi lần lưu bệnh án. Từ khi có cấp
        phát một phần (20260807000004), mỗi dòng đơn mang số ĐÃ CẤP và sổ kho
        trỏ về `prescription.id`. Lưu lại bệnh án sau khi dược sĩ đã cấp là:
        mất dấu đã cấp, sổ kho trỏ vào dòng không còn tồn tại, và dòng mới về
        CHUA_CAP — cấp lại được, trừ kho hai lần (phát hiện 15/09/2026).

        Luật:
          · Dòng ĐÃ KHOÁ = đã cấp (`dispensed_qty > 0`) hoặc đã chốt/từ chối
            (`closed_at`). Không bao giờ bị xoá. Bản gửi lên phải còn đúng thuốc
            và số lượng của nó, không thì từ chối bằng câu nói rõ dòng nào —
            sửa đơn đã cấp là việc của nhà thuốc, không phải của nút Lưu.
            Liều dùng/lưu ý của dòng khoá được cập nhật tại chỗ theo `id`.
            Bản cũ thiếu `id` chỉ được ghép khi không có dòng trùng tên/số lượng.
          · Dòng CHƯA KHOÁ vẫn là bản nháp: thay như cũ.
          · Dòng mới ghi luôn `quantity_num`/`unit` bằng CHÍNH hàm SQL của
            migration cấp phát — trước đây không đường ghi nào điền hai cột
            này, nên chốt "không cấp quá số kê" chưa từng chạy với đơn mới.
          · `source_ref` duy nhất theo dòng (uuid), không theo vị trí: dòng khoá
            giữ ref cũ nên đánh số lại từ 0 sẽ đụng UNIQUE.
        """

        cu = await conn.fetch(
            """
            SELECT id, drug_name_raw, quantity, dispensed_qty, closed_at
              FROM prescription
             WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
             ORDER BY created_at, id
               FOR UPDATE
            """,
            visit_id,
            clinic_id,
        )
        gui_len = _validated_prescription_items(
            prescriptions, {str(row["id"]) for row in cu}
        )
        locked_matches = _locked_prescription_matches(list(cu), gui_len)
        matched = {id(item) for _, item in locked_matches}
        con_lai = [item for item in gui_len if id(item) not in matched]
        for dong, khop in locked_matches:
            await conn.execute(
                """
                UPDATE prescription
                   SET dosage_instructions = $3, caution = $4, updated_at = now()
                 WHERE id = $1::uuid AND clinic_id = $2::uuid
                """,
                dong["id"],
                clinic_id,
                (khop.get("dosage") or "").strip() or None,
                (khop.get("caution") or "").strip() or None,
            )

        await conn.execute(
            """
            DELETE FROM prescription
             WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
               AND dispensed_qty = 0 AND closed_at IS NULL
            """,
            visit_id,
            clinic_id,
        )
        rows = [
            (
                f"dash-rx-{visit_id}-{uuid.uuid4().hex}",
                clinic_patient_id,
                str(visit_id),
                (item.get("drug_name") or "").strip(),
                (item.get("quantity") or "").strip() or None,
                (item.get("dosage") or "").strip() or None,
                (item.get("caution") or "").strip() or None,
                clinic_id,
                created_by,
            )
            for item in con_lai
        ]
        if not rows:
            return
        await conn.executemany(
            """
            INSERT INTO prescription (
                source_ref, clinic_patient_id, visit_id, drug_name_raw,
                quantity, dosage_instructions, caution, clinic_id,
                quantity_num, unit, created_by
            )
            VALUES ($1, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::uuid,
                    public.so_luong_tu_van_ban($5),
                    public.don_vi_tu_van_ban($5), $9::uuid)
            """,
            rows,
        )


def _json_or_none(value: Any) -> str | None:
    return None if value is None else json.dumps(value)
