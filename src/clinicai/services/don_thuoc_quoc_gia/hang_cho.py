"""Hàng chờ gửi đơn thuốc quốc gia — VÀO HÀNG (outbox trên Postgres, SO-LUAT 7.1).

"Đơn chốt" = lượt khám ĐÃ ĐÓNG (`visit.closed_at`: khách về / về giữa chừng) có
ít nhất một dòng thuốc bác sĩ kê. Lúc ấy đơn thôi đổi trong ca; TT 26/2025 Điều
12 khoản 6d đòi gửi "ngay sau khi kết thúc việc khám bệnh".

Vào hàng bằng SOÁT, không bằng sự kiện: mỗi vòng worker đọc lượt đã đóng trong
`soat_ngay` ngày gần nhất, dựng gói đơn hiện hành, so dấu vân tay với phiên bản
mới nhất đã vào hàng — khác thì thêm phiên bản mới, MÃ ĐƠN MỚI. Vì đơn đã gửi
không sửa được trên hệ thống quốc gia (QĐ 425 Điều 9), đính chính sau khi khách
về (sửa số, gỡ dòng, bổ sung số CCHN…) thành một ĐƠN THAY THẾ. Công tắc tắt thì
không sự kiện / bên nhận nào đổi.

Idempotent ở Postgres: `uq_dtqg_gui_phien_ban` + `ON CONFLICT DO NOTHING`.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import asyncpg

from clinicai.ports.don_thuoc_quoc_gia import GoiDon
from clinicai.services.don_thuoc_quoc_gia.anh_xa import (
    dau_don,
    dau_van_tay_goi_don,
    doc_goi_don,
    goi_sang_json,
    goi_tu_json,
)
from clinicai.services.don_thuoc_quoc_gia.cau_hinh import CauHinh
from clinicai.services.don_thuoc_quoc_gia.ma_don import sinh_ma_don

#: Trạng thái tính ra của một dòng hàng chờ (một luật với SQL `dtqg_trang_thai`).
DA_GUI = "DA_GUI"
BI_THAY = "BI_THAY"
KHONG_CAN = "KHONG_CAN"
LOI = "LOI"
CHO_GUI = "CHO_GUI"

#: Mỗi trang soát chừng này lượt khám (một vòng đi HẾT các trang).
LO_SOAT = 300


def trang_thai_dong(
    *,
    da_gui: bool,
    co_ban_moi_hon: bool,
    het_luot: bool,
    la_huy: bool,
    da_tung_gui: bool,
) -> str:
    """HÀM THUẦN. `da_tung_gui` = lượt có phiên bản TRƯỚC đã gửi thành công.
    Đơn gỡ hết mà chưa từng lên hệ thống thì không có gì phải báo."""
    if da_gui:
        return DA_GUI
    if co_ban_moi_hon:
        return BI_THAY
    if la_huy and not da_tung_gui:
        return KHONG_CAN
    if het_luot:
        return LOI
    return CHO_GUI


_UNG_VIEN_SQL = """
SELECT v.visit_id::text AS visit_id, v.closed_at
  FROM public.visit v
  JOIN public.patient pt
    ON pt.clinic_patient_id = v.clinic_patient_id AND pt.clinic_id = v.clinic_id
 WHERE v.clinic_id = $1::uuid
   AND COALESCE(v.location_id, pt.location_id) = $2::uuid
   AND v.closed_at IS NOT NULL
   AND v.closed_at >= ($3::date)::timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh'
   AND v.closed_at >= now() - make_interval(days => $4::int)
   AND EXISTS (SELECT 1 FROM public.prescription p
                WHERE p.clinic_id = v.clinic_id AND p.visit_id = v.visit_id
                  AND p.nguon = 'BAC_SI')
   -- rx:gom-ca-lich-su: lượt từng có đơn (kể cả dòng đã gỡ) vẫn là ứng viên, để
   -- bắt "đơn đã gửi rồi bị gỡ hết"; nội dung gói đơn đọc hiện hành ở anh_xa.
   AND ($5::timestamptz IS NULL
        OR (v.closed_at, v.visit_id) > ($5::timestamptz, $6::uuid))
 ORDER BY v.closed_at, v.visit_id
 LIMIT $7
