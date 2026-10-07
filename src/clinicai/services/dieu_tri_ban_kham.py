"""CHỈ ĐỊNH ĐIỀU TRỊ của lượt trong hồ sơ khám (Tuyền chốt 07/10/2026).

Khối 4 "Điều trị" = các chỉ định ĐIỀU TRỊ của lượt (dịch vụ trỏ bởi một loại
khám nhóm DIEU_TRI — `service_type.service_price_id`), mỗi chỉ định một thẻ:

* PHIẾU ĐIỀU TRỊ = phiếu KẾT QUẢ của chính chỉ định ấy (mẫu `PHIEU_DIEU_TRI`
  gắn ở `dich_vu_mau_ket_qua`, một `form_instance` mỗi chỉ định) — bàn khám và
  phòng mở CÙNG một phiếu. File này chỉ trả mẫu + phiếu đang có; điền / lưu đi
  đường phiếu kết quả sẵn có (`FormEngineService`, revision chống ghi đè).
* TRẠNG THÁI: chưa làm (đã xếp P. X?) · đang làm ở P. X · đang làm tại bàn khám
  · xong (ở đâu, ai, lúc nào) · không làm / dừng.
* LÀM TẠI BÀN KHÁM: [Làm tại bàn khám] → [Xong], hoàn tác từng bước — lệnh của
  module Thực hiện (`ServiceExecutionService.*_tai_ban_kham`); cửa tiền CÙNG
  FinanceGate với phòng (`cua_tien_ban_kham`). Điền phiếu KHÔNG tính là đã làm.
* "Khách đã đặt": chỉ định trùng dịch vụ lượt Điều trị đã đặt (T1) → cờ `da_dat`.

Chỉ định điều trị (tự sinh hay bác sĩ kê) là `service_order` bình thường: quầy
thu đúng dòng giá, một lần; bỏ chỉ định đã thu → tiền thừa (luật 06/10).
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import ValidationError
from clinicai.permissions.doc_bang import doi_mot_quyen
from clinicai.phieu_kham.mau_dieu_tri import MAU_PHIEU_DIEU_TRI
from clinicai.phieu_kham.mau_goi_y import mau_cho_cac_dich_vu
from clinicai.services.finance_gate import READY_STATES, states_for_orders
from clinicai.services.lenh_kham_core import ma_uuid
from clinicai.services.service_execution_service import (
    CAU_KHONG_QUYEN_BAN_KHAM,
    NOI_BAN_KHAM,
    QUYEN_LAM_TAI_BAN_KHAM,
    ServiceExecutionService,
    cua_tien_ban_kham,
    duoc_lam_khi_chua_thu,
)

#: Mã dịch vụ ĐIỀU TRỊ của phòng khám — dịch vụ mà một loại khám nhóm DIEU_TRI
#: trỏ tới (không viết cứng mã).
MA_DIEU_TRI_SQL = """
SELECT sp.service_code
  FROM public.service_type st
  JOIN public.service_price sp
    ON sp.id = st.service_price_id AND sp.clinic_id = st.clinic_id
 WHERE st.clinic_id = $1::uuid AND st.nhom = 'DIEU_TRI'
"""

_THE_SQL = f"""
SELECT o.id::text AS order_id, o.service_code, o.service_name,
       o.selection_status, o.execution_status, o.execution_revision,
       o.room_id::text AS room_id, r.name AS phong,
       (o.service_code = dat.service_code) AS da_dat,
       a.id::text AS attempt_id, a.status AS lan_status, a.noi_lam,
       a.started_at, a.completed_at, ra.name AS phong_lam,
       coalesce(nx.full_name, nb.full_name) AS nguoi_lam
  FROM public.service_order o
  LEFT JOIN public.clinic_room r ON r.id = o.room_id AND r.clinic_id = o.clinic_id
  LEFT JOIN LATERAL (
       SELECT sp.service_code
         FROM public.visit v
         LEFT JOIN public.appointment ap
           ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
         JOIN public.service_type st
           ON st.id = coalesce(v.service_type_id, ap.service_type_id)
          AND st.nhom = 'DIEU_TRI'
         JOIN public.service_price sp
           ON sp.id = st.service_price_id AND sp.clinic_id = v.clinic_id
        WHERE v.clinic_id = o.clinic_id AND v.visit_id = o.visit_id) dat ON true
  LEFT JOIN LATERAL (
       SELECT x.id, x.status, x.noi_lam, x.started_at, x.completed_at,
              x.room_id_snapshot, x.started_by, x.completed_by
         FROM public.service_execution_attempt x
        WHERE x.clinic_id = o.clinic_id AND x.service_order_id = o.id
        ORDER BY x.attempt_no DESC LIMIT 1) a ON true
  LEFT JOIN public.clinic_room ra
    ON ra.id = a.room_id_snapshot AND ra.clinic_id = o.clinic_id
  LEFT JOIN public.staff nb ON nb.id = a.started_by
  LEFT JOIN public.staff nx ON nx.id = a.completed_by
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid
   AND o.exec_status NOT IN ('draft', 'cancelled')
   AND o.service_code IN ({MA_DIEU_TRI_SQL.replace("$1", "o.clinic_id")})
 ORDER BY o.created_at, o.id
