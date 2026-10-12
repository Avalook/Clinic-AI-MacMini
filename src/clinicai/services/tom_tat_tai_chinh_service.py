"""Các chỉ số tài chính từ nguồn báo cáo đã lọc quyền, ngày và ca.

Không suy giảm giá từ chênh lệch bảng giá: hệ thống chưa có sổ giảm giá.
Không thay đổi tập ngày của báo cáo cũ; đây là số hiệu lực hiện tại của tập ấy.
"""

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import asyncpg


async def doc_no_trong_khoang(
    conn: asyncpg.Connection,
    clinic_id: str,
    tu: date,
    den: date,
    *,
    co_so: str | None = None,
    loai: str | None = None,
    tu_luc: datetime | None = None,
    den_luc: datetime | None = None,
) -> int:
    """Nợ được ghi trong khoảng/ca đã chọn, còn chưa thu tới hiện tại."""
    so = await conn.fetchval(
        """
        SELECT coalesce(sum(CASE WHEN $5::text IS NULL THEN n.so_tien
          ELSE (SELECT coalesce(sum((d->>'so_tien')::numeric), 0)
                  FROM jsonb_array_elements(n.dong) d
                 WHERE d->>'loai' = $5) END), 0)
          FROM public.cong_no n
          JOIN public.visit v ON v.visit_id = n.visit_id
                             AND v.clinic_id = n.clinic_id
          LEFT JOIN public.appointment a ON a.id = v.appointment_id
                                        AND a.clinic_id = n.clinic_id
         WHERE n.clinic_id = $1::uuid AND n.trang_thai = 'CHUA_THU'
           AND (n.ghi_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
           AND ($4::uuid IS NULL OR coalesce(v.location_id,a.location_id) = $4)
           AND ($6::timestamptz IS NULL OR n.ghi_luc >= $6)
           AND ($7::timestamptz IS NULL OR n.ghi_luc < $7)
        """,
        clinic_id,
        tu,
        den,
        co_so,
        loai,
        tu_luc,
        den_luc,
    )
    return int(so)


def tom_tat_tai_chinh(
    bao_cao: Mapping[str, Any], *, no_trong_khoang: int | None
) -> dict[str, Any]:
    """Nợ phải được truy vấn theo phạm vi đã cấp quyền, không dùng nợ toàn clinic.

    Doanh thu lấy dòng hàng của phiếu PAID, không lấy số lần thu làm doanh thu.
    Hoàn tiền chỉ COMPLETED; ngày thuộc tập khoản hoàn tạo trong khoảng đã chọn.
    """
    tong = bao_cao.get("tong") or {}
    hang_hoa = bao_cao.get("hang_hoa") or {}
    doanh_thu = sum(int(v["tong"]["doanh_thu"]) for v in hang_hoa.values())
    doanh_thu_thuan = sum(int(v["tong"]["doanh_thu_thuan"]) for v in hang_hoa.values())
    hoan = {r["ma"]: int(r.get("hoan") or 0) for r in bao_cao.get("theo_hinh_thuc", ())}
    return {
        "so_phieu_thu": int(tong.get("so_phieu_thu") or 0),
        "doanh_thu": doanh_thu,
        "hoan_tien_mat": hoan.get("CASH", 0),
        "hoan_chuyen_khoan": hoan.get("TRANSFER", 0) + hoan.get("QR", 0),
        "no_chua_thu": no_trong_khoang,
        "giam_gia": None,
        "doanh_thu_thuan": doanh_thu_thuan,
        "thuc_thu": int(tong.get("thuc_thu") or 0),
        "chua_co_du_lieu": ["giam_gia"]
        + (["no_chua_thu"] if no_trong_khoang is None else []),
        "pham_vi": {
            "so_phieu_thu": "Phiếu có ngày thu trong khoảng, gồm phiếu đã huỷ.",
            "doanh_thu": "Dòng hàng của phiếu còn hiệu lực, theo ngày thu.",
            "hoan": "Khoản đã hoàn, theo ngày lập khoản hoàn trong khoảng.",
            "no_chua_thu": "Nợ ghi trong khoảng đã chọn, còn chưa thu tới hiện tại.",
            "doanh_thu_thuan": (
                "Doanh thu trừ giá trị dòng hàng đã hoàn trong tập báo cáo."
            ),
            "thuc_thu": "Tiền thu trừ phiếu huỷ và khoản đã hoàn trong tập báo cáo.",
        },
    }
