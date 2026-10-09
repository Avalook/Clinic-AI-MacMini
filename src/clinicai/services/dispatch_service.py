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

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services import finance_gate
from clinicai.services.audit_labels import action_label_theo_nguon
from clinicai.services.gate_rule_service import enforce as gate_enforce
from clinicai.services.luot_kham_rules import doi_phong_duoc
from clinicai.services.nhan_trang_thai_dieu_phoi import (
    trang_thai_dich_vu,
    trang_thai_khach,
)

logger = structlog.get_logger()


#: Lý do xếp phòng của luồng mới, đọc được (`service.routed.reason_code`).
_LY_DO_XEP = {
    "INITIAL_ASSIGNMENT": "xếp phòng",
    "LOAD_BALANCE": "cân tải",
}
#: Màn gây ra lần xếp (`nguon`).
_NGUON_XEP = {"truong_ca": "trưởng ca", "quay_thu": "quầy thu", "tu_dong": "tự động"}


def _ly_do_xep_phong(r: Any) -> str | None:
    """ "Siêu âm 2D · cân tải · trưởng ca" — dòng `service.routed`; dòng
    `service.room_transferred` (29/09/2026) thêm lý do chữ của trưởng ca."""
    if r["event_type"] == "service.room_transferred":
        phan = [r["dich_vu"], "đang làm", r["ly_do_chu"], "trưởng ca"]
        return " · ".join(x for x in phan if x) or None
    if r["event_type"] != "service.routed":
        return None
    phan = [
        r["dich_vu"],
        _LY_DO_XEP.get(r["ly_do_ma"] or "", r["ly_do_ma"]),
        _NGUON_XEP.get(r["nguon"] or ""),
    ]
    return " · ".join(x for x in phan if x) or None


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
       r.floor                                    AS room_floor,
       p.clinic_patient_id,
       p.full_name                                AS patient_name,
       p.patient_code,
       a.queue_number,
       a.so_tiep_don,
       a.so_booking,
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
       -- Luồng mới: bước đã xong = chỉ định đã làm; luồng cũ: work_item.
       coalesce(
           (SELECT array_agg(o2.node_code ORDER BY o2.finished_at)
              FROM public.service_order o2
             WHERE o2.visit_id = v.visit_id AND o2.clinic_id = v.clinic_id
               AND o2.exec_status = 'performed'),
           (SELECT array_agg(w2.node_code ORDER BY w2.finished_at)
              FROM public.work_item w2
             WHERE w2.visit_id = v.visit_id AND w2.status = 'COMPLETED'))
                                                  AS done_steps,
       -- BƯỚC KẾ TIẾP theo chỉ định còn mở (tuyến điều phối đã bỏ 16/09).
       (SELECT o3.node_code
          FROM public.service_order o3
         WHERE o3.visit_id = v.visit_id AND o3.clinic_id = v.clinic_id
           AND o3.exec_status IN ('authorized', 'assigned')
           AND o3.node_code IS DISTINCT FROM v.current_node_code
         ORDER BY o3.created_at
         LIMIT 1)                                 AS buoc_chi_dinh_ke,
       -- Luồng mới (Slice 1): trưởng ca chuyển phòng TỪNG CHỈ ĐỊNH, không
       -- chuyển cả lượt bằng move_visit_to_station.
       (EXISTS (SELECT 1 FROM public.encounter_flow f
                 WHERE f.visit_id = v.visit_id AND f.clinic_id = v.clinic_id)
        OR EXISTS (SELECT 1 FROM public.consultation c
                    WHERE c.visit_id = v.visit_id AND c.clinic_id = v.clinic_id))
                                                  AS luong_moi,
       vr.steps                                   AS route_steps,
       vr.id                                      AS route_id,
       -- NHÃN TRẠNG THÁI KHÁCH (Tuyền 29/09/2026): chỗ chờ sống quan trọng
       -- nhất của lượt + mốc giờ; máy chủ quyết nhãn, màn tính phút.
       v.closed_at                                AS khach_ve_luc,
       hq.lane AS hang_lane, hq.status AS hang_status,
       hq.eligible_at AS hang_vao, hq.called_at AS hang_goi,
       hq.serving_at AS hang_lam, hq.so_truoc AS hang_so_truoc,
       EXISTS (SELECT 1 FROM public.service_order od
                 JOIN public.node_definition nd
                   ON nd.clinic_id = od.clinic_id AND nd.code = od.node_code
                  AND nd.lam_ben_ngoai
                WHERE od.clinic_id = v.clinic_id AND od.visit_id = v.visit_id
                  AND od.execution_status = 'COMPLETED'
                  AND od.ket_qua_luc IS NULL)     AS cho_kq_doi_tac
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
  LEFT JOIN LATERAL (
      SELECT q.lane, q.status, q.eligible_at, q.called_at, q.serving_at,
             CASE WHEN q.status = 'waiting' THEN (
                 SELECT count(*)::int FROM public.queue_entry o
                  WHERE o.clinic_id = q.clinic_id AND o.lane = q.lane
                    AND o.id <> q.id AND o.status IN ('waiting', 'called')
                    AND (q.lane = 'TU_VAN'
                         OR (q.lane = 'ROOM' AND o.room_id = q.room_id)
                         OR (q.lane = 'DOCTOR'
                             AND o.doctor_staff_id
                                 IS NOT DISTINCT FROM q.doctor_staff_id))
                    AND (coalesce(o.eligible_at, o.created_at), o.id)
                        < (coalesce(q.eligible_at, q.created_at), q.id))
             END AS so_truoc
        FROM public.queue_entry q
       WHERE q.clinic_id = v.clinic_id AND q.visit_id = v.visit_id
         AND q.status IN ('serving', 'called', 'waiting', 'blocked')
       ORDER BY CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                WHEN 'waiting' THEN 2 ELSE 3 END,
                (q.room_id IS NOT DISTINCT FROM v.current_room_id) DESC,
                coalesce(q.eligible_at, q.created_at)
       LIMIT 1
  ) hq ON TRUE
 WHERE v.clinic_id = $1::uuid
   AND v.status = ANY($2::text[])
   -- CHỈ LƯỢT CÒN MỞ HÔM NAY (Tuyền 29/09/2026): khách đã check-out / đóng lượt
   -- (`closed_at`, hoặc đứng ở bước đóng lượt LUOTKHAM-15) và lượt của các ngày
   -- trước không còn "trong phòng khám" — không đếm, không báo chờ quá lâu.
   AND v.closed_at IS NULL
   AND v.current_node_code IS DISTINCT FROM 'LUOTKHAM-15'
   -- V8: lượt BÁN LẺ (khách chỉ mua thuốc ở quầy) không qua điều phối.
   AND NOT v.ban_le
   AND coalesce(v.checked_in_at, v.created_at) >=
       (date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')
        AT TIME ZONE 'Asia/Ho_Chi_Minh')
   -- CHỈ LƯỢT CỦA CƠ SỞ ĐANG ĐỨNG (08/10/2026). Không biết cơ sở của lượt hoặc
   -- không truyền cơ sở ($3 rỗng) → giữ.
   AND coalesce(v.location_id, a.location_id, $3::uuid)
       IS NOT DISTINCT FROM coalesce($3::uuid, v.location_id, a.location_id)
 ORDER BY v.current_node_since NULLS LAST, v.checked_in_at
 LIMIT 400
