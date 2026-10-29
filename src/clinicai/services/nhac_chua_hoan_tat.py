"""NHẮC LƯỢT CHƯA HOÀN TẤT KHÁM — Tuyền duyệt phiếu 22/10/2026.

Hoàn tất khám KHÔNG phải một nút: máy tự khép lượt
(`LuotKhamService._ket_thuc_neu_xong`) khi hết việc dở. Lượt chưa Hoàn tất là
lượt CÒN VIỆC DỞ, nên nhắc phải nói đúng việc ấy, không chỉ "chưa ký". Đo prod
21/10: 26 lượt kẹt — 22 vì vòng đọc kết quả chưa đóng, 4 vì phiên khám bỏ dở,
0 vì chỉ định chưa làm.

Lượt được nhắc: còn mở, chưa check-out, không phải bán lẻ, chưa khám xong
(`moc_kham_xong`), check-in quá `NGUONG_PHUT` phút (lượt từ hôm trước luôn quá).
Nhắc sớm hơn là nhắc oan khách đang khám dở.

PHẠM VI = luật khối "Chờ bác sĩ quyết" (`LuotKhamService.cho_quyet`): thư ký đã
phân → khách của bác sĩ mình; người Hoàn tất được → lượt của mình; còn lại → cả
cơ sở. Thêm MỘT nhánh: quản lý (lego Cài đặt, `config.clinic.manage`) → cả cơ
sở — từ "mở full" 27/09 ai cũng có Hoàn tất, nên thiếu nhánh này quản lý bấm
dòng đếm ở Trang chủ sang Bàn khám chỉ thấy danh sách rỗng.

Việc dở đọc cùng câu với màn check-out (`checkout_service._READINESS_SQL`): lượt
ĐIỀU TRỊ có phiên bác sĩ chưa ai nhận không tính — hàng bác sĩ ở đó tuỳ chọn.
"""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.luot_kham_chung import CHI_DINH_CON_VIEC_GIU_LUOT_SQL
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.thu_ky_bac_si import bac_si_cua_thu_ky

#: Check-in quá bấy nhiêu phút mà chưa Hoàn tất thì nhắc (Tuyền duyệt 22/10).
NGUONG_PHUT = 120
_TRAN = 300

#: Chữ hiện trên màn — máy chủ nói, màn không tự đặt.
LY_DO_CHU = {
    "cho_doc_ket_qua": "Kết quả đã về đủ — chờ bác sĩ đọc",
    "dang_doc_do": "Đang đọc kết quả dở — chưa bấm xong",
    "cho_ket_qua": "Đang chờ kết quả dịch vụ",
    "kham_do": "Phiên khám đang mở dở — chưa bấm Khám xong",
    "cho_kham": "Khách chờ khám, chưa ai nhận",
    "con_chi_dinh": "Còn chỉ định đã duyệt chưa làm",
}

# Thứ tự CASE = việc bác sĩ phải làm trước: vòng đọc (việc chiếm 22/26 lượt
# kẹt) rồi phiên khám, cuối cùng chỉ định chưa làm (việc của phòng dịch vụ).
_DS_SQL = (
    """
WITH ds AS (
SELECT v.visit_id::text AS visit_id,
       v.checked_in_at,
       (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay,
       (v.checked_in_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date
         < (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS tu_hom_truoc,
       p.full_name, p.patient_code,
       coalesce(
           (SELECT c.doctor_staff_id FROM public.consultation c
             WHERE c.clinic_id = v.clinic_id AND c.visit_id = v.visit_id
               AND c.status <> 'cancelled' AND c.doctor_staff_id IS NOT NULL
             ORDER BY c.round_no DESC LIMIT 1),
           v.attending_doctor_id, ap.doctor_id)::text AS bac_si_id,
       CASE (SELECT r.status FROM public.review_round r
              WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                AND r.status <> 'closed'
              ORDER BY r.round_no DESC LIMIT 1)
            WHEN 'ready' THEN 'cho_doc_ket_qua'
            WHEN 'in_review' THEN 'dang_doc_do'
            WHEN 'collecting' THEN 'cho_ket_qua'
            ELSE CASE
                WHEN EXISTS (SELECT 1 FROM public.consultation c
                              WHERE c.clinic_id = v.clinic_id
                                AND c.visit_id = v.visit_id
                                AND c.status = 'in_progress') THEN 'kham_do'
                WHEN EXISTS (SELECT 1 FROM public.consultation c
                              WHERE c.clinic_id = v.clinic_id
                                AND c.visit_id = v.visit_id
                                AND c.status = 'queued')
                     AND NOT EXISTS (SELECT 1 FROM public.service_type st
                                      WHERE st.id = v.service_type_id
                                        AND st.nhom = 'DIEU_TRI') THEN 'cho_kham'
                WHEN EXISTS (SELECT 1 FROM public.service_order o
                              WHERE o.clinic_id = v.clinic_id
                                AND o.visit_id = v.visit_id
                                AND """
    + CHI_DINH_CON_VIEC_GIU_LUOT_SQL
    + """) THEN 'con_chi_dinh'
            END
       END AS ly_do,
       v.attending_doctor_id::text AS bac_si_luot,
       ap.doctor_id::text AS bac_si_hen
  FROM public.visit v
  LEFT JOIN public.appointment ap
         ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
  LEFT JOIN public.patient p
         ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 WHERE v.clinic_id = $1::uuid
   -- INCOMPLETE (khách về giữa chừng) / FINALIZED / AMENDED: đã có người chốt
   -- số phận lượt — không nhắc (cùng luật `luot_treo.py`).
   AND v.status IN ('OPEN', 'IN_PROGRESS') AND v.closed_at IS NULL
   AND NOT coalesce(v.ban_le, false)
   AND v.checked_in_at IS NOT NULL
   AND v.checked_in_at < now() - make_interval(mins => """
    + str(NGUONG_PHUT)
    + """)
   AND NOT """
    + kham_xong_sql("v")
    + """
   -- Cơ sở đang đứng; $2 NULL = không lọc (cùng câu `cho_quyet`).
   AND coalesce(v.location_id, ap.location_id, $2::uuid)
       IS NOT DISTINCT FROM coalesce($2::uuid, v.location_id, ap.location_id)
)
SELECT ds.*, s.full_name AS bac_si_ten
  FROM ds
  LEFT JOIN public.staff s ON s.id::text = ds.bac_si_id
 WHERE ds.ly_do IS NOT NULL
   AND ($3::text[] IS NULL
        OR ds.bac_si_luot = ANY($3::text[])
        OR ds.bac_si_hen = ANY($3::text[])
        OR EXISTS (SELECT 1 FROM public.consultation c
                    WHERE c.clinic_id = $1::uuid
                      AND c.visit_id::text = ds.visit_id
                      AND c.doctor_staff_id::text = ANY($3::text[])))
 ORDER BY ds.checked_in_at
"""
)


