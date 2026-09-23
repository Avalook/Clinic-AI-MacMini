"""Thực hiện dịch vụ — Bắt đầu, Xong, Không làm được, Gián đoạn, Chuẩn bị làm lại.

Contract: `docs/ai/lifecycle-v1/ClinicAI-EXECUTION-v1.md` (đóng băng 22/09/2026).

NĂM CÂU HỎI mà module này trả lời, và chỉ nó được trả lời:

    đã thực sự bắt đầu chưa · lần làm nào đang chạy · đã xong thật chưa ·
    chưa bắt đầu mà không làm được · đã bắt đầu mà phải dừng giữa chừng

Nó KHÔNG chọn dịch vụ, KHÔNG thu tiền, KHÔNG xếp phòng, KHÔNG quyết kết quả.

MỘT CHỈ ĐỊNH, NHIỀU LẦN LÀM. Máy siêu âm hỏng lúc 10:05 thì lần làm #1 dừng, lần
#2 ở phòng khác bắt đầu lúc 10:18. Luật cũ "mỗi chỉ định chỉ được bắt đầu một
lần" sai với đời thật; luật đúng là **mỗi LẦN LÀM chỉ được bắt đầu một lần**.

`attempt_id` BẮT BUỘC khi bấm Xong hoặc Gián đoạn. Đây không phải thủ tục thừa:
một request mạng cũ của lần làm #1 tới muộn không được phép đóng lần làm #2 đang
chạy — hệ thống nhìn `attempt_id` và từ chối.

BỐN THỨ KHÔNG BAO GIỜ TỰ ĐỘNG khi dừng giữa chừng hay không làm được: không tự
hoàn tiền, không tự đánh dấu đã xong, không tự mở lần làm mới, không tự chọn
phòng khác. Mỗi cái là một quyết định của người, và có lệnh riêng.

"CHỜ LÀM" KHÔNG PHẢI MỘT GIÁ TRỊ ĐƯỢC LƯU. Lược đồ chỉ nhận PENDING ·
IN_PROGRESS · COMPLETED · CANCELLED · NOT_PERFORMED · INTERRUPTED. "Chờ làm"
(`WAITING`) là kết luận TÍNH RA: đang PENDING + khách đã chọn + tiền đã đủ + đã
xếp phòng + không có lần làm nào đang chạy. Lưu nó thành một giá trị riêng nghĩa
là Thu tiền và Xếp phòng cũng phải nhớ ghi execution_status — và ngày nào một
trong hai quên thì hàng chờ sai mà không ai biết.

KHÔNG SUY "AI LÀM CHUYÊN MÔN" TỪ AI BẤM NÚT. Bảng lần làm ghi `started_by`,
`completed_by`, `interrupted_by` — đó là ai thao tác trên hệ thống. Ai chịu
trách nhiệm chuyên môn là dữ liệu khác, ở phiếu kết quả (`thuc_hien_boi`).
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.events.catalogue import (
    DichVuDaBatDau,
    DichVuDaXong,
    DichVuGianDoan,
    DichVuKhongLam,
    DichVuSanSangLamLai,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.finance_gate import can_start
from clinicai.services.luot_kham_service import LuotKhamConflictError, LuotKhamService

QUYEN_BAT_DAU = "service.execute.start"
QUYEN_XONG = "service.execute.complete"
QUYEN_KHONG_LAM = "service.execute.not_performed"
QUYEN_GIAN_DOAN = "service.execute.interrupt"
QUYEN_LAM_LAI = "service.execute.retry"

#: Vì sao KHÔNG bắt đầu được. Sau khi đã bắt đầu thì dùng lý do gián đoạn.
LY_DO_KHONG_LAM = frozenset(
    {
        "PATIENT_DECLINED_AT_ROOM",
        "CLINICAL_CONTRAINDICATION_BEFORE_START",
        "EQUIPMENT_UNAVAILABLE_BEFORE_START",
        "STAFF_UNAVAILABLE",
        "OTHER",
    }
)

#: Vì sao đang làm mà phải dừng.
LY_DO_GIAN_DOAN = frozenset(
    {
        "EQUIPMENT_FAILURE",
        "PATIENT_REQUEST",
        "CLINICAL_SAFETY",
        "TECHNICAL_FAILURE",
        "STAFF_UNAVAILABLE",
        "OTHER",
    }
)


class ServiceExecutionService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        # Dùng nhờ hai thứ của kernel cũ: biên nhận lệnh và con trỏ "khách đang
        # ở đâu". Cả hai là CƠ CHẾ DÙNG CHUNG, chép lại là tạo bản thứ hai sẽ
        # lệch.
        self._luot = LuotKhamService(pool)

    # ------------------------------------------------------------------
    async def bat_dau(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        expected_routing_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`StartService` — mở một lần làm mới cho chỉ định này."""
        cid = identity.clinic_id
        payload = {
            "order_id": order_id,
            "exec_rev": expected_execution_revision,
            "routing_rev": expected_routing_revision,
        }
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_BAT_DAU)
            don, vid = await self._khoa_don(conn, cid, order_id)

            cached = await LuotKhamService._receipt_get(
                conn, identity, "service.start", idempotency_key, payload
            )
            if cached is not None:
                return cached

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            self._doi_revision(don, expected_routing_revision, "routing_revision")

            if don["selection_status"] != "SELECTED":
                raise LuotKhamConflictError(
                    "SELECTION_NOT_CONFIRMED", "Khách chưa xác nhận làm dịch vụ này."
                )
            if don["routing_status"] != "ASSIGNED":
                raise LuotKhamConflictError(
                    "ROUTING_NOT_ASSIGNED", "Chỉ định chưa được xếp phòng."
                )
            # "Chờ làm" tính ra chứ không lưu: đủ điều kiện dưới đây mới là chờ.
            if don["execution_status"] not in (None, "PENDING"):
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID",
                    f"Chỉ định đang ở trạng thái {don['execution_status']}.",
                )
            dang_chay = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS')",
                cid,
                order_id,
            )
            if dang_chay:
                raise LuotKhamConflictError(
                    "EXECUTION_ALREADY_RUNNING", "Đang có một lần làm chạy dở."
                )

            tien = await can_start(conn, cid, order_id)
            if tien is None or not tien.financially_ready:
                raise LuotKhamConflictError(
                    "FINANCE_NOT_READY",
                    "Chưa đủ điều kiện tài chính để bắt đầu.",
                )

            lan_truoc = await conn.fetchval(
                "SELECT COALESCE(max(attempt_no), 0) FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
                cid,
                order_id,
            )
            lan = await conn.fetchrow(
                """
                INSERT INTO service_execution_attempt
                    (clinic_id, service_order_id, attempt_no, room_id_snapshot,
                     routing_revision_snapshot, status, started_by, started_at)
                VALUES ($1::uuid, $2::uuid, $3, $4::uuid, $5, 'IN_PROGRESS',
                        $6::uuid, now())
                RETURNING id::text, attempt_no, started_at
                """,
                cid,
                order_id,
                int(lan_truoc) + 1,
                don["room_id"],
                don["routing_revision"],
                identity.staff_id,
            )

            if await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND status = 'serving' AND reason = 'SERVICE'"
                "   AND ref_id <> $3::uuid)",
                cid,
                vid,
                order_id,
            ):
                # Đang làm ở phòng khác thì không giành khách giữa chừng — phòng
                # kia bấm Xong (hay Dừng) trước.
                raise LuotKhamConflictError(
                    "PATIENT_BUSY", "Khách đang làm dịch vụ ở phòng khác."
                )
            moi = await self._doi_trang_thai(conn, cid, order_id, "IN_PROGRESS")
            # KHÁCH RỜI CHỖ CŨ SANG PHÒNG NÀY. Luồng chuẩn (Tuyền 23/09/2026):
            # "chỉ định đi chỗ khác = ĐỢI QUAY LẠI, không phải khám xong" — bác
            # sĩ chính còn mở phiên trong lúc khách đi siêu âm. Chỗ đang phục vụ
            # ở bàn bác sĩ (và mọi chỗ đang chờ khác) chuyển "đợi quay lại"
            # (blocked); phiên khám KHÔNG đổi. Làm xong ở phòng thì mở lại
            # (`_dong_hang_cho`). Trước bản này phòng không Bắt đầu được khi
            # phiên bác sĩ còn mở: Postgres chỉ cho MỘT chỗ 'serving' mỗi lượt.
            await conn.execute(
                "UPDATE queue_entry SET status = 'blocked',"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND status IN ('waiting', 'called', 'serving')"
                "   AND NOT (reason = 'SERVICE' AND ref_id = $3::uuid)",
                cid,
                vid,
                order_id,
            )
            # Khách đang ở trong phòng này: hàng chờ của phòng chuyển sang
            # "đang làm". Chỉ MỘT chỗ chờ được 'serving' trong một lượt — chính
            # Postgres giữ luật ấy, không phải Python. Chỗ chờ còn "đợi" (khách
            # vừa ở bàn bác sĩ, chưa có giờ vào hàng) lấy giờ vào hàng = bây giờ.
            await conn.execute(
                "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                "       eligible_at = coalesce(eligible_at, now()),"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid"
                "   AND reason = 'SERVICE'"
                "   AND status NOT IN ('done', 'left', 'cancelled')",
                cid,
                order_id,
            )
            # CON TRỎ "KHÁCH ĐANG Ở ĐÂU" — việc mà nút [Gọi vào] từng làm.
            #
            # Bỏ [Gọi vào] mà không bù chỗ này là dựng lại đúng sự cố 17/09/2026
            # ghi trong `_cap_nhat_vi_tri`: khám xong cả vòng rồi mà trưởng ca
            # vẫn thấy khách "đang ở Đo chỉ số", và quầy không đóng được lượt.
            # Bảng điều phối, TV phòng chờ và bước đóng lượt đều đọc con trỏ này.
            #
            # Trong CÙNG giao dịch với việc mở lần làm: hai thứ ấy hoặc cùng
            # đúng, hoặc cùng không xảy ra.
            await self._luot._cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="service.started",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuDaBatDau(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    room_id=str(don["room_id"]) if don["room_id"] else None,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )

            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "attempt_no": lan["attempt_no"],
                "execution_status": "IN_PROGRESS",
                "execution_revision": moi,
                "started_at": lan["started_at"].isoformat(),
            }
            await LuotKhamService._receipt_put(
                conn, identity, "service.start", idempotency_key, payload, vid, ket_qua
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def xong(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`CompleteService` — lần làm này đã xong.

        KHÔNG nhận nội dung kết quả: `service.completed` ≠ `result.ready`. Kết
        quả là việc của biểu mẫu (`form_instance`), một vòng đời riêng.
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_XONG)
            don, vid = await self._khoa_don(conn, cid, order_id)
            cached = await LuotKhamService._receipt_get(
                conn, identity, "service.complete", idempotency_key, payload
            )
            if cached is not None:
                return cached

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_dang_chay(conn, cid, order_id, attempt_id)

            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'COMPLETED', completed_by = $3::uuid,"
                "       completed_at = now(), updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "COMPLETED")
            await self._dong_hang_cho(conn, cid, order_id)

            await emit_event(
                conn,
                ten="service.completed",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuDaXong(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "COMPLETED",
                "execution_revision": moi,
            }
            await LuotKhamService._receipt_put(
                conn,
                identity,
                "service.complete",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def khong_lam(
        self,
        *,
        order_id: str,
        expected_execution_revision: int,
        ly_do: str,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`MarkServiceNotPerformed` — đã tới lượt mà cuối cùng không làm.

        Không sinh "lần làm giả": chưa ai bắt đầu thì không có lần làm nào.
        Tiền đã thu KHÔNG tự hoàn — hoàn tiền là quyết định của người, đi đường
        tài chính riêng.
        """
        if ly_do not in LY_DO_KHONG_LAM:
            raise ValidationError(f"Lý do không hợp lệ: {ly_do}.")
        if ly_do == "OTHER" and not (ghi_chu or "").strip():
            raise ValidationError("Chọn lý do Khác thì phải ghi rõ.")

        cid = identity.clinic_id
        payload = {"order_id": order_id, "ly_do": ly_do}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_KHONG_LAM)
            don, vid = await self._khoa_don(conn, cid, order_id)
            cached = await LuotKhamService._receipt_get(
                conn, identity, "service.not_performed", idempotency_key, payload
            )
            if cached is not None:
                return cached

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] not in (None, "PENDING"):
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID",
                    "Đã bắt đầu làm thì dùng Gián đoạn, không phải Không làm.",
                )
            da_tung_bat_dau = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid)",
                cid,
                order_id,
            )
            if da_tung_bat_dau:
                raise LuotKhamConflictError(
                    "EXECUTION_ALREADY_STARTED",
                    "Chỉ định này đã từng bắt đầu — dùng đường gián đoạn.",
                )

            moi = await self._doi_trang_thai(conn, cid, order_id, "NOT_PERFORMED")
            await self._dong_hang_cho(conn, cid, order_id)

            tien = await can_start(conn, cid, order_id)
            await emit_event(
                conn,
                ten="service.not_performed",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuKhongLam(
                    visit_id=vid,
                    service_order_id=order_id,
                    ly_do=ly_do,
                    execution_revision=moi,
                    # Đã thu tiền mà không làm: có người phải xử lý, nên nói rõ
                    # ngay trong sự kiện thay vì để bên nghe tự suy.
                    da_thu_tien=bool(tien and tien.finance_state == "PAID"),
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "execution_status": "NOT_PERFORMED",
                "execution_revision": moi,
                "can_doi_soat_tien": bool(tien and tien.finance_state == "PAID"),
            }
            await LuotKhamService._receipt_put(
                conn,
                identity,
                "service.not_performed",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def gian_doan(
        self,
        *,
        order_id: str,
        attempt_id: str,
        expected_execution_revision: int,
        ly_do: str,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`InterruptService` — đã bắt đầu nhưng không hoàn thành được."""
        if ly_do not in LY_DO_GIAN_DOAN:
            raise ValidationError(f"Lý do không hợp lệ: {ly_do}.")
        if ly_do == "OTHER" and not (ghi_chu or "").strip():
            raise ValidationError("Chọn lý do Khác thì phải ghi rõ.")

        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": attempt_id, "ly_do": ly_do}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_GIAN_DOAN)
            don, vid = await self._khoa_don(conn, cid, order_id)
            cached = await LuotKhamService._receipt_get(
                conn, identity, "service.interrupt", idempotency_key, payload
            )
            if cached is not None:
                return cached

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "IN_PROGRESS":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang được làm."
                )
            lan = await self._lan_dang_chay(conn, cid, order_id, attempt_id)

            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'INTERRUPTED', interrupted_by = $3::uuid,"
                "       interrupted_at = now(), interruption_reason_code = $4,"
                "       interruption_reason_note = $5, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
                identity.staff_id,
                ly_do,
                ghi_chu,
            )
            moi = await self._doi_trang_thai(conn, cid, order_id, "INTERRUPTED")
            await self._dong_hang_cho(conn, cid, order_id)

            await emit_event(
                conn,
                ten="service.interrupted",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuGianDoan(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=lan["id"],
                    attempt_no=lan["attempt_no"],
                    ly_do=ly_do,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "attempt_id": lan["id"],
                "execution_status": "INTERRUPTED",
                "execution_revision": moi,
            }
            await LuotKhamService._receipt_put(
                conn,
                identity,
                "service.interrupt",
                idempotency_key,
                payload,
                vid,
                ket_qua,
            )
        return ket_qua

    # ------------------------------------------------------------------
    async def chuan_bi_lam_lai(
        self,
        *,
        order_id: str,
        interrupted_attempt_id: str,
        expected_execution_revision: int,
        ghi_chu: str | None,
        identity: StaffIdentity,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """`PrepareServiceRetry` — người quyết định sẽ làm lại.

        Cố ý là một lệnh RIÊNG. Để `StartService` tự hiểu "gián đoạn thì bắt đầu
        lại luôn" là bỏ qua đúng những thứ phải có người quyết: bác sĩ đồng ý
        chưa, đổi phòng chưa, máy sửa chưa, khách còn muốn làm không.
        """
        cid = identity.clinic_id
        payload = {"order_id": order_id, "attempt_id": interrupted_attempt_id}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN_LAM_LAI)
            don, vid = await self._khoa_don(conn, cid, order_id)
            cached = await LuotKhamService._receipt_get(
                conn, identity, "service.retry", idempotency_key, payload
            )
            if cached is not None:
                return cached

            self._doi_revision(don, expected_execution_revision, "execution_revision")
            if don["execution_status"] != "INTERRUPTED":
                raise LuotKhamConflictError(
                    "EXECUTION_STATE_INVALID", "Chỉ định không đang ở trạng thái dừng."
                )
            lan_cuoi = await conn.fetchrow(
                "SELECT id::text, attempt_no, status FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY attempt_no DESC LIMIT 1",
                cid,
                order_id,
            )
            if lan_cuoi is None or lan_cuoi["id"] != interrupted_attempt_id:
                raise LuotKhamConflictError(
                    "EXECUTION_ATTEMPT_NOT_ACTIVE",
                    "Lần làm này không phải lần bị dừng gần nhất.",
                )

            # Về PENDING chứ không phải "WAITING": chờ làm là thứ tính ra, và
            # lúc này chỉ định lại đủ điều kiện để ai đó bấm Bắt đầu.
            moi = await self._doi_trang_thai(conn, cid, order_id, "PENDING")
            await emit_event(
                conn,
                ten="service.retry_prepared",
                clinic_id=cid,
                aggregate_id=order_id,
                so_ke_tiep=True,  # một dãy số cho cả chỉ định (emit.py)
                payload=DichVuSanSangLamLai(
                    visit_id=vid,
                    service_order_id=order_id,
                    attempt_id=interrupted_attempt_id,
                    execution_revision=moi,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            ket_qua = {
                "ok": True,
                "order_id": order_id,
                "execution_status": "PENDING",
                "cho_lam": True,
                "execution_revision": moi,
                "ghi_chu": ghi_chu,
            }
            await LuotKhamService._receipt_put(
                conn, identity, "service.retry", idempotency_key, payload, vid, ket_qua
            )
        return ket_qua

    # ------------------------------------------------------------------
    # Nhìn (chỉ đọc)
    # ------------------------------------------------------------------
    async def xem(self, *, order_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Màn phòng cần gì để bấm được 5 lệnh — trả đúng ngần ấy, không hơn.

        Không kiểm quyền ghi ở đây: đọc trạng thái một chỉ định trong phòng
        mình đang trực không phải hành động nguy hiểm, và **ẩn nút không phải
        bảo mật** — từng lệnh vẫn tự hỏi capability của nó khi bấm.

        Hai `revision` là thứ khiến màn này không phải đoán: bấm kèm số nào
        đang thấy, máy chủ so lại, lệch thì từ chối thay vì ghi đè người khác.
        """
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            don = await conn.fetchrow(
                # KHÔNG có `billing_status`: tiền là thứ SUY RA từ sổ thanh
                # toán (FinanceGate), không phải một cột trên chỉ định. Hỏi cột
                # ấy là hỏi một sự thật thứ hai về tiền — và hai sự thật về
                # tiền thì sớm muộn lệch nhau.
                "SELECT so.id::text AS order_id, so.service_code, so.service_name,"
                "       so.selection_status, so.routing_status,"
                "       so.execution_status, so.execution_revision,"
                "       so.routing_revision, so.room_id::text AS room_id,"
                "       so.visit_id::text AS visit_id"
                "  FROM service_order so"
                " WHERE so.clinic_id = $1::uuid AND so.id = $2::uuid",
                cid,
                order_id,
            )
            if don is None:
                raise ValidationError("Không tìm thấy chỉ định này.")

            lan = await conn.fetch(
                "SELECT a.id::text, a.attempt_no, a.status,"
                "       a.started_at, a.completed_at, a.interrupted_at,"
                "       a.interruption_reason_code,"
                "       nb.full_name AS bat_dau_boi, nx.full_name AS xong_boi"
                "  FROM service_execution_attempt a"
                "  LEFT JOIN staff nb ON nb.id = a.started_by"
                "  LEFT JOIN staff nx ON nx.id = a.completed_by"
                " WHERE a.clinic_id = $1::uuid AND a.service_order_id = $2::uuid"
                " ORDER BY a.attempt_no",
                cid,
                order_id,
            )
            mau = await conn.fetch(
                "SELECT m.ma, m.ten, m.nhom FROM dich_vu_mau_ket_qua d"
                "  JOIN ket_qua_mau m"
                "    ON m.clinic_id = d.clinic_id AND m.ma = d.mau AND m.active"
                " WHERE d.clinic_id = $1::uuid AND d.service_code = $2"
                " ORDER BY m.ten",
                cid,
                don["service_code"],
            )
            phieu = await conn.fetch(
                "SELECT id::text, form_id, trang_thai, revision, hoan_tat_luc"
                "  FROM form_instance"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                " ORDER BY tao_luc",
                cid,
                order_id,
            )

        dang_chay = next((d for d in lan if d["status"] == "IN_PROGRESS"), None)
        cuoi = lan[-1] if lan else None
        return {
            **{k: don[k] for k in don.keys()},
            "lan_dang_chay": dict(dang_chay) if dang_chay is not None else None,
            # Làm lại phải chỉ đúng lần đã dừng — màn không được tự đoán.
            "lan_da_dung": (
                dict(cuoi)
                if cuoi is not None and cuoi["status"] == "INTERRUPTED"
                else None
            ),
            "cac_lan": [dict(d) for d in lan],
            "mau_ket_qua": [dict(d) for d in mau],
            "phieu": [dict(d) for d in phieu],
            "ly_do_khong_lam": sorted(LY_DO_KHONG_LAM),
            "ly_do_gian_doan": sorted(LY_DO_GIAN_DOAN),
        }

    # ------------------------------------------------------------------
    # Dùng chung
    # ------------------------------------------------------------------
    @staticmethod
    async def _khoa_don(
        conn: asyncpg.Connection, clinic_id: str, order_id: str
    ) -> tuple[asyncpg.Record, str]:
        """Khoá lượt rồi khoá chỉ định — luôn cùng thứ tự, để không kẹt nhau."""
        vid = await LuotKhamService._visit_of(
            conn, "service_order", clinic_id, order_id
        )
        await LuotKhamService._lock_visit(conn, clinic_id, vid)
        don = await conn.fetchrow(
            "SELECT id::text, selection_status, routing_status, execution_status,"
            "       execution_revision, routing_revision, room_id"
            "  FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
            clinic_id,
            order_id,
        )
        if don is None:
            raise ValidationError("Không tìm thấy chỉ định này.")
        return don, vid

    @staticmethod
    def _doi_revision(don: asyncpg.Record, mong_doi: int, cot: str) -> None:
        """Màn đang mở có còn khớp hiện trạng không."""
        hien = int(don[cot] or 0)
        if hien != mong_doi:
            raise LuotKhamConflictError(
                "VERSION_CONFLICT",
                f"Màn hình đã cũ ({cot} {mong_doi} ≠ {hien}) — tải lại rồi bấm.",
            )

    @staticmethod
    async def _lan_dang_chay(
        conn: asyncpg.Connection, clinic_id: str, order_id: str, attempt_id: str
    ) -> asyncpg.Record:
        """Lần làm đang chạy, và phải đúng lần mà người bấm đang nhìn.

        Request cũ của lần làm trước tới muộn thì dừng ở đây, không đóng nhầm
        lần làm mới.
        """
        lan = await conn.fetchrow(
            "SELECT id::text, attempt_no FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
            "   AND id = $3::uuid AND status = 'IN_PROGRESS' FOR UPDATE",
            clinic_id,
            order_id,
            attempt_id,
        )
        if lan is None:
            raise LuotKhamConflictError(
                "EXECUTION_ATTEMPT_NOT_ACTIVE",
                "Lần làm này không còn đang chạy — tải lại màn hình.",
            )
        return lan

    @staticmethod
    async def _doi_trang_thai(
        conn: asyncpg.Connection, clinic_id: str, order_id: str, trang_thai: str
    ) -> int:
        moi = await conn.fetchval(
            "UPDATE service_order"
            "   SET execution_status = $3, execution_revision = execution_revision + 1,"
            "       updated_at = now()"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            " RETURNING execution_revision",
            clinic_id,
            order_id,
            trang_thai,
        )
        return int(moi)

    @staticmethod
    async def _dong_hang_cho(
        conn: asyncpg.Connection, clinic_id: str, order_id: str
    ) -> None:
        """Đóng chỗ chờ của chỉ định này; các chỗ chờ khác của lượt mở lại.

        Khách rời phòng → quay lại hàng bác sĩ chính (và các phòng khác đang
        đợi), tính giờ từ lúc quay lại — "đợi quay lại" của `bat_dau` kết thúc
        ở đây (Tuyền 23/09/2026).
        """
        vid = await conn.fetchval(
            "SELECT visit_id::text FROM service_order"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
            clinic_id,
            order_id,
        )
        await conn.execute(
            "UPDATE queue_entry SET status = 'done', done_at = now(),"
            "       version = version + 1, updated_at = now()"
            " WHERE clinic_id = $1::uuid AND ref_id = $2::uuid AND reason = 'SERVICE'"
            "   AND status NOT IN ('done', 'left', 'cancelled')",
            clinic_id,
            order_id,
        )
        if vid is not None:
            await LuotKhamService._release_blocked(conn, clinic_id, vid)


__all__ = [
    "LY_DO_GIAN_DOAN",
    "LY_DO_KHONG_LAM",
    "QUYEN_BAT_DAU",
    "QUYEN_GIAN_DOAN",
    "QUYEN_KHONG_LAM",
    "QUYEN_LAM_LAI",
    "QUYEN_XONG",
    "ServiceExecutionService",
]