"""

_STATIONS_SQL = """
SELECT r.id, r.code, r.name, r.node_code, r.capacity, r.accepting, r.sort,
       r.show_on_tv, r.floor,
       -- MỘT PHÒNG PHỤC VỤ NHIỀU BƯỚC. `node_code` chỉ là bước CHÍNH (dùng để
       -- xếp nhóm); danh sách thật nằm ở clinic_room_node. Giao diện lọc "phòng
       -- nào chuyển sang được" phải đọc danh sách này, không đọc cột đơn — nếu
       -- không thì một ca Nam khoa sẽ không thấy phòng khám nào.
       (SELECT coalesce(array_agg(rn.node_code ORDER BY rn.node_code), '{}')
          FROM public.clinic_room_node rn WHERE rn.room_id = r.id)
                                                  AS serves_nodes,
       n.name AS node_name,
       coalesce(t.wait_minutes, d.wait_minutes, 20) AS threshold_minutes,
       coalesce(t.max_waiting,  d.max_waiting,  8)  AS threshold_waiting,
       -- ĐANG PHỤC VỤ vs ĐANG CHỜ. Bước đã bắt đầu (IN_PROGRESS) là đang phục
       -- vụ; PENDING là đang chờ tới lượt. Gộp hai số này lại thì Trưởng ca
       -- không biết phòng đang kẹt hay đang rảnh.
       -- ĐẾM THEO HÀNG CHỜ THẬT (queue_entry) — 17/09/2026. Bản cũ đếm
       -- work_item của luồng chỉ định cũ, nên khách trên luồng mới không bao
       -- giờ làm phòng "đông": trưởng ca nhìn SA1 có 5 người chờ vẫn thấy 0.
       coalesce(qq.serving, 0)  AS serving,
       coalesce(qq.waiting, 0)  AS waiting,
       coalesce(qq.max_wait, 0) AS max_wait,
       coalesce(qq.avg_wait, 0) AS avg_wait
  FROM public.clinic_room r
  LEFT JOIN public.node_definition n
         ON n.code = r.node_code AND n.clinic_id = r.clinic_id
  LEFT JOIN public.dispatch_threshold t
         ON t.room_id = r.id AND t.clinic_id = r.clinic_id
  LEFT JOIN public.dispatch_threshold d
         ON d.room_id IS NULL AND d.clinic_id = r.clinic_id
  LEFT JOIN LATERAL (
      SELECT count(*) FILTER (WHERE q.status IN ('called', 'serving')) AS serving,
             count(*) FILTER (WHERE q.status = 'waiting')             AS waiting,
             max(EXTRACT(EPOCH FROM (
                     now() - coalesce(q.eligible_at, q.created_at))) / 60)
                 FILTER (WHERE q.status = 'waiting')::int              AS max_wait,
             avg(EXTRACT(EPOCH FROM (
                     now() - coalesce(q.eligible_at, q.created_at))) / 60)
                 FILTER (WHERE q.status = 'waiting')::int              AS avg_wait
        FROM public.queue_entry q
        JOIN public.visit v
          ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
         AND v.status = ANY($2::text[])
         -- Cùng luật với _OVERVIEW_SQL: lượt đã đóng / ngày cũ không tính tải phòng.
         AND v.closed_at IS NULL
         AND v.current_node_code IS DISTINCT FROM 'LUOTKHAM-15'
         AND coalesce(v.checked_in_at, v.created_at) >=
             (date_trunc('day', now() AT TIME ZONE 'Asia/Ho_Chi_Minh')
              AT TIME ZONE 'Asia/Ho_Chi_Minh')
       WHERE q.clinic_id = r.clinic_id
         AND q.status IN ('waiting', 'called', 'serving')
         -- Hàng DOCTOR không mang phòng: tính vào phòng khách đang đứng.
         AND coalesce(q.room_id, v.current_room_id) = r.id
  ) qq ON TRUE
 WHERE r.clinic_id = $1::uuid AND r.is_active
   -- CHỈ PHÒNG CỦA CƠ SỞ ĐANG ĐỨNG. Không lọc thì khi Hào Nam mở, nhân sự ở đó
   -- thấy nguyên danh sách phòng của Kim Ngưu và bấm chuyển bệnh nhân sang một
   -- phòng cách vài cây số. NULL = không truyền cơ sở (bảng tổng của quản lý)
   -- thì hiện tất.
   -- `coalesce` thay cho `($3 IS NULL OR col = $3)`: cùng nghĩa, nhưng không có
   -- nhánh OR nào để một bộ lọc tenant lọt qua. Bài soi phạm vi tenant chặn
   -- đúng hình dạng đó, và nó chặn đúng — một OR viết vội ở đây là mở đường
   -- đọc dữ liệu của phòng khám khác.
   AND r.location_id = coalesce($3::uuid, r.location_id)
 GROUP BY r.id, r.code, r.name, r.node_code, r.capacity, r.accepting, r.sort,
          r.show_on_tv, r.floor, n.name, t.wait_minutes, d.wait_minutes,
          t.max_waiting, d.max_waiting, qq.serving, qq.waiting, qq.max_wait,
          qq.avg_wait
 ORDER BY r.sort, r.code
