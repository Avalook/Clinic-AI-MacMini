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
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.ho_so.cong_doc import NguCanhHoSo, dong
from clinicai.permissions.can import doi_quyen
from clinicai.phieu_kham.mang_sang import doc_chan_doan
from clinicai.services.audit import record_event
from clinicai.services.clinical_prescription_service import (
    prepare_prescription_write,
)
from clinicai.services.dinh_chinh_don import luu_don_chua_ky
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


#: Lưu bệnh án có kèm sinh hiệu thì ghi `vital_measurement` + đẩy bước sinh hiệu
#: sang "đã đo" (đường cũ 17/09). OFF từ 24/09: một đường ghi duy nhất là màn
#: Đo sinh hiệu. Xem chú thích tại chỗ dùng trong `save`.
HO_SO_GHI_SINH_HIEU = False


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
        prescription_correction_reason: str | None = None,
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
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # QUYỀN, không vai (CORE-B3, 23/09/2026): `clinical.record.write`,
                # hỏi trong chính giao dịch ghi.
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.record.write",
                    cau="Bạn không có quyền ghi bệnh án.",
                )
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
                # MỘT ĐƯỜNG GHI SINH HIỆU (24/09/2026, nợ "Single write path for
                # vitals"): lưu bệnh án KHÔNG tạo số đo, KHÔNG hoàn tất bước sinh
                # hiệu nữa — số đo chỉ vào từ màn Đo sinh hiệu ([Bắt đầu] →
                # lưu), để mốc "ai đo, lúc nào" luôn thật. Bệnh án vẫn lưu bình
                # thường (ô sinh hiệu nằm trong nội dung hồ sơ). Cũ thì OFF:
                # bật lại bằng `HO_SO_GHI_SINH_HIEU = True`.
                if HO_SO_GHI_SINH_HIEU and (vitals_only or vitals_moi != vitals_cu):
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
                        # NGƯỜI NHẬP (Tuyền 24/09: ghi đúng người nhập, thư ký =
                        # bác sĩ). Duyệt nháp cũ: người nhập là thư ký đã gõ.
                        created_by=prescription_write.recorded_by or identity.staff_id,
                        identity=identity,
                        ly_do_dinh_chinh=prescription_correction_reason,
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
        from clinicai.services.sinh_hieu_service import SinhHieuService

        await SinhHieuService(self._pool).dong_bo_sinh_hieu_tu_ho_so(
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
        identity: StaffIdentity | None = None,
        ly_do_dinh_chinh: str | None = None,
    ) -> dict[str, Any]:
        """Lưu đơn thuốc CHƯA KÝ — theo mức dấu vết, xem `dinh_chinh_don`.

        Lịch sử: bản đầu xoá TOÀN BỘ đơn rồi chèn lại (mất số đã cấp, sổ kho trỏ
        vào dòng không còn — 15/09/2026); CP2 khoá mọi dòng khi đã thu và bắt
        thu ngân huỷ phiếu trước. CP6 (20/09/2026): dòng đã có dấu vết không
        sửa nghĩa tại chỗ mà ĐÍNH CHÍNH — dòng cũ ở lại làm lịch sử, bác sĩ
        không phải huỷ phiếu / hoàn tiền trước.
        """
        try:
            return await luu_don_chua_ky(
                conn,
                visit_id=visit_id,
                clinic_id=clinic_id,
                clinic_patient_id=clinic_patient_id,
                prescriptions=prescriptions,
                created_by=created_by,
                identity=identity,
                ly_do=ly_do_dinh_chinh,
            )
        except asyncpg.CheckViolationError as exc:
            # Lưới DB (4a) chặn một thay đổi service đã không lường trước — nói
            # thành câu 409, không để 500.
            raise ConflictError(
                "Đơn thuốc không lưu được: "
                + (exc.message or "vi phạm luật đơn thuốc")
                + ". Tải lại bệnh án rồi thử lại."
            ) from exc


def _json_or_none(value: Any) -> str | None:
    return None if value is None else json.dumps(value)


# ── CỔNG ĐỌC cho hồ sơ khám (cách B, 24/09/2026 — `ho_so/cong_doc.py`) ──────

