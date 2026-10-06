"""HOÀN TÁC ở mọi thao tác (Tuyền 01/10/2026, sau buổi thực nghiệm thật 30/09).

    "Người dùng thao tác rối và hay làm sai, sai rồi thì không ấn lại được →
     cần nút HOÀN TÁC ở tất cả các việc để họ thao tác lại và sửa được …
     Không được để bất kể cái gì khoá hẳn."

Bốn lệnh của đợt này, mỗi lệnh là NGHỊCH ĐẢO đúng một lệnh đã có:

    ReopenConsultation    ↔ Khám xong / Hoàn tất / Xong tư vấn
    CancelServiceOrder    ↔ Chỉ định (bỏ chỉ định sai chỗ)
    UndoServiceCompletion ↔ Xong làm dịch vụ
    ReopenVisit           ↔ Check-out / Về giữa chừng
    RevokeResultApproval  ↔ Bác sĩ duyệt kết quả (cho phép gửi)

LUẬT CHUNG (mọi lệnh dưới đây):
  * Gác bằng ĐÚNG quyền của lệnh gốc (mở — ai làm được thì rút lại được).
  * Khoá lượt trước (cùng thứ tự với mọi lệnh khác của lượt), một giao dịch:
    đưa MỌI bảng liên quan về đúng chỗ — hàng chờ, vòng đọc, mốc "khám xong
    hẳn", lịch hẹn, con trỏ "khách đang ở đâu". Bảng nào đổi thì NOTIFY của bảng
    ấy làm mọi màn tự tải lại (`useNgheBang`) — quầy thu, bàn khám, phòng.
  * Ghi một sự kiện `domain_event` (ai, lúc nào, rút lại cái gì, lý do) → dòng
    thời gian Hành trình khách; và một dòng `event_log` cho màn Lịch sử thao tác.
  * Bấm hai lần = không làm gì thêm (trả `already`).
  * Ràng buộc nghiệp vụ THẬT (đã thu tiền, khách đã về, kết quả đã duyệt) KHÔNG
    khoá: máy chủ trả 409 `CAN_XAC_NHAN` kèm câu nói rõ hệ quả; màn mở hộp xác
    nhận, người bấm ghi lý do rồi gửi lại với `xac_nhan=True`.
  * Không xoá lịch sử: lần làm, phiếu thu, kết quả đã gõ đều giữ nguyên.

Phần TIỀN: bỏ một chỉ định ĐÃ THU không động vào phiếu thu (việc của nhóm thu
tiền — huỷ phiếu / hoàn tiền). Khoản ấy hiện ở quầy thu thành "tiền thừa"
(`tien_thua_cua_luot`) để thu ngân hoàn cho khách hoặc trừ vào dịch vụ khác.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import (
    ChiDinhDaHuy,
    DichVuHoanTacXong,
    KetQuaThuHoiDuyet,
    LuotMoLai,
    PhienKhamMoLai,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    chan_cho_khac,
    mo_cho_bi_chan,
    ve_lai_hang_phong,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    LuotKhamValidationError,
    khoa_luot,
    luot_cua,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

ORIGIN = "api:hoan-tac"

#: Mã lỗi khi hoàn tác chạm một ràng buộc nghiệp vụ thật — màn hỏi xác nhận.
CAN_XAC_NHAN = "CAN_XAC_NHAN"

LY_DO_TOI_THIEU = 5
LY_DO_TOI_DA = 500

#: Bước "Đóng lượt" của checklist lượt khám (cùng mã với checkout_service).
_BUOC_DONG_LUOT = "LUOTKHAM-15"


# ---------------------------------------------------------------------------
# Phần thuần
# ---------------------------------------------------------------------------


def doc_ly_do(raw: Any) -> str | None:
    """Lý do người bấm gõ: rỗng/rác → None (không ném); quá dài thì cắt."""
    if not isinstance(raw, str):
        return None
    ly = " ".join(raw.split())
    return ly[:LY_DO_TOI_DA] or None


def doi_xac_nhan(*, ly_do: str | None, xac_nhan: bool, hau_qua: list[str]) -> None:
    """Còn hệ quả nghiệp vụ mà người bấm chưa xác nhận (kèm lý do) → 409.

    `hau_qua` rỗng = hoàn tác vô hại, làm luôn. Có hệ quả mà thiếu xác nhận
    hoặc lý do quá ngắn → `CAN_XAC_NHAN` với câu nói rõ từng hệ quả; màn mở hộp
    xác nhận (components/ui) rồi gửi lại.
    """
    if not hau_qua:
        return
    if xac_nhan and ly_do and len(ly_do) >= LY_DO_TOI_THIEU:
        return
    raise LuotKhamConflictError(
        CAN_XAC_NHAN,
        " ".join(hau_qua),
        chi_tiet={
            "can_xac_nhan": True,
            "can_ly_do": True,
            "ly_do_toi_thieu": LY_DO_TOI_THIEU,
        },
    )


def _so(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def _tien(v: int) -> str:
    return f"{v:,}".replace(",", ".") + "đ"


# ---------------------------------------------------------------------------
# Nền dùng chung
# ---------------------------------------------------------------------------


async def _khoa_luot_bat_ky(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> asyncpg.Record:
    """Khoá dòng visit ở MỌI trạng thái sống (kể cả khách đã về / về giữa chừng).

    Hồ sơ đã KÝ (FINALIZED / AMENDED, TT13) thì trigger chặn mọi UPDATE của
    visit — nói thẳng đường đúng thay vì để Postgres ném lỗi khó hiểu.
    """
    row = await conn.fetchrow(
        "SELECT visit_id::text AS visit_id, status, closed_at, exam_completed_at,"
        "       appointment_id::text AS appointment_id"
        "  FROM visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   FOR UPDATE",
        clinic_id,
        visit_id,
    )
    if row is None:
        raise LuotKhamValidationError("VISIT_NOT_FOUND", "Không tìm thấy lượt khám.")
    if row["status"] in ("FINALIZED", "AMENDED"):
        raise LuotKhamConflictError(
            "VISIT_SIGNED",
            "Hồ sơ lượt này đã KÝ (khoá theo TT13) — sửa bằng đường đính chính"
            " hồ sơ, không hoàn tác được.",
        )
    return row


async def mo_lai_moc_kham_xong(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> bool:
    """Lượt đang "khám xong hẳn" mà nay còn việc → mở lại mốc ấy.

    Nghịch đảo của `LuotKhamService._ket_thuc_neu_xong`: bỏ
    `visit.exam_completed_at`, `encounter_flow.finished_at`, lịch hẹn
    COMPLETED → CHECKED_IN (lượt chưa check-out). Quầy thu / nhà thuốc /
    trạng thái "Khám xong" đọc đúng mốc này nên tự về "đang khám". Trả True khi
    có mở lại. Lượt đã check-out thì để nguyên (lịch theo lượt đã về).
    """
    da_ve = await conn.fetchval(
        "SELECT closed_at IS NOT NULL FROM visit"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        clinic_id,
        visit_id,
    )
    if da_ve:
        return False
    mo = await conn.execute(
        "UPDATE visit SET exam_completed_at = NULL, updated_at = now()"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND exam_completed_at IS NOT NULL",
        clinic_id,
        visit_id,
    )
    await conn.execute(
        "UPDATE encounter_flow SET finished_at = NULL, version = version + 1,"
        "       updated_at = now()"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        "   AND finished_at IS NOT NULL",
        clinic_id,
        visit_id,
    )
    hen = await conn.execute(
        """
        UPDATE appointment a
           SET status = 'CHECKED_IN', updated_at = now()
          FROM visit v
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
           AND a.id = v.appointment_id AND a.clinic_id = v.clinic_id
           AND a.status = 'COMPLETED'
        """,
        clinic_id,
        visit_id,
    )
    return bool(mo == "UPDATE 1" or hen == "UPDATE 1")


async def _mo_lai_luot_trong(
    conn: asyncpg.Connection, identity: StaffIdentity, visit: asyncpg.Record
) -> bool:
    """Phần ghi của ReopenVisit (đã khoá visit). Trả True khi lượt từng ở
    "về giữa chừng".

    Nghịch đảo của `CheckoutService.close`: bỏ `closed_at`, trạng thái
    INCOMPLETE → IN_PROGRESS, bước "Đóng lượt" về PENDING, chỗ chờ `left`
    (đóng lúc khách về) mở lại, lịch hẹn về CHECKED_IN nếu bác sĩ chưa khám
    xong hẳn. Việc đã HUỶ lúc đóng (work_item đời cũ) không dựng lại — hàng chờ
    đời mới (`queue_entry`) mới là thứ các màn đọc.
    """
    cid = identity.clinic_id
    vid = visit["visit_id"]
    ve_giua_chung = bool(visit["status"] == "INCOMPLETE")
    await conn.execute(
        """
        UPDATE visit
           SET closed_at = NULL, closed_by_staff_id = NULL,
               status = CASE WHEN status = 'INCOMPLETE' THEN 'IN_PROGRESS'
                             ELSE status END,
               incomplete_at = NULL, incomplete_reason = NULL,
               incomplete_by = NULL, updated_at = now()
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
        """,
        cid,
        vid,
    )
    await conn.execute(
        """
        UPDATE work_item
           SET status = 'PENDING', started_at = NULL, finished_at = NULL,
               updated_at = now()
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND node_code = $3 AND status = 'COMPLETED'
        """,
        cid,
        vid,
        _BUOC_DONG_LUOT,
    )
    await conn.execute(
        """
        UPDATE queue_entry
           SET status = 'waiting', eligible_at = now(), serving_at = NULL,
               called_at = NULL, version = version + 1, updated_at = now()
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status = 'left'
        """,
        cid,
        vid,
    )
    if visit["exam_completed_at"] is None:
        await conn.execute(
            """
            UPDATE appointment a
               SET status = 'CHECKED_IN', updated_at = now()
              FROM visit v
             WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
               AND a.id = v.appointment_id AND a.clinic_id = v.clinic_id
               AND a.status = 'COMPLETED'
            """,
            cid,
            vid,
        )
    return ve_giua_chung


async def tien_da_thu_cua_chi_dinh(
    conn: asyncpg.Connection, clinic_id: str, order_ids: list[str]
) -> dict[str, dict[str, int]]:
    """Chỉ định → {da_thu, da_hoan, cho_xac_minh} (phòng khám thu, kể cả món kèm).

    `da_thu` = lần thu ĐÃ THU (PAID), `cho_xac_minh` = chuyển khoản đang chờ,
    `da_hoan` = khoản hoàn đang làm / đã xong trên đúng các dòng ấy.
    """
    if not order_ids:
        return {}
    rows = await conn.fetch(
        """
        WITH dong AS (
            SELECT o.id::text AS order_id, bl.id AS line_id, bl.line_total,
                   c.status
              FROM service_order o
              JOIN payment_bill_line bl
                ON bl.clinic_id = o.clinic_id
               AND bl.billing_owner = 'CLINIC'
               AND ((bl.source_type = 'service_order' AND bl.source_id = o.id::text)
                    OR (bl.source_type = 'phu_thu' AND bl.source_id IN (
                        SELECT p.id::text FROM luot_phu_thu p
                         WHERE p.clinic_id = o.clinic_id
                           AND p.service_order_id = o.id)))
              JOIN payment_cycle c
                ON c.clinic_id = bl.clinic_id
               AND c.payment_cycle_id = bl.payment_cycle_id
             WHERE o.clinic_id = $1::uuid AND o.id::text = ANY($2::text[])
               AND c.status IN ('PAID', 'PENDING_VERIFICATION')
        )
        SELECT d.order_id,
               coalesce(sum(d.line_total) FILTER (WHERE d.status = 'PAID'), 0)
                   AS da_thu,
               coalesce(sum(d.line_total)
                        FILTER (WHERE d.status = 'PENDING_VERIFICATION'), 0)
                   AS cho_xac_minh,
               coalesce(sum((
                   SELECT sum(rl.amount)
                     FROM payment_refund_line rl
                     JOIN payment_refund r
                       ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
                    WHERE rl.clinic_id = $1::uuid
                      AND rl.payment_bill_line_id = d.line_id
                      AND r.status IN ('PENDING', 'COMPLETED'))), 0) AS da_hoan
          FROM dong d
         GROUP BY d.order_id
        """,
        clinic_id,
        order_ids,
    )
    return {
        r["order_id"]: {
            "da_thu": _so(r["da_thu"]),
            "da_hoan": _so(r["da_hoan"]),
            "cho_xac_minh": _so(r["cho_xac_minh"]),
        }
        for r in rows
    }


async def tien_thua_cua_luot(
    conn: asyncpg.Connection, clinic_id: str, visit_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """TIỀN THỪA ở quầy thu: đã thu cho dịch vụ nay đã BỎ chỉ định / không làm.

    Lượt → {"tong", "dong": [{order_id, ten, so_tien, ly_do, loai}]}. Số đã
    hoàn (đang làm hoặc xong) được trừ ra; về 0 thì không còn dòng. Không động
    vào phiếu thu — quầy hoàn cho khách (Hoàn tiền / Huỷ phiếu) hoặc trừ vào
    dịch vụ khác. Chỉ đọc.
    """
    if not visit_ids:
        return {}
    don = await conn.fetch(
        """
        SELECT o.id::text AS id, o.visit_id::text AS visit_id, o.service_name,
               o.exec_status, o.cancel_reason, o.not_performed_reason
          FROM service_order o
         WHERE o.clinic_id = $1::uuid AND o.visit_id::text = ANY($2::text[])
           AND o.exec_status IN ('cancelled', 'not_performed')
         ORDER BY o.updated_at, o.id
        """,
        clinic_id,
        visit_ids,
    )
    if not don:
        return {}
    tien = await tien_da_thu_cua_chi_dinh(conn, clinic_id, [r["id"] for r in don])
    out: dict[str, dict[str, Any]] = {}
    for r in don:
        t = tien.get(r["id"])
        if t is None:
            continue
        con = t["da_thu"] - t["da_hoan"]
        if con <= 0:
            continue
        huy = r["exec_status"] == "cancelled"
        muc = out.setdefault(r["visit_id"], {"tong": 0, "dong": []})
        muc["tong"] += con
        muc["dong"].append(
            {
                "order_id": r["id"],
                "ten": r["service_name"],
                "so_tien": con,
                "loai": "BO_CHI_DINH" if huy else "KHONG_LAM",
                "ly_do": (r["cancel_reason"] if huy else r["not_performed_reason"]),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Lệnh
# ---------------------------------------------------------------------------


class HoanTacService:
    """Bốn lệnh hoàn tác. Mỗi lệnh nằm ở module của lệnh gốc (modules.py)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── (a) Khám xong / Xong tư vấn → mở lại khám ─────────────────────────
    async def mo_lai_kham(
        self,
        *,
        consultation_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
    ) -> dict[str, Any]:
        """`ReopenConsultation` — hoàn tác "Khám xong" / "Hoàn tất" / "Xong tư vấn".

        Phiên về lại ĐANG KHÁM (khách về lại bàn bác sĩ), mọi thứ lần bấm ấy
        đã mở ra được thu về: vòng đọc kết quả vừa mở (chưa ai đọc), việc theo
        dõi vừa mở, mốc "khám xong hẳn" của lượt (quầy thu / nhà thuốc thôi coi
        là xong), lịch hẹn COMPLETED → CHECKED_IN. Phiên TƯ VẤN: hàng bác sĩ
        chính chưa nhận thì huỷ, khách về lại bàn tư vấn.

        Sửa đơn thuốc / chỉ định rồi bấm khám xong lại như thường.
        """
        from clinicai.services.luot_kham_service import LuotKhamService

        cid = identity.clinic_id
        con_id = _uuid(consultation_id, "Mã phiên khám không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            loai = await conn.fetchval(
                "SELECT kind FROM consultation WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid",
                cid,
                con_id,
            )
            if loai is None:
                raise LuotKhamValidationError(
                    "CONSULTATION_NOT_FOUND", "Không tìm thấy phiên khám này."
                )
            # Cùng quyền với lệnh gốc: tư vấn ↔ "Khám tư vấn", khám ↔ "Khám bệnh".
            await doi_quyen(
                conn,
                identity,
                (
                    "clinical.intake.perform"
                    if loai == "TU_VAN"
                    else "clinical.consult.perform"
                ),
                cau="Bạn không có quyền hoàn tác phiên khám này.",
            )
            vid = await luot_cua(conn, "consultation", cid, con_id)
            visit = await _khoa_luot_bat_ky(conn, cid, vid)
            c = await conn.fetchrow(
                "SELECT kind, status, round_no, outcome, completed_at"
                "  FROM consultation WHERE clinic_id = $1::uuid AND id = $2::uuid"
                "   FOR UPDATE",
                cid,
                con_id,
            )
            assert c is not None
            if c["status"] == "in_progress":
                return {"ok": True, "consultation_id": con_id, "already": True}
            if c["status"] != "completed":
                raise LuotKhamConflictError(
                    "CONSULTATION_NOT_COMPLETED",
                    "Phiên này chưa khám xong — không có gì để hoàn tác.",
                )
            round_no = int(c["round_no"])
            # Phiên SAU đã có người nhận (đang đọc / đã đọc kết quả, hay bác sĩ
            # chính đã bắt đầu sau tư vấn) → hoàn tác phiên sau trước. Đây là
            # thứ tự, không phải khoá: nút Hoàn tác của phiên sau nằm ngay đó.
            sau = await conn.fetchrow(
                "SELECT kind, status FROM consultation"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND round_no > $3 AND status IN ('in_progress', 'completed')"
                " ORDER BY round_no LIMIT 1",
                cid,
                vid,
                round_no,
            )
            if sau is not None:
                if c["kind"] == "TU_VAN":
                    cau = (
                        "Bác sĩ chính đã bắt đầu khám khách này — không đưa về tư"
                        " vấn được nữa. Ghi bổ sung vào phiếu khám của bác sĩ chính."
                    )
                else:
                    cau = (
                        "Khách đã vào đọc kết quả ở lần sau — bấm Hoàn tác ở lần"
                        " đọc kết quả ấy trước."
                    )
                raise LuotKhamConflictError("LATER_CONSULTATION_STARTED", cau)

            hau_qua: list[str] = []
            if visit["closed_at"] is not None:
                hau_qua.append(
                    "Khách đã check-out — mở lại khám sẽ mở lại cả lượt (khách"
                    " về lại hàng chờ)."
                )
            doi_xac_nhan(ly_do=ly, xac_nhan=xac_nhan, hau_qua=hau_qua)

            if visit["closed_at"] is not None:
                await _mo_lai_luot_trong(conn, identity, visit)
                await emit_event(
                    conn,
                    ten="visit.reopened",
                    clinic_id=cid,
                    aggregate_id=vid,
                    payload=LuotMoLai(
                        visit_id=vid,
                        tu_ve_giua_chung=visit["status"] == "INCOMPLETE",
                        ly_do=ly,
                    ),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )

            # 1. Phiên sau chưa ai nhận (đọc kết quả / bác sĩ chính sau tư vấn):
            #    thôi chờ. Phiên giữ dòng (đã huỷ) — mở lại sau sẽ đưa về chờ.
            await conn.execute(
                """
                WITH c AS (
                    UPDATE consultation
                       SET status = 'cancelled', version = version + 1,
                           updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND round_no > $3 AND status = 'queued'
                    RETURNING id
                )
                UPDATE queue_entry q
                   SET status = 'cancelled', version = q.version + 1,
                       updated_at = now()
                  FROM c
                 WHERE q.clinic_id = $1::uuid AND q.ref_id = c.id
                   AND q.status NOT IN ('done', 'left', 'cancelled')
                """,
                cid,
                vid,
                round_no,
            )
            if c["kind"] != "TU_VAN":
                # 2. Vòng đọc kết quả lần bấm ấy mở ra (chưa ai đọc): bỏ hẳn —
                #    khám xong lại sẽ mở vòng mới đúng theo chỉ định khi ấy.
                await conn.execute(
                    "DELETE FROM review_round WHERE clinic_id = $1::uuid"
                    " AND visit_id = $2::uuid AND round_no > $3",
                    cid,
                    vid,
                    round_no,
                )
                # 3. Việc theo dõi lần bấm ấy mở (cùng giao dịch → cùng giờ).
                if c["completed_at"] is not None:
                    await conn.execute(
                        """
                        UPDATE follow_up_case
                           SET status = 'CANCELLED', closed_at = now(),
                               updated_at = now()
                         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                           AND status = 'OPEN' AND created_at >= $3
                        """,
                        cid,
                        vid,
                        c["completed_at"],
                    )
            if c["kind"] == "REVIEW":
                # 4. Vòng đang đọc đã đóng lúc bấm → về "đang đọc".
                await conn.execute(
                    "UPDATE review_round SET status = 'in_review', closed_at = NULL,"
                    "       version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    "   AND round_no = $3 AND status = 'closed'",
                    cid,
                    vid,
                    round_no,
                )
            if c["kind"] == "TU_VAN":
                await conn.execute(
                    """
                    UPDATE encounter_flow
                       SET route_decision = 'TU_VAN',
                           route_reason = 'hoàn tác xong tư vấn — về lại bàn tư vấn',
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                    """,
                    cid,
                    vid,
                )

            # 5. Phiên về đang khám.
            await conn.execute(
                """
                UPDATE consultation
                   SET status = 'in_progress', outcome = NULL,
                       completed_by = NULL, completed_at = NULL,
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                con_id,
            )
            # 6. Khách về lại bàn của phiên: đang không ở phòng nào → "đang
            #    khám" ngay (nút Hoàn tất hiện lại); đang ở phòng khác → chờ ở
            #    hàng bàn khám (bấm Bắt đầu là tiếp tục).
            ban = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND status = 'serving'"
                " AND ref_id <> $3::uuid)",
                cid,
                vid,
                con_id,
            )
            cho = await conn.fetchval(
                "SELECT id::text FROM queue_entry WHERE clinic_id = $1::uuid"
                " AND visit_id = $2::uuid AND ref_id = $3::uuid"
                " ORDER BY (status NOT IN ('done', 'left', 'cancelled')) DESC,"
                "          updated_at DESC LIMIT 1",
                cid,
                vid,
                con_id,
            )
            if cho is not None:
                await conn.execute(
                    """
                    UPDATE queue_entry
                       SET status = $3, done_at = NULL,
                           serving_at = CASE WHEN $3 = 'serving' THEN now()
                                             ELSE serving_at END,
                           eligible_at = CASE WHEN $3 = 'waiting' THEN now()
                                              ELSE coalesce(eligible_at, now()) END,
                           version = version + 1, updated_at = now()
                     WHERE clinic_id = $1::uuid AND id = $2::uuid
                    """,
                    cid,
                    cho,
                    "waiting" if ban else "serving",
                )
                if not ban:
                    await chan_cho_khac(conn, cid, vid, cho)
            # 7. Mốc "khám xong hẳn" của lượt.
            mo_moc = await mo_lai_moc_kham_xong(conn, cid, vid)
            await LuotKhamService(pool=None)._evaluate_rounds(conn, identity, vid)
            await cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="consultation.reopened",
                clinic_id=cid,
                aggregate_id=con_id,
                payload=PhienKhamMoLai(
                    visit_id=vid,
                    consultation_id=con_id,
                    loai=c["kind"],
                    ket_qua_cu=c["outcome"],
                    mo_lai_kham_xong=mo_moc,
                    ly_do=ly,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type="consult.reopened",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "consultation_id": con_id,
                    "kind": c["kind"],
                    "outcome_cu": c["outcome"],
                },
            )
        return {
            "ok": True,
            "consultation_id": con_id,
            "visit_id": vid,
            "mo_lai_kham_xong": mo_moc,
        }

    # ── (b) Chỉ định → bỏ chỉ định ────────────────────────────────────────
    async def huy_chi_dinh(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
    ) -> dict[str, Any]:
        """`CancelServiceOrder` — bỏ một chỉ định (chỉ định sai chỗ / đổi ý).

        CHƯA THU: huỷ ngay — hoá đơn quầy do máy chủ dựng lại nên tự bớt dòng
        ấy; chỗ chờ phòng (nếu đã xếp) đóng; yêu cầu của vòng đọc bỏ. ĐÃ THU:
        không khoá — hỏi xác nhận + lý do, huỷ chỉ định, khoản đã thu thành
        "tiền thừa" ở quầy (hoàn cho khách hoặc trừ vào dịch vụ khác).

        Đang làm / đã làm xong thì hoàn tác ở phòng trước (Huỷ bắt đầu nhầm /
        Hoàn tác Xong) — bỏ chỉ định không được xoá ngầm việc người khác đang làm.
        """
        from clinicai.services.luot_kham_service import LuotKhamService
        from clinicai.services.so_sua_chi_dinh_service import (
            bao_bac_si_chinh,
            chan_ho_so_cu,
            dat_ngu_canh,
            dong_bo_moi_nhat,
        )

        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            # QUYỀN, không vai (Khối 2, 06/10/2026): ai có quyền chỉ định thì bỏ
            # được NGAY — trưởng ca, quản lý ngang bác sĩ chính; không chờ ai
            # duyệt. Bác sĩ chính được báo (kèm nút Hoàn tác) nếu người bỏ là
            # người khác.
            await doi_quyen(
                conn,
                identity,
                "clinical.order.place",
                cau="Bạn không có quyền chỉ định dịch vụ nên không bỏ được chỉ định.",
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await chan_ho_so_cu(conn, vid)
            await khoa_luot(conn, cid, vid, cho_phep_ve_giua_chung=True)
            o = await conn.fetchrow(
                "SELECT id::text, service_code, service_name, exec_status,"
                "       execution_status, room_id::text AS room_id"
                "  FROM service_order WHERE clinic_id = $1::uuid AND id = $2::uuid"
                "   FOR UPDATE",
                cid,
                oid,
            )
            assert o is not None
            if o["exec_status"] == "cancelled":
                return {"ok": True, "order_id": oid, "already": True}
            if "IN_PROGRESS" in (o["execution_status"], str(o["exec_status"]).upper()):
                raise LuotKhamConflictError(
                    "ORDER_IN_PROGRESS",
                    "Dịch vụ đang làm ở phòng — phòng bấm “Huỷ bắt đầu nhầm” trước,"
                    " rồi bỏ chỉ định.",
                )
            if o["execution_status"] == "COMPLETED" or o["exec_status"] == "performed":
                raise LuotKhamConflictError(
                    "ORDER_PERFORMED",
                    "Dịch vụ đã làm xong — phòng bấm “Hoàn tác” ở dòng “Đã xong”"
                    " trước, rồi bỏ chỉ định.",
                )
            tien = (await tien_da_thu_cua_chi_dinh(conn, cid, [oid])).get(oid) or {
                "da_thu": 0,
                "da_hoan": 0,
                "cho_xac_minh": 0,
            }
            thua = max(tien["da_thu"] - tien["da_hoan"], 0)
            hau_qua: list[str] = []
            if thua > 0:
                hau_qua.append(
                    f"“{o['service_name']}” đã thu {_tien(thua)} — bỏ chỉ định thì"
                    " khoản này thành TIỀN THỪA ở quầy thu (hoàn cho khách hoặc trừ"
                    " vào dịch vụ khác)."
                )
            if tien["cho_xac_minh"] > 0:
                hau_qua.append(
                    f"Có khoản chuyển khoản {_tien(tien['cho_xac_minh'])} đang chờ"
                    " xác minh cho dịch vụ này — quầy thu xử lý sau khi bỏ."
                )
            doi_xac_nhan(ly_do=ly, xac_nhan=xac_nhan, hau_qua=hau_qua)

            # Sổ sửa chỉ định ghi bằng trigger trong chính lệnh UPDATE dưới —
            # đặt người bấm / vai đang dùng / lý do cho nó.
            await dat_ngu_canh(conn, identity, ly_do=ly)
            await conn.execute(
                """
                UPDATE service_order
                   SET exec_status = 'cancelled', execution_status = 'CANCELLED',
                       cancelled_by = $3::uuid,
                       cancel_reason = coalesce($4, 'Bỏ chỉ định (hoàn tác)'),
                       version = version + 1, updated_at = now()
                 WHERE clinic_id = $1::uuid AND id = $2::uuid
                """,
                cid,
                oid,
                identity.staff_id,
                ly,
            )
            # Chỗ chờ ở phòng (đã xếp) → đóng; khách không còn ở hàng phòng ấy.
            await conn.execute(
                "UPDATE queue_entry SET status = 'cancelled', version = version + 1,"
                "       updated_at = now()"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                "   AND reason = 'SERVICE' AND ref_id = $3::uuid"
                "   AND status NOT IN ('done', 'left', 'cancelled')",
                cid,
                vid,
                oid,
            )
            # Yêu cầu của vòng đọc chưa đóng: bỏ — không còn gì để chờ.
            await conn.execute(
                """
                DELETE FROM round_requirement q
                 USING review_round r
                 WHERE q.clinic_id = $1::uuid AND q.service_order_id = $2::uuid
                   AND r.clinic_id = q.clinic_id AND r.id = q.round_id
                   AND r.status <> 'closed'
                """,
                cid,
                oid,
            )
            await conn.execute(
                "UPDATE follow_up_case SET status = 'CANCELLED', closed_at = now(),"
                "       updated_at = now()"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'OPEN'",
                cid,
                oid,
            )
            so_id = await dong_bo_moi_nhat(conn, service_order_id=oid)
            da_bao = await bao_bac_si_chinh(conn, identity, so_id)
            luot = LuotKhamService(pool=None)
            await mo_cho_bi_chan(conn, cid, vid)
            await luot._evaluate_rounds(conn, identity, vid)
            # Bỏ dịch vụ cuối cùng còn chờ có thể làm lượt "khám xong hẳn".
            await luot._ket_thuc_neu_xong(conn, identity, vid)
            await cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="service_order.cancelled",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=ChiDinhDaHuy(
                    visit_id=vid,
                    service_order_id=oid,
                    service_code=o["service_code"],
                    service_name=o["service_name"],
                    da_thu_tien=thua > 0,
                    tien_thua=thua or None,
                    ly_do=ly,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type="service_order.cancelled",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={
                    "visit_id": vid,
                    "order_id": oid,
                    "service_code": o["service_code"],
                    "tien_thua": thua,
                },
            )
        return {
            "ok": True,
            "order_id": oid,
            "visit_id": vid,
            "da_thu_tien": thua > 0,
            "tien_thua": thua,
            "so_sua_id": so_id,
            "da_bao_bac_si_chinh": da_bao,
        }

    # ── (c) Xong làm dịch vụ → về đang làm ────────────────────────────────
    async def hoan_tac_xong_dich_vu(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
    ) -> dict[str, Any]:
        """`UndoServiceCompletion` — hoàn tác "Xong" của một dịch vụ.

        Lần làm xong gần nhất về ĐANG LÀM, chỉ định về đang làm, khách về lại
        phòng (đang không ở phòng nào khác → đang được làm; đang ở chỗ khác →
        đợi quay lại). Vòng đọc đã "sẵn sàng" nhờ lần Xong ấy lùi về "đang
        thu"; lượt "khám xong hẳn" mở lại. Phiếu kết quả, tệp đã tải GIỮ
        NGUYÊN. Kết quả đã hoàn tất / đã duyệt cho gửi thì hỏi xác nhận + lý do.
        """
        from clinicai.permissions.lich import doi_lich_phong
        from clinicai.services.luot_kham_service import LuotKhamService
        from clinicai.services.service_execution_service import (
            QUYEN_XONG,
            ServiceExecutionService,
            _doi_quyen_lam,
        )

        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_lam(conn, identity, QUYEN_XONG)
            don, vid = await ServiceExecutionService._khoa_don(conn, cid, oid)
            await doi_quyen(conn, identity, QUYEN_XONG, phong_id=don["room_id"])
            await doi_lich_phong(
                conn,
                self._pool,
                identity,
                don["room_id"],
                ngay_cu=bool(don["la_ngay_cu"]),
            )
            if don["execution_status"] == "IN_PROGRESS":
                return {"ok": True, "order_id": oid, "already": True}
            if don["execution_status"] != "COMPLETED":
                raise LuotKhamConflictError(
                    "EXECUTION_NOT_COMPLETED",
                    "Dịch vụ này chưa ở trạng thái “Đã xong” — không có gì để"
                    " hoàn tác.",
                )
            lan = await conn.fetchrow(
                "SELECT id::text, attempt_no FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'COMPLETED'"
                " ORDER BY attempt_no DESC LIMIT 1 FOR UPDATE",
                cid,
                oid,
            )
            if lan is None:
                raise LuotKhamConflictError(
                    "EXECUTION_ATTEMPT_NOT_FOUND",
                    "Không tìm thấy lần làm đã xong của dịch vụ này.",
                )
            dau = await conn.fetchrow(
                """
                SELECT o.duyet_luc IS NOT NULL AS da_duyet,
                       EXISTS (SELECT 1 FROM form_instance f
                                WHERE f.clinic_id = o.clinic_id
                                  AND f.service_order_id = o.id
                                  AND f.trang_thai = 'READY') AS phieu_xong,
                       EXISTS (SELECT 1 FROM consultation c
                                 JOIN round_requirement q
                                   ON q.clinic_id = c.clinic_id
                                 JOIN review_round r
                                   ON r.clinic_id = q.clinic_id AND r.id = q.round_id
                                  AND r.visit_id = c.visit_id
                                  AND r.round_no = c.round_no
                                WHERE c.clinic_id = o.clinic_id
                                  AND c.visit_id = o.visit_id
                                  AND q.service_order_id = o.id
                                  AND c.status IN ('in_progress', 'completed'))
                           AS bac_si_da_doc
                  FROM service_order o
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                """,
                cid,
                oid,
            )
            assert dau is not None
            hau_qua: list[str] = []
            if dau["da_duyet"]:
                hau_qua.append("Kết quả dịch vụ này bác sĩ đã duyệt cho gửi khách.")
            elif dau["phieu_xong"]:
                hau_qua.append("Phiếu kết quả của dịch vụ này đã hoàn tất.")
            if dau["bac_si_da_doc"]:
                hau_qua.append("Bác sĩ đã vào đọc kết quả của dịch vụ này.")
            if hau_qua:
                hau_qua.append(
                    "Hoàn tác chỉ đưa dịch vụ về “đang làm” — kết quả đã gõ giữ nguyên."
                )
            doi_xac_nhan(ly_do=ly, xac_nhan=xac_nhan, hau_qua=hau_qua)

            await conn.execute(
                "UPDATE service_execution_attempt"
                "   SET status = 'IN_PROGRESS', completed_by = NULL,"
                "       completed_at = NULL, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                lan["id"],
            )
            moi = await ServiceExecutionService._doi_trang_thai(
                conn, cid, oid, "IN_PROGRESS"
            )
            # (trigger `service_order_dong_bo_trang_thai` tự bỏ giờ xong.)
            trang = await ve_lai_hang_phong(conn, cid, vid, oid, don["room_id"])
            if trang == "waiting":
                # Khách không đang ở phòng nào khác → đang được làm ở đây.
                cho = await conn.fetchval(
                    "UPDATE queue_entry SET status = 'serving', serving_at = now(),"
                    "       version = version + 1, updated_at = now()"
                    " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
                    "   AND reason = 'SERVICE' AND ref_id = $3::uuid"
                    "   AND status = 'waiting'"
                    " RETURNING id::text",
                    cid,
                    vid,
                    oid,
                )
                if cho is not None:
                    await chan_cho_khac(conn, cid, vid, cho)
            luot = LuotKhamService(pool=None)
            await luot._evaluate_rounds(conn, identity, vid)
            mo_moc = await mo_lai_moc_kham_xong(conn, cid, vid)
            if mo_moc and await luot._ket_thuc_neu_xong(conn, identity, vid):
                # Dịch vụ này không giữ lượt (chuyển theo dõi / đối tác): lượt
                # vẫn "khám xong hẳn" như cũ.
                mo_moc = False
            await cap_nhat_vi_tri(conn, cid, vid)

            await emit_event(
                conn,
                ten="service.completion_undone",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DichVuHoanTacXong(
                    visit_id=vid,
                    service_order_id=oid,
                    attempt_id=lan["id"],
                    attempt_no=int(lan["attempt_no"]),
                    execution_revision=moi,
                    mo_lai_kham_xong=mo_moc,
                    ly_do=ly,
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type="service.completion_undone",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid, "attempt_id": lan["id"]},
            )
        return {
            "ok": True,
            "order_id": oid,
            "attempt_id": lan["id"],
            "execution_status": "IN_PROGRESS",
            "execution_revision": moi,
            "mo_lai_kham_xong": mo_moc,
        }

    # ── (h) Duyệt kết quả → thu hồi về "chờ bác sĩ duyệt" ─────────────────
    async def thu_hoi_duyet_ket_qua(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
    ) -> dict[str, Any]:
        """`RevokeResultApproval` — hoàn tác "Duyệt kết quả" (bấm duyệt nhầm).

        Chỉ định về "chờ bác sĩ duyệt": bỏ mốc duyệt + người duyệt; việc theo
        dõi "chờ kết quả" mà CHÍNH lần duyệt ấy đóng thì mở lại. Đánh giá bác
        sĩ đã ghi, tệp, phiếu kết quả giữ nguyên (là bản nháp cho lần duyệt
        sau). Mốc "cho phép gửi" trên từng tệp KHÔNG xoá — trigger CSDL giữ nó
        làm vết, và từ 23/09 nó không còn là cửa gửi. Tệp đã GỬI khách thì hỏi
        xác nhận + lý do (khách vẫn giữ bản đã nhận). Như lệnh duyệt: không
        đòi lượt còn mở (kết quả muộn duyệt sau khi khách về).
        """
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                "result.review.approve",
                cau="Bạn không có quyền duyệt kết quả nên không thu hồi được.",
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await conn.execute(
                "SELECT 1 FROM visit WHERE clinic_id = $1::uuid AND visit_id ="
                " $2::uuid FOR UPDATE",
                cid,
                vid,
            )
            o = await conn.fetchrow(
                "SELECT duyet_luc FROM service_order"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            assert o is not None
            if o["duyet_luc"] is None:
                return {"ok": True, "order_id": oid, "already": True}
            da_gui = _so(
                await conn.fetchval(
                    "SELECT count(*) FROM tep_ket_qua"
                    " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                    "   AND gui_luc IS NOT NULL AND da_xoa_luc IS NULL",
                    cid,
                    oid,
                )
            )
            hau_qua: list[str] = []
            if da_gui:
                hau_qua.append(
                    f"Đã gửi {da_gui} tệp kết quả cho khách — khách vẫn giữ bản"
                    " đã nhận; thu hồi chỉ đưa kết quả về “chờ bác sĩ duyệt”."
                )
            doi_xac_nhan(ly_do=ly, xac_nhan=xac_nhan, hau_qua=hau_qua)

            await conn.execute(
                "UPDATE service_order SET duyet_luc = NULL, duyet_boi = NULL,"
                "       version = version + 1, updated_at = now()"
                " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                oid,
            )
            # Lần duyệt đầu đóng việc theo dõi trong CÙNG giao dịch → cùng
            # `now()` với `duyet_luc`: mở lại đúng việc ấy, không đụng việc
            # đóng vì lý do khác. Đã có việc mở khác thì thôi (một việc mở /
            # chỉ định — `uq_follow_up_case_order_open`).
            await conn.execute(
                """
                UPDATE follow_up_case f
                   SET status = 'OPEN', closed_at = NULL, updated_at = now()
                 WHERE f.id = (
                        SELECT id FROM follow_up_case
                         WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                           AND status = 'DONE' AND closed_at = $3
                         ORDER BY created_at DESC LIMIT 1)
                   AND NOT EXISTS (
                        SELECT 1 FROM follow_up_case
                         WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid
                           AND status = 'OPEN')
                """,
                cid,
                oid,
                o["duyet_luc"],
            )
            await emit_event(
                conn,
                ten="result.approval_revoked",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=KetQuaThuHoiDuyet(
                    visit_id=vid, service_order_id=oid, tep_da_gui=da_gui, ly_do=ly
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type="result.approval_revoked",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "order_id": oid, "tep_da_gui": da_gui},
            )
        return {"ok": True, "order_id": oid, "tep_da_gui": da_gui}

    # ── (d) Check-out / về giữa chừng → mở lại lượt ───────────────────────
    async def mo_lai_luot(
        self,
        *,
        visit_id: str,
        identity: StaffIdentity,
        ly_do: Any = None,
        xac_nhan: bool = False,
    ) -> dict[str, Any]:
        """`ReopenVisit` — hoàn tác check-out (check-out nhầm) / "về giữa chừng".

        Cùng quyền với check-out (lego Tiếp đón). Lượt mở lại, khách về lại các
        hàng chờ còn dở; tiền đã thu, việc đã làm giữ nguyên.
        """
        cid = identity.clinic_id
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        ly = doc_ly_do(ly_do)
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                "reception.checkin.perform",
                cau="Bạn không có quyền check-out nên không mở lại lượt được.",
            )
            visit = await _khoa_luot_bat_ky(conn, cid, vid)
            if visit["closed_at"] is None and visit["status"] != "INCOMPLETE":
                return {"ok": True, "visit_id": vid, "already": True}
            ve_giua_chung = await _mo_lai_luot_trong(conn, identity, visit)
            await mo_cho_bi_chan(conn, cid, vid)
            await cap_nhat_vi_tri(conn, cid, vid)
            await emit_event(
                conn,
                ten="visit.reopened",
                clinic_id=cid,
                aggregate_id=vid,
                payload=LuotMoLai(
                    visit_id=vid, tu_ve_giua_chung=ve_giua_chung, ly_do=ly
                ),
                boi=nguoi(identity),
                correlation_id=vid,
            )
            await record_event(
                conn,
                event_type="visit.reopened",
                aggregate_type="visit",
                aggregate_id=vid,
                identity=identity,
                origin=ORIGIN,
                payload={"visit_id": vid, "tu_ve_giua_chung": ve_giua_chung},
            )
        return {"ok": True, "visit_id": vid, "tu_ve_giua_chung": ve_giua_chung}


__all__ = [
    "CAN_XAC_NHAN",
    "HoanTacService",
    "doc_ly_do",
    "doi_xac_nhan",
    "mo_lai_moc_kham_xong",
    "tien_da_thu_cua_chi_dinh",
    "tien_thua_cua_luot",
]
