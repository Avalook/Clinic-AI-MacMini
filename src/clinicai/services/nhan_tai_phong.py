"""NHẬN KHÁCH TẠI PHÒNG — dây ``nhan_tai_phong`` (Tuyền chốt 07/10/2026).

Kế hoạch: ``docs/KE-HOACH-NHAN-TAI-PHONG.md``. Dây TẮT = y như cũ (dây H4 tự xếp
phòng). Dây BẬT:

    Sắp đến → [Nhận ☑ chỉ định] → Đang chờ → [Bắt đầu] → Đang làm → [Xong]

  * "Sắp đến" của một phòng = MỌI chỉ định chưa vào phòng nào mà phòng ấy làm
    được — bác sĩ chỉ định, làm thêm tại quầy, mang sang khi check-in, kể cả
    khách chưa chốt ở quầy — gom theo KHÁCH, không ẩn theo phòng chuyên.
  * Nhận THEO TỪNG CHỈ ĐỊNH (sửa lỗi staging 07/10: phòng thủ thuật làm được cả
    ba node nên "nhận theo khách" gom luôn hai chỉ định quầy hướng dẫn sang
    phòng siêu âm). Tick sẵn: chỉ định hướng dẫn tới phòng này, hoặc chưa hướng
    dẫn mà phòng này là PHÒNG CHUYÊN ★ (`phong_chuyen`). Còn lại tick được.
  * Không khoá cứng — NHẬN CHÉO theo chỉ định được tick: chỉ định đang chờ ở
    phòng A thì rời hàng A; khách đang LÀM ở A (A quên Xong) thì đóng hàng A
    nhưng lần làm của A GIỮ mở — A tự bấm Xong / Gián đoạn.
  * CHỈ GHI SỰ KIỆN THẬT người bấm (07/10): không có nút Nhả, Xong không tự
    nhả chỉ định khác. Khách rời hàng một phòng chỉ khi phòng khác Nhận
    (NHAN_CHEO) hoặc quầy bỏ dịch vụ (BO_DICH_VU) — sự kiện `service.room_released`.

Hai người Nhận cùng lúc: cả hai khoá LƯỢT (`khoa_luot`) — người sau đọc lại thấy
chỉ định đã ở phòng kia và nhận câu hỏi nhận chéo, không có hai phòng cùng giữ.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import KhachRoiPhong, NhanVaoPhongDaHoanTac
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

NHA_NHAN_CHEO = "NHAN_CHEO"
NHA_BO_DICH_VU = "BO_DICH_VU"
ACTION_NHAN = "service_routing.receive"

#: Trạng thái một chỉ định NHÌN TỪ một phòng (ô khách ở mọi danh sách).
SAP_DEN = "sap_den"
CHO = "cho"
LAM = "lam"
XONG = "xong"
PHONG_KHAC = "o_phong_khac"

#: Chỉ định CHƯA VÀO PHÒNG NÀO (alias ``o`` service_order, ``v`` visit): bác sĩ
#: đã duyệt, khách chưa bỏ, chưa bắt đầu, lượt còn mở, không phải đối tác làm
#: trọn, không bị bác sĩ dặn "làm sau khi đọc kết quả vòng trước". KHÔNG xét
#: nguồn sinh ra chỉ định và KHÔNG đòi khách đã chốt / đã thu. Lượt INCOMPLETE
#: (khách về giữa chừng) cố ý loại: khách đã rời phòng khám thì không "sắp đến".
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

#: Mỗi (phòng, chỉ định phòng làm được) của khách check-in hôm nay, kèm chỗ
#: chờ sống mới nhất của chỉ định (phòng nào, chờ hay làm). Một truy vấn cho
#: Sắp đến, ô khách, đếm và lệnh Nhận — cùng một cách nhìn.
_CHI_DINH_SQL = f"""
WITH o AS MATERIALIZED (
    SELECT o.id, o.clinic_id, o.visit_id, o.node_code, o.service_code,
           o.service_name, o.selection_status, o.routing_revision,
           o.execution_status, o.room_id, o.phong_du_kien_id, o.created_at,
           ({CHUA_VAO_PHONG_SQL}) AS chua_vao,
           coalesce(v.location_id, a.location_id) AS co_so, v.checked_in_at,
           p.full_name, p.patient_code, a.so_tiep_don, a.so_booking,
           q.id AS q_id, q.status AS q_status, q.room_id AS q_room_id
      FROM service_order o
      JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
      JOIN patient p
        ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
      LEFT JOIN appointment a
        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
      LEFT JOIN LATERAL (
           SELECT q.id::text AS id, q.status, q.room_id
             FROM queue_entry q
            WHERE q.clinic_id = o.clinic_id AND q.ref_id = o.id
              AND q.reason = 'SERVICE' AND q.lane = 'ROOM'
              AND q.status IN ('waiting', 'called', 'blocked', 'serving')
            ORDER BY q.updated_at DESC LIMIT 1) q ON true
     WHERE o.clinic_id = $1::uuid
       AND ($3::uuid[] IS NULL OR o.visit_id = ANY($3::uuid[]))
       AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
           = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       AND o.exec_status NOT IN ('draft', 'cancelled')
       AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
       AND NOT {DOI_TAC_LAM_TRON_SQL}
)
SELECT pr.id::text AS room_id, pr.accepting,
       o.id::text AS id, o.visit_id::text AS visit_id,
       o.service_name, o.selection_status, o.routing_revision,
       o.execution_status, o.room_id::text AS o_room_id, orr.name AS o_phong,
       o.phong_du_kien_id::text AS huong_dan_id, hd.name AS huong_dan,
       -- ★ chỉ cần khi vẽ ô (đếm toàn phòng khám thì bỏ cho nhẹ).
       CASE WHEN $4::boolean THEN false
            ELSE phong_chuyen(pr.clinic_id, pr.id, o.node_code, o.service_code)
       END AS chuyen,
       o.chua_vao,
       o.q_id, o.q_status, o.q_room_id::text AS q_room_id,
       qr.name AS q_phong,
       o.full_name, o.patient_code, o.so_tiep_don, o.so_booking
  FROM o
  -- Phòng ỨNG VIÊN đi theo chỉ mục (bước / dịch vụ gắn riêng) rồi mới hỏi luật
  -- `phong_lam_duoc` — tránh tích chéo mọi phòng × mọi chỉ định.
  CROSS JOIN LATERAL (
       SELECT rn.room_id FROM clinic_room_node rn
        WHERE rn.clinic_id = o.clinic_id AND rn.node_code = o.node_code
       UNION
       SELECT s.room_id FROM clinic_room_service s
        WHERE s.clinic_id = o.clinic_id AND s.service_code = o.service_code
  ) ung
  JOIN clinic_room pr
    ON pr.id = ung.room_id AND pr.clinic_id = o.clinic_id
   AND ($2::uuid IS NULL OR pr.id = $2::uuid)
   AND pr.is_active AND NOT pr.la_doi_tac
   AND (pr.location_id IS NULL OR o.co_so IS NULL OR pr.location_id = o.co_so)
   AND {phong_lam_duoc_sql("pr", "o")}
  LEFT JOIN clinic_room hd
    ON hd.id = o.phong_du_kien_id AND hd.clinic_id = o.clinic_id
  LEFT JOIN clinic_room orr ON orr.id = o.room_id AND orr.clinic_id = o.clinic_id
  LEFT JOIN clinic_room qr ON qr.id = o.q_room_id AND qr.clinic_id = o.clinic_id
 WHERE o.clinic_id = $1::uuid
   AND (NOT $4::boolean
        OR o.chua_vao OR o.q_id IS NOT NULL OR o.execution_status = 'IN_PROGRESS')
 ORDER BY o.checked_in_at, o.created_at, o.id
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


