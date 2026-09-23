"""Luồng khám lát 1 — lệnh và bảng làm việc.

Contract: demo-clinicai/docs/handoff/DANH-GIA-THIET-KE-CLAUDE-20260911-v2.md §3.

Luật QUYẾT nằm ở ``luot_kham_rules`` (thuần, test không cần database). File này
đọc, khoá, gọi luật, rồi ghi. Mỗi lệnh chạy trong MỘT transaction và khoá dòng
``visit`` đầu tiên: hai lệnh trên cùng một lượt khám luôn chạy nối tiếp, và thứ
tự khoá cố định (visit → dòng của lệnh) nên không có deadlock chéo.

BIÊN NHẬN NẰM TRONG CÙNG TRANSACTION. Khoá gửi lại (Idempotency-Key) được giữ
bằng advisory lock theo (phòng khám, người gọi, lệnh, khoá), đọc biên nhận, làm
việc, ghi biên nhận, commit — tất cả một lần. Chết giữa chừng thì cả việc lẫn
biên nhận cùng mất; gửi lại thì làm lại từ đầu, không có khoảng hở "đã commit
mà chưa lưu biên nhận" như ``api/idempotency.py`` (S6).

GIỚI HẠN CỦA LÁT 1, nói rõ:
  * Chưa có kết quả theo phiên bản, nên yêu cầu "có kết quả hợp lệ" bị từ chối
    thay vì để vòng đọc kẹt mãi — chỉ nhận "đã làm".
  * Chưa có nhánh kế hoạch trước, huỷ/miễn yêu cầu, rời tạm.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import (
    VAI_LAM_VIEC,
    ClinicRole,
    StaffIdentity,
    mo_quyen_tam_thoi,
)
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import SinhHieuBatDau, SinhHieuDaDo
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services import luot_kham_rules as rules
from clinicai.services.audit import record_event
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

logger = structlog.get_logger()

ORIGIN = "api:luot-kham"

#: Trần số chỉ định trả về cho bảng trưởng ca trong một lần đọc. Có trần là đúng
#: (một ngày hỏng dữ liệu không được kéo sập màn), nhưng cắt mà không báo thì
#: sai — xem `bi_cat` trong `chi_dinh_hom_nay`.
_TRAN_CHI_DINH_HOM_NAY = 500

BOARD_ROLES = frozenset(
    {
        ClinicRole.RECEPTION,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.TRUONG_CA,
        ClinicRole.MANAGEMENT,
    }
)
CHECKIN_ROLES = frozenset({ClinicRole.RECEPTION, ClinicRole.MANAGEMENT})
VITALS_ROLES = frozenset(
    {ClinicRole.NURSE_ULTRASOUND, ClinicRole.RECEPTION, ClinicRole.DOCTOR}
)
DOCTOR_ROLES = frozenset({ClinicRole.DOCTOR})
#: Bấm "Bắt đầu khám" / "Đã khám xong" — bác sĩ, hoặc thư ký đi kèm bác sĩ ấy
#: (Tuyền 16/09/2026: *"check-in check-out cho khách ở từng phòng sẽ do thư ký
#: đi kèm bác sĩ hoặc bác sĩ làm"*). DUYỆT chỉ định vẫn chỉ bác sĩ.
CONSULT_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
NOTE_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.TKYK})
DRAFT_ROLES = frozenset({ClinicRole.TKYK})
DISPATCH_ROLES = frozenset({ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT})
#: Duyệt kết quả + cho phép gửi (Notion v1.0.0: bác sĩ chính & bác sĩ siêu âm/xét
#: nghiệm). Không nới theo công tắc — đây là quyết định chuyên môn.
REVIEW_ROLES = frozenset({ClinicRole.DOCTOR, ClinicRole.ULTRASOUND_DOCTOR})
PERFORMER_ROLES = frozenset(
    {
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
    }
)
#: NGƯỜI ĐI KÈM Ở PHÒNG DỊCH VỤ (Tuyền 17/09/2026): điều dưỡng hoặc thư ký đi
#: cùng bác sĩ thủ thuật / siêu âm GỌI khách, CHECK-IN (Bắt đầu) và CHECK-OUT
#: (Xong) — y như ở bàn khám bác sĩ chính. Chuyên môn vẫn là của bác sĩ: node
#: giữ actor_roles = DOCTOR, và bác sĩ bấm Xong thì được ghi là người thực hiện.
HO_TRO_PHONG = frozenset({ClinicRole.NURSE_ULTRASOUND, ClinicRole.TKYK})
# Ai đọc được nội dung khám (ghi chú, kết quả). Lễ tân và trưởng ca làm việc
# với trạng thái, không cần đọc chữ bác sĩ viết.
CLINICAL_READ_ROLES = frozenset(
    {
        ClinicRole.DOCTOR,
        ClinicRole.TKYK,
        ClinicRole.ULTRASOUND_DOCTOR,
        ClinicRole.NURSE_ULTRASOUND,
    }
)

_CAU_CHAN_DIEU_PHOI = {
    "NO_VALID_ORDER": "Chỉ định này chưa được bác sĩ duyệt — chưa điều phối được.",
    "ORDER_NOT_DISPATCHABLE": "Chỉ định này không còn ở trạng thái điều phối được.",
    "PLAN_NOT_APPLIED": "Kế hoạch trước chưa được áp hợp lệ cho lượt khám này.",
    # KHÔNG CÒN PHÁT từ 23/09/2026 (Tuyền chốt: sinh hiệu không chặn xếp phòng).
    # Giữ lại để đọc được nhật ký cũ — một bản ghi kiểm toán không đọc lại được
    # là một bản ghi vô dụng.
    "VITALS_REQUIRED": (
        "Khách chưa được đo huyết áp — đo sinh hiệu trước khi điều phối."
    ),
    "ROUTE_NOT_DECIDED": "Lượt khám chưa xác định bước tiếp theo.",
    "HELD_UNTIL_ROUND": "Bác sĩ dặn làm dịch vụ này sau khi đọc kết quả vòng trước.",
}

_LIVE = "('done', 'left', 'cancelled')"


class LuotKhamConflictError(ConflictError):
    """409 kèm mã máy đọc được (``error_code``) và câu cho người đọc."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


