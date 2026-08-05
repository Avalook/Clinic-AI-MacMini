"""Bộ phận Siêu âm — bốn màn: hàng chờ, điều phối phòng, soạn kết quả, đã ký.

Bản mẫu giao diện ở `src/truong-ca-prototype` dựng đủ bốn tab bằng dữ liệu giả.
File này là phần thật đứng sau, đọc từ đúng những bảng đang chạy:

    work_item (node DICHVU-SIEUAM)  → ai đang chờ siêu âm, ở phòng nào
    clinic_room (3 phòng SA)        → SA1 / SA2 / SA3
    ultrasound_record               → bản ghi kết quả, chữ ký bác sĩ siêu âm

KHÔNG BỊA MỘT TRẠNG THÁI NÀO. Bản mẫu có sáu nhãn trạng thái hàng chờ và bốn ô
"sẵn sàng"; mỗi cái ở đây phải suy ra được từ dữ liệu thật, hoặc không tồn tại.
Một ô tích màu xanh mà không có gì đứng sau còn tệ hơn không có ô đó: nó nói với
kỹ thuật viên rằng bệnh nhân đã đủ điều kiện, trong khi hệ thống chưa từng kiểm.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ

logger = structlog.get_logger()

#: Vai được mở màn siêu âm. Bác sĩ siêu âm và điều dưỡng siêu âm làm việc trực
#: tiếp ở đây; TKYK nhập hộ kết quả; Trưởng ca điều phối phòng.
ULTRASOUND_ROLES: frozenset[ClinicRole] = frozenset(
    {
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.TKYK,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)

SONO_NODE = "DICHVU-SIEUAM"


def _vn_midnight() -> datetime:
    """Nửa đêm hôm nay giờ Việt Nam, CÓ múi giờ.

    `created_at` là timestamptz; một datetime trần bị Postgres hiểu theo TimeZone
    của phiên và biên ngày lệch bảy tiếng — kỹ thuật viên sẽ thấy bệnh nhân của
    hôm qua nằm lẫn trong hàng chờ hôm nay.
    """
    return datetime.now(CLINIC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


# ── Tab 1: hàng chờ ────────────────────────────────────────────────────────
#
# BỐN Ô "SẴN SÀNG" của bản mẫu, mỗi ô một sự thật kiểm được:
#
#   đã check-in       visit.checked_in_at có giá trị
#   đủ định danh      bệnh nhân có mã VÀ có năm sinh (đủ để gọi tên và đối chiếu)
#   chỉ định còn hiệu lực   work_item chưa bị huỷ
#   được phép làm     cả ba ô trên
#
# Ô cuối KHÔNG phải một cột riêng trong database — nó là phép AND, và phải luôn
# là phép AND. Lưu nó thành cột thứ tư là mở đường cho một dòng "được phép làm"
# đúng trong khi ba ô kia sai.
_QUEUE_SQL = """
SELECT w.id                                   AS work_item_id,
       w.status,
       w.created_at,
       w.room_id,
       r.code                                 AS room_code,
       r.name                                 AS room_name,
       r.floor                                AS room_floor,
       v.visit_id,
       a.queue_number,
       v.checked_in_at,
       p.clinic_patient_id,
       p.full_name,
       p.patient_code,
       p.gender,
       coalesce(p.birth_year, date_part('year', p.date_of_birth))::int AS birth_year,
       st.name                                AS service_name,
       a.slot_start,
       d.full_name                            AS indication_doctor,
       w.payload,
       GREATEST(0, EXTRACT(EPOCH FROM (now() - w.created_at)) / 60)::int
                                              AS wait_minutes
  FROM public.work_item w
  JOIN public.visit v  ON v.visit_id = w.visit_id
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
  LEFT JOIN public.service_type st ON st.id = v.service_type_id
  LEFT JOIN public.staff d ON d.id = v.attending_doctor_id
  LEFT JOIN public.clinic_room r ON r.id = w.room_id
 WHERE w.clinic_id = $1::uuid
   AND w.node_code = $2
   AND w.status IN ('PENDING', 'IN_PROGRESS')
   AND w.created_at >= $3
 ORDER BY w.created_at
 LIMIT 300
