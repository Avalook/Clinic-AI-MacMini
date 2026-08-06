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

  1. dịch vụ đã chỉ định mà chưa thực hiện xong;
  2. kết quả xét nghiệm đang chờ;
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
    -- ① Dịch vụ đã chỉ định mà chưa xong. `status` rỗng nghĩa là chưa ai đụng
    --    tới, nên tính là chưa xong — im lặng bỏ qua sẽ cho đóng lượt còn dở.
    coalesce((SELECT count(*) FROM public.service_log s
               WHERE s.clinic_id = v.clinic_id
                 AND s.visit_link_raw = v.visit_id::text
                 AND coalesce(s.status, '') NOT IN ('DONE', 'COMPLETED',
                                                    'CANCELLED')), 0) AS svc_open,
    -- ② Kết quả xét nghiệm chưa về.
    coalesce((SELECT count(*) FROM public.lab_result l
               WHERE l.clinic_id = v.clinic_id
                 AND l.appointment_id = v.appointment_id
                 AND nullif(btrim(coalesce(l.result_value, '')), '') IS NULL
                 AND nullif(btrim(coalesce(l.external_ref,  '')), '') IS NULL), 0)
                                                               AS lab_pending,
    -- ③ Khoản đã thu, theo nhóm. Bỏ giao dịch đã huỷ.
    EXISTS (SELECT 1 FROM public.payment pm
             WHERE pm.visit_id = v.visit_id AND pm.kind = 'dich_vu'
               AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS paid_service,
    EXISTS (SELECT 1 FROM public.payment pm
             WHERE pm.visit_id = v.visit_id AND pm.kind = 'thuoc'
               AND pm.status = 'PAID' AND pm.voided_at IS NULL) AS paid_drug,
    EXISTS (SELECT 1 FROM public.prescription pr
             WHERE pr.visit_id = v.visit_id)                    AS has_drug
  FROM public.visit v
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN public.clinic_room r ON r.id = v.current_room_id
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $3::uuid
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
                    "blockers": blockers,
                    "can_close": not blockers and not r["already_closed"],
                }
            )
        return out

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
                # không còn đếm họ vào hàng đợi nào.
                await conn.execute(
                    """
                    UPDATE public.visit
                       SET current_room_id = NULL, current_node_code = $3,
                           current_node_since = now(), updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND status <> 'FINALIZED'
                    """,
                    identity.clinic_id,
                    visit_id,
                    CLOSE_NODE,
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
                    # Huỷ những bước còn treo. Không làm thì bảng việc của điều
                    # dưỡng vẫn còn đầu việc cho một người đã ra về.
                    await conn.execute(
                        """
                        UPDATE public.work_item
                           SET status = 'CANCELLED', updated_at = now()
                         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                           AND status IN ('PENDING', 'IN_PROGRESS')
                        """,
                        identity.clinic_id,
                        visit_id,
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
                            "incomplete_reason": ly_do_do or None,
                        },
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        {
                            "actor_auth_user_id": identity.auth_user_id,
                            "clinic_staff_id": identity.staff_id,
                            "clinic_role": identity.role.value,
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
                "message": f"Còn {row['lab_pending']} kết quả xét nghiệm chưa về",
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
