"""NHẬN KHÁCH TẠI PHÒNG — dây ``nhan_tai_phong`` (Tuyền chốt 07/10/2026).

Kế hoạch: ``docs/KE-HOACH-NHAN-TAI-PHONG.md``. Dây TẮT = y như cũ (dây H4 tự xếp
phòng). Dây BẬT:

    Sắp đến → [Nhận] (từng chỉ định) → Đang chờ → [Bắt đầu] → Đang làm → [Xong]

  * "Sắp đến" của một phòng = MỌI khách check-in hôm nay chưa check-out, cùng
    cơ sở (Tuyền 07/10 tối) — mỗi khách một ô, trong ô các chỉ định phòng làm
    được (kể cả khách chưa chốt ở quầy) với nút theo dòng; khách chưa có chỉ
    định ở phòng mang nhãn nơi đang ở thật. Khách đang chờ / làm ở chính phòng
    này nằm ở "Đang chờ / Đang làm", không lặp ở đây.
  * Nhận THEO TỪNG CHỈ ĐỊNH (sửa lỗi staging 07/10: phòng thủ thuật làm được cả
    ba node nên "nhận theo khách" gom luôn hai chỉ định quầy hướng dẫn sang
    phòng siêu âm): mỗi dòng một nút Nhận, thêm "Nhận cả N". PHÒNG CHUYÊN ★
    (`phong_chuyen`) và hướng dẫn chỉ là nhãn + thứ tự xếp, không quyết gì.
  * Không khoá cứng — NHẬN CHÉO theo chỉ định được nhận: chỉ định đang chờ ở
    phòng A thì rời hàng A; khách đang LÀM ở A (A quên Xong) thì đóng hàng A
    nhưng lần làm của A GIỮ mở — A tự bấm Xong / Gián đoạn.
  * CHỈ GHI SỰ KIỆN THẬT người bấm (07/10): không có nút Nhả, Xong không tự
    nhả chỉ định khác. Khách rời hàng một phòng chỉ khi phòng khác Nhận
    (NHAN_CHEO) hoặc quầy bỏ dịch vụ (BO_DICH_VU) — sự kiện `service.room_released`.

Hai người Nhận cùng lúc: cả hai khoá LƯỢT (`khoa_luot`) — người sau đọc lại thấy
chỉ định đã ở phòng kia và nhận câu hỏi nhận chéo, không có hai phòng cùng giữ.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import (
    KhachRoiPhong,
    NhanVaoPhongDaHoanTac,
    NhaPhongDaHoanTac,
)
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services import finance_gate
from clinicai.services.day_noi import doc_day
from clinicai.services.hang_cho import (
    cap_nhat_vi_tri,
    chan_cho_khac,
    mo_cho_bi_chan,
    ve_lai_hang_phong,
)
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

#: Lượt đã check-out: không nhận vào phòng (cùng câu với lệnh bàn khám).
CAU_DA_CHECK_OUT = "Lượt đã check-out — mở lại lượt trước."
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


#: Chỉ định đang có lần làm do BÀN KHÁM mở (`noi_lam = BAN_KHAM`) + bác sĩ của
#: bàn khám (phiên khám chính của lượt; không có thì người bấm).
_BAN_KHAM_SQL = """
SELECT a.service_order_id::text AS oid, a.started_at,
       coalesce(bs.full_name, nb.full_name) AS bac_si
  FROM service_execution_attempt a
  JOIN service_order o ON o.id = a.service_order_id AND o.clinic_id = a.clinic_id
  LEFT JOIN staff nb ON nb.id = a.started_by
  LEFT JOIN LATERAL (
       SELECT s.full_name
         FROM consultation c JOIN staff s ON s.id = c.doctor_staff_id
        WHERE c.clinic_id = o.clinic_id AND c.visit_id = o.visit_id
          AND c.kind = 'PRIMARY' AND c.status <> 'cancelled'
        ORDER BY c.round_no DESC LIMIT 1) bs ON true
 WHERE a.clinic_id = $1::uuid AND a.service_order_id = ANY($2::uuid[])
   AND a.status = 'IN_PROGRESS' AND a.noi_lam = 'BAN_KHAM'
"""

#: Điều kiện SQL "chỉ định này KHÔNG đang làm ở bàn khám" (alias đơn ``ref``).
KHONG_LAM_BAN_KHAM_SQL = """NOT EXISTS (
    SELECT 1 FROM service_execution_attempt bk
     WHERE bk.clinic_id = $1::uuid AND bk.service_order_id = {ref}
       AND bk.status = 'IN_PROGRESS' AND bk.noi_lam = 'BAN_KHAM')"""


def cau_ban_kham(bac_si: str | None) -> str:
    """Nơi đang làm khi bác sĩ làm chỉ định ngay tại bàn khám — HÀM THUẦN."""
    return f"bàn khám BS {bac_si}" if bac_si else "bàn khám"


async def ban_kham_dang_lam(
    conn: asyncpg.Connection, cid: str, order_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Chỉ định đang làm TẠI BÀN KHÁM: ``{bac_si, luc, noi}`` — phòng của chỉ
    định không coi là việc của mình (không đếm "đang làm", không Xong hộ)."""
    if not order_ids:
        return {}
    return {
        r["oid"]: {
            "bac_si": r["bac_si"],
            "luc": r["started_at"].isoformat() if r["started_at"] else None,
            "noi": cau_ban_kham(r["bac_si"]),
        }
        for r in await conn.fetch(_BAN_KHAM_SQL, cid, list(set(order_ids)))
    }


