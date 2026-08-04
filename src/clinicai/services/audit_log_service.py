"""Nhật ký thao tác — một truy vấn, và tên người thay cho tên đường ghi.

Màn ``/audit-log`` trước đây KHÔNG đi qua FastAPI: Server Component gọi thẳng
Supabase PostgREST bằng anon key, chạy hai truy vấn phẳng rồi trộn kết quả bằng
JavaScript. Ba hệ quả, và cái thứ ba là thứ người dùng nhìn thấy:

  1. Không JOIN được sang ``staff``/``patient`` — PostgREST không nối được qua
     một khoá nằm trong ``jsonb``. Nên màn hình không có cách nào biết tên.
  2. TRỘN RỒI CẮT LÀM MẤT DÒNG. Mỗi nguồn lấy 200 dòng mới nhất, trộn lại rồi
     cắt còn 200 — nên mốc thời gian cũ nhất là min của hai nguồn, và những
     dòng nằm giữa hai mốc ấy biến mất khỏi màn hình mà không ai biết.
  3. Bảng nhãn và cách dựng nhãn đối tượng nằm trong TSX — trái nguyên tắc dự
     án, và là lý do có hai bảng nhãn lệch nhau.

Ở đây là một câu SQL: ``UNION ALL`` gộp hai nguồn TRƯỚC khi sắp xếp và cắt, nên
ranh giới thời gian đúng.

MỘT ĐIỀU PHẢI NHỚ KHI ĐỌC FILE NÀY. Backend chạy bằng service role và BỎ QUA
RLS. Hôm nay chính RLS (policy ``event_log_select_ops``) mới là thứ giới hạn
phạm vi đọc theo phòng khám. Chuyển sang FastAPI mà quên ``WHERE clinic_id`` là
rò dữ liệu chéo phòng khám — nên ``clinic_id`` lấy từ ``identity``, KHÔNG bao
giờ từ tham số của người gọi.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.audit_labels import action_label

logger = structlog.get_logger()

#: Ba vai được đọc nhật ký — đúng bằng policy `event_log_select_ops` đang cho
#: phép. Backend bỏ qua RLS nên danh sách này phải tự khớp; lệch một vai là mở
#: rộng quyền đọc mà không ai thấy.
AUDIT_ROLES: frozenset[ClinicRole] = frozenset(
    {ClinicRole.MANAGEMENT, ClinicRole.TRUONG_CA, ClinicRole.CSKH}
)

MAX_ROWS = 200

_SQL = """
WITH nhat_ky AS (
    SELECT a.event_id::text          AS id,
           a.occurred_at,
           a.event_type,
           a.aggregate_type,
           a.aggregate_id::text      AS aggregate_id,
           a.payload,
           a.actor_name,
           a.actor_role,
           a.actor_staff_id::text    AS actor_staff_id,
           a.nguon_thao_tac,
           a.subject_name,
           a.subject_code,
           a.subject_kind,
           a.subject_ref_name
      FROM public.v_audit_log a
     WHERE a.clinic_id = $1::uuid
     ORDER BY a.occurred_at DESC
     LIMIT $2
),
-- Workflow kernel ghi vào bảng riêng. Gộp TRƯỚC khi sắp xếp, không phải sau —
-- xem ghi chú đầu file về chuyện trộn-rồi-cắt làm mất dòng.
quy_trinh AS (
    SELECT 'wie:' || w.id::text     AS id,
           w.occurred_at,
           'work_item.' || w.command AS event_type,
           'work_item'              AS aggregate_type,
           w.work_item_id::text     AS aggregate_id,
           jsonb_build_object('command', w.command,
                              'from_status', w.from_status,
                              'to_status', w.to_status,
                              'reason', w.reason) AS payload,
           s.full_name              AS actor_name,
           w.actor_role,
           w.actor_staff_id::text   AS actor_staff_id,
           'workflow-kernel'        AS nguon_thao_tac,
           p.full_name              AS subject_name,
           p.patient_code           AS subject_code,
           NULL                     AS subject_kind,
           NULL                     AS subject_ref_name
      FROM public.work_item_event w
      JOIN public.work_item wi
        ON wi.id = w.work_item_id AND wi.clinic_id = $1::uuid
      LEFT JOIN public.staff s
             ON s.id = w.actor_staff_id
      LEFT JOIN public.patient p
             ON p.clinic_patient_id = wi.clinic_patient_id
            AND p.clinic_id = $1::uuid
     WHERE w.clinic_id = $1::uuid
     ORDER BY w.occurred_at DESC
     LIMIT $2
)
SELECT * FROM (
    SELECT * FROM nhat_ky
    UNION ALL
    SELECT * FROM quy_trinh
) gop
ORDER BY occurred_at DESC
LIMIT $2
"""


def subject_label(row: dict[str, Any] | asyncpg.Record) -> str:
    """Việc này về ai — một chuỗi màn hình hiện thẳng.

    Dựng ở backend chứ không ở TSX, vì nó là luật nghiệp vụ: thứ tự ưu tiên
    giữa "tên bệnh nhân", "luật của bác sĩ nào" và "cấu hình phòng khám" là
    quyết định về nghĩa, không phải về trình bày.

    Khi không tra được thì giữ ``<loại> · <8 ký tự đầu>`` như cũ — nó xấu nhưng
    tra cứu được, và một ô trống sẽ đọc thành "mất dữ liệu".
    """
    if row["subject_name"]:
        ma = f" ({row['subject_code']})" if row["subject_code"] else ""
        return f"{row['subject_name']}{ma}"

    kind = row["subject_kind"]
    if kind == "luat_dat_lich":
        return (
            f"Luật của {row['subject_ref_name']}"
            if row["subject_ref_name"]
            else "Luật đặt lịch"
        )
    if kind == "cau_hinh_phong_kham":
        return "Cấu hình phòng khám"
    if kind == "nhan_su":
        return row["subject_ref_name"] or "Nhân sự"

    return f"{row['aggregate_type']} · {(row['aggregate_id'] or '')[:8]}"


class AuditLogService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def events(
        self, *, identity: StaffIdentity, limit: int = MAX_ROWS
    ) -> dict[str, Any]:
        n = max(1, min(limit, MAX_ROWS))
        rows = await self._pool.fetch(_SQL, identity.clinic_id, n)

        items = [
            {
                "id": r["id"],
                "occurred_at": r["occurred_at"].isoformat(),
                "event_type": r["event_type"],
                # Ba trường màn hình hiện thẳng, đã giải nghĩa xong ở đây.
                "actor_name": r["actor_name"],
                "actor_role": r["actor_role"],
                "actor_staff_id": r["actor_staff_id"],
                "subject_label": subject_label(r),
                "action_label": action_label(r["event_type"]),
                # `source` là thông tin có ích — nó chỉ không được đứng THAY
                # tên người, nên trả về dưới nhãn riêng.
                "nguon_thao_tac": r["nguon_thao_tac"],
                "aggregate_type": r["aggregate_type"],
                "aggregate_id": r["aggregate_id"],
                "payload": r["payload"],
            }
            for r in rows
        ]

        logger.info(
            "audit_log_read",
            clinic_id=identity.clinic_id,
            rows=len(items),
            co_ten=sum(1 for i in items if i["actor_name"]),
        )
        return {
            "items": items,
            # Số NGƯỜI, không phải số nguồn máy. Màn hình trước đếm
            # `new Set(source)` nên ra 14 — đó là 14 chuỗi tên đường ghi, không
            # phải 14 nhân viên.
            "so_nguoi": len(
                {i["actor_staff_id"] for i in items if i["actor_staff_id"]}
            ),
        }