class LuotKhamValidationError(ValidationError):
    """422 kèm mã — dữ liệu gửi lên tự mâu thuẫn."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = code


#: Những tập vai NỚI ĐƯỢC theo công tắc mở quyền tạm thời. Tập nào KHÔNG có ở
#: đây thì không bao giờ nới: `DOCTOR_ROLES`, `NOTE_ROLES`, `DRAFT_ROLES` là
#: việc của bác sĩ và thư ký cạnh bác sĩ — Tuyền nói rõ "trừ bác sĩ ra thui".
#:
#: `CLINICAL_READ_ROLES` cũng KHÔNG nới: nó quyết định ai đọc được chữ bác sĩ
#: viết trong bệnh án, và đó là đọc hồ sơ y tế chứ không phải thao tác vận hành.
_TAP_NOI_DUOC: tuple[frozenset[ClinicRole], ...] = (
    BOARD_ROLES,
    CHECKIN_ROLES,
    VITALS_ROLES,
    DISPATCH_ROLES,
    PERFORMER_ROLES,
)


def _require(identity: StaffIdentity, roles: frozenset[ClinicRole], cau: str) -> None:
    """Chặn theo vai — và đây là cửa THẬT, cửa ở router chỉ là lớp ngoài.

    Luật nghiệp vụ nằm trong hàm dịch vụ (CLAUDE.md), nên nới `require_role` ở
    router mà quên chỗ này thì vai mới qua được cửa ngoài rồi ăn `SafetyGateError`
    ở cửa trong — đúng cái đã xảy ra chiều 16/09: CSKH và thu ngân vẫn 403 ở
    bảng lượt khám sau khi đã nới router, và cửa gác ở router thì trông hoàn
    toàn đúng.
    """
    # So theo ĐÚNG TẬP (is), không theo giá trị: hai tập khác nghĩa có thể trùng
    # thành phần — PERFORMER_ROLES từ 17/09 trùng khít CLINICAL_READ_ROLES, và so
    # bằng `in` đã nới nhầm quyền đọc bệnh án.
    if mo_quyen_tam_thoi() and any(roles is t for t in _TAP_NOI_DUOC):
        if identity.co_vai(VAI_LAM_VIEC):
            return
    if not identity.co_vai(roles):
        raise SafetyGateError(cau)


def _uuid(value: Any, cau: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(cau) from None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _num(value: Decimal | int | None) -> float | int | None:
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def _cung_ngay_vn(value: datetime) -> bool:
    """Mốc giờ này có thuộc HÔM NAY giờ Việt Nam không."""
    from clinicai.core.clock import now_vn

    return bool(value.astimezone(now_vn().tzinfo).date() == now_vn().date())


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _theo_luat_xep_hang(rows: list[Any]) -> list[Any]:
    """Hàng chờ theo phòng xếp bằng ĐÚNG MỘT luật: ``rules.order_queue``.

    S0-1 (18/09/2026): ``hang_cho`` từng tự viết ORDER BY riêng có chèn
    ``p.uu_tien DESC`` — khách VIP tự nhảy lên đầu, trái luật 15/09 "ưu tiên chỉ
    là nhãn, không tự đổi thứ tự" (COMMENT cột ``patient.uu_tien``). Bảng điều
    phối đã dùng ``order_queue``; nay hàng chờ theo phòng dùng chung, để không
    còn hai bản của một luật. Người đã xong (không thuộc hàng sống) đứng cuối,
    giữ thứ tự SQL như trước.
    """
    views = [
        rules.QueueView(r["id"], r["status"], r["eligible_at"], r["created_at"])
        for r in rows
    ]
    hang = {e.id: i for i, e in enumerate(rules.order_queue(views))}
    return sorted(
        rows,
        key=lambda r: (0, hang[r["id"]]) if r["id"] in hang else (1, 0),
    )


class LuotKhamService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ------------------------------------------------------------------
    # Nền: khoá, biên nhận, hàng chờ, D1, D2
    # ------------------------------------------------------------------

    @staticmethod
    async def _lock_visit(
        conn: asyncpg.Connection,
        clinic_id: str,
        visit_id: str,
        *,
        cho_phep_da_ky: bool = False,
    ) -> asyncpg.Record:
        row = await conn.fetchrow(
            """
            SELECT visit_id::text AS visit_id, status,
                   attending_doctor_id::text AS doctor_id
              FROM visit
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        # INCOMPLETE (khách về giữa chừng) nói riêng một câu: người đứng quầy
        # cần biết khách đã rời đi, không phải "lượt đã đóng" như ký xong.
        if row["status"] == "INCOMPLETE":
            raise LuotKhamConflictError(
                "VISIT_INCOMPLETE", "Khách đã rời phòng khám giữa chừng."
            )
        hop_le = (
            ("OPEN", "IN_PROGRESS", "FINALIZED")
            if cho_phep_da_ky
            else ("OPEN", "IN_PROGRESS")
        )
        if row["status"] not in hop_le:
            raise LuotKhamConflictError("VISIT_CLOSED", "Lượt khám này đã đóng.")
        return row

    @staticmethod
    async def _lock_flow(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> asyncpg.Record:
        await conn.execute(
            """
            INSERT INTO encounter_flow (clinic_id, visit_id)
            VALUES ($1::uuid, $2::uuid)
            ON CONFLICT (visit_id) DO NOTHING
            """,
            clinic_id,
            visit_id,
        )
        row = await conn.fetchrow(
            """
            SELECT vitals_status, plan_check_status, route_decision, content_revision
              FROM encounter_flow
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )
        assert row is not None  # vừa chèn trong cùng transaction
        return row

    @staticmethod
    async def _visit_of(
        conn: asyncpg.Connection, table: str, clinic_id: str, row_id: str
    ) -> str:
        """Lượt khám chứa một phiên khám hoặc một chỉ định — để khoá visit trước."""
        if table == "consultation":
            visit = await conn.fetchval(
                "SELECT visit_id::text FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                row_id,
            )
            cau = "Không tìm thấy phiên khám này."
        else:
            visit = await conn.fetchval(
                "SELECT visit_id::text FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                clinic_id,
                row_id,
            )
            cau = "Không tìm thấy chỉ định này."
        if visit is None:
            raise NotFoundError(cau)
        return str(visit)

    @staticmethod
    async def _receipt_get(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        action: str,
        key: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not key:
            return None
        if not 8 <= len(key) <= 200:
            raise ValidationError("Khoá gửi lại phải dài từ 8 đến 200 ký tự.")
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"{identity.clinic_id}|{identity.staff_id}|{action}|{key}",
        )
        row = await conn.fetchrow(
            """
            SELECT payload_hash, result
              FROM command_receipt
             WHERE clinic_id = $1::uuid AND actor_staff_id = $2::uuid
               AND action = $3 AND idempotency_key = $4
            """,
            identity.clinic_id,
            identity.staff_id,
            action,
            key,
        )
        if row is None:
            return None
        if row["payload_hash"] != _hash(payload):
            raise LuotKhamConflictError(
                "IDEMPOTENCY_KEY_REUSED",
                "Khoá gửi lại này đã dùng cho một yêu cầu khác.",
            )
        result = row["result"]
        loaded = json.loads(result) if isinstance(result, str) else result
        return dict(loaded)

    @staticmethod
    async def _receipt_put(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        action: str,
        key: str | None,
        payload: dict[str, Any],
        target: str,
        result: dict[str, Any],
    ) -> None:
        if not key:
            return
        await conn.execute(
            """
            INSERT INTO command_receipt
                (clinic_id, actor_staff_id, action, idempotency_key,
                 payload_hash, target_ref, result)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid, $7::jsonb)
            """,
            identity.clinic_id,
            identity.staff_id,
            action,
            key,
            _hash(payload),
            target,
            json.dumps(result),
        )

    @staticmethod
    async def _visit_busy(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> bool:
        return bool(
            await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                " AND status = 'serving')",
                clinic_id,
                visit_id,
            )
        )

    @staticmethod
    async def _block_others(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str, serving_id: str
    ) -> None:
        """Khách vào một phòng thì các chỗ chờ khác của khách tạm khoá (I9)."""
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'blocked', updated_at = now(), version = version + 1
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND id <> $3::uuid AND status IN ('waiting', 'called')
            """,
            clinic_id,
            visit_id,
            serving_id,
        )

    @staticmethod
    async def _release_blocked(
        conn: asyncpg.Connection, clinic_id: str, visit_id: str
    ) -> None:
        """Khách rời phòng: chỗ chờ đang khoá mở ra, tính giờ từ BÂY GIỜ.

        ``eligible_at = now()`` là luật "quay lại sau những người đang chờ,
        trước người vào sau" (START-HERE :49), không phải tiện tay.
        """
        await conn.execute(
            """
            UPDATE queue_entry
               SET status = 'waiting', eligible_at = now(),
                   updated_at = now(), version = version + 1
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status = 'blocked'
               AND NOT EXISTS (
                   SELECT 1 FROM queue_entry s
                    WHERE s.clinic_id = $1::uuid AND s.visit_id = $2::uuid
                      AND s.status = 'serving')
            """,
            clinic_id,
            visit_id,
        )

    async def _enqueue(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
        lane: str,
        reason: str,
        ref_id: str,
        doctor_id: str | None = None,
        room_id: str | None = None,
    ) -> None:
        status = rules.initial_queue_status(
            visit_busy=await self._visit_busy(conn, clinic_id, visit_id)
        )
        await conn.execute(
            """
            INSERT INTO queue_entry
                (clinic_id, visit_id, lane, doctor_staff_id, room_id, reason,
                 ref_id, status, eligible_at)
            VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5::uuid, $6, $7::uuid, $8,
                    CASE WHEN $8 = 'waiting' THEN now() END)
            ON CONFLICT (visit_id, reason, ref_id)
                WHERE status NOT IN ('done', 'left', 'cancelled')
            DO NOTHING
            """,
            clinic_id,
            visit_id,
            lane,
            doctor_id,
            room_id,
            reason,
            ref_id,
            status,
        )

    async def _decide_route(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit: asyncpg.Record
    ) -> str | None:
        """D1 — chạy cuối mọi lệnh có thể đổi điều kiện của đích."""
        cid, vid = identity.clinic_id, visit["visit_id"]
        flow = await self._lock_flow(conn, cid, vid)
        new = rules.decide_route(
            vitals_recorded=flow["vitals_status"] == "recorded",
            plan_status=flow["plan_check_status"],
            current_route=flow["route_decision"],
        )
        if new is None:
            return str(flow["route_decision"]) if flow["route_decision"] else None
        await conn.execute(
            """
            UPDATE encounter_flow
               SET route_decision = $3, route_decided_at = now(), route_reason = $4,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND route_decision IS NULL
            """,
            cid,
            vid,
            new,
            "không có kế hoạch trước hợp lệ — vào bác sĩ chính"
            if new == rules.PRIMARY
            else "kế hoạch trước đã áp hợp lệ",
        )
        if new == rules.PRIMARY:
            consultation_id = await conn.fetchval(
                """
                INSERT INTO consultation
                    (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                VALUES ($1::uuid, $2::uuid, 1, 'PRIMARY', 'queued', $3::uuid)
                ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now()
                RETURNING id::text
                """,
                cid,
                vid,
                visit["doctor_id"],
            )
            await self._enqueue(
                conn,
                clinic_id=cid,
                visit_id=vid,
                lane="DOCTOR",
                reason="PRIMARY",
                ref_id=str(consultation_id),
                doctor_id=visit["doctor_id"],
            )
        await record_event(
            conn,
            event_type="visit.routed",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "route": new},
        )
        return new

    @staticmethod
    async def _yeu_cau_cua_vong(
        conn: asyncpg.Connection, clinic_id: str, round_id: str
    ) -> list[asyncpg.Record]:
        """Yêu cầu của một vòng kèm trạng thái THỰC HIỆN và KẾT QUẢ của chỉ định.

        "Kết quả hợp lệ" (Blocker 1):
          - Đối với chỉ định làm bên ngoài (node_definition.lam_ben_ngoai = true):
            BẮT BUỘC phải có ít nhất một tệp kết quả ở trạng thái HOP_LE
            (xác nhận đúng người, đúng chỉ định bởi nhân sự có capability).
            Mốc ket_qua_luc chỉ là mốc tài liệu tới, không làm co_ket_qua = true.
          - Đối với chỉ định nội bộ: giữ nguyên quy tắc ket_qua_luc IS NOT NULL.
        """
        return list(
            await conn.fetch(
                """
                SELECT q.id::text AS id, q.service_order_id::text AS order_id,
                       q.need, q.status, o.exec_status,
                       CASE
                         WHEN coalesce(nd.lam_ben_ngoai, false) THEN
                           EXISTS (
                             SELECT 1 FROM tep_ket_qua t
                              WHERE t.clinic_id = q.clinic_id
                                AND t.service_order_id = o.id
                                AND t.xac_nhan_trang_thai = 'HOP_LE'
                           )
                         ELSE o.ket_qua_luc IS NOT NULL
                       END AS co_ket_qua
                  FROM round_requirement q
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                 WHERE q.clinic_id = $1::uuid AND q.round_id = $2::uuid
                 ORDER BY q.created_at, q.id
                """,
                clinic_id,
                round_id,
            )
        )

    @staticmethod
    def _view(q: asyncpg.Record) -> rules.RequirementView:
        return rules.RequirementView(
            q["order_id"], q["need"], q["status"], q["exec_status"], q["co_ket_qua"]
        )

    async def _evaluate_rounds(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> None:
        """D2 — vòng đọc nào vừa đủ điều kiện thì mở phiên và chỗ chờ, đúng MỘT.

        Vòng mà mọi yêu cầu đều đã được bác sĩ miễn hoặc chuyển theo dõi thì
        KHÔNG cần đọc: đóng luôn, không gọi khách về bác sĩ (FOLLOW_UP không giữ
        lượt chờ). Vòng đang đọc (``in_review``) không bị đụng.
        """
        cid = identity.clinic_id
        rounds = await conn.fetch(
            """
            SELECT id::text AS id, round_no, status
              FROM review_round
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('collecting', 'ready')
             ORDER BY round_no
               FOR UPDATE
            """,
            cid,
            visit_id,
        )
        for rd in rounds:
            views = []
            for q in await self._yeu_cau_cua_vong(conn, cid, rd["id"]):
                view = self._view(q)
                if q["status"] in ("open", "satisfied"):
                    target = (
                        "satisfied"
                        if rules.requirement_state(view) == "satisfied"
                        else "open"
                    )
                    if target != q["status"]:
                        await conn.execute(
                            "UPDATE round_requirement SET status = $3, updated_at ="
                            " now()"
                            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                            cid,
                            q["id"],
                            target,
                        )
                views.append(view)
            if rules.vong_khong_can_doc(views):
                await conn.execute(
                    "UPDATE review_round SET status = 'closed', closed_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                # Vòng đã "sẵn sàng" (khách đang chờ bác sĩ đọc) mà bác sĩ vừa
                # chuyển hết sang theo dõi: bỏ phiên đọc và chỗ chờ của nó.
                await conn.execute(
                    """
                    WITH c AS (
                        UPDATE consultation
                           SET status = 'cancelled', version = version + 1,
                               updated_at = now()
                         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                           AND round_no = $3 AND status = 'queued'
                        RETURNING id
                    )
                    UPDATE queue_entry q
                       SET status = 'cancelled', updated_at = now(),
                           version = q.version + 1
                      FROM c
                     WHERE q.clinic_id = $1::uuid AND q.ref_id = c.id
                       AND q.reason = 'REVIEW'
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                )
                await record_event(
                    conn,
                    event_type="review.skipped",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )
                continue
            ready = rules.round_ready(views)
            if ready and rd["status"] == "collecting":
                await conn.execute(
                    "UPDATE review_round SET status = 'ready', ready_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                doctor = await conn.fetchval(
                    """
                    SELECT coalesce(
                        (SELECT c.doctor_staff_id FROM consultation c
                          WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                            AND c.round_no = 1),
                        (SELECT v.attending_doctor_id FROM visit v
                          WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid))::text
                    """,
                    cid,
                    visit_id,
                )
                consultation_id = await conn.fetchval(
                    """
                    INSERT INTO consultation
                        (clinic_id, visit_id, round_no, kind, status, doctor_staff_id)
                    VALUES ($1::uuid, $2::uuid, $3, 'REVIEW', 'queued', $4::uuid)
                    ON CONFLICT (visit_id, round_no) DO UPDATE SET updated_at = now()
                    RETURNING id::text
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                    doctor,
                )
                await self._enqueue(
                    conn,
                    clinic_id=cid,
                    visit_id=visit_id,
                    lane="DOCTOR",
                    reason="REVIEW",
                    ref_id=str(consultation_id),
                    doctor_id=doctor,
                )
                await record_event(
                    conn,
                    event_type="review.ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )
            elif not ready and rd["status"] == "ready":
                # Lùi trước khi bác sĩ bắt đầu: huỷ chỗ chờ (không để "blocked",
                # vì blocked nghĩa là "khách đang ở phòng khác" và sẽ tự mở).
                await conn.execute(
                    "UPDATE review_round SET status = 'collecting', ready_at = NULL,"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    rd["id"],
                )
                await conn.execute(
                    """
                    UPDATE queue_entry q
                       SET status = 'cancelled', updated_at = now(),
                          version = q.version + 1
                      FROM consultation c
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
                       AND c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                       AND c.round_no = $3 AND q.ref_id = c.id
                       AND q.reason = 'REVIEW'
                       AND q.status IN ('waiting', 'called', 'blocked')
                    """,
                    cid,
                    visit_id,
                    rd["round_no"],
                )
                await record_event(
                    conn,
                    event_type="review.not_ready",
                    aggregate_type="visit",
                    aggregate_id=visit_id,
                    identity=identity,
                    origin=ORIGIN,
                    payload={"visit_id": visit_id, "round_no": rd["round_no"]},
                )

    async def _ket_thuc_neu_xong(
        self, conn: asyncpg.Connection, identity: StaffIdentity, vid: str
    ) -> bool:
        """Khép phần khám của lượt khi rail mới nói không còn gì phải chờ.

        Một chỗ cho mọi lối khép (Slice 1). Trước đây chỉ bấm "khám xong" với
        kết quả NO_SERVICES/DONE mới khép, nên hai ca kẹt thật:
          * bác sĩ đọc xong (DONE) khi còn một chỉ định chưa làm — chỉ định ấy
            làm xong sau đó thì không ai khép lượt, quầy thu tiền chờ mãi;
          * mọi dịch vụ chuyển theo dõi (không mở vòng đọc) — không có phiên
            nào kết thúc bằng DONE nữa.

        Điều kiện: đã có ít nhất một phiên khám xong; không phiên nào đang chờ
        hay đang khám; không vòng đọc nào còn mở; không chỉ định đã duyệt nào
        còn chưa làm. Việc theo dõi (follow_up_case) KHÔNG giữ lượt lại.

        Khép = ``encounter_flow.finished_at`` + lịch hẹn COMPLETED +
        ``visit.exam_completed_at`` (quầy thu tiền và bước đóng lượt đợi mốc
        này). Gọi lại bao nhiêu lần cũng vậy.
        """
        cid = identity.clinic_id
        xong = await conn.fetchval(
            """
            SELECT EXISTS (SELECT 1 FROM consultation c
                            WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                              AND c.status = 'completed')
               AND NOT EXISTS (SELECT 1 FROM consultation c
                                WHERE c.clinic_id = $1::uuid AND c.visit_id = $2::uuid
                                  AND c.status IN ('queued', 'in_progress'))
               AND NOT EXISTS (SELECT 1 FROM review_round r
                                WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
                                  AND r.status <> 'closed')
               AND NOT EXISTS (SELECT 1 FROM service_order o
                                WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                                  AND o.exec_status IN ('authorized', 'assigned',
                                                        'in_progress'))
            """,
            cid,
            vid,
        )
        if not xong:
            return False
        await conn.execute(
            """
            UPDATE encounter_flow f
               SET finished_at = now(), version = f.version + 1, updated_at = now()
             WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid
               AND f.finished_at IS NULL
            """,
            cid,
            vid,
        )
        # BÁC SĨ KHÁM XONG HẲN = lịch hẹn COMPLETED (demo 17/09/2026). Quầy thu
        # tiền và bước đóng lượt đều đợi mốc này.
        hen = await conn.fetchval(
            """
            UPDATE appointment a
               SET status = 'COMPLETED', updated_at = now()
              FROM visit v
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
               AND a.id = v.appointment_id AND a.clinic_id = v.clinic_id
               AND a.status = 'CHECKED_IN'
            RETURNING a.id::text
            """,
            cid,
            vid,
        )
        await conn.execute(
            "UPDATE visit SET exam_completed_at = coalesce("
            "exam_completed_at, now()), updated_at = now()"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND exam_completed_at IS NULL",
            cid,
            vid,
        )
        if hen:
            await record_event(
                conn,
                event_type="appointment.completed",
                aggregate_type="appointment",
                aggregate_id=hen,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "boi": "luot_kham.kham_xong"},
            )
        return True

    async def _mo_theo_doi(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        cau_hinh: dict[str, Any],
        bac_si: str | None,
    ) -> str:
        """Mở (hoặc lấy lại) việc theo dõi ĐANG MỞ của một chỉ định.

        Người phụ trách mặc định là bác sĩ của phiên (người đọc kết quả); hạn
        mặc định theo luật CSKH ``CHO_KQ_XN`` (hiện 3 ngày). Mỗi chỉ định một
        việc đang mở — bấm lại trả về đúng việc cũ.
        """
        cid = identity.clinic_id
        co_san = await conn.fetchval(
            "SELECT id::text FROM follow_up_case WHERE clinic_id = $1::uuid"
            " AND service_order_id = $2::uuid AND status = 'OPEN'",
            cid,
            oid,
        )
        if co_san:
            return str(co_san)
        chu = cau_hinh.get("owner_id") or bac_si or identity.staff_id
        chu = _uuid(chu, "Người phụ trách theo dõi không hợp lệ.")
        la_nhan_vien = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM clinic_membership WHERE clinic_id ="
            " $1::uuid AND staff_id = $2::uuid AND is_active)",
            cid,
            chu,
        )
        if not la_nhan_vien:
            raise ValidationError("Người phụ trách theo dõi không thuộc phòng khám.")
        han = rules.doc_han_theo_doi(cau_hinh.get("han"))
        ly_do_raw = cau_hinh.get("ly_do")
        ly_do = ly_do_raw.strip() if isinstance(ly_do_raw, str) else ""
        o = await conn.fetchrow(
            """
            SELECT o.service_name, v.clinic_patient_id::text AS patient_id
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
            """,
            cid,
            oid,
        )
        assert o is not None
        fid = await conn.fetchval(
            """
            INSERT INTO follow_up_case
                (clinic_id, clinic_patient_id, visit_id, service_order_id, reason,
                 owner_staff_id, owner_role, due_at, created_by)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6::uuid,
                    (SELECT m.role FROM clinic_membership m
                      WHERE m.clinic_id = $1::uuid AND m.staff_id = $6::uuid
                        AND m.is_active ORDER BY m.role LIMIT 1),
                    coalesce($7::date,
                             (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                             + coalesce((SELECT l.so_ngay FROM luat_cskh l
                                          WHERE l.clinic_id = $1::uuid
                                            AND l.loai_viec = 'CHO_KQ_XN'
                                          LIMIT 1), 3))
                        ::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh',
                    $8::uuid)
            RETURNING id::text
            """,
            cid,
            o["patient_id"],
            vid,
            oid,
            ly_do or f"Chờ kết quả {o['service_name']}",
            chu,
            han,
            identity.staff_id,
        )
        await record_event(
            conn,
            event_type="follow_up.opened",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={
                "visit_id": vid,
                "order_id": oid,
                "follow_up_case_id": fid,
                "owner_staff_id": chu,
                # Lý do nằm ở follow_up_case.reason — nhật ký chỉ giữ mã,
                # không giữ chữ (audit.py: "never clinical text").
            },
        )
        return str(fid)

    async def _services(
        self, conn: asyncpg.Connection, clinic_id: str, codes: list[str]
    ) -> list[asyncpg.Record]:
        wanted = [c.strip() for c in codes if isinstance(c, str) and c.strip()]
        if not wanted:
            raise ValidationError("Chưa chọn dịch vụ nào.")
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (s.service_code)
                   s.service_code, s.name, s.node_code
              FROM service_price s
             WHERE s.clinic_id = $1::uuid AND s.active
               AND s.service_code = ANY($2::text[])
             ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
            """,
            clinic_id,
            wanted,
        )
        found = {r["service_code"]: r for r in rows}
        missing = [c for c in wanted if c not in found]
        if missing:
            raise ValidationError("Không có dịch vụ: " + ", ".join(missing) + ".")
        unmapped = [found[c]["name"] for c in wanted if not found[c]["node_code"]]
        if unmapped:
            raise LuotKhamConflictError(
                "SERVICE_NOT_MAPPED",
                "Dịch vụ chưa gắn với bước thực hiện: " + ", ".join(unmapped) + ".",
            )
        return [found[c] for c in wanted]

    async def _cap_nhat_vi_tri(
        self, conn: asyncpg.Connection, cid: str, vid: str
    ) -> None:
        """Đặt con trỏ "khách đang ở đâu" (visit.current_node_code/room) theo
        hàng chờ của luồng khám mới.

        Bảng điều phối của trưởng ca, TV phòng chờ và bước đóng lượt đều đọc con
        trỏ này, mà luồng khám mới chưa từng dời nó: demo 17/09/2026 khám xong
        cả vòng rồi mà trưởng ca vẫn thấy khách "đang ở Đo chỉ số", và quầy
        không đóng được lượt.

        Đang được phục vụ ở đâu → ở đó; không thì chỗ đang gọi/đang chờ sớm nhất.
        Chỉ còn chỗ bị chặn (chờ kết quả) → giữ nguyên. Hết mọi chỗ → bước đóng
        lượt ở quầy tiếp đón.
        """
        r = await conn.fetchrow(
            """
            SELECT coalesce(
                       q.room_id,
                       (SELECT vt.room_id
                          FROM work_roster w
                          JOIN vi_tri_lam_viec vt
                            ON vt.clinic_id = w.clinic_id AND vt.code = w.station
                         WHERE w.clinic_id = q.clinic_id
                           AND w.staff_id = coalesce(q.doctor_staff_id,
                                                     c.doctor_staff_id)
                           AND w.status <> 'REJECTED'
                           AND vt.room_id IS NOT NULL
                           AND w.work_date
                               = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                         ORDER BY vt.sort
                         LIMIT 1)
                   ) AS room_id,
                   coalesce(
                       o.node_code,
                       -- Bàn khám chưa rõ phòng (bác sĩ không có ca xếp phòng):
                       -- vẫn nói được khách đang ở bước KHÁM loại nào.
                       CASE WHEN q.reason <> 'SERVICE' THEN
                           CASE st.form_code
                               WHEN 'NT' THEN 'KHAM-NOITIET'
                               WHEN 'PK' THEN 'KHAM-PHUKHOA'
                               WHEN 'SK' THEN 'KHAM-SANKHOA'
                               WHEN 'NK' THEN 'KHAM-NAMKHOA'
                               WHEN 'HMVS' THEN 'KHAM-HIEMMUON-VOSINH'
                           END
                       END
                   ) AS node_code
              FROM queue_entry q
              JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
              LEFT JOIN service_type st ON st.id = v.service_type_id
              LEFT JOIN consultation c
                ON c.id = q.ref_id AND q.reason <> 'SERVICE'
               AND c.clinic_id = q.clinic_id
              LEFT JOIN service_order o
                ON o.id = q.ref_id AND q.reason = 'SERVICE'
               AND o.clinic_id = q.clinic_id
             WHERE q.clinic_id = $1::uuid AND q.visit_id = $2::uuid
               AND q.status IN ('serving', 'called', 'waiting')
             ORDER BY CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                      ELSE 2 END,
                      coalesce(q.eligible_at, q.created_at)
             LIMIT 1
            """,
            cid,
            vid,
        )
        if r is not None:
            room_id = r["room_id"]
            node = r["node_code"] or (
                await conn.fetchval(
                    "SELECT node_code FROM clinic_room WHERE id = $1::uuid",
                    room_id,
                )
                if room_id
                else None
            )
        else:
            con_mo = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND status NOT IN ('done', 'left',"
                " 'cancelled'))",
                cid,
                vid,
            )
            if con_mo:
                return
            node = "LUOTKHAM-15"
            room_id = await conn.fetchval(
                "SELECT id FROM clinic_room WHERE clinic_id = $1::uuid"
                " AND node_code = 'LUOTKHAM-01' AND is_active ORDER BY sort LIMIT 1",
                cid,
            )
        # node rỗng (chưa suy ra được bước) vẫn ghi: để trống còn hơn trỏ vào
        # phòng khách đã rời — trưởng ca đọc "đang ở Siêu âm" sai thì điều sai.
        await conn.execute(
            """
            UPDATE visit
               SET previous_node_code = CASE
                       WHEN current_node_code IS DISTINCT FROM $3
                       THEN current_node_code ELSE previous_node_code END,
                   current_node_since = CASE
                       WHEN current_node_code IS DISTINCT FROM $3
                         OR current_room_id IS DISTINCT FROM $4::uuid
                       THEN now() ELSE current_node_since END,
                   current_node_code = $3,
                   current_room_id = $4::uuid,
                   updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND status IN ('OPEN', 'IN_PROGRESS')
            """,
            cid,
            vid,
            node,
            room_id,
        )

    async def _thu_ky_cua_bac_si(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        doctor_id: str | None,
    ) -> None:
        """Thư ký chỉ bấm được cho khách của bác sĩ mình đi kèm."""
        if not identity.co_vai({ClinicRole.TKYK}):
            return
        ds = await bac_si_cua_thu_ky(conn, identity)
        if ds is not None and (doctor_id is None or doctor_id not in ds):
            raise SafetyGateError(
                "Khách này của bác sĩ khác — thư ký chỉ làm cho bác sĩ mình đi kèm."
            )

    async def _cung_ekip(
        self, conn: asyncpg.Connection, identity: StaffIdentity, c: asyncpg.Record
    ) -> bool:
        """Người gọi thuộc ê-kíp của phiên: chính bác sĩ, hoặc thư ký của bác sĩ ấy."""
        if identity.co_vai({ClinicRole.DOCTOR}):
            return bool(c["doctor_id"] == identity.staff_id)
        if identity.co_vai({ClinicRole.TKYK}):
            ds = await bac_si_cua_thu_ky(conn, identity)
            return ds is None or c["doctor_id"] in ds
        return False

    async def _consultation_in_progress(
        self, conn: asyncpg.Connection, clinic_id: str, consultation_id: str
    ) -> asyncpg.Record:
        c = await conn.fetchrow(
            """
            SELECT id::text AS id, visit_id::text AS visit_id, round_no, kind,
                   status, started_by::text AS started_by,
                   doctor_staff_id::text AS doctor_id
              FROM consultation
             WHERE clinic_id = $1::uuid AND id = $2::uuid
               FOR UPDATE
            """,
            clinic_id,
            consultation_id,
        )
        if c is None:
            raise NotFoundError("Không tìm thấy phiên khám này.")
        if c["status"] != "in_progress":
            raise LuotKhamConflictError(
                "CONSULTATION_NOT_IN_PROGRESS",
                "Phiên khám chưa bắt đầu hoặc đã kết thúc.",
            )
        return c

    # ------------------------------------------------------------------
    # Bảng làm việc
    # ------------------------------------------------------------------

    async def bang(self, *, identity: StaffIdentity) -> dict[str, Any]:
        _require(identity, BOARD_ROLES, "Vai của bạn không dùng màn lượt khám.")
        cid = identity.clinic_id
        doc_noi_dung = identity.co_vai(CLINICAL_READ_ROLES)
        async with self._pool.acquire() as conn:
            visits = await conn.fetch(
                """
                SELECT v.visit_id::text AS visit_id, v.checked_in_at,
                       v.attending_doctor_id::text AS doctor_id,
                       p.full_name, p.patient_code, d.full_name AS doctor_name,
                       f.vitals_status, f.route_decision, f.finished_at,
                       f.goi_do_luc, g.full_name AS goi_do_boi,
                       f.vitals_started_at, bd.full_name AS vitals_started_by,
                       ap.so_tiep_don, ap.so_booking
                  FROM visit v
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN encounter_flow f
                    ON f.visit_id = v.visit_id AND f.clinic_id = v.clinic_id
                  LEFT JOIN staff g ON g.id = f.goi_do_boi
                  LEFT JOIN staff bd ON bd.id = f.vitals_started_by
                  LEFT JOIN appointment ap
                    ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
                 WHERE v.clinic_id = $1::uuid
                   -- INCOMPLETE cố ý không hiện: khách đã về.
                   AND v.status IN ('OPEN', 'IN_PROGRESS')
                   AND v.checked_in_at IS NOT NULL
                   AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   -- Thư ký chỉ thấy lượt của bác sĩ mình (20260915000020).
                   AND coalesce(v.attending_doctor_id::text, '~')
                       = ANY(coalesce(
                             $2::text[],
                             ARRAY[coalesce(v.attending_doctor_id::text, '~')]))
                 ORDER BY v.checked_in_at, v.visit_id
                """,
                cid,
                await bac_si_cua_thu_ky(conn, identity),
            )
            ids = [r["visit_id"] for r in visits]
            vitals: list[asyncpg.Record] = []
            phien: list[asyncpg.Record] = []
            ghi_chu: list[asyncpg.Record] = []
            chi_dinh: list[asyncpg.Record] = []
            hang_cho: list[asyncpg.Record] = []
            vong: list[asyncpg.Record] = []
            yeu_cau: list[asyncpg.Record] = []
            if ids:
                vitals = await conn.fetch(
                    """
                    SELECT DISTINCT ON (m.visit_id)
                           m.visit_id::text AS visit_id, m.systolic, m.diastolic,
                           m.pulse, m.temperature, m.weight_kg, m.height_cm,
                           m.respiratory_rate, m.spo2, m.bmi, m.pain_score,
                           m.created_at, s.full_name AS recorded_by_name
                      FROM vital_measurement m
                      LEFT JOIN staff s ON s.id = m.recorded_by
                     WHERE m.clinic_id = $1::uuid AND m.visit_id = ANY($2::uuid[])
                     ORDER BY m.visit_id, m.created_at DESC
                    """,
                    cid,
                    ids,
                )
                phien = await conn.fetch(
                    """
                    SELECT c.id::text AS id, c.visit_id::text AS visit_id, c.round_no,
                           c.kind, c.status, c.outcome,
                           c.doctor_staff_id::text AS doctor_id,
                           c.started_by::text AS started_by
                      FROM consultation c
                     WHERE c.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                     ORDER BY c.visit_id, c.round_no
                    """,
                    cid,
                    ids,
                )
                if doc_noi_dung:
                    ghi_chu = await conn.fetch(
                        """
                        SELECT n.consultation_id::text AS consultation_id, n.body,
                               n.created_at, s.full_name AS recorded_by_name
                          FROM consultation_note n
                          JOIN consultation c
                            ON c.id = n.consultation_id AND c.clinic_id = n.clinic_id
                          LEFT JOIN staff s ON s.id = n.recorded_by
                         WHERE n.clinic_id = $1::uuid AND c.visit_id = ANY($2::uuid[])
                         ORDER BY n.created_at
                        """,
                        cid,
                        ids,
                    )
                chi_dinh = await conn.fetch(
                    """
                    SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                           o.consultation_id::text AS consultation_id,
                           o.service_code, o.service_name, o.node_code, o.exec_status,
                           o.room_id::text AS room_id, r.name AS room_name,
                           o.hold_until_round, o.version, o.result_note,
                           o.not_performed_reason,
                           rec.full_name AS recorded_by_name,
                           au.full_name AS authorized_by_name,
                           pf.full_name AS performed_by_name,
                           coalesce(nd.lam_ben_ngoai, false) AS doi_tac,
                           o.ket_qua_luc, o.doi_tac_cho_tai_lieu_luc,
                           o.selection_status, o.execution_status,
                           o.routing_revision,
                           lam.started_at AS lam_bat_dau_luc,
                           lam.ended_at AS lam_xong_luc,
                           lam.status AS lam_trang_thai,
                           lam.phong AS lam_phong
                      FROM service_order o
                      LEFT JOIN node_definition nd
                        ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                      LEFT JOIN clinic_room r
                        ON r.id = o.room_id AND r.clinic_id = o.clinic_id
                      -- GIỜ CỦA PHÒNG (luồng chuẩn bước 8, 23/09/2026): bác sĩ
                      -- chính thấy dịch vụ đang làm ở đâu, bắt đầu/xong lúc nào —
                      -- nối thẳng tới lần làm gần nhất mà phòng đã bấm.
                      LEFT JOIN LATERAL (
                          SELECT a.started_at,
                                 coalesce(a.completed_at, a.interrupted_at) AS ended_at,
                                 a.status, ar.name AS phong
                            FROM service_execution_attempt a
                            LEFT JOIN clinic_room ar
                              ON ar.id = a.room_id_snapshot
                             AND ar.clinic_id = a.clinic_id
                           WHERE a.clinic_id = o.clinic_id
                             AND a.service_order_id = o.id
                           ORDER BY a.attempt_no DESC
                           LIMIT 1
                      ) lam ON true
                      LEFT JOIN staff rec ON rec.id = o.recorded_by
                      LEFT JOIN staff au ON au.id = o.authorized_by
                      LEFT JOIN staff pf ON pf.id = o.performed_by
                     WHERE o.clinic_id = $1::uuid AND o.visit_id = ANY($2::uuid[])
                       AND (o.exec_status <> 'draft' OR $3::boolean)
                     ORDER BY o.created_at, o.id
                    """,
                    cid,
                    ids,
                    identity.co_vai(NOTE_ROLES),
                )
                hang_cho = await conn.fetch(
                    """
                    SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.lane,
                           q.reason, q.ref_id::text AS ref_id, q.status,
                           q.eligible_at, q.created_at,
                           q.room_id::text AS room_id,
                           q.doctor_staff_id::text AS doctor_id
                      FROM queue_entry q
                     WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
                       AND q.status NOT IN ('done', 'left', 'cancelled')
                    """,
                    cid,
                    ids,
                )
                vong = await conn.fetch(
                    """
                    SELECT r.id::text AS id, r.visit_id::text AS visit_id,
                           r.round_no, r.status
                      FROM review_round r
                     WHERE r.clinic_id = $1::uuid AND r.visit_id = ANY($2::uuid[])
                     ORDER BY r.visit_id, r.round_no
                    """,
                    cid,
                    ids,
                )
                if vong:
                    yeu_cau = await conn.fetch(
                        """
                        SELECT q.round_id::text AS round_id,
                               q.service_order_id::text AS order_id, q.need, q.status
                          FROM round_requirement q
                         WHERE q.clinic_id = $1::uuid AND q.round_id = ANY($2::uuid[])
                        """,
                        cid,
                        [r["id"] for r in vong],
                    )
            phong = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active AND r.accepting
                 GROUP BY r.id, r.code, r.name, r.sort
                 ORDER BY r.sort, r.code
                """,
                cid,
            )
            dich_vu = await conn.fetch(
                """
                SELECT DISTINCT ON (s.service_code)
                       s.service_code, s.name, s.node_code, n.actor_roles
                  FROM service_price s
                  JOIN node_definition n
                    ON n.clinic_id = s.clinic_id AND n.code = s.node_code
                 WHERE s.clinic_id = $1::uuid AND s.active
                   AND s.node_code LIKE 'DICHVU-%'
                 ORDER BY s.service_code, (s."group" = 'dich_vu') DESC
                """,
                cid,
            )
            lich: list[asyncpg.Record] = []
            if identity.co_vai(CHECKIN_ROLES):
                lich = await conn.fetch(
                    """
                    SELECT a.id::text AS id, a.slot_start, a.status,
                           p.full_name, p.patient_code, d.full_name AS doctor_name
                      FROM appointment a
                      JOIN patient p
                        ON p.clinic_patient_id = a.clinic_patient_id
                       AND p.clinic_id = a.clinic_id
                      LEFT JOIN staff d ON d.id = a.doctor_id
                     WHERE a.clinic_id = $1::uuid
                       AND a.status IN ('SCHEDULED', 'CSKH_CONFIRMED', 'CONFIRMED')
                       AND (a.slot_start AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                     ORDER BY a.slot_start, a.id
                    """,
                    cid,
                )

        by_visit: dict[str, dict[str, Any]] = {}
        for v in visits:
            by_visit[v["visit_id"]] = {
                "visit_id": v["visit_id"],
                "ma_bn": v["patient_code"],
                "ten": v["full_name"],
                "bac_si_id": v["doctor_id"],
                "bac_si": v["doctor_name"],
                "check_in_luc": _iso(v["checked_in_at"]),
                "sinh_hieu_trang_thai": v["vitals_status"] or "pending",
                # Mốc [Bắt đầu] đo — trạng thái "đang đo" đọc từ ĐÂY và từ
                # `sinh_hieu_trang_thai`, không còn suy từ giờ gọi.
                "bat_dau_do_luc": _iso(v["vitals_started_at"]),
                "bat_dau_do_boi": v["vitals_started_by"],
                # DỮ LIỆU CŨ: giữ để lượt trước 23/09 còn đọc được giờ gọi.
                # Màn Đo sinh hiệu KHÔNG dùng nó làm trạng thái nữa.
                "goi_do_luc": _iso(v["goi_do_luc"]),
                "goi_do_boi": v["goi_do_boi"],
                "so_tiep_don": v["so_tiep_don"],
                "so_booking": v.get("so_booking"),
                "dich": v["route_decision"],
                "ket_thuc_luc": _iso(v["finished_at"]),
                "sinh_hieu": None,
                "phien": [],
                "chi_dinh": [],
                "hang_cho": [],
                "vong": [],
            }
        for m in vitals:
            by_visit[m["visit_id"]]["sinh_hieu"] = {
                "tam_thu": m["systolic"],
                "tam_truong": m["diastolic"],
                "mach": m["pulse"],
                "nhiet_do": _num(m["temperature"]),
                "can_nang": _num(m["weight_kg"]),
                "chieu_cao": _num(m["height_cm"]),
                "nhip_tho": m["respiratory_rate"],
                "spo2": m["spo2"],
                "bmi": _num(m["bmi"]),
                "muc_do_dau": m["pain_score"],
                "luc": _iso(m["created_at"]),
                "nguoi_do": m["recorded_by_name"],
            }
        notes_by: dict[str, list[dict[str, Any]]] = {}
        for n in ghi_chu:
            notes_by.setdefault(n["consultation_id"], []).append(
                {
                    "noi_dung": n["body"],
                    "nguoi_ghi": n["recorded_by_name"],
                    "luc": _iso(n["created_at"]),
                }
            )
        for c in phien:
            by_visit[c["visit_id"]]["phien"].append(
                {
                    "id": c["id"],
                    "vong": c["round_no"],
                    "loai": c["kind"],
                    "trang_thai": c["status"],
                    "ket_qua": c["outcome"],
                    "bac_si_id": c["doctor_id"],
                    "nguoi_bat_dau_id": c["started_by"],
                    "ghi_chu": notes_by.get(c["id"], []),
                }
            )
        for o in chi_dinh:
            by_visit[o["visit_id"]]["chi_dinh"].append(
                {
                    "id": o["id"],
                    "phien_id": o["consultation_id"],
                    "ma_dich_vu": o["service_code"],
                    "ten_dich_vu": o["service_name"],
                    "node": o["node_code"],
                    "trang_thai": o["exec_status"],
                    "phong_id": o["room_id"],
                    "phong": o["room_name"],
                    "giu_toi_vong": o["hold_until_round"],
                    "version": o["version"],
                    "nguoi_ghi": o["recorded_by_name"],
                    "nguoi_duyet": o["authorized_by_name"],
                    "nguoi_lam": o["performed_by_name"],
                    "ket_qua": o["result_note"] if doc_noi_dung else None,
                    "ly_do_khong_lam": o["not_performed_reason"],
                    # Lần làm gần nhất ở phòng: bắt đầu/xong lúc nào, ở phòng
                    # nào (có thể khác phòng được xếp nếu lễ tân đã đổi).
                    "lam_bat_dau_luc": _iso(o.get("lam_bat_dau_luc")),
                    "lam_xong_luc": _iso(o.get("lam_xong_luc")),
                    "lam_trang_thai": o.get("lam_trang_thai"),
                    "lam_phong": o.get("lam_phong"),
                    "routing_revision": o.get("routing_revision"),
                    "doi_phong_duoc": rules.doi_phong_duoc(
                        selection_status=o.get("selection_status"),
                        execution_status=o.get("execution_status"),
                        exec_status=o["exec_status"],
                        doi_tac=bool(o["doi_tac"]),
                    ),
                    # Việc gửi đối tác: không phòng nào của phòng khám xếp được,
                    # màn hình nói trạng thái ĐỐI TÁC thay vì "chờ xếp phòng".
                    "doi_tac": o["doi_tac"],
                    "trang_thai_doi_tac": (
                        trang_thai_doi_tac(
                            exec_status=o["exec_status"],
                            cho_tai_lieu=o["doi_tac_cho_tai_lieu_luc"] is not None,
                            co_ket_qua=o["ket_qua_luc"] is not None,
                        )
                        if o["doi_tac"]
                        else None
                    ),
                }
            )
        views = [
            rules.QueueView(q["id"], q["status"], q["eligible_at"], q["created_at"])
            for q in hang_cho
        ]
        order = {e.id: i for i, e in enumerate(rules.order_queue(views))}
        for q in sorted(hang_cho, key=lambda x: order.get(x["id"], 0)):
            by_visit[q["visit_id"]]["hang_cho"].append(
                {
                    "id": q["id"],
                    "hang": q["lane"],
                    "ly_do": q["reason"],
                    "ref_id": q["ref_id"],
                    "trang_thai": q["status"],
                    "du_dieu_kien_luc": _iso(q["eligible_at"]),
                    "phong_id": q["room_id"],
                    "bac_si_id": q["doctor_id"],
                }
            )
        req_by: dict[str, list[dict[str, Any]]] = {}
        for q in yeu_cau:
            req_by.setdefault(q["round_id"], []).append(
                {
                    "chi_dinh_id": q["order_id"],
                    "can": q["need"],
                    "trang_thai": q["status"],
                }
            )
        for r in vong:
            by_visit[r["visit_id"]]["vong"].append(
                {
                    "id": r["id"],
                    "vong": r["round_no"],
                    "trang_thai": r["status"],
                    "yeu_cau": req_by.get(r["id"], []),
                }
            )
        return {
            "vai": identity.role.value,
            "toi": identity.staff_id,
            "luot": list(by_visit.values()),
            "phong": [
                {
                    "id": p["id"],
                    "ma": p["code"],
                    "ten": p["name"],
                    "nodes": list(p["nodes"]),
                }
                for p in phong
            ],
            "dich_vu": [
                {
                    "ma": s["service_code"],
                    "ten": s["name"],
                    "node": s["node_code"],
                    "vai_lam": list(s["actor_roles"] or []),
                }
                for s in dich_vu
            ],
            "lich_cho_check_in": [
                {
                    "id": a["id"],
                    "gio": _iso(a["slot_start"]),
                    "ten": a["full_name"],
                    "ma_bn": a["patient_code"],
                    "bac_si": a["doctor_name"],
                }
                for a in lich
            ],
        }

    # ------------------------------------------------------------------
    # C0 — check-in: dùng lại đúng máy trạng thái đang chạy
    # ------------------------------------------------------------------

    async def phong_hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Phòng mà người gọi đứng trong lịch HÔM NAY — mỗi phòng một hàng chờ."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT r.id::text AS id, r.code, r.name, r.floor, r.sort,
                       array_agg(DISTINCT w.station) AS vi_tri,
                       array_agg(DISTINCT rn.node_code) AS nodes
                  FROM work_roster w
                  JOIN vi_tri_lam_viec v
                    ON v.clinic_id = w.clinic_id AND v.code = w.station
                  JOIN clinic_room r
                    ON r.id = v.room_id AND r.clinic_id = w.clinic_id AND r.is_active
                  LEFT JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE w.clinic_id = $1::uuid AND w.staff_id = $2::uuid
                   AND w.status <> 'REJECTED'
                   AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
                identity.staff_id,
            )
            tat_ca = await conn.fetch(
                """
                SELECT r.id::text AS id, r.code, r.name, r.floor,
                       array_agg(rn.node_code ORDER BY rn.node_code) AS nodes
                  FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.is_active
                 GROUP BY r.id, r.code, r.name, r.floor, r.sort
                 ORDER BY r.sort, r.code
                """,
                identity.clinic_id,
            )
        return {
            "phong_cua_toi": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "vi_tri": list(r["vi_tri"] or []),
                    "nodes": [n for n in (r["nodes"] or []) if n],
                }
                for r in rows
            ],
            "tat_ca_phong": [
                {
                    "id": r["id"],
                    "code": r["code"],
                    "ten": r["name"],
                    "tang": r["floor"],
                    "nodes": list(r["nodes"] or []),
                }
                for r in tat_ca
            ],
        }

    async def hang_cho(
        self,
        *,
        identity: StaffIdentity,
        room_id: str | None,
    ) -> dict[str, Any]:
        """HÀNG CHỜ của một phòng: ai đang chờ, ai đang trong phòng, ai đã xong.

        Tuyền 16/09/2026: *"sẽ luôn có 1 danh sách các khách đang xếp hàng, sau đó
        bác sĩ chọn rồi ấn bắt đầu khám cho người đó, rồi điền thông tin bên
        trong, khám xong thì ghi đã khám xong — vậy là check-out cho khách ở
        phòng đó"*.

        Một phòng có hai loại chỗ chờ:
          * chỉ định xếp vào phòng (siêu âm, lấy mẫu, thủ thuật) — theo `room_id`;
          * lượt khám chính của BÁC SĨ đứng phòng ấy hôm nay — khám chính chờ theo
            bác sĩ, không theo phòng, nên phải tra lịch để biết bác sĩ nào.

        THỨ TỰ: giờ vào hàng chờ, tức giờ đo sinh hiệu xong hoặc giờ được chỉ
        định; số thứ tự trong ngày là thứ tự CHECK-IN, như phiếu lễ tân phát.
        """
        _require(identity, BOARD_ROLES, "Vai của bạn không dùng hàng chờ phòng.")
        cid = identity.clinic_id
        doc_noi_dung = identity.co_vai(CLINICAL_READ_ROLES)
        rid = _uuid(room_id, "Mã phòng không hợp lệ.") if room_id else None
        async with self._pool.acquire() as conn:
            phong = None
            if rid is not None:
                phong = await conn.fetchrow(
                    """
                    SELECT r.id::text AS id, r.code, r.name, r.floor,
                           array_agg(rn.node_code) AS nodes
                      FROM clinic_room r
                      LEFT JOIN clinic_room_node rn
                        ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                     WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                     GROUP BY r.id
                    """,
                    cid,
                    rid,
                )
                if phong is None:
                    raise NotFoundError("Không tìm thấy phòng này.")
            # Bác sĩ có lượt khám chính trong hàng chờ này.
            if rid is not None:
                bac_si = await conn.fetch(
                    """
                    SELECT DISTINCT w.staff_id::text AS id
                      FROM work_roster w
                      JOIN vi_tri_lam_viec v
                        ON v.clinic_id = w.clinic_id AND v.code = w.station
                      JOIN clinic_membership m
                        ON m.staff_id = w.staff_id AND m.clinic_id = w.clinic_id
                       AND m.is_active AND m.role = 'DOCTOR'
                     WHERE w.clinic_id = $1::uuid AND v.room_id = $2::uuid
                       AND w.status <> 'REJECTED'
                       AND w.work_date = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                    """,
                    cid,
                    rid,
                )
                ds_bac_si = [r["id"] for r in bac_si]
            else:
                ds_bac_si = []
            so_bac_si_trong_phong = len(ds_bac_si)
            # "Khách của tôi" (không chọn phòng) cho người ĐIỀU PHỐI hoặc thư ký
            # chưa bị giới hạn theo bác sĩ: thấy lượt khám chính của MỌI bác sĩ.
            # Bản trước trả rỗng cho thư ký ở chế độ mở quyền — thư ký mở Bàn khám
            # mà không thấy ai (tự kiểm 16/09/2026).
            tat_ca_bac_si = False
            if identity.co_vai({ClinicRole.DOCTOR}):
                ds_bac_si = sorted({*ds_bac_si, identity.staff_id})
            if identity.co_vai({ClinicRole.TKYK}):
                cua_toi = await bac_si_cua_thu_ky(conn, identity)
                if cua_toi is not None:
                    ds_bac_si = sorted(
                        {*ds_bac_si, *cua_toi} if rid is None else cua_toi
                    )
                elif rid is None:
                    tat_ca_bac_si = True
            if rid is None and identity.co_vai(
                {ClinicRole.TRUONG_CA, ClinicRole.MANAGEMENT}
            ):
                tat_ca_bac_si = True
            rows = await conn.fetch(
                """
                WITH stt AS (
                    SELECT v.visit_id,
                           row_number() OVER (ORDER BY v.checked_in_at, v.visit_id)
                               AS so
                      FROM visit v
                     WHERE v.clinic_id = $1::uuid AND v.checked_in_at IS NOT NULL
                       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                )
                SELECT q.id::text AS id, q.status, q.lane, q.reason,
                       q.ref_id::text AS ref_id, q.visit_id::text AS visit_id,
                       q.eligible_at, q.called_at, q.serving_at, q.done_at,
                       q.created_at,
                       stt.so AS so_thu_tu,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code, p.uu_tien, p.uu_tien_ly_do,
                       v.appointment_id::text AS appointment_id,
                       v.checked_in_at,
                       st.name AS dich_vu_kham, st.form_code,
                       d.full_name AS bac_si,
                       coalesce(o.service_name, st.name) AS viec,
                       o.service_code, o.node_code, o.exec_status,
                       o.result_note, o.ket_qua_luc, o.duyet_luc,
                       o.not_performed_reason, pf.full_name AS nguoi_lam,
                       v.status AS visit_status, v.finalized_at,
                       fb.full_name AS nguoi_ky,
                       c.status AS phien_status, c.kind AS phien_kind,
                       r.name AS phong
                  FROM queue_entry q
                  JOIN visit v ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id
                  JOIN stt ON stt.visit_id = q.visit_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN service_type st ON st.id = v.service_type_id
                  LEFT JOIN staff d
                    ON d.id = coalesce(q.doctor_staff_id, v.attending_doctor_id)
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN clinic_room r ON r.id = q.room_id
                  LEFT JOIN staff pf ON pf.id = o.performed_by
                  LEFT JOIN staff fb ON fb.id = v.finalized_by
                 WHERE q.clinic_id = $1::uuid
                   AND q.status IN ('blocked', 'waiting', 'called', 'serving', 'done')
                   AND (
                        ($2::uuid IS NOT NULL AND q.lane = 'ROOM'
                             AND q.room_id = $2::uuid)
                     OR (q.lane = 'DOCTOR'
                             AND ($4::boolean
                                  OR q.doctor_staff_id::text = ANY($3::text[])
                                  -- Khách CHƯA có bác sĩ (lịch hẹn không gắn
                                  -- bác sĩ): hiện ở mọi hàng chờ khám có bác sĩ,
                                  -- ai bấm Bắt đầu khám thì nhận. Bản trước khách
                                  -- này không nằm trong hàng chờ của AI cả (tự
                                  -- kiểm 16/09/2026).
                                  OR (q.doctor_staff_id IS NULL
                                      AND cardinality($3::text[]) > 0)))
                   )
                 ORDER BY
                   CASE q.status WHEN 'serving' THEN 0 WHEN 'called' THEN 1
                        WHEN 'waiting' THEN 2 WHEN 'blocked' THEN 3 ELSE 4 END,
                   coalesce(q.eligible_at, q.created_at), q.id
                """,
                cid,
                rid,
                ds_bac_si,
                tat_ca_bac_si,
            )
        now_rows = [
            {
                "id": r["id"],
                "trang_thai": r["status"],
                "loai": "KHAM" if r["reason"] != "SERVICE" else "DICH_VU",
                "ref_id": r["ref_id"],
                "visit_id": r["visit_id"],
                "clinic_patient_id": r["clinic_patient_id"],
                "appointment_id": r["appointment_id"],
                "so_thu_tu": int(r["so_thu_tu"]),
                "ten": r["full_name"],
                "ma_bn": r["patient_code"],
                "uu_tien": bool(r["uu_tien"]),
                "uu_tien_ly_do": r["uu_tien_ly_do"],
                "viec": r["viec"],
                "dich_vu_kham": r["dich_vu_kham"],
                "form_code": r["form_code"],
                "service_code": r["service_code"],
                "node_code": r["node_code"],
                "exec_status": r["exec_status"],
                "phien_status": r["phien_status"],
                "bac_si": r["bac_si"],
                "phong": r["phong"],
                "vao_hang_luc": _iso(r["eligible_at"] or r["created_at"]),
                # Mốc check-in của CẢ lượt: khách quay lại bác sĩ chính đọc kết
                # quả thì đồng hồ tổng vẫn chạy từ lúc vào phòng khám.
                "checkin_luc": _iso(r["checked_in_at"]),
                "vong": r["phien_kind"],
                "goi_luc": _iso(r["called_at"]),
                "bat_dau_luc": _iso(r["serving_at"]),
                "xong_luc": _iso(r["done_at"]),
                "ket_qua_luc": _iso(r["ket_qua_luc"]),
                "duyet_luc": _iso(r["duyet_luc"]),
                # Bệnh án đã ký (FINALIZED/AMENDED): màn khoá phiếu theo mốc
                # NÀY, không theo trạng thái hàng chờ — khách còn "đang khám"
                # mà bác sĩ đã ký thì phiếu tự lưu sẽ ăn 409 (rà 18/09).
                "da_ky": r["visit_status"] in ("FINALIZED", "AMENDED"),
                "ky_luc": _iso(r["finalized_at"]),
                "nguoi_ky": r["nguoi_ky"],
                "nguoi_lam": r["nguoi_lam"],
                # Nội dung kết quả là chữ chuyên môn: chỉ vai đọc lâm sàng thấy.
                "ket_qua_ghi": r["result_note"] if doc_noi_dung else None,
                "ly_do_khong_lam": r["not_performed_reason"],
            }
            for r in _theo_luat_xep_hang(rows)
            # Người đã xong chỉ giữ của hôm nay.
            if r["status"] != "done"
            or (r["done_at"] is not None and _cung_ngay_vn(r["done_at"]))
        ]
        return {
            "phong": (
                {
                    "id": phong["id"],
                    "code": phong["code"],
                    "ten": phong["name"],
                    "tang": phong["floor"],
                    "nodes": [n for n in (phong["nodes"] or []) if n],
                }
                if phong
                else None
            ),
            "hang_cho": now_rows,
            # Phòng khám mà hôm nay chưa có bác sĩ nào trong lịch: màn nói rõ
            # vì sao hàng chờ khám trống, thay vì trông như "hết khách".
            "so_bac_si_trong_phong": so_bac_si_trong_phong if rid else None,
        }

    async def goi_khach(
        self, *, queue_entry_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """GỌI khách vào phòng (Tuyền 16/09/2026: *"gọi khách vào khám rồi ấn bắt
        đầu khám"*). Chờ → Đã gọi; gọi lại thì cập nhật giờ gọi.

        Ai gọi được: lượt khám chính — bác sĩ hoặc thư ký đi kèm bác sĩ ấy; chỉ
        định trong phòng — vai thực hiện bước ấy (thủ thuật: bác sĩ; siêu âm: bác
        sĩ/điều dưỡng siêu âm; lấy mẫu: điều dưỡng), tính cả vai vị trí hôm nay.
        """
        cid = identity.clinic_id
        qid = _uuid(queue_entry_id, "Mã chỗ chờ không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            q = await conn.fetchrow(
                """
                SELECT q.id::text AS id, q.visit_id::text AS visit_id, q.reason,
                       q.status, q.ref_id::text AS ref_id,
                       coalesce(q.doctor_staff_id, c.doctor_staff_id)::text
                           AS doctor_id,
                       n.actor_roles
                  FROM queue_entry q
                  LEFT JOIN consultation c
                    ON c.id = q.ref_id AND q.reason <> 'SERVICE'
                   AND c.clinic_id = q.clinic_id
                  LEFT JOIN service_order o
                    ON o.id = q.ref_id AND q.reason = 'SERVICE'
                   AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                """,
                cid,
                qid,
            )
            if q is None:
                raise NotFoundError("Không tìm thấy khách trong hàng chờ.")
            await self._lock_visit(conn, cid, q["visit_id"])
            if q["reason"] == "SERVICE":
                if not set(identity.ds_vai()) & (
                    set(q["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
                ):
                    raise SafetyGateError("Vai của bạn không làm bước này.")
            else:
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.perform",
                    cau="Bạn chưa được cấp quyền gọi khách vào khám.",
                )
                await self._thu_ky_cua_bac_si(conn, identity, q["doctor_id"])
            trang_thai = await conn.fetchval(
                "SELECT status FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid FOR UPDATE",
                cid,
                qid,
            )
            if trang_thai not in ("waiting", "called"):
                raise LuotKhamConflictError(
                    "NOT_WAITING",
                    "Khách không còn trong hàng chờ (đang làm bước khác hoặc đã xong).",
                )
            await conn.execute(
                "UPDATE queue_entry SET status = 'called', called_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                qid,
            )
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, q["visit_id"])
            await record_event(
                conn,
                event_type="queue.called",
                aggregate_type="visit",
                aggregate_id=q["visit_id"],
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": q["visit_id"], "queue_entry_id": qid},
            )
        return {
            "ok": True,
            "queue_entry_id": qid,
            "lan_goi_lai": trang_thai == "called",
        }

    async def kham_xong(
        self,
        *,
        consultation_id: str,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
        ke_hoach: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Nút "Đã khám xong" — hệ thống tự chọn kết quả phiên, người bấm không phải.

        Còn chỉ định đã duyệt chưa làm → "cần dịch vụ", khách quay lại khi các
        dịch vụ ấy làm xong. Không còn → "không cần dịch vụ", lượt khám chính
        khép lại. Bắt bác sĩ chọn giữa hai mã kỹ thuật ấy là đẩy luật vận hành
        lên đầu người đang khám.

        Mức cần của từng dịch vụ (Slice 1) mặc định theo loại dịch vụ
        (``rules.need_mac_dinh``): lấy mẫu gửi ngoài cần KẾT QUẢ, thủ thuật/siêu
        âm làm xong là đủ. ``ke_hoach`` = {mã chỉ định: PERFORMED|VALID_RESULT|
        FOLLOW_UP} để bác sĩ đổi từng dịch vụ (FOLLOW_UP chỉ bác sĩ).
        """
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Bạn chưa được cấp quyền kết thúc phiên khám.",
            )
            c = await conn.fetchrow(
                "SELECT kind, visit_id::text AS visit_id FROM consultation"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                con_id,
            )
            if c is None:
                raise NotFoundError("Không tìm thấy phiên khám này.")
            con_lai = await conn.fetch(
                """
                SELECT o.id::text AS id, n.lam_ben_ngoai, n.flow_group
                  FROM service_order o
                  LEFT JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
                   AND o.exec_status IN ('authorized', 'assigned', 'in_progress')
                   AND o.hold_until_round IS NULL
                 ORDER BY o.created_at, o.id
                """,
                cid,
                c["visit_id"],
            )
        doi = ke_hoach if isinstance(ke_hoach, dict) else {}
        if con_lai:
            outcome = "SERVICES" if c["kind"] == "PRIMARY" else "MORE_SERVICES"
            reqs = []
            for r in con_lai:
                chon = doi.get(r["id"])
                item: dict[str, Any] = (
                    dict(chon) if isinstance(chon, dict) else {"need": chon}
                )
                if item.get("need") not in rules.PLAN_NEEDS:
                    item["need"] = rules.need_mac_dinh(
                        lam_ben_ngoai=r["lam_ben_ngoai"], flow_group=r["flow_group"]
                    )
                item["order_id"] = r["id"]
                reqs.append(item)
        else:
            outcome = "NO_SERVICES" if c["kind"] == "PRIMARY" else "DONE"
            reqs = []
        return await self.complete_consultation(
            consultation_id=con_id,
            outcome=outcome,
            requirements=reqs,
            identity=identity,
            idempotency_key=idempotency_key,
        )

    async def check_in(
        self,
        *,
        appointment_id: str,
        identity: StaffIdentity,
        xac_minh_cach: str | None = None,
    ) -> dict[str, Any]:
        # Quyền check-in (`reception.checkin.perform`) do BookingService hỏi
        # trong chính giao dịch chuyển trạng thái lịch hẹn.
        from clinicai.services.booking_service import BookingService

        result = await BookingService(self._pool).apply_action(
            appointment_id=_uuid(appointment_id, "Mã lịch hẹn không hợp lệ."),
            action="checkin",
            identity=identity,
            xac_minh_cach=xac_minh_cach,
        )
        return {"ok": True, **result}

    # ------------------------------------------------------------------
    # C2 — ghi sinh hiệu
    # ------------------------------------------------------------------

    async def goi_do_sinh_hieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Điều dưỡng GỌI khách vào đo sinh hiệu (Tuyền 17/09/2026: *"điều
        dưỡng gọi và đo sinh hiệu"*). Gọi lại thì cập nhật giờ gọi."""
        cid = identity.clinic_id
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            await self._lock_visit(conn, cid, vid)
            flow = await self._lock_flow(conn, cid, vid)
            if flow["vitals_status"] == "recorded":
                raise LuotKhamConflictError(
                    "VITALS_DONE", "Khách này đã đo sinh hiệu rồi."
                )
            lan_goi_lai = await conn.fetchval(
                "SELECT goi_do_luc IS NOT NULL FROM encounter_flow"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                cid,
                vid,
            )
            await conn.execute(
                """
                UPDATE encounter_flow
                   SET goi_do_luc = now(), goi_do_boi = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                cid,
                vid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="vitals.called",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
        return {"ok": True, "lan_goi_lai": bool(lan_goi_lai)}

    async def bat_dau_do_sinh_hieu(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """`StartVitals` — điều dưỡng bấm [Bắt đầu] đo cho khách này.

        Thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026: `Gọi vào → Bắt đầu` là
        hai bước cho một việc). `pending → in_progress`, ghi ai bắt đầu và lúc
        nào, phát `vitals.started` ĐÚNG MỘT LẦN.

        BA TÌNH HUỐNG BẤM TRÙNG, xử lý khác nhau có chủ ý:

          * cùng người bấm hai lần (double-click, mạng chập) → `already=True`,
            không sự kiện thứ hai. Không phải lỗi, không làm người ta hoảng.
          * người KHÁC bấm sau → từ chối, nói rõ ai đã bắt đầu, lúc mấy giờ.
            Hai điều dưỡng cùng đo một khách là chuyện phải biết ngay.
          * hai người bấm CÙNG LÚC → `_lock_flow` khoá dòng; người sau chờ,
            rồi rơi vào một trong hai trường hợp trên.

        Mốc này là để ĐO THỜI GIAN CHỜ, không phải cửa khoá: lưu sinh hiệu mà
        chưa ai bấm [Bắt đầu] vẫn được (xem migration 20260923000015).

        CỬA QUYỀN theo VAI, không theo capability — CỐ Ý, và là nợ biết trước.
        Lệnh anh em ngay bên cạnh (`record_vitals`) vẫn gác bằng `VITALS_ROLES`.
        Hai nút trên CÙNG một màn mà gác bằng hai luật khác nhau thì lễ tân sẽ
        lưu được sinh hiệu nhưng không bấm được [Bắt đầu] (nhóm mẫu lễ tân
        chưa có khối Sinh hiệu). Chuyển cả hai sang `vitals.measure` là một
        bước riêng.
        """
        cid = identity.clinic_id
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            await self._lock_visit(conn, cid, vid)
            flow = await self._lock_flow(conn, cid, vid)
            if flow["vitals_status"] == "recorded":
                raise LuotKhamConflictError(
                    "VITALS_DONE", "Khách này đã đo sinh hiệu rồi."
                )
            if flow["vitals_status"] == "in_progress":
                ai = await conn.fetchrow(
                    "SELECT f.vitals_started_by::text AS boi,"
                    "       f.vitals_started_at AS luc, s.full_name AS ten"
                    "  FROM encounter_flow f"
                    "  LEFT JOIN staff s ON s.id = f.vitals_started_by"
                    " WHERE f.clinic_id = $1::uuid AND f.visit_id = $2::uuid",
                    cid,
                    vid,
                )
                assert ai is not None  # vừa khoá trong cùng giao dịch
                if ai["boi"] == identity.staff_id:
                    return {
                        "ok": True,
                        "already": True,
                        "vitals_status": "in_progress",
                        "bat_dau_do_luc": _iso(ai["luc"]),
                    }
                gio = (
                    ai["luc"].astimezone(CLINIC_TZ).strftime("%H:%M")
                    if ai["luc"]
                    else "?"
                )
                raise LuotKhamConflictError(
                    "VITALS_STARTED_BY_OTHER",
                    f"{ai['ten'] or 'Người khác'} đã bắt đầu đo cho khách này"
                    f" lúc {gio}.",
                )

            luc = await conn.fetchval(
                """
                UPDATE encounter_flow
                   SET vitals_status = 'in_progress',
                       vitals_started_at = now(), vitals_started_by = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                RETURNING vitals_started_at
                """,
                cid,
                vid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="vitals.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
            await emit_event(
                conn,
                ten="vitals.started",
                clinic_id=cid,
                aggregate_id=vid,
                payload=SinhHieuBatDau(visit_id=vid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
        return {
            "ok": True,
            "already": False,
            "vitals_status": "in_progress",
            "bat_dau_do_luc": _iso(luc),
        }

    async def dong_bo_sinh_hieu_tu_ho_so(
        self, conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
    ) -> str | None:
        """Sinh hiệu lưu qua BIỂU MẪU BỆNH ÁN (đường cũ) cũng đẩy khách vào luồng.

        17/09/2026: ĐD Huế lưu sinh hiệu cho khách "Khám Hôm Na" qua biểu mẫu
        bệnh án (bấm tên khách ở Trang chủ) — `vital_measurement` có dòng nhưng
        `encounter_flow` không biết "đã đo", không quyết tuyến, không mở phiên
        khám, nên bác sĩ và thư ký KHÔNG BAO GIỜ thấy khách trong hàng chờ.
        Chạy trong CÙNG giao dịch của lệnh lưu. Chưa có huyết áp thì chưa đủ
        điều kiện (luật I8) — để nguyên như màn Đo sinh hiệu.
        """
        cid = identity.clinic_id
        co_huyet_ap = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM vital_measurement
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND systolic IS NOT NULL AND diastolic IS NOT NULL)
            """,
            cid,
            visit_id,
        )
        if not co_huyet_ap:
            return None
        visit = await self._lock_visit(conn, cid, visit_id)
        flow = await self._lock_flow(conn, cid, visit_id)
        if flow["vitals_status"] == "recorded":
            return str(flow["route_decision"]) if flow["route_decision"] else None
        await conn.execute(
            """
            UPDATE encounter_flow
               SET vitals_status = 'recorded',
                   content_revision = content_revision + 1,
                   version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            cid,
            visit_id,
        )
        await record_event(
            conn,
            event_type="vitals.recorded",
            aggregate_type="visit",
            aggregate_id=visit_id,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": visit_id, "qua": "ho_so_benh_an"},
        )
        route = await self._decide_route(conn, identity, visit)
        await self._cap_nhat_vi_tri(conn, cid, visit_id)
        return route

    async def record_vitals(
        self,
        *,
        visit_id: str,
        raw: Any,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        vitals, loi = rules.parse_vitals(raw)
        if vitals is None:
            raise ValidationError(loi or "Sinh hiệu không hợp lệ.")
        payload = {
            "visit_id": vid,
            **{k: str(v) if v is not None else None for k, v in asdict(vitals).items()},
        }
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "vitals.measure")
            visit = await self._lock_visit(conn, identity.clinic_id, vid)
            cached = await self._receipt_get(
                conn, identity, "vitals.record", idempotency_key, payload
            )
            if cached is not None:
                return cached
            # LẦN LƯU ĐẦU PHẢI SAU [Bắt đầu] (chốt 23/09/2026). Bỏ qua được thì
            # lại có lượt "đã đo" mà không biết bắt đầu lúc nào — đúng cái lỗ
            # StartVitals sinh ra để bịt. KHÔNG tự bắt đầu thay người dùng:
            # `vitals_started_at` khi ấy sẽ là giờ LƯU, sai nghĩa.
            # Kiểm SAU khoá encounter_flow nên không có kẽ tranh chấp.
            # Đã `recorded` → lưu thêm vẫn được. Người bắt đầu và người lưu
            # được phép khác nhau (bàn giao giữa hai điều dưỡng).
            flow = await self._lock_flow(conn, identity.clinic_id, vid)
            if flow["vitals_status"] == "pending":
                raise LuotKhamConflictError(
                    "VITALS_NOT_STARTED",
                    "Bấm [Bắt đầu] trước khi lưu sinh hiệu.",
                )
            co_thai = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pregnancy p JOIN visit v
                      ON v.clinic_id = p.clinic_id
                     AND v.clinic_patient_id = p.clinic_patient_id
                   WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                     AND coalesce(p.outcome, 'ONGOING') = 'ONGOING')
                """,
                identity.clinic_id,
                vid,
            )
            loi_thai = rules.thieu_sinh_hieu_khi_co_thai(vitals, co_thai=bool(co_thai))
            if loi_thai:
                raise ValidationError(loi_thai)
            await conn.execute(
                """
                INSERT INTO vital_measurement
                    (clinic_id, visit_id, systolic, diastolic, pulse, temperature,
                     weight_kg, height_cm, respiratory_rate, spo2, bmi,
                     pain_score, recorded_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10,
                        $11, $12, $13::uuid)
                """,
                identity.clinic_id,
                vid,
                vitals.systolic,
                vitals.diastolic,
                vitals.pulse,
                vitals.temperature,
                vitals.weight_kg,
                vitals.height_cm,
                vitals.respiratory_rate,
                vitals.spo2,
                vitals.bmi,
                vitals.pain_score,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE encounter_flow
                   SET vitals_status = 'recorded',
                       content_revision = content_revision + 1,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                """,
                identity.clinic_id,
                vid,
            )
            await record_event(
                conn,
                event_type="vitals.recorded",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid},
            )
            # Sự kiện nghiệp vụ, CÙNG giao dịch với việc ghi sinh hiệu. Payload
            # KHÔNG mang chỉ số: huyết áp là dữ liệu lâm sàng, còn sổ sự kiện
            # thì không xoá được.
            await emit_event(
                conn,
                ten="vitals.recorded",
                clinic_id=identity.clinic_id,
                aggregate_id=vid,
                payload=SinhHieuDaDo(visit_id=vid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            route = await self._decide_route(conn, identity, visit)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            result = {"ok": True, "visit_id": vid, "route": route}
            await self._receipt_put(
                conn, identity, "vitals.record", idempotency_key, payload, vid, result
            )
        return result

    # ------------------------------------------------------------------
    # C3 — bác sĩ nhận khách vào phiên khám
    # ------------------------------------------------------------------

    async def start_consultation(
        self, *, consultation_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Bạn chưa được cấp quyền nhận khách vào khám.",
            )
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            c = await conn.fetchrow(
                """
                SELECT id::text AS id, kind, status, started_by::text AS started_by,
                       doctor_staff_id::text AS doctor_id
                  FROM consultation
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                con_id,
            )
            assert c is not None
            await self._thu_ky_cua_bac_si(conn, identity, c["doctor_id"])
            if c["status"] == "in_progress":
                # Thư ký bấm rồi bác sĩ bấm lại (hay ngược lại) là CÙNG một phiên
                # đang khám, không phải bị người khác giành.
                if c["started_by"] == identity.staff_id or await self._cung_ekip(
                    conn, identity, c
                ):
                    return {"ok": True, "consultation_id": con_id, "already": True}
                raise LuotKhamConflictError(
                    "CONSULTATION_TAKEN", "Phiên khám này bác sĩ khác đang khám."
                )
            if c["status"] != "queued":
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_QUEUED", "Phiên khám này không còn chờ khám."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status
                  FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid AND reason = $4
                   AND status NOT IN ('done', 'left', 'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                con_id,
                c["kind"],
            )
            if (
                entry is None
                or entry["status"] not in ("waiting", "called")
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa gọi vào khám được.",
                )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'in_progress', started_by = $3::uuid,
                      started_at = now(),
                       -- Thư ký bấm thì KHÔNG thành bác sĩ của phiên.
                       doctor_staff_id = coalesce(
                           doctor_staff_id, CASE WHEN $4 THEN $3::uuid END),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                identity.staff_id,
                identity.co_vai({ClinicRole.DOCTOR}),
            )
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            if c["kind"] == "REVIEW":
                # Bác sĩ đã bắt đầu đọc: vòng không còn tự lùi về "đang thu".
                await conn.execute(
                    "UPDATE review_round r SET status = 'in_review',"
                    " version = r.version + 1, updated_at = now()"
                    " FROM consultation c WHERE c.clinic_id = $1::uuid"
                    " AND c.id = $2::uuid AND r.clinic_id = c.clinic_id"
                    " AND r.visit_id = c.visit_id AND r.round_no = c.round_no"
                    " AND r.status = 'ready'",
                    cid,
                    con_id,
                )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id, "kind": c["kind"]},
            )
        return {"ok": True, "consultation_id": con_id}

    # ------------------------------------------------------------------
    # C4 — ghi chú khám (bác sĩ hoặc thư ký gõ hộ)
    # ------------------------------------------------------------------

    async def save_note(
        self, *, consultation_id: str, body: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        text = (body or "").strip() if isinstance(body, str) else ""
        if not text:
            raise ValidationError("Ghi chú đang trống.")
        if len(text) > 20000:
            raise ValidationError("Ghi chú quá dài.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "clinical.record.write")
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            await self._consultation_in_progress(conn, cid, con_id)
            await self._lock_flow(conn, cid, vid)
            await conn.execute(
                "INSERT INTO consultation_note (clinic_id, consultation_id, body,"
                " recorded_by)"
                " VALUES ($1::uuid, $2::uuid, $3, $4::uuid)",
                cid,
                con_id,
                text,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE encounter_flow SET content_revision = content_revision + 1,"
                " updated_at = now() WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid",
                cid,
                vid,
            )
            await record_event(
                conn,
                event_type="consult.note_saved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id},
            )
        return {"ok": True}

    # ------------------------------------------------------------------
    # C5 / C6 — nháp chỉ định (thư ký) và duyệt chỉ định (chỉ bác sĩ)
    # ------------------------------------------------------------------

    async def propose_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str],
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DRAFT_ROLES, "Chỉ thư ký y khoa ghi nháp chỉ định.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        payload = {"consultation_id": con_id, "codes": list(service_codes or [])}
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.draft", idempotency_key, payload
            )
            if cached is not None:
                return cached
            await self._consultation_in_progress(conn, cid, con_id)
            services = await self._services(conn, cid, list(service_codes or []))
            ids = []
            for s in services:
                ids.append(
                    await conn.fetchval(
                        """
                        INSERT INTO service_order
                            (clinic_id, visit_id, consultation_id, service_code,
                             service_name, node_code, exec_status, recorded_by)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'draft',
                           $7::uuid)
                        RETURNING id::text
                        """,
                        cid,
                        vid,
                        con_id,
                        s["service_code"],
                        s["name"],
                        s["node_code"],
                        identity.staff_id,
                    )
                )
            await record_event(
                conn,
                event_type="orders.drafted",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids, "versions": {oid: 1 for oid in ids}}
            await self._receipt_put(
                conn, identity, "orders.draft", idempotency_key, payload, con_id, result
            )
        return result

    async def authorize_orders(
        self,
        *,
        consultation_id: str,
        service_codes: list[str] | None,
        draft_order_ids: list[str] | None,
        identity: StaffIdentity,
        expected_versions: dict[str, int] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DOCTOR_ROLES, "Chỉ bác sĩ duyệt chỉ định được.")
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        codes = list(service_codes or [])
        drafts = [
            _uuid(d, "Mã chỉ định nháp không hợp lệ.") for d in (draft_order_ids or [])
        ]
        if not codes and not drafts:
            raise ValidationError("Chưa chọn dịch vụ nào để duyệt.")
        versions = dict(expected_versions or {})
        if drafts and (
            set(versions) != set(drafts)
            or any(type(v) is not int or v < 1 for v in versions.values())
        ):
            raise LuotKhamConflictError(
                "DRAFT_VERSION_REQUIRED",
                "Cần phiên bản hiện tại của từng chỉ định nháp.",
            )
        payload = {
            "consultation_id": con_id,
            "codes": codes,
            "drafts": sorted(drafts),
            "expected_versions": versions,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "orders.authorize", idempotency_key, payload
            )
            if cached is not None:
                return cached
            consultation = await self._consultation_in_progress(conn, cid, con_id)
            # Bác sĩ của phiên duyệt được kể cả khi thư ký là người bấm "Bắt đầu".
            if identity.staff_id not in (
                consultation["doctor_id"],
                consultation["started_by"],
            ) or not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM staff s JOIN clinic_membership m"
                " ON m.staff_id = s.id WHERE s.id = $1::uuid AND s.is_active"
                " AND m.clinic_id = $2::uuid AND m.is_active"
                " AND m.role = 'DOCTOR')",
                identity.staff_id,
                cid,
            ):
                raise SafetyGateError(
                    "Chỉ bác sĩ đang phụ trách phiên khám được duyệt chỉ định."
                )
            ids: list[str] = []
            if drafts:
                selected = await conn.fetch(
                    "SELECT id::text AS id, version, exec_status FROM service_order"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    " AND consultation_id = $3::uuid AND id = ANY($4::uuid[])"
                    " ORDER BY id FOR UPDATE",
                    cid,
                    vid,
                    con_id,
                    drafts,
                )
                if len(selected) != len(set(drafts)) or any(
                    row["exec_status"] != "draft" for row in selected
                ):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Chỉ định nháp không thuộc phiên khám này hoặc đã xử lý.",
                    )
                if any(row["version"] != versions[row["id"]] for row in selected):
                    raise LuotKhamConflictError(
                        "VERSION_CONFLICT",
                        "Chỉ định nháp đã thay đổi — tải lại trước khi duyệt.",
                    )
                flipped = await conn.fetch(
                    """
                    UPDATE service_order
                       SET exec_status = 'authorized', authorized_by = $4::uuid,
                           authorized_at = now(), version = version + 1,
                              updated_at = now(),
                           -- Lifecycle v1: chỉ định chính thức chờ khách chọn,
                           -- chưa có phòng chính thức (routing_revision = 0).
                           selection_status = 'PENDING',
                           routing_status = 'UNASSIGNED'
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[]) AND exec_status = 'draft'
                       AND consultation_id = $5::uuid
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    drafts,
                    identity.staff_id,
                    con_id,
                )
                if len(flipped) != len(set(drafts)):
                    raise LuotKhamConflictError(
                        "DRAFT_NOT_FOUND",
                        "Có chỉ định nháp không thuộc lượt khám này hoặc đã được xử"
                        " lý.",
                    )
                ids.extend(r["id"] for r in flipped)
            if codes:
                for s in await self._services(conn, cid, codes):
                    ids.append(
                        await conn.fetchval(
                            """
                            INSERT INTO service_order
                                (clinic_id, visit_id, consultation_id, service_code,
                                 service_name, node_code, exec_status, recorded_by,
                                 authorized_by, authorized_at, selection_status,
                                 routing_status)
                            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6,
                                    'authorized', $7::uuid, $7::uuid, now(),
                                    'PENDING', 'UNASSIGNED')
                            RETURNING id::text
                            """,
                            cid,
                            vid,
                            con_id,
                            s["service_code"],
                            s["name"],
                            s["node_code"],
                            identity.staff_id,
                        )
                    )
            await self._tu_xep_phong(conn, identity, vid)
            await record_event(
                conn,
                event_type="orders.authorized",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "consultation_id": con_id, "order_ids": ids},
            )
            result = {"ok": True, "order_ids": ids}
            await self._receipt_put(
                conn,
                identity,
                "orders.authorize",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # C11 / C12 — kết thúc phiên khám
    # ------------------------------------------------------------------

    async def _kiem_ho_so_truoc_khi_khep(
        self,
        conn: asyncpg.Connection,
        *,
        clinic_id: str,
        visit_id: str,
    ) -> None:
        row = await conn.fetchrow(
            """
            SELECT prescription_draft
              FROM clinical_record
             WHERE clinic_id = $1::uuid
               AND visit_id = $2::uuid
             FOR UPDATE
            """,
            clinic_id,
            visit_id,
        )

        if row is not None and row["prescription_draft"] is not None:
            raise LuotKhamConflictError(
                "PRESCRIPTION_DRAFT_PENDING",
                "Còn đơn thuốc thư ký nhập chờ bác sĩ duyệt.",
            )

    async def complete_consultation(
        self,
        *,
        consultation_id: str,
        outcome: str,
        requirements: list[dict[str, Any]] | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        plan: list[tuple[str, str]] = []
        theo_doi_cau_hinh: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for item in requirements or []:
            if not isinstance(item, dict):
                raise ValidationError("Danh sách yêu cầu không đúng dạng.")
            oid = _uuid(item.get("order_id"), "Mã chỉ định trong yêu cầu không hợp lệ.")
            need = str(item.get("need") or "")
            if need not in rules.PLAN_NEEDS:
                raise ValidationError(
                    "Mỗi dịch vụ phải chọn: đã làm, có kết quả, hoặc theo dõi sau."
                )
            if oid not in seen:
                seen.add(oid)
                plan.append((oid, need))
                if need == rules.FOLLOW_UP:
                    han = item.get("han")
                    if han not in (None, "") and rules.doc_han_theo_doi(han) is None:
                        raise ValidationError(
                            "Hạn theo dõi phải là ngày dạng YYYY-MM-DD."
                        )
                    theo_doi_cau_hinh[oid] = item
        reqs, theo_doi = rules.tach_ke_hoach(plan)
        payload = {
            "consultation_id": con_id,
            "outcome": outcome,
            "reqs": sorted(plan),
            "theo_doi": {
                k: {
                    "owner_id": v.get("owner_id"),
                    "han": v.get("han"),
                    "ly_do": v.get("ly_do"),
                }
                for k, v in sorted(theo_doi_cau_hinh.items())
            },
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "consultation", cid, con_id)
            await self._lock_visit(conn, cid, vid, cho_phep_da_ky=True)
            cached = await self._receipt_get(
                conn, identity, "consult.complete", idempotency_key, payload
            )
            if cached is not None:
                return cached
            await doi_quyen(
                conn,
                identity,
                "clinical.consult.perform",
                cau="Bạn chưa được cấp quyền kết thúc phiên khám.",
            )
            if theo_doi:
                # Cho khách về trước khi có kết quả là quyết định chuyên môn —
                # cùng quyền với Hoàn tất khám.
                await doi_quyen(
                    conn,
                    identity,
                    "clinical.consult.finalize",
                    cau="Chỉ bác sĩ quyết cho khách về trước và theo dõi kết quả sau.",
                )
            c = await self._consultation_in_progress(conn, cid, con_id)
            await self._thu_ky_cua_bac_si(conn, identity, c["doctor_id"])
            if not rules.outcome_allowed(c["kind"], outcome):
                raise LuotKhamConflictError(
                    "WRONG_CONSULTATION_KIND",
                    "Kết quả này không dùng cho loại phiên khám hiện tại.",
                )
            next_round: int | None = None
            if outcome == "NO_SERVICES":
                live = await conn.fetchval(
                    """
                    SELECT count(*) FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status IN ('authorized', 'assigned', 'in_progress')
                    """,
                    cid,
                    vid,
                )
                if live:
                    raise LuotKhamConflictError(
                        "ORDERS_PENDING",
                        "Còn chỉ định đã duyệt chưa làm — không kết thúc 'không cần"
                        " dịch vụ' được.",
                    )
                await conn.execute(
                    """
                    UPDATE service_order
                       SET exec_status = 'cancelled', cancelled_by = $3::uuid,
                           cancel_reason = 'Nháp không được duyệt khi kết thúc khám',
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND exec_status = 'draft'
                    """,
                    cid,
                    vid,
                    identity.staff_id,
                )
            elif outcome in rules.OUTCOMES_OPENING_ROUND:
                if not plan:
                    raise LuotKhamConflictError(
                        "REQUIREMENTS_REQUIRED",
                        "Chọn ít nhất một dịch vụ phải xong trước lần đọc kết quả.",
                    )
                rows = await conn.fetch(
                    """
                    SELECT id::text AS id, exec_status, hold_until_round
                      FROM service_order
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND id = ANY($3::uuid[])
                    """,
                    cid,
                    vid,
                    [oid for oid, _ in plan],
                )
                found = {r["id"]: r for r in rows}
                bad = [
                    oid
                    for oid, _ in plan
                    if oid not in found
                    or found[oid]["exec_status"] in ("draft", "cancelled")
                ]
                if bad:
                    raise LuotKhamConflictError(
                        "REQUIREMENT_ORDER_INVALID",
                        "Yêu cầu trỏ tới chỉ định chưa duyệt, đã huỷ hoặc không"
                        " thuộc lượt này.",
                    )
                cyclic = rules.cyclic_orders(
                    int(c["round_no"]) + 1,
                    [(oid, found[oid]["hold_until_round"]) for oid, _ in reqs],
                )
                if cyclic:
                    raise LuotKhamValidationError(
                        "CYCLIC_REQUIREMENT",
                        "Có dịch vụ vừa bắt buộc trước lần đọc kết quả vừa được dặn"
                        " làm sau lần đọc ấy.",
                    )
                # FOLLOW_UP không thành yêu cầu của vòng đọc: chỉ còn dịch vụ
                # theo dõi thì KHÔNG mở vòng, khách làm xong là về.
                next_round = int(c["round_no"]) + 1 if reqs else None
                for oid in theo_doi:
                    await self._mo_theo_doi(
                        conn,
                        identity,
                        vid=vid,
                        oid=oid,
                        cau_hinh=theo_doi_cau_hinh[oid],
                        bac_si=c["doctor_id"],
                    )
            if c["kind"] == "REVIEW":
                vong = await conn.fetchval(
                    "SELECT id::text FROM review_round WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND round_no = $3",
                    cid,
                    vid,
                    c["round_no"],
                )
                if vong is not None:
                    con_quyet = rules.can_quyet(
                        [
                            self._view(q)
                            for q in await self._yeu_cau_cua_vong(conn, cid, vong)
                        ]
                    )
                    if con_quyet:
                        # NOT_PERFORMED không tự coi là đạt: đóng vòng đọc khi
                        # bác sĩ chưa quyết là để lọt một dịch vụ không làm.
                        raise LuotKhamConflictError(
                            "REQUIREMENT_DECISION_REQUIRED",
                            f"Còn {len(con_quyet)} dịch vụ không thực hiện được —"
                            " bác sĩ miễn (ghi lý do) hoặc chuyển theo dõi trước.",
                        )
            if outcome in ("NO_SERVICES", "DONE"):
                # HOÀN TẤT KHÁM (CORE-A, 23/09/2026): phiên khám cuối. Cần quyền
                # `clinical.consult.finalize` VÀ là bác sĩ phụ trách phiên này.
                # KHÔNG khoá hồ sơ — Tuyền chốt 23/09: "không khoá, sửa thoải
                # mái"; bệnh án vẫn sửa trực tiếp sau khi hoàn tất.
                if (
                    not await can(conn, identity, "clinical.consult.finalize")
                    or identity.staff_id != c["doctor_id"]
                ):
                    raise SafetyGateError(
                        "Chỉ bác sĩ phụ trách mới được kết thúc phần khám lâm sàng."
                    )
                await self._kiem_ho_so_truoc_khi_khep(
                    conn,
                    clinic_id=cid,
                    visit_id=vid,
                )
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'completed', outcome = $3, completed_by = $4::uuid,
                       completed_at = now(), version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
                outcome,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                con_id,
            )
            if c["kind"] == "REVIEW":
                await conn.execute(
                    "UPDATE review_round SET status = 'closed', closed_at = now(),"
                    " version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND"
                    " round_no = $3",
                    cid,
                    vid,
                    c["round_no"],
                )
            if next_round is not None:
                round_id = await conn.fetchval(
                    """
                    INSERT INTO review_round (clinic_id, visit_id, round_no, status,
                       locked_by)
                    VALUES ($1::uuid, $2::uuid, $3, 'collecting', $4::uuid)
                    RETURNING id::text
                    """,
                    cid,
                    vid,
                    next_round,
                    identity.staff_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO round_requirement (clinic_id, round_id,
                       service_order_id, need)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4)
                    """,
                    [(cid, round_id, oid, need) for oid, need in reqs],
                )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="consult.completed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "outcome": outcome,
                    "next_round": next_round,
                },
            )
            result = {
                "ok": True,
                "consultation_id": con_id,
                "next_round": next_round,
            }
            await self._receipt_put(
                conn,
                identity,
                "consult.complete",
                idempotency_key,
                payload,
                con_id,
                result,
            )
        return result

    # ------------------------------------------------------------------
    # Slice 1 — bác sĩ quyết một yêu cầu: miễn hoặc chuyển theo dõi
    # ------------------------------------------------------------------

    async def quyet_yeu_cau(
        self,
        *,
        requirement_id: str,
        hanh_dong: str,
        ly_do: str | None,
        identity: StaffIdentity,
        owner_id: str | None = None,
        han: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Bác sĩ quyết một yêu cầu của vòng đọc chưa đạt.

        ``WAIVE``: không cần nữa (đổi kế hoạch: miễn ở đây rồi chỉ định thêm
        trong phiên đọc kết quả). ``FOLLOW_UP``: khách không phải chờ — mở việc
        theo dõi có người phụ trách và hạn. Cả hai bắt buộc lý do và ghi nhật
        ký; chỉ bác sĩ phụ trách lượt khám làm được (thư ký không quyết).
        """
        _require(identity, DOCTOR_ROLES, "Chỉ bác sĩ quyết miễn hoặc theo dõi.")
        cid = identity.clinic_id
        rid = _uuid(requirement_id, "Mã yêu cầu không hợp lệ.")
        if hanh_dong not in ("WAIVE", "FOLLOW_UP"):
            raise ValidationError("Chọn miễn hoặc chuyển theo dõi.")
        ghi = ly_do.strip() if isinstance(ly_do, str) else ""
        if not ghi:
            raise ValidationError("Ghi lý do bác sĩ quyết như vậy.")
        if len(ghi) > 2000:
            raise ValidationError("Lý do quá dài.")
        if han not in (None, "") and rules.doc_han_theo_doi(han) is None:
            raise ValidationError("Hạn theo dõi phải là ngày dạng YYYY-MM-DD.")
        payload = {
            "requirement_id": rid,
            "hanh_dong": hanh_dong,
            "ly_do": ghi,
            "owner_id": owner_id,
            "han": han,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                "SELECT r.visit_id::text FROM round_requirement q"
                " JOIN review_round r ON r.id = q.round_id AND r.clinic_id ="
                " q.clinic_id WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid",
                cid,
                rid,
            )
            if vid is None:
                raise NotFoundError("Không tìm thấy yêu cầu này.")
            visit = await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "requirement.decide", idempotency_key, payload
            )
            if cached is not None:
                return cached
            q = await conn.fetchrow(
                """
                SELECT q.status, q.service_order_id::text AS order_id,
                       q.round_id::text AS round_id, o.exec_status,
                       r.status AS vong_status, r.round_no
                  FROM round_requirement q
                  JOIN review_round r ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                 WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                   FOR UPDATE OF q
                """,
                cid,
                rid,
            )
            assert q is not None
            phu_trach = {
                visit["doctor_id"],
                *[
                    r["d"]
                    for r in await conn.fetch(
                        "SELECT doctor_staff_id::text AS d FROM consultation"
                        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
                        cid,
                        vid,
                    )
                ],
            }
            if identity.staff_id not in phu_trach:
                raise SafetyGateError(
                    "Chỉ bác sĩ phụ trách lượt khám này quyết được yêu cầu."
                )
            if q["vong_status"] == "closed":
                raise LuotKhamConflictError(
                    "ROUND_CLOSED", "Lần đọc kết quả này đã đóng."
                )
            if q["status"] in ("waived", "follow_up"):
                raise LuotKhamConflictError(
                    "REQUIREMENT_DECIDED", "Yêu cầu này bác sĩ đã quyết rồi."
                )
            trang_thai = rules.requirement_state(
                self._view(
                    next(
                        r
                        for r in await self._yeu_cau_cua_vong(conn, cid, q["round_id"])
                        if r["id"] == rid
                    )
                )
            )
            if trang_thai == "satisfied":
                raise LuotKhamConflictError(
                    "REQUIREMENT_SATISFIED",
                    "Yêu cầu này đã đạt — không cần miễn hay theo dõi nữa.",
                )
            if hanh_dong == "FOLLOW_UP" and q["exec_status"] != "performed":
                # Việc theo dõi đóng khi bác sĩ DUYỆT KẾT QUẢ. Dịch vụ không làm
                # được thì không bao giờ có kết quả → việc mồ côi. Hẹn làm lại
                # là tái khám: miễn ở đây (ghi lý do) + hẹn trong bệnh án.
                raise LuotKhamConflictError(
                    "FOLLOW_UP_NEEDS_RESULT",
                    "Chỉ chuyển theo dõi khi đang chờ kết quả. Dịch vụ không làm"
                    " được: miễn (ghi lý do) và hẹn tái khám trong bệnh án.",
                )
            fid: str | None = None
            mien = hanh_dong == "WAIVE"
            if mien:
                await conn.execute(
                    """
                    UPDATE round_requirement
                       SET status = 'waived', waived_by = $3::uuid,
                           waived_reason = $4, updated_at = now()
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    """,
                    cid,
                    rid,
                    identity.staff_id,
                    ghi,
                )
            else:
                fid = await self._mo_theo_doi(
                    conn,
                    identity,
                    vid=vid,
                    oid=q["order_id"],
                    cau_hinh={"owner_id": owner_id, "han": han, "ly_do": ghi},
                    bac_si=identity.staff_id,
                )
                await conn.execute(
                    """
                    UPDATE round_requirement q
                       SET status = 'follow_up', waived_by = $3::uuid,
                           waived_reason = $4, follow_up_case_id = $5::uuid,
                           followup_owner = f.owner_staff_id,
                           followup_due = (f.due_at AT TIME ZONE
                                           'Asia/Ho_Chi_Minh')::date,
                           updated_at = now()
                      FROM follow_up_case f
                     WHERE q.clinic_id = $1::uuid AND q.id = $2::uuid
                       AND f.id = $5::uuid
                    """,
                    cid,
                    rid,
                    identity.staff_id,
                    ghi,
                    fid,
                )
            await record_event(
                conn,
                # f-string có chủ ý: bài canh nhãn (test_audit_labels_drift)
                # đọc được cả hai nhánh mã.
                event_type=f"requirement.{'waived' if mien else 'follow_up'}",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "requirement_id": rid,
                    "order_id": q["order_id"],
                    "round_no": q["round_no"],
                    # Lý do ở round_requirement.waived_reason, không ở nhật ký.
                    "follow_up_case_id": fid,
                },
            )
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, cid, vid)
            result = {
                "ok": True,
                "requirement_id": rid,
                "trang_thai": "waived" if hanh_dong == "WAIVE" else "follow_up",
                "follow_up_case_id": fid,
            }
            await self._receipt_put(
                conn,
                identity,
                "requirement.decide",
                idempotency_key,
                payload,
                rid,
                result,
            )
        return result

    async def cho_quyet(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Yêu cầu của vòng đọc đang CHỜ bác sĩ: kết quả chưa về, hoặc dịch vụ
        không làm được cần bác sĩ quyết.

        Khách đang chờ kết quả không nằm trong hàng chờ khám nào (vòng đọc chưa
        sẵn sàng), nên trước Slice 1 bác sĩ không thấy họ ở đâu cả — và không có
        chỗ nào để nói "cho khách về, báo kết quả sau". Bác sĩ thấy khách của
        mình; thư ký thấy khách của bác sĩ mình đi kèm (chỉ xem — quyết là việc
        của bác sĩ).
        """
        _require(identity, CONSULT_ROLES, "Chỉ bác sĩ hoặc thư ký xem việc chờ quyết.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            if identity.co_vai(DOCTOR_ROLES):
                bac_si: list[str] | None = [identity.staff_id]
            else:
                bac_si = await bac_si_cua_thu_ky(conn, identity)
            rows = await conn.fetch(
                """
                SELECT q.id::text AS id, q.need, q.status,
                       q.service_order_id::text AS order_id,
                       o.exec_status,
                       CASE
                         WHEN coalesce(nd.lam_ben_ngoai, false) THEN
                           EXISTS (
                             SELECT 1 FROM tep_ket_qua t
                              WHERE t.clinic_id = q.clinic_id
                                AND t.service_order_id = o.id
                                AND t.xac_nhan_trang_thai = 'HOP_LE'
                           )
                         ELSE o.ket_qua_luc IS NOT NULL
                       END AS co_ket_qua,
                       o.service_name, o.not_performed_reason,
                       r.round_no, r.status AS vong_status,
                       v.visit_id::text AS visit_id, p.full_name, p.patient_code
                  FROM round_requirement q
                  JOIN review_round r
                    ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                  JOIN service_order o
                    ON o.id = q.service_order_id AND o.clinic_id = q.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                  JOIN visit v ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                 WHERE q.clinic_id = $1::uuid
                   AND r.status <> 'closed' AND q.status = 'open'
                   AND v.status IN ('OPEN', 'IN_PROGRESS')
                   -- Chỉ việc của BÁC SĨ: đang chờ kết quả (đã làm, chưa có kết
                   -- quả) hoặc không làm được. Lọc ở SQL để LIMIT không cắt mất.
                   AND ((q.need = 'VALID_RESULT' AND o.exec_status = 'performed'
                         AND (
                           CASE
                             WHEN coalesce(nd.lam_ben_ngoai, false) THEN
                               NOT EXISTS (
                                 SELECT 1 FROM tep_ket_qua t
                                  WHERE t.clinic_id = q.clinic_id
                                    AND t.service_order_id = o.id
                                    AND t.xac_nhan_trang_thai = 'HOP_LE'
                               )
                             ELSE o.ket_qua_luc IS NULL
                           END
                         ))
                        OR o.exec_status IN ('not_performed', 'cancelled'))
                   AND ($2::text[] IS NULL
                        OR v.attending_doctor_id::text = ANY($2::text[])
                        OR EXISTS (SELECT 1 FROM consultation c
                                    WHERE c.clinic_id = v.clinic_id
                                      AND c.visit_id = v.visit_id
                                      AND c.doctor_staff_id::text = ANY($2::text[])))
                 ORDER BY r.created_at, q.created_at
                 LIMIT 200
                """,
                cid,
                bac_si,
            )
        # Hàng "chờ bác sĩ quyết": cắt im lặng là một yêu cầu chờ mãi.
        canh_bao_neu_day("bac_si.cho_quyet", len(rows), 200, clinic_id=cid)
        viec = []
        for q in rows:
            trang_thai = rules.requirement_state(self._view(q))
            # Đã đạt rồi (chờ vòng tự cập nhật) hay chỉ cần "đã làm" mà chưa
            # làm tới — đó là việc của phòng dịch vụ, không phải của bác sĩ.
            if trang_thai == "satisfied":
                continue
            if trang_thai == "open" and (
                q["need"] != "VALID_RESULT" or q["exec_status"] != "performed"
            ):
                continue
            viec.append(
                {
                    "id": q["id"],
                    "visit_id": q["visit_id"],
                    "ten": q["full_name"],
                    "ma_bn": q["patient_code"],
                    "dich_vu": q["service_name"],
                    "can": q["need"],
                    "trang_thai": (
                        "can_quyet" if trang_thai == "needs_decision" else "cho_ket_qua"
                    ),
                    "ly_do_khong_lam": q["not_performed_reason"],
                    "vong": q["round_no"],
                }
            )
        return {"viec": viec, "duoc_quyet": identity.co_vai(DOCTOR_ROLES)}

    async def chi_dinh_hom_nay(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Mọi chỉ định bác sĩ đã duyệt hôm nay, chia bốn nhóm cho trưởng ca.

        Cần điều phối (chưa có phòng) · Đã điều phối (có phòng, chưa làm) ·
        Đang thực hiện · Đã hoàn tất (đã làm / không làm được). Trưởng ca chỉ
        XẾP PHÒNG từng chỉ định — không tạo chỉ định, không bấm xong thay phòng.
        Kèm các mốc để dựng dòng thời gian, và vòng đọc kết quả (khách đã quay
        lại bác sĩ chưa).
        """
        _require(identity, DISPATCH_ROLES, "Chỉ trưởng ca hoặc quản lý xem điều phối.")
        rows = await self._pool.fetch(
            """
            SELECT o.id::text AS id, o.visit_id::text AS visit_id,
                   o.service_name, o.exec_status, o.created_at, o.authorized_at,
                   o.assigned_at, o.started_at, o.finished_at, o.ket_qua_luc,
                   rm.name AS phong, pb.full_name AS nguoi_lam,
                   p.full_name, p.patient_code,
                   (SELECT r.status FROM round_requirement q
                      JOIN review_round r
                        ON r.id = q.round_id AND r.clinic_id = q.clinic_id
                     WHERE q.clinic_id = o.clinic_id AND q.service_order_id = o.id
                     ORDER BY r.round_no DESC LIMIT 1)          AS vong_doc,
                   (SELECT q.need FROM round_requirement q
                     WHERE q.clinic_id = o.clinic_id AND q.service_order_id = o.id
                     ORDER BY q.created_at DESC LIMIT 1)        AS can,
                   -- Không phòng nào (kể cả phòng đối tác) làm bước này: chỉ
                   -- định sẽ kẹt "chờ xếp phòng" mãi — cấu hình, không phải
                   -- việc trưởng ca tự xoay được.
                   NOT EXISTS (
                       SELECT 1 FROM clinic_room_node rn
                         JOIN clinic_room r2
                           ON r2.id = rn.room_id AND r2.clinic_id = rn.clinic_id
                        WHERE rn.clinic_id = o.clinic_id
                          AND rn.node_code = o.node_code
                          AND r2.is_active)                     AS khong_co_phong
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              LEFT JOIN clinic_room rm
                ON rm.id = o.room_id AND rm.clinic_id = o.clinic_id
              LEFT JOIN staff pb ON pb.id = o.performed_by
             WHERE o.clinic_id = $1::uuid
               AND o.exec_status NOT IN ('draft', 'cancelled')
               AND (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
             ORDER BY o.created_at, o.id
             LIMIT $2
            """,
            identity.clinic_id,
            _TRAN_CHI_DINH_HOM_NAY,
        )
        # Cắt bớt mà không nói là nói dối bằng cách im lặng: trưởng ca nhìn một
        # bảng thiếu người mà tưởng đã hết. Đếm tổng để màn hình báo được.
        tong = await self._pool.fetchval(
            """
            SELECT count(*) FROM service_order o
             WHERE o.clinic_id = $1::uuid
               AND o.exec_status NOT IN ('draft', 'cancelled')
               AND (o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                   = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
            """,
            identity.clinic_id,
        )
        nhom = {
            "authorized": "can_dieu_phoi",
            "assigned": "da_dieu_phoi",
            "in_progress": "dang_thuc_hien",
            "performed": "da_hoan_tat",
            "not_performed": "da_hoan_tat",
        }
        return {
            "chi_dinh": [
                {
                    "id": r["id"],
                    "visit_id": r["visit_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "dich_vu": r["service_name"],
                    "trang_thai": r["exec_status"],
                    "nhom": nhom.get(r["exec_status"], "can_dieu_phoi"),
                    "phong": r["phong"],
                    "nguoi_lam": r["nguoi_lam"],
                    "can": r["can"],
                    "vong_doc": r["vong_doc"],
                    "khong_co_phong": bool(r["khong_co_phong"]),
                    "chi_dinh_luc": _iso(r["authorized_at"] or r["created_at"]),
                    "xep_phong_luc": _iso(r["assigned_at"]),
                    "bat_dau_luc": _iso(r["started_at"]),
                    "xong_luc": _iso(r["finished_at"]),
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                }
                for r in rows
            ],
            "tong": int(tong or 0),
            # True = bảng đang thiếu; màn hình phải nói ra, đừng để người dùng
            # tự phát hiện bằng cách không tìm thấy khách của mình.
            "bi_cat": int(tong or 0) > len(rows),
        }

    async def sau_khi_co_ket_qua(
        self, *, order_id: str, identity: StaffIdentity
    ) -> None:
        """Kết quả vừa gắn vào một chỉ định (tệp tải lên): chạy lại vòng đọc.

        Tệp kết quả đi đường riêng (``tep_ket_qua_service``) nên phải gọi lại
        D2 ở đây — không thì yêu cầu "cần kết quả" đứng im dù kết quả đã về.
        Lượt đã đóng thì thôi: kết quả muộn lúc ấy thuộc việc theo dõi.
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            try:
                vid = await self._visit_of(conn, "service_order", cid, oid)
                await self._lock_visit(conn, cid, vid)
            except (NotFoundError, LuotKhamConflictError):
                return
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, cid, vid)

    # ------------------------------------------------------------------
    # C7 — điều phối chỉ định vào phòng
    # ------------------------------------------------------------------

    async def dispatch_order(
        self,
        *,
        order_id: str,
        room_id: str,
        expected_version: int | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        _require(identity, DISPATCH_ROLES, "Chỉ trưởng ca hoặc quản lý điều phối được.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        payload = {
            "order_id": oid,
            "room_id": rid,
            "expected_version": expected_version,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            cached = await self._receipt_get(
                conn, identity, "dispatch.assign", idempotency_key, payload
            )
            if cached is not None:
                return cached
            o = await conn.fetchrow(
                """
                SELECT exec_status, source, authorized_by::text AS authorized_by,
                       hold_until_round, node_code, version, selection_status
                  FROM service_order
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                   FOR UPDATE
                """,
                cid,
                oid,
            )
            assert o is not None
            if o["selection_status"] is not None:
                # Lifecycle v1 (Slice 4 §D): chỉ định mới chỉ xếp phòng qua
                # AssignServiceRoom — sau khi khách chọn, đủ tài chính, đúng
                # routing_revision. Đường cũ không có revision để đối chiếu, nên
                # từ chối thay vì đoán (không lấy `version` thay revision).
                raise LuotKhamConflictError(
                    "LIFECYCLE_ROUTING_REQUIRED",
                    "Chỉ định này điều phối bằng lệnh xếp phòng mới"
                    " (AssignServiceRoom).",
                )
            if expected_version is not None and o["version"] != expected_version:
                raise LuotKhamConflictError(
                    "STALE_VERSION",
                    "Chỉ định vừa được người khác cập nhật — tải lại màn hình.",
                )
            flow = await self._lock_flow(conn, cid, vid)
            closed = {
                int(r["round_no"])
                for r in await conn.fetch(
                    "SELECT round_no FROM review_round"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                    " = 'closed'",
                    cid,
                    vid,
                )
            }
            code = rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            )
            if code:
                raise LuotKhamConflictError(code, _CAU_CHAN_DIEU_PHOI[code])
            version = await self._gan_phong(
                conn, identity, vid=vid, oid=oid, rid=rid, o=o
            )
            result = {"ok": True, "order_id": oid, "version": version}
            await self._receipt_put(
                conn, identity, "dispatch.assign", idempotency_key, payload, oid, result
            )
        return result

    async def _gan_phong(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        vid: str,
        oid: str,
        rid: str,
        o: asyncpg.Record,
    ) -> int:
        """Đặt một chỉ định (đã qua luật chặn) vào hàng chờ của một phòng."""
        cid = identity.clinic_id
        serves = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM clinic_room r
                  JOIN clinic_room_node rn
                    ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.id = $2::uuid
                   AND rn.node_code = $3 AND r.is_active AND r.accepting)
            """,
            cid,
            rid,
            o["node_code"],
        )
        if not serves:
            raise LuotKhamConflictError(
                "ROOM_NOT_SERVING", "Phòng đã chọn không làm dịch vụ này."
            )
        if o["exec_status"] == "assigned":
            dang_goi = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM queue_entry
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND ref_id = $3::uuid AND reason = 'SERVICE'
                       AND status IN ('called', 'serving'))
                """,
                cid,
                vid,
                oid,
            )
            if dang_goi:
                # Phòng cũ đã gọi/đang làm: đổi phòng lúc này là khách đứng
                # giữa hai phòng cùng gọi tên mình.
                raise LuotKhamConflictError(
                    "ROOM_ALREADY_CALLED",
                    "Phòng hiện tại đã gọi khách vào — không chuyển phòng được nữa.",
                )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET room_id = $4::uuid, version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
                rid,
            )
        else:
            await self._enqueue(
                conn,
                clinic_id=cid,
                visit_id=vid,
                lane="ROOM",
                reason="SERVICE",
                ref_id=oid,
                room_id=rid,
            )
        version = await conn.fetchval(
            """
            UPDATE service_order
               SET exec_status = 'assigned', room_id = $3::uuid,
                  assigned_by = $4::uuid,
                   assigned_at = now(), version = version + 1, updated_at = now()
             WHERE clinic_id = $1::uuid AND id = $2::uuid
            RETURNING version
            """,
            cid,
            oid,
            rid,
            identity.staff_id,
        )
        await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
        await record_event(
            conn,
            event_type="dispatch.assigned",
            aggregate_type="visit",
            aggregate_id=vid,
            identity=identity,
            origin=ORIGIN,
            payload={"visit_id": vid, "order_id": oid, "room_id": rid},
        )
        return int(version)

    async def _tu_xep_phong(
        self, conn: asyncpg.Connection, identity: StaffIdentity, vid: str
    ) -> list[str]:
        """Chỉ định vừa duyệt TỰ vào hàng chờ phòng làm được việc ấy.

        Notion "Kế hoạch v1.0.0", vai Trưởng ca: *"Ngay khi chỉ định, hệ thống sẽ
        tự phân bổ người bệnh về các phòng dựa trên tình trạng thực tế"*.

        Chọn phòng: có người đứng trong lịch HÔM NAY trước, rồi phòng ít người
        chờ nhất. Chỉ định nào luật chặn (chưa đo huyết áp, dặn làm sau khi đọc
        kết quả…) hoặc không phòng nào làm được thì ĐỂ NGUYÊN "đã duyệt" — trưởng
        ca thấy và xếp tay. Không bao giờ ném lỗi làm hỏng lệnh duyệt.
        """
        from clinicai.services.service_routing_service import (
            eligible_rooms,
            rank_rooms,
        )

        cid = identity.clinic_id
        flow = await self._lock_flow(conn, cid, vid)
        closed = {
            int(r["round_no"])
            for r in await conn.fetch(
                "SELECT round_no FROM review_round"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status"
                " = 'closed'",
                cid,
                vid,
            )
        }
        orders = await conn.fetch(
            """
            SELECT id::text AS id, exec_status, source,
                   authorized_by::text AS authorized_by, hold_until_round,
                   node_code, version
              FROM service_order o
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
               AND exec_status = 'authorized'
               -- Lifecycle v1 (CHECKPOINT §1): chỉ định có selection_status chỉ
               -- được xếp phòng SAU khi khách chọn và đủ điều kiện tài chính —
               -- qua lệnh Routing (Slice 4), không tự xếp lúc duyệt. Dòng cũ
               -- (NULL) giữ hành vi cũ.
               AND o.selection_status IS NULL
               -- Đối tác tự lấy mẫu thì khách không xếp hàng ở phòng nào của
               -- phòng khám — việc ấy nằm trên bàn đối tác.
               AND NOT EXISTS (
                   SELECT 1 FROM service_price sp
                    WHERE sp.clinic_id = o.clinic_id
                      AND sp.service_code = o.service_code
                      AND sp.doi_tac_lay_mau)
             ORDER BY created_at, id
               FOR UPDATE
            """,
            cid,
            vid,
        )
        da_xep: list[str] = []
        for o in orders:
            if rules.dispatch_block(
                exec_status=o["exec_status"],
                source=o["source"],
                authorized_by=o["authorized_by"],
                plan_applied=False,
                route_decision=flow["route_decision"],
                vitals_recorded=flow["vitals_status"] == "recorded",
                hold_until_round=o["hold_until_round"],
                closed_rounds=closed,
            ):
                continue
            # Cùng luật gợi ý với Routing v1 (EligibleRoomQuery + advisor theo
            # luật): chỉ dòng CŨ (selection_status NULL) mới tự xếp ở đây.
            xep = rank_rooms(await eligible_rooms(conn, cid, o["node_code"]))
            rid = xep[0]["room_id"] if xep else None
            if rid is None:
                continue
            await self._gan_phong(conn, identity, vid=vid, oid=o["id"], rid=rid, o=o)
            da_xep.append(o["id"])
        return da_xep

    # ------------------------------------------------------------------
    # Kết quả: bác sĩ duyệt theo TỪNG chỉ định
    # ------------------------------------------------------------------

    async def ket_qua_cho_duyet(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Chỉ định đã có kết quả (tệp hoặc nội dung) mà bác sĩ chưa duyệt.

        Cả chỉ định ĐÃ duyệt mà có tệp mới tải lên sau đó (đối tác gửi bản điều
        chỉnh): tệp mới không thừa hưởng lần duyệt cũ, nên phải quay lại đây —
        nếu không nó nằm im mãi, CSKH không bao giờ thấy (smoke 18/09).
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, "result.review.approve")
            rows = await conn.fetch(
                """
                SELECT o.id::text AS id, o.service_name, o.node_code,
                       o.result_note, o.ket_qua_luc, o.exec_status,
                       o.visit_id::text AS visit_id,
                       v.appointment_id::text AS appointment_id,
                       p.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code,
                       d.full_name AS bac_si, v.attending_doctor_id::text AS bac_si_id,
                       pf.full_name AS nguoi_lam, o.duyet_luc
                  FROM service_order o
                  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                  LEFT JOIN staff d ON d.id = v.attending_doctor_id
                  LEFT JOIN staff pf ON pf.id = o.performed_by
                 WHERE o.clinic_id = $1::uuid
                   AND (
                     (coalesce(nd.lam_ben_ngoai, false) AND EXISTS (
                         SELECT 1 FROM tep_ket_qua t
                          WHERE t.clinic_id = o.clinic_id
                            AND t.service_order_id = o.id
                            AND t.xac_nhan_trang_thai = 'HOP_LE'
                     ))
                     OR
                     (
                       NOT coalesce(nd.lam_ben_ngoai, false)
                       AND o.ket_qua_luc IS NOT NULL
                     )
                   )
                   AND (o.duyet_luc IS NULL
                        OR EXISTS (SELECT 1 FROM tep_ket_qua t
                                    WHERE t.clinic_id = o.clinic_id
                                      AND t.service_order_id = o.id
                                      AND t.xac_nhan_trang_thai = 'HOP_LE'
                                      AND t.cho_phep_gui_luc IS NULL))
                   AND o.exec_status NOT IN ('draft', 'cancelled')
                   AND o.created_at > now() - interval '60 days'
                 ORDER BY (v.attending_doctor_id = $2::uuid) DESC NULLS LAST,
                          o.ket_qua_luc, o.id
                 LIMIT 200
                """,
                cid,
                identity.staff_id,
            )
            teps = await conn.fetch(
                """
                SELECT t.id::text AS id, t.service_order_id::text AS order_id,
                       t.ten_hien_thi, t.loai_tep, t.mime, t.so_byte, t.tai_len_luc,
                       t.cho_phep_gui_luc IS NOT NULL AS da_cho_gui
                  FROM tep_ket_qua t
                 WHERE t.clinic_id = $1::uuid
                   AND t.service_order_id = ANY($2::uuid[])
                   AND t.xac_nhan_trang_thai = 'HOP_LE'
                 ORDER BY t.tai_len_luc
                """,
                cid,
                [r["id"] for r in rows],
            )
        theo: dict[str, list[dict[str, Any]]] = {}
        for t in teps:
            theo.setdefault(t["order_id"], []).append(
                {
                    "id": t["id"],
                    "ten": t["ten_hien_thi"],
                    "loai_tep": t["loai_tep"],
                    "mime": t["mime"],
                    "so_byte": int(t["so_byte"]),
                    "tai_len_luc": _iso(t["tai_len_luc"]),
                    "da_cho_gui": t["da_cho_gui"],
                }
            )
        return {
            "ket_qua": [
                {
                    "id": r["id"],
                    "dich_vu": r["service_name"],
                    "node_code": r["node_code"],
                    "noi_dung": r["result_note"],
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                    "visit_id": r["visit_id"],
                    "appointment_id": r["appointment_id"],
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten": r["full_name"],
                    "ma_bn": r["patient_code"],
                    "bac_si": r["bac_si"],
                    "cua_toi": r["bac_si_id"] == identity.staff_id,
                    "nguoi_lam": r["nguoi_lam"],
                    "tep": theo.get(r["id"], []),
                    # Đã duyệt một lần — thẻ này có mặt vì có tệp mới chưa duyệt.
                    "duyet_lan_truoc": _iso(r["duyet_luc"]),
                }
                for r in rows
            ]
        }

    async def duyet_ket_qua(
        self,
        *,
        order_id: str,
        danh_gia: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Bác sĩ đánh giá + PHÊ DUYỆT CHO GỬI kết quả của một chỉ định.

        Notion v1.0.0: *"Dưới kết quả xét nghiệm sẽ có nút Phê duyệt cho gửi và
        chỗ ghi Đánh giá của bác sĩ"*. Duyệt xong thì mọi tệp của chỉ định ấy
        được phép gửi — CSKH thấy "Đã có kết quả".
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ghi = (danh_gia or "").strip() if isinstance(danh_gia, str) else ""
        if len(ghi) > 5000:
            raise ValidationError("Đánh giá quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, "result.review.approve")
            vid = await self._visit_of(conn, "service_order", cid, oid)
            # KẾT QUẢ MUỘN về sau khi bác sĩ đã ký bệnh án (FINALIZED) hay quầy
            # đã đóng lượt vẫn phải duyệt được — đó chính là việc theo dõi.
            # Nên chỉ khoá dòng visit để tuần tự hoá, không đòi lượt còn mở.
            await conn.execute(
                "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid FOR UPDATE",
                cid,
                vid,
            )
            o = await conn.fetchrow(
                """
                SELECT o.exec_status, o.ket_qua_luc, o.duyet_luc,
                       coalesce(nd.lam_ben_ngoai, false) AS lam_ben_ngoai
                  FROM service_order o
                  LEFT JOIN node_definition nd
                    ON nd.clinic_id = o.clinic_id AND nd.code = o.node_code
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            assert o is not None
            if o["lam_ben_ngoai"]:
                has_hop_le = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM tep_ket_qua t
                         WHERE t.clinic_id = $1::uuid
                           AND t.service_order_id = $2::uuid
                           AND t.xac_nhan_trang_thai = 'HOP_LE'
                    )
                    """,
                    cid,
                    oid,
                )
                if not has_hop_le:
                    raise LuotKhamConflictError(
                        "NO_VALID_RESULT",
                        "Chỉ định ngoài chưa có tệp kết quả được xác nhận "
                        "hợp lệ để duyệt.",
                    )
            if o["duyet_luc"] is not None:
                # Đã duyệt trước đó. Tệp mới gửi SAU lần duyệt không thừa hưởng
                # quyền gửi — bác sĩ bấm duyệt lần nữa thì chỉ mở các tệp ấy,
                # giữ nguyên đánh giá cũ trừ khi ghi đánh giá mới.
                moi = await conn.fetch(
                    """
                    UPDATE tep_ket_qua
                       SET cho_phep_gui_luc = now(),
                           cho_phep_gui_boi_staff_id = $3::uuid
                     WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                       AND cho_phep_gui_luc IS NULL
                       AND xac_nhan_trang_thai = 'HOP_LE'
                    RETURNING id::text
                    """,
                    cid,
                    oid,
                    identity.staff_id,
                )
                if not moi:
                    return {"ok": True, "order_id": oid, "already": True}
                if ghi:
                    await conn.execute(
                        """
                        UPDATE service_order
                           SET bac_si_danh_gia = $3,
                               version = version + 1, updated_at = now()
                         WHERE clinic_id = $1::uuid AND id = $2::uuid
                        """,
                        cid,
                        oid,
                        ghi,
                    )
                await record_event(
                    conn,
                    event_type="result.approved",
                    aggregate_type="visit",
                    aggregate_id=vid,
                    identity=identity,
                    origin=ORIGIN,
                    payload={
                        "visit_id": vid,
                        "order_id": oid,
                        "tep_moi": [r["id"] for r in moi],
                    },
                )
                return {"ok": True, "order_id": oid, "tep_moi": len(moi)}
            if o["ket_qua_luc"] is None and not o["lam_ben_ngoai"]:
                raise LuotKhamConflictError(
                    "NO_RESULT_YET", "Chỉ định này chưa có kết quả để duyệt."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET duyet_luc = now(), duyet_boi = $3::uuid,
                       bac_si_danh_gia = nullif($4, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
                ghi,
            )
            await conn.execute(
                """
                UPDATE tep_ket_qua
                   SET cho_phep_gui_luc = now(), cho_phep_gui_boi_staff_id = $3::uuid
                 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                   AND cho_phep_gui_luc IS NULL
                   AND xac_nhan_trang_thai = 'HOP_LE'
                """,
                cid,
                oid,
                identity.staff_id,
            )
            # Việc theo dõi "chờ kết quả" của chỉ định này xong khi bác sĩ duyệt.
            await conn.execute(
                """
                UPDATE follow_up_case
                   SET status = 'DONE', closed_at = now(), updated_at = now()
                 WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                   AND status = 'OPEN'
                """,
                cid,
                oid,
            )
            await record_event(
                conn,
                event_type="result.approved",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}

    # ------------------------------------------------------------------
    # Đối tác: hai trạng thái "Chờ lấy mẫu" → "Đã lấy mẫu" → (tải kết quả)
    # ------------------------------------------------------------------

    async def viec_doi_tac(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Việc trên bàn đối tác, gom theo khách.

        Hai loại xét nghiệm (Tuyền 16/09/2026: *"cả 2, tuỳ loại xét nghiệm"*):
          * ĐỐI TÁC TỰ LẤY MẪU (`service_price.doi_tac_lay_mau`) — hiện ngay từ
            lúc bác sĩ duyệt, trạng thái "Chờ lấy mẫu", đối tác bấm "Đã lấy mẫu".
          * ĐIỀU DƯỠNG LẤY — chỉ hiện SAU khi điều dưỡng bấm xong ở phòng Lấy
            mẫu; trước đó ống máu còn chưa có, đối tác chẳng có gì để nhận.
        Có kết quả (tệp đầu tiên) là rời bàn — duyệt và gửi là việc bác sĩ, CSKH.
        """
        if not identity.co_vai((ClinicRole.PARTNER, ClinicRole.MANAGEMENT)):
            raise SafetyGateError("Màn này chỉ dành cho đối tác.")
        rows = await self._pool.fetch(
            """
            SELECT o.id::text AS chi_dinh_id, o.service_code, o.exec_status,
                   coalesce(sp.name, o.service_name) AS ten_dich_vu,
                   coalesce(sp.doi_tac_lay_mau, false) AS doi_tac_lay_mau,
                   p.full_name AS ten_khach, p.patient_code AS ma_khach,
                   p.clinic_patient_id::text AS clinic_patient_id,
                   v.appointment_id::text AS appointment_id,
                   o.created_at, o.finished_at, o.ket_qua_luc,
                   o.doi_tac_cho_tai_lieu_luc
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
               AND n.lam_ben_ngoai
              LEFT JOIN LATERAL (
                   SELECT s.name, s.doi_tac_lay_mau FROM service_price s
                    WHERE s.clinic_id = o.clinic_id
                      AND s.service_code = o.service_code AND s.active
                    ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
             WHERE o.clinic_id = $1::uuid
               -- Đã gửi kết quả HÔM NAY vẫn ở lại bàn (mục "Đã gửi") để đối
               -- tác thấy mình vừa gửi gì và gửi thêm tài liệu nếu còn thiếu.
               AND (o.ket_qua_luc IS NULL
                    OR (o.ket_qua_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
               AND o.created_at > now() - interval '60 days'
               AND (
                    o.exec_status = 'performed'
                 OR (coalesce(sp.doi_tac_lay_mau, false)
                     AND o.exec_status IN ('authorized', 'assigned', 'in_progress'))
               )
             -- Việc CHƯA gửi trước, mới nhất trước: trần 300 dòng không bao giờ
             -- được cắt mất một chỉ định vừa gửi sang chỉ vì còn tồn việc cũ.
             ORDER BY (o.ket_qua_luc IS NOT NULL), o.created_at DESC, o.id
             LIMIT 300
            """,
            identity.clinic_id,
        )
        khach: dict[str, dict[str, Any]] = {}
        for r in rows:
            k = khach.setdefault(
                r["clinic_patient_id"],
                {
                    "clinic_patient_id": r["clinic_patient_id"],
                    "ten_khach": r["ten_khach"],
                    "ma_khach": r["ma_khach"],
                    "cho_tu": None,
                    "viec": [],
                },
            )
            luc = _iso(r["created_at"])
            if luc and (k["cho_tu"] is None or luc < k["cho_tu"]):
                k["cho_tu"] = luc
            k["viec"].append(
                {
                    "chi_dinh_id": r["chi_dinh_id"],
                    "ten_dich_vu": r["ten_dich_vu"],
                    "appointment_id": r["appointment_id"],
                    "chi_dinh_luc": luc,
                    "trang_thai": trang_thai_doi_tac(
                        exec_status=r["exec_status"],
                        cho_tai_lieu=r["doi_tac_cho_tai_lieu_luc"] is not None,
                        co_ket_qua=r["ket_qua_luc"] is not None,
                    ),
                    "lay_mau_luc": _iso(r["finished_at"]),
                    "cho_tai_lieu_luc": _iso(r["doi_tac_cho_tai_lieu_luc"]),
                    "ket_qua_luc": _iso(r["ket_qua_luc"]),
                }
            )
        con_viec = sum(1 for r in rows if r["ket_qua_luc"] is None)
        # Người đến trước lên trước — truy vấn đã lấy mới nhất trước cho trần.
        ds = sorted(khach.values(), key=lambda k: k["cho_tu"] or "")
        for k in ds:
            k["viec"].sort(key=lambda v: v["chi_dinh_luc"] or "")
        return {"khach": ds, "so_viec": con_viec}

    async def doi_tac_cho_tai_lieu(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đối tác bấm "Chờ tài liệu": đã nhận mẫu, đang làm, sẽ gửi tài liệu.

        Tuyền 17/09/2026: *"phải có nút cho họ là chờ tài liệu, up tài liệu… như
        vậy trạng thái mới đồng bộ về cho cskh"*. Chỉ bấm được khi mẫu đã có
        (performed); bấm lại không đổi mốc đầu tiên.
        """
        if not identity.co_vai((ClinicRole.PARTNER, ClinicRole.MANAGEMENT)):
            raise SafetyGateError("Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            o = await conn.fetchrow(
                """
                SELECT o.visit_id::text AS visit_id, o.exec_status,
                       o.doi_tac_cho_tai_lieu_luc, o.ket_qua_luc
                  FROM service_order o
                  JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                   AND n.lam_ben_ngoai
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            if o is None:
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            if o["ket_qua_luc"] is not None or o["doi_tac_cho_tai_lieu_luc"]:
                return {"ok": True, "already": True}
            if o["exec_status"] != "performed":
                raise LuotKhamConflictError(
                    "SAMPLE_NOT_READY", "Chưa có mẫu — bấm “Đã lấy mẫu” trước."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET doi_tac_cho_tai_lieu_luc = now(),
                       doi_tac_cho_tai_lieu_boi = $3::uuid,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await record_event(
                conn,
                event_type="partner.awaiting_documents",
                aggregate_type="visit",
                aggregate_id=o["visit_id"],
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": o["visit_id"], "order_id": oid},
            )
        return {"ok": True, "already": False}

    async def doi_tac_da_lay_mau(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đối tác bấm "Đã lấy mẫu" cho xét nghiệm họ tự lấy."""
        if not identity.co_vai((ClinicRole.PARTNER, ClinicRole.MANAGEMENT)):
            raise SafetyGateError("Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await conn.fetchval(
                """
                SELECT o.visit_id::text
                  FROM service_order o
                  JOIN node_definition n
                    ON n.clinic_id = o.clinic_id AND n.code = o.node_code
                   AND n.lam_ben_ngoai
                  JOIN service_price sp
                    ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
                   AND sp.doi_tac_lay_mau
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                """,
                cid,
                oid,
            )
            if vid is None:
                # Một câu cho cả "không có" lẫn "không phải việc đối tác tự lấy".
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            await self._lock_visit(conn, cid, vid)
            trang_thai = await conn.fetchval(
                "SELECT exec_status FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            if trang_thai == "performed":
                return {"ok": True, "already": True}
            if trang_thai not in ("authorized", "assigned", "in_progress"):
                raise LuotKhamConflictError(
                    "ORDER_NOT_OPEN", "Việc này không còn chờ lấy mẫu."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'performed', performed_by = $3::uuid,
                       room_id = coalesce(room_id, (
                           SELECT r.id FROM clinic_room r
                             JOIN clinic_room_node rn
                               ON rn.room_id = r.id AND rn.clinic_id = r.clinic_id
                            WHERE r.clinic_id = $1::uuid AND r.la_doi_tac
                              AND r.is_active AND rn.node_code = service_order.node_code
                            ORDER BY r.sort LIMIT 1)),
                       assigned_by = coalesce(assigned_by, $3::uuid),
                       assigned_at = coalesce(assigned_at, now()),
                       started_at = coalesce(started_at, now()), finished_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                       updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND ref_id = $3::uuid AND reason = 'SERVICE'
                   AND status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                oid,
            )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.performed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid, "doi_tac_lay_mau": True},
            )
        return {"ok": True, "order_id": oid}

    # ------------------------------------------------------------------
    # C8 / C9 — người thực hiện bắt đầu và kết thúc dịch vụ
    # ------------------------------------------------------------------

    async def _order_for_performer(
        self, conn: asyncpg.Connection, identity: StaffIdentity, oid: str
    ) -> asyncpg.Record:
        o = await conn.fetchrow(
            """
            SELECT o.exec_status, o.node_code, o.performed_by::text AS performed_by,
                   n.actor_roles
              FROM service_order o
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
             WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
               FOR UPDATE OF o
            """,
            identity.clinic_id,
            oid,
        )
        assert o is not None
        duoc = set(o["actor_roles"] or []) | {v.value for v in HO_TRO_PHONG}
        if not set(identity.ds_vai()) & duoc:
            raise SafetyGateError("Vai của bạn không thực hiện được dịch vụ này.")
        return o

    async def start_service(
        self, *, order_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if (
                o["exec_status"] == "in_progress"
                and o["performed_by"] == identity.staff_id
            ):
                return {"ok": True, "order_id": oid, "already": True}
            if o["exec_status"] != "assigned":
                raise LuotKhamConflictError(
                    "ORDER_NOT_ASSIGNED", "Dịch vụ này chưa được điều phối vào phòng."
                )
            entry = await conn.fetchrow(
                """
                SELECT id::text AS id, status FROM queue_entry
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                   FOR UPDATE
                """,
                cid,
                vid,
                oid,
            )
            if (
                entry is None
                or entry["status"] not in ("waiting", "called")
                or await self._visit_busy(conn, cid, vid)
            ):
                raise LuotKhamConflictError(
                    "PATIENT_BUSY",
                    "Khách đang ở một bước khác, chưa làm dịch vụ này được.",
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'in_progress', performed_by = $3::uuid,
                      started_at = now(),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
            )
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                " version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                entry["id"],
            )
            await self._block_others(conn, cid, vid, entry["id"])
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.started",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}

    async def complete_service(
        self,
        *,
        order_id: str,
        performed: bool,
        reason: str | None,
        result_note: str | None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        _require(identity, PERFORMER_ROLES, "Vai của bạn không thực hiện dịch vụ.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly_do = (reason or "").strip() if isinstance(reason, str) else ""
        ghi = (result_note or "").strip() if isinstance(result_note, str) else ""
        if not performed and not ly_do:
            raise ValidationError("Ghi lý do không thực hiện được dịch vụ.")
        if len(ghi) > 20000 or len(ly_do) > 2000:
            raise ValidationError("Nội dung quá dài.")
        async with self._pool.acquire() as conn, conn.transaction():
            vid = await self._visit_of(conn, "service_order", cid, oid)
            await self._lock_visit(conn, cid, vid)
            o = await self._order_for_performer(conn, identity, oid)
            if o["exec_status"] != "in_progress":
                raise LuotKhamConflictError(
                    "ORDER_NOT_IN_PROGRESS", "Dịch vụ này chưa bắt đầu hoặc đã xong."
                )
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = $3, finished_at = now(),
                       -- Bác sĩ bấm Xong ⇒ bác sĩ là người thực hiện, kể cả khi
                       -- điều dưỡng đi kèm đã bấm Bắt đầu.
                       performed_by = CASE WHEN $6 THEN $7::uuid
                                           ELSE performed_by END,
                       result_note = nullif($4, ''),
                       ket_qua_luc = CASE WHEN nullif($4, '') IS NOT NULL
                                          THEN coalesce(ket_qua_luc, now())
                                          ELSE ket_qua_luc END,
                          not_performed_reason = nullif($5, ''),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                "performed" if performed else "not_performed",
                ghi,
                ly_do,
                bool(set(identity.ds_vai()) & set(o["actor_roles"] or [])),
                identity.staff_id,
            )
            if not performed:
                # Không làm được thì sẽ không có kết quả: việc theo dõi "chờ kết
                # quả" của chỉ định này huỷ (lý do nằm ở not_performed_reason),
                # không để mồ côi. Bác sĩ quyết tiếp qua vòng đọc / tái khám.
                await conn.execute(
                    """
                    UPDATE follow_up_case
                       SET status = 'CANCELLED', closed_at = now(),
                           updated_at = now()
                     WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                       AND status = 'OPEN'
                    """,
                    cid,
                    oid,
                )
            await conn.execute(
                """
                UPDATE queue_entry
                   SET status = 'done', done_at = now(), version = version + 1,
                      updated_at = now()
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    AND ref_id = $3::uuid
                   AND reason = 'SERVICE' AND status NOT IN ('done', 'left',
                      'cancelled')
                """,
                cid,
                vid,
                oid,
            )
            await self._release_blocked(conn, cid, vid)
            await self._evaluate_rounds(conn, identity, vid)
            await self._ket_thuc_neu_xong(conn, identity, vid)
            await self._cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await record_event(
                conn,
                event_type="service.performed"
                if performed
                else "service.not_performed",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid},
            )
        return {"ok": True, "order_id": oid}


def trang_thai_doi_tac(
    *, exec_status: str, cho_tai_lieu: bool, co_ket_qua: bool
) -> str:
    """Trạng thái một việc trên bàn đối tác — một chỗ tính cho cả đối tác lẫn CSKH.

    DA_GUI_KET_QUA > CHO_TAI_LIEU > DA_LAY_MAU > CHO_LAY_MAU.
    """
    if co_ket_qua:
        return "DA_GUI_KET_QUA"
    if cho_tai_lieu:
        return "CHO_TAI_LIEU"
    if exec_status == "performed":
        return "DA_LAY_MAU"
    return "CHO_LAY_MAU"
