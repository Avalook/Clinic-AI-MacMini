"""Việc tiền còn chờ hiện tại; độc lập với khoảng ngày của báo cáo thu."""

from __future__ import annotations

from typing import Any

import asyncpg

from clinicai.core.clock import now_vn
from clinicai.services.cong_no_service import doc_khach_con_no
from clinicai.services.tien_thua_service import dong_tien_thua, giu_lai_dang_co

_TRAN = 100
_JOIN = """
 LEFT JOIN public.visit v ON v.visit_id = t.visit_id AND v.clinic_id = t.clinic_id
 LEFT JOIN public.appointment a ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
 LEFT JOIN public.patient p
   ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
"""
_LOC = """
 t.clinic_id = $1::uuid AND ($2::uuid IS NULL OR
 coalesce(v.location_id, a.location_id) = $2::uuid)
 AND ($3::text IS NULL OR t.kind = $3)
"""


def _gom(rows: list[dict[str, Any]], *, pham_vi_loai: str) -> dict[str, Any]:
    """Tổng tính trước khi cắt chi tiết, không làm mất số tiền ở danh sách dài."""
    return {
        "so_phieu": len(rows),
        "so_tien": sum(int(r["so_tien"]) for r in rows),
        "ds": rows[:_TRAN],
        "bi_cat": len(rows) > _TRAN,
        "pham_vi_loai": pham_vi_loai,
    }


async def _cho(
    conn: asyncpg.Connection,
    cid: str,
    cs: str | None,
    loai: str | None,
    *,
    hoan: bool,
) -> dict[str, Any]:
    table, key, status = (
        ("payment_refund", "refund_id", "PENDING")
        if hoan
        else ("payment_cycle", "payment_cycle_id", "PENDING_VERIFICATION")
    )
    # Các tên bảng/cột và trạng thái đều cố định nội bộ; tham số người dùng
    # chỉ đi qua bind parameters.
    rows = await conn.fetch(
        f"""SELECT t.{key}::text AS id, t.visit_id::text AS visit_id,
                   t.amount AS so_tien, t.kind AS loai_tien, t.created_at AS luc,
                   p.full_name AS khach, p.patient_code AS ma_bn
              FROM public.{table} t {_JOIN}
             WHERE {_LOC} AND t.status = '{status}'
             ORDER BY t.created_at, t.{key}""",
        cid,
        cs,
        loai,
    )
    ds = [
        {
            **dict(r),
            "so_tien": int(r["so_tien"]),
            "luc": r["luc"].isoformat() if r["luc"] else None,
        }
        for r in rows
    ]
    return _gom(ds, pham_vi_loai=loai or "dich_vu_va_thuoc")


async def _thua(
    conn: asyncpg.Connection,
    cid: str,
    cs: str | None,
    loai: str | None,
) -> dict[str, Any]:
    rows = (
        []
        if loai == "thuoc"
        else await conn.fetch(
            """SELECT v.visit_id::text AS visit_id, p.full_name AS khach,
                   p.patient_code AS ma_bn, v.created_at AS luc
              FROM public.visit v
              LEFT JOIN public.appointment a
                ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = v.clinic_patient_id
               AND p.clinic_id = v.clinic_id
             WHERE v.clinic_id = $1::uuid AND ($2::uuid IS NULL OR
                   coalesce(v.location_id, a.location_id) = $2::uuid)
             ORDER BY v.created_at, v.visit_id""",
            cid,
            cs,
        )
    )
    vids = [r["visit_id"] for r in rows]
    dong = await dong_tien_thua(conn, cid, vids)
    giu = await giu_lai_dang_co(conn, cid, vids)
    ds = []
    for r in rows:
        so = sum(int(d["so_tien"]) for d in dong.get(r["visit_id"], []))
        so -= int(giu.get(r["visit_id"], {}).get("so_tien", 0))
        if so > 0:
            ds.append(
                {
                    **dict(r),
                    "id": r["visit_id"],
                    "so_tien": so,
                    "luc": r["luc"].isoformat() if r["luc"] else None,
                }
            )
    kq = _gom(ds, pham_vi_loai="dich_vu")
    return {**kq, "so_luot": kq["so_phieu"]}


async def doc_viec_tien(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    co_so: str | None,
    loai: str | None,
    con_no: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Các khoản còn chờ của phòng khám/cơ sở, không phải ảnh chụp ngày cũ.

    Lần thu chia TM+CK chờ xác minh được đếm toàn phiếu, không chỉ phần CK.
    Công nợ đã ghi nhận có cả hai loại; không giả phân bổ tiền nợ theo quầy.
    """
    no = (
        con_no
        if con_no is not None
        else await doc_khach_con_no(
            conn,
            clinic_id,
            location_id=co_so,
        )
    )
    return {
        "tinh_den": now_vn().isoformat(),
        "pham_vi": "Các khoản còn chờ tính đến hiện tại, không theo ngày hoặc ca",
        "cho_xac_minh": await _cho(conn, clinic_id, co_so, loai, hoan=False),
        "hoan_cho": await _cho(conn, clinic_id, co_so, loai, hoan=True),
        "tien_thua": await _thua(conn, clinic_id, co_so, loai),
        "khach_con_no": {**no, "pham_vi_loai": "dich_vu_va_thuoc"},
    }
