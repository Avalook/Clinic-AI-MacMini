"""Quầy lễ tân — hai mốc thời gian của một buổi khám.

VÌ SAO CÓ FILE NÀY. Màn hàng đợi tiếp nhận trước đây chỉ có các lệnh kernel thô
(``start`` / ``complete``) và không mốc nào đo được thời gian khám. Tuyền chốt
20/08/2026: hai nút tròn trên thanh tiến độ phải BẤM ĐƯỢC, và **bấm lại là hoàn
tác** — đúng cơ chế nút tròn của màn CSKH.

HAI QUỸ THỜI GIAN, KHÔNG PHẢI MỘT:

    checked_in_at    khách có mặt ở quầy   → mở đồng hồ CHỜ
    exam_started_at  khách được gọi vào    → đóng đồng hồ chờ, mở đồng hồ KHÁM

Nguyên văn: *"check-in lúc 18h, gọi khách vào lúc 18h10, thì thời gian khám tính
từ 18h10; check-in chỉ là mốc của buổi khám thôi"*. Gộp hai mốc làm một là mất
vĩnh viễn khả năng trả lời hai câu hỏi khác nhau — "phòng khám để khách chờ bao
lâu" và "một ca khám kéo dài bao lâu" — mà câu thứ hai chính là số liệu để sau
này xếp lịch cho đúng.

ĐI TỚI THÌ QUA KERNEL, LÙI LẠI THÌ KHÔNG.
``goi_vao_kham`` gọi thẳng ``WorkItemService.issue("complete")`` để mọi chốt an
toàn, mọi bản ghi ``work_item_event`` của kernel vẫn chạy đủ. Nhưng kernel KHÔNG
có lệnh mở lại (``start → complete`` là một chiều, cùng triết lý với COMPLETED
của lịch hẹn), nên đường lùi là một **hành động bù** viết ở đây, có vết trong
``event_log``. Tiền lệ: ``BookingService._cancel_visit_workflow`` cũng động thẳng
vào ``work_item`` khi hoàn tác check-in.

CHỐT AN TOÀN CỦA ĐƯỜNG LÙI (Tuyền chọn 20/08): chỉ lùi được khi **bác sĩ chưa
động vào**. Bác sĩ đã mở hồ sơ hay đã bắt đầu bước của mình rồi mà lễ tân kéo
khách về hàng chờ thì màn của bác sĩ mất người giữa chừng — hỏng nặng hơn cái
nhầm mà nút này định sửa.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.work_item_service import WorkItemService

#: Bước của chính quầy lễ tân. Việc thuộc workspace khác nghĩa là hồ sơ đã sang
#: tay người khác — điều dưỡng, bác sĩ, thu ngân.
WORKSPACE_QUAY = "bang_dieu_phoi"

#: Trạng thái việc chứng tỏ NGƯỜI KHÁC ĐÃ CHẠM vào lượt khám này.
DA_CHAM = ("IN_PROGRESS", "COMPLETED")


class ReceptionService:
    """Hai mốc thời gian của quầy, và đường lùi có chốt."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def goi_vao_kham(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Gọi khách vào khám: đóng bước tiếp nhận và MỞ ĐỒNG HỒ KHÁM.

        Thứ tự có chủ ý: kernel chạy TRƯỚC (nó là bên có quyền từ chối), rồi mới
        ghi mốc. Ghi mốc trước mà kernel từ chối thì database có một giờ khám cho
        một người chưa được gọi.
        """
        visit = await self._doc_luot(visit_id, identity)

        if visit["exam_started_at"] is not None:
            # Hai người cùng bấm, hoặc bấm lại sau khi mạng lag. Không phải lỗi.
            return {
                "ok": True,
                "da_goi_truoc_do": True,
                "exam_started_at": visit["exam_started_at"].isoformat(),
            }

        item = await self._viec_cua_quay(visit_id, identity)
        if item is not None and item["status"] in ("PENDING", "IN_PROGRESS"):
            if item["status"] == "PENDING":
                await WorkItemService(self._pool).issue(
                    work_item_id=str(item["id"]), command="start", identity=identity
                )
            await WorkItemService(self._pool).issue(
                work_item_id=str(item["id"]), command="complete", identity=identity
            )

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                moc = await conn.fetchval(
                    """
                    UPDATE public.visit
                       SET exam_started_at = now(),
                           exam_started_by = $3::uuid,
                           updated_at = now()
                     WHERE clinic_id = $1::uuid
                       AND visit_id = $2::uuid
                       AND exam_started_at IS NULL
                 RETURNING exam_started_at
                    """,
                    identity.clinic_id,
                    visit_id,
                    identity.staff_id,
                )
                if moc is None:
                    raise ConflictError("Lượt khám vừa được người khác gọi vào.")
                await self._ghi_su_kien(
                    conn,
                    visit=visit,
                    identity=identity,
                    event_type="reception.called_in",
                    payload={"exam_started_at": moc.isoformat()},
                )
        return {"ok": True, "exam_started_at": moc.isoformat()}

    async def hoan_tac_goi_vao_kham(
        self, *, visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Bấm nhầm thì rút lại — nếu bác sĩ chưa động vào.

        KHÔNG XOÁ DẤU VẾT: mốc giờ bị gỡ khỏi ``visit`` (nó là *hiện trạng*, không
        phải nhật ký), còn chuyện "đã gọi rồi lại rút" nằm lại trong ``event_log``
        — cùng triết lý với hoàn tác của CSKH.
        """
        visit = await self._doc_luot(visit_id, identity)
        if visit["exam_started_at"] is None:
            return {"ok": True, "chua_tung_goi": True}

        vuong = await self._ai_da_cham(visit_id, identity)
        if vuong:
            raise ValidationError(
                f"Không rút lại được: {vuong}. Nhờ Quản lý mở lại lượt khám."
            )

        item = await self._viec_cua_quay(visit_id, identity)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                cu = await conn.fetchval(
                    """
                    UPDATE public.visit
                       SET exam_started_at = NULL,
                           exam_started_by = NULL,
                           updated_at = now()
                     WHERE clinic_id = $1::uuid
                       AND visit_id = $2::uuid
                       AND exam_started_at IS NOT NULL
                 RETURNING exam_started_at
                    """,
                    identity.clinic_id,
                    visit_id,
                )
                if cu is None:
                    return {"ok": True, "chua_tung_goi": True}

                # HÀNH ĐỘNG BÙ, có vết. Kernel không có lệnh mở lại nên câu UPDATE
                # này là đường duy nhất — và nó phải kèm `work_item_event` để
                # nhật ký của kernel không có lỗ hổng không giải thích được.
                if item is not None and item["status"] == "COMPLETED":
                    await conn.execute(
                        """
                        UPDATE public.work_item
                           SET status = 'IN_PROGRESS',
                               finished_at = NULL,
                               version = version + 1,
                               updated_at = now()
                         WHERE clinic_id = $1::uuid AND id = $2::uuid
                           AND status = 'COMPLETED'
                        """,
                        identity.clinic_id,
                        item["id"],
                    )
                    await conn.execute(
                        """
                        INSERT INTO public.work_item_event (
                            clinic_id, work_item_id, command, from_status,
                            to_status, actor_staff_id, actor_role, metadata)
                        VALUES ($1::uuid, $2::uuid, 'reopen', 'COMPLETED',
                                'IN_PROGRESS', $3::uuid, $4,
                                jsonb_build_object('ly_do',
                                    'le tan hoan tac goi vao kham'))
                        """,
                        identity.clinic_id,
                        item["id"],
                        identity.staff_id,
                        identity.role.value,
                    )

                await self._ghi_su_kien(
                    conn,
                    visit=visit,
                    identity=identity,
                    event_type="reception.called_in_undone",
                    payload={"da_goi_luc": cu.isoformat()},
                )
        return {"ok": True, "da_rut_lai": True}

    # ── phần dùng chung ───────────────────────────────────────────────────
    async def _doc_luot(self, visit_id: str, identity: StaffIdentity) -> asyncpg.Record:
        row = await self._pool.fetchrow(
            """
            SELECT visit_id, clinic_patient_id, appointment_id, status,
                   checked_in_at, exam_started_at
              FROM public.visit
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            """,
            identity.clinic_id,
            visit_id,
        )
        if row is None:
            raise NotFoundError("Không tìm thấy lượt khám này.")
        if row["checked_in_at"] is None:
            raise ValidationError("Khách chưa check-in nên chưa gọi vào khám được.")
        return row

    async def _viec_cua_quay(
        self, visit_id: str, identity: StaffIdentity
    ) -> asyncpg.Record | None:
        """Việc đang mở của CHÍNH quầy lễ tân (workspace bang_dieu_phoi).

        Lấy việc chưa xong trước; không còn việc nào chưa xong thì lấy việc vừa
        xong gần nhất — đường lùi cần đúng nó để mở lại.
        """
        return await self._pool.fetchrow(
            """
            SELECT w.id, w.status, w.version, w.node_code
              FROM public.work_item w
              JOIN public.node_definition n
                ON n.clinic_id = w.clinic_id AND n.code = w.node_code
             WHERE w.clinic_id = $1::uuid
               AND w.visit_id = $2::uuid
               AND n.workspace = $3
               AND w.status <> 'CANCELLED'
             ORDER BY (w.status = 'COMPLETED'), w.updated_at DESC
             LIMIT 1
            """,
            identity.clinic_id,
            visit_id,
            WORKSPACE_QUAY,
        )

    async def _ai_da_cham(self, visit_id: str, identity: StaffIdentity) -> str | None:
        """Câu giải thích vì sao KHÔNG lùi được — hoặc None nếu lùi được.

        Trả về CÂU CHỮ chứ không phải cờ boolean: người ngồi quầy cần biết đang
        vướng ai để đi hỏi, chứ "không thao tác được" thì họ chỉ bấm lại lần nữa.
        """
        buoc = await self._pool.fetchval(
            """
            SELECT n.name
              FROM public.work_item w
              JOIN public.node_definition n
                ON n.clinic_id = w.clinic_id AND n.code = w.node_code
             WHERE w.clinic_id = $1::uuid
               AND w.visit_id = $2::uuid
               AND n.workspace <> $3
               AND w.status = ANY($4::text[])
             ORDER BY w.updated_at
             LIMIT 1
            """,
            identity.clinic_id,
            visit_id,
            WORKSPACE_QUAY,
            list(DA_CHAM),
        )
        if buoc:
            return f'bước "{buoc}" đã bắt đầu'

        co_ho_so = await self._pool.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM public.clinical_record
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            ) OR EXISTS (
                SELECT 1 FROM public.lab_result
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            ) OR EXISTS (
                SELECT 1 FROM public.ultrasound_record
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
            )
            """,
            identity.clinic_id,
            visit_id,
        )
        if co_ho_so:
            return "hồ sơ khám đã có dữ liệu"
        return None

    async def _ghi_su_kien(
        self,
        conn: asyncpg.Connection,
        *,
        visit: asyncpg.Record,
        identity: StaffIdentity,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Ghi vào sổ sự kiện TRONG CÙNG giao dịch với thay đổi.

        Cùng giao dịch nghĩa là: có thay đổi thì CHẮC CHẮN có sự kiện. Đây cũng
        là thứ đánh thức realtime và màn Lịch sử thao tác.
        """
        import json

        # KHÔNG có cột `actor_staff_id` trong `event_log` — người thực hiện đi
        # trong payload dưới khoá `by_staff_id`, đúng mẫu của sổ CSKH
        # (`tuong_tac_cskh_service.py:255`). Cột `source` nói sự kiện sinh ra từ
        # màn nào, để sau này lọc được "việc gì do quầy làm".
        await conn.execute(
            """
            INSERT INTO public.event_log
                (clinic_id, event_type, aggregate_type, aggregate_id,
                 payload, source, occurred_at)
            VALUES ($1::uuid, $2, 'visit', $3::uuid, $4::jsonb,
                    'reception.queue', now())
            """,
            identity.clinic_id,
            event_type,
            visit["visit_id"],
            json.dumps(
                {
                    **payload,
                    "by_staff_id": identity.staff_id,
                    "clinic_patient_id": str(visit["clinic_patient_id"]),
                    "appointment_id": (
                        str(visit["appointment_id"])
                        if visit["appointment_id"]
                        else None
                    ),
                }
            ),
        )
