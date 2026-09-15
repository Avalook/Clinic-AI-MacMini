"""Bác sĩ chính nghỉ giữa chừng → trưởng ca chuyển lượt cho bác sĩ khác (15/09/2026).

LUẬT (Tuyền chốt): trưởng ca chuyển cho bác sĩ khác, BẮT BUỘC lý do; bác sĩ mới
đọc bệnh án đang dở rồi khám tiếp.

Trước bản này không có đường nào: `reschedule` đổi được `appointment.doctor_id`
(không lý do) nhưng không đụng `visit.attending_doctor_id`, và phiên khám của
luồng mới vẫn khoá cho bác sĩ cũ (CONSULTATION_TAKEN). Bệnh án không cần chép:
nó gắn với LƯỢT KHÁM, và quyền ghi đọc bác sĩ của lịch hẹn — đổi bác sĩ ở cả hai
chỗ là bác sĩ mới mở ra thấy đúng bản đang dở.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event

logger = structlog.get_logger()

VAI_DOI_BAC_SI: frozenset[ClinicRole] = frozenset(
    {ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT}
)
_LUOT_CON_MO = ("OPEN", "IN_PROGRESS")


class DoiBacSiService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def bac_si_trong_phong_kham(
        self, *, identity: StaffIdentity
    ) -> list[dict[str, Any]]:
        rows = await self._pool.fetch(
            """
            SELECT s.id::text AS id, s.full_name, m.role
              FROM clinic_membership m
              JOIN staff s ON s.id = m.staff_id AND s.is_active
             WHERE m.clinic_id = $1::uuid AND m.is_active
               AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR')
             ORDER BY s.full_name
            """,
            identity.clinic_id,
        )
        return [dict(r) for r in rows]

    async def doi(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        bac_si_moi_id: str,
        ly_do: str,
    ) -> dict[str, Any]:
        if identity.role not in VAI_DOI_BAC_SI:
            raise SafetyGateError("Chỉ trưởng ca / quản lý chuyển bác sĩ giữa lượt.")
        ly_do_sach = (ly_do or "").strip()
        if not ly_do_sach:
            raise ValidationError("Chuyển bác sĩ giữa lượt phải ghi lý do.")

        async with self._pool.acquire() as conn, conn.transaction():
            visit = await conn.fetchrow(
                """
                SELECT visit_id::text AS visit_id, status, appointment_id,
                       attending_doctor_id::text AS bac_si_cu
                  FROM visit
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   FOR UPDATE
                """,
                identity.clinic_id,
                visit_id,
            )
            if visit is None:
                raise NotFoundError("Không tìm thấy lượt khám này.")
            if visit["status"] == "INCOMPLETE":
                # Khách về giữa chừng: không còn ai để bác sĩ mới khám tiếp.
                raise ValidationError(
                    "Khách đã rời phòng khám giữa chừng — không chuyển bác sĩ."
                )
            if visit["status"] not in _LUOT_CON_MO:
                raise ValidationError("Lượt khám đã đóng — không chuyển bác sĩ được.")
            if visit["bac_si_cu"] == bac_si_moi_id:
                raise ValidationError("Lượt khám đang ở chính bác sĩ này.")
            la_bac_si = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM clinic_membership m
                      JOIN staff s ON s.id = m.staff_id AND s.is_active
                     WHERE m.clinic_id = $1::uuid AND m.staff_id = $2::uuid
                       AND m.is_active
                       AND m.role IN ('DOCTOR', 'ULTRASOUND_DOCTOR'))
                """,
                identity.clinic_id,
                bac_si_moi_id,
            )
            if not la_bac_si:
                raise ValidationError("Người nhận không phải bác sĩ đang làm ở đây.")

            await conn.execute(
                """
                UPDATE visit SET attending_doctor_id = $3::uuid, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                visit_id,
                bac_si_moi_id,
            )
            if visit["appointment_id"] is not None:
                await conn.execute(
                    """
                    UPDATE appointment SET doctor_id = $3::uuid, updated_at = now()
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    """,
                    identity.clinic_id,
                    visit["appointment_id"],
                    bac_si_moi_id,
                )
            # Luồng khám mới: phiên khám + chỗ trong hàng bác sĩ theo người mới.
            await conn.execute(
                """
                UPDATE consultation
                   SET doctor_staff_id = $3::uuid,
                       started_by = CASE WHEN status = 'in_progress'
                                         THEN $3::uuid ELSE started_by END,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND status IN ('queued', 'in_progress')
                """,
                identity.clinic_id,
                visit_id,
                bac_si_moi_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET doctor_staff_id = $3::uuid, version = version + 1,
                       updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND lane = 'DOCTOR'
                   AND status IN ('blocked', 'waiting', 'called', 'serving')
                """,
                identity.clinic_id,
                visit_id,
                bac_si_moi_id,
            )
            await record_event(
                conn,
                event_type="visit.doctor_reassigned",
                aggregate_type="visit",
                aggregate_id=visit_id,
                identity=identity,
                origin="api:dispatch",
                payload={
                    "tu_bac_si_id": visit["bac_si_cu"],
                    "sang_bac_si_id": bac_si_moi_id,
                    "ly_do": ly_do_sach,
                },
            )
        logger.info("visit_doctor_reassigned", visit_id=visit_id, by=identity.staff_id)
        return {"ok": True, "visit_id": visit_id, "bac_si_moi_id": bac_si_moi_id}