"""

#: Phiếu của chỉ định — PHIẾU ĐIỀU TRỊ trước (thẻ vẽ đúng phiếu 2 ô dù chỉ định
#: từng có phiếu mẫu khác, vd "Kết quả chung" mở trước khi gắn mẫu).
_PHIEU_SQL = f"""
SELECT i.service_order_id::text AS order_id, i.id::text AS phieu_id, i.form_id,
       i.trang_thai, i.revision, i.du_lieu, i.sua_luc, d.khung,
       s.full_name AS nguoi_sua
  FROM public.form_instance i
  JOIN public.form_definition d
    ON d.clinic_id = i.clinic_id AND d.form_id = i.form_id
   AND d.version = i.version
  LEFT JOIN public.staff s ON s.id = i.nhap_boi
 WHERE i.clinic_id = $1::uuid AND i.service_order_id = ANY($2::uuid[])
 ORDER BY (i.form_id = 'KQ_{MAU_PHIEU_DIEU_TRI}') DESC,
          (i.trang_thai = 'READY') DESC, i.hoan_tat_luc DESC NULLS LAST,
          i.tao_luc DESC
"""


def o_phieu(khung: Any, du_lieu: Any) -> list[dict[str, Any]]:
    """Các ô chữ của phiếu (MỘT nhãn mỗi ô — tên ô, không lặp tên mục) + giá
    trị đang lưu, để thẻ chỉ đọc / bản in vẽ — hàm thuần, không ném."""
    k = json.loads(khung) if isinstance(khung, str) else khung
    d = json.loads(du_lieu) if isinstance(du_lieu, str) else du_lieu
    if not isinstance(k, list) or not isinstance(d, dict):
        return []
    ra: list[dict[str, Any]] = []
    for muc in k:
        for o in (muc.get("block") or []) if isinstance(muc, dict) else []:
            if not isinstance(o, dict) or not o.get("ma"):
                continue
            gt = d.get(o["ma"])
            gia_tri = gt.get("gia_tri") if isinstance(gt, dict) else None
            ra.append(
                {
                    "ma": o["ma"],
                    "ten": o.get("ten") or o["ma"],
                    "gia_tri": gia_tri if isinstance(gia_tri, str) else "",
                }
            )
    return ra


_LUOT_SQL = """
SELECT status, closed_at FROM public.visit
 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