def trang_thai_chi_dinh(
    r: Any, room_id: str, *, tien_chan: bool
) -> dict[str, Any] | None:
    """Một chỉ định NHÌN TỪ phòng ``room_id`` — HÀM THUẦN. None = không hiện
    (đang giữ chờ đọc kết quả, tiền đang hoàn, lượt đã đóng…).

    ``nhan_duoc``: phòng bấm Nhận được chỉ định này — chưa vào phòng nào, hoặc
    đang CHỜ ở phòng khác (nhận chéo). ``tick_san``: hướng dẫn tới đây, hoặc
    chưa hướng dẫn mà đây là phòng chuyên ★."""
    ex = r["execution_status"]
    o_dau: str | None = None
    o_trang: str | None = None
    if ex in ("COMPLETED", "NOT_PERFORMED"):
        tt = XONG
        o_dau = r["o_phong"] if r["o_room_id"] != room_id else None
    elif ex in ("IN_PROGRESS", "INTERRUPTED"):
        if r["o_room_id"] == room_id:
            tt = LAM
        else:
            tt, o_dau, o_trang = PHONG_KHAC, r["o_phong"], LAM
    elif r["q_id"] is not None:
        lam = r["q_status"] == "serving"
        if r["q_room_id"] == room_id:
            tt = LAM if lam else CHO
        else:
            tt, o_dau, o_trang = PHONG_KHAC, r["q_phong"], LAM if lam else CHO
    elif r["chua_vao"] and not tien_chan:
        tt = SAP_DEN
    else:
        return None
    nhan_duoc = tt == SAP_DEN or (tt == PHONG_KHAC and o_trang == CHO)
    hd = r["huong_dan_id"]
    return {
        "id": r["id"],
        "ten": r["service_name"],
        "trang_thai": tt,
        "phong": o_dau,
        "o_trang_thai": o_trang,
        "huong_dan_id": hd,
        "huong_dan": r["huong_dan"],
        "huong_dan_day": hd == room_id,
        "chuyen": bool(r["chuyen"]),
        "chua_chot": r["selection_status"] != "SELECTED",
        "nhan_duoc": nhan_duoc,
        "tick_san": nhan_duoc and (hd == room_id or (hd is None and bool(r["chuyen"]))),
    }


