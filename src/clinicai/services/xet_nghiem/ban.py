"""Bàn xét nghiệm đối tác — ĐỌC (kế hoạch 4.6, 5, chặng 3).

Một câu SQL đọc SỰ VIỆC của mỗi việc (thu, mẫu, tệp, gửi, đóng); trạng
thái do `trang_thai_xet_nghiem()` tính (luật 3 — không tính lại ở SQL hay TSX). Nút
nào bấm được cũng tính ở đây (`nut_cua`) — màn chỉ hiển thị cờ (luật 7).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

import asyncpg

from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.xet_nghiem.anh_ck import anh_cua_cac_khoan
from clinicai.services.xet_nghiem.doi_tac import CaiDatXN, doc_cai_dat
from clinicai.services.xet_nghiem.hanh_trinh import (
    buoc_dang,
    hanh_trinh,
    so_ngay_cho,
)
from clinicai.services.xet_nghiem.trang_thai import (
    LOC,
    NHAN,
    THU_TU,
    XONG,
    SuViecXN,
    TrangThaiXN,
    nut_cua,
    trang_thai_xet_nghiem,
)

TRAN_BAN = 500

#: $1 clinic · $2 từ ngày chỉ định (giờ VN) · $3 danh sách việc (NULL = mọi việc) ·
#: $4 ngày màn đang xem (NULL = không) — nạp THÊM đúng ngày đó, xếp lên trước trần
#: để ngày cũ không bị LIMIT cắt (mở rộng cửa sổ thì ngày cũ nhất bị cắt trước).
_SU_VIEC_SQL = f"""
SELECT x.service_order_id::text AS order_id, o.visit_id::text AS visit_id,
       o.service_name AS ten_dich_vu, (o.exec_status = 'cancelled') AS da_huy,
       x.doi_tac_id::text AS doi_tac_id, d.ten AS ten_doi_tac,
       d.tai_khoan_nhan_ck,
       (SELECT s.full_name FROM staff s WHERE s.id = tep.tai_len_boi_staff_id)
           AS tep_boi,
       x.gia_goi_y_luc_chi_dinh AS gia_goi_y, x.tao_luc,
       (x.tao_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_chi_dinh,
       t.ghi_luc AS thu_luc, m.lay_luc, tep.tai_len_luc AS tep_luc,
       tep.gui_luc, dg.dong_luc,
       v.clinic_patient_id::text AS clinic_patient_id,
       p.full_name AS ten_khach, p.patient_code AS ma_bn, p.phone_primary AS sdt,
       ap.so_tiep_don, ap.so_booking,
       t.id::text AS thu_id, t.so_tien AS da_thu, t.tien_mat, t.chuyen_khoan,
       t.ma_giao_dich,
       (t.ghi_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS ngay_thu,
       coalesce((SELECT sum(h.so_tien) FROM doi_tac_hoan_tien h
                  WHERE h.clinic_id = x.clinic_id AND h.thanh_toan_id = t.id), 0)
           AS da_hoan,
       m.id::text AS mau_id, m.ma_mau, m.hen_tra_ngay,
       tep.id::text AS tep_id, tep.ten_hien_thi AS ten_tep,
       tep.loai_tep, tep.mime AS mime_tep, tep.nguon AS tep_nguon,
       tep.drive_nguoi_tai,
       (SELECT count(*) FROM tep_ket_qua b
         WHERE b.clinic_id = x.clinic_id AND b.service_order_id = o.id
           AND b.da_xoa_luc IS NULL
           AND coalesce(b.xac_nhan_trang_thai, '') NOT IN ('TU_CHOI', 'THU_HOI'))
           AS so_ban,
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
  LEFT JOIN appointment ap ON ap.id = v.appointment_id AND ap.clinic_id = v.clinic_id
  LEFT JOIN doi_tac_thanh_toan t
    ON t.clinic_id = x.clinic_id AND t.service_order_id = o.id AND t.huy_luc IS NULL
  LEFT JOIN mau_xet_nghiem_viec mv
    ON mv.clinic_id = x.clinic_id AND mv.service_order_id = o.id AND mv.go_luc IS NULL
  LEFT JOIN mau_xet_nghiem m ON m.id = mv.mau_id AND m.huy_luc IS NULL
  LEFT JOIN LATERAL (
       SELECT k.id, k.ten_hien_thi, k.loai_tep, k.mime, k.gui_luc, k.tai_len_luc,
              k.tai_len_boi_staff_id, k.nguon, k.drive_nguoi_tai
         FROM tep_ket_qua k
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
        OR (x.tao_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $4::date
        OR (o.exec_status <> 'cancelled' AND dg.id IS NULL
            AND NOT coalesce(tep.gui_luc IS NOT NULL, false)))
 ORDER BY ((x.tao_luc AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = $4::date)
          DESC NULLS LAST,
          x.tao_luc DESC
 LIMIT {TRAN_BAN}
"""


def su_viec_cua(r: Any, hom_nay: date, nguong: int) -> SuViecXN:
    """Hàng SQL → sự việc (thuần)."""
    return SuViecXN(
        hom_nay=hom_nay,
        da_huy_chi_dinh=bool(r["da_huy"]),
        ngay_thu=r["ngay_thu"],
        co_mau=r["mau_id"] is not None,
        hen_tra=r["hen_tra_ngay"],
        co_tep=r["tep_id"] is not None,
        tep_moi_nhat_da_gui=bool(r["tep_moi_nhat_da_gui"]),
        tung_gui=bool(r["tung_gui"]),
        da_dong=r["dong_id"] is not None,
        da_hoan_tien=int(r["da_hoan"] or 0) > 0,
        nguong_lay_mau_ngay=nguong,
    )


def nguon_tep(r: Any) -> str | None:
    """Nguồn tờ kết quả cho màn: Drive (tự về / ghép tay bởi ai) hoặc tải tay."""
    if not r["tep_id"]:
        return None
    if r["tep_nguon"] == "DRIVE":
        nguoi = f" · {r['drive_nguoi_tai']}" if r["drive_nguoi_tai"] else ""
        ghep = f" · ghép bởi {r['tep_boi']}" if r["tep_boi"] else " · tự ghép"
        return f"Drive{nguoi}{ghep}"
    return f"Tải tay · {r['tep_boi']}" if r["tep_boi"] else "Tải tay"


def dong_ban(
    r: Any, tt: TrangThaiXN, hom_nay: date, *, hien_ma_ong: bool = True
) -> dict[str, Any]:
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
            "loai_tep",
            "mime_tep",
            "ma_giao_dich",
            "thu_id",
            "tai_khoan_nhan_ck",
            "sdt",
            "so_tiep_don",
            "so_booking",
        )
    }
    if not hien_ma_ong:
        # Công tắc "Hiện mã ống" tắt: mã vẫn có ở DB, chỉ không ra khỏi máy chủ.
        out["ma_mau"] = None
    out["nguon_tep"] = nguon_tep(r)
    out["so_ban"] = int(r["so_ban"] or 0)
    out["anh_ck"] = []
    for k in ("gia_goi_y", "da_thu", "tien_mat", "chuyen_khoan", "da_hoan"):
        out[k] = int(r[k]) if r[k] is not None else None
    for k in ("tao_luc", "ngay_chi_dinh", "tep_luc"):
        out[k] = r[k]
    out["so_ngay_cho"] = so_ngay_cho(r["ngay_chi_dinh"], hom_nay)
    out["hanh_trinh"] = hanh_trinh(r, tt)
    out["buoc_dang"] = buoc_dang(out["hanh_trinh"])
    out["trang_thai"] = asdict(tt)
    out["nut"] = nut_cua(
        tt,
        co_thu=r["thu_id"] is not None,
        con_hoan=int(r["da_thu"] or 0) - int(r["da_hoan"] or 0),
        co_mau=r["mau_id"] is not None,
        co_tep=r["tep_id"] is not None,
        tep_moi_nhat_da_gui=bool(r["tep_moi_nhat_da_gui"]),
    )
    return out


async def doc_viec(
    conn: asyncpg.Connection,
    cid: str,
    *,
    hom_nay: date,
    tu_ngay: date | None = None,
    order_ids: list[str] | None = None,
    ngay_xem: date | None = None,
    cai_dat: CaiDatXN | None = None,
) -> list[dict[str, Any]]:
    """`cai_dat`: người gọi đã đọc sẵn (cả bàn) thì truyền vào, khỏi đọc lại."""
    cd = cai_dat or await doc_cai_dat(conn, cid)
    rows = await conn.fetch(_SU_VIEC_SQL, cid, tu_ngay or hom_nay, order_ids, ngay_xem)
    canh_bao_neu_day("xet_nghiem_viec", len(rows), TRAN_BAN, clinic_id=cid)
    ds = [
        dong_ban(
            r,
            trang_thai_xet_nghiem(su_viec_cua(r, hom_nay, cd.nguong_lay_mau_ngay)),
            hom_nay,
            hien_ma_ong=cd.hien_ma_ong,
        )
        for r in rows
    ]
    anh = await anh_cua_cac_khoan(conn, cid, [v["thu_id"] for v in ds])
    for v in ds:
        v["anh_ck"] = anh.get(v["thu_id"] or "", [])
    return ds


def sap_xep(viec: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Việc cần làm trước lên đầu (THU_TU của module trạng thái)."""
    return sorted(viec, key=lambda v: THU_TU.index(v["trang_thai"]["ma"]))


def bo_loc() -> list[dict[str, Any]]:
    """Chip "Tình trạng" (thứ tự hành trình); `ton` = có ở tab "Còn tồn"."""
    return [{"ma": m, "nhan": NHAN[m], "ton": m not in XONG} for m in LOC]
