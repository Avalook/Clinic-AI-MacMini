"""Bàn xét nghiệm đối tác — ĐỌC (kế hoạch 4.6, 5, chặng 3).

Một câu SQL đọc SỰ VIỆC của mỗi việc (thu, cho qua, mẫu, tệp, gửi, đóng); trạng
thái do `trang_thai_xet_nghiem()` tính (luật 3 — không tính lại ở SQL hay TSX). Nút
nào bấm được cũng tính ở đây (`nut_cua`) — màn chỉ hiển thị cờ (luật 7).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

import asyncpg

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.xet_nghiem.doi_tac import doc_nguong
from clinicai.services.xet_nghiem.trang_thai import (
    THU_TU,
    SuViecXN,
    TrangThaiXN,
    nut_cua,
    trang_thai_xet_nghiem,
)

TRAN_BAN = 500

#: $1 clinic · $2 từ ngày chỉ định (giờ VN) · $3 danh sách việc (NULL = mọi việc).
_SU_VIEC_SQL = """
SELECT x.service_order_id::text AS order_id, o.visit_id::text AS visit_id,
       o.service_name AS ten_dich_vu, (o.exec_status = 'cancelled') AS da_huy,
       x.doi_tac_id::text AS doi_tac_id, d.ten AS ten_doi_tac,
       x.gia_goi_y_luc_chi_dinh AS gia_goi_y, x.tao_luc,
       v.clinic_patient_id::text AS clinic_patient_id,
       p.full_name AS ten_khach, p.patient_code AS ma_bn,
       t.id::text AS thu_id, t.so_tien AS da_thu, t.tien_mat, t.chuyen_khoan,
       t.ma_giao_dich,
       (t.ghi_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_thu,
       coalesce((SELECT sum(h.so_tien) FROM doi_tac_hoan_tien h
                  WHERE h.clinic_id = x.clinic_id AND h.thanh_toan_id = t.id), 0)
           AS da_hoan,
       (x.cho_lay_mau_truoc_luc IS NOT NULL AND x.cho_lay_mau_go_luc IS NULL)
           AS duoc_cho_qua,
       (x.cho_lay_mau_go_luc IS NOT NULL) AS da_go_cho_qua,
       m.id::text AS mau_id, m.ma_mau, m.hen_tra_ngay,
       tep.id::text AS tep_id, tep.ten_hien_thi AS ten_tep,
       (tep.gui_luc IS NOT NULL) AS tep_moi_nhat_da_gui,
       EXISTS (SELECT 1 FROM tep_ket_qua g
                WHERE g.clinic_id = x.clinic_id AND g.service_order_id = o.id
                  AND g.gui_luc IS NOT NULL) AS tung_gui,
       dg.id::text AS dong_id
  FROM xet_nghiem_viec x
  JOIN service_order o ON o.id = x.service_order_id AND o.clinic_id = x.clinic_id
  JOIN doi_tac d ON d.id = x.doi_tac_id AND d.clinic_id = x.clinic_id
  LEFT JOIN visit v ON v.visit_id = o.visit_id AND v.clinic_id = o.clinic_id
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
  LEFT JOIN doi_tac_thanh_toan t
    ON t.clinic_id = x.clinic_id AND t.service_order_id = o.id AND t.huy_luc IS NULL
  LEFT JOIN mau_xet_nghiem_viec mv
    ON mv.clinic_id = x.clinic_id AND mv.service_order_id = o.id AND mv.go_luc IS NULL
  LEFT JOIN mau_xet_nghiem m ON m.id = mv.mau_id AND m.huy_luc IS NULL
  LEFT JOIN LATERAL (
       SELECT k.id, k.ten_hien_thi, k.gui_luc FROM tep_ket_qua k
        WHERE k.clinic_id = x.clinic_id AND k.service_order_id = o.id
          AND k.da_xoa_luc IS NULL
          AND coalesce(k.xac_nhan_trang_thai, '') NOT IN ('TU_CHOI', 'THU_HOI')
        ORDER BY k.tai_len_luc DESC LIMIT 1) tep ON true
  LEFT JOIN xet_nghiem_dong dg
    ON dg.clinic_id = x.clinic_id AND dg.service_order_id = o.id
   AND dg.mo_lai_luc IS NULL
 WHERE x.clinic_id = $1::uuid
   AND ($3::uuid[] IS NULL OR x.service_order_id = ANY ($3::uuid[]))
   -- Mặc định 30 ngày cho việc ĐÃ XONG; việc còn dở (chưa gửi, chưa đóng, chưa huỷ)
   -- luôn hiện dù cũ bao lâu — việc tồn không được biến mất khỏi bàn (soát chặng 3).
   AND ($3::uuid[] IS NOT NULL
        OR (x.tao_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date >= $2
        OR (o.exec_status <> 'cancelled' AND dg.id IS NULL
            AND NOT coalesce(tep.gui_luc IS NOT NULL, false)))
 ORDER BY x.tao_luc DESC
 LIMIT 500
"""


def su_viec_cua(r: Any, hom_nay: date, nguong: int) -> SuViecXN:
    """Hàng SQL → sự việc (thuần)."""
    return SuViecXN(
        hom_nay=hom_nay,
        da_huy_chi_dinh=bool(r["da_huy"]),
        ngay_thu=r["ngay_thu"],
        duoc_cho_qua=bool(r["duoc_cho_qua"]),
        co_mau=r["mau_id"] is not None,
        hen_tra=r["hen_tra_ngay"],
        co_tep=r["tep_id"] is not None,
        tep_moi_nhat_da_gui=bool(r["tep_moi_nhat_da_gui"]),
        tung_gui=bool(r["tung_gui"]),
        da_dong=r["dong_id"] is not None,
        da_hoan_tien=int(r["da_hoan"] or 0) > 0,
        nguong_lay_mau_ngay=nguong,
    )


def dong_ban(r: Any, tt: TrangThaiXN) -> dict[str, Any]:
    out = {
        k: r[k]
        for k in (
            "order_id",
            "visit_id",
            "ten_dich_vu",
            "doi_tac_id",
            "ten_doi_tac",
            "clinic_patient_id",
            "ten_khach",
            "ma_bn",
            "mau_id",
            "ma_mau",
            "hen_tra_ngay",
            "tep_id",
            "ten_tep",
            "ma_giao_dich",
        )
    }
    for k in ("gia_goi_y", "da_thu", "tien_mat", "chuyen_khoan", "da_hoan"):
        out[k] = int(r[k]) if r[k] is not None else None
    out["tao_luc"] = r["tao_luc"]
    out["trang_thai"] = asdict(tt)
    out["nut"] = nut_cua(
        tt,
        co_thu=r["thu_id"] is not None,
        con_hoan=int(r["da_thu"] or 0) - int(r["da_hoan"] or 0),
        co_mau=r["mau_id"] is not None,
        co_tep=r["tep_id"] is not None,
        tep_moi_nhat_da_gui=bool(r["tep_moi_nhat_da_gui"]),
        duoc_cho_qua=bool(r["duoc_cho_qua"]),
        da_go_cho_qua=bool(r["da_go_cho_qua"]),
    )
    return out


async def doc_viec(
    conn: asyncpg.Connection,
    cid: str,
    *,
    hom_nay: date,
    tu_ngay: date | None = None,
    order_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    nguong = await doc_nguong(conn, cid)
    rows = await conn.fetch(_SU_VIEC_SQL, cid, tu_ngay or hom_nay, order_ids)
    canh_bao_neu_day("xet_nghiem_viec", len(rows), TRAN_BAN, clinic_id=cid)
    return [
        dong_ban(r, trang_thai_xet_nghiem(su_viec_cua(r, hom_nay, nguong)))
        for r in rows
    ]


def sap_xep(viec: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Việc cần làm trước lên đầu (THU_TU của module trạng thái)."""
    return sorted(viec, key=lambda v: THU_TU.index(v["trang_thai"]["ma"]))