"""

#: Lượt đã check-out / đã đóng: thẻ chỉ đọc, lệnh bị từ chối (Tuyền 07/10/2026 —
#: staging: 15:37 vẫn bấm làm tại bàn khám cho khách check-out lúc 15:32).
CAU_LUOT_DA_DONG = "Lượt đã check-out — muốn làm tiếp thì Mở lại lượt trước."


def luot_da_dong(status: str | None, closed_at: Any) -> bool:
    """Lượt đã check-out (`closed_at`) hoặc không còn sống — hàm thuần.

    INCOMPLETE (khách về giữa chừng), FINALIZED / AMENDED đều là đã đóng: thẻ
    chỉ đọc; mở lại lượt thì làm tiếp được."""
    return closed_at is not None or status not in ("OPEN", "IN_PROGRESS")


#: Nhãn trạng thái — máy chủ nói, màn chỉ vẽ.
NHAN = {
    "CHUA_LAM": "Chưa làm",
    "DANG_LAM_PHONG": "Đang làm ở phòng",
    "DANG_LAM_BAN_KHAM": "Đang làm tại bàn khám",
    "XONG": "Đã làm xong",
    "KHONG_LAM": "Không làm",
    "DUNG": "Dừng giữa chừng",
}


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


def trang_thai_the(execution_status: str | None, noi_lam: str | None) -> str:
    """Trạng thái của thẻ chỉ định điều trị — hàm thuần."""
    ex = execution_status or "PENDING"
    if ex == "IN_PROGRESS":
        return "DANG_LAM_BAN_KHAM" if noi_lam == NOI_BAN_KHAM else "DANG_LAM_PHONG"
    if ex == "COMPLETED":
        return "XONG"
    if ex == "NOT_PERFORMED":
        return "KHONG_LAM"
    if ex == "INTERRUPTED":
        return "DUNG"
    return "CHUA_LAM"


async def doc_the(
    pool: asyncpg.Pool, *, identity: StaffIdentity, visit_id: str
) -> dict[str, Any]:
    """Các thẻ chỉ định điều trị của lượt (khối 4 hồ sơ khám)."""
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    async with pool.acquire() as conn:
        await doi_mot_quyen(
            conn,
            identity,
            QUYEN_LAM_TAI_BAN_KHAM,
            cau="Bạn không có quyền xem hồ sơ khám của lượt này.",
        )
        luot = await conn.fetchrow(_LUOT_SQL, cid, vid)
        if luot is None:
            raise NotFoundError("Không tìm thấy lượt khám.")
        chi_doc = luot_da_dong(luot["status"], luot["closed_at"])
        rows = await conn.fetch(_THE_SQL, cid, vid)
        ids = [r["order_id"] for r in rows]
        tien = await states_for_orders(conn, cid, ids)
        chua_thu = (await duoc_lam_khi_chua_thu(conn, cid, [vid])).get(vid, False)
        mau = await mau_cho_cac_dich_vu(
            conn, clinic_id=cid, service_codes=[r["service_code"] for r in rows]
        )
        phieu: dict[str, dict[str, Any]] = {}
        for p in await conn.fetch(_PHIEU_SQL, cid, ids):
            phieu.setdefault(
                p["order_id"],
                {
                    "phieu_id": p["phieu_id"],
                    "form_id": p["form_id"],
                    "trang_thai": p["trang_thai"],
                    "revision": p["revision"],
                    "sua_luc": _iso(p["sua_luc"]),
                    "nguoi_sua": p["nguoi_sua"],
                    "o": o_phieu(p["khung"], p["du_lieu"]),
                },
            )
    the = []
    for r in rows:
        oid = r["order_id"]
        tt = trang_thai_the(r["execution_status"], r["noi_lam"])
        t = tien.get(oid)
        lam_duoc, cau, _ = cua_tien_ban_kham(
            t, selection_status=r["selection_status"], duoc_chua_thu=chua_thu
        )
        dang_ban_kham = tt == "DANG_LAM_BAN_KHAM"
        xong_ban_kham = tt == "XONG" and r["noi_lam"] == NOI_BAN_KHAM
        m = mau.get(r["service_code"]) or {"mau": [], "chon_san": None}
        ph = phieu.get(oid)
        the.append(
            {
                "order_id": oid,
                "ten": r["service_name"],
                "service_code": r["service_code"],
                "da_dat": bool(r["da_dat"]),
                "trang_thai": tt,
                "nhan": NHAN[tt],
                # Phòng: đang làm → phòng của lần làm; chưa làm → phòng đã xếp.
                "phong": r["phong_lam"] if tt == "DANG_LAM_PHONG" else r["phong"],
                "noi_lam": r["noi_lam"]
                if tt in ("XONG", "DANG_LAM_BAN_KHAM")
                else None,
                "nguoi_lam": r["nguoi_lam"] if tt != "CHUA_LAM" else None,
                "bat_dau_luc": _iso(r["started_at"]) if tt != "CHUA_LAM" else None,
                "xong_luc": _iso(r["completed_at"]) if tt == "XONG" else None,
                "attempt_id": r["attempt_id"] if dang_ban_kham else None,
                "execution_revision": int(r["execution_revision"] or 0),
                "da_thu": bool(t is not None and t.finance_state in READY_STATES),
                # Nút — máy chủ quyết, màn chỉ vẽ. Lượt đã check-out: chỉ đọc.
                "lam_duoc": not chi_doc and tt == "CHUA_LAM" and lam_duoc,
                "ly_do_khong_lam": (
                    CAU_LUOT_DA_DONG
                    if chi_doc and tt in ("CHUA_LAM", "DANG_LAM_BAN_KHAM")
                    else cau
                    if tt == "CHUA_LAM" and not lam_duoc
                    else None
                ),
                "xong_duoc": not chi_doc and dang_ban_kham,
                "huy_lam_duoc": not chi_doc and dang_ban_kham,
                "hoan_tac_xong_duoc": not chi_doc and xong_ban_kham,
                "mau": m["mau"],
                "mau_chon_san": (ph["form_id"].removeprefix("KQ_") if ph else None)
                or m["chon_san"],
                "phieu": ph,
            }
        )
    return {"visit_id": vid, "chi_doc": chi_doc, "the": the}


THAO_TAC = frozenset({"lam", "xong", "huy-lam", "hoan-tac-xong"})


async def thao_tac(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    visit_id: str,
    order_id: str,
    lenh: str,
    expected_execution_revision: int,
    attempt_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """[Làm tại bàn khám] · [Xong] · hoàn tác hai bước ấy — lệnh của module
    Thực hiện. Chỉ cho chỉ định ĐIỀU TRỊ của đúng lượt này."""
    if lenh not in THAO_TAC:
        raise ValidationError("Thao tác không hợp lệ.")
    cid = identity.clinic_id
    vid = ma_uuid(visit_id, "Mã lượt khám không hợp lệ.")
    oid = ma_uuid(order_id, "Mã chỉ định không hợp lệ.")
    async with pool.acquire() as conn:
        await doi_mot_quyen(
            conn, identity, QUYEN_LAM_TAI_BAN_KHAM, cau=CAU_KHONG_QUYEN_BAN_KHAM
        )
        la_dieu_tri = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM public.service_order o"
            " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid"
            "   AND o.visit_id = $3::uuid"
            f"  AND o.service_code IN ({MA_DIEU_TRI_SQL}))",
            cid,
            oid,
            vid,
        )
        luot = await conn.fetchrow(_LUOT_SQL, cid, vid)
    if luot is None or luot_da_dong(luot["status"], luot["closed_at"]):
        raise ValidationError(CAU_LUOT_DA_DONG)
    if not la_dieu_tri:
        raise ValidationError(
            "Chỉ làm tại bàn khám được chỉ định ĐIỀU TRỊ của lượt này."
        )
    svc = ServiceExecutionService(pool)
    rev = int(expected_execution_revision)
    if lenh == "lam":
        return await svc.bat_dau_tai_ban_kham(
            order_id=oid,
            expected_execution_revision=rev,
            identity=identity,
            idempotency_key=idempotency_key,
        )
    if lenh == "hoan-tac-xong":
        return await svc.hoan_tac_xong_tai_ban_kham(
            order_id=oid, expected_execution_revision=rev, identity=identity
        )
    lan = ma_uuid(attempt_id, "Thiếu mã lần làm — tải lại màn hình.")
    if lenh == "xong":
        return await svc.xong_tai_ban_kham(
            order_id=oid,
            attempt_id=lan,
            expected_execution_revision=rev,
            identity=identity,
            idempotency_key=idempotency_key,
        )
    return await svc.huy_bat_dau_tai_ban_kham(
        order_id=oid,
        attempt_id=lan,
        expected_execution_revision=rev,
        identity=identity,
    )


async def chi_dinh_dieu_tri_dang_co(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str, codes: list[str]
) -> dict[str, str]:
    """Mã dịch vụ ĐIỀU TRỊ (trong `codes`) đã có chỉ định còn sống ở lượt → mã
    chỉ định. Kê lại cùng dịch vụ điều trị không đẻ dòng thứ hai (không thu hai
    lần) — `ChiDinhService.dat_chi_dinh` dùng."""
    if not codes:
        return {}
    rows = await conn.fetch(
        "SELECT DISTINCT ON (o.service_code) o.service_code, o.id::text AS id"
        "  FROM public.service_order o"
        " WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid"
        "   AND o.service_code = ANY($3::text[])"
        "   AND o.exec_status NOT IN ('draft', 'cancelled')"
        f"  AND o.service_code IN ({MA_DIEU_TRI_SQL})"
        " ORDER BY o.service_code, o.created_at",
        clinic_id,
        visit_id,
        codes,
    )
    return {r["service_code"]: r["id"] for r in rows}


__all__ = [
    "MA_DIEU_TRI_SQL",
    "NHAN",
    "THAO_TAC",
    "chi_dinh_dieu_tri_dang_co",
    "doc_the",
    "thao_tac",
    "trang_thai_the",
]