"""

# ── Tab 2: điều phối phòng ────────────────────────────────────────────────
_ROOMS_SQL = """
SELECT r.id, r.code, r.name, r.floor, r.capacity, r.accepting, r.sort,
       (SELECT count(*) FROM public.work_item w
         WHERE w.room_id = r.id AND w.node_code = $2
           AND w.status = 'IN_PROGRESS')      AS dang_lam,
       (SELECT count(*) FROM public.work_item w
         WHERE w.room_id = r.id AND w.node_code = $2
           AND w.status = 'PENDING')          AS dang_cho
  FROM public.clinic_room r
 WHERE r.clinic_id = $1::uuid AND r.is_active
   AND EXISTS (SELECT 1 FROM public.clinic_room_node rn
                WHERE rn.room_id = r.id AND rn.node_code = $2)
   -- `coalesce` thay cho `($3 IS NULL OR col = $3)`: cùng nghĩa, nhưng không có
   -- nhánh OR nào để một bộ lọc tenant lọt qua. Bài soi phạm vi tenant chặn
   -- đúng hình dạng đó, và nó chặn đúng — một OR viết vội ở đây là mở đường
   -- đọc dữ liệu của phòng khám khác.
   AND r.location_id = coalesce($3::uuid, r.location_id)
 ORDER BY r.sort, r.code
"""

# ── Tab 3 + 4: bản ghi kết quả ────────────────────────────────────────────
#
# MỘT CÂU CHO CẢ HAI TAB, khác nhau đúng một mệnh đề `signed_at`. Viết hai câu
# gần giống nhau là hai chỗ để lệch khi thêm cột.
_RECORDS_SQL = """
SELECT u.ultrasound_id,
       u.visit_id,
       u.clinic_patient_id,
       u.ultrasound_type,
       u.findings,
       u.impression,
       u.image_refs,
       u.gestational_age_weeks,
       u.performed_at,
       u.signed_at,
       u.updated_at,
       perf.full_name                         AS performed_by_name,
       sig.full_name                          AS signed_by_name,
       p.full_name                            AS patient_name,
       p.patient_code,
       p.gender,
       coalesce(p.birth_year, date_part('year', p.date_of_birth))::int AS birth_year,
       r.name                                 AS room_name,
       r.floor                                AS room_floor
  FROM public.ultrasound_record u
  LEFT JOIN public.staff perf ON perf.id = u.performed_by
  LEFT JOIN public.staff sig  ON sig.id  = u.signed_by
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = u.clinic_patient_id AND p.clinic_id = u.clinic_id
  LEFT JOIN public.visit v ON v.visit_id = u.visit_id
  LEFT JOIN public.clinic_room r ON r.id = v.current_room_id
 WHERE u.clinic_id = $1::uuid
   AND (($2 AND u.signed_at IS NOT NULL) OR (NOT $2 AND u.signed_at IS NULL))
   AND u.performed_at >= $3
 ORDER BY u.performed_at DESC
 LIMIT 300