async def doc_luot_chua_hoan_tat(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    location_id: str | None,
    bac_si: list[str] | None,
) -> list[dict[str, Any]]:
    """Lượt chưa Hoàn tất quá ngưỡng; `bac_si` None = không lọc theo bác sĩ."""
    rows = await conn.fetch(
        _DS_SQL + f" LIMIT {_TRAN}", clinic_id, location_id or None, bac_si
    )
    canh_bao_neu_day("nhac_chua_hoan_tat", len(rows), _TRAN, clinic_id=clinic_id)
    return [
        {
            "visit_id": r["visit_id"],
            "ten": r["full_name"],
            "ma_bn": r["patient_code"],
            "checked_in_at": r["checked_in_at"].isoformat(),
            "ngay": r["ngay"].isoformat(),
            "tu_hom_truoc": bool(r["tu_hom_truoc"]),
            "ly_do": r["ly_do"],
            "ly_do_chu": LY_DO_CHU[r["ly_do"]],
            "bac_si_id": r["bac_si_id"],
            "bac_si_ten": r["bac_si_ten"],
        }
        for r in rows
    ]


async def dem_luot_chua_hoan_tat(
    conn: asyncpg.Connection, *, clinic_id: str, location_id: str | None
) -> int:
    """Số lượt chưa Hoàn tất của cả cơ sở — dòng "Cần xử lý" ở Trang chủ."""
    return int(
        await conn.fetchval(
            f"SELECT count(*) FROM ({_DS_SQL}) t",
            clinic_id,
            location_id or None,
            None,
        )
    )


async def luot_chua_hoan_tat(
    conn: asyncpg.Connection, *, identity: StaffIdentity
) -> dict[str, Any]:
    """Khối nhắc ở đầu Bàn khám. Phạm vi xem đầu tệp."""
    await doi_quyen(
        conn,
        identity,
        "clinical.consult.perform",
        cau="Chỉ người có quyền Bàn khám xem lượt chưa Hoàn tất.",
    )
    bac_si = await bac_si_cua_thu_ky(conn, identity)
    pham_vi = "bac_si_duoc_phan"
    if bac_si is None:
        if await can(conn, identity, "config.clinic.manage"):
            # Quản lý bấm dòng đếm ở Trang chủ sang đây → thấy cả cơ sở.
            pham_vi = "co_so"
        elif await can(conn, identity, "clinical.consult.finalize"):
            bac_si, pham_vi = [identity.staff_id], "cua_toi"
        else:
            pham_vi = "co_so"
    items = await doc_luot_chua_hoan_tat(
        conn,
        clinic_id=identity.clinic_id,
        location_id=identity.location_id,
        bac_si=bac_si,
    )
    return {"items": items, "pham_vi": pham_vi, "nguong_phut": NGUONG_PHUT}


__all__ = [
    "LY_DO_CHU",
    "NGUONG_PHUT",
    "dem_luot_chua_hoan_tat",
    "doc_luot_chua_hoan_tat",
    "luot_chua_hoan_tat",
]
