"""NHẬN KHÁCH TẠI PHÒNG — dây ``nhan_tai_phong`` (Tuyền chốt 07/10/2026).

Kế hoạch: ``docs/KE-HOACH-NHAN-TAI-PHONG.md``. Dây TẮT = y như cũ (dây H4 tự xếp
phòng). Dây BẬT:

    Sắp đến → [Nhận] → Đang chờ → [Bắt đầu] → Đang làm → [Xong] (tự nhả)

  * "Sắp đến" của một phòng = MỌI chỉ định chưa vào phòng nào mà phòng ấy làm
    được — bác sĩ chỉ định, làm thêm tại quầy, mang sang khi check-in, kể cả
    khách chưa chốt ở quầy. Nhận theo KHÁCH (mọi chỉ định phòng làm được).
  * Không khoá cứng — NHẬN CHÉO: khách đang chờ ở phòng A thì rời hàng A, chỉ
    định A về Sắp đến; khách đang LÀM ở A (A quên Xong) thì đóng hàng A nhưng
    lần làm của A GIỮ mở — A tự bấm Xong / Gián đoạn, hệ thống không đoán thay.
  * Mốc NHẢ có lý do: XONG (bấm Xong — sự kiện `service.completed`), DIEU_PHOI
    (nút Nhả), NHAN_CHEO, BO_DICH_VU (quầy bỏ dịch vụ). Mọi nút hoàn tác được;
    hoàn tác Nhận KHÔNG đi đường huỷ xếp phòng (không đẻ việc trưởng ca).

Hai người Nhận cùng lúc: cả hai khoá LƯỢT (`khoa_luot`) — người sau đọc lại thấy
khách đã ở phòng kia và nhận câu hỏi nhận chéo, không có hai phòng cùng giữ.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import (
    KhachRoiPhong,
    NhanVaoPhongDaHoanTac,
    RoiPhongDaHoanTac,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services import finance_gate
from clinicai.services.day_noi import doc_day
from clinicai.services.hang_cho import cap_nhat_vi_tri, mo_cho_bi_chan
from clinicai.services.lenh_kham_core import (
    LuotKhamConflictError,
    bien_nhan_doc,
    bien_nhan_ghi,
    khoa_luot,
)
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.service_routing_service import (
    DAY_NHAN_TAI_PHONG,
    DOI_TAC_LAM_TRON_SQL,
    KHONG_DOI,
    NGUON_TAI_PHONG,
    QUYEN_XEP,
    TIEN_CHAN_NHAN,
    ServiceRoutingService,
    phong_lam_duoc_sql,
)

NHA_DIEU_PHOI = "DIEU_PHOI"
NHA_NHAN_CHEO = "NHAN_CHEO"
NHA_BO_DICH_VU = "BO_DICH_VU"
ACTION_NHAN = "service_routing.receive"

#: Chỉ định CHƯA VÀO PHÒNG NÀO (alias ``o`` service_order, ``v`` visit): bác sĩ
#: đã duyệt, khách chưa bỏ, chưa bắt đầu, lượt còn mở, không phải đối tác làm
#: trọn, không bị bác sĩ dặn "làm sau khi đọc kết quả vòng trước". KHÔNG xét
#: nguồn sinh ra chỉ định và KHÔNG đòi khách đã chốt / đã thu.
CHUA_VAO_PHONG_SQL = f"""
       o.exec_status IN ('authorized', 'assigned')
   AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
   AND coalesce(o.routing_status, 'UNASSIGNED')
       IN ('UNASSIGNED', 'REASSIGNMENT_REQUIRED')
   AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
   AND v.status IN ('OPEN', 'IN_PROGRESS') AND v.closed_at IS NULL
   AND NOT {DOI_TAC_LAM_TRON_SQL}
   AND (o.hold_until_round IS NULL OR EXISTS (
        SELECT 1 FROM review_round rr
         WHERE rr.clinic_id = o.clinic_id AND rr.visit_id = o.visit_id
           AND rr.round_no = o.hold_until_round AND rr.status = 'closed'))
