"""Báo cáo TIÊU HAO vật tư theo phòng × kỳ (G8a, 14/10/2026) — chỉ đọc.

Tiêu hao = đầu + nhận − trả − cuối, trong đó đầu / cuối là SỐ ĐẾM THẬT (``thuc_te``
của phiếu KIEM / DIEU_CHINH), không phải tồn trên sổ:

* đầu = lần đếm gần nhất ≤ đầu kỳ; CHƯA có lần nào ≤ đầu kỳ (hệ thống mới, hoặc
  đếm ngay buổi sáng ngày đầu kỳ) thì lấy lần đếm ĐẦU TIÊN trong kỳ và báo
  ``dau_trong_ky`` — mỗi dòng luôn ghi giờ thật của hai lần đếm. Cuối = lần đếm
  gần nhất ≤ cuối kỳ;
* nhận / trả / huỷ chỉ tính GIỮA hai lần đếm ấy (theo thứ tự ghi sổ, không theo
  giờ — hai phiếu cùng lúc vẫn có thứ tự: ``giao_dich`` do khoá cơ sở sinh ra);
* thiếu một trong hai lần đếm → "chưa đủ dữ liệu", KHÔNG suy tồn sổ thành số đếm;
* lần đếm đã bị phiếu đảo thì không còn là mốc;
* giá = ``gia_nhap`` bản chụp trên dòng sổ gần nhất tới lần đếm cuối: đổi giá
  danh mục sau đó không làm đổi lịch sử;
* huỷ hỏng nằm TRONG tiêu hao, hiện thêm "trong đó huỷ";
* bán cho khách (phiếu BAN, 31/10/2026) cũng nằm TRONG tiêu hao. Công thức hai lần
  đếm giữ nguyên, chỉ TÁCH RA: hao hụt theo số đếm = đã bán + dùng (không bán) +
  huỷ. Không ai ghi sổ "đã dùng" nên số ấy là PHẦN CÒN LẠI; âm = đếm dư so với sổ.

Phiếu đảo lấy loại và chiều của dòng gốc (qua ``dao_txn_id``) nên nhận / trả / huỷ
là số RÒNG sau hoàn tác. Chỉ tính các phòng; kho cơ sở không có "tiêu hao".
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.services.kho_thuoc_service import dau_ngay_vn, khoang_xnt
from clinicai.services.vat_tu_kho_service import doc_ton, tinh_tieu_hao

_KY = ("tuan", "thang")

_SQL = """
WITH dong AS (
    SELECT x.id, x.dao_txn_id IS NOT NULL AS la_dong_dao,
           x.ton_id, x.vat_tu_id, x.so_luong, x.thuc_te, x.gia_nhap,
           p.tao_luc, p.giao_dich,
           coalesce(po.loai, p.loai) AS loai_goc,
           coalesce(o.so_luong, x.so_luong) AS so_goc,
           EXISTS (SELECT 1 FROM public.vat_tu_txn r
                    WHERE r.dao_txn_id = x.id AND r.clinic_id = x.clinic_id) AS da_dao
      FROM public.vat_tu_txn x
      JOIN public.vat_tu_phieu p ON p.id = x.phieu_id AND p.clinic_id = x.clinic_id
      JOIN public.vat_tu_ton t ON t.id = x.ton_id AND t.clinic_id = x.clinic_id
      LEFT JOIN public.vat_tu_txn o ON o.id = x.dao_txn_id AND o.clinic_id = x.clinic_id
      LEFT JOIN public.vat_tu_phieu po
             ON po.id = o.phieu_id AND po.clinic_id = o.clinic_id
     WHERE x.clinic_id = $1::uuid AND t.location_id = $2::uuid
       AND t.room_id IS NOT NULL
), dem AS (
    SELECT * FROM dong WHERE thuc_te IS NOT NULL AND NOT da_dao
), dem_moi_nhat AS (
    SELECT DISTINCT ON (ton_id) ton_id, giao_dich, tao_luc, thuc_te
      FROM dem ORDER BY ton_id, giao_dich DESC
), dau AS (
    SELECT DISTINCT ON (ton_id) ton_id, giao_dich, tao_luc, thuc_te
      FROM dem WHERE tao_luc <= $3 ORDER BY ton_id, giao_dich DESC
), dau_trong AS (
    SELECT DISTINCT ON (ton_id) ton_id, giao_dich, tao_luc, thuc_te
      FROM dem WHERE tao_luc > $3 AND tao_luc <= $4 ORDER BY ton_id, giao_dich
), cuoi AS (
    SELECT DISTINCT ON (ton_id) ton_id, giao_dich, tao_luc, thuc_te
      FROM dem WHERE tao_luc <= $4 ORDER BY ton_id, giao_dich DESC
), moc_dau AS (
    SELECT t.id AS ton_id,
           coalesce(a.giao_dich, b.giao_dich) AS giao_dich,
           coalesce(a.tao_luc, b.tao_luc) AS tao_luc,
           coalesce(a.thuc_te, b.thuc_te) AS thuc_te,
           (a.giao_dich IS NULL AND b.giao_dich IS NOT NULL) AS trong_ky
      FROM public.vat_tu_ton t
      LEFT JOIN dau a ON a.ton_id = t.id
      LEFT JOIN dau_trong b ON b.ton_id = t.id
     WHERE t.clinic_id = $1::uuid AND t.location_id = $2::uuid
)
SELECT t.vat_tu_id::text, t.room_id::text, s.name AS ten, s.don_vi,
       r.name AS phong, r.is_active AS phong_dang_bat,
       d.thuc_te AS dau, d.tao_luc AS dau_luc, d.trong_ky AS dau_trong_ky,
       c.thuc_te AS cuoi, c.tao_luc AS cuoi_luc,
       (d.giao_dich IS NOT NULL AND c.giao_dich IS NOT NULL
        AND c.giao_dich > d.giao_dich) AS du_moc,
       coalesce(f.nhan, 0) AS nhan, coalesce(f.tra, 0) AS tra,
       coalesce(f.huy, 0) AS huy, coalesce(f.tra_ncc, 0) AS tra_ncc,
       coalesce(f.da_ban, 0) AS da_ban,
       coalesce(cp.cap_trong_ky, 0) AS cap_trong_ky,
       dm.thuc_te AS thuc_te_gan_nhat, dm.tao_luc AS thuc_te_gan_nhat_luc,
       coalesce((SELECT g.gia_nhap FROM dong g
                  WHERE g.vat_tu_id = t.vat_tu_id
                    AND g.ton_id = t.id
                    AND (c.giao_dich IS NULL OR g.giao_dich <= c.giao_dich)
                  ORDER BY g.giao_dich DESC, g.tao_luc DESC
                  FETCH FIRST 1 ROW ONLY), 0) AS gia_nhap
  FROM public.vat_tu_ton t
  JOIN public.service_price s ON s.id = t.vat_tu_id AND s.clinic_id = t.clinic_id
  JOIN public.clinic_room r ON r.id = t.room_id AND r.clinic_id = t.clinic_id
  LEFT JOIN moc_dau d ON d.ton_id = t.id
  LEFT JOIN cuoi c ON c.ton_id = t.id
  LEFT JOIN dem_moi_nhat dm ON dm.ton_id = t.id
  LEFT JOIN LATERAL (
      SELECT sum(
                 CASE
                     WHEN f.la_dong_dao AND f.so_goc > 0 THEN f.so_luong
                     WHEN NOT f.la_dong_dao AND f.so_luong > 0 THEN f.so_luong
                     ELSE 0
                 END
             ) AS cap_trong_ky
        FROM dong f
       WHERE f.ton_id = t.id AND f.tao_luc >= $3 AND f.tao_luc < $4
         AND f.loai_goc IN ('XUAT_PHONG', 'CHUYEN_PHONG')
  ) cp ON true
  LEFT JOIN LATERAL (
      SELECT sum(f.so_luong)
                 FILTER (WHERE f.so_goc > 0 AND f.loai_goc <> 'HUY') AS nhan,
             -sum(f.so_luong)
                 FILTER (WHERE f.so_goc < 0 AND f.loai_goc NOT IN ('HUY', 'BAN'))
                 AS tra,
             -sum(f.so_luong) FILTER (WHERE f.loai_goc = 'HUY') AS huy,
             -sum(f.so_luong) FILTER (WHERE f.loai_goc = 'TRA_NCC') AS tra_ncc,
             -sum(f.so_luong) FILTER (WHERE f.loai_goc = 'BAN') AS da_ban
        FROM dong f
       WHERE f.ton_id = t.id
         AND d.giao_dich IS NOT NULL AND c.giao_dich IS NOT NULL
         AND f.giao_dich > d.giao_dich AND f.giao_dich <= c.giao_dich
         AND f.loai_goc IN (
             'NHAP', 'XUAT_PHONG', 'TRA_KHO', 'CHUYEN_PHONG', 'HUY', 'TRA_NCC',
             'BAN'
         )
  ) f ON true
 WHERE t.clinic_id = $1::uuid AND t.location_id = $2::uuid AND t.room_id IS NOT NULL
   AND EXISTS (SELECT 1 FROM dong z WHERE z.ton_id = t.id)
 ORDER BY r.name, s.name, t.id
