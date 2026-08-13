"""Per-visit progress flags for the front desk (ROLE-02, ADR-0012).

WHY THIS EXISTS. /home shows a progress bar per patient: arrived → vitals taken
→ seen → paid. It built that by reading `clinical_record` and `prescription`
through the caller's own session, which meant reception — who opens /home all
day — had to be able to read the doctor's note. That single read was what kept
the role-level RLS tightening (ROLE-02) blocked: narrowing the policy while the
screen still did it would only have blanked the screen.

So the read moves here, and what goes back is the answer, not the evidence: four
booleans and the list of fees already collected. Reception learns that vitals
were taken; it does not learn the blood pressure. That is the distinction the
policy could not draw and an endpoint can.

Any signed-in staff member may call this — it is the same information the
progress bar has always shown — but the tables it reads are now closed to them
directly (migration 20260730000013).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.core.clock import CLINIC_TZ as _CLINIC_TZ

logger = structlog.get_logger()

# The clinic's day is a Vietnam-local day, not the server's.
# VÙNG IANA, KHÔNG PHẢI OFFSET CỐ ĐỊNH. Dòng này từng là
# `timezone(timedelta(hours=7))`. Với Việt Nam hai thứ cho cùng kết quả (nước
# này chưa từng dùng giờ mùa hè), nên sai lệch không bao giờ lộ — cho tới ngày
# ai đó copy nó sang một chỗ có DST.
_VN = _CLINIC_TZ

# /home asks for a week. The cap is there so a mistyped range cannot ask for a
# year of appointments in one query.
_MAX_RANGE_DAYS = 31


@dataclass(frozen=True)
class VisitProgress:
    appointment_id: str
    visit_id: str | None
    vitals_recorded: bool = False
    has_clinical_record: bool = False
    has_prescription: bool = False
    paid_kinds: list[str] = field(default_factory=list)
    # Giờ BẮT ĐẦU của từng mốc trên thanh tiến trình ở /home. Chỉ hai mốc này
    # phải hỏi tới đây; hai mốc kia (`checked_in_at`, `finalized_at`) nằm ngay
    # trên bảng `visit` mà màn hình đã đọc.
    #
    # `exam_started_at` = lúc bệnh án đầu tiên của lượt được mở, tức lúc một
    # người làm lâm sàng THẬT SỰ bắt tay vào khám.
    #
    # KHÔNG dùng `min(work_item.started_at)` — đã thử và sai. Giao dịch check-in
    # mở sẵn nhiều bước cùng lúc (đo trên prod: LUOTKHAM-01 và LUOTKHAM-03 đều
    # có `started_at` bằng ĐÚNG `checked_in_at`), nên con số ấy chỉ là giờ
    # check-in đội lốt giờ khám. Bỏ trống thì người xem biết là chưa biết; một
    # con số sai thì không.
    exam_started_at: datetime | None = None
    # Lúc thu XONG khâu cuối — không phải khâu đầu. Người xem bảng cần biết
    # "đã thu xong lúc mấy giờ", nên lấy mốc muộn nhất.
    paid_at: datetime | None = None


# One statement instead of the page's four round-trips. "Vitals recorded" means
# blood pressure, weight and height are all filled in — the rule the page used
# to apply after downloading every note, tested here where the rows already are.
_PROGRESS_SQL = """
    SELECT a.id::text                       AS appointment_id,
           v.visit_id::text                 AS visit_id,
           COALESCE(cr.vitals_recorded, FALSE) AS vitals_recorded,
           (cr.visit_id IS NOT NULL)        AS has_clinical_record,
           COALESCE(rx.has_prescription, FALSE) AS has_prescription,
           COALESCE(pay.kinds, ARRAY[]::text[]) AS paid_kinds,
           cr.exam_started_at,
           pay.paid_at
      FROM appointment a
      LEFT JOIN LATERAL (
          SELECT v2.visit_id
            FROM visit v2
           WHERE v2.appointment_id = a.id
           ORDER BY v2.created_at DESC
           LIMIT 1
      ) v ON TRUE
      LEFT JOIN LATERAL (
          SELECT r.visit_id,
                 bool_or(
                     NULLIF(TRIM(r.soap_objective #>> '{vitals,huyet_ap}'), '')
                         IS NOT NULL
                 AND NULLIF(TRIM(r.soap_objective #>> '{vitals,can_nang}'), '')
                         IS NOT NULL
                 AND NULLIF(TRIM(r.soap_objective #>> '{vitals,chieu_cao}'), '')
                         IS NOT NULL
                 ) AS vitals_recorded,
                 min(r.created_at) AS exam_started_at
            FROM clinical_record r
           WHERE r.visit_id = v.visit_id
           GROUP BY r.visit_id
      ) cr ON TRUE
      LEFT JOIN LATERAL (
          SELECT TRUE AS has_prescription
            FROM prescription p
           WHERE p.visit_id = v.visit_id
           LIMIT 1
      ) rx ON TRUE
      -- `status = 'PAID'` KHÔNG phải thừa. Không có nó thì một khoản đã HUỶ
      -- (VOIDED) vẫn tính là đã thu, và thanh tiến trình tích xanh mốc thanh
      -- toán cho một lượt chưa ai trả tiền. Trên prod hôm nay cả hai dòng
      -- payment đều đang ở trạng thái VOIDED.
      LEFT JOIN LATERAL (
          SELECT array_agg(DISTINCT pm.kind) AS kinds,
                 max(pm.paid_at)             AS paid_at
            FROM payment pm
           WHERE pm.visit_id = v.visit_id
             AND pm.status = 'PAID'
      ) pay ON TRUE
     WHERE a.clinic_id = $1::uuid
       AND a.slot_start >= $2::timestamptz
       AND a.slot_start <  $3::timestamptz
       AND a.status NOT IN ('CANCELLED', 'NO_SHOW')
"""


class VisitProgressService:
    """Read-only progress flags for a day's appointments."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def for_range(
        self, *, date_from: date, date_to: date, clinic_id: str | None
    ) -> list[VisitProgress]:
        """Flags for every live appointment from `date_from` to `date_to`.

        A range rather than a day because /home draws a week: one call for the
        board, instead of one per column. Both ends are Vietnam-local calendar
        days and both are inclusive — the clinic's day is what the board shows,
        and doing that conversion here stops each caller getting it slightly
        differently.
        """
        if date_to < date_from:
            raise ValidationError("Khoảng ngày không hợp lệ")
        if (date_to - date_from).days > _MAX_RANGE_DAYS:
            raise ValidationError(f"Khoảng ngày tối đa {_MAX_RANGE_DAYS} ngày")

        # Real datetimes, not ISO strings: asyncpg encodes the parameter on the
        # client from the inferred type, so a "::timestamptz" cast in the SQL
        # does not make a string acceptable.
        start = datetime.combine(date_from, time.min, tzinfo=_VN)
        end = datetime.combine(date_to, time.min, tzinfo=_VN) + timedelta(days=1)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_PROGRESS_SQL, clinic_id, start, end)

        return [
            VisitProgress(
                appointment_id=r["appointment_id"],
                visit_id=r["visit_id"],
                vitals_recorded=r["vitals_recorded"],
                has_clinical_record=r["has_clinical_record"],
                has_prescription=r["has_prescription"],
                paid_kinds=sorted(r["paid_kinds"] or []),
                exam_started_at=r["exam_started_at"],
                paid_at=r["paid_at"],
            )
            for r in rows
        ]