def trang_thai_chi_dinh(
    r: Any,
    room_id: str,
    *,
    tien_chan: bool,
    cau_tien: str | None = None,
    ban_kham: str | None = None,
) -> dict[str, Any] | None:
    """Một chỉ định NHÌN TỪ phòng ``room_id`` — HÀM THUẦN. None = không hiện
    (đang giữ chờ đọc kết quả, tiền đang hoàn, lượt đã đóng…).

    ``nhan_duoc``: phòng bấm Nhận được chỉ định này — chưa vào phòng nào, hoặc
    đang CHỜ ở phòng khác (nhận chéo) — và tiền không đang hoàn / đã hoàn / sổ
    lệch (``tien_chan``, cả khi đang chờ ở phòng khác; ``cau_tien`` = vì sao,
    trả ở ``ly_do_khong_nhan``). ``ban_kham`` = nhãn nơi làm khi bác sĩ đang làm
    chỉ định này tại bàn khám (không phải việc của phòng nào). ``chuyen`` (★) /
    ``huong_dan_day``: chỉ để gắn nhãn và xếp trước."""
    ex = r["execution_status"]
    o_dau: str | None = None
    o_trang: str | None = None
    if ex == "IN_PROGRESS" and ban_kham:
        tt, o_dau, o_trang = PHONG_KHAC, ban_kham, LAM
    elif ex in ("COMPLETED", "NOT_PERFORMED"):
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
    cho_khac = tt == PHONG_KHAC and o_trang == CHO
    nhan_duoc = tt == SAP_DEN or (cho_khac and not tien_chan)
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
        "ly_do_khong_nhan": (cau_tien or "Tiền của dịch vụ này đang cần xử lý.")
        if cho_khac and tien_chan
        else None,
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
    # Cổng tiền cho MỌI chỉ định có thể bị Nhận: chưa vào phòng nào VÀ đang chờ
    # ở phòng khác (review 07/10: chỉ định chờ ở A mà tiền đang hoàn vẫn bị B
    # nhận → rời A rồi không vào được B, mất chỗ).
    tien = await finance_gate.states_for_orders(
        conn,
        cid,
        list({r["id"] for r in rows if r["chua_vao"] or r["q_id"] is not None}),
    )
    bk = await ban_kham_dang_lam(
        conn,
        cid,
        [r["id"] for r in rows if r["execution_status"] == "IN_PROGRESS"],
    )
    out: list[tuple[asyncpg.Record, dict[str, Any]]] = []
    for r in rows:
        q = tien.get(r["id"])
        chan = q is not None and q.finance_state in TIEN_CHAN_NHAN
        c = trang_thai_chi_dinh(
            r,
            r["room_id"],
            tien_chan=chan,
            cau_tien=finance_gate.cau_chan_lam(q) if chan else None,
            ban_kham=(bk.get(r["id"]) or {}).get("noi"),
        )
        if c is not None:
            out.append((r, c))
    return out


#: Khách check-in HÔM NAY chưa check-out, cùng cơ sở với phòng, kèm chỗ chờ
#: sống "cao nhất" của khách (đang làm trước, phòng dịch vụ trước) — một câu
#: cho cả danh sách Sắp đến (không N+1).
_KHACH_HOM_NAY_SQL = """
SELECT v.visit_id::text AS visit_id, p.full_name, p.patient_code,
       a.so_tiep_don, a.so_booking,
       q.lane AS q_lane, q.status AS q_status, q.room_id::text AS q_room_id,
       qr.name AS q_phong, st.nhom AS nhom_kham,
       EXISTS (SELECT 1 FROM consultation c
                WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
                  AND c.kind = 'PRIMARY' AND c.status <> 'queued') AS da_qua_ban_kham,
       (SELECT count(*) FROM service_order o
         WHERE o.clinic_id = v.clinic_id AND o.visit_id = v.visit_id
           AND o.exec_status NOT IN ('draft', 'cancelled')
           AND o.selection_status IS DISTINCT FROM 'NOT_SELECTED'
           AND coalesce(o.execution_status, 'PENDING')
               IN ('PENDING', 'IN_PROGRESS', 'INTERRUPTED')) AS con_viec
  FROM clinic_room pr
  JOIN visit v ON v.clinic_id = pr.clinic_id
  JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN appointment a ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN service_type st
    ON st.id = v.service_type_id AND st.clinic_id = v.clinic_id
  LEFT JOIN LATERAL (
       SELECT q.lane, q.status, q.room_id
         FROM queue_entry q
        WHERE q.clinic_id = v.clinic_id AND q.visit_id = v.visit_id
          AND q.status IN ('waiting', 'called', 'serving')
        ORDER BY (q.status = 'serving') DESC, (q.lane = 'ROOM') DESC,
                 q.updated_at DESC
        LIMIT 1) q ON true
  LEFT JOIN clinic_room qr ON qr.id = q.room_id AND qr.clinic_id = v.clinic_id
 WHERE pr.clinic_id = $1::uuid AND pr.id = $2::uuid
   AND pr.is_active AND NOT pr.la_doi_tac
   AND v.clinic_id = $1::uuid
   AND v.closed_at IS NULL AND v.status <> 'INCOMPLETE'
   AND v.checked_in_at IS NOT NULL
   AND (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
       = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
   AND (pr.location_id IS NULL
        OR coalesce(v.location_id, a.location_id) IS NULL
        OR pr.location_id = coalesce(v.location_id, a.location_id))
 ORDER BY v.checked_in_at, v.visit_id
"""


