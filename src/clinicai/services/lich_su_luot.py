"""LỊCH SỬ KHÁM của một khách — MỌI lượt (Tuyền chốt 07/10/2026, T7/T8 của
docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md).

`clinical_form_service.lich_su_kham` chỉ trả lượt CÓ PHIẾU, tối đa 20 (chip "Lần
n" ở Bàn khám — giữ nguyên). Đây là danh sách đủ: cả lượt không phiếu, lượt
chuyển từ hồ sơ Notion; lọc theo khoảng ngày / loại dịch vụ; kèm các NGÀY khách
có khám để lịch chấm xanh. Mỗi lượt mang `loai_du_lieu` — màn chọn khung đọc
theo đó (máy chủ quyết, không suy trong TSX):

* ``v5``     — có phiếu khám v5 (`phieu_kham_luot`) → hồ sơ kiểu Bàn khám.
* ``notion`` — lượt chuyển từ hồ sơ cũ Notion → khung đọc cũ.
* ``cu``     — phiếu đời cũ (`clinical_form_response`) → khung đọc cũ.
* ``trong``  — chưa có phiếu nào → khung đọc cũ.

Ngày lọc là chữ người dùng gõ: rác thì BỎ lọc ấy (không 500 — luật repo).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.core.clock import CLINIC_TZ

#: Nhãn hiện cạnh mỗi lượt (máy chủ nói, màn chỉ vẽ).
NHAN_LOAI: dict[str, str] = {
    "v5": "Phiếu khám",
    "notion": "Hồ sơ cũ (Notion)",
    "cu": "Phiếu đời cũ",
    "trong": "Chưa ghi phiếu",
}

#: Trần số lượt một lần đọc — khách lâu năm cũng chỉ vài trăm lượt.
TRAN = 500

#: Loại dữ liệu của MỘT lượt `v` (mẫu SQL dùng chung với danh sách bệnh nhân).
LOAI_DU_LIEU_SQL = """
CASE
  WHEN EXISTS (SELECT 1 FROM lich_su_notion.luot_that n
                WHERE n.clinic_id = {v}.clinic_id AND n.visit_id = {v}.visit_id)
    THEN 'notion'
  WHEN EXISTS (SELECT 1 FROM public.phieu_kham_luot p
                WHERE p.clinic_id = {v}.clinic_id AND p.visit_id = {v}.visit_id)
    THEN 'v5'
  WHEN EXISTS (SELECT 1 FROM public.clinical_form_response r
                WHERE r.clinic_id = {v}.clinic_id AND r.visit_id = {v}.visit_id)
    THEN 'cu'
  ELSE 'trong'
END
"""

_SQL = f"""
SELECT v.visit_id::text, v.appointment_id::text, v.status,
       coalesce(v.checked_in_at, a.slot_start, v.created_at) AS luc,
       st.id::text AS dich_vu_id, st.name AS dich_vu, st.nhom, st.form_code,
       s.full_name AS bac_si,
       (SELECT r.service_code FROM public.clinical_form_response r
         WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
         ORDER BY r.updated_at DESC LIMIT 1) AS service_code_cu,
       {LOAI_DU_LIEU_SQL.format(v="v")} AS loai_du_lieu
  FROM public.visit v
  LEFT JOIN public.appointment a
    ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
  LEFT JOIN public.service_type st
    ON st.id = coalesce(v.service_type_id, a.service_type_id)
  LEFT JOIN public.staff s ON s.id = v.attending_doctor_id
 WHERE v.clinic_id = $1::uuid AND v.clinic_patient_id = $2::uuid
 ORDER BY luc DESC, v.visit_id
 LIMIT {TRAN}
"""


def doc_ngay(v: Any) -> date | None:
    """Chuỗi ngày người dùng gửi (yyyy-mm-dd) → date; rác / rỗng → None."""
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    try:
        return date.fromisoformat(str(v or "").strip()[:10])
    except ValueError:
        return None


def ngay_vn(luc: Any) -> date | None:
    if not isinstance(luc, datetime):
        return None
    return (
        (luc if luc.tzinfo else luc.replace(tzinfo=CLINIC_TZ))
        .astimezone(CLINIC_TZ)
        .date()
    )


def loc(
    luot: list[dict[str, Any]],
    *,
    tu: date | None,
    den: date | None,
    dich_vu_id: str | None,
) -> list[dict[str, Any]]:
    """Lọc theo khoảng ngày (giờ VN, gồm hai đầu) + loại dịch vụ. Thuần."""
    if tu and den and tu > den:
        tu, den = den, tu
    ra = []
    for x in luot:
        n = doc_ngay(x.get("ngay"))
        if tu and (n is None or n < tu):
            continue
        if den and (n is None or n > den):
            continue
        if dich_vu_id and x.get("dich_vu_id") != dich_vu_id:
            continue
        ra.append(x)
    return ra


async def doc(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    clinic_patient_id: str,
    tu: Any = None,
    den: Any = None,
    dich_vu_id: str | None = None,
) -> dict[str, Any]:
    """Mọi lượt của khách (mới nhất trước) + ngày có khám + loại dịch vụ đã khám."""
    rows = await conn.fetch(_SQL, clinic_id, clinic_patient_id)
    tat_ca = [
        {
            "visit_id": r["visit_id"],
            "appointment_id": r["appointment_id"],
            "ngay": (ngay_vn(r["luc"]) or date.min).isoformat(),
            "luc": r["luc"].isoformat() if r["luc"] else None,
            "trang_thai": r["status"],
            "dich_vu_id": r["dich_vu_id"],
            "dich_vu": r["dich_vu"],
            "nhom": r["nhom"],
            "bac_si": r["bac_si"],
            "loai_du_lieu": r["loai_du_lieu"],
            "nhan_loai": NHAN_LOAI.get(r["loai_du_lieu"], r["loai_du_lieu"]),
            "service_code_cu": r["service_code_cu"],
        }
        for r in rows
    ]
    loai = {x["dich_vu_id"]: x["dich_vu"] for x in tat_ca if x["dich_vu_id"]}
    return {
        "luot": loc(tat_ca, tu=doc_ngay(tu), den=doc_ngay(den), dich_vu_id=dich_vu_id),
        "ngay_co_kham": sorted({x["ngay"] for x in tat_ca}),
        "dich_vu": [
            {"id": k, "ten": v}
            for k, v in sorted(loai.items(), key=lambda t: t[1] or "")
        ],
        "tong": len(tat_ca),
    }


__all__ = ["LOAI_DU_LIEU_SQL", "NHAN_LOAI", "TRAN", "doc", "doc_ngay", "loc", "ngay_vn"]