"""

_SAP_DEN_SQL = f"""
SELECT pr.id::text AS room_id, o.id::text AS id, o.visit_id::text AS visit_id,
       o.service_name, o.selection_status, o.routing_revision,
       o.phong_du_kien_id::text AS huong_dan_id,
       p.full_name, p.patient_code, a.so_tiep_don, a.so_booking
  FROM clinic_room pr
  JOIN service_order o
    ON o.clinic_id = pr.clinic_id AND {phong_lam_duoc_sql("pr", "o")}
  JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN appointment a ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
 WHERE pr.clinic_id = $1::uuid
   AND ($2::uuid IS NULL OR pr.id = $2::uuid)
   AND ($3::uuid IS NULL OR o.visit_id = $3::uuid)
   AND pr.is_active AND pr.accepting AND NOT pr.la_doi_tac
   AND (pr.location_id IS NULL
        OR coalesce(v.location_id, a.location_id) IS NULL
        OR pr.location_id = coalesce(v.location_id, a.location_id))
   AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
   AND {CHUA_VAO_PHONG_SQL}
 ORDER BY v.checked_in_at, o.created_at, o.id
"""

#: Chỗ chờ SỐNG của khách ở các phòng dịch vụ (đang chờ / đang làm).
_O_PHONG_SQL = """
SELECT q.id::text AS id, q.ref_id::text AS ref_id, q.visit_id::text AS visit_id,
       q.room_id::text AS room_id, r.name AS phong, q.status,
       coalesce(q.serving_at, q.eligible_at, q.created_at) AS luc
  FROM queue_entry q
  LEFT JOIN clinic_room r ON r.id = q.room_id AND r.clinic_id = q.clinic_id
 WHERE q.clinic_id = $1::uuid AND q.visit_id = ANY($2::uuid[])
   AND q.reason = 'SERVICE' AND q.lane = 'ROOM'
   AND q.status IN ('waiting', 'called', 'blocked', 'serving')
 ORDER BY q.visit_id, (q.status = 'serving') DESC, coalesce(q.eligible_at, q.created_at)
