"""Bảng điều phối của Trưởng ca — đọc vị trí, và di chuyển bệnh nhân.

NGUỒN DỮ LIỆU LÀ MỘT. Bảng toàn cảnh, hàng đợi từng phòng, TV phòng chờ và cảnh
báo đều đọc từ `visit.current_node_code/current_room_id` — con trỏ mà
``move_visit_to_station()`` ghi. Yêu cầu khách hàng nói thẳng: *"Màn hình phải
lấy dữ liệu từ cùng nguồn với hàng đợi thực tế để vị trí bệnh nhân và bước tiếp
theo không bị lệch giữa các bộ phận."* Bốn màn hình đọc bốn nơi là cách chắc
chắn nhất để chúng nói bốn điều khác nhau.

MỌI ĐƯỜNG GHI ĐI QUA ĐÚNG MỘT HÀM SQL. Đóng bước cũ, mở bước mới, cập nhật con
trỏ, ghi nhật ký — bốn việc trong một giao dịch, có khoá dòng. Làm bốn việc đó ở
Python thì một lần mất kết nối giữa chừng để lại bệnh nhân ở hai hàng đợi, đúng
cái mà chính danh sách cảnh báo của khách hàng liệt kê là bất thường.
"""

from __future__ import annotations

from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Lượt khám còn "trong phòng khám". Đóng lượt rồi thì không còn là việc của
# Trưởng ca nữa.
LIVE_VISIT_STATUSES = ("OPEN", "IN_PROGRESS")

# ── Bảng toàn cảnh ─────────────────────────────────────────────────────────

_OVERVIEW_SQL = """
WITH nguong AS (
    SELECT r.id AS room_id,
           coalesce(t.wait_minutes, d.wait_minutes, 20) AS wait_minutes
      FROM public.clinic_room r
      LEFT JOIN public.dispatch_threshold t
             ON t.room_id = r.id AND t.clinic_id = r.clinic_id
      LEFT JOIN public.dispatch_threshold d
             ON d.room_id IS NULL AND d.clinic_id = r.clinic_id
     WHERE r.clinic_id = $1::uuid
)
SELECT v.visit_id,
       v.status                                   AS visit_status,
       v.checked_in_at,
       v.current_node_code,
       v.current_node_since,
       n.name                                     AS current_node_name,
       r.id                                       AS room_id,
       r.code                                     AS room_code,
       r.name                                     AS room_name,
       p.clinic_patient_id,
       p.full_name                                AS patient_name,
       p.patient_code,
       a.queue_number,
       a.status                                   AS appointment_status,
       st.name                                    AS specialty,
       d.full_name                                AS doctor_name,
       -- Thời gian ĐỢI Ở BƯỚC HIỆN TẠI và TỔNG thời gian trong phòng khám là
       -- hai con số khác nhau, và yêu cầu khách hàng đòi cả hai. Trộn chúng làm
       -- một sẽ khiến người vừa được chuyển phòng trông như vừa mới đến.
       GREATEST(0, EXTRACT(EPOCH FROM (now() - v.current_node_since)) / 60)::int
                                                  AS wait_minutes,
       GREATEST(0, EXTRACT(EPOCH FROM (
           now() - coalesce(v.checked_in_at, v.created_at))) / 60)::int
                                                  AS total_minutes,
       ng.wait_minutes                            AS threshold_minutes,
       -- Bước đã xong: đọc từ timeline, theo đúng thứ tự đã đi.
       (SELECT array_agg(w2.node_code ORDER BY w2.finished_at)
          FROM public.work_item w2
         WHERE w2.visit_id = v.visit_id AND w2.status = 'COMPLETED')
                                                  AS done_steps,
       vr.steps                                   AS route_steps,
       vr.id                                      AS route_id
  FROM public.visit v
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN public.appointment a ON a.id = v.appointment_id
  LEFT JOIN public.service_type st ON st.id = v.service_type_id
  LEFT JOIN public.staff d ON d.id = v.attending_doctor_id
  LEFT JOIN public.clinic_room r ON r.id = v.current_room_id
  LEFT JOIN public.node_definition n
         ON n.code = v.current_node_code AND n.clinic_id = v.clinic_id
  LEFT JOIN public.visit_route vr
         ON vr.visit_id = v.visit_id AND vr.superseded_at IS NULL
  LEFT JOIN nguong ng ON ng.room_id = r.id
 WHERE v.clinic_id = $1::uuid
   AND v.status = ANY($2::text[])
 ORDER BY v.current_node_since NULLS LAST, v.checked_in_at
 LIMIT 400
"""