#: Nhãn ô Sắp đến khi khách không đứng hàng nào và chưa có chỉ định phòng làm được.
CAU_CHUA_CO_CHI_DINH = "chưa có chỉ định ở phòng này"
#: Lượt Điều trị không qua bàn khám, mọi chỉ định đã xong — hàng bác sĩ chỉ là
#: tuỳ chọn, khách thật ra đang đi thanh toán (Tuyền 07/10: "đang chờ khám" sai).
CAU_CHO_THANH_TOAN = "chờ thanh toán / check-out"


def cho_thanh_toan(k: Mapping[str, Any]) -> bool:
    """Lượt nhóm Điều trị chưa từng vào bàn khám và không còn chỉ định chờ làm."""
    return (
        k.get("nhom_kham") == "DIEU_TRI"
        and not k.get("da_qua_ban_kham")
        and not k.get("con_viec")
    )


def cau_dang_o(
    lane: str | None,
    status: str | None,
    phong: str | None,
    *,
    cho_tt: bool = False,
) -> str | None:
    """Khách đang ở đâu THẬT (chỗ chờ sống cao nhất) — HÀM THUẦN, câu máy chủ
    viết cho ô Sắp đến. None = không đứng hàng nào (vd chờ đo sinh hiệu).
    ``cho_tt``: lượt Điều trị xong hết, hàng bác sĩ chỉ là tuỳ chọn."""
    lam = status == "serving"
    if cho_tt and not lam and lane in (None, "DOCTOR"):
        return CAU_CHO_THANH_TOAN
    if lane == "ROOM":
        return f"đang {'làm' if lam else 'chờ'} ở {phong or 'phòng khác'}"
    if lane == "DOCTOR":
        return f"đang khám ở {phong or 'bàn khám'}" if lam else "đang chờ khám"
    if lane == "TU_VAN":
        return "đang tư vấn" if lam else "đang chờ tư vấn"
    return None


def o_phong_nay(dong: Iterable[tuple[Any, dict[str, Any]]], room_id: str) -> set[str]:
    """Khách đã có chỉ định chờ / làm ở CHÍNH phòng này (nằm ở hàng chờ phòng)."""
    return {
        r["visit_id"]
        for r, c in dong
        if r["room_id"] == room_id and c["trang_thai"] in (CHO, LAM)
    }


def dem_sap_den(dong: Iterable[tuple[Any, dict[str, Any]]], room_id: str) -> int:
    """Số "sắp đến" của phòng — HÀM THUẦN: khách có chỉ định CHƯA VÀO PHÒNG NÀO
    mà phòng làm được, chưa chờ / làm ở phòng này, phòng đang nhận khách. Khách
    đang ở phòng khác đã được đếm ở "đang chờ / đang làm" phòng ấy."""
    ds = [(r, c) for r, c in dong if r["room_id"] == room_id]
    o_day = o_phong_nay(ds, room_id)
    return len(
        {r["visit_id"] for r, c in ds if c["trang_thai"] == SAP_DEN and r["accepting"]}
        - o_day
    )


def gom_sap_den(
    khach: Iterable[Mapping[str, Any]],
    dong: Iterable[tuple[Any, dict[str, Any]]],
    room_id: str,
) -> list[dict[str, Any]]:
    """Ô SẮP ĐẾN của phòng ``room_id`` — HÀM THUẦN. ``khach`` = khách hôm nay
    (``_KHACH_HOM_NAY_SQL``), ``dong`` = chỉ định phòng làm được.

    MỌI khách trừ khách đang chờ / làm ở chính phòng này, và khách ĐÃ XONG ở
    phòng này mà không còn gì nhận được ở đây (họ chỉ nằm ở "Đã xong" — mỗi
    khách đúng một nhóm; hiện hai chỗ thì trông như hai người). Mỗi ô: các chỉ định
    phòng làm được + trạng thái; ``dang_o`` = câu nơi khách đang ở thật (không
    đứng hàng nào mà chưa có chỉ định ở phòng → ``CAU_CHUA_CO_CHI_DINH``).
    ``tinh_so`` = khách vào số "sắp đến" (cùng luật ``dem_sap_den``). Xếp: có
    chỉ định nhận được mà ★ / hướng dẫn tới đây → có chỉ định nhận được → còn
    lại; trong nhóm giữ thứ tự check-in."""
    ds = [(r, c) for r, c in dong if r["room_id"] == room_id]
    o_day = o_phong_nay(ds, room_id)
    xong_day = {
        r["visit_id"]
        for r, c in ds
        if c["trang_thai"] == XONG and r["o_room_id"] == room_id
    }
    cd: dict[str, list[dict[str, Any]]] = {}
    for r, c in ds:
        cd.setdefault(r["visit_id"], []).append(c)
    out = []
    for k in khach:
        vid = k["visit_id"]
        if vid in o_day:
            continue
        cua = cd.get(vid, [])
        nhan = [c for c in cua if c["nhan_duoc"]]
        if vid in xong_day and not nhan:
            continue
        out.append(
            {
                "visit_id": vid,
                "khach": k["full_name"],
                "ma_khach": k["patient_code"],
                "so_tiep_don": k["so_tiep_don"],
                "so_booking": k["so_booking"],
                "chi_dinh": cua,
                "so_chi_dinh": len(cua),
                "so_nhan_duoc": len(nhan),
                "tinh_so": any(c["trang_thai"] == SAP_DEN for c in cua),
                "duoc_huong_dan": any(c["huong_dan_day"] for c in cua),
                "dang_o": (
                    cau_dang_o(
                        k["q_lane"],
                        k["q_status"],
                        k["q_phong"],
                        cho_tt=cho_thanh_toan(k),
                    )
                    if k["q_room_id"] != room_id
                    else None
                )
                or (None if cua else CAU_CHUA_CO_CHI_DINH),
                "_hang": 0
                if any(c["chuyen"] or c["huong_dan_day"] for c in nhan)
                else 1
                if nhan
                else 2,
            }
        )
    out.sort(key=lambda k: k["_hang"])
    for k in out:
        del k["_hang"]
    return out


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
    """Danh sách SẮP ĐẾN của một phòng — mọi khách hôm nay chưa check-out, mỗi
    khách một ô (``gom_sap_den``). Hai câu SQL, không theo từng khách."""
    khach = await conn.fetch(_KHACH_HOM_NAY_SQL, cid, room_id)
    if not khach:
        return []
    dong = await _chi_dinh(conn, cid, room_id, [k["visit_id"] for k in khach])
    return gom_sap_den(khach, dong, room_id)