"""


async def dang_bat(conn: asyncpg.Connection, clinic_id: str) -> bool:
    return bool(await doc_day(conn, clinic_id, DAY_NHAN_TAI_PHONG))


async def _sap_den_rows(
    conn: asyncpg.Connection,
    cid: str,
    room_id: str | None = None,
    visit_id: str | None = None,
) -> list[asyncpg.Record]:
    rows = await conn.fetch(_SAP_DEN_SQL, cid, room_id, visit_id)
    tien = await finance_gate.states_for_orders(
        conn, cid, list({r["id"] for r in rows})
    )
    return [
        r
        for r in rows
        if (q := tien.get(r["id"])) is None or q.finance_state not in TIEN_CHAN_NHAN
    ]


async def dang_o_phong(
    conn: asyncpg.Connection, cid: str, visit_ids: Sequence[str], *, ca_cho: bool
) -> dict[str, dict[str, Any]]:
    """Khách đang ở phòng dịch vụ nào: ``{phong_id, phong, trang_thai, luc}``.

    ``trang_thai`` 'lam' (đang làm) / 'cho' (đã nhận, đang chờ). ``ca_cho``
    False (dây tắt — khách nằm trong nhiều hàng cùng lúc) thì chỉ nói nơi
    khách ĐANG LÀM."""
    out: dict[str, dict[str, Any]] = {}
    for r in await conn.fetch(_O_PHONG_SQL, cid, list(set(visit_ids))):
        lam = r["status"] == "serving"
        if r["visit_id"] in out or not (lam or ca_cho):
            continue
        out[r["visit_id"]] = {
            "phong_id": r["room_id"],
            "phong": r["phong"],
            "trang_thai": "lam" if lam else "cho",
            "luc": r["luc"].isoformat() if r["luc"] else None,
        }
    return out


async def sap_den(
    conn: asyncpg.Connection, cid: str, room_id: str
) -> list[dict[str, Any]]:
    """Danh sách SẮP ĐẾN của một phòng, theo KHÁCH. Khách được hướng dẫn đến
    phòng này lên đầu; khách đang chờ / làm ở phòng khác mang nhãn nơi ấy."""
    khach: dict[str, dict[str, Any]] = {}
    for r in await _sap_den_rows(conn, cid, room_id):
        k = khach.setdefault(
            r["visit_id"],
            {
                "visit_id": r["visit_id"],
                "khach": r["full_name"],
                "ma_khach": r["patient_code"],
                "so_tiep_don": r["so_tiep_don"],
                "so_booking": r["so_booking"],
                "duoc_huong_dan": False,
                "chi_dinh": [],
            },
        )
        k["duoc_huong_dan"] |= r["huong_dan_id"] == room_id
        k["chi_dinh"].append(
            {
                "id": r["id"],
                "ten": r["service_name"],
                "chua_chot": r["selection_status"] != "SELECTED",
            }
        )
    o_dau = await dang_o_phong(conn, cid, list(khach), ca_cho=True)
    for vid, k in khach.items():
        noi = o_dau.get(vid)
        k["dang_o_phong"] = noi if noi and noi["phong_id"] != room_id else None
    # sorted giữ thứ tự check-in trong từng nhóm.
    return sorted(khach.values(), key=lambda k: not k["duoc_huong_dan"])


async def dem_theo_phong(
    conn: asyncpg.Connection, cid: str, *, bat: bool
) -> dict[str, dict[str, int | None]]:
    """Ba số của mỗi phòng: sắp đến (chỉ khi dây bật) · đang chờ · đang làm —
    số KHÁCH, lượt check-in hôm nay."""
    out: dict[str, dict[str, int | None]] = {}

    def o(rid: str) -> dict[str, int | None]:
        return out.setdefault(
            rid, {"sap_den": 0 if bat else None, "dang_cho": 0, "dang_lam": 0}
        )

    if bat:
        sap: dict[str, set[str]] = {}
        for r in await _sap_den_rows(conn, cid):
            sap.setdefault(r["room_id"], set()).add(r["visit_id"])
        for rid, vids in sap.items():
            o(rid)["sap_den"] = len(vids)
    hom_nay = (
        "(v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        " = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    )
    for r in await conn.fetch(
        "SELECT q.room_id::text AS room_id, count(DISTINCT q.visit_id)::int AS so"
        "  FROM queue_entry q JOIN visit v"
        "    ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id"
        " WHERE q.clinic_id = $1::uuid AND q.reason = 'SERVICE' AND q.lane = 'ROOM'"
        "   AND q.room_id IS NOT NULL"
        "   AND q.status IN ('waiting', 'called', 'blocked') AND "
        + hom_nay
        + " GROUP BY q.room_id",
        cid,
    ):
        o(r["room_id"])["dang_cho"] = r["so"]
    # Đang làm theo LẦN LÀM đang mở của phòng — kể cả khi khách đã được phòng
    # khác nhận (nhận chéo), vì phòng này vẫn còn một việc phải bấm Xong.
    for r in await conn.fetch(
        "SELECT o.room_id::text AS room_id, count(DISTINCT o.visit_id)::int AS so"
        "  FROM service_order o JOIN visit v"
        "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
        " WHERE o.clinic_id = $1::uuid AND o.execution_status = 'IN_PROGRESS'"
        "   AND o.room_id IS NOT NULL AND " + hom_nay + " GROUP BY o.room_id",
        cid,
    ):
        o(r["room_id"])["dang_lam"] = r["so"]
    return out


async def roi_phong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    vid: str,
    cho: Sequence[asyncpg.Record],
    ly_do: str,
    sang_room_id: str | None = None,
) -> list[str]:
    """NHẢ những chỗ chờ ``cho`` (dòng ``_O_PHONG_SQL``): chỗ chờ đóng; chỉ định
    chưa bắt đầu về "Sắp đến" (chưa vào phòng nào); khách đang LÀM thì lần làm
    giữ mở. Mỗi chỗ một sự kiện `service.room_released`. Người gọi đã kiểm quyền
    + khoá lượt. Trả các chỉ định đã về Sắp đến."""
    cid = identity.clinic_id
    ve: list[str] = []
    for q in cho:
        lam = q["status"] == "serving"
        await conn.execute(
            "UPDATE queue_entry SET status = 'cancelled', version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            q["id"],
        )
        lan = rev = None
        if lam:
            lan = await conn.fetchval(
                "SELECT id::text FROM service_execution_attempt"
                " WHERE clinic_id = $1::uuid AND service_order_id = $2::uuid"
                "   AND status = 'IN_PROGRESS'",
                cid,
                q["ref_id"],
            )
        else:
            rev = await _ve_chua_xep(conn, cid, q["ref_id"])
            if rev is not None:
                ve.append(q["ref_id"])
        await emit_event(
            conn,
            ten="service.room_released",
            clinic_id=cid,
            aggregate_id=q["ref_id"],
            so_ke_tiep=True,
            payload=KhachRoiPhong(
                visit_id=vid,
                service_order_id=q["ref_id"],
                room_id=q["room_id"],
                ly_do=ly_do,
                trang_thai_truoc="lam" if lam else "cho",
                sang_room_id=sang_room_id,
                attempt_id=lan,
                routing_revision=rev,
                huong_dan_room_id=await conn.fetchval(
                    "SELECT phong_du_kien_id::text FROM service_order"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    q["ref_id"],
                ),
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )
    if cho:
        await mo_cho_bi_chan(conn, cid, vid)
        await cap_nhat_vi_tri(conn, cid, vid)
    return ve


async def _ve_chua_xep(conn: asyncpg.Connection, cid: str, oid: str) -> int | None:
    """Chỉ định CHƯA BẮT ĐẦU về "chưa vào phòng nào" (Sắp đến) — không như huỷ
    xếp phòng (REASSIGNMENT_REQUIRED + việc trưởng ca). Trả routing mới."""
    rev = await conn.fetchval(
        """
        UPDATE service_order
           SET routing_status = 'UNASSIGNED', room_id = NULL,
               routing_revision = routing_revision + 1,
               assigned_by = NULL, assigned_at = NULL,
               exec_status = CASE WHEN exec_status = 'assigned'
                                  THEN 'authorized' ELSE exec_status END,
               version = version + 1, updated_at = now()
         WHERE clinic_id = $1::uuid AND id = $2::uuid
           AND coalesce(execution_status, 'PENDING') = 'PENDING'
        RETURNING routing_revision
        """,
        cid,
        oid,
    )
    return int(rev) if rev is not None else None


async def _cho_cua(
    conn: asyncpg.Connection, cid: str, vid: str
) -> list[asyncpg.Record]:
    return list(await conn.fetch(_O_PHONG_SQL, cid, [vid]))


def _khach_dang_lam(cho: Sequence[asyncpg.Record]) -> None:
    if any(q["status"] == "serving" for q in cho):
        raise LuotKhamConflictError(
            "KHACH_DANG_LAM",
            "Khách đang được làm dịch vụ ở phòng này — bấm Xong / Huỷ bắt đầu trước.",
        )


async def nha_chi_dinh(
    conn: asyncpg.Connection, identity: StaffIdentity, *, vid: str, oid: str
) -> bool:
    """Trưởng ca đổi phòng khi dây bật = nhả chỉ định khỏi phòng đang chờ."""
    cho = [
        q for q in await _cho_cua(conn, identity.clinic_id, vid) if q["ref_id"] == oid
    ]
    _khach_dang_lam(cho)
    return bool(await roi_phong(conn, identity, vid=vid, cho=cho, ly_do=NHA_DIEU_PHOI))


async def nha_khi_bo_chon(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    vid: str,
    order_ids: Sequence[str],
) -> None:
    """Quầy bỏ dịch vụ khách đã được phòng nhận → khách rời hàng phòng ấy."""
    cho = [
        q
        for q in await _cho_cua(conn, identity.clinic_id, vid)
        if q["ref_id"] in set(order_ids) and q["status"] != "serving"
    ]
    await roi_phong(conn, identity, vid=vid, cho=cho, ly_do=NHA_BO_DICH_VU)


async def da_sang_phong(
    conn: asyncpg.Connection, cid: str, order_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Chỉ định ĐANG LÀM mà khách đã được phòng khác nhận (nhận chéo): phòng
    mới + lúc khách rời — cho nhãn đỏ ở thẻ của phòng cũ."""
    if not order_ids:
        return {}
    return {
        r["oid"]: {"phong": r["phong"], "luc": r["luc"].isoformat()}
        for r in await conn.fetch(
            """
            SELECT DISTINCT ON (e.aggregate_id) e.aggregate_id::text AS oid,
                   r.name AS phong, e.occurred_at AS luc
              FROM domain_event e
              LEFT JOIN clinic_room r
                ON r.clinic_id = e.clinic_id
               AND r.id = (e.payload->>'sang_room_id')::uuid
             WHERE e.clinic_id = $1::uuid AND e.aggregate_type = 'service_order'
               AND e.aggregate_id = ANY($2::uuid[])
               AND e.event_type = 'service.room_released'
               AND e.payload->>'ly_do' = 'NHAN_CHEO'
             ORDER BY e.aggregate_id, e.seq DESC
            """,
            cid,
            list(order_ids),
        )
    }


