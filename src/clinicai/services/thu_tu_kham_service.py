"""Khách ưu tiên (cờ hồ sơ) và thứ tự khám lễ tân kéo tay (15/09/2026).

LUẬT (Tuyền chốt 15/09 tối): không còn ghế/vé ưu tiên. Khách ưu tiên/VIP là
một DẤU trên hồ sơ kèm lý do để lễ tân biết. Khám theo thứ tự check-in; hôm nào
cần thì lễ tân tự kéo một người lên trước ai đó (theo chỉ đạo trưởng ca) —
không có luật nào tự đẩy ai lên.

Thứ tự tay lưu thành MỐC (`visit.thu_tu_tay_ms`, epoch ms "coi như check-in lúc
này"), không phải số thứ tự: kéo X vào giữa A và B thì X nhận trung điểm mốc của
A và B. Xem migration 20260915000016.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event

logger = structlog.get_logger()

#: Ai được kéo thứ tự khám: lễ tân đứng quầy, trưởng ca chỉ đạo, quản lý.
VAI_KEO_THU_TU: frozenset[ClinicRole] = frozenset(
    {ClinicRole.RECEPTION, ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT}
)
#: Ai được đánh dấu khách ưu tiên: người tiếp xúc khách + trưởng ca, quản lý.
VAI_DANH_DAU_UU_TIEN: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.CSKH,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)

#: Kéo lên đầu/xuống cuối hàng: cách người kế bên bao nhiêu mili giây.
KHOANG_DAU_CUOI_MS = 1000.0


def moc_moi(truoc: float | None, sau: float | None) -> float:
    """Mốc cho người vừa được kéo, nằm SAU `sau` và TRƯỚC `truoc`.

    `sau` = mốc người đứng ngay trên chỗ thả; `truoc` = mốc người đứng ngay
    dưới. Thiếu cả hai là lời gọi sai — không có chỗ nào để thả.
    """
    if truoc is not None and sau is not None:
        if sau >= truoc:
            raise ValidationError("Thứ tự hai người kế bên không hợp lệ.")
        return (sau + truoc) / 2
    if truoc is not None:
        return truoc - KHOANG_DAU_CUOI_MS
    if sau is not None:
        return sau + KHOANG_DAU_CUOI_MS
    raise ValidationError("Chưa chọn chỗ thả trong hàng chờ.")


_MOC_SQL = """
SELECT a.id::text AS appointment_id, v.visit_id::text AS visit_id,
       coalesce(v.thu_tu_tay_ms,
                extract(epoch FROM v.checked_in_at) * 1000)::float8 AS moc
  FROM appointment a
  JOIN LATERAL (
      SELECT vi.visit_id, vi.checked_in_at, vi.thu_tu_tay_ms
        FROM visit vi
       WHERE vi.appointment_id = a.id AND vi.clinic_id = a.clinic_id
       ORDER BY vi.checked_in_at DESC NULLS LAST
       LIMIT 1
  ) v ON TRUE
 WHERE a.clinic_id = $1::uuid
   AND a.id = ANY($2::uuid[])
   AND a.status = 'CHECKED_IN'
   AND v.checked_in_at IS NOT NULL
"""


class ThuTuKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def keo(
        self,
        *,
        identity: StaffIdentity,
        appointment_id: str,
        sau_appointment_id: str | None,
        truoc_appointment_id: str | None,
    ) -> dict[str, Any]:
        """Đặt khách vào giữa hai người trong hàng chờ đã check-in."""
        ids = [appointment_id] + [
            x for x in (sau_appointment_id, truoc_appointment_id) if x
        ]
        if len(set(ids)) != len(ids):
            raise ValidationError("Không thể kéo một khách vào cạnh chính mình.")
        async with self._pool.acquire() as conn, conn.transaction():
            # Kéo thứ tự hỏi QUYỀN "Check-in khách" (24/09/2026 — cùng người với
            # VAI_KEO_THU_TU: lễ tân / trưởng ca / quản lý).
            await doi_quyen(
                conn,
                identity,
                "reception.checkin.perform",
                cau="Chỉ lễ tân / trưởng ca / quản lý đổi thứ tự khám.",
            )
            rows = await conn.fetch(_MOC_SQL, identity.clinic_id, ids)
            theo_id = {r["appointment_id"]: r for r in rows}
            if appointment_id not in theo_id:
                raise NotFoundError("Khách này không còn trong hàng chờ đã check-in.")
            for x in (sau_appointment_id, truoc_appointment_id):
                if x and x not in theo_id:
                    raise ValidationError(
                        "Hàng chờ vừa thay đổi — tải lại rồi kéo lại."
                    )
            moc = moc_moi(
                theo_id[truoc_appointment_id]["moc"] if truoc_appointment_id else None,
                theo_id[sau_appointment_id]["moc"] if sau_appointment_id else None,
            )
            visit_id = theo_id[appointment_id]["visit_id"]
            await conn.execute(
                """
                UPDATE visit
                   SET thu_tu_tay_ms = $3, thu_tu_tay_boi = $4::uuid,
                       thu_tu_tay_luc = now(), updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                visit_id,
                moc,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="queue.reordered",
                aggregate_type="visit",
                aggregate_id=visit_id,
                identity=identity,
                origin="api:queue-reorder",
                payload={
                    "appointment_id": appointment_id,
                    "sau_appointment_id": sau_appointment_id,
                    "truoc_appointment_id": truoc_appointment_id,
                },
            )
        logger.info(
            "queue_reordered", appointment_id=appointment_id, by=identity.staff_id
        )
        return {"ok": True, "visit_id": visit_id, "thu_tu_tay_ms": moc}

    async def dat_uu_tien(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str,
        uu_tien: bool,
        ly_do: str | None,
    ) -> dict[str, Any]:
        """Bật/tắt dấu khách ưu tiên. Bật thì bắt buộc lý do."""
        if not identity.co_vai(VAI_DANH_DAU_UU_TIEN):
            raise SafetyGateError(
                "Chỉ lễ tân / CSKH / trưởng ca / quản lý đánh dấu khách ưu tiên."
            )
        ly_do_sach = (ly_do or "").strip() or None
        if uu_tien and not ly_do_sach:
            raise ValidationError("Đánh dấu khách ưu tiên phải ghi lý do.")
        async with self._pool.acquire() as conn, conn.transaction():
            doi = await conn.fetchval(
                """
                UPDATE patient
                   SET uu_tien = $3,
                       uu_tien_ly_do = CASE WHEN $3 THEN $4 ELSE NULL END,
                       uu_tien_boi = $5::uuid, uu_tien_luc = now()
                 WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
                RETURNING clinic_patient_id::text
                """,
                identity.clinic_id,
                clinic_patient_id,
                uu_tien,
                ly_do_sach,
                identity.staff_id,
            )
            if doi is None:
                raise NotFoundError("Không tìm thấy khách hàng này.")
            # Chỉ cờ vào nhật ký; lý do nằm ở hồ sơ (có thể là chuyện riêng).
            await record_event(
                conn,
                event_type="patient.uu_tien_changed",
                aggregate_type="patient",
                aggregate_id=clinic_patient_id,
                identity=identity,
                origin="api:patient-uu-tien",
                payload={"uu_tien": uu_tien},
            )
        return {"ok": True, "uu_tien": uu_tien, "uu_tien_ly_do": ly_do_sach}