async def _chi_dinh(
    conn: asyncpg.Connection,
    cid: str,
    room_id: str | None = None,
    visit_ids: Sequence[str] | None = None,
    *,
    chi_sap_den: bool = False,
) -> list[tuple[asyncpg.Record, dict[str, Any]]]:
    """(dòng, trạng thái nhìn từ phòng của dòng) — bỏ dòng không hiện.
    ``chi_sap_den``: chỉ những chỉ định có thể làm khách "sắp đến" / đang ở
    phòng (cho đếm toàn phòng khám — bỏ chỉ định đã xong không hướng dẫn)."""
    rows = await conn.fetch(
        _CHI_DINH_SQL,
        cid,
        room_id,
        list(visit_ids) if visit_ids is not None else None,
        chi_sap_den,
    )
    tien = await finance_gate.states_for_orders(
        conn, cid, list({r["id"] for r in rows if r["chua_vao"]})
    )
    out: list[tuple[asyncpg.Record, dict[str, Any]]] = []
    for r in rows:
        q = tien.get(r["id"])
        c = trang_thai_chi_dinh(
            r,
            r["room_id"],
            tien_chan=q is not None and q.finance_state in TIEN_CHAN_NHAN,
        )
        if c is not None:
            out.append((r, c))
    return out


def gom_sap_den(
    dong: Iterable[tuple[Any, dict[str, Any]]], room_id: str
) -> list[dict[str, Any]]:
    """Khách SẮP ĐẾN phòng ``room_id`` — HÀM THUẦN. MỌI khách có chỉ định phòng
    làm được chưa xong: chưa vào phòng nào, HOẶC đang chờ / đang làm ở phòng
    khác (Tuyền 07/10: list đủ hết, "ngu ngu tí nhưng pick ra dễ" — nhãn nói
    đang ở đâu, nhận chéo theo luật). Trừ khách đã có chỉ định chờ / làm ở
    chính phòng này (nằm ở "Đang chờ", nhận tiếp bằng "Nhận thêm").

    ``tinh_so``: khách có ít nhất một chỉ định CHƯA VÀO PHÒNG NÀO — chỉ những
    khách này vào số "sắp đến" (khách đang ở phòng khác đã được đếm ở "đang
    chờ / đang làm" của phòng ấy, không đếm hai lần). Khách có chỉ định tick
    sẵn (hướng dẫn tới / phòng chuyên) lên đầu, giữ thứ tự check-in."""
    khach: dict[str, dict[str, Any]] = {}
    o_day: set[str] = set()
    for r, c in dong:
        if r["room_id"] != room_id:
            continue
        if c["trang_thai"] in (CHO, LAM):
            o_day.add(r["visit_id"])
        k = khach.setdefault(
            r["visit_id"],
            {
                "visit_id": r["visit_id"],
                "khach": r["full_name"],
                "ma_khach": r["patient_code"],
                "so_tiep_don": r["so_tiep_don"],
                "so_booking": r["so_booking"],
                "accepting": r["accepting"],
                "chi_dinh": [],
            },
        )
        k["chi_dinh"].append(c)
    out = []
    for vid, k in khach.items():
        sap = [c for c in k["chi_dinh"] if c["trang_thai"] in (SAP_DEN, PHONG_KHAC)]
        if vid in o_day or not sap or not k.pop("accepting"):
            continue
        k["tinh_so"] = any(c["trang_thai"] == SAP_DEN for c in sap)
        k["nhan_duoc"] = any(c["nhan_duoc"] for c in sap)
        k["duoc_huong_dan"] = any(c["huong_dan_day"] for c in sap)
        k["co_tick_san"] = any(c["tick_san"] for c in k["chi_dinh"])
        k["so_chi_dinh"] = len(k["chi_dinh"])
        out.append(k)
    return sorted(out, key=lambda k: not k["co_tick_san"])


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
    """Danh sách SẮP ĐẾN của một phòng, theo KHÁCH (mỗi khách một ô, trong ô
    các chỉ định phòng làm được kèm trạng thái + tick sẵn). Khách đang chờ /
    làm ở phòng khác mang nhãn nơi ấy."""
    khach = gom_sap_den(await _chi_dinh(conn, cid, room_id), room_id)
    o_dau = await dang_o_phong(conn, cid, [k["visit_id"] for k in khach], ca_cho=True)
    for k in khach:
        noi = o_dau.get(k["visit_id"])
        k["dang_o_phong"] = noi if noi and noi["phong_id"] != room_id else None
    return khach