_STATIONS_SQL = """
SELECT r.id, r.code, r.name, r.node_code, r.capacity, r.accepting, r.sort,
       r.show_on_tv,
       n.name AS node_name,
       coalesce(t.wait_minutes, d.wait_minutes, 20) AS threshold_minutes,
       coalesce(t.max_waiting,  d.max_waiting,  8)  AS threshold_waiting,
       -- ĐANG PHỤC VỤ vs ĐANG CHỜ. Bước đã bắt đầu (IN_PROGRESS) là đang phục
       -- vụ; PENDING là đang chờ tới lượt. Gộp hai số này lại thì Trưởng ca
       -- không biết phòng đang kẹt hay đang rảnh.
       count(v.visit_id) FILTER (WHERE v.status = 'IN_PROGRESS'
                                   AND w.status = 'IN_PROGRESS') AS serving,
       count(v.visit_id) FILTER (WHERE w.status = 'PENDING')      AS waiting,
       coalesce(max(EXTRACT(EPOCH FROM (now() - v.current_node_since)) / 60)
                FILTER (WHERE w.status = 'PENDING'), 0)::int      AS max_wait,
       coalesce(avg(EXTRACT(EPOCH FROM (now() - v.current_node_since)) / 60)
                FILTER (WHERE w.status = 'PENDING'), 0)::int      AS avg_wait
  FROM public.clinic_room r
  LEFT JOIN public.node_definition n
         ON n.code = r.node_code AND n.clinic_id = r.clinic_id
  LEFT JOIN public.dispatch_threshold t
         ON t.room_id = r.id AND t.clinic_id = r.clinic_id
  LEFT JOIN public.dispatch_threshold d
         ON d.room_id IS NULL AND d.clinic_id = r.clinic_id
  LEFT JOIN public.visit v
         ON v.current_room_id = r.id AND v.status = ANY($2::text[])
  LEFT JOIN public.work_item w
         ON w.visit_id = v.visit_id AND w.node_code = r.node_code
        AND w.status IN ('PENDING', 'IN_PROGRESS')
 WHERE r.clinic_id = $1::uuid AND r.is_active
 GROUP BY r.id, r.code, r.name, r.node_code, r.capacity, r.accepting, r.sort,
          r.show_on_tv, n.name, t.wait_minutes, d.wait_minutes,
          t.max_waiting, d.max_waiting
 ORDER BY r.sort, r.code
"""


