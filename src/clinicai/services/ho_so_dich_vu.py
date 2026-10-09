"""DỊCH VỤ của lượt NGAY TRONG HỒ SƠ KHÁM (Tuyền chốt 07/10/2026 — T1, T5, T6 của
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md).

* **Đọc** (`doc`): dịch vụ hiện tại + đổi được không, lịch sử đổi (ai, lúc, từ →
  sang — từ `appointment.service_switched`), phiếu CŨ của lượt (mẫu khác dịch vụ
  hiện tại, "đã nhập N ô"), ghi chú lúc đặt. Chỉ định "Khách đã đặt" của lượt
  Điều trị hiện ở khối 4 (`dieu_tri_ban_kham.doc_the`, cờ `da_dat`).
* **Đổi dịch vụ** (`doi`): đi đúng đường `BookingService.doi_dich_vu_kham` với
  ``trong_ho_so=True`` — không đường ghi thứ hai.
* **Lượt Điều trị vào hàng** (`sinh_chi_dinh_dieu_tri`, consumer
  `events/consumers/dieu_tri.py`): sinh sẵn chỉ định đúng dịch vụ đã đặt — một
  `service_order` bình thường (không xếp phòng, không thu phí khám).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.events.catalogue import ChiDinhDaDat
from clinicai.events.emit import HE_THONG, NguoiGayRa, emit_event
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.phieu_kham.khung import FORM_IDS, dinh_nghia
from clinicai.services.dich_vu_dat_lich import COT_SQL, gom_nhom
from clinicai.services.doi_dich_vu_kham import QUYEN_DOI_TRONG_HO_SO, doc_trang_thai
from clinicai.services.lenh_kham_core import ma_uuid

logger = structlog.get_logger()

_LUOT_SQL = """
SELECT v.visit_id::text, v.status, v.appointment_id::text, a.notes,
       st.id::text AS dv_id, st.name AS dv_ten, st.nhom, st.form_code
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
"""

_LICH_SU_SQL = """
SELECT e.occurred_at, e.payload, s.full_name AS ai
  FROM public.event_log e
  LEFT JOIN public.staff s
    ON s.id::text = e.metadata ->> 'clinic_staff_id'
 WHERE e.clinic_id = $1::uuid AND e.aggregate_id = $2::uuid
   AND e.event_type = 'appointment.service_switched'
 ORDER BY e.occurred_at, e.event_id
"""

_PHIEU_SQL = """
SELECT p.form_id, p.sua_luc,
       (SELECT count(*) FROM jsonb_each(p.du_lieu) o
         WHERE coalesce(o.value ->> 'gia_tri', '') NOT IN ('', '[]', '{}'))
           AS so_o
  FROM public.phieu_kham_luot p
 WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid
 ORDER BY p.sua_luc DESC
"""


#: Chỉ định cùng dịch vụ còn sống (chưa làm xong, chưa huỷ) ở MỘT LƯỢT KHÁC của
#: cùng khách mà lượt ấy chưa check-out.
_CON_O_LUOT_KHAC_SQL = """
SELECT EXISTS (
    SELECT 1
      FROM public.visit v
      JOIN public.visit x
        ON x.clinic_id = v.clinic_id AND x.clinic_patient_id = v.clinic_patient_id
       AND x.visit_id <> v.visit_id
       AND x.status IN ('OPEN', 'IN_PROGRESS') AND x.closed_at IS NULL
      JOIN public.service_order o
        ON o.clinic_id = x.clinic_id AND o.visit_id = x.visit_id
     WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
       AND o.service_code = $3
       AND o.exec_status IN ('authorized', 'assigned', 'in_progress')
       AND coalesce(o.execution_status, 'PENDING') IN ('PENDING', 'IN_PROGRESS'))
