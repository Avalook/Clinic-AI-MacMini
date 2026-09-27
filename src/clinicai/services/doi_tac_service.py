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

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import (
    DoiTacDaLayMau,
    DoiTacDaThuTien,
    DoiTacHuyThuTien,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
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


#: Hình thức khách trả đối tác (khớp CHECK của `doi_tac_thanh_toan`).
HINH_THUC_THU = ("CASH", "TRANSFER")

#: Trần một ghi nhận — chặn gõ thừa số 0 (100.000.000 đồng / một việc).
SO_TIEN_TOI_DA = 100_000_000


def doc_so_tien(value: Any) -> int | None:
    """Số tiền đối tác ghi nhận đã thu. Rác / âm / quá trần → None, không ném.

    Nhận số nguyên, chuỗi có dấu chấm / phẩy / khoảng trắng / "đ" ("900.000đ").
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        so = value
    elif isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        if value != int(value):
            return None
        so = int(value)
    elif isinstance(value, str):
        chu = value.strip().lower().replace("đ", "").replace("vnd", "")
        for k in (".", ",", " ", "\u00a0", "_"):
            chu = chu.replace(k, "")
        if not chu.isdigit():
            return None
        so = int(chu)
    else:
        return None
    if so < 0 or so > SO_TIEN_TOI_DA:
        return None
    return so


def doc_hinh_thuc(value: Any) -> str | None:
    """CASH / TRANSFER (không phân biệt hoa thường). Rác → None."""
    if not isinstance(value, str):
        return None
    v = value.strip().upper()
    return v if v in HINH_THUC_THU else None


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


async def _ghi_chu_doi_tac(
    conn: asyncpg.Connection, cid: str, oid: str, cot: str, ghi_chu: str | None
) -> None:
    """Ghi chú của đối tác vào dòng nhận việc (bảng của khối Đối tác)."""
    ghi = (ghi_chu or "").strip() or None
    if ghi is None:
        return
    if len(ghi) > 2000:
        raise LuotKhamConflictError(
            "NOTE_TOO_LONG", "Ghi chú quá dài (tối đa 2.000 ký tự)."
        )
    sql = {
        "ghi_chu_lay_mau": "UPDATE doi_tac_nhan_viec SET ghi_chu_lay_mau = $3",
        "ghi_chu_tai_lieu": "UPDATE doi_tac_nhan_viec SET ghi_chu_tai_lieu = $3",
    }[cot]
    await conn.execute(
        sql + " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid",
        cid,
        oid,
        ghi,
    )


class DoiTacService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _doi_quyen_doi_tac(self, identity: StaffIdentity, cau: str) -> None:
        """Lego 21 "Đối tác" (quyền `partner.work`) — cùng câu router hỏi
        (`get_partner_identity`). Trước 27/09/2026 hỏi vai PARTNER/MANAGEMENT,
        nên quyền này là nhãn: thu lego không mất gì."""
        async with self._pool.acquire() as conn:
            if not await can(conn, identity, "partner.work"):
                raise SafetyGateError(cau)

    async def viec_doi_tac(self, *, identity: StaffIdentity) -> dict[str, Any]:
        """Việc trên bàn đối tác, gom theo khách.

        Hai loại xét nghiệm (Tuyền 16/09/2026: *"cả 2, tuỳ loại xét nghiệm"*):
          * ĐỐI TÁC TỰ LẤY MẪU (`service_price.doi_tac_lay_mau`) — hiện ngay từ
            lúc bác sĩ duyệt, trạng thái "Chờ lấy mẫu", đối tác bấm "Đã lấy mẫu".
          * ĐIỀU DƯỠNG LẤY — chỉ hiện SAU khi điều dưỡng bấm xong ở phòng Lấy
            mẫu; trước đó ống máu còn chưa có, đối tác chẳng có gì để nhận.
        Có kết quả (tệp đầu tiên) là rời bàn — duyệt và gửi là việc bác sĩ, CSKH.

        NHẬN QUA SỰ KIỆN (24/09/2026): bàn chỉ hiện chỉ định ĐÃ NHẬN
        (`doi_tac_nhan_viec`, ghi bởi bên nhận cùng tên khi nghe "đã thu tiền"
        / "lấy mẫu xong") — không còn hiện việc tự-lấy-mẫu trước khi khách
        chọn làm và trả tiền.
        """
        await self._doi_quyen_doi_tac(identity, "Màn này chỉ dành cho đối tác.")
        rows = await self._pool.fetch(
            """
            SELECT o.id::text AS chi_dinh_id, o.service_code, o.exec_status,
                   coalesce(sp.name, o.service_name) AS ten_dich_vu,
                   coalesce(sp.doi_tac_lay_mau, false) AS doi_tac_lay_mau,
                   p.full_name AS ten_khach, p.patient_code AS ma_khach,
                   p.clinic_patient_id::text AS clinic_patient_id,
                   v.appointment_id::text AS appointment_id,
                   o.created_at, o.finished_at, o.ket_qua_luc,
                   o.doi_tac_cho_tai_lieu_luc,
                   nv.ghi_chu_lay_mau, nv.ghi_chu_tai_lieu,
                   -- Đối tác tự thu (27/09/2026): giá tham khảo + đã ghi nhận chưa.
                   sp.unit_price AS gia_tham_khao,
                   coalesce(sp.billing_owner = 'EXTERNAL_PARTNER', false)
                     AS doi_tac_thu,
                   tt.id::text AS thu_id, tt.so_tien AS thu_so_tien,
                   tt.hinh_thuc AS thu_hinh_thuc, tt.ghi_chu AS thu_ghi_chu,
                   tt.ghi_luc AS thu_luc
              FROM service_order o
              JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
              JOIN patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
              JOIN node_definition n
                ON n.clinic_id = o.clinic_id AND n.code = o.node_code
               AND n.lam_ben_ngoai
              JOIN doi_tac_nhan_viec nv
                ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
              LEFT JOIN LATERAL (
                   SELECT s.name, s.doi_tac_lay_mau, s.unit_price, s.billing_owner
                     FROM service_price s
                    WHERE s.clinic_id = o.clinic_id
                      AND s.service_code = o.service_code AND s.active
                    ORDER BY (s."group" = 'dich_vu') DESC LIMIT 1) sp ON true
              LEFT JOIN doi_tac_thanh_toan tt
                ON tt.clinic_id = o.clinic_id AND tt.service_order_id = o.id
               AND tt.huy_luc IS NULL
             WHERE o.clinic_id = $1::uuid
               -- Đã gửi kết quả HÔM NAY vẫn ở lại bàn (mục "Đã gửi") để đối
               -- tác thấy mình vừa gửi gì và gửi thêm tài liệu nếu còn thiếu.
               AND (o.ket_qua_luc IS NULL
                    OR (o.ket_qua_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
                       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date)
               AND o.created_at > now() - interval '60 days'
               AND o.exec_status IN ('authorized', 'assigned', 'in_progress',
                                     'performed')
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
                    "ghi_chu_lay_mau": r["ghi_chu_lay_mau"],
                    "ghi_chu_tai_lieu": r["ghi_chu_tai_lieu"],
                    # Khách trả TRỰC TIẾP cho đối tác (Q1, 27/09/2026).
                    "doi_tac_thu": bool(r["doi_tac_thu"]),
                    "gia_tham_khao": (
                        int(r["gia_tham_khao"])
                        if r["gia_tham_khao"] is not None
                        else None
                    ),
                    "da_thu": (
                        {
                            "id": r["thu_id"],
                            "so_tien": int(r["thu_so_tien"]),
                            "hinh_thuc": r["thu_hinh_thuc"],
                            "ghi_chu": r["thu_ghi_chu"],
                            "luc": _iso(r["thu_luc"]),
                        }
                        if r["thu_id"]
                        else None
                    ),
                }
            )
        con_viec = sum(1 for r in rows if r["ket_qua_luc"] is None)
        # Người đến trước lên trước — truy vấn đã lấy mới nhất trước cho trần.
        ds = sorted(khach.values(), key=lambda k: k["cho_tu"] or "")
        for k in ds:
            k["viec"].sort(key=lambda v: v["chi_dinh_luc"] or "")
        return {"khach": ds, "so_viec": con_viec}

    async def doi_tac_cho_tai_lieu(
        self, *, order_id: str, identity: StaffIdentity, ghi_chu: str | None = None
    ) -> dict[str, Any]:
        """Đối tác bấm "Chờ tài liệu": đã nhận mẫu, đang làm, sẽ gửi tài liệu.

        Tuyền 17/09/2026: *"phải có nút cho họ là chờ tài liệu, up tài liệu… như
        vậy trạng thái mới đồng bộ về cho cskh"*. Chỉ bấm được khi mẫu đã có
        (performed); bấm lại không đổi mốc đầu tiên.
        """
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
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
            # Ghi chú đối tác (24/09/2026) — lưu cả khi bấm lại để bổ sung.
            await _ghi_chu_doi_tac(conn, cid, oid, "ghi_chu_tai_lieu", ghi_chu)
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
        self, *, order_id: str, identity: StaffIdentity, ghi_chu: str | None = None
    ) -> dict[str, Any]:
        """Đối tác bấm "Đã lấy mẫu" cho xét nghiệm họ tự lấy."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
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
            await _ghi_chu_doi_tac(conn, cid, oid, "ghi_chu_lay_mau", ghi_chu)
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

    # ------------------------------------------------------------------
    # ĐỐI TÁC TỰ THU (Tuyền chốt 27/09/2026, Q1): "khách trả trực tiếp cho đối
    # tác, màn đối tác cũng phải có ghi nhận thanh toán thực hiện". Sổ của khối
    # Đối tác — KHÔNG phải tiền phòng khám (không vào két, không vào phiếu thu).

    async def ghi_nhan_da_thu(
        self,
        *,
        order_id: str,
        identity: StaffIdentity,
        so_tien: Any,
        hinh_thuc: Any,
        ghi_chu: str | None = None,
    ) -> dict[str, Any]:
        """Đối tác bấm "Đã thu tiền khách" cho một việc đã nhận.

        Một việc — một ghi nhận còn hiệu lực (unique ở Postgres). Bấm lại cùng số
        tiền + hình thức = trả lại bản cũ (chạy lại được); khác số = phải huỷ bản
        cũ (có lý do) rồi ghi lại.
        """
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        tien = doc_so_tien(so_tien)
        if tien is None:
            raise ValidationError("Số tiền không hợp lệ (số nguyên ≥ 0, đơn vị đồng).")
        ht = doc_hinh_thuc(hinh_thuc)
        if ht is None:
            raise ValidationError("Hình thức phải là Tiền mặt hoặc Chuyển khoản.")
        ghi = (ghi_chu or "").strip() or None
        if ghi is not None and len(ghi) > 2000:
            raise LuotKhamConflictError(
                "NOTE_TOO_LONG", "Ghi chú quá dài (tối đa 2.000 ký tự)."
            )
        async with self._pool.acquire() as conn, conn.transaction():
            o = await conn.fetchrow(
                """
                SELECT o.visit_id::text AS visit_id
                  FROM service_order o
                  JOIN doi_tac_nhan_viec nv
                    ON nv.clinic_id = o.clinic_id AND nv.service_order_id = o.id
                  JOIN service_price sp
                    ON sp.clinic_id = o.clinic_id AND sp.service_code = o.service_code
                   AND sp.active AND sp."group" = 'dich_vu'
                   AND sp.billing_owner = 'EXTERNAL_PARTNER'
                 WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid
                   AND o.exec_status <> 'cancelled'
                 LIMIT 1
                 FOR UPDATE OF o
                """,
                cid,
                oid,
            )
            if o is None:
                # Một câu cho "không có" lẫn "không phải việc khách trả đối tác".
                raise SafetyGateError(
                    "Không tìm thấy việc này trong danh sách của bạn."
                )
            cu = await conn.fetchrow(
                "SELECT id::text AS id, so_tien, hinh_thuc FROM doi_tac_thanh_toan"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND huy_luc IS NULL",
                cid,
                oid,
            )
            if cu is not None:
                if int(cu["so_tien"]) == tien and cu["hinh_thuc"] == ht:
                    return {"ok": True, "already": True, "id": cu["id"]}
                raise LuotKhamConflictError(
                    "PARTNER_PAYMENT_EXISTS",
                    "Việc này đã ghi nhận đã thu — huỷ ghi nhận cũ (kèm lý do)"
                    " rồi ghi lại.",
                )
            moi = await conn.fetchval(
                """
                INSERT INTO doi_tac_thanh_toan
                    (clinic_id, service_order_id, so_tien, hinh_thuc, ghi_chu,
                     ghi_boi)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::uuid)
                RETURNING id::text
                """,
                cid,
                oid,
                tien,
                ht,
                ghi,
                identity.staff_id,
            )
            await emit_event(
                conn,
                ten="partner.payment_recorded",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacDaThuTien(
                    visit_id=o["visit_id"],
                    service_order_id=oid,
                    so_tien=tien,
                    hinh_thuc=ht,
                ),
                boi=nguoi(identity),
                correlation_id=o["visit_id"],
            )
        return {"ok": True, "already": False, "id": moi}

    async def huy_da_thu(
        self, *, order_id: str, identity: StaffIdentity, ly_do: Any
    ) -> dict[str, Any]:
        """Huỷ ghi nhận "đã thu" đang hiệu lực (ghi nhầm / sửa số) — bắt buộc lý
        do. Không xoá: dòng cũ giữ lại kèm ai huỷ, lúc nào, vì sao."""
        await self._doi_quyen_doi_tac(identity, "Chỉ đối tác bấm được việc này.")
        cid = identity.clinic_id
        oid = _uuid(order_id, "Mã việc không hợp lệ.")
        ly = ly_do.strip() if isinstance(ly_do, str) else ""
        if not 3 <= len(ly) <= 2000:
            raise ValidationError("Ghi lý do huỷ (3–2.000 ký tự).")
        async with self._pool.acquire() as conn, conn.transaction():
            cu = await conn.fetchrow(
                """
                SELECT t.id::text AS id, t.so_tien, o.visit_id::text AS visit_id
                  FROM doi_tac_thanh_toan t
                  JOIN service_order o
                    ON o.clinic_id = t.clinic_id AND o.id = t.service_order_id
                 WHERE t.clinic_id = $1::uuid AND t.service_order_id = $2::uuid
                   AND t.huy_luc IS NULL
                   FOR UPDATE OF t
                """,
                cid,
                oid,
            )
            if cu is None:
                return {"ok": True, "already": True}
            await conn.execute(
                "UPDATE doi_tac_thanh_toan SET huy_luc = now(), huy_boi = $3::uuid,"
                " ly_do_huy = $4 WHERE clinic_id = $1::uuid AND id = $2::uuid",
                cid,
                cu["id"],
                identity.staff_id,
                ly,
            )
            await emit_event(
                conn,
                ten="partner.payment_voided",
                clinic_id=cid,
                aggregate_id=oid,
                so_ke_tiep=True,
                payload=DoiTacHuyThuTien(
                    visit_id=cu["visit_id"],
                    service_order_id=oid,
                    so_tien=int(cu["so_tien"]),
                ),
                boi=nguoi(identity),
                correlation_id=cu["visit_id"],
            )
        return {"ok": True, "already": False}