class DispatchService:
    """Đọc và ghi vị trí bệnh nhân cho bảng điều phối."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────

    async def overview(self, *, clinic_id: str) -> list[dict[str, Any]]:
        """Mỗi bệnh nhân đang trong phòng khám là một dòng."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _OVERVIEW_SQL, clinic_id, list(LIVE_VISIT_STATUSES)
            )
        return [_overview_row(r) for r in rows]

    async def stations(self, *, clinic_id: str) -> list[dict[str, Any]]:
        """Tải của từng phòng: đang phục vụ, đang chờ, chờ lâu nhất."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _STATIONS_SQL, clinic_id, list(LIVE_VISIT_STATUSES)
            )
        return [
            {
                "id": str(r["id"]),
                "code": r["code"],
                "name": r["name"],
                "node_code": r["node_code"],
                "node_name": r["node_name"],
                "capacity": r["capacity"],
                "accepting": r["accepting"],
                "show_on_tv": r["show_on_tv"],
                "serving": r["serving"],
                "waiting": r["waiting"],
                "max_wait": r["max_wait"],
                "avg_wait": r["avg_wait"],
                "threshold_minutes": r["threshold_minutes"],
                "threshold_waiting": r["threshold_waiting"],
                "state": _station_state(
                    r["waiting"],
                    r["max_wait"],
                    r["threshold_waiting"],
                    r["threshold_minutes"],
                ),
            }
            for r in rows
        ]

    async def alerts(self, *, clinic_id: str) -> list[dict[str, Any]]:
        """Cảnh báo vận hành, xếp theo mức độ.

        Tính từ chính hai truy vấn trên chứ không từ một bảng cảnh báo riêng:
        một bảng cảnh báo là một bản sao của sự thật, và nó sẽ cũ đúng vào lúc
        Trưởng ca cần tin nó nhất.
        """
        patients = await self.overview(clinic_id=clinic_id)
        rooms = await self.stations(clinic_id=clinic_id)
        return build_alerts(patients, rooms)

    # ── Ghi ────────────────────────────────────────────────────────────

    async def move(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        node_code: str,
        room_id: str | None,
        reason: str | None,
        event_type: str = "dispatch.moved",
    ) -> dict[str, Any]:
        """Chuyển bệnh nhân sang bước/phòng khác. Một lời gọi, một giao dịch."""
        async with self._pool.acquire() as conn:
            try:
                item_id = await conn.fetchval(
                    "SELECT public.move_visit_to_station("
                    "$1::uuid, $2::uuid, $3, $4::uuid, $5::uuid, $6, $7)",
                    identity.clinic_id,
                    visit_id,
                    node_code,
                    room_id,
                    identity.auth_user_id,
                    reason,
                    event_type,
                )
            except asyncpg.RaiseError as exc:
                # Hàm SQL ném câu tiếng Việt sẵn ("Phòng đã chọn không phục vụ
                # bước …"). Đưa thẳng lên người dùng thay vì gói lại thành một
                # câu chung chung — nó đã nói đúng vấn đề rồi.
                raise ValidationError(str(exc).split("\n")[0]) from exc

        logger.info(
            "dispatch_move",
            clinic_id=identity.clinic_id,
            visit_id=visit_id,
            node_code=node_code,
            room_id=room_id,
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "work_item_id": str(item_id)}

    async def apply_route(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        template_code: str,
        is_exception: bool,
        reason: str | None,
    ) -> dict[str, Any]:
        """Chọn tuyến điều phối cho một lượt khám.

        Bước ĐÃ HOÀN TẤT không bị đụng tới — yêu cầu khách hàng nói rõ *"chỉ
        thay đổi các bước chưa làm"*. Chúng được chụp vào ``kept_steps`` để về
        sau đọc lại được tuyến này đã bỏ qua những gì.
        """
        if is_exception and not (reason or "").strip():
            raise ValidationError(
                "Đổi tuyến giữa chừng bắt buộc phải ghi lý do."
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                tpl = await conn.fetchrow(
                    "SELECT id, steps FROM public.route_template"
                    " WHERE clinic_id = $1::uuid AND code = $2 AND is_active",
                    identity.clinic_id,
                    template_code,
                )
                if tpl is None:
                    raise ValidationError(f"Không có tuyến {template_code}.")

                done = await conn.fetchval(
                    "SELECT coalesce(array_agg(node_code), '{}')"
                    "  FROM public.work_item"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    "   AND status = 'COMPLETED'",
                    identity.clinic_id,
                    visit_id,
                )

                # Đóng tuyến đang chạy. Chỉ mục uq_visit_route_one_active bảo
                # đảm không bao giờ có hai tuyến cùng hiệu lực; đóng trước khi
                # mở là cách duy nhất chèn được dòng mới.
                await conn.execute(
                    "UPDATE public.visit_route SET superseded_at = now()"
                    " WHERE visit_id = $1::uuid AND superseded_at IS NULL",
                    visit_id,
                )
                route_id = await conn.fetchval(
                    """
                    INSERT INTO public.visit_route
                        (clinic_id, visit_id, template_id, steps, kept_steps,
                         is_exception, reason, applied_by)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7, $8::uuid)
                    RETURNING id
                    """,
                    identity.clinic_id,
                    visit_id,
                    tpl["id"],
                    list(tpl["steps"]),
                    list(done or []),
                    is_exception,
                    reason,
                    identity.auth_user_id,
                )

                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, 'dispatch.route_applied', 'visit',
                            $2::uuid, $3::jsonb, $4::jsonb, 'api:dispatch', FALSE)
                    """,
                    identity.clinic_id,
                    visit_id,
                    _json(
                        {
                            "to_node": None,
                            "template": template_code,
                            "steps": list(tpl["steps"]),
                            "kept_steps": list(done or []),
                            "is_exception": is_exception,
                            "reason": reason,
                        }
                    ),
                    _json({"actor_auth_user_id": identity.auth_user_id}),
                )

        logger.info(
            "dispatch_route_applied",
            clinic_id=identity.clinic_id,
            visit_id=visit_id,
            template=template_code,
            is_exception=is_exception,
        )
        return {"ok": True, "route_id": str(route_id)}

    # ── Cấu hình ───────────────────────────────────────────────────────

    async def routes(self, *, clinic_id: str) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT code, name, steps FROM public.route_template"
                " WHERE clinic_id = $1::uuid AND is_active ORDER BY sort, code",
                clinic_id,
            )
        return [
            {"code": r["code"], "name": r["name"], "steps": list(r["steps"])}
            for r in rows
        ]

    async def history(
        self, *, clinic_id: str, limit: int = 200
    ) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT created_at, event_type, visit_id, from_node, to_node,"
                "       from_room, to_room, reason, actor_name, patient_name,"
                "       patient_code"
                "  FROM public.v_dispatch_history"
                " WHERE clinic_id = $1::uuid"
                " ORDER BY created_at DESC LIMIT $2",
                clinic_id,
                limit,
            )
        return [
            {
                "at": r["created_at"].isoformat(),
                "event_type": r["event_type"],
                "visit_id": str(r["visit_id"]) if r["visit_id"] else None,
                "from_node": r["from_node"],
                "to_node": r["to_node"],
                "from_room": r["from_room"],
                "to_room": r["to_room"],
                "reason": r["reason"],
                "actor_name": r["actor_name"],
                "patient_name": r["patient_name"],
                "patient_code": r["patient_code"],
            }
            for r in rows
        ]

    async def set_threshold(
        self,
        *,
        identity: StaffIdentity,
        room_id: str | None,
        wait_minutes: int,
        max_waiting: int,
    ) -> dict[str, Any]:
        if not 1 <= wait_minutes <= 480:
            raise ValidationError("Ngưỡng chờ phải từ 1 đến 480 phút.")
        if not 1 <= max_waiting <= 200:
            raise ValidationError("Số người chờ tối đa phải từ 1 đến 200.")

        async with self._pool.acquire() as conn:
            # Hai chỉ mục duy nhất (một cho phòng, một cho mặc định) nên phải
            # nói rõ đang đụng chỉ mục nào.
            if room_id:
                await conn.execute(
                    "INSERT INTO public.dispatch_threshold"
                    " (clinic_id, room_id, wait_minutes, max_waiting, updated_by)"
                    " VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid)"
                    " ON CONFLICT (clinic_id, room_id) WHERE room_id IS NOT NULL"
                    " DO UPDATE SET wait_minutes = EXCLUDED.wait_minutes,"
                    "   max_waiting = EXCLUDED.max_waiting,"
                    "   updated_by = EXCLUDED.updated_by, updated_at = now()",
                    identity.clinic_id,
                    room_id,
                    wait_minutes,
                    max_waiting,
                    identity.auth_user_id,
                )
            else:
                await conn.execute(
                    "INSERT INTO public.dispatch_threshold"
                    " (clinic_id, room_id, wait_minutes, max_waiting, updated_by)"
                    " VALUES ($1::uuid, NULL, $2, $3, $4::uuid)"
                    " ON CONFLICT (clinic_id) WHERE room_id IS NULL"
                    " DO UPDATE SET wait_minutes = EXCLUDED.wait_minutes,"
                    "   max_waiting = EXCLUDED.max_waiting,"
                    "   updated_by = EXCLUDED.updated_by, updated_at = now()",
                    identity.clinic_id,
                    wait_minutes,
                    max_waiting,
                    identity.auth_user_id,
                )
        return {"ok": True}