"""


def khoang_ky(ky: Any, tu: Any, den: Any, hom_nay: date) -> tuple[date, date]:
    """Kỳ báo cáo: ``tuan`` = thứ Hai → hôm nay, ``thang`` = mùng 1 → hôm nay, còn
    lại = hai ngày người dùng chọn. Rác / rỗng → hôm nay, KHÔNG ném."""
    if ky == "tuan":
        return hom_nay - timedelta(days=hom_nay.weekday()), hom_nay
    if ky == "thang":
        return hom_nay.replace(day=1), hom_nay
    return khoang_xnt(tu, den, hom_nay)


def chuan_nhan_tra(nhan: Decimal, tra: Decimal) -> tuple[Decimal, Decimal]:
    """Nhận / trả RÒNG không âm: hoàn tác một phiếu của kỳ trước làm một vế âm."""
    if nhan >= 0 and tra >= 0:
        return nhan, tra
    rong = nhan - tra
    return (rong, Decimal(0)) if rong >= 0 else (Decimal(0), -rong)


def _thieu(dau: Any, cuoi: Any, du_moc: bool) -> str:
    if du_moc:
        return ""
    if dau is None and cuoi is None:
        return "Chưa có lần kiểm đếm nào"
    return "Mới có một lần kiểm đếm — cần hai lần (kiểm đếm ở tab Phiếu) để tính"


async def tinh_theo_moc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, tu_luc: Any, den_luc: Any
) -> list[dict[str, Any]]:
    """Từng (phòng, vật tư) có sổ: đủ hai lần đếm thì kèm tiêu hao và giá trị."""
    rows = await pool.fetch(
        _SQL, identity.clinic_id, identity.location_id, tu_luc, den_luc
    )
    ds: list[dict[str, Any]] = []
    for r in rows:
        nhan, tra = chuan_nhan_tra(Decimal(r["nhan"]), Decimal(r["tra"]))
        kq = (
            tinh_tieu_hao(r["dau"], nhan, tra, r["cuoi"], r["gia_nhap"])
            if r["du_moc"]
            else None
        )
        ds.append(
            {
                "vat_tu_id": r["vat_tu_id"],
                "room_id": r["room_id"],
                "ten": r["ten"],
                "don_vi": r["don_vi"],
                "phong": r["phong"],
                "phong_dang_bat": r["phong_dang_bat"],
                "du_du_lieu": kq is not None,
                "ly_do_thieu": "" if kq else _thieu(r["dau"], r["cuoi"], r["du_moc"]),
                "dau": r["dau"] if kq else None,
                "nhan": nhan if kq else None,
                "tra": tra if kq else None,
                "cuoi": r["cuoi"] if kq else None,
                "tieu_hao": kq["so_luong"] if kq else None,
                "da_dung": kq["so_luong"] - Decimal(r["huy"]) if kq else None,
                "trong_do_huy": r["huy"] if kq else None,
                "da_ban": r["da_ban"] if kq else None,
                "dung_khong_ban": (
                    kq["so_luong"] - Decimal(r["huy"]) - Decimal(r["da_ban"])
                    if kq
                    else None
                ),
                "tra_nha_san_xuat": r["tra_ncc"] if kq else None,
                "cap_trong_ky": Decimal(r["cap_trong_ky"]),
                "thuc_te_gan_nhat": r["thuc_te_gan_nhat"],
                "thuc_te_gan_nhat_luc": r["thuc_te_gan_nhat_luc"],
                "gia_nhap": r["gia_nhap"],
                "gia_tri": kq["gia_tri"] if kq else None,
                "gia_tri_da_dung": (kq["so_luong"] - Decimal(r["huy"]))
                * Decimal(r["gia_nhap"])
                if kq
                else None,
                "dem_dau_luc": r["dau_luc"] if kq else None,
                "dau_trong_ky": bool(r["dau_trong_ky"]) if kq else False,
                "dem_cuoi_luc": r["cuoi_luc"] if kq else None,
            }
        )
    return ds


async def doc_tieu_hao(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ky: Any = None,
    tu: Any = None,
    den: Any = None,
) -> dict[str, Any]:
    """Báo cáo của một kỳ (ngày VN, gồm cả hai đầu) + tổng giá trị từng phòng."""
    a, b = khoang_ky(ky, tu, den, hom_nay_vn())
    ds = await tinh_theo_moc(
        pool,
        identity=identity,
        tu_luc=dau_ngay_vn(a),
        den_luc=dau_ngay_vn(b + timedelta(days=1)),
    )
    nhac = {
        (t["vat_tu_id"], t["room_id"]): t["canh_bao"]
        for t in await doc_ton(pool, identity=identity)
    }
    tong: dict[str, dict[str, Any]] = {}
    for d in ds:
        d["canh_bao"] = nhac.get((d["vat_tu_id"], d["room_id"]), "")
        t = tong.setdefault(
            d["room_id"],
            {
                "room_id": d["room_id"],
                "phong": d["phong"],
                "gia_tri": Decimal(0),
                "gia_tri_da_dung": Decimal(0),
                "so_dong": 0,
                "chua_du": 0,
            },
        )
        t["so_dong"] += 1
        if d["du_du_lieu"]:
            t["gia_tri"] += d["gia_tri"]
            t["gia_tri_da_dung"] += d["gia_tri_da_dung"]
        else:
            t["chua_du"] += 1
    return {
        "ky": ky if ky in _KY else "tuy",
        "tu": a.isoformat(),
        "den": b.isoformat(),
        "items": ds,
        "theo_phong": list(tong.values()),
        "tong_gia_tri": sum((t["gia_tri"] for t in tong.values()), Decimal(0)),
        "tong_gia_tri_da_dung": sum(
            (t["gia_tri_da_dung"] for t in tong.values()), Decimal(0)
        ),
    }