#: Vai được thấy đơn thuốc NHÁP của thư ký (đường cũ, OFF từ 23/09 — còn đọc
#: được cho lượt cũ). Khớp hàm SQL `read_prescription_draft`.
_VAI_THAY_DON_NHAP = frozenset(
    {ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR, ClinicRole.TKYK}
)
_COT_BENH_AN_JSON = (
    "soap_subjective",
    "soap_objective",
    "soap_assessment",
    "soap_plan",
    "prescription_draft",
)


async def ho_so_y_te_cho_ho_so(
    conn: asyncpg.Connection, ngu_canh: NguCanhHoSo
) -> dict[str, Any]:
    """Tiền sử, dị ứng, bệnh mạn, thuốc đang dùng… của khách."""
    r = await conn.fetchrow(
        """
        SELECT blood_type, allergies, chronic_diseases, current_medications,
               surgical_history, family_history, notes
          FROM patient_medical_profile
         WHERE clinic_patient_id = $1::uuid AND clinic_id = $2::uuid
        """,
        ngu_canh.khach,
        ngu_canh.clinic_id,
    )
    return {"profile": dong(r)}


async def benh_an_cho_ho_so(
    conn: asyncpg.Connection, ngu_canh: NguCanhHoSo
) -> dict[str, Any]:
    """Bệnh án (SOAP) của lượt đang xem + revision để lưu không đè nhau."""
    lt = None
    if ngu_canh.visit_id:
        lt = dong(
            await conn.fetchrow(
                """
                SELECT v.visit_id::text, v.status, v.created_at,
                       EXISTS (SELECT 1 FROM phieu_kham_luot p
                                WHERE p.clinic_id = v.clinic_id
                                  AND p.visit_id = v.visit_id) AS phieu_v5,
                       r.revision, r.chief_complaint_at_visit, r.soap_subjective,
                       r.soap_objective, r.soap_assessment, r.soap_plan,
                       r.prescription_draft
                  FROM visit v
                  LEFT JOIN clinical_record r
                    ON r.visit_id = v.visit_id AND r.clinic_id = v.clinic_id
                 WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
                """,
                ngu_canh.visit_id,
                ngu_canh.clinic_id,
            ),
            _COT_BENH_AN_JSON,
        )
    g = lt or {}
    return {
        "revision": g.get("revision") or 0,
        "prescription_draft": (
            g.get("prescription_draft")
            if ngu_canh.identity.co_vai(_VAI_THAY_DON_NHAP)
            else None
        ),
        "visit": (
            {
                "visit_id": g["visit_id"],
                "status": g["status"],
                "created_at": g["created_at"],
                # Lượt ghi phiếu khám v5 (29/09/2026): màn bệnh án cũ mở phiếu v5
                # chỉ-xem thay cho phiếu theo dịch vụ đời cũ (trống với lượt này).
                "phieu_v5": bool(g.get("phieu_v5")),
            }
            if lt
            else None
        ),
        "draft": {
            "chief_complaint": g.get("chief_complaint_at_visit") or "",
            "subjective": g.get("soap_subjective"),
            "objective": g.get("soap_objective"),
            "assessment": g.get("soap_assessment"),
            "plan": g.get("soap_plan"),
        },
    }


async def lich_su_cho_ho_so(
    conn: asyncpg.Connection, ngu_canh: NguCanhHoSo
) -> dict[str, Any]:
    """8 lượt khám gần nhất (bỏ chính lượt của lịch đang mở)."""
    rows = await conn.fetch(
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
        ngu_canh.khach,
        ngu_canh.clinic_id,
    )
    appt = ngu_canh.appointment_id
    ra: list[dict[str, Any]] = []
    for r in rows:
        if appt is not None and r["appointment_id"] == appt:
            continue
        d = dong(r, ["soap_assessment"]) or {}
        # Lượt ghi phiếu v5: chẩn đoán nằm ở mục D của phiếu (29/09/2026) —
        # phiếu v5 trước, bệnh án đời cũ sau.
        cd = await doc_chan_doan(
            conn, clinic_id=ngu_canh.clinic_id, visit_id=r["visit_id"]
        )
        if cd:
            d["soap_assessment"] = cd
        ra.append(d)
    return {"history_raw": ra}