# ── Luật thuần, kiểm được không cần database ───────────────────────────────


def _station_state(
    waiting: int, max_wait: int, cap_waiting: int, cap_minutes: int
) -> str:
    """Màu của một phòng: ok / warning / critical.

    Vượt CẢ HAI ngưỡng mới là critical. Vượt một là warning. Coi mọi lần vượt là
    critical sẽ làm cả màn hình đỏ vào giờ cao điểm, và một màn hình đỏ toàn bộ
    không nói cho Trưởng ca biết nên xử lý phòng nào trước.
    """
    over_count = waiting > cap_waiting
    over_time = max_wait > cap_minutes
    if over_count and over_time:
        return "critical"
    if over_count or over_time:
        return "warning"
    return "ok"


def build_alerts(
    patients: list[dict[str, Any]], rooms: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Bốn loại cảnh báo mà yêu cầu khách hàng liệt kê, xếp theo mức độ.

    Tách thành hàm thuần để thử được mọi tình huống mà không cần một phòng khám
    đang chạy — và vì đây là chỗ quyết định Trưởng ca nhìn vào việc gì trước.
    """
    out: list[dict[str, Any]] = []

    for r in rooms:
        if r["state"] != "ok":
            affected = [
                {"name": p["patient_name"], "code": p["patient_code"]}
                for p in patients
                if p["room_code"] == r["code"]
            ]
            out.append(
                {
                    "type": "room_overloaded",
                    "severity": "critical" if r["state"] == "critical" else "warning",
                    # Câu dễ hiểu, không phải mã kỹ thuật — yêu cầu khách hàng
                    # nói rõ điều này.
                    "message": (
                        f"{r['name']}: {r['waiting']} người chờ, "
                        f"lâu nhất {r['max_wait']} phút"
                    ),
                    "room_code": r["code"],
                    # "chỉ rõ phòng VÀ danh sách bệnh nhân bị ảnh hưởng"
                    "patients": affected,
                }
            )

    for p in patients:
        if p["wait_minutes"] > p["threshold_minutes"]:
            out.append(
                {
                    "type": "wait_too_long",
                    "severity": "critical"
                    if p["wait_minutes"] > p["threshold_minutes"] * 2
                    else "warning",
                    "message": (
                        f"{p['patient_name']} chờ {p['wait_minutes']} phút tại "
                        f"{p['current_node_name'] or 'chưa xếp trạm'}"
                    ),
                    "room_code": p["room_code"],
                    "patients": [
                        {"name": p["patient_name"], "code": p["patient_code"]}
                    ],
                }
            )
        if not p["current_node_code"]:
            out.append(
                {
                    "type": "missing_next_step",
                    "severity": "warning",
                    "message": (
                        f"{p['patient_name']} đã check-in nhưng chưa được xếp "
                        "trạm nào"
                    ),
                    "room_code": None,
                    "patients": [
                        {"name": p["patient_name"], "code": p["patient_code"]}
                    ],
                }
            )
        elif not p["next_step"] and not p["route_steps"]:
            out.append(
                {
                    "type": "no_route",
                    "severity": "warning",
                    "message": (
                        f"{p['patient_name']} chưa được chọn tuyến điều phối"
                    ),
                    "room_code": p["room_code"],
                    "patients": [
                        {"name": p["patient_name"], "code": p["patient_code"]}
                    ],
                }
            )

    rank = {"critical": 0, "warning": 1}
    out.sort(key=lambda a: (rank.get(a["severity"], 9), a["message"]))
    return out


def next_step_of(
    route_steps: list[str] | None, done_steps: list[str] | None, current: str | None
) -> str | None:
    """Bước kế tiếp = bước đầu tiên trong tuyến chưa xong và không phải bước hiện tại.

    Trả ``None`` khi chưa có tuyến hoặc đã đi hết — hai trường hợp khác nhau, và
    người gọi phân biệt bằng việc có ``route_steps`` hay không.
    """
    if not route_steps:
        return None
    done = set(done_steps or [])
    for s in route_steps:
        if s not in done and s != current:
            return s
    return None


def _overview_row(r: asyncpg.Record) -> dict[str, Any]:
    route = list(r["route_steps"]) if r["route_steps"] else None
    done = list(r["done_steps"]) if r["done_steps"] else []
    return {
        "visit_id": str(r["visit_id"]),
        "patient_name": r["patient_name"],
        "patient_code": r["patient_code"],
        "clinic_patient_id": (
            str(r["clinic_patient_id"]) if r["clinic_patient_id"] else None
        ),
        "queue_number": r["queue_number"],
        "specialty": r["specialty"],
        "doctor_name": r["doctor_name"],
        "current_node_code": r["current_node_code"],
        "current_node_name": r["current_node_name"],
        "room_id": str(r["room_id"]) if r["room_id"] else None,
        "room_code": r["room_code"],
        "room_name": r["room_name"],
        "wait_minutes": r["wait_minutes"],
        "total_minutes": r["total_minutes"],
        "threshold_minutes": r["threshold_minutes"] or 20,
        "done_steps": done,
        "route_steps": route,
        "next_step": next_step_of(route, done, r["current_node_code"]),
        "checked_in_at": (
            r["checked_in_at"].isoformat() if r["checked_in_at"] else None
        ),
    }


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