"""


class UltrasoundBoardService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def queue(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Ai đang chờ siêu âm hôm nay, và đã đủ điều kiện làm chưa."""
        rows = await self._pool.fetch(
            _QUEUE_SQL, identity.clinic_id, SONO_NODE, _vn_midnight()
        )
        return {"items": [_queue_row(r, i) for i, r in enumerate(rows, start=1)]}

    async def rooms(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Ba phòng siêu âm: đang làm, đang chờ, còn nhận không."""
        rows = await self._pool.fetch(
            _ROOMS_SQL, identity.clinic_id, SONO_NODE, identity.location_id
        )
        return {
            "items": [
                {
                    "id": str(r["id"]),
                    "code": r["code"],
                    "name": r["name"],
                    "floor": r["floor"],
                    "capacity": r["capacity"],
                    "accepting": r["accepting"],
                    "serving": r["dang_lam"],
                    "waiting": r["dang_cho"],
                }
                for r in rows
            ]
        }

    async def save_draft(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        ultrasound_type: str,
        findings: dict[str, Any] | None,
        impression: str | None,
        gestational_age_weeks: int | None,
    ) -> dict[str, Any]:
        """Lưu bản nháp kết quả — MỘT bản ghi cho mỗi (lượt khám, loại siêu âm).

        Một lượt khám có thể siêu âm nhiều loại (đầu dò rồi ổ bụng), nên khoá là
        cặp chứ không phải riêng lượt khám. Cùng loại thì ghi đè bản nháp; khác
        loại thì thêm bản mới.

        KHÔNG đụng bản ĐÃ KÝ. Trigger `ultrasound_signed_block_update` chặn mọi
        sửa nội dung sau chữ ký; ở đây lọc sẵn `signed_at IS NULL` để người dùng
        nhận một câu tiếng Việt thay vì một lỗi trigger.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow(
                """
                SELECT clinic_patient_id FROM public.visit
                 WHERE visit_id = $1::uuid AND clinic_id = $2::uuid
                """,
                visit_id,
                identity.clinic_id,
            )
            if row is None:
                raise ValidationError("Không tìm thấy lượt khám.")

            existing = await conn.fetchrow(
                """
                SELECT ultrasound_id, signed_at FROM public.ultrasound_record
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ultrasound_type = $3
                 ORDER BY performed_at DESC LIMIT 1
                """,
                identity.clinic_id,
                visit_id,
                ultrasound_type,
            )
            if existing and existing["signed_at"] is not None:
                raise ValidationError(
                    "Kết quả này đã ký — sửa nội dung phải qua đường đính chính."
                )

            if existing:
                uid = await conn.fetchval(
                    """
                    UPDATE public.ultrasound_record
                       SET findings = $2::jsonb, impression = $3,
                           gestational_age_weeks = $4, updated_at = now()
                     WHERE ultrasound_id = $1::uuid AND clinic_id = $5::uuid
                    RETURNING ultrasound_id
                    """,
                    existing["ultrasound_id"],
                    # `findings` là jsonb — mô tả hình ảnh có cấu trúc (từng
                    # tạng, từng số đo), không phải một đoạn văn. Gửi chuỗi trần
                    # xuống thì Postgres từ chối ngay ở ký tự tiếng Việt đầu
                    # tiên: 'invalid input syntax for type json'.
                    json.dumps(findings) if findings is not None else None,
                    impression,
                    gestational_age_weeks,
                )
            else:
                uid = await conn.fetchval(
                    """
                    INSERT INTO public.ultrasound_record
                        (clinic_id, visit_id, clinic_patient_id, performed_by,
                         ultrasound_type, findings, impression,
                         gestational_age_weeks, performed_at)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5,
                            $6::jsonb, $7, $8, now())
                    RETURNING ultrasound_id
                    """,
                    identity.clinic_id,
                    visit_id,
                    row["clinic_patient_id"],
                    identity.staff_id,
                    ultrasound_type,
                    json.dumps(findings) if findings is not None else None,
                    impression,
                    gestational_age_weeks,
                )

        logger.info(
            "ultrasound_draft_saved",
            ultrasound_id=str(uid),
            visit_id=visit_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "ultrasound_id": str(uid)}

    async def records(
        self, *, identity: StaffIdentity, signed: bool, days: int = 1
    ) -> dict[str, Any]:
        """Bản ghi siêu âm — chưa ký (tab soạn) hoặc đã ký (tab lưu trữ).

        `days` mở rộng cửa sổ cho tab đã ký: người ta tra lại kết quả của tuần
        trước, không chỉ hôm nay.
        """
        since = _vn_midnight() - timedelta(days=max(0, days - 1))
        rows = await self._pool.fetch(_RECORDS_SQL, identity.clinic_id, signed, since)
        return {"items": [_record_row(r) for r in rows]}


def _queue_row(r: asyncpg.Record, stt: int) -> dict[str, Any]:
    """Một dòng hàng chờ, kèm bốn ô sẵn sàng."""
    checked_in = r["checked_in_at"] is not None
    # Đủ định danh = gọi được tên VÀ đối chiếu được. Mã bệnh nhân một mình chưa
    # đủ: hai người trùng tên vẫn cần năm sinh để không siêu âm nhầm người.
    identified = bool(r["patient_code"]) and r["birth_year"] is not None
    # Chỉ định còn hiệu lực: work_item chưa bị huỷ. Câu SQL đã lọc PENDING/
    # IN_PROGRESS nên tới đây luôn đúng — giữ lại thành ô riêng vì kỹ thuật viên
    # đọc bốn ô, và ô nào cũng phải có nghĩa độc lập.
    indication_ok = r["status"] in ("PENDING", "IN_PROGRESS")
    return {
        "work_item_id": str(r["work_item_id"]),
        "visit_id": str(r["visit_id"]),
        "stt": stt,
        "queue_number": r["queue_number"],
        "patient_name": r["full_name"],
        "patient_code": r["patient_code"],
        "clinic_patient_id": (
            str(r["clinic_patient_id"]) if r["clinic_patient_id"] else None
        ),
        "gender": r["gender"],
        "birth_year": r["birth_year"],
        "service_name": r["service_name"],
        "appointment_at": r["slot_start"].isoformat() if r["slot_start"] else None,
        "indication_doctor": r["indication_doctor"],
        "room_code": r["room_code"],
        "room_name": r["room_name"],
        "room_floor": r["room_floor"],
        "status": r["status"],
        "wait_minutes": r["wait_minutes"],
        "readiness": {
            "checked_in": checked_in,
            "identified": identified,
            "indication_valid": indication_ok,
            # Phép AND, luôn luôn. Không bao giờ là một cột lưu sẵn.
            "may_perform": checked_in and identified and indication_ok,
        },
    }


def _record_row(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "ultrasound_id": str(r["ultrasound_id"]),
        "visit_id": str(r["visit_id"]) if r["visit_id"] else None,
        "clinic_patient_id": (
            str(r["clinic_patient_id"]) if r["clinic_patient_id"] else None
        ),
        "patient_name": r["patient_name"],
        "patient_code": r["patient_code"],
        "gender": r["gender"],
        "birth_year": r["birth_year"],
        "ultrasound_type": r["ultrasound_type"],
        "findings": r["findings"],
        "impression": r["impression"],
        # Khoá tệp trên đĩa Mac, do `media_service.safe_path()` sinh — dạng
        # `<clinic_id>/ultrasound/<ultrasound_id>/<uuid>.<đuôi>`. KHÔNG phải
        # đường dẫn công khai: màn hình đọc qua `/api/ultrasound/image?key=…`,
        # và service kiểm hai lần trước khi trả byte nào — khoá phải bắt đầu
        # bằng đúng clinic_id của người hỏi, VÀ phải thuộc một bản ghi có thật.
        # Thiếu phép kiểm thứ hai thì đoán được một UUID là đọc được ảnh của
        # bệnh nhân bất kỳ.
        "image_refs": list(r["image_refs"] or []),
        "gestational_age_weeks": r["gestational_age_weeks"],
        "performed_at": (r["performed_at"].isoformat() if r["performed_at"] else None),
        "performed_by_name": r["performed_by_name"],
        "signed_at": r["signed_at"].isoformat() if r["signed_at"] else None,
        "signed_by_name": r["signed_by_name"],
        "room_name": r["room_name"],
        "room_floor": r["room_floor"],
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
    }


def group_by_patient(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tab "đã ký" gom theo BỆNH NHÂN, không theo bản ghi.

    Một người có thể siêu âm nhiều lần trong một đợt (đầu dò rồi ổ bụng), và
    người tra cứu nghĩ theo "chị A có những phiếu nào", không theo "phiếu số
    mấy". Gom ở backend để hai màn hình không tự gom mỗi nơi một kiểu.
    """
    order: list[str] = []
    groups: dict[str, dict[str, Any]] = {}
    for rec in records:
        key = rec["clinic_patient_id"] or f"__{rec['ultrasound_id']}"
        if key not in groups:
            order.append(key)
            groups[key] = {
                "clinic_patient_id": rec["clinic_patient_id"],
                "patient_name": rec["patient_name"],
                "patient_code": rec["patient_code"],
                "gender": rec["gender"],
                "birth_year": rec["birth_year"],
                "reports": [],
            }
        groups[key]["reports"].append(rec)
    for key in order:
        groups[key]["report_count"] = len(groups[key]["reports"])
    return [groups[k] for k in order]