async def chi_dinh_cua_khach(
    conn: asyncpg.Connection, cid: str, room_id: str, visit_ids: Sequence[str]
) -> dict[str, list[dict[str, Any]]]:
    """Ô KHÁCH ở hàng chờ phòng (đang chờ · đang làm · đã xong): mỗi khách các
    chỉ định phòng làm được kèm trạng thái — dòng ``nhan_duoc`` có nút Nhận."""
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
            o(rid)["sap_den"] = dem_sap_den(dong, rid)
    hom_nay = (
        "(v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
        " = (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
    )
    # Đang làm theo LẦN LÀM đang mở của phòng — kể cả khi khách đã được phòng
    # khác nhận (nhận chéo), vì phòng này vẫn còn một việc phải bấm Xong. Lần
    # làm do BÀN KHÁM mở thì không phải việc của phòng (không đếm ở đây, cũng
    # không là "đang chờ" — khách đang ở bàn khám).
    lam: dict[str, set[str]] = {}
    for r in await conn.fetch(
        "SELECT o.room_id::text AS room_id, o.visit_id::text AS visit_id"
        "  FROM service_order o JOIN visit v"
        "    ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id"
        " WHERE o.clinic_id = $1::uuid AND o.execution_status = 'IN_PROGRESS'"
        "   AND o.room_id IS NOT NULL AND "
        + KHONG_LAM_BAN_KHAM_SQL.format(ref="o.id")
        + " AND "
        + hom_nay,
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
        "   AND q.status IN ('waiting', 'called', 'blocked') AND "
        + KHONG_LAM_BAN_KHAM_SQL.format(ref="q.ref_id")
        + " AND "
        + hom_nay,
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
    lan_nhan_id: str | None = None,
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
                lan_nhan_id=lan_nhan_id,
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
    # Lần Nhận đã bị hoàn tác (`service.room_receive_undone` trỏ về đúng sự
    # kiện ấy) không phải phòng khách thật sự đã đi.
    da_nhan = await conn.fetchval(
        "SELECT count(DISTINCT e.payload->>'room_id') FROM domain_event e"
        " WHERE e.clinic_id = $1::uuid AND e.correlation_id = $2::uuid"
        "   AND e.event_type = 'service.routed' AND e.payload->>'nguon' = $3"
        "   AND e.payload->>'room_id' <> $4"
        "   AND NOT EXISTS (SELECT 1 FROM domain_event u"
        "        WHERE u.clinic_id = e.clinic_id"
        "          AND u.aggregate_type = 'service_order'"
        "          AND u.aggregate_id = e.aggregate_id"
        "          AND u.event_type = 'service.room_receive_undone'"
        "          AND u.payload->>'hoan_tac_event_id' = e.event_id::text)",
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
        """ReceiveAtRoom — phòng nhận ĐÚNG các chỉ định ``chi_dinh_ids`` (nút
        Nhận trên từng dòng = một id; "Nhận cả N" = các id ấy; không gửi = mọi
        chỉ định nhận được). Cũng dùng khi khách đã chờ ở phòng.

        Nhận chéo — 409 ``KHACH_O_PHONG_KHAC`` (kèm tên phòng), gửi lại
        ``xac_nhan`` (một nút, không lý do) khi: chỉ định được nhận đang CHỜ ở
        phòng khác (rời hàng ấy), hoặc khách đang LÀM ở phòng khác (đóng hàng
        ấy, lần làm giữ mở). Chỉ định khác ở phòng khác không bị đụng.
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
            luot = await khoa_luot(conn, cid, vid)
            cached = await bien_nhan_doc(
                conn, identity, ACTION_NHAN, idempotency_key, payload
            )
            if cached is not None:
                return cached
            # Check-out chỉ đặt `closed_at` (status vẫn IN_PROGRESS) — khách đã
            # về thì không phòng nào nhận nữa (review 07/10).
            if luot["closed_at"] is not None:
                raise LuotKhamConflictError("VISIT_CHECKED_OUT", CAU_DA_CHECK_OUT)
            ds = {c["id"]: c for _, c in await _chi_dinh(conn, cid, rid, [vid])}
            # CỔNG TIỀN TRƯỚC MỌI THAY ĐỔI (review 07/10): chỉ định đang chờ ở
            # phòng khác mà tiền đang hoàn / đã hoàn / sổ lệch thì KHÔNG nhận
            # được — loại khỏi lô kèm lý do, hàng phòng kia không bị đụng.
            if ids is None:
                chon = [c for c in ds.values() if c["nhan_duoc"]]
                chan_tien = [c for c in ds.values() if c["ly_do_khong_nhan"]]
            else:
                chon = [ds[i] for i in ids if i in ds and ds[i]["nhan_duoc"]]
                chan_tien = [
                    ds[i] for i in ids if i in ds and ds[i]["ly_do_khong_nhan"]
                ]
                da_o_day = [
                    i for i in ids if i in ds and ds[i]["trang_thai"] in (CHO, LAM)
                ]
                if not chon and da_o_day and len(da_o_day) == len(ids):
                    return {"ok": True, "already": True, "visit_id": vid}
            bo_qua: list[dict[str, Any]] = [
                {"id": c["id"], "ten": c["ten"], "cau": c["ly_do_khong_nhan"]}
                for c in chan_tien
            ]
            if not chon:
                if ids == []:
                    raise LuotKhamConflictError(
                        "CHUA_CHON_CHI_DINH",
                        "Chọn ít nhất một chỉ định để nhận vào phòng này.",
                    )
                if ids is None and any(
                    c["trang_thai"] in (CHO, LAM) for c in ds.values()
                ):
                    return {"ok": True, "already": True, "visit_id": vid}
                if chan_tien:
                    raise LuotKhamConflictError(
                        "SERVICE_FINANCE_NOT_READY",
                        str(chan_tien[0]["ly_do_khong_nhan"]),
                    )
                raise LuotKhamConflictError(
                    "KHONG_CON_GI_DE_NHAN",
                    "Chỉ định không còn chờ vào phòng này — tải lại.",
                )
            cho = await _cho_cua(conn, cid, vid)
            chon_ids = {c["id"] for c in chon}
            # Chỗ ở phòng khác: (a) chỉ định được nhận đang CHỜ ở đó — rời cùng
            # lúc với lần nhận của CHÍNH nó; (b) khách đang LÀM chỉ định khác ở
            # đó (A quên Xong) — đóng hàng A, lần làm giữ mở.
            khac_cho: dict[str, list[asyncpg.Record]] = {}
            for q in cho:
                if q["room_id"] != rid and q["ref_id"] in chon_ids:
                    khac_cho.setdefault(q["ref_id"], []).append(q)
            khac_lam = [
                q
                for q in cho
                if q["room_id"] != rid
                and q["status"] == "serving"
                and q["ref_id"] not in chon_ids
            ]
            khac = [q for ds_q in khac_cho.values() for q in ds_q] + khac_lam
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
            # Mã của LẦN BẤM này — ghi ở mọi sự kiện rời phòng / nhận của nó để
            # hoàn tác dựng lại đúng chỗ ở phòng cũ.
            lan_nhan = str(uuid.uuid4())
            # Khách đang làm ở A: đóng hàng A trước (để chỗ mới ở đây là 'chờ',
            # không 'đợi quay lại'). Không nhận được chỉ định nào → cả giao dịch
            # cuộn lại, chỗ ở A về như cũ.
            await roi_phong(
                conn,
                identity,
                vid=vid,
                cho=khac_lam,
                ly_do=NHA_NHAN_CHEO,
                sang_room_id=rid,
                lan_nhan_id=lan_nhan,
            )
            doi_chieu = await _doi_chieu(conn, cid, vid, rid)
            gan = ServiceRoutingService(self._pool)
            da_nhan: list[str] = []
            nhan_cheo = bool(khac_lam)
            loi_dau: LuotKhamConflictError | None = None
            for c in chon:
                o_cu = khac_cho.get(c["id"], [])
                tu_phong = (o_cu or khac_lam or [None])[0]
                try:
                    # MỘT savepoint cho cả "rời chỗ ở phòng cũ" lẫn "nhận vào
                    # đây" của chỉ định này: nhận hỏng thì chỗ cũ và sự kiện rời
                    # phòng cuộn lại theo — không chỉ định nào mất chỗ.
                    async with conn.transaction():
                        await roi_phong(
                            conn,
                            identity,
                            vid=vid,
                            cho=o_cu,
                            ly_do=NHA_NHAN_CHEO,
                            sang_room_id=rid,
                            lan_nhan_id=lan_nhan,
                        )
                        rev = await conn.fetchval(
                            "SELECT routing_revision FROM service_order"
                            " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                            cid,
                            c["id"],
                        )
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
                                "nhan_cheo_tu_room_id": tu_phong["room_id"]
                                if tu_phong is not None
                                else None,
                                "lan_nhan_id": lan_nhan,
                            },
                        )
                    da_nhan.append(c["id"])
                    nhan_cheo = nhan_cheo or bool(o_cu)
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
                "nhan_cheo": nhan_cheo,
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
        """UndoReceiveAtRoom — hoàn tác các lần NHẬN TẠI PHÒNG của phòng này
        (``chi_dinh_ids``; không gửi = mọi chỉ định phòng này đã Nhận mà còn
        CHỜ). Chỉ đụng chỗ do Nhận tại phòng tạo (`routing_nguon = tai_phong`)
        — chỗ quầy / trưởng ca xếp theo đường cũ giữ nguyên. Mỗi thay đổi một
        sự kiện; không thay đổi được thì không đụng (trả ở ``bo_qua``).

        * Nhận thường → chỉ định về "Sắp đến" (không REASSIGNMENT_REQUIRED,
          không đẻ việc trưởng ca).
        * NHẬN CHÉO (chỉ định đang CHỜ ở phòng A thì phòng này nhận) → về lại
          ĐÚNG hàng A: giờ vào hàng cũ, người / giờ xếp ở A, bác sĩ đã chọn ở A.
        * Lần nhận ấy đã đóng hàng A của chỉ định khác đang LÀM (A quên Xong) →
          khi lần nhận ấy không còn chỉ định nào ở đây, chỗ của A dựng lại
          "đang làm" (giờ bắt đầu cũ); khách đang được làm ở chỗ khác (Postgres
          chỉ cho một chỗ 'serving' — `uq_queue_entry_one_serving`) thì để
          "chờ" kèm ghi chú trong sự kiện.

        Chỉ định đã Bắt đầu thì Huỷ bắt đầu trước. Bấm hai lần = ``already``."""
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
            nguon = {
                r["id"]: r["routing_nguon"]
                for r in await conn.fetch(
                    "SELECT id::text, routing_nguon FROM service_order"
                    " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])",
                    cid,
                    [q["ref_id"] for q in cho],
                )
            }
            # Chỗ quầy / trưởng ca xếp theo đường cũ KHÔNG phải lần Nhận tại
            # phòng — hoàn tác Nhận không huỷ nó (review 07/10).
            cho = [q for q in cho if nguon.get(q["ref_id"]) == NGUON_TAI_PHONG]
            if not cho:
                return {"ok": True, "already": True, "visit_id": vid}
            ve: list[str] = []
            ve_phong_cu: list[str] = []
            bo_qua: list[dict[str, Any]] = []
            lan_da_hoan: set[str] = set()
            for q in cho:
                nhan = await _su_kien_nhan(conn, cid, q["ref_id"], rid)
                lan = (nhan or {}).get("lan_nhan_id")
                nha = (
                    await _nha_cua_lan(conn, cid, q["ref_id"], lan, "cho")
                    if lan
                    else None
                )
                if nha is not None:
                    if await _ve_lai_phong_cu(conn, identity, vid, q, nha, nhan):
                        ve_phong_cu.append(q["ref_id"])
                    else:
                        bo_qua.append({"id": q["ref_id"], "cau": CAU_KHONG_HOAN_TAC})
                        continue
                else:
                    rev = await _ve_chua_xep(conn, cid, q["ref_id"])
                    if rev is None:
                        # Không đổi được gì thì KHÔNG huỷ chỗ (không có thay
                        # đổi nào mà thiếu sự kiện).
                        bo_qua.append({"id": q["ref_id"], "cau": CAU_KHONG_HOAN_TAC})
                        continue
                    await _huy_cho(conn, cid, q["id"])
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
                            hoan_tac_event_id=(nhan or {}).get("event_id"),
                            routing_revision=int(rev),
                        ),
                        boi=nguoi(identity),
                        correlation_id=vid,
                    )
                if lan:
                    lan_da_hoan.add(str(lan))
            for lan in sorted(lan_da_hoan):
                await _dung_lai_cho_lam(conn, identity, vid, rid, lan)
            await cap_nhat_vi_tri(conn, cid, vid)
        return {
            "ok": True,
            "visit_id": vid,
            "room_id": rid,
            "ve_sap_den": ve,
            "ve_phong_cu": ve_phong_cu,
            "bo_qua": bo_qua,
        }


CAU_KHONG_HOAN_TAC = "Chỉ định không còn chờ ở phòng này — tải lại."


def _payload(v: Any) -> dict[str, Any]:
    if isinstance(v, str):
        return dict(json.loads(v))
    return dict(v or {})


async def _huy_cho(conn: asyncpg.Connection, cid: str, qid: str) -> None:
    await conn.execute(
        "UPDATE queue_entry SET status = 'cancelled',"
        " version = version + 1, updated_at = now()"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
        cid,
        qid,
    )


async def _su_kien_nhan(
    conn: asyncpg.Connection, cid: str, oid: str, rid: str
) -> dict[str, Any] | None:
    """Lần Nhận tại phòng ``rid`` mới nhất của chỉ định (sự kiện đang bị hoàn
    tác): ``event_id`` + payload."""
    r = await conn.fetchrow(
        "SELECT event_id::text, seq, payload FROM domain_event"
        " WHERE clinic_id = $1::uuid AND aggregate_type = 'service_order'"
        "   AND aggregate_id = $2::uuid AND event_type = 'service.routed'"
        "   AND payload->>'nguon' = $3 AND payload->>'room_id' = $4"
        " ORDER BY seq DESC LIMIT 1",
        cid,
        oid,
        NGUON_TAI_PHONG,
        rid,
    )
    if r is None:
        return None
    return {**_payload(r["payload"]), "event_id": r["event_id"], "seq": r["seq"]}


async def _nha_cua_lan(
    conn: asyncpg.Connection, cid: str, oid: str, lan: str, truoc: str
) -> asyncpg.Record | None:
    """Sự kiện rời phòng cũ của chỉ định ``oid`` do CHÍNH lần Nhận ``lan`` gây ra
    (``truoc`` = trạng thái lúc rời: 'cho' / 'lam')."""
    return await conn.fetchrow(
        "SELECT event_id::text, seq, payload FROM domain_event"
        " WHERE clinic_id = $1::uuid AND aggregate_type = 'service_order'"
        "   AND aggregate_id = $2::uuid AND event_type = 'service.room_released'"
        "   AND payload->>'lan_nhan_id' = $3 AND payload->>'trang_thai_truoc' = $4"
        " ORDER BY seq DESC LIMIT 1",
        cid,
        oid,
        lan,
        truoc,
    )


async def _ve_lai_phong_cu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    vid: str,
    q: asyncpg.Record,
    nha: asyncpg.Record,
    nhan: Mapping[str, Any] | None,
) -> bool:
    """Hoàn tác một NHẬN CHÉO lúc chỉ định đang CHỜ ở phòng A: chỉ định về lại
    đúng hàng A như trước lần nhận (chỗ chờ cũ mở lại — giờ vào hàng cũ; người
    / giờ xếp ở A; bác sĩ đã chọn ở A). Trả False khi không còn đúng hiện
    trạng để trả (chỉ định đã bắt đầu…) — không đụng gì."""
    cid = identity.clinic_id
    oid = q["ref_id"]
    p = _payload(nha["payload"])
    a = str(p["room_id"])
    o = await conn.fetchrow(
        "SELECT coalesce(execution_status, 'PENDING') AS ex FROM service_order"
        " WHERE clinic_id = $1::uuid AND id = $2::uuid FOR UPDATE",
        cid,
        oid,
    )
    if o is None or o["ex"] != "PENDING":
        return False
    # Lần xếp vào A (trước lúc rời) và lựa chọn bác sĩ ở A — dựng lại đúng.
    xep = await conn.fetchrow(
        "SELECT actor_staff_id::text AS ai, occurred_at, payload->>'nguon' AS nguon"
        "  FROM domain_event WHERE clinic_id = $1::uuid"
        "   AND aggregate_type = 'service_order' AND aggregate_id = $2::uuid"
        "   AND event_type = 'service.routed' AND payload->>'room_id' = $3"
        "   AND seq < $4 ORDER BY seq DESC LIMIT 1",
        cid,
        oid,
        a,
        nha["seq"],
    )
    bs = await conn.fetchrow(
        "SELECT actor_staff_id::text AS ai, occurred_at,"
        "       payload->>'bac_si_id' AS bac_si_id, (payload->>'lan')::int AS lan"
        "  FROM domain_event WHERE clinic_id = $1::uuid"
        "   AND aggregate_type = 'service_order' AND aggregate_id = $2::uuid"
        "   AND event_type = 'service.doctor_chosen' AND payload->>'room_id' = $3"
        "   AND seq < $4 ORDER BY seq DESC LIMIT 1",
        cid,
        oid,
        a,
        nha["seq"],
    )
    nguon_a = (xep["nguon"] if xep else None) or NGUON_TAI_PHONG
    if nguon_a not in ("quay_thu", "truong_ca", "tu_dong", "khac", NGUON_TAI_PHONG):
        nguon_a = NGUON_TAI_PHONG
    co_bs = bs is not None and bs["bac_si_id"] is not None
    # Một chỗ sống mỗi chỉ định (`uq_queue_entry_live`): đóng chỗ ở đây trước.
    await _huy_cho(conn, cid, q["id"])
    rev = await conn.fetchval(
        """
        UPDATE service_order
           SET routing_status = 'ASSIGNED', room_id = $3::uuid,
               routing_revision = routing_revision + 1,
               assigned_by = coalesce($4::uuid, $9::uuid),
               assigned_at = coalesce($5::timestamptz, now()),
               routing_nguon = $6,
               exec_status = CASE WHEN exec_status = 'authorized'
                                  THEN 'assigned' ELSE exec_status END,
               bac_si_lam_id = CASE WHEN $7 THEN $8::uuid ELSE bac_si_lam_id END,
               lan_lam = CASE WHEN $7 THEN $10::int ELSE lan_lam END,
               bac_si_lam_boi = CASE WHEN $7 THEN $11::uuid ELSE bac_si_lam_boi END,
               bac_si_lam_luc = CASE WHEN $7 THEN $12::timestamptz
                                     ELSE bac_si_lam_luc END,
               version = version + 1, updated_at = now()
         WHERE clinic_id = $1::uuid AND id = $2::uuid
        RETURNING routing_revision
        """,
        cid,
        oid,
        a,
        xep["ai"] if xep else None,
        xep["occurred_at"] if xep else None,
        nguon_a,
        co_bs,
        bs["bac_si_id"] if co_bs else None,
        identity.staff_id,
        bs["lan"] if co_bs else None,
        bs["ai"] if co_bs else None,
        bs["occurred_at"] if co_bs else None,
    )
    ban = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
        " AND visit_id = $2::uuid AND status = 'serving')",
        cid,
        vid,
    )
    trang_thai = "blocked" if ban else "waiting"
    cu = await conn.fetchval(
        "SELECT id::text FROM queue_entry WHERE clinic_id = $1::uuid"
        " AND ref_id = $2::uuid AND reason = 'SERVICE' AND room_id = $3::uuid"
        " AND status = 'cancelled' ORDER BY updated_at DESC LIMIT 1",
        cid,
        oid,
        a,
    )
    if cu is not None:
        # Mở lại CHÍNH chỗ cũ: giờ vào hàng (eligible_at) giữ nguyên.
        await conn.execute(
            "UPDATE queue_entry SET status = $3, version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            cu,
            trang_thai,
        )
    else:
        trang_thai = await ve_lai_hang_phong(conn, cid, vid, oid, a) or trang_thai
    await emit_event(
        conn,
        ten="service.room_receive_undone",
        clinic_id=cid,
        aggregate_id=oid,
        so_ke_tiep=True,
        payload=NhanVaoPhongDaHoanTac(
            visit_id=vid,
            service_order_id=oid,
            room_id=q["room_id"],
            hoan_tac_event_id=(nhan or {}).get("event_id"),
            routing_revision=int(rev),
            tra_ve_room_id=a,
        ),
        boi=nguoi(identity),
        correlation_id=vid,
    )
    await emit_event(
        conn,
        ten="service.room_release_undone",
        clinic_id=cid,
        aggregate_id=oid,
        so_ke_tiep=True,
        payload=NhaPhongDaHoanTac(
            visit_id=vid,
            service_order_id=oid,
            room_id=a,
            trang_thai=trang_thai,
            hoan_tac_event_id=nha["event_id"],
            routing_revision=int(rev),
            bac_si_id=bs["bac_si_id"] if co_bs else None,
        ),
        boi=nguoi(identity),
        correlation_id=vid,
    )
    return True


CAU_KHONG_DUNG_LAI_DANG_LAM = (
    "Khách đang được làm ở chỗ khác — chỗ ở phòng này để 'chờ'; phòng tự bấm"
    " Xong / Gián đoạn cho lần làm còn mở."
)


async def _dung_lai_cho_lam(
    conn: asyncpg.Connection, identity: StaffIdentity, vid: str, rid: str, lan: str
) -> None:
    """Lần Nhận ``lan`` (ở phòng ``rid``) đã đóng hàng A của chỉ định khác đang
    LÀM — khi lần nhận ấy không còn chỉ định nào ở ``rid``, dựng lại chỗ của A
    như trước: 'serving' với giờ bắt đầu cũ. Lần làm ở A đã đóng (A bấm Xong /
    Gián đoạn) hoặc chỗ đã đổi thì thôi — không có gì để trả."""
    cid = identity.clinic_id
    if await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1 FROM domain_event e
              JOIN queue_entry q
                ON q.clinic_id = e.clinic_id AND q.ref_id = e.aggregate_id
               AND q.reason = 'SERVICE' AND q.room_id = $3::uuid
               AND q.status IN ('waiting', 'called', 'blocked', 'serving')
             WHERE e.clinic_id = $1::uuid AND e.correlation_id = $2::uuid
               AND e.event_type = 'service.routed'
               AND e.payload->>'lan_nhan_id' = $4)
        """,
        cid,
        vid,
        rid,
        lan,
    ):
        return
    for nha in await conn.fetch(
        "SELECT event_id::text, aggregate_id::text AS oid, payload FROM domain_event"
        " WHERE clinic_id = $1::uuid AND correlation_id = $2::uuid"
        "   AND event_type = 'service.room_released'"
        "   AND payload->>'lan_nhan_id' = $3"
        "   AND payload->>'trang_thai_truoc' = 'lam'"
        " ORDER BY seq",
        cid,
        vid,
        lan,
    ):
        p = _payload(nha["payload"])
        lam_id = p.get("attempt_id")
        if not lam_id or not await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM service_execution_attempt"
            " WHERE clinic_id = $1::uuid AND id = $2::uuid"
            "   AND status = 'IN_PROGRESS')",
            cid,
            lam_id,
        ):
            continue
        cu = await conn.fetchval(
            "SELECT id::text FROM queue_entry q WHERE q.clinic_id = $1::uuid"
            " AND q.ref_id = $2::uuid AND q.reason = 'SERVICE'"
            " AND q.room_id = $3::uuid AND q.status = 'cancelled'"
            " AND q.id = (SELECT q2.id FROM queue_entry q2"
            "              WHERE q2.clinic_id = q.clinic_id AND q2.reason = 'SERVICE'"
            "                AND q2.ref_id = q.ref_id"
            "              ORDER BY q2.updated_at DESC LIMIT 1)",
            cid,
            nha["oid"],
            p["room_id"],
        )
        if cu is None:
            continue
        ban = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM queue_entry WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid AND status = 'serving')",
            cid,
            vid,
        )
        trang_thai = "waiting" if ban else "serving"
        # serving_at giữ nguyên — giờ bắt đầu thật của phòng A.
        await conn.execute(
            "UPDATE queue_entry SET status = $3, version = version + 1,"
            " updated_at = now() WHERE clinic_id = $1::uuid AND id = $2::uuid",
            cid,
            cu,
            trang_thai,
        )
        if not ban:
            # Khách lại đang ở A: chỗ chờ khác của khách tạm khoá (I9).
            await chan_cho_khac(conn, cid, vid, cu)
        await emit_event(
            conn,
            ten="service.room_release_undone",
            clinic_id=cid,
            aggregate_id=nha["oid"],
            so_ke_tiep=True,
            payload=NhaPhongDaHoanTac(
                visit_id=vid,
                service_order_id=nha["oid"],
                room_id=str(p["room_id"]),
                trang_thai=trang_thai,
                hoan_tac_event_id=nha["event_id"],
                ghi_chu=CAU_KHONG_DUNG_LAI_DANG_LAM if ban else None,
                attempt_id=str(lam_id),
            ),
            boi=nguoi(identity),
            correlation_id=vid,
        )


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
    "CAU_CHUA_CO_CHI_DINH",
    "CHUA_VAO_PHONG_SQL",
    "NHA_BO_DICH_VU",
    "NHA_NHAN_CHEO",
    "NhanTaiPhongService",
    "cau_dang_o",
    "chi_dinh_cua_khach",
    "da_sang_phong",
    "dang_bat",
    "dang_o_phong",
    "dem_sap_den",
    "dem_theo_phong",
    "gom_sap_den",
    "nha_khi_bo_chon",
    "roi_phong",
    "sap_den",
    "trang_thai_chi_dinh",
]
