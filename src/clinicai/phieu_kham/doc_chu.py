"""Phiếu khám v5 ĐỌC THÀNH CHỮ — cho các màn xem lại / bản PDF không vẽ phiếu.

Tuyền 29/09/2026: "LƯỢT KHÁM TRƯỚC" không thấy phiếu v5. Phiếu v5 lưu ở
``phieu_kham_luot`` (khoá ô → ``{gia_tri, nguon}``), còn các màn đọc lượt cũ
(hồ sơ khám CSKH + PDF, tóm tắt lượt trước) chỉ biết bảng đời cũ
``clinical_form_response``. Module này dịch MỘT phiếu v5 thành các mục
``{ten, dong: [{nhan, chu}]}`` theo ĐÚNG khung phiên bản phiếu đã ghim — nhãn,
lựa chọn lấy từ khung, không suy từ khoá. Ô trống không in (như bản in A4).

Chỉ ĐỌC. Không quyền nào ở đây — người gọi đã gác.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import asyncpg

_NGAY_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _json(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    try:
        return json.loads(v)
    except ValueError:
        return None


def chu_o(o: Mapping[str, Any], nhap: Any) -> str | None:
    """Chữ đọc được của MỘT ô theo khung; ô trống → None."""
    gia = nhap.get("gia_tri") if isinstance(nhap, Mapping) else None
    if gia is None:
        return None
    nhan = {lc.get("ma"): lc.get("ten") for lc in o.get("lua_chon") or []}
    if isinstance(gia, Mapping):  # ô bảng: {cột: giá trị}
        phan = [f"{k}: {v}" for k, v in gia.items() if v not in (None, "")]
        return " · ".join(phan) or None
    if isinstance(gia, list):
        phan = [str(nhan.get(m) or m) for m in gia if m not in (None, "")]
        return ", ".join(phan) or None
    chu = str(gia).strip()
    if not chu:
        return None
    if o.get("kieu") == "chon":
        return str(nhan.get(chu) or chu)
    if o.get("kieu") == "ngay":
        m = _NGAY_ISO.match(chu)
        if m:
            return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    return chu


def noi_dung_phieu(khung: Any, du_lieu: Any) -> list[dict[str, Any]]:
    """Các mục CÓ CHỮ của phiếu, theo thứ tự khung. Rác → danh sách rỗng."""
    khung = _json(khung)
    du_lieu = _json(du_lieu)
    if not isinstance(khung, list) or not isinstance(du_lieu, Mapping):
        return []
    ra: list[dict[str, Any]] = []
    for muc in khung:
        if not isinstance(muc, Mapping):
            continue
        dong = []
        for o in muc.get("block") or []:
            if not isinstance(o, Mapping):
                continue
            chu = chu_o(o, du_lieu.get(o.get("ma")))
            if chu:
                dong.append({"ma": o.get("ma"), "nhan": o.get("ten"), "chu": chu})
        if dong:
            ra.append({"ten": muc.get("ten"), "dong": dong})
    return ra


async def doc_phieu_v5_chu(
    conn: asyncpg.Connection, *, clinic_id: str, visit_id: str
) -> list[dict[str, Any]]:
    """Mọi phiếu v5 của một lượt, đã dịch thành chữ — theo thứ tự tạo."""
    rows = await conn.fetch(
        """
        SELECT p.form_id, p.du_lieu, p.sua_luc, d.ten, d.khung,
               s.full_name AS nguoi_ghi
          FROM phieu_kham_luot p
          JOIN form_definition d
            ON d.clinic_id = p.clinic_id AND d.form_id = p.form_id
           AND d.version = p.version
          LEFT JOIN staff s ON s.id = coalesce(p.sua_boi, p.tao_boi)
         WHERE p.clinic_id = $1::uuid AND p.visit_id = $2::uuid
         ORDER BY p.tao_luc
        """,
        clinic_id,
        visit_id,
    )
    return [
        {
            "form_code": r["form_id"],
            "ten": r["ten"],
            "updated_at": r["sua_luc"],
            "nguoi_ghi": r["nguoi_ghi"],
            "v5": True,
            "muc": noi_dung_phieu(r["khung"], r["du_lieu"]),
        }
        for r in rows
    ]


__all__ = ["chu_o", "doc_phieu_v5_chu", "noi_dung_phieu"]