"""
#: Con trỏ đầu (NULL = chưa có): trước mọi lượt.
_DAU: tuple[Any, Any] = (None, None)

_MOI_NHAT_SQL = """
SELECT DISTINCT ON (g.visit_id) g.visit_id::text AS visit_id, g.phien_ban,
       g.dau_van_tay, g.la_huy, g.goi, g.da_gui_luc IS NOT NULL AS da_gui
  FROM public.dtqg_gui g
 WHERE g.clinic_id = $1::uuid AND g.visit_id = ANY($2::uuid[])
 ORDER BY g.visit_id, g.phien_ban DESC
"""


def can_ban_moi(g: GoiDon, cu: asyncpg.Record | None) -> bool:
    """Có phải thêm phiên bản mới cho lượt không (so với phiên bản mới nhất `cu`)."""
    if not g.thuoc and (cu is None or cu["la_huy"]):
        # Chưa từng vào hàng mà rỗng / đã ghi bản rỗng: không có gì mới.
        return False
    if cu is None:
        return True
    if cu["dau_van_tay"] == dau_van_tay_goi_don(g):
        return False
    if cu["da_gui"] and not cu["la_huy"]:
        # Đã lên hệ thống quốc gia: chỉ phần ĐƠN đổi mới thành đơn thay thế.
        tho = cu["goi"]
        return dau_don(
            goi_tu_json(json.loads(tho) if isinstance(tho, str) else tho)
        ) != (dau_don(g))
    return True


async def _vao_hang_lo(conn: asyncpg.Connection, ch: CauHinh, vids: list[str]) -> int:
    goi = await doc_goi_don(
        conn,
        clinic_id=ch.clinic_id,
        visit_ids=vids,
        ma_lien_thong={k: v.ma_lien_thong for k, v in ch.bac_si.items()},
    )
    moi_nhat = {
        r["visit_id"]: r
        for r in await conn.fetch(_MOI_NHAT_SQL, ch.clinic_id, sorted(goi))
    }
    them = 0
    for vid, g in goi.items():
        cu = moi_nhat.get(vid)
        if not can_ban_moi(g, cu):
            continue
        g = replace(g, ma_don=sinh_ma_don(ch.ma_co_so))
        kq = await conn.execute(
            "INSERT INTO public.dtqg_gui"
            " (clinic_id, visit_id, phien_ban, ma_don, goi, dau_van_tay, la_huy)"
            " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7)"
            " ON CONFLICT ON CONSTRAINT uq_dtqg_gui_phien_ban DO NOTHING",
            ch.clinic_id,
            vid,
            (cu["phien_ban"] if cu else 0) + 1,
            g.ma_don,
            json.dumps(goi_sang_json(g), ensure_ascii=False),
            dau_van_tay_goi_don(g),
            not g.thuoc,
        )
        them += str(kq).endswith(" 1")
    return them


async def vao_hang_don_thuoc(pool: asyncpg.Pool, ch: CauHinh) -> int:
    """Một lượt soát HẾT cửa sổ `soat_ngay` (theo trang `LO_SOAT`, con trỏ
    (closed_at, visit_id) — lượt mới nhất không bao giờ bị lô cũ chiếm chỗ).
    Trả số phiên bản mới đã vào hàng. CÓ THỂ ném (lỗi DB)."""
    them = 0
    sau: tuple[Any, Any] = _DAU
    async with pool.acquire() as conn:
        while True:
            rows = await conn.fetch(
                _UNG_VIEN_SQL,
                ch.clinic_id,
                ch.location_id,
                ch.gui_tu,
                ch.soat_ngay,
                *sau,
                LO_SOAT,
            )
            if rows:
                them += await _vao_hang_lo(conn, ch, [r["visit_id"] for r in rows])
            if len(rows) < LO_SOAT:
                return them
            sau = (rows[-1]["closed_at"], rows[-1]["visit_id"])


__all__ = [
    "BI_THAY",
    "CHO_GUI",
    "DA_GUI",
    "KHONG_CAN",
    "LOI",
    "trang_thai_dong",
    "vao_hang_don_thuoc",
]