async def _doi_chieu(
    conn: asyncpg.Connection, cid: str, vid: str, rid: str
) -> dict[str, Any]:
    """Hướng dẫn ↔ thực tế: thứ tự phòng trên phiếu hướng dẫn (thứ tự dòng —
    `quay_thu_service._HUONG_DAN_SQL`) và thứ tự phòng khách thật sự được nhận."""
    hd = [
        r["phong"]
        for r in await conn.fetch(
            "SELECT phong_du_kien_id::text AS phong FROM service_order"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            "   AND phong_du_kien_id IS NOT NULL"
            "   AND selection_status IS DISTINCT FROM 'NOT_SELECTED'"
            "   AND exec_status NOT IN ('draft', 'cancelled')"
            " ORDER BY created_at, id",
            cid,
            vid,
        )
    ]
    thu_tu_hd = list(dict.fromkeys(hd))
    da_nhan = await conn.fetchval(
        "SELECT count(DISTINCT payload->>'room_id') FROM domain_event"
        " WHERE clinic_id = $1::uuid AND correlation_id = $2::uuid"
        "   AND event_type = 'service.routed' AND payload->>'nguon' = $3"
        "   AND payload->>'room_id' <> $4",
        cid,
        vid,
        NGUON_TAI_PHONG,
        rid,
    )
    return {
        "thu_tu_huong_dan": thu_tu_hd.index(rid) + 1 if rid in thu_tu_hd else None,
        "thu_tu_thuc_te": int(da_nhan) + 1,
    }