"""


class DispatchService:
    """Đọc và ghi vị trí bệnh nhân cho bảng điều phối."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────

    async def overview(
        self, *, clinic_id: str, location_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Mỗi bệnh nhân đang trong phòng khám là một dòng.

        `location_id` = cơ sở người đang xem; None = mọi cơ sở.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _OVERVIEW_SQL,
                clinic_id,
                list(LIVE_VISIT_STATUSES),
                location_id or None,
            )
        # Mỗi dòng là một người đang ở trong phòng khám. Cắt im lặng ở đây nghĩa
        # là có người đứng đó mà bảng điều phối không thấy.
        canh_bao_neu_day("dieu_phoi.tong_quan", len(rows), 400, clinic_id=clinic_id)
        return [_overview_row(r) for r in rows]

    async def chi_dinh(self, *, clinic_id: str, visit_id: str) -> list[dict[str, Any]]:
        """BÁC SĨ ĐÃ CHỈ ĐỊNH GÌ cho lượt khám này — Tuyền chốt 16/09/2026.

        Thay khối "tuyến điều phối" (áp một quy trình mẫu lên cả lượt khám):
        *"cái tuyến lúc ấn vào hiện tại nó quá cứng, cần mềm để linh hoạt"*.

        Trưởng ca không tự nghĩ ra việc cho bệnh nhân — việc đã có sẵn trong chỉ
        định của bác sĩ. Thứ ông ấy cần biết là: còn những việc nào chưa làm, và
        chỗ làm việc ấy có đang tắc không. Cột `dang_cho_buoc` trả lời vế sau,
        nên quyết định "đổi phòng hay đổi bác sĩ" dựa trên số thật chứ không
        dựa vào cảm giác.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _CHI_DINH_SQL, clinic_id, visit_id, list(LIVE_VISIT_STATUSES)
            )
            tai_chinh = await finance_gate.states_for_orders(
                conn, clinic_id, [r["id"] for r in rows]
            )
        return [
            {
                **dict(r),
                # json_agg về tay asyncpg là chuỗi — giải ra danh sách.
                "phong_lam_duoc": json.loads(r["phong_lam_duoc"] or "[]"),
                "xong": r["exec_status"] in _CHI_DINH_XONG,
                # Nhãn trạng thái rõ (Tuyền 29/09/2026) — máy chủ quyết, màn vẽ.
                "trang_thai": _iso_nhan(
                    trang_thai_dich_vu(
                        exec_status=r["exec_status"],
                        execution_status=r["execution_status"],
                        doi_tac=bool(r["doi_tac"]),
                        ket_qua_luc=r["ket_qua_luc"],
                        xong_luc=r["xong_luc"],
                        khach_ve=r["khach_ve_luc"] is not None,
                        hang=r["work_status"],
                        vao_hang_luc=r["vao_hang_luc"],
                        goi_luc=r["goi_luc"],
                        lam_tu=r["lan_lam_tu"] or r["serving_at"],
                        so_truoc=r["so_truoc"],
                        tai_chinh_xong=bool(
                            (q := tai_chinh.get(r["id"])) is not None
                            and q.financially_ready
                        ),
                    )
                ),
                # Chỉ định đời mới đổi phòng qua lệnh xếp phòng CHÍNH THỨC (khối
                # "Đổi phòng" chung, `xep-phong-v1`) — lối điều phối cũ từ chối
                # chúng (LIFECYCLE_ROUTING_REQUIRED). Cùng một luật với Bàn khám.
                "doi_phong_duoc": doi_phong_duoc(
                    selection_status=r["selection_status"],
                    execution_status=r["execution_status"],
                    exec_status=r["exec_status"],
                    doi_tac=bool(r["doi_tac"]),
                ),
            }
            for r in rows
        ]

    async def stations(
        self, *, clinic_id: str, location_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Tải của từng phòng: đang phục vụ, đang chờ, chờ lâu nhất.

        `location_id` = cơ sở người đang xem. None = hiện mọi cơ sở (bảng tổng
        của quản lý).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _STATIONS_SQL, clinic_id, list(LIVE_VISIT_STATUSES), location_id
            )
        return [
            {
                "id": str(r["id"]),
                "code": r["code"],
                "name": r["name"],
                # NULL = chưa khai tầng, và giao diện phải NÓI RA chứ không
                # đoán. Ba phòng siêu âm của Kim Ngưu đang ở trạng thái này:
                # báo cáo onsite nói siêu âm ở tầng 2 VÀ tầng 4 nhưng không nói
                # phòng nào ở tầng nào.
                "floor": r["floor"],
                "node_code": r["node_code"],
                "serves_nodes": list(r["serves_nodes"] or []),
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

    async def alerts(
        self, *, clinic_id: str, location_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Cảnh báo vận hành, xếp theo mức độ.

        Tính từ chính hai truy vấn trên chứ không từ một bảng cảnh báo riêng:
        một bảng cảnh báo là một bản sao của sự thật, và nó sẽ cũ đúng vào lúc
        Trưởng ca cần tin nó nhất.

        Chỉ cơ sở ĐANG ĐỨNG (`location_id`; Tuyền 08/10/2026: "sang cơ sở khác
        là của cơ sở đó hết") — người ở Hào Nam không xử lý được phòng Kim Ngưu
        đang tắc. None = mọi cơ sở.
        """
        patients = await self.overview(clinic_id=clinic_id, location_id=location_id)
        rooms = await self.stations(
            clinic_id=clinic_id, location_id=location_id or None
        )
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
        target_staff_id: str | None = None,
    ) -> dict[str, Any]:
        """Chuyển bệnh nhân sang bước/phòng khác. Một lời gọi, một giao dịch."""
        overridden: dict[str, Any] | None = None
        async with self._pool.acquire() as conn, conn.transaction():
            # LƯỢT ĐI LUỒNG KHÁM MỚI không chuyển bằng đường này (Slice 1,
            # 18/09/2026). `move_visit_to_station` là rail cũ: ghi work_item và
            # con trỏ vị trí, ghi nhật ký thiếu vai — trong khi luồng mới tự đặt
            # vị trí theo hàng chờ (`_cap_nhat_vi_tri`) và có chuyển phòng TỪNG
            # CHỈ ĐỊNH (`LuotKhamService.dispatch_order`, nhật ký đủ vai). Hai
            # người cùng ghi một con trỏ là cách khách "đang ở" sai phòng.
            if await la_luong_moi(conn, identity.clinic_id, visit_id):
                raise ValidationError(
                    "Lượt khám này đi luồng mới — chuyển phòng từng chỉ định ở mục"
                    " “Bác sĩ chỉ định gì”."
                )
            # LUẬT THỨ TỰ BẮT BUỘC chạy TRƯỚC, trong cùng transaction. Chạy sau
            # thì bệnh nhân đã bị chuyển rồi mới báo "không được" — và không có
            # nút hoàn tác nào cho một người đang đi bộ sang phòng khác.
            overridden = await gate_enforce(
                conn,
                identity=identity,
                visit_id=visit_id,
                to_node=node_code,
                target_staff_id=target_staff_id,
                override_reason=reason,
            )
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
        return {
            "ok": True,
            "work_item_id": str(item_id),
            # Màn hình nói rõ vừa bỏ qua luật nào, chứ không im lặng cho qua.
            "gate_overridden": overridden,
        }

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
            raise ValidationError("Đổi tuyến giữa chừng bắt buộc phải ghi lý do.")

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

                # Tuyến là THỨ TỰ các việc bác sĩ đã chỉ định (15/09/2026, CONTEXT
                # v1.0: bác sĩ duyệt chỉ định → trưởng ca điều phối). Mẫu tuyến
                # liệt kê cả dịch vụ lượt này không có; giữ lại bước dịch vụ nào
                # đã có việc (chưa huỷ), bỏ phần còn lại và nói rõ đã bỏ gì —
                # không để tuyến gợi ý một dịch vụ không ai chỉ định.
                steps, bo_qua = await _buoc_theo_chi_dinh(
                    conn,
                    clinic_id=identity.clinic_id,
                    visit_id=visit_id,
                    steps=list(tpl["steps"]),
                )
                if not steps:
                    raise ValidationError(
                        f"Tuyến {template_code} chỉ gồm dịch vụ bác sĩ chưa chỉ định "
                        "cho lượt này — chờ bác sĩ chỉ định rồi mới xếp tuyến."
                    )

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
                    steps,
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
                            "steps": steps,
                            "bo_qua_chua_chi_dinh": bo_qua,
                            "kept_steps": list(done or []),
                            "is_exception": is_exception,
                            "reason": reason,
                        }
                    ),
                    _json(
                        # Ba khoá, cùng hình dạng với `audit.record_event`.
                        # Thiếu `clinic_staff_id` thì nhật ký chỉ tra ra tên
                        # qua `auth_user_id`, mà khoá ấy chỉ phủ 9/57 nhân sự
                        # (số người đã liên kết tài khoản đăng nhập).
                        {
                            "actor_auth_user_id": identity.auth_user_id,
                            "clinic_staff_id": identity.staff_id,
                            "clinic_role": identity.role.value,
                            # Vai tài khoản gốc (vai dùng có thể khác).
                            "vai_tai_khoan": identity.vai_goc.value,
                        }
                    ),
                )

        logger.info(
            "dispatch_route_applied",
            clinic_id=identity.clinic_id,
            visit_id=visit_id,
            template=template_code,
            is_exception=is_exception,
        )
        return {
            "ok": True,
            "route_id": str(route_id),
            "steps": steps,
            "bo_qua_chua_chi_dinh": bo_qua,
        }

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
        self, *, clinic_id: str, limit: int = 200, location_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Lịch sử điều phối: sổ `dispatch.*` cũ (theo lượt) GỘP với xếp / đổi
        phòng TỪNG CHỈ ĐỊNH của luồng mới (`service.routed` — Bàn khám, quầy thu,
        trưởng ca, kéo thả ở Điều phối ca). Thiếu nửa sau thì mọi lần chuyển
        phòng đời mới không hiện ở đâu cả (bấm thật 28/09/2026). Phòng trả TÊN,
        không trả mã."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT x.*, nf.name AS from_node_name, nt.name AS to_node_name
                  FROM (
                  SELECT h.created_at, h.event_type, h.visit_id::text AS visit_id,
                         h.from_node, h.to_node,
                         coalesce(rf.name, h.from_room) AS from_room,
                         coalesce(rt.name, h.to_room) AS to_room,
                         h.reason, h.actor_name, h.patient_name, h.patient_code,
                         NULL::text AS dich_vu, NULL::text AS ly_do_ma,
                         NULL::text AS nguon, NULL::text AS ly_do_chu
                    FROM public.v_dispatch_history h
                    LEFT JOIN public.clinic_room rf
                      ON rf.clinic_id = h.clinic_id AND rf.code = h.from_room
                    LEFT JOIN public.clinic_room rt
                      ON rt.clinic_id = h.clinic_id AND rt.code = h.to_room
                   WHERE h.clinic_id = $1::uuid
                  UNION ALL
                  SELECT e.occurred_at, e.event_type, e.payload ->> 'visit_id',
                         NULL, NULL, rf.name, rt.name, NULL, s.full_name,
                         p.full_name, p.patient_code,
                         o.service_name, e.payload ->> 'reason_code',
                         e.payload ->> 'nguon', e.payload ->> 'ly_do'
                    FROM public.event_log e
                    LEFT JOIN public.clinic_room rf
                      ON rf.clinic_id = e.clinic_id
                     AND rf.id = NULLIF(e.payload ->> 'from_room_id', '')::uuid
                    LEFT JOIN public.clinic_room rt
                      ON rt.clinic_id = e.clinic_id
                     AND rt.id = NULLIF(e.payload ->> 'to_room_id', '')::uuid
                    LEFT JOIN public.service_order o
                      ON o.clinic_id = e.clinic_id AND o.id = e.aggregate_id
                    LEFT JOIN public.staff s
                      ON s.auth_user_id =
                         NULLIF(e.metadata ->> 'actor_auth_user_id', '')::uuid
                    LEFT JOIN public.visit v
                      ON v.clinic_id = e.clinic_id
                     AND v.visit_id = NULLIF(e.payload ->> 'visit_id', '')::uuid
                    LEFT JOIN public.patient p
                      ON p.clinic_id = e.clinic_id
                     AND p.clinic_patient_id = v.clinic_patient_id
                   WHERE e.clinic_id = $1::uuid
                     AND e.aggregate_type = 'service_order'
                     AND e.event_type IN ('service.routed',
                                          'service.room_transferred')
                ) x
                LEFT JOIN public.node_definition nf
                  ON nf.clinic_id = $1::uuid AND nf.code = x.from_node
                LEFT JOIN public.node_definition nt
                  ON nt.clinic_id = $1::uuid AND nt.code = x.to_node
                CROSS JOIN LATERAL (
                    SELECT public.co_so_cua_luot(
                               $1::uuid, NULLIF(x.visit_id, '')::uuid) AS co_so
                ) cs
                -- Chỉ lượt của cơ sở đang đứng (08/10/2026); không biết → giữ.
                WHERE coalesce(cs.co_so, $3::uuid)
                      IS NOT DISTINCT FROM coalesce($3::uuid, cs.co_so)
                ORDER BY x.created_at DESC LIMIT $2
                """,
                clinic_id,
                limit,
                location_id or None,
            )
        return [
            {
                "at": r["created_at"].isoformat(),
                "event_type": r["event_type"],
                # Nhãn tiếng Việt + tên bước do máy chủ quyết — màn không in mã thô.
                "event_label": action_label_theo_nguon(r["event_type"], r.get("nguon")),
                "visit_id": r["visit_id"],
                "from_node": r["from_node"],
                "to_node": r["to_node"],
                "from_node_name": r.get("from_node_name"),
                "to_node_name": r.get("to_node_name"),
                "from_room": r["from_room"],
                "to_room": r["to_room"],
                "reason": r["reason"] or _ly_do_xep_phong(r),
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
                        f"{p['patient_name']} đã check-in nhưng chưa được xếp trạm nào"
                    ),
                    "room_code": None,
                    "patients": [
                        {"name": p["patient_name"], "code": p["patient_code"]}
                    ],
                }
            )
        # Cảnh báo "chưa được chọn tuyến điều phối" ĐÃ BỎ (17/09/2026): tuyến
        # điều phối không còn nút chọn từ 16/09, nên câu này báo mọi khách.

    rank = {"critical": 0, "warning": 1}
    out.sort(key=lambda a: (rank.get(a["severity"], 9), a["message"]))
    return out


async def la_luong_moi(conn: asyncpg.Connection, clinic_id: str, visit_id: str) -> bool:
    """Lượt khám này đã vào luồng khám mới (đã đo sinh hiệu / có phiên khám)."""
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.encounter_flow f"
            " WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid)"
            " OR EXISTS (SELECT 1 FROM public.consultation c"
            " WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid)",
            clinic_id,
            visit_id,
        )
    )


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
        "so_tiep_don": r.get("so_tiep_don"),
        "so_booking": r.get("so_booking"),
        "specialty": r["specialty"],
        "doctor_name": r["doctor_name"],
        "current_node_code": r["current_node_code"],
        "current_node_name": r["current_node_name"],
        "room_id": str(r["room_id"]) if r["room_id"] else None,
        "room_code": r["room_code"],
        "room_name": r["room_name"],
        "room_floor": r["room_floor"],
        "wait_minutes": r["wait_minutes"],
        "total_minutes": r["total_minutes"],
        "threshold_minutes": r["threshold_minutes"] or 20,
        "done_steps": done,
        "luong_moi": bool(r.get("luong_moi")),
        "route_steps": route,
        "next_step": next_step_of(route, done, r["current_node_code"])
        or r.get("buoc_chi_dinh_ke"),
        "checked_in_at": (
            r["checked_in_at"].isoformat() if r["checked_in_at"] else None
        ),
        # Nhãn trạng thái khách (Tuyền 29/09/2026) — màn chỉ vẽ.
        "trang_thai": _iso_nhan(
            trang_thai_khach(
                khach_ve=r.get("khach_ve_luc") is not None,
                lane=r.get("hang_lane"),
                hang=r.get("hang_status"),
                vao_hang_luc=r.get("hang_vao"),
                goi_luc=r.get("hang_goi"),
                lam_tu=r.get("hang_lam"),
                so_truoc=r.get("hang_so_truoc"),
                cho_kq_doi_tac=bool(r.get("cho_kq_doi_tac")),
            )
        ),
    }


def _iso_nhan(nhan: dict[str, Any]) -> dict[str, Any]:
    """`tu_luc` ra chuỗi ISO — các dòng tổng quan đi qua JSON tay (SSE)."""
    tu = nhan.get("tu_luc")
    return {**nhan, "tu_luc": tu.isoformat() if tu is not None else None}


def _json(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


#: Nhóm bước chỉ sinh từ chỉ định của bác sĩ (order_services và chuỗi của nó).
NHOM_BUOC_DICH_VU: tuple[str, ...] = ("dich_vu", "ket_qua")


async def _buoc_theo_chi_dinh(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str, steps: list[str]
) -> tuple[list[str], list[str]]:
    """(bước giữ lại, bước dịch vụ bị bỏ vì lượt khám không có chỉ định).

    Cùng luật với `move_visit_to_station` (20260915000013): bước dịch vụ cần
    việc sinh từ chỉ định; nhà thuốc (THUOC-*) cần đơn thuốc của lượt khám.
    """
    rows = await conn.fetch(
        """
        SELECT n.code,
               CASE WHEN n.code LIKE 'THUOC-%' THEN EXISTS (
                   SELECT 1 FROM public.prescription r
                    WHERE r.clinic_id = n.clinic_id AND r.visit_id = $2::uuid
                      AND r.removed_at IS NULL
               ) ELSE EXISTS (
                   SELECT 1 FROM public.work_item w
                    WHERE w.clinic_id = n.clinic_id AND w.visit_id = $2::uuid
                      AND w.node_code = n.code AND w.status <> 'CANCELLED'
               ) END AS co_viec
          FROM public.node_definition n
         WHERE n.clinic_id = $1::uuid AND n.code = ANY($3::text[])
           AND n.flow_group = ANY($4::text[])
        """,
        clinic_id,
        visit_id,
        steps,
        list(NHOM_BUOC_DICH_VU),
    )
    khong_chi_dinh = {r["code"] for r in rows if not r["co_viec"]}
    return (
        [s for s in steps if s not in khong_chi_dinh],
        [s for s in steps if s in khong_chi_dinh],
    )


#: Trạng thái chỉ định đã XONG — không còn là việc phải xếp phòng nữa.
_CHI_DINH_XONG: tuple[str, ...] = ("performed", "not_performed", "cancelled")

_CHI_DINH_SQL = """
SELECT o.id::text,
       o.service_code, o.service_name, o.node_code, o.exec_status, o.version,
       o.selection_status, o.execution_status, o.routing_revision,
       n.name AS node_name,
       coalesce(n.lam_ben_ngoai, false) AS doi_tac,
       o.room_id::text AS room_id, r.name AS room_name, r.floor AS room_floor,
       q.status AS work_status,
       -- NHÃN TRẠNG THÁI (Tuyền 29/09/2026): mốc giờ + vị trí trong hàng.
       q.eligible_at AS vao_hang_luc, q.called_at AS goi_luc,
       q.serving_at, q.so_truoc,
       o.ket_qua_luc, o.finished_at AS xong_luc, v.closed_at AS khach_ve_luc,
       (SELECT a.started_at FROM public.service_execution_attempt a
         WHERE a.clinic_id = o.clinic_id AND a.service_order_id = o.id
           AND a.status = 'IN_PROGRESS') AS lan_lam_tu,
       -- SỐ NGƯỜI ĐANG CHỜ Ở PHÒNG ĐANG XẾP — câu trưởng ca thật sự hỏi khi
       -- nhìn một chỉ định: "chỗ ấy có tắc không?". Đếm theo hàng chờ thật.
       (SELECT count(*) FROM public.queue_entry q2
          JOIN public.visit v2
            ON v2.visit_id = q2.visit_id AND v2.clinic_id = q2.clinic_id
           AND v2.status = ANY($3::text[])
         WHERE q2.clinic_id = o.clinic_id AND q2.room_id = o.room_id
           AND q2.status = 'waiting') AS dang_cho_buoc,
       -- CÁC PHÒNG LÀM ĐƯỢC BƯỚC NÀY + tải + ngưỡng "đầy", để chuyển khách
       -- sang phòng vắng hơn ngay tại đây (Tuyền 17/09: "siêu âm có 4 khách
       -- chờ là đầy rồi nên khách 5 được trưởng ca điều hướng sang SA2").
       (SELECT coalesce(json_agg(json_build_object(
                   'id', r3.id, 'name', r3.name, 'floor', r3.floor,
                   'waiting', (SELECT count(*) FROM public.queue_entry q3
                                 JOIN public.visit v3
                                   ON v3.visit_id = q3.visit_id
                                  AND v3.clinic_id = q3.clinic_id
                                  AND v3.status = ANY($3::text[])
                                WHERE q3.clinic_id = r3.clinic_id
                                  AND q3.room_id = r3.id AND q3.status = 'waiting'),
                   'threshold_waiting', coalesce(t3.max_waiting, d3.max_waiting, 8)
               ) ORDER BY r3.sort, r3.code), '[]'::json)
          FROM public.clinic_room r3
          LEFT JOIN public.dispatch_threshold t3
                 ON t3.room_id = r3.id AND t3.clinic_id = r3.clinic_id
          LEFT JOIN public.dispatch_threshold d3
                 ON d3.room_id IS NULL AND d3.clinic_id = r3.clinic_id
         WHERE r3.clinic_id = o.clinic_id AND r3.is_active AND r3.accepting
           AND NOT r3.la_doi_tac
           -- Chỉ phòng ở cơ sở của lượt (08/10/2026) — không thì chọn được
           -- phòng cơ sở kia rồi mới bị chặn khi xếp.
           AND coalesce(r3.location_id, public.co_so_cua_luot(v.clinic_id, v.visit_id))
               IS NOT DISTINCT FROM
               coalesce(public.co_so_cua_luot(v.clinic_id, v.visit_id), r3.location_id)
           -- Dịch vụ gắn phòng riêng thì chỉ các phòng ấy (30/09/2026).
           AND public.phong_lam_duoc(r3.clinic_id, r3.id, o.node_code,
                                     o.service_code)
       ) AS phong_lam_duoc
  FROM public.service_order o
  JOIN public.visit v
    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
   AND v.status = ANY($3::text[])
  LEFT JOIN public.node_definition n
         ON n.code = o.node_code AND n.clinic_id = o.clinic_id
  LEFT JOIN public.clinic_room r ON r.id = o.room_id
  LEFT JOIN LATERAL (
      SELECT q1.status, q1.eligible_at, q1.called_at, q1.serving_at,
             CASE WHEN q1.status = 'waiting' THEN (
                 SELECT count(*)::int FROM public.queue_entry o1
                  WHERE o1.clinic_id = q1.clinic_id AND o1.lane = q1.lane
                    AND o1.room_id = q1.room_id AND o1.id <> q1.id
                    AND o1.status IN ('waiting', 'called')
                    AND (coalesce(o1.eligible_at, o1.created_at), o1.id)
                        < (coalesce(q1.eligible_at, q1.created_at), q1.id))
             END AS so_truoc
        FROM public.queue_entry q1
       WHERE q1.clinic_id = o.clinic_id AND q1.visit_id = o.visit_id
         AND q1.ref_id = o.id AND q1.reason = 'SERVICE'
       ORDER BY q1.created_at DESC LIMIT 1
  ) q ON TRUE
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   -- Khách đã bỏ ở quầy thu (NOT_SELECTED) không còn là việc phải làm — trước
   -- 26/09/2026 nó vẫn hiện "Đã duyệt · chờ xếp phòng" và bị đếm vào "còn N
   -- việc chưa làm" (bấm thật trên prod).
   AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
 ORDER BY o.created_at
"""
