"""Đóng lượt khám ở quầy Lễ tân — đối soát trước, rồi mới đóng.

ĐÓNG LƯỢT KHÔNG PHẢI LÀ KÝ BỆNH ÁN, VÀ ĐÂY LÀ CHỖ SUÝT SAI.

``visit.status = 'FINALIZED'`` trông như "lượt khám đã xong", nhưng nó là KHOÁ
HỒ SƠ BỆNH ÁN theo TT13/2011/TT-BYT: trigger ``visit_finalized_block_update``
chặn mọi UPDATE sau đó, trừ đúng một đường FINALIZED → AMENDED. Đó là chữ ký
chuyên môn của bác sĩ.

Nếu Lễ tân bấm "Hoàn tất check-out" mà hệ thống đặt FINALIZED, thì một thao tác
hành chính vừa khoá vĩnh viễn một hồ sơ y tế — và bác sĩ muốn sửa sau đó phải đi
đường đính chính. Yêu cầu khách hàng cũng nói thẳng: *"Trạng thái lượt khám và
trạng thái thanh toán phải được quản lý riêng: đã khám xong không đồng nghĩa đã
thanh toán đủ."*

Nên đóng lượt ở đây là hoàn tất BƯỚC ``LUOTKHAM-15`` trong checklist, không đụng
tới ``visit.status``. Bác sĩ vẫn ký bệnh án theo đường của mình, lúc nào cũng
được.

ĐỐI SOÁT TRƯỚC KHI ĐÓNG — bốn thứ Notion §2 liệt kê, cộng một thứ nữa:

  1. dịch vụ đã chỉ định (bác sĩ đã duyệt) mà chưa thực hiện xong;
  2. kết quả bác sĩ còn chờ để đọc trong lượt, hoặc bác sĩ chưa khám/đọc xong
     — cả hai đọc RAIL MỚI (service_order, review_round, round_requirement);
     kết quả đã chuyển theo dõi (follow_up_case) không giữ lượt;
  3. khoản chưa thu (dịch vụ luôn phải thu; thuốc chỉ khi có đơn);
  4. bệnh nhân vẫn đang đứng ở một phòng — *"Không cho đóng lượt khi bệnh nhân
     vẫn đang được xử lý tại một phòng"*.

Vượt qua bằng NGOẠI LỆ thì bắt buộc lý do, và lý do được ghi cùng ảnh chụp
danh sách vướng mắc tại thời điểm đóng — để về sau đọc lại được người đóng đã
nhìn thấy gì mà vẫn quyết định đóng.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.xem_luot_service import doc_su_kien_luot

logger = structlog.get_logger()

# Bước "Đóng lượt khám" trong node_definition.
CLOSE_NODE = "LUOTKHAM-15"

_READINESS_SQL = """
SELECT
    v.visit_id,
    v.status                       AS visit_status,
    v.current_node_code,
    v.checked_in_at,
    r.code                         AS room_code,
    r.name                         AS room_name,
    p.full_name                    AS patient_name,
    p.patient_code,
    -- Đã hoàn tất bước đóng lượt chưa.
    EXISTS (SELECT 1 FROM public.work_item w
             WHERE w.visit_id = v.visit_id AND w.node_code = $2
               AND w.status = 'COMPLETED')                     AS already_closed,
    -- ①–② ĐỌC RAIL MỚI (Slice 1, 18/09/2026). Bản trước đếm `service_log` và
    --    `lab_result` — hai bảng mà luồng khám mới không ghi nữa, nên quầy
    --    không bao giờ thấy chỉ định còn dở hay kết quả bác sĩ còn chờ đọc.
    --
    -- ① Chỉ định bác sĩ đã duyệt mà chưa làm (nháp của thư ký không tính).
    coalesce((SELECT count(*) FROM public.service_order o
               WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
                 AND o.exec_status IN ('authorized', 'assigned', 'in_progress')),
             0)                                                AS svc_open,
    -- ② Kết quả bác sĩ còn chờ để đọc lại trong lượt: yêu cầu "cần kết quả"
    --    chưa đạt của vòng đọc chưa đóng. Kết quả đã CHUYỂN THEO DÕI không
    --    tính — nó không giữ lượt (follow_up_case lo tiếp).
    coalesce((SELECT count(*) FROM public.round_requirement q
                JOIN public.review_round r
                  ON r.id = q.round_id AND r.clinic_id = q.clinic_id
               WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                 AND r.status <> 'closed' AND q.need = 'VALID_RESULT'
                 AND q.status = 'open'), 0)                    AS lab_pending,
    -- ②b Bác sĩ chưa khám/đọc xong: còn phiên khám đang chờ hoặc đang khám,
    --     hoặc vòng đọc kết quả chưa đóng.
    (EXISTS (SELECT 1 FROM public.consultation c
              WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
                AND c.status IN ('queued', 'in_progress'))
     OR EXISTS (SELECT 1 FROM public.review_round r
                 WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                   AND r.status <> 'closed'))                   AS exam_open,
    -- Việc theo dõi lượt này bàn giao (không chặn, chỉ để quầy biết).
    coalesce((SELECT count(*) FROM public.follow_up_case f
               WHERE f.clinic_id = v.clinic_id AND f.visit_id = v.visit_id
                 AND f.status = 'OPEN'), 0)                    AS follow_up_open,
    -- ③ Khoản đã thu, theo nhóm. Bỏ giao dịch đã huỷ.
    EXISTS (SELECT 1 FROM public.payment pm
             WHERE pm.visit_id = v.visit_id AND pm.kind = 'dich_vu'
               AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS paid_service,
    EXISTS (SELECT 1 FROM public.payment pm
             WHERE pm.visit_id = v.visit_id AND pm.kind = 'thuoc'
               AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS paid_drug,
    EXISTS (SELECT 1 FROM public.prescription pr
             WHERE pr.visit_id = v.visit_id
               AND pr.removed_at IS NULL)                        AS has_drug
  FROM public.visit v
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_room r ON r.id = v.current_room_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $3::uuid
"""


_BUOC_WORK_ITEM_SQL = """
SELECT w.node_code, w.status, w.started_at, w.finished_at,
       coalesce(nd.name, w.node_code) AS ten_buoc,
       s.full_name                    AS nguoi_lam,
       w.assigned_role                AS vai
  FROM public.work_item w
  LEFT JOIN public.node_definition nd
         ON nd.code = w.node_code AND nd.clinic_id = w.clinic_id
  LEFT JOIN public.staff s ON s.id = w.assigned_to
 WHERE w.visit_id = $2::uuid AND w.clinic_id = $1::uuid
   AND w.status <> 'CANCELLED'
 ORDER BY coalesce(w.finished_at, w.started_at, w.created_at)
"""

_BUOC_LUONG_MOI_SQL = """
SELECT * FROM (
    SELECT 'CHECKIN'::text AS node_code, 'COMPLETED'::text AS status,
           v.checked_in_at AS started_at, v.checked_in_at AS finished_at,
           'Tiếp nhận người bệnh (check-in)'::text AS ten_buoc,
           s.full_name AS nguoi_lam, NULL::text AS vai, 1 AS thu_tu
      FROM public.visit v
      LEFT JOIN public.staff s ON s.id = v.checked_in_by
     WHERE v.visit_id = $2::uuid AND v.clinic_id = $1::uuid
    UNION ALL
    SELECT 'SINH_HIEU', CASE WHEN m.created_at IS NULL THEN 'PENDING'
                             ELSE 'COMPLETED' END,
           m.created_at, m.created_at, 'Đo sinh hiệu', s.full_name, NULL, 2
      FROM (SELECT 1) x
      LEFT JOIN LATERAL (
          SELECT vm.created_at, vm.recorded_by
            FROM public.vital_measurement vm
           WHERE vm.visit_id = $2::uuid AND vm.clinic_id = $1::uuid
           ORDER BY vm.created_at DESC LIMIT 1) m ON TRUE
      LEFT JOIN public.staff s ON s.id = m.recorded_by
    UNION ALL
    SELECT 'KHAM', CASE c.status WHEN 'completed' THEN 'COMPLETED'
                                 WHEN 'in_progress' THEN 'IN_PROGRESS'
                                 ELSE 'PENDING' END,
           c.started_at, c.completed_at,
           CASE c.kind WHEN 'PRIMARY' THEN 'Khám với bác sĩ'
                       ELSE 'Đọc kết quả với bác sĩ' END,
           d.full_name, NULL, 3
      FROM public.consultation c
      LEFT JOIN public.staff d ON d.id = c.doctor_staff_id
     WHERE c.visit_id = $2::uuid AND c.clinic_id = $1::uuid
       AND c.status <> 'cancelled'
    UNION ALL
    SELECT o.node_code, CASE o.exec_status WHEN 'performed' THEN 'COMPLETED'
                                           -- Không làm được ≠ đã làm (smoke 18/09:
                                           -- Lan hiện "✓ Xong" siêu âm bị miễn).
                                           WHEN 'not_performed' THEN 'NOT_PERFORMED'
                                           WHEN 'in_progress' THEN 'IN_PROGRESS'
                                           ELSE 'PENDING' END,
           o.started_at, o.finished_at, coalesce(o.service_name, o.service_code),
           pf.full_name, NULL, 4
      FROM public.service_order o
      LEFT JOIN public.staff pf ON pf.id = o.performed_by
     WHERE o.visit_id = $2::uuid AND o.clinic_id = $1::uuid
       AND o.exec_status NOT IN ('draft', 'cancelled')
) b
ORDER BY coalesce(b.finished_at, b.started_at), b.thu_tu
"""


class CheckoutService:
    """Đối soát và đóng lượt khám tại quầy."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def readiness(
        self, *, identity: StaffIdentity, visit_id: str
    ) -> dict[str, Any]:
        """Lượt khám này đóng được chưa, và còn vướng gì."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                _READINESS_SQL, identity.clinic_id, CLOSE_NODE, visit_id
            )
        if row is None:
            raise ValidationError("Không tìm thấy lượt khám ở phòng khám này.")

        blockers = build_blockers(dict(row))
        return {
            "visit_id": str(row["visit_id"]),
            "patient_name": row["patient_name"],
            "patient_code": row["patient_code"],
            "room_code": row["room_code"],
            "room_name": row["room_name"],
            "already_closed": row["already_closed"],
            "checked_in_at": (
                row["checked_in_at"].isoformat() if row["checked_in_at"] else None
            ),
            "paid_service": row["paid_service"],
            "paid_drug": row["paid_drug"],
            "has_drug": row["has_drug"],
            "so_theo_doi": int(row["follow_up_open"] or 0),
            "blockers": blockers,
            "can_close": not blockers and not row["already_closed"],
        }

    async def pending_list(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Các lượt khám hôm nay chưa đóng, kèm vướng mắc của từng lượt.

        Một truy vấn cho cả danh sách. Gọi ``readiness()`` trong vòng lặp cũng
        ra kết quả ấy nhưng tốn một vòng mạng cho mỗi bệnh nhân — với 100 lượt
        một ngày thì đó là 100 vòng để vẽ một cái bảng.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _READINESS_SQL.replace(
                    "WHERE v.clinic_id = $1::uuid AND v.visit_id = $3::uuid",
                    "WHERE v.clinic_id = $1::uuid"
                    "   AND v.status <> 'FINALIZED'"
                    "   AND coalesce(v.checked_in_at, v.created_at) >= $3"
                    " ORDER BY coalesce(v.checked_in_at, v.created_at) DESC"
                    " LIMIT 300",
                ),
                identity.clinic_id,
                CLOSE_NODE,
                _vn_day_start(),
            )

        out: list[dict[str, Any]] = []
        for r in rows:
            blockers = build_blockers(dict(r))
            out.append(
                {
                    "visit_id": str(r["visit_id"]),
                    "patient_name": r["patient_name"],
                    "patient_code": r["patient_code"],
                    "room_name": r["room_name"],
                    "already_closed": r["already_closed"],
                    "checked_in_at": (
                        r["checked_in_at"].isoformat() if r["checked_in_at"] else None
                    ),
                    "so_theo_doi": int(r["follow_up_open"] or 0),
                    "blockers": blockers,
                    "can_close": not blockers and not r["already_closed"],
                }
            )
        return out

    async def chi_tiet(
        self, *, identity: StaffIdentity, visit_id: str
    ) -> dict[str, Any]:
        """Toàn cảnh một lượt khám để Lễ tân đối soát trước khi đóng.

        Bốn mục theo đúng bản thiết kế Quang gửi 06/08 — nhưng CHỈ ba mục có dữ
        liệu thật đứng sau, và mục thứ tư nói rõ là chưa có:

          ① Dịch vụ — từng bước trong luồng khám, ai làm, xong chưa (`work_item`).
          ② Tài chính — từng khoản đã thu (`payment`), và còn nợ gì.
          ③ Hồ sơ trả bệnh nhân — tệp kết quả THẬT của lượt (`tep_ket_qua`),
            kèm trạng thái từng tệp: chờ bác sĩ cho phép / được gửi / đã gửi.
            (Bản 06/08 luôn báo "chưa có kho lưu tệp" — đúng hồi đó, sai từ
            khi tệp kết quả lưu thật.)
          ④ Theo dõi sau khám — `follow_up_case`.

        Cộng một dòng thời gian dựng từ `event_log` — CHỈ việc đã xảy ra. Bản cũ
        đọc `work_item_event`, nơi luồng mới chỉ có các bước DỰ KIẾN tạo sẵn lúc
        check-in, nên hiện "Thanh toán — Lễ tân 15:36" như thể đã làm.
        """
        async with self._pool.acquire() as conn:
            chung = await conn.fetchrow(
                _READINESS_SQL, identity.clinic_id, CLOSE_NODE, visit_id
            )
            if chung is None:
                return {"ok": False, "visit_id": visit_id}

            # LUỒNG MỚI (lượt có phiên khám) đọc bước từ chính dữ liệu luồng mới:
            # check-in → đo sinh hiệu → các phiên khám → từng chỉ định. Bản cũ
            # chỉ đọc work_item, nên lượt đi luồng mới hiện "Thanh toán: Chưa
            # làm", "Sinh hiệu: Đang làm" dù đã thu đủ (17/09/2026).
            luong_moi = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.consultation"
                " WHERE visit_id = $2::uuid AND clinic_id = $1::uuid)",
                identity.clinic_id,
                visit_id,
            )
            buoc = await conn.fetch(
                _BUOC_LUONG_MOI_SQL if luong_moi else _BUOC_WORK_ITEM_SQL,
                identity.clinic_id,
                visit_id,
            )

            tien = await conn.fetch(
                """
                SELECT pm.kind, pm.amount, pm.status, pm.paid_at,
                       pm.voided_at IS NOT NULL AS da_huy
                  FROM public.payment pm
                 WHERE pm.visit_id = $2::uuid AND pm.clinic_id = $1::uuid
                 ORDER BY pm.paid_at NULLS LAST
                """,
                identity.clinic_id,
                visit_id,
            )

            appt = await conn.fetchval(
                "SELECT appointment_id FROM public.visit"
                " WHERE visit_id = $2::uuid AND clinic_id = $1::uuid",
                identity.clinic_id,
                visit_id,
            )
            moc = await doc_su_kien_luot(conn, identity.clinic_id, visit_id, appt)

            # Tệp kết quả của lượt: theo chỉ định của lượt, hoặc gắn thẳng
            # vào lịch hẹn của lượt (tệp tải từ màn CSKH / đời trước).
            tep = await conn.fetch(
                """
                SELECT t.ten_hien_thi, t.loai_tep, t.tai_len_luc,
                       t.cho_phep_gui_luc, t.gui_luc, t.gui_kenh
                  FROM public.tep_ket_qua t
                 WHERE t.clinic_id = $1::uuid
                   AND (t.service_order_id IN (
                            SELECT o.id FROM public.service_order o
                             WHERE o.visit_id = $2::uuid
                               AND o.clinic_id = $1::uuid)
                        OR ($3::uuid IS NOT NULL AND t.appointment_id = $3::uuid))
                 ORDER BY t.tai_len_luc
                """,
                identity.clinic_id,
                visit_id,
                appt,
            )

            # Việc theo dõi lượt này sinh ra — `follow_up_case.visit_id` (Slice
            # 1). Trước đó phải nối qua work_item của rail cũ, và rail mới không
            # đẻ work_item nên mục này luôn rỗng.
            theo_doi = await conn.fetch(
                """
                SELECT f.id, f.status, f.due_at, f.reason, f.owner_role,
                       s.full_name AS chu_so_huu
                  FROM public.follow_up_case f
                  LEFT JOIN public.staff s ON s.id = f.owner_staff_id
                 WHERE f.visit_id = $2::uuid AND f.clinic_id = $1::uuid
                 ORDER BY f.due_at NULLS LAST
                """,
                identity.clinic_id,
                visit_id,
            )

        blockers = build_blockers(dict(chung))
        return {
            "ok": True,
            "visit_id": str(chung["visit_id"]),
            "patient_name": chung["patient_name"],
            "patient_code": chung["patient_code"],
            "visit_status": chung["visit_status"],
            "checked_in_at": (
                chung["checked_in_at"].isoformat() if chung["checked_in_at"] else None
            ),
            "room_name": chung["room_name"],
            "already_closed": chung["already_closed"],
            "blockers": blockers,
            "can_close": not blockers and not chung["already_closed"],
            "dich_vu": [
                {
                    "ten": r["ten_buoc"],
                    "nguoi_lam": r["nguoi_lam"],
                    "vai": r["vai"],
                    "status": r["status"],
                    "xong_luc": (
                        r["finished_at"].isoformat() if r["finished_at"] else None
                    ),
                }
                for r in buoc
            ],
            "tai_chinh": [
                {
                    "loai": r["kind"],
                    "so_tien": float(r["amount"]) if r["amount"] is not None else None,
                    "status": r["status"],
                    "da_huy": r["da_huy"],
                    "luc": r["paid_at"].isoformat() if r["paid_at"] else None,
                }
                for r in tien
            ],
            "ho_so_tra": {
                "muc": [
                    {
                        "ten": r["ten_hien_thi"],
                        "loai_tep": r["loai_tep"],
                        "trang_thai": (
                            "DA_GUI"
                            if r["gui_luc"]
                            else "DUOC_GUI"
                            if r["cho_phep_gui_luc"]
                            else "CHO_BAC_SI"
                        ),
                        "gui_kenh": r["gui_kenh"],
                        "tai_len_luc": r["tai_len_luc"].isoformat(),
                    }
                    for r in tep
                ],
                "vi_sao_rong": "Lượt này chưa có tệp kết quả nào.",
            },
            "theo_doi": [
                {
                    "id": str(r["id"]),
                    "status": r["status"],
                    "ly_do": r["reason"],
                    "chu_so_huu": r["chu_so_huu"] or r["owner_role"],
                    "han": r["due_at"].isoformat() if r["due_at"] else None,
                }
                for r in theo_doi
            ],
            "moc_thoi_gian": [
                {
                    "luc": m["luc"],
                    "ten": m["viec"],
                    "lenh": m["ma"],
                    "den_trang_thai": None,
                    "nguoi_lam": m["ai"],
                }
                for m in moc
            ],
        }

    async def stale_list(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Lượt khám còn mở từ NHỮNG NGÀY TRƯỚC — thứ không màn hình nào thấy.

        Đo trên máy chủ ngày 06/08: 35 lượt đang OPEN/IN_PROGRESS, trong đó 18
        lượt check-in từ hôm trước. `pending_list` chỉ nhìn trong ngày (đúng cho
        việc của quầy hôm nay), `/visits/active` cũng vậy — nên 18 dòng ấy không
        có chỗ nào để xuất hiện, và cũng không có ai để hỏi.

        Chúng không phải rác cần dọn bằng script: mỗi dòng là một người thật đã
        bước vào phòng khám. Muốn đóng thì phải có người nhìn và ghi lý do —
        đúng đường mà `close(incomplete=True)` mở ra. `prevent_hard_delete` vốn
        đã cấm cách làm tắt.

        Cả những lượt KHÔNG CÓ giờ check-in (đo được 5 dòng) cũng vào đây: một
        lượt khám không biết bắt đầu lúc nào thì lại càng cần người xem lại.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                _READINESS_SQL.replace(
                    "WHERE v.clinic_id = $1::uuid AND v.visit_id = $3::uuid",
                    "WHERE v.clinic_id = $1::uuid"
                    "   AND v.status IN ('OPEN', 'IN_PROGRESS')"
                    "   AND (v.checked_in_at IS NULL OR v.checked_in_at < $3)"
                    " ORDER BY coalesce(v.checked_in_at, v.created_at) DESC"
                    " LIMIT 300",
                ),
                identity.clinic_id,
                CLOSE_NODE,
                _vn_day_start(),
            )

        return [
            {
                "visit_id": str(r["visit_id"]),
                "patient_name": r["patient_name"],
                "patient_code": r["patient_code"],
                "room_name": r["room_name"],
                "checked_in_at": (
                    r["checked_in_at"].isoformat() if r["checked_in_at"] else None
                ),
                "blockers": build_blockers(dict(r)),
            }
            for r in rows
        ]

    async def close(
        self,
        *,
        identity: StaffIdentity,
        visit_id: str,
        override_reason: str | None = None,
        incomplete: bool = False,
        incomplete_reason: str | None = None,
        ly_do_tu_dong: str | None = None,
    ) -> dict[str, Any]:
        """Đóng lượt. Còn vướng thì phải có lý do ngoại lệ.

        ``incomplete=True`` = KHÁCH VỀ GIỮA CHỪNG.

        Trước đây tình huống này không có chỗ nào ghi, nên cách duy nhất làm
        được là huỷ lịch hẹn — và hồ sơ trông như người ấy CHƯA TỪNG ĐẾN: mất
        dấu vết họ đã lấy số, đã đo sinh hiệu, đã được chỉ định dịch vụ.

        Đây là ĐƯỜNG DUY NHẤT ghi ``visit.status = 'INCOMPLETE'``. Mệnh đề
        ``WHERE status IN ('OPEN','IN_PROGRESS')`` bên dưới là thứ ngăn ai đó
        kéo một hồ sơ ĐÃ KÝ về "khám dở".

        Và nó KHÔNG chốt hồ sơ bệnh án. Khám dở là trạng thái KHÔNG-CUỐI: khách
        còn quay lại, bác sĩ còn ghi tiếp được và còn ký lên FINALIZED được. Đó
        đúng là ranh giới mà docstring đầu file này dựng lên — đóng lượt là việc
        của quầy, ký hồ sơ là việc của bác sĩ.
        """
        state = await self.readiness(identity=identity, visit_id=visit_id)
        if state["already_closed"]:
            # Không phải lỗi: hai người cùng bấm, hoặc bấm lại sau khi mạng lag.
            return {"ok": True, "already_closed": True}

        blockers = state["blockers"]
        reason = (override_reason or "").strip()
        ly_do_do = (incomplete_reason or "").strip()

        if incomplete and not ly_do_do:
            # Một lượt dở không lý do là một người bệnh mà CSKH không biết phải
            # gọi lại để nói gì. Ràng buộc ở database cũng chặn, nhưng câu từ
            # chối ở đây nói được bằng tiếng người.
            raise ValidationError(
                "Đóng lượt khám dở thì phải ghi vì sao khách về giữa chừng."
            )
        if blockers and not reason and not incomplete:
            # `ly_do_tu_dong` = "đóng đi, và ghi hộ tôi vì sao".
            #
            # Màn CSKH không có ô nhập lý do, nên bắt nó "ghi lý do ngoại lệ" là
            # đưa ra một yêu cầu người dùng không có cách nào đáp ứng — ngõ cụt,
            # không phải chốt (Tuyền chốt 14/08/2026, lần thứ hai).
            #
            # Câu được dựng TỪ CHÍNH `blockers` vừa đọc ở trên, không đọc lại
            # lần nữa: hai lần đọc có thể ra hai kết quả khác nhau, và khi đó
            # cột lý do ghi một danh sách không khớp với thứ thật sự bị vượt.
            if ly_do_tu_dong:
                reason = (
                    ly_do_tu_dong
                    + " Còn vướng: "
                    + "; ".join(str(b["message"]) for b in blockers)
                    + "."
                )
            else:
                raise ValidationError(
                    "Lượt khám còn "
                    + str(len(blockers))
                    + " việc chưa xong. Muốn đóng thì phải ghi lý do ngoại lệ."
                )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # KHÔNG đụng visit.status — đó là khoá hồ sơ bệnh án (xem
                # docstring đầu file). Đóng lượt = hoàn tất bước trong checklist.
                closed = await conn.fetchval(
                    """
                    UPDATE public.work_item
                       SET status = 'COMPLETED', finished_at = now(),
                           -- `work_item_started_when_progressed` đòi started_at
                           -- khi bước rời PENDING. Bước "Đóng lượt" do
                           -- instantiate_visit_workflow tạo sẵn, chưa ai bấm bắt
                           -- đầu, nên started_at còn NULL — đóng thẳng sẽ vi phạm
                           -- ràng buộc. Lấy now() làm mốc bắt đầu: đúng sự thật,
                           -- bước này bắt đầu và kết thúc trong cùng một thao tác
                           -- của Lễ tân.
                           started_at = coalesce(started_at, now()),
                           updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND node_code = $3
                       AND status IN ('PENDING', 'IN_PROGRESS')
                    RETURNING id
                    """,
                    identity.clinic_id,
                    visit_id,
                    CLOSE_NODE,
                )
                # Bệnh nhân rời phòng khám: bỏ con trỏ vị trí để bảng điều phối
                # không còn đếm họ vào hàng đợi nào, và ĐÓNG DẤU MỐC ĐÓNG.
                #
                # `closed_at` không phải để hiển thị. Nó là thứ trigger
                # `update_visit_current_node` đọc để biết đứng yên. Không có nó,
                # một work_item còn sót sẽ kéo bệnh nhân đã về nhà trở lại bảng
                # Trưởng ca — đã xảy ra thật, xem 20260807000003.
                await conn.execute(
                    """
                    UPDATE public.visit
                       SET current_room_id = NULL, current_node_code = $3,
                           current_node_since = now(),
                           closed_at = coalesce(closed_at, now()),
                           closed_by_staff_id = coalesce(
                               closed_by_staff_id, $4::uuid),
                           updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND status <> 'FINALIZED'
                    """,
                    identity.clinic_id,
                    visit_id,
                    CLOSE_NODE,
                    identity.staff_id,
                )

                # HUỶ NHỮNG BƯỚC CÒN TREO — MỌI LẦN ĐÓNG, KHÔNG CHỈ KHI KHÁM DỞ.
                #
                # Câu này trước đây nằm trong nhánh `if incomplete:` bên dưới,
                # nên một lượt đóng bình thường để lại toàn bộ việc chưa xong
                # sống mãi. Đo trên prod 07/08: LUOTKHAM-13 (Đối soát chi phí)
                # và LUOTKHAM-14 (Thanh toán) mỗi mã 23 PENDING và 0 COMPLETED
                # trong suốt đời hệ thống — 23 đầu việc cho những người đã ra về.
                #
                # Bước "Đóng lượt" đã COMPLETED ở câu trên nên không rơi vào đây.
                # Cái gì còn dở đã được chụp lại trong `blockers` của event_log,
                # nên huỷ ở đây không làm mất dấu vết nào.
                # `finished_at` bắt buộc: ràng buộc
                # `work_item_finished_when_terminal` của workflow kernel buộc
                # status ∈ (COMPLETED, SKIPPED, CANCELLED) ⟺ finished_at có giá
                # trị. Bản cũ của câu này (nằm trong nhánh `if incomplete:`)
                # thiếu nó, nên đóng một lượt khám dở CÒN VIỆC TREO sẽ đổ cả
                # giao dịch — chưa lộ ra vì lượt duy nhất đóng theo đường ấy
                # không còn bước nào đang treo.
                #
                # TRỪ VIỆC KẾT QUẢ (15/09/2026). [CHỐT-TUYỀN] "Đóng lượt không
                # xóa nhiệm vụ trả kết quả muộn." Khách ra về không làm kết quả
                # xét nghiệm biến mất: việc nhập kết quả (TKYK) và duyệt kết quả
                # (bác sĩ) vẫn phải có người làm sau đó. Nhận diện bằng
                # `node_definition.flow_group = 'ket_qua'` — nhóm mà danh mục
                # node đã khai, không liệt kê mã cứng ở đây. Việc lấy mẫu chưa
                # làm (flow `dich_vu`) vẫn huỷ: khách về thì mẫu không còn lấy.
                # Các việc kết quả không tự sinh theo khung lượt khám
                # (instantiate_visit_workflow chỉ đi chuỗi LUOTKHAM), nên việc
                # giữ lại luôn là việc có thật, không phải đầu việc rỗng.
                giu_ket_qua = await conn.fetchval(
                    """
                    WITH huy AS (
                        UPDATE public.work_item w
                           SET status = 'CANCELLED',
                               finished_at = coalesce(w.finished_at, now()),
                               updated_at = now()
                         WHERE w.clinic_id = $1::uuid AND w.visit_id = $2::uuid
                           AND w.status IN ('PENDING', 'IN_PROGRESS')
                           AND NOT EXISTS (
                               SELECT 1 FROM public.node_definition n
                                WHERE n.clinic_id = w.clinic_id
                                  AND n.code = w.node_code
                                  AND n.flow_group = 'ket_qua'
                           )
                        RETURNING w.id
                    )
                    SELECT count(*)::int
                      FROM public.work_item w
                      JOIN public.node_definition n
                        ON n.clinic_id = w.clinic_id AND n.code = w.node_code
                     WHERE w.clinic_id = $1::uuid AND w.visit_id = $2::uuid
                       AND w.status IN ('PENDING', 'IN_PROGRESS')
                       AND n.flow_group = 'ket_qua'
                    """,
                    identity.clinic_id,
                    visit_id,
                )
                if incomplete:
                    # Ghi trạng thái khám dở. WHERE giới hạn ở hai trạng thái
                    # ĐANG SỐNG: một hồ sơ đã ký không được kéo ngược về đây.
                    await conn.execute(
                        """
                        UPDATE public.visit
                           SET status = 'INCOMPLETE',
                               incomplete_at = now(),
                               incomplete_reason = $3,
                               incomplete_by = $4::uuid,
                               updated_at = now()
                         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                           AND status IN ('OPEN', 'IN_PROGRESS')
                        """,
                        identity.clinic_id,
                        visit_id,
                        ly_do_do,
                        identity.staff_id,
                    )

                await conn.execute(
                    """
                    INSERT INTO public.event_log
                        (clinic_id, event_type, aggregate_type, aggregate_id,
                         payload, metadata, source, event_published)
                    VALUES ($1::uuid, $5, 'visit', $2::uuid,
                            $3::jsonb, $4::jsonb, 'api:reception', FALSE)
                    """,
                    identity.clinic_id,
                    visit_id,
                    json.dumps(
                        {
                            "to_node": CLOSE_NODE,
                            "reason": reason or None,
                            # Ảnh chụp vướng mắc TẠI THỜI ĐIỂM ĐÓNG. Về sau đọc
                            # lại được: người đóng đã nhìn thấy gì mà vẫn đóng.
                            "blockers": blockers,
                            "override": bool(blockers),
                            "incomplete": incomplete,
                            # Việc kết quả còn mở được GIỮ lại khi đóng lượt.
                            "viec_ket_qua_giu_lai": int(giu_ket_qua or 0),
                            "incomplete_reason": ly_do_do or None,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "actor_auth_user_id": identity.auth_user_id,
                            "clinic_staff_id": identity.staff_id,
                            "clinic_role": identity.role.value,
                            # Vai tài khoản gốc (vai dùng có thể khác).
                            "vai_tai_khoan": identity.vai_goc.value,
                        }
                    ),
                    "visit.closed_incomplete" if incomplete else "dispatch.checkout",
                )

        logger.info(
            "visit_checked_out",
            visit_id=visit_id,
            clinic_id=identity.clinic_id,
            by_staff_id=identity.staff_id,
            override=bool(blockers),
            blocker_count=len(blockers),
        )
        return {
            "ok": True,
            "closed": closed is not None,
            "override": bool(blockers),
            "incomplete": incomplete,
            "viec_ket_qua_giu_lai": int(giu_ket_qua or 0),
        }


def _vn_day_start() -> datetime:
    """Nửa đêm HÔM NAY giờ Việt Nam, dạng datetime CÓ múi giờ.

    Có múi giờ vì `checked_in_at` là timestamptz: một datetime trần sẽ được
    Postgres hiểu theo TimeZone của phiên, và biên ngày lệch bảy tiếng.
    """
    return datetime.now(CLINIC_TZ).replace(hour=0, minute=0, second=0, microsecond=0)


# ── Luật thuần ─────────────────────────────────────────────────────────────


def build_blockers(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Những gì còn vướng, thành câu đọc được.

    Hàm thuần để thử được mọi tổ hợp mà không cần một lượt khám thật — và vì
    đây là chỗ quyết định Lễ tân có được đóng lượt hay không.

    Câu chữ nói VIỆC PHẢI LÀM, không nói tên bảng: *"Còn 2 dịch vụ chưa thực
    hiện xong"* chứ không phải *"service_log.status != DONE"*.
    """
    out: list[dict[str, Any]] = []

    if row.get("svc_open"):
        out.append(
            {
                "type": "service_open",
                "message": f"Còn {row['svc_open']} dịch vụ chưa thực hiện xong",
            }
        )
    if row.get("lab_pending"):
        out.append(
            {
                "type": "lab_pending",
                "message": (
                    f"Còn {row['lab_pending']} kết quả bác sĩ đang chờ để đọc"
                    " (chưa về hoặc chưa chuyển theo dõi)"
                ),
            }
        )
    if row.get("exam_open") and not row.get("lab_pending"):
        out.append(
            {
                "type": "exam_open",
                "message": "Bác sĩ chưa khám hoặc chưa đọc kết quả xong",
            }
        )
    if not row.get("paid_service"):
        out.append({"type": "unpaid_service", "message": "Chưa thu tiền dịch vụ khám"})
    # Chỉ đòi thu tiền thuốc KHI CÓ ĐƠN. Đòi ở mọi lượt sẽ chặn mọi bệnh nhân
    # không được kê thuốc — tức là phần lớn.
    if row.get("has_drug") and not row.get("paid_drug"):
        out.append({"type": "unpaid_drug", "message": "Có đơn thuốc chưa thu tiền"})

    # Vẫn đang đứng ở một phòng. Bước đóng lượt không tính là "đang xử lý".
    node = row.get("current_node_code")
    if node and node != CLOSE_NODE and row.get("room_name"):
        out.append(
            {
                "type": "still_at_station",
                "message": f"Bệnh nhân vẫn đang ở {row['room_name']}",
            }
        )
    return out
