"""Foetal ultrasound measurements attached to a visit (W5, ADR-0012).

Ported from ``src/dashboard/app/api/ultrasound/route.ts``. Rules preserved 1:1,
including the ones that are deliberate clinical restraint rather than missing
features:

* **ULTRASOUND_DOCTOR only.** Not widened to doctors in general.
* **EFW is typed in, never computed.** Hadlock and friends would be easy to add
  and are exactly the kind of "helpful" inference that puts a number nobody
  chose onto a pregnancy record. It stays manual until the clinic's doctor
  signs off on a formula.
* **Abnormality is a doctor pressing a button**, never derived from the
  measurements.
* A visit that is no longer OPEN or IN_PROGRESS is closed to edits: measurements
  cannot be changed after the record is finalised.
* One ultrasound_record per visit; measurements merge into the existing
  ``findings`` JSONB rather than replacing it, so saving just BPD does not wipe
  the rest of the exam.

The visit find-or-create and the record write now share a transaction. In the
route they did not, so a crash in between left an empty visit attached to the
appointment.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.audit import record_event

logger = structlog.get_logger()

MEASURE_KEYS: tuple[str, ...] = ("crl", "nt", "bpd", "hc", "ac", "fl", "efw")
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


def num_or_none(value: Any) -> float | None:
    """A measurement, or None for anything that is not a finite number.

    An empty field means "not measured", which is different from zero, so a
    blank must never become 0.0 on a pregnancy record.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return number


def merge_findings(
    previous: dict[str, Any] | None,
    *,
    measurements: dict[str, Any] | None,
    is_abnormal: bool | None,
    status: str | None,
) -> dict[str, Any]:
    """Merge an update into the findings already recorded.

    Pure, so the merge — the part that could quietly lose a measurement — is
    testable without a database.
    """
    merged: dict[str, Any] = dict(previous or {})
    if measurements:
        for key in MEASURE_KEYS:
            if key in measurements:
                merged[key] = num_or_none(measurements[key])
    if is_abnormal is not None:
        merged["is_abnormal"] = is_abnormal
    if status:
        merged["status"] = status
    return merged