async def chi_dinh_cua_khach(
    conn: asyncpg.Connection, cid: str, room_id: str, visit_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """Ô KHÁCH ở hàng chờ phòng (đang chờ · đang làm · đã xong): mỗi khách các
    chỉ định phòng làm được kèm trạng thái — "Nhận thêm" nhận những cái
    ``nhan_duoc``."""
    out: dict[str, list[dict[str, Any]]] = {}
    if not visit_ids:
        return out
    for r, c in await _chi_dinh(conn, cid, room_id, list(set(visit_ids))):
        out.setdefault(r["visit_id"], []).append(c)
    return out


async def dem_theo_phong(
    conn: asyncpg.Connection, cid: str, *, bat: bool
) -> dict[str, dict[str, int | None]]:
    """Ba số của mỗi phòng: sắp đến (chỉ khi dây bật) · đang chờ · đang làm —
    số KHÁCH, lượt check-in hôm nay. Mỗi khách đúng một nhóm của phòng: có
    chỉ định đang làm → "đang làm"; không thì có chỉ định chờ → "đang chờ";
    khách đã ở phòng không tính "sắp đến" (cùng luật ``gom_sap_den``)."""
    out: dict[str, dict[str, int | None]] = {}

    def o(rid: str) -> dict[str, int | None]:
        return out.setdefault(
            rid, {"sap_den": 0 if bat else None, "dang_cho": 0, "dang_lam": 0}
        )

    if bat:
        theo_phong: dict[str, list[tuple[asyncpg.Record, dict[str, Any]]]] = {}
        for r, c in await _chi_dinh(conn, cid, chi_sap_den=True):
            theo_phong.setdefault(r["room_id"], []).append((r, c))
        for rid, dong in theo_phong.items():
            o(rid)["sap_den"] = sum(1 for k in gom_sap_den(dong, rid) if k["tinh_so"])
    hom_nay = (
        "(v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        " = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    )
    # Đang làm theo LẦN LÀM đang mở của phòng — kể cả khi khách đã được phòng
    # khác nhận (nhận chéo), vì phòng này vẫn còn một việc phải bấm Xong.
    lam: dict[str, set[str]] = {}
    for r in await conn.fetch(
        "SELECT o.room_id::text AS room_id, o.visit_id::text AS visit_id"
        "  FROM service_order o JOIN visit v"
        "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
        " WHERE o.clinic_id = $1::uuid AND o.execution_status = 'IN_PROGRESS'"
        "   AND o.room_id IS NOT NULL AND " + hom_nay,
        cid,
    ):
        lam.setdefault(r["room_id"], set()).add(r["visit_id"])
    cho: dict[str, set[str]] = {}
    for r in await conn.fetch(
        "SELECT q.room_id::text AS room_id, q.visit_id::text AS visit_id"
        "  FROM queue_entry q JOIN visit v"
        "    ON v.visit_id = q.visit_id AND v.clinic_id = q.clinic_id"
        " WHERE q.clinic_id = $1::uuid AND q.reason = 'SERVICE' AND q.lane = 'ROOM'"
        "   AND q.room_id IS NOT NULL"
        "   AND q.status IN ('waiting', 'called', 'blocked') AND " + hom_nay,
        cid,
    ):
        cho.setdefault(r["room_id"], set()).add(r["visit_id"])
    for rid, vids in lam.items():
        o(rid)["dang_lam"] = len(vids)
    for rid, vids in cho.items():
        o(rid)["dang_cho"] = len(vids - lam.get(rid, set()))
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
    """Khách RỜI những chỗ chờ ``cho`` (dòng ``_O_PHONG_SQL``) — chỉ khi có thao
    tác thật: phòng khác Nhận (NHAN_CHEO) hoặc quầy bỏ dịch vụ (BO_DICH_VU).
    Chỗ chờ đóng; chỉ định chưa bắt đầu về "chưa vào phòng nào"; khách đang LÀM
    thì lần làm giữ mở. Mỗi chỗ một sự kiện `service.room_released`. Người gọi
    đã kiểm quyền + khoá lượt. Trả các chỉ định đã về chưa vào phòng."""
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


def _ma_chi_dinh(ids: Sequence[Any] | None) -> list[str] | None:
    if ids is None:
        return None
    if not isinstance(ids, list | tuple):
        raise LuotKhamConflictError(
            "CHI_DINH_KHONG_HOP_LE", "Danh sách chỉ định không hợp lệ."
        )
    return list(dict.fromkeys(_uuid(i, "Mã chỉ định không hợp lệ.") for i in ids))


class NhanTaiPhongService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def nhan(
        self,
        *,
        visit_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        chi_dinh_ids: Sequence[Any] | None = None,
        xac_nhan: bool = False,
        bac_si_lam_id: Any = KHONG_DOI,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """ReceiveAtRoom — phòng nhận CÁC CHỈ ĐỊNH ĐƯỢC TICK (``chi_dinh_ids``;
        không gửi = những cái máy chủ tick sẵn). Cũng là "Nhận thêm" khi khách
        đã chờ ở phòng. Phải có ≥1 chỉ định.

        Nhận chéo — 409 ``KHACH_O_PHONG_KHAC`` (kèm tên phòng), gửi lại
        ``xac_nhan`` (một nút, không lý do) khi: chỉ định được tick đang CHỜ ở
        phòng khác (rời hàng ấy), hoặc khách đang LÀM ở phòng khác (đóng hàng
        ấy, lần làm giữ mở). Chỉ định KHÔNG tick ở phòng khác không bị đụng.
        Chỉ định không nhận được (tiền đang hoàn…) bỏ qua, trả câu lý do;
        không nhận được cái nào thì báo lỗi của cái đầu tiên."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        ids = _ma_chi_dinh(chi_dinh_ids)
        cid = identity.clinic_id
        payload = {
            "visit_id": vid,
            "room_id": rid,
            "xac_nhan": bool(xac_nhan),
            "chi_dinh_ids": sorted(ids) if ids is not None else None,
        }
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
            ds = {c["id"]: c for _, c in await _chi_dinh(conn, cid, rid, [vid])}
            if ids is None:
                chon = [c for c in ds.values() if c["tick_san"]]
            else:
                chon = [ds[i] for i in ids if i in ds and ds[i]["nhan_duoc"]]
                da_o_day = [
                    i for i in ids if i in ds and ds[i]["trang_thai"] in (CHO, LAM)
                ]
                if not chon and da_o_day and len(da_o_day) == len(ids):
                    return {"ok": True, "already": True, "visit_id": vid}
            if not chon:
                if not any(c["nhan_duoc"] for c in ds.values()):
                    if any(c["trang_thai"] in (CHO, LAM) for c in ds.values()):
                        return {"ok": True, "already": True, "visit_id": vid}
                    raise LuotKhamConflictError(
                        "KHONG_CON_GI_DE_NHAN",
                        "Khách không còn dịch vụ nào chờ vào phòng này — tải lại.",
                    )
                raise LuotKhamConflictError(
                    "CHUA_CHON_CHI_DINH",
                    "Tick ít nhất một chỉ định để nhận vào phòng này.",
                )
            cho = await _cho_cua(conn, cid, vid)
            chon_ids = {c["id"] for c in chon}
            khac = [
                q
                for q in cho
                if q["room_id"] != rid
                and (q["ref_id"] in chon_ids or q["status"] == "serving")
            ]
            if khac and not xac_nhan:
                lam = next((q for q in khac if q["status"] == "serving"), None)
                q0 = lam or khac[0]
                ten = q0["phong"] or "khác"
                cau = (
                    f"Khách đang làm ở phòng {ten} — nhận sang phòng này?"
                    if lam
                    else "Chỉ định "
                    + ", ".join(
                        c["ten"] or "" for c in chon if c["trang_thai"] == PHONG_KHAC
                    )
                    + f" đang chờ ở phòng {ten} — nhận sang phòng này?"
                )
                raise LuotKhamConflictError(
                    "KHACH_O_PHONG_KHAC",
                    cau,
                    {
                        "ma": "KHACH_O_PHONG_KHAC",
                        "phong": q0["phong"],
                        "trang_thai": "lam" if lam else "cho",
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
            for c in chon:
                rev = await conn.fetchval(
                    "SELECT routing_revision FROM service_order"
                    " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                    cid,
                    c["id"],
                )
                try:
                    async with conn.transaction():
                        await gan._gan(
                            conn,
                            identity,
                            vid=vid,
                            oid=c["id"],
                            rid=rid,
                            rev=int(rev),
                            ly_do="INITIAL_ASSIGNMENT",
                            ref=None,
                            tu_dong=False,
                            nguon=NGUON_TAI_PHONG,
                            bac_si=bac_si_lam_id,
                            doi_chieu={
                                **doi_chieu,
                                "huong_dan_room_id": c["huong_dan_id"],
                                "dung_huong_dan": None
                                if c["huong_dan_id"] is None
                                else c["huong_dan_id"] == rid,
                                "nhan_cheo_tu_room_id": tu_phong,
                            },
                        )
                    da_nhan.append(c["id"])
                except LuotKhamConflictError as e:
                    loi_dau = loi_dau or e
                    bo_qua.append({"id": c["id"], "ten": c["ten"], "cau": str(e)})
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
        self,
        *,
        visit_id: Any,
        room_id: Any,
        identity: StaffIdentity,
        chi_dinh_ids: Sequence[Any] | None = None,
    ) -> dict[str, Any]:
        """UndoReceiveAtRoom — các chỉ định ``chi_dinh_ids`` (không gửi = mọi
        chỉ định đang CHỜ ở phòng) về "Sắp đến" (không như huỷ xếp phòng: không
        REASSIGNMENT_REQUIRED, không đẻ việc trưởng ca). Chỉ định đã Bắt đầu
        thì Huỷ bắt đầu trước. Bấm hai lần = ``already``."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        rid = _uuid(room_id, "Mã phòng không hợp lệ.")
        ids = _ma_chi_dinh(chi_dinh_ids)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn, identity, QUYEN_XEP, cau="Bạn không có quyền điều phối khách."
            )
            await khoa_luot(conn, cid, vid)
            cho = [
                q
                for q in await _cho_cua(conn, cid, vid)
                if q["room_id"] == rid and (ids is None or q["ref_id"] in ids)
            ]
            dang_lam = [q for q in cho if q["status"] == "serving"]
            cho = [q for q in cho if q["status"] != "serving"]
            if dang_lam and (ids is not None or not cho):
                raise LuotKhamConflictError(
                    "KHACH_DANG_LAM",
                    "Khách đang được làm dịch vụ ở phòng này — bấm Xong / Huỷ bắt"
                    " đầu trước.",
                )
            if not cho:
                return {"ok": True, "already": True, "visit_id": vid}
            ve: list[str] = []
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
    "NHA_NHAN_CHEO",
    "NhanTaiPhongService",
    "chi_dinh_cua_khach",
    "da_sang_phong",
    "dang_bat",
    "dang_o_phong",
    "dem_theo_phong",
    "gom_sap_den",
    "nha_khi_bo_chon",
    "roi_phong",
    "sap_den",
    "trang_thai_chi_dinh",
]