class NhanTaiPhongService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def nhan(
        self,
        *,
        visit_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        xac_nhan: bool = False,
        bac_si_lam_id: Any = KHONG_DOI,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """ReceiveAtRoom — phòng nhận KHÁCH: mọi chỉ định Sắp đến của khách mà
        phòng làm được. Khách đang ở phòng khác → 409 ``KHACH_O_PHONG_KHAC``
        (kèm tên phòng); gửi lại ``xac_nhan`` = nhận chéo, một nút, không lý do.
        Chỉ định không nhận được (giữ chờ đọc kết quả, tiền đang hoàn…) bỏ qua,
        trả câu lý do; không nhận được cái nào thì báo lỗi của cái đầu tiên."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        cid = identity.clinic_id
        payload = {"visit_id": vid, "room_id": rid, "xac_nhan": bool(xac_nhan)}
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                QUYEN_XEP,
                cau="Bạn không có quyền nhận khách vào phòng.",
            )
            if not await dang_bat(conn, cid):
                raise LuotKhamConflictError(
                    "NHAN_TAI_PHONG_TAT",
                    "Dây Nhận khách tại phòng đang tắt — phòng nhận theo cách cũ.",
                )
            await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(
                conn, identity, ACTION_NHAN, idempotency_key, payload
            )
            if cached is not None:
                return cached
            don = await _sap_den_rows(conn, cid, rid, vid)
            cho = await _cho_cua(conn, cid, vid)
            if not don:
                if any(q["room_id"] == rid for q in cho):
                    return {"ok": True, "already": True, "visit_id": vid}
                raise LuotKhamConflictError(
                    "KHONG_CON_GI_DE_NHAN",
                    "Khách không còn dịch vụ nào chờ vào phòng này — tải lại.",
                )
            khac = [q for q in cho if q["room_id"] != rid]
            if khac and not xac_nhan:
                lam = next((q for q in khac if q["status"] == "serving"), khac[0])
                trang = "làm" if lam["status"] == "serving" else "chờ"
                raise LuotKhamConflictError(
                    "KHACH_O_PHONG_KHAC",
                    f"Khách đang {trang} ở phòng {lam['phong'] or 'khác'} — nhận"
                    " sang phòng này?",
                    {
                        "ma": "KHACH_O_PHONG_KHAC",
                        "phong": lam["phong"],
                        "trang_thai": "lam" if trang == "làm" else "cho",
                    },
                )
            tu_phong = khac[0]["room_id"] if khac else None
            await roi_phong(
                conn, identity, vid=vid, cho=khac, ly_do=NHA_NHAN_CHEO, sang_room_id=rid
            )
            doi_chieu = await _doi_chieu(conn, cid, vid, rid)
            gan = ServiceRoutingService(self._pool)
            da_nhan: list[str] = []
            bo_qua: list[dict[str, Any]] = []
            loi_dau: LuotKhamConflictError | None = None
            for o in await _sap_den_rows(conn, cid, rid, vid):
                try:
                    async with conn.transaction():
                        await gan._gan(
                            conn,
                            identity,
                            vid=vid,
                            oid=o["id"],
                            rid=rid,
                            rev=int(o["routing_revision"]),
                            ly_do="INITIAL_ASSIGNMENT",
                            ref=None,
                            tu_dong=False,
                            nguon=NGUON_TAI_PHONG,
                            bac_si=bac_si_lam_id,
                            doi_chieu={
                                **doi_chieu,
                                "huong_dan_room_id": o["huong_dan_id"],
                                "dung_huong_dan": None
                                if o["huong_dan_id"] is None
                                else o["huong_dan_id"] == rid,
                                "nhan_cheo_tu_room_id": tu_phong,
                            },
                        )
                    da_nhan.append(o["id"])
                except LuotKhamConflictError as e:
                    loi_dau = loi_dau or e
                    bo_qua.append(
                        {"id": o["id"], "ten": o["service_name"], "cau": str(e)}
                    )
            if not da_nhan:
                assert loi_dau is not None
                raise loi_dau
            await cap_nhat_vi_tri(conn, cid, vid)
            result = {
                "ok": True,
                "visit_id": vid,
                "room_id": rid,
                "da_nhan": da_nhan,
                "bo_qua": bo_qua,
                "nhan_cheo": tu_phong is not None,
            }
            await bien_nhan_ghi(
                conn, identity, ACTION_NHAN, idempotency_key, payload, vid, result
            )
        return result

    async def hoan_tac_nhan(
        self, *, visit_id: Any, room_id: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """UndoReceiveAtRoom — khách về "Sắp đến" (không như huỷ xếp phòng:
        không REASSIGNMENT_REQUIRED, không đẻ việc trưởng ca). Bấm hai lần =
        ``already``."""
        return await self._ve_sap_den(
            visit_id=visit_id, room_id=room_id, identity=identity, nha=False
        )

    async def nha(
        self,
        *,
        visit_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        huong_dan_room_id: Any = None,
    ) -> dict[str, Any]:
        """ReleaseFromRoom — nút Nhả trên dòng đang chờ (phòng / trưởng ca):
        khách về Sắp đến, mốc NHẢ lý do DIEU_PHOI; tuỳ chọn hướng dẫn phòng mới."""
        hd = (
            None
            if huong_dan_room_id in (None, "")
            else _uuid(huong_dan_room_id, "Mã phòng hướng dẫn không hợp lệ.")
        )
        return await self._ve_sap_den(
            visit_id=visit_id, room_id=room_id, identity=identity, nha=True, hd=hd
        )

    async def _ve_sap_den(
        self,
        *,
        visit_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        nha: bool,
        hd: str | None = None,
    ) -> dict[str, Any]:
        from clinicai.services.service_routing_service import ghi_huong_dan

        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn không có quyền điều phối khách."
            )
            await khoa_luot(conn, cid, vid)
            cho = [q for q in await _cho_cua(conn, cid, vid) if q["room_id"] == rid]
            _khach_dang_lam(cho)
            if not cho:
                return {"ok": True, "already": True, "visit_id": vid}
            if nha:
                ve = await roi_phong(
                    conn, identity, vid=vid, cho=cho, ly_do=NHA_DIEU_PHOI
                )
                for oid in ve if hd else []:
                    if await conn.fetchval(
                        f"SELECT {phong_lam_duoc_sql('r', 'o')} FROM clinic_room r,"
                        " service_order o WHERE r.clinic_id = $1::uuid"
                        " AND r.id = $2::uuid AND o.clinic_id = r.clinic_id"
                        " AND o.id = $3::uuid",
                        cid,
                        hd,
                        oid,
                    ):
                        await ghi_huong_dan(
                            conn, identity, vid=vid, oid=oid, rid=hd, nguon="tai_phong"
                        )
            else:
                ve = []
                for q in cho:
                    rev = await _ve_chua_xep(conn, cid, q["ref_id"])
                    await conn.execute(
                        "UPDATE queue_entry SET status = 'cancelled',"
                        " version = version + 1, updated_at = now()"
                        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                        cid,
                        q["id"],
                    )
                    if rev is None:
                        continue
                    ve.append(q["ref_id"])
                    await emit_event(
                        conn,
                        ten="service.room_receive_undone",
                        clinic_id=cid,
                        aggregate_id=q["ref_id"],
                        so_ke_tiep=True,
                        payload=NhanVaoPhongDaHoanTac(
                            visit_id=vid,
                            service_order_id=q["ref_id"],
                            room_id=rid,
                            hoan_tac_event_id=await _su_kien_cuoi(
                                conn, cid, q["ref_id"], "service.routed"
                            ),
                            routing_revision=int(rev),
                        ),
                        boi=nguoi(identity),
                        correlation_id=vid,
                    )
                await cap_nhat_vi_tri(conn, cid, vid)
        return {"ok": True, "visit_id": vid, "room_id": rid, "ve_sap_den": ve}

    async def hoan_tac_nha(
        self, *, visit_id: Any, room_id: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """UndoReleaseFromRoom — lần Nhả (DIEU_PHOI) gần nhất ở phòng này rút
        lại: khách về lại hàng chờ phòng, GIỮ giờ vào hàng cũ. Khách đã được
        phòng khác nhận rồi thì phòng ấy Nhả / hoàn tác trước."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn không có quyền điều phối khách."
            )
            await khoa_luot(conn, cid, vid)
            nha = await conn.fetch(
                """
                WITH cuoi AS (
                    SELECT max(e.occurred_at) AS luc FROM domain_event e
                     WHERE e.clinic_id = $1::uuid AND e.correlation_id = $2::uuid
                       AND e.event_type = 'service.room_released'
                       AND e.payload->>'room_id' = $3
                       AND e.payload->>'ly_do' = 'DIEU_PHOI')
                SELECT e.event_id::text AS event_id, e.aggregate_id::text AS oid,
                       o.routing_revision,
                       (SELECT q.eligible_at FROM queue_entry q
                         WHERE q.clinic_id = e.clinic_id AND q.reason = 'SERVICE'
                           AND q.ref_id = e.aggregate_id AND q.status = 'cancelled'
                         ORDER BY q.updated_at DESC LIMIT 1) AS vao_hang
                  FROM domain_event e
                  JOIN cuoi ON cuoi.luc = e.occurred_at
                  JOIN service_order o
                    ON o.id = e.aggregate_id AND o.clinic_id = e.clinic_id
                 WHERE e.clinic_id = $1::uuid AND e.correlation_id = $2::uuid
                   AND e.event_type = 'service.room_released'
                   AND e.payload->>'room_id' = $3
                   AND coalesce(o.routing_status, 'UNASSIGNED') = 'UNASSIGNED'
                   AND coalesce(o.execution_status, 'PENDING') = 'PENDING'
                   AND NOT EXISTS (
                       SELECT 1 FROM domain_event u
                        WHERE u.clinic_id = e.clinic_id
                          AND u.aggregate_id = e.aggregate_id
                          AND u.event_type = 'service.room_release_undone'
                          AND u.payload->>'hoan_tac_event_id' = e.event_id::text)
                """,
                cid,
                vid,
                rid,
            )
            if not nha:
                return {"ok": True, "already": True, "visit_id": vid}
            khac = [q for q in await _cho_cua(conn, cid, vid) if q["room_id"] != rid]
            if khac:
                raise LuotKhamConflictError(
                    "KHACH_O_PHONG_KHAC",
                    f"Khách đã được phòng {khac[0]['phong'] or 'khác'} nhận — phòng"
                    " ấy Nhả hoặc hoàn tác trước.",
                )
            gan = ServiceRoutingService(self._pool)
            for r in nha:
                kq = await gan._gan(
                    conn,
                    identity,
                    vid=vid,
                    oid=r["oid"],
                    rid=rid,
                    rev=int(r["routing_revision"]),
                    ly_do="MANUAL_CORRECTION",
                    ref=None,
                    tu_dong=False,
                    nguon=NGUON_TAI_PHONG,
                    phat_su_kien=False,
                    vao_hang_luc=r["vao_hang"],
                )
                await emit_event(
                    conn,
                    ten="service.room_release_undone",
                    clinic_id=cid,
                    aggregate_id=r["oid"],
                    so_ke_tiep=True,
                    payload=RoiPhongDaHoanTac(
                        visit_id=vid,
                        service_order_id=r["oid"],
                        room_id=rid,
                        hoan_tac_event_id=r["event_id"],
                        routing_revision=int(kq["routing_revision"]),
                    ),
                    boi=nguoi(identity),
                    correlation_id=vid,
                )
            await cap_nhat_vi_tri(conn, cid, vid)
        return {"ok": True, "visit_id": vid, "room_id": rid, "ve_phong": len(nha)}


async def _su_kien_cuoi(
    conn: asyncpg.Connection, cid: str, oid: str, ten: str
) -> str | None:
    v = await conn.fetchval(
        "SELECT event_id::text FROM domain_event WHERE clinic_id = $1::uuid"
        " AND aggregate_type = 'service_order' AND aggregate_id = $2::uuid"
        " AND event_type = $3 ORDER BY seq DESC LIMIT 1",
        cid,
        oid,
        ten,
    )
    return str(v) if v else None


__all__ = [
    "CHUA_VAO_PHONG_SQL",
    "NHA_BO_DICH_VU",
    "NHA_DIEU_PHOI",
    "NHA_NHAN_CHEO",
    "NhanTaiPhongService",
    "da_sang_phong",
    "dang_bat",
    "dang_o_phong",
    "dem_theo_phong",
    "nha_chi_dinh",
    "nha_khi_bo_chon",
    "roi_phong",
    "sap_den",
]