class UltrasoundService:
    """Record foetal measurements against a visit."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def save_measurements(
        self,
        *,
        appointment_id: str,
        clinic_patient_id: str,
        measurements: dict[str, Any] | None,
        is_abnormal: bool | None,
        status: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Upsert the visit's ultrasound record. Returns the merged findings."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                appointment = await conn.fetchrow(
                    """
                    SELECT
                        a.clinic_patient_id,
                        p.clinic_patient_id IS NOT NULL AS patient_in_clinic,
                        EXISTS (
                            SELECT 1
                              FROM clinic_membership m
                             WHERE m.staff_id = $3::uuid
                               AND m.clinic_id = a.clinic_id
                               AND m.is_active
                        ) AS performer_in_clinic
                      FROM appointment a
                      LEFT JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                     WHERE a.id = $1::uuid AND a.clinic_id = $2::uuid
                    """,
                    appointment_id,
                    identity.clinic_id,
                    identity.staff_id,
                )
                if appointment is None:
                    raise ValidationError("Không tìm thấy lịch hẹn siêu âm")
                if (
                    not appointment["patient_in_clinic"]
                    or str(appointment["clinic_patient_id"]) != clinic_patient_id
                ):
                    raise ValidationError("Lịch hẹn siêu âm không thuộc bệnh nhân này")
                if not appointment["performer_in_clinic"]:
                    raise ValidationError("Bác sĩ siêu âm không thuộc phòng khám này")

                visit = await conn.fetchrow(
                    """
                    SELECT visit_id, status, clinic_patient_id
                      FROM visit
                     WHERE appointment_id = $1::uuid AND clinic_id = $2::uuid
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    appointment_id,
                    identity.clinic_id,
                )

                if visit is not None:
                    if str(visit["clinic_patient_id"]) != clinic_patient_id:
                        raise ValidationError(
                            "Lượt khám siêu âm không thuộc bệnh nhân này"
                        )
                    if visit["status"] not in WRITABLE_VISIT_STATUSES:
                        raise ConflictError(
                            f"Hồ sơ đã chốt ({visit['status']}) — không sửa số đo."
                        )
                    visit_id = visit["visit_id"]
                else:
                    # The sonographer is the attending doctor for their own scan.
                    visit_id = await conn.fetchval(
                        """
                        INSERT INTO visit (
                            clinic_id, clinic_patient_id, appointment_id,
                            attending_doctor_id, status, checked_in_at
                        )
                        VALUES ($4::uuid, $1::uuid, $2::uuid, $3::uuid,
                                'IN_PROGRESS', now())
                        RETURNING visit_id
                        """,
                        clinic_patient_id,
                        appointment_id,
                        identity.staff_id,
                        identity.clinic_id,
                    )

                record = await conn.fetchrow(
                    """
                    SELECT ultrasound_id, findings, clinic_patient_id
                      FROM ultrasound_record
                     WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
                     ORDER BY created_at DESC
                     LIMIT 1
                    """,
                    visit_id,
                    identity.clinic_id,
                )
                if (
                    record is not None
                    and str(record["clinic_patient_id"]) != clinic_patient_id
                ):
                    raise ValidationError(
                        "Phiếu siêu âm không thuộc bệnh nhân của lượt khám này"
                    )

                findings = merge_findings(
                    _as_dict(record["findings"]) if record else None,
                    measurements=measurements,
                    is_abnormal=is_abnormal,
                    status=status,
                )

                if record is not None:
                    await conn.execute(
                        """
                        UPDATE ultrasound_record
                           SET findings = $2, performed_by = $3::uuid,
                               performed_at = now()
                         WHERE ultrasound_id = $1 AND clinic_id = $4::uuid
                        """,
                        record["ultrasound_id"],
                        _json(findings),
                        identity.staff_id,
                        identity.clinic_id,
                    )
                else:
                    # ON CONFLICT, VÌ CÂU SELECT Ở TRÊN KHÔNG KHOÁ GÌ CẢ.
                    #
                    # Giữa lúc đọc "chưa có phiếu" và lúc ghi, một request khác
                    # có thể đã ghi xong. Trước 20260803000006 bảng không có ràng
                    # buộc duy nhất nào, nên kết quả là HAI phiếu siêu âm cho một
                    # lượt khám, không lỗi, không dấu hiệu — và lần đọc sau lấy
                    # phiếu nào là tuỳ thứ tự database trả về, tức số đo hiện ra
                    # có thể là bản cũ.
                    #
                    # uq_ultrasound_visit_type biến cuộc đua đó thành xung đột,
                    # và DO UPDATE hợp nhất nó vào đúng phiếu đang có thay vì bắt
                    # người dùng nhập lại.
                    await conn.execute(
                        """
                        INSERT INTO ultrasound_record (
                            clinic_id, visit_id, clinic_patient_id, performed_by,
                            ultrasound_type, findings, performed_at
                        )
                        VALUES ($5::uuid, $1::uuid, $2::uuid, $3::uuid, 'Thai',
                                $4, now())
                        ON CONFLICT (clinic_id, visit_id, ultrasound_type)
                            WHERE visit_id IS NOT NULL
                        DO UPDATE SET
                            findings     = EXCLUDED.findings,
                            performed_by = EXCLUDED.performed_by,
                            performed_at = now()
                        """,
                        visit_id,
                        clinic_patient_id,
                        identity.staff_id,
                        _json(findings),
                        identity.clinic_id,
                    )

                # Số đo siêu âm là dữ liệu lâm sàng và cũng là căn cứ của quyết
                # định điều trị — ai nhập, lúc nào, cho lượt khám nào phải có
                # dấu vết. Ghi TÊN chỉ số đã nhập, không ghi trị số.
                await record_event(
                    conn,
                    event_type=(
                        "ultrasound.measurements_updated"
                        if record is not None
                        else "ultrasound.measurements_created"
                    ),
                    aggregate_type="ultrasound_record",
                    aggregate_id=str(visit_id),
                    identity=identity,
                    origin="api:ultrasound",
                    payload={
                        "visit_id": str(visit_id),
                        "measurements": sorted(measurements.keys())
                        if isinstance(measurements, dict)
                        else [],
                        "is_abnormal": is_abnormal,
                        "status": status,
                    },
                )

        logger.info(
            "ultrasound_measurements_saved",
            visit_id=str(visit_id),
            by_staff_id=identity.staff_id,
        )
        return findings


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        import json

        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return value or {}


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value)