"""


async def _da_co_chi_dinh(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str, service_code: str
) -> bool:
    return bool(
        await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.service_order"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND service_code = $3 AND exec_status <> 'cancelled')",
            clinic_id,
            visit_id,
            service_code,
        )
    )


def _ten_phieu(form_id: str) -> str:
    try:
        return str(dinh_nghia(form_id)["ten"])
    except (KeyError, ValueError, FileNotFoundError):
        return form_id


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


async def _luot(conn: asyncpg.Connection, cid: str, vid: str) -> asyncpg.Record:
    r = await conn.fetchrow(_LUOT_SQL, cid, vid)
    if r is None:
        raise NotFoundError("Không tìm thấy lượt khám.")
    return r


async def doc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, visit_id: str
) -> dict[str, Any]:
    """Khối "Dịch vụ của lượt" ở đầu hồ sơ khám (chỉ đọc)."""
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    async with pool.acquire() as conn:
        await doi_mot_quyen(
            conn,
            identity,
            QUYEN_DOI_TRONG_HO_SO,
            cau="Bạn không có quyền xem hồ sơ khám của lượt này.",
        )
        luot = await _luot(conn, cid, vid)
        ly_do: str | None = "Lượt không gắn lịch hẹn — không đổi dịch vụ ở đây."
        lich_su: list[dict[str, Any]] = []
        if luot["appointment_id"]:
            tt = await doc_trang_thai(conn, cid, luot["appointment_id"])
            ly_do = tt.ly_do_khong_doi(trong_ho_so=True)
            for e in await conn.fetch(_LICH_SU_SQL, cid, luot["appointment_id"]):
                p = e["payload"]
                p = json.loads(p) if isinstance(p, str) else dict(p or {})
                lich_su.append(
                    {
                        "luc": _iso(e["occurred_at"]),
                        "ai": e["ai"],
                        "tu": p.get("tu_ten"),
                        "sang": p.get("den_ten"),
                        "trong_ho_so": bool(p.get("trong_ho_so")),
                    }
                )
        dv = [
            {**dict(r), "hien_tai": r["id"] == luot["dv_id"]}
            for r in await conn.fetch(
                f"SELECT {COT_SQL} FROM public.service_type"
                " WHERE clinic_id = $1::uuid AND is_active AND nhom <> 'THUOC'"
                " ORDER BY thu_tu, name",
                cid,
            )
        ]
        phieu_hien = luot["form_code"] if luot["form_code"] in FORM_IDS else None
        phieu = await conn.fetch(_PHIEU_SQL, cid, vid)
        if phieu_hien is None and phieu:
            # Dịch vụ không gắn phiếu: phiếu đang mở là phiếu sửa gần nhất.
            phieu_hien = phieu[0]["form_id"]
    return {
        "visit_id": vid,
        "dich_vu": {
            "id": luot["dv_id"],
            "ten": luot["dv_ten"],
            "nhom": luot["nhom"],
        },
        "doi_duoc": ly_do is None,
        "ly_do_khong_doi": ly_do,
        "nhom": gom_nhom(dv),
        "lich_su_doi": lich_su,
        "phieu_cu": [
            {
                "form_id": p["form_id"],
                "ten": _ten_phieu(p["form_id"]),
                "so_o": int(p["so_o"]),
                "sua_luc": _iso(p["sua_luc"]),
            }
            for p in phieu
            if p["form_id"] != phieu_hien
        ],
        "ghi_chu_dat": luot["notes"],
    }


async def doi(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str,
    service_type_id: str,
) -> dict[str, Any]:
    """Đổi dịch vụ khám trong hồ sơ — đường ghi DUY NHẤT của BookingService."""
    from clinicai.services.booking_service import BookingService  # vòng nhập

    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    aid = await pool.fetchval(
        "SELECT appointment_id::text FROM public.visit"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
        identity.clinic_id,
        vid,
    )
    if not aid:
        raise ValidationError("Lượt không gắn lịch hẹn — không đổi dịch vụ ở đây.")
    return await BookingService(pool).doi_dich_vu_kham(
        appointment_id=aid,
        service_type_id=service_type_id,
        identity=identity,
        trong_ho_so=True,
    )


async def sinh_chi_dinh_dieu_tri(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    nguoi_bam: str | None,
    causation_id: str | None = None,
) -> str | None:
    """Lượt ĐIỀU TRỊ vừa vào hàng → chỉ định đúng dịch vụ đã đặt (T1).

    Chạy lại được (người đưa tin giao ít nhất một lần): đã có chỉ định cùng mã
    còn sống thì thôi. Chỉ định là `service_order` bình thường, gắn phiên khám
    của lượt, khách vẫn tự chọn ở quầy (PENDING) — không tự xếp phòng. Trả mã
    chỉ định vừa tạo (None = không làm gì).
    """
    r = await conn.fetchrow(
        """
        SELECT v.status, v.closed_at, v.checked_in_by::text,
               v.attending_doctor_id::text,
               sp.service_code, sp.name, sp.node_code
          FROM public.visit v
          LEFT JOIN public.appointment a
            ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
          JOIN public.service_type st
            ON st.id = coalesce(v.service_type_id, a.service_type_id)
           AND st.nhom = 'DIEU_TRI'
          JOIN public.service_price sp
            ON sp.id = st.service_price_id AND sp.clinic_id = v.clinic_id
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
           FOR UPDATE OF v
        """,
        clinic_id,
        visit_id,
    )
    # Khách đã về (FINALIZED / AMENDED), về giữa chừng (INCOMPLETE) hay đã
    # check-out (chỉ `closed_at`, status vẫn IN_PROGRESS): không sinh — chỉ định
    # chưa thu cho lượt đã đóng là nợ ảo.
    if (
        r is None
        or r["status"] not in ("OPEN", "IN_PROGRESS")
        or r["closed_at"] is not None
    ):
        return None
    if await _da_co_chi_dinh(conn, clinic_id, visit_id, r["service_code"]):
        return None
    # Bác sĩ đã kê đúng dịch vụ ấy mà khách chưa làm, chưa thu → DÙNG LUÔN chỉ
    # định ấy (Tuyền 09/10/2026), không đẻ cái thứ hai. Check-in đã mang sang
    # (H2, chạy trước tin này); gọi lại ở đây cho lối đến KHÔNG qua check-in
    # (đổi dịch vụ sau check-in, tự chữa đường đi) — lệnh chạy lại được.
    from clinicai.services.chi_dinh_service import ChiDinhService  # vòng nhập

    await ChiDinhService.mang_sang_luot_moi(
        conn, clinic_id=clinic_id, visit_id=visit_id, causation_id=causation_id
    )
    if await _da_co_chi_dinh(conn, clinic_id, visit_id, r["service_code"]):
        return None
    # Chỉ định ấy còn sống ở lượt khác đang mở nhưng KHÔNG mang được (đã xếp
    # phòng / tiền đang chờ xác minh): khách làm ở đó — đẻ thêm là thu hai lần.
    if await conn.fetchval(
        _CON_O_LUOT_KHAC_SQL, clinic_id, visit_id, r["service_code"]
    ):
        logger.warning(
            "dieu_tri_dung_chi_dinh_luot_khac",
            visit_id=visit_id,
            service_code=r["service_code"],
        )
        return None
    # Phiên khám của lượt: bác sĩ chính trước, rồi phiên mới nhất còn sống.
    phien = await conn.fetchval(
        "SELECT id::text FROM public.consultation"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND status <> 'cancelled'"
        " ORDER BY (kind = 'PRIMARY') DESC, round_no DESC LIMIT 1",
        clinic_id,
        visit_id,
    )
    ai = nguoi_bam or r["checked_in_by"] or r["attending_doctor_id"]
    if phien is None or ai is None:
        logger.warning(
            "dieu_tri_khong_sinh_chi_dinh", visit_id=visit_id, co_phien=bool(phien)
        )
        return None
    oid = str(
        await conn.fetchval(
            """
            INSERT INTO public.service_order
                (clinic_id, visit_id, consultation_id, service_code, service_name,
                 node_code, exec_status, recorded_by, authorized_by, authorized_at,
                 selection_status, routing_status)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, 'authorized',
                    $7::uuid, $7::uuid, now(), 'PENDING', 'UNASSIGNED')
            RETURNING id::text
            """,
            clinic_id,
            visit_id,
            phien,
            r["service_code"],
            r["name"],
            r["node_code"],
            ai,
        )
    )
    await emit_event(
        conn,
        ten="service_order.placed",
        clinic_id=clinic_id,
        aggregate_id=oid,
        aggregate_version=1,
        payload=ChiDinhDaDat(
            order_id=oid,
            service_code=r["service_code"],
            service_name=r["name"],
            consultation_id=phien,
            visit_id=visit_id,
            selection_status="PENDING",
            billing_status="UNPAID",
        ),
        # domain_event_actor_type chỉ nhận HUMAN/SYSTEM/AGENT — "STAFF" làm
        # INSERT sự kiện vỡ, chỉ định lượt Điều trị không sinh ra.
        boi=NguoiGayRa(actor_type="HUMAN", staff_id=nguoi_bam)
        if nguoi_bam
        else HE_THONG,
        correlation_id=visit_id,
        causation_id=causation_id,
    )
    return oid


__all__ = [
    "doc",
    "doi",
    "sinh_chi_dinh_dieu_tri",
]
