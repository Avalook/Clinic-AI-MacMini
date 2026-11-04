"""Đọc sổ chạy bóng luật "đứng đâu làm việc đó" cho /ops (Tuyền 04/11/2026).

Gom `quyen_chay_bong` theo người / việc / phòng trong một khoảng ngày. "Sẽ bị
chặn" = hôm nay luật cũ CHO mà luật mới KHÔNG cho — đúng con số phải biết trước
khi bật luật. Dòng luật cũ cũng chặn thì không tính (đằng nào cũng bị chặn).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import asyncpg

from clinicai.core.clock import doc_ngay_xem, hom_nay_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.permissions.chay_bong import GIU_NGAY, LY_DO

THEO = ("nguoi", "viec", "phong")

# Khoá gom + tên hiện của từng cách gom. Phòng: một lệnh tính cho MỌI phòng
# người ấy đứng hôm đó; không đứng phòng nào → nhóm "Không đứng phòng nào".
_GOM: dict[str, tuple[str, str, str]] = {
    "nguoi": (
        "b.staff_id::text",
        "coalesce(max(s.full_name), 'Không rõ')",
        "LEFT JOIN staff s ON s.id = b.staff_id",
    ),
    "viec": (
        "coalesce(b.work_pack, '?')",
        "coalesce(max(w.ten), max(b.work_pack), '?')",
        "LEFT JOIN work_pack w ON w.ma = b.work_pack",
    ),
    "phong": (
        "p.room_id::text",
        "coalesce(max(r.name), 'Không đứng phòng nào')",
        "LEFT JOIN LATERAL unnest(CASE WHEN cardinality(b.phong_lich) = 0"
        " THEN ARRAY[NULL::uuid] ELSE b.phong_lich END) AS p(room_id) ON true"
        " LEFT JOIN clinic_room r ON r.id = p.room_id",
    ),
}


def khoang_ngay(tu: str | None, den: str | None) -> tuple[date, date]:
    """Khoảng ngày người chọn. Rác / trống → hôm nay; đảo ngược thì đổi chỗ;
    dài quá số ngày sổ giữ thì cắt (đằng nào cũng không còn dòng)."""
    a = doc_ngay_xem(tu) or hom_nay_vn()
    b = doc_ngay_xem(den) or a
    if b < a:
        a, b = b, a
    if (b - a).days > GIU_NGAY:
        a = b - timedelta(days=GIU_NGAY)
    return a, b


async def tong_hop(
    pool: asyncpg.Pool,
    *,
    clinic_id: str,
    tu: str | None = None,
    den: str | None = None,
    theo: str | None = None,
) -> dict[str, Any]:
    cach = theo if theo in THEO else "nguoi"
    a, b = khoang_ngay(tu, den)
    khoa, ten, noi = _GOM[cach]
    # Chuỗi ghép chỉ từ bảng _GOM cố định ở trên, không từ người dùng.
    sql = f"""
        SELECT {khoa} AS khoa, {ten} AS ten,
               count(*) AS so_lenh,
               count(*) FILTER (WHERE b.cho_cu AND NOT b.cho_moi) AS so_chan,
               count(DISTINCT b.staff_id) AS so_nguoi,
               coalesce(jsonb_object_agg(b.ly_do, 1)
                   FILTER (WHERE b.cho_cu AND NOT b.cho_moi), '{{}}') AS ly_do
          FROM quyen_chay_bong b
          {noi}
         WHERE b.clinic_id = $1::uuid AND b.ngay BETWEEN $2 AND $3
         GROUP BY 1
         ORDER BY so_chan DESC, so_lenh DESC, ten
         LIMIT 300
    """  # noqa: S608
    rows = await pool.fetch(sql, clinic_id, a, b)
    canh_bao_neu_day("quyen_chay_bong.gom", len(rows), 300, theo=cach)
    tong = await pool.fetchrow(
        """
        SELECT count(*) AS so_lenh,
               count(*) FILTER (WHERE cho_cu AND NOT cho_moi) AS so_chan,
               count(DISTINCT staff_id) AS so_nguoi,
               count(DISTINCT staff_id) FILTER (WHERE cho_cu AND NOT cho_moi)
                   AS so_nguoi_bi_chan
          FROM quyen_chay_bong
         WHERE clinic_id = $1::uuid AND ngay BETWEEN $2 AND $3
        """,
        clinic_id,
        a,
        b,
    )
    gan_day = await pool.fetch(
        """
        SELECT b.luc, coalesce(s.full_name, 'Không rõ') AS nguoi,
               b.capability, coalesce(w.ten, b.work_pack) AS viec, b.ly_do,
               (SELECT string_agg(r.name, ', ' ORDER BY r.name)
                  FROM clinic_room r WHERE r.id = ANY(b.phong_lich)) AS phong
          FROM quyen_chay_bong b
          LEFT JOIN staff s ON s.id = b.staff_id
          LEFT JOIN work_pack w ON w.ma = b.work_pack
         WHERE b.clinic_id = $1::uuid AND b.ngay BETWEEN $2 AND $3
           AND b.cho_cu AND NOT b.cho_moi
         ORDER BY b.luc DESC
         LIMIT 100
        """,
        clinic_id,
        a,
        b,
    )
    # 100 dòng chặn gần nhất là cố ý (xem mẫu, không phải danh sách đủ) — số
    # đủ nằm ở `tong.so_chan`.
    canh_bao_neu_day("quyen_chay_bong.gan_day", len(gan_day), 100)
    return {
        "tu": a.isoformat(),
        "den": b.isoformat(),
        "theo": cach,
        "ly_do_ten": LY_DO,
        "tong": dict(tong) if tong else {},
        "dong": [
            {
                "khoa": r["khoa"],
                "ten": r["ten"],
                "so_lenh": r["so_lenh"],
                "so_chan": r["so_chan"],
                "so_nguoi": r["so_nguoi"],
                "ly_do": sorted(_ly_do(r["ly_do"])),
            }
            for r in rows
        ],
        "gan_day": [
            {
                "luc": r["luc"].isoformat(),
                "nguoi": r["nguoi"],
                "viec": r["viec"],
                "capability": r["capability"],
                "phong": r["phong"],
                "ly_do": r["ly_do"],
            }
            for r in gan_day
        ],
    }


def _ly_do(v: object) -> list[str]:
    # asyncpg trả jsonb dạng chuỗi khi không gắn codec.
    if isinstance(v, str):
        v = json.loads(v)
    return list(v) if isinstance(v, dict) else []


__all__ = ["THEO", "khoang_ngay", "tong_hop"]
