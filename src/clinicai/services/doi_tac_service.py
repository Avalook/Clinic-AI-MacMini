"""Việc của ĐỐI TÁC xét nghiệm — danh sách việc, chờ tài liệu, đã lấy mẫu.

Bóc khỏi ``luot_kham_service`` ngày 24/09/2026 (bước 4 đợt bóc lõi). Khối
``doi_tac`` (modules.py): ghi bảng của mình rồi PHÁT ``partner.sample_collected``.
Vòng đọc + khép lượt KHÔNG gọi thẳng nữa — khối VÒNG ĐỌC nghe sự kiện ấy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
)
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import (
    DoiTacDaLayMau,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.audit import record_event
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    mo_cho_bi_chan,
)
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

logger = structlog.get_logger()

#: Giữ nguồn nhật ký cũ — đọc lại event_log không phải đổi truy vấn.
ORIGIN = "api:luot-kham"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


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


class DoiTacService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

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
        canh_bao_neu_day("doi_tac.viec", len(rows), 300, clinic_id=identity.clinic_id)
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
            await khoa_luot(conn, cid, vid)
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
            await mo_cho_bi_chan(conn, cid, vid)
            await cap_nhat_vi_tri(conn, identity.clinic_id, vid)
            await emit_event(
                conn,
                ten="partner.sample_collected",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacDaLayMau(visit_id=vid, service_order_id=oid),
                boi=nguoi(identity),
                correlation_id=vid,
            )
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
