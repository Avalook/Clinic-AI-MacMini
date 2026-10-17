"""Kho thuốc kiểu KiotViet (Tuyền 29/09/2026: "ai cho vào có lịch sử ghi hết lại").

Bốn việc, tất cả đứng trên sổ kho `inventory_txn` có sẵn (chỉ-thêm, trigger
cộng tồn, CHECK tồn ≥ 0) — file này KHÔNG thêm đường nào đổi tồn ngoài sổ:

* **Thẻ kho** một thuốc: mọi dòng sổ VẬT LÝ (nhập, giao, điều chỉnh, huỷ,
  khách trả, kiểm kho) kèm tồn trước → tồn sau, người làm, mã phiếu.
* **Xuất – nhập – tồn** theo khoảng ngày: tồn đầu / nhập / xuất / điều chỉnh /
  huỷ / tồn cuối / giá trị tồn theo giá nhập của lô.
* **Phiếu nhập** nhiều dòng: một lệnh, một giao dịch; mỗi dòng đi đúng đường
  `nhap_vao_lo` của lệnh `receive`.
* **Phiếu kiểm kho**: máy chủ đọc tồn máy (khoá lô), tính lệch, ghi ADJUST.

`SALE` / `SALE_REVERSAL` là cam kết bán, không đổi tồn vật lý (CP3) — không
vào thẻ kho, không vào XNT.

Tồn trước/sau tính NGƯỢC từ tồn hiện tại (tồn sau của một dòng = tồn hiện tại
− tổng các dòng sau nó), nên đúng cả khi một lô có tồn khởi điểm không qua sổ.

KHO RIÊNG TỪNG CƠ SỞ (08/10/2026): mọi màn ở đây (thẻ kho, XNT, phiếu nhập,
kiểm kho) chỉ đọc/ghi kho của cơ sở đang làm — `identity.location_id`.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, doc_ngay_xem, hom_nay_vn
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.pharmacy_service import (
    DIEU_CHINH,
    PharmacyService,
    _so,
    ghi_nhat_ky,
    kiem_dong_nhap,
    nhap_vao_lo,
    quy_doi_dong_nhap,
    tach_kho_quay_bat,
    xet_quy_doi,
)

#: Loại dòng sổ đổi tồn VẬT LÝ (khác SALE / SALE_REVERSAL).
LOAI_VAT_LY = (
    "RECEIVE",
    "DISPENSE",
    "ADJUST",
    "DISCARD",
    "RETURN_RECEIVED",
    # G7: chuyển KHO ↔ QUẦY — đổi tồn từng HÀNG, tổng hai hàng của lô không đổi.
    "CHUYEN_RA",
    "CHUYEN_VAO",
)

#: Khoảng XNT dài nhất (ngày) — một năm là đủ cho báo cáo quý / năm.
XNT_TOI_DA_NGAY = 366

#: Số dòng tối đa một phiếu.
PHIEU_TOI_DA_DONG = 200

_TIEN_TO = {"NHAP": "PN", "KIEM": "KK", "CHUYEN": "CK"}


# ── Hàm thuần ────────────────────────────────────────────────────────────


def khoang_xnt(tu: Any, den: Any, hom_nay: date) -> tuple[date, date]:
    """Khoảng ngày XNT từ hai ô người dùng gửi. Rác / rỗng → hôm nay, KHÔNG ném.

    Đảo ngược thì đổi chỗ; dài quá `XNT_TOI_DA_NGAY` thì cắt từ ngày cuối lùi lại.
    """
    a = doc_ngay_xem(tu) or hom_nay
    b = doc_ngay_xem(den) or hom_nay
    if a > b:
        a, b = b, a
    if (b - a).days >= XNT_TOI_DA_NGAY:
        a = b - timedelta(days=XNT_TOI_DA_NGAY - 1)
    return a, b


def ma_phieu_kho(loai: str, ma_co_so: str, so: int) -> str:
    """Mã phiếu kho theo cơ sở: `PN-HN-0001`, `KK-KN-0012` (08/10/2026)."""
    return f"{_TIEN_TO[loai]}-{ma_co_so}-{so:04d}"


def dau_ngay_vn(ngay: date) -> datetime:
    """00:00 giờ VN của một ngày — mốc so với `performed_at` (timestamptz)."""
    return datetime.combine(ngay, time.min, tzinfo=CLINIC_TZ)


def _chu(v: Any, toi_da: int = 300) -> str | None:
    chu = " ".join(str(v or "").split())[:toi_da]
    return chu or None


# ── Đọc ──────────────────────────────────────────────────────────────────


async def the_kho(
    pool: asyncpg.Pool, *, identity: StaffIdentity, drug_catalog_id: str
) -> dict[str, Any]:
    """Thẻ kho một thuốc — mới nhất trước, tối đa 1000 dòng."""
    async with pool.acquire() as conn:
        thuoc = await conn.fetchrow(
            """
            SELECT c.id::text, c.name_raw AS ten, c.ma_hang, c.don_vi_ban,
                   c.ton_toi_thieu,
                   -- Tồn TÁCH THEO ĐƠN VỊ LÔ (29/09): 20 hộp + 50 viên không
                   -- phải 70 của thứ gì cả. `ton_hien_tai` chỉ có khi mọi lô
                   -- còn tồn cùng một đơn vị; nhiều đơn vị → NULL, đọc
                   -- `ton_theo_don_vi`. Đơn vị đã hết sạch bỏ qua (30/09).
                   (SELECT CASE WHEN count(*) = 0 THEN 0
                                WHEN count(*) = 1 THEN min(dv.ton) END
                      FROM (SELECT sum(b.quantity_on_hand) AS ton
                              FROM public.drug_batch b
                             WHERE b.clinic_id = c.clinic_id
                               AND b.location_id = $3::uuid
                               AND b.drug_catalog_id = c.id
                             GROUP BY lower(btrim(b.unit))
                            HAVING sum(b.quantity_on_hand) <> 0) dv) AS ton_hien_tai,
                   coalesce((
                       SELECT jsonb_agg(jsonb_build_object('don_vi', dv.don_vi,
                                                           'ton', dv.ton)
                                        ORDER BY dv.don_vi)
                         FROM (SELECT min(b.unit) AS don_vi,
                                      sum(b.quantity_on_hand) AS ton
                                 FROM public.drug_batch b
                                WHERE b.clinic_id = c.clinic_id
                                  AND b.location_id = $3::uuid
                                  AND b.drug_catalog_id = c.id
                                GROUP BY lower(btrim(b.unit))
                               HAVING sum(b.quantity_on_hand) <> 0) dv
                   ), '[]'::jsonb) AS ton_theo_don_vi
              FROM public.drug_catalog c
             WHERE c.clinic_id = $1::uuid AND c.id = $2::uuid
            """,
            identity.clinic_id,
            drug_catalog_id,
            identity.location_id,
        )
        if thuoc is None:
            raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
        rows = await conn.fetch(
            """
            -- rx:gom-ca-lich-su: sổ kho trỏ dòng đơn ĐÃ giao — dòng đó có
            -- bị đính chính sau này thì lần xuất kho vẫn là sự thật.
            WITH ton AS (
                SELECT lower(btrim(b.unit)) AS dv, sum(b.quantity_on_hand) AS ton
                  FROM public.drug_batch b
                 WHERE b.clinic_id = $1::uuid AND b.drug_catalog_id = $2::uuid
                   AND b.location_id = $4::uuid
                 GROUP BY lower(btrim(b.unit))
            ), so AS (
                SELECT t.id, t.performed_at, t.txn_type, t.quantity, t.reason,
                       t.ref_type, t.ref_id, t.performed_by_staff_id,
                       b.batch_code, b.expiry_date, b.unit,
                       lower(btrim(b.unit)) AS dv
                  FROM public.inventory_txn t
                  JOIN public.drug_batch b
                    ON b.id = t.drug_batch_id AND b.clinic_id = t.clinic_id
                 WHERE t.clinic_id = $1::uuid
                   AND b.drug_catalog_id = $2::uuid
                   AND b.location_id = $4::uuid
                   AND t.txn_type = ANY($3::text[])
            ), tinh AS (
                -- Tồn trước → sau chạy RIÊNG từng đơn vị lô.
                SELECT so.*,
                       coalesce(ton.ton, 0) - coalesce(sum(so.quantity) OVER (
                           PARTITION BY so.dv
                           ORDER BY so.performed_at DESC, so.id DESC
                           ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                       ), 0) AS ton_sau
                  FROM so
                  LEFT JOIN ton ON ton.dv = so.dv
            )
            SELECT tinh.id::text, tinh.performed_at AS luc, tinh.txn_type AS loai,
                   CASE
                       WHEN tinh.ref_type = 'phieu_kho' AND pk.loai = 'KIEM'
                           THEN 'Kiểm kho'
                       WHEN tinh.txn_type = 'CHUYEN_RA' THEN 'Chuyển kho (ra)'
                       WHEN tinh.txn_type = 'CHUYEN_VAO' THEN 'Chuyển kho (vào)'
                       WHEN tinh.ref_type = 'phieu_kho' THEN 'Nhập hàng'
                       WHEN tinh.txn_type = 'RECEIVE' THEN 'Nhập hàng'
                       WHEN tinh.txn_type = 'DISPENSE' THEN 'Bán / giao thuốc'
                       WHEN tinh.txn_type = 'ADJUST' THEN 'Điều chỉnh'
                       WHEN tinh.txn_type = 'DISCARD' THEN 'Huỷ thuốc'
                       WHEN tinh.txn_type = 'RETURN_RECEIVED' THEN 'Khách trả'
                       ELSE tinh.txn_type
                   END AS loai_nhan,
                   CASE
                       WHEN tinh.ref_type = 'phieu_kho' THEN pk.ma_phieu
                       WHEN tinh.ref_type = 'prescription' THEN p.patient_code
                   END AS ma_phieu,
                   CASE WHEN tinh.ref_type = 'prescription' THEN p.full_name END
                       AS khach,
                   tinh.batch_code AS so_lo, tinh.expiry_date AS han_dung,
                   tinh.quantity AS so_luong, tinh.unit AS don_vi,
                   tinh.ton_sau - tinh.quantity AS ton_truoc, tinh.ton_sau,
                   s.full_name AS nguoi_lam, tinh.reason AS ly_do
              FROM tinh
              LEFT JOIN public.phieu_kho pk
                ON tinh.ref_type = 'phieu_kho' AND pk.id = tinh.ref_id
               AND pk.clinic_id = $1::uuid
              LEFT JOIN public.prescription r
                ON tinh.ref_type = 'prescription' AND r.id = tinh.ref_id
               AND r.clinic_id = $1::uuid
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = r.clinic_patient_id
               AND p.clinic_id = r.clinic_id
              LEFT JOIN public.staff s ON s.id = tinh.performed_by_staff_id
             ORDER BY tinh.performed_at DESC, tinh.id DESC
             LIMIT 1000
            """,
            identity.clinic_id,
            drug_catalog_id,
            list(LOAI_VAT_LY),
            identity.location_id,
        )
    canh_bao_neu_day("kho.the_kho", len(rows), 1000, clinic_id=identity.clinic_id)
    return {
        "thuoc": {
            **dict(thuoc),
            "ton_theo_don_vi": json.loads(thuoc["ton_theo_don_vi"]),
        },
        "dong": [dict(r) for r in rows],
    }


async def xuat_nhap_ton(
    pool: asyncpg.Pool, *, identity: StaffIdentity, tu: Any, den: Any
) -> dict[str, Any]:
    """Xuất – nhập – tồn mỗi thuốc trong [tu, den] (ngày VN, gồm cả hai đầu)."""
    a, b = khoang_xnt(tu, den, hom_nay_vn())
    moc_dau = dau_ngay_vn(a)
    moc_cuoi = dau_ngay_vn(b + timedelta(days=1))
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH so AS (
                SELECT t.drug_batch_id,
                       sum(t.quantity) AS tu_dau,
                       sum(t.quantity) FILTER (WHERE t.performed_at >= $3)
                           AS tu_cuoi,
                       sum(t.quantity) FILTER (WHERE t.performed_at < $3
                           AND t.txn_type = 'RECEIVE') AS nhap,
                       sum(-t.quantity) FILTER (WHERE t.performed_at < $3
                           AND t.txn_type = 'DISPENSE') AS xuat,
                       sum(t.quantity) FILTER (WHERE t.performed_at < $3
                           AND t.txn_type = 'ADJUST') AS dieu_chinh,
                       sum(-t.quantity) FILTER (WHERE t.performed_at < $3
                           AND t.txn_type = 'DISCARD') AS huy,
                       sum(t.quantity) FILTER (WHERE t.performed_at < $3
                           AND t.txn_type = 'RETURN_RECEIVED') AS tra_lai
                  FROM public.inventory_txn t
                 WHERE t.clinic_id = $1::uuid
                   AND t.performed_at >= $2
                   AND t.txn_type = ANY($4::text[])
                 GROUP BY t.drug_batch_id
            ), lo AS (
                SELECT b.drug_catalog_id, b.cost_price, b.unit,
                       lower(btrim(b.unit)) AS dv,
                       b.quantity_on_hand - coalesce(so.tu_dau, 0) AS ton_dau,
                       b.quantity_on_hand - coalesce(so.tu_cuoi, 0) AS ton_cuoi,
                       coalesce(so.nhap, 0) AS nhap, coalesce(so.xuat, 0) AS xuat,
                       coalesce(so.dieu_chinh, 0) AS dieu_chinh,
                       coalesce(so.huy, 0) AS huy, coalesce(so.tra_lai, 0) AS tra_lai
                  FROM public.drug_batch b
                  LEFT JOIN so ON so.drug_batch_id = b.id
                 WHERE b.clinic_id = $1::uuid AND b.location_id = $5::uuid
            )
            -- Một dòng mỗi (thuốc, đơn vị lô) — không cộng hộp với viên (29/09).
            SELECT c.id::text AS drug_catalog_id, c.name_raw AS ten, c.ma_hang,
                   c.don_vi_ban, min(lo.unit) AS don_vi,
                   coalesce(sum(lo.ton_dau), 0) AS ton_dau,
                   coalesce(sum(lo.nhap), 0) AS nhap,
                   coalesce(sum(lo.xuat), 0) AS xuat,
                   coalesce(sum(lo.dieu_chinh), 0) AS dieu_chinh,
                   coalesce(sum(lo.huy), 0) AS huy,
                   coalesce(sum(lo.tra_lai), 0) AS tra_lai,
                   coalesce(sum(lo.ton_cuoi), 0) AS ton_cuoi,
                   CASE WHEN bool_or(lo.cost_price IS NOT NULL AND lo.ton_cuoi <> 0)
                        THEN sum(lo.ton_cuoi * lo.cost_price) END AS gia_tri_ton
              FROM public.drug_catalog c
              LEFT JOIN lo ON lo.drug_catalog_id = c.id
             WHERE c.clinic_id = $1::uuid
             GROUP BY c.id, lo.dv
            HAVING c.is_active
                OR coalesce(sum(abs(lo.ton_dau) + abs(lo.ton_cuoi) + lo.nhap
                                + lo.xuat + abs(lo.dieu_chinh) + lo.huy
                                + lo.tra_lai), 0) <> 0
             ORDER BY lower(c.name_raw), lo.dv
            """,
            identity.clinic_id,
            moc_dau,
            moc_cuoi,
            list(LOAI_VAT_LY),
            identity.location_id,
        )
    return {"tu": a.isoformat(), "den": b.isoformat(), "dong": [dict(r) for r in rows]}


async def xem_truoc_quy_doi(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    drug_catalog_id: str,
    unit: str,
    he_so: Any = None,
    so_luong: Any = None,
) -> dict[str, Any]:
    """Xem trước một dòng nhập: có phải đổi về đơn vị bán, hệ số nào, "= N đơn vị
    bán", và có cần xác nhận hệ số lạ không. Chỉ đọc — không nhớ hệ số.
    Số lượng rác → không có dòng "= N" (không ném)."""
    async with pool.acquire() as conn:
        x = await xet_quy_doi(
            conn,
            identity=identity,
            drug_catalog_id=drug_catalog_id,
            unit=unit,
            he_so=he_so,
        )
    kq: dict[str, Any] = {
        "can_doi": x["can_doi"],
        "don_vi_ban": x["don_vi_ban"],
        "he_so_da_nho": x["he_so_da_nho"],
        "he_so": x["he_so"],
        "can_xac_nhan": x["la"],
        "so_luong_quy_doi": None,
    }
    if x["can_doi"] and x["he_so"] is not None:
        try:
            luong = _so(so_luong, ten="Số lượng nhập")
        except ValidationError:
            return kq
        kq["so_luong_quy_doi"] = (luong * x["he_so"]).quantize(Decimal("0.001"))
    return kq


async def danh_sach_phieu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, loai: str
) -> list[dict[str, Any]]:
    """100 phiếu gần nhất một loại (NHAP / KIEM), kèm dòng — chỉ đọc."""
    if loai not in _TIEN_TO:
        raise ValidationError("Loại phiếu không hợp lệ.")
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT pk.id::text, pk.ma_phieu, pk.loai, pk.nha_cung_cap, pk.so_hoa_don,
                   pk.ngay_chung_tu, pk.ghi_chu, pk.tao_luc, s.full_name AS nguoi_tao,
                   pk.huong, pk.ly_do, pk.hoan_tac_cua::text,
                   EXISTS (SELECT 1 FROM public.phieu_kho h
                            WHERE h.hoan_tac_cua = pk.id) AS da_hoan_tac,
                   coalesce((
                       SELECT jsonb_agg(jsonb_build_object(
                                  'stt', d.stt, 'ten', c.name_raw,
                                  'so_lo', b.batch_code, 'han_dung', b.expiry_date,
                                  'don_vi', b.unit, 'so_luong', d.so_luong,
                                  'gia_nhap', d.gia_nhap, 'ton_may', d.ton_may,
                                  'thuc_te', d.thuc_te, 'lech', d.lech,
                                  'noi_chua', b.noi_chua)
                              ORDER BY d.stt)
                         FROM public.phieu_kho_dong d
                         JOIN public.drug_catalog c ON c.id = d.drug_catalog_id
                         JOIN public.drug_batch b ON b.id = d.drug_batch_id
                        WHERE d.clinic_id = pk.clinic_id AND d.phieu_kho_id = pk.id
                   ), '[]'::jsonb) AS dong
              FROM public.phieu_kho pk
              LEFT JOIN public.staff s ON s.id = pk.tao_boi
             WHERE pk.clinic_id = $1::uuid AND pk.loai = $2
               AND pk.location_id = $3::uuid
             ORDER BY pk.tao_luc DESC
             LIMIT 100
            """,
            identity.clinic_id,
            loai,
            identity.location_id,
        )
    canh_bao_neu_day("kho.phieu", len(rows), 100, clinic_id=identity.clinic_id)
    return [{**dict(r), "dong": json.loads(r["dong"])} for r in rows]


# ── Ghi ──────────────────────────────────────────────────────────────────


async def _phieu_da_co(
    conn: asyncpg.Connection, identity: StaffIdentity, khoa_gui: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT id::text, ma_phieu, loai FROM public.phieu_kho"
        " WHERE clinic_id = $1::uuid AND khoa_gui = $2",
        identity.clinic_id,
        khoa_gui,
    )
    return (
        None
        if row is None
        else {
            "ok": True,
            "id": row["id"],
            "ma_phieu": row["ma_phieu"],
            "loai": row["loai"],
            "gui_lai": True,
        }
    )


async def _mo_phieu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    loai: str,
    khoa_gui: str,
    nha_cung_cap: str | None = None,
    so_hoa_don: str | None = None,
    ngay_chung_tu: date | None = None,
    ghi_chu: str | None = None,
    huong: str | None = None,
    ly_do: str | None = None,
    hoan_tac_cua: str | None = None,
) -> tuple[str, str]:
    """Tạo đầu phiếu với mã kế tiếp CỦA KHO CƠ SỞ đang làm — `PN-HN-0001`:
    mỗi cơ sở một dãy số, mã cơ sở (`clinic_location.code`) nằm trong mã nên
    hai cơ sở không trùng nhau. Khoá tư vấn theo (phòng khám, cơ sở, loại) để
    hai phiếu cùng lúc không tranh một mã; UNIQUE (clinic_id, ma_phieu) là
    chốt cuối."""
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext($1))",
        f"phieu_kho:{identity.clinic_id}:{identity.location_id}:{loai}",
    )
    ma_co_so = await conn.fetchval(
        "SELECT upper(btrim(code)) FROM public.clinic_location"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid",
        identity.location_id,
        identity.clinic_id,
    )
    if not ma_co_so:
        raise NotFoundError("Không xác định được cơ sở đang làm — đăng nhập lại.")
    so = await conn.fetchval(
        "SELECT count(*) FROM public.phieu_kho"
        " WHERE clinic_id = $1::uuid AND location_id = $2::uuid AND loai = $3",
        identity.clinic_id,
        identity.location_id,
        loai,
    )
    ma = ma_phieu_kho(loai, ma_co_so, int(so) + 1)
    phieu_id = await conn.fetchval(
        """
        INSERT INTO phieu_kho
            (clinic_id, location_id, loai, ma_phieu, nha_cung_cap, so_hoa_don,
             ngay_chung_tu, ghi_chu, tao_boi, khoa_gui, huong, ly_do, hoan_tac_cua)
        VALUES ($1::uuid, $10::uuid, $2, $3, $4, $5, $6, $7, $8::uuid, $9,
                $11, $12, $13::uuid)
        RETURNING id::text
        """,
        identity.clinic_id,
        loai,
        ma,
        nha_cung_cap,
        so_hoa_don,
        ngay_chung_tu,
        ghi_chu,
        identity.staff_id,
        khoa_gui,
        identity.location_id,
        huong,
        ly_do,
        hoan_tac_cua,
    )
    return str(phieu_id), ma


def _khoa(khoa_gui: str | None) -> str:
    khoa = (khoa_gui or "").strip()
    if not khoa or len(khoa) > 200:
        raise ValidationError("Thiếu khoá chống gửi trùng — tải lại trang rồi thử lại.")
    return khoa


async def tao_phieu_nhap(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    nha_cung_cap: Any = None,
    so_hoa_don: Any = None,
    ngay_chung_tu: Any = None,
    ghi_chu: Any = None,
    dong: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phiếu nhập nhiều dòng — MỘT giao dịch: dòng nào hỏng thì cả phiếu không vào."""
    khoa = _khoa(khoa_gui)
    if not dong:
        raise ValidationError("Phiếu nhập cần ít nhất một dòng thuốc.")
    if len(dong) > PHIEU_TOI_DA_DONG:
        raise ValidationError(f"Một phiếu tối đa {PHIEU_TOI_DA_DONG} dòng.")
    # Ngày chứng từ rác → bỏ trống (không ném) — ngày ghi sổ vẫn là lúc bấm.
    ngay = doc_ngay_xem(ngay_chung_tu)
    sach: list[dict[str, Any]] = []
    for i, d in enumerate(dong, start=1):
        if not str(d.get("drug_catalog_id") or "").strip():
            raise ValidationError(f"Dòng {i}: chọn thuốc trong danh mục.")
        try:
            luong, ma_lo, _dv, han = kiem_dong_nhap(
                so_luong=d.get("so_luong"),
                batch_code=d.get("batch_code"),
                expiry_date=doc_ngay_xem(d.get("expiry_date")),
                unit=d.get("unit") or "-",
            )
        except ValidationError as exc:
            raise ValidationError(f"Dòng {i}: {exc.message}") from exc
        gia = d.get("gia_nhap")
        gia_so = (
            None
            if gia in (None, "")
            else _so(gia, ten=f"Dòng {i}: giá nhập", cho_0=True)
        )
        sach.append(
            {
                "drug_catalog_id": str(d.get("drug_catalog_id") or ""),
                "so_luong": luong,
                "ma_lo": ma_lo,
                "don_vi": (d.get("unit") or "").strip() or None,
                "han": han,
                "gia": gia_so,
                "he_so": d.get("he_so"),
                "xac_nhan_he_so": bool(d.get("xac_nhan_he_so")),
            }
        )
    trung = {
        x["ma_lo"] for x in sach if [y["ma_lo"] for y in sach].count(x["ma_lo"]) > 1
    }
    if trung:
        raise ValidationError(
            f"Số lô lặp trong phiếu: {', '.join(sorted(trung))} — gộp lại một dòng."
        )

    try:
        async with pool.acquire() as conn:
            cu = await _phieu_da_co(conn, identity, khoa)
            if cu is not None:
                return cu
            async with conn.transaction():
                phieu_id, ma = await _mo_phieu(
                    conn,
                    identity,
                    loai="NHAP",
                    khoa_gui=khoa,
                    nha_cung_cap=_chu(nha_cung_cap),
                    so_hoa_don=_chu(so_hoa_don, 100),
                    ngay_chung_tu=ngay,
                    ghi_chu=_chu(ghi_chu, 1000),
                )
                for stt, x in enumerate(sach, start=1):
                    don_vi = x["don_vi"] or await conn.fetchval(
                        "SELECT don_vi_ban FROM public.drug_catalog"
                        " WHERE clinic_id = $1::uuid AND id = $2::uuid",
                        identity.clinic_id,
                        x["drug_catalog_id"] or None,
                    )
                    if not don_vi:
                        raise ValidationError(f"Dòng {stt}: nhập đơn vị (viên, hộp…).")
                    try:
                        qd = await quy_doi_dong_nhap(
                            conn,
                            identity=identity,
                            drug_catalog_id=x["drug_catalog_id"],
                            so_luong=x["so_luong"],
                            unit=don_vi,
                            cost_price=x["gia"],
                            he_so=x["he_so"],
                            xac_nhan_he_so=x["xac_nhan_he_so"],
                        )
                        lo_id, txn_id = await nhap_vao_lo(
                            conn,
                            identity=identity,
                            drug_catalog_id=x["drug_catalog_id"],
                            so_luong=qd.so_luong,
                            batch_code=x["ma_lo"],
                            expiry_date=x["han"],
                            unit=qd.don_vi,
                            cost_price=qd.cost_price,
                            ly_do=" · ".join(
                                s for s in (f"Phiếu nhập {ma}", qd.ghi_chu) if s
                            ),
                            ref_type="phieu_kho",
                            ref_id=phieu_id,
                        )
                    except (NotFoundError, ConflictError, ValidationError) as exc:
                        raise type(exc)(f"Dòng {stt}: {exc.message}") from exc
                    goc = qd.goc
                    await conn.execute(
                        """
                        INSERT INTO phieu_kho_dong
                            (clinic_id, phieu_kho_id, loai, stt, drug_catalog_id,
                             drug_batch_id, so_luong, gia_nhap, inventory_txn_id,
                             so_luong_goc, don_vi_goc, he_so)
                        VALUES ($1::uuid, $2::uuid, 'NHAP', $3, $4::uuid, $5::uuid,
                                $6, $7, $8::uuid, $9, $10, $11)
                        """,
                        identity.clinic_id,
                        phieu_id,
                        stt,
                        x["drug_catalog_id"],
                        lo_id,
                        qd.so_luong,
                        qd.cost_price,
                        txn_id,
                        goc[0] if goc else None,
                        goc[1] if goc else None,
                        goc[2] if goc else None,
                    )
                await ghi_nhat_ky(
                    conn,
                    identity=identity,
                    event_type="pharmacy.phieu_nhap",
                    aggregate_type="phieu_kho",
                    aggregate_id=phieu_id,
                    payload={"ma_phieu": ma, "so_dong": len(sach)},
                )
    except asyncpg.UniqueViolationError as exc:
        # Hai lần bấm cùng khoá chạy song song: lần sau đâm UNIQUE khoá gửi →
        # trả phiếu của lần trước, không ghi gì thêm.
        if getattr(exc, "constraint_name", "") != "uq_phieu_kho_khoa":
            raise
        async with pool.acquire() as conn:
            cu = await _phieu_da_co(conn, identity, khoa)
        if cu is None:
            raise
        return cu
    return {
        "ok": True,
        "id": phieu_id,
        "ma_phieu": ma,
        "loai": "NHAP",
        "gui_lai": False,
    }


async def kiem_kho(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    ghi_chu: Any = None,
    dong: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phiếu kiểm kho: mỗi dòng (lô, số đếm thực tế). Máy chủ đọc tồn máy dưới
    khoá lô, ghi lệch; lệch ≠ 0 → một dòng ADJUST lý do "Kiểm kho <mã>"."""
    khoa = _khoa(khoa_gui)
    if not dong:
        raise ValidationError("Chọn ít nhất một lô để kiểm.")
    if len(dong) > PHIEU_TOI_DA_DONG:
        raise ValidationError(f"Một phiếu tối đa {PHIEU_TOI_DA_DONG} dòng.")
    sach: dict[str, Decimal] = {}
    for i, d in enumerate(dong, start=1):
        lo = str(d.get("drug_batch_id") or "").strip()
        if not lo:
            raise ValidationError(f"Dòng {i}: chưa chọn lô.")
        if lo in sach:
            raise ValidationError(f"Dòng {i}: lô này đã có trong phiếu.")
        sach[lo] = _so(d.get("thuc_te"), ten=f"Dòng {i}: số đếm thực tế", cho_0=True)

    ket_qua: list[dict[str, Any]] = []
    try:
        async with pool.acquire() as conn:
            cu = await _phieu_da_co(conn, identity, khoa)
            if cu is not None:
                return cu
            async with conn.transaction():
                phieu_id, ma = await _mo_phieu(
                    conn,
                    identity,
                    loai="KIEM",
                    khoa_gui=khoa,
                    ghi_chu=_chu(ghi_chu, 1000),
                )
                # Khoá lô theo thứ tự id — hai phiếu kiểm chồng lô không khoá chéo.
                # Chỉ lô của kho cơ sở đang làm: lô cơ sở khác = "không thấy".
                los = await conn.fetch(
                    """
                    SELECT id::text, drug_catalog_id::text, quantity_on_hand
                      FROM public.drug_batch
                     WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
                       AND location_id = $3::uuid
                     ORDER BY id
                     FOR UPDATE
                    """,
                    identity.clinic_id,
                    list(sach),
                    identity.location_id,
                )
                theo_id = {r["id"]: r for r in los}
                for stt, (lo_id, thuc_te) in enumerate(sach.items(), start=1):
                    ban_ghi = theo_id.get(lo_id)
                    if ban_ghi is None:
                        raise NotFoundError(
                            f"Dòng {stt}: không tìm thấy lô này trong kho cơ sở "
                            "đang làm."
                        )
                    ton_may = Decimal(str(ban_ghi["quantity_on_hand"]))
                    lech = thuc_te - ton_may
                    txn_id = None
                    if lech != 0:
                        txn_id = await PharmacyService._ghi_so_trong(
                            conn,
                            identity=identity,
                            drug_batch_id=lo_id,
                            txn_type=DIEU_CHINH,
                            quantity=lech,
                            reason=f"Kiểm kho {ma}",
                            ref_type="phieu_kho",
                            ref_id=phieu_id,
                        )
                    await conn.execute(
                        """
                        INSERT INTO phieu_kho_dong
                            (clinic_id, phieu_kho_id, loai, stt, drug_catalog_id,
                             drug_batch_id, ton_may, thuc_te, lech, inventory_txn_id)
                        VALUES ($1::uuid, $2::uuid, 'KIEM', $3, $4::uuid, $5::uuid,
                                $6, $7, $8, $9::uuid)
                        """,
                        identity.clinic_id,
                        phieu_id,
                        stt,
                        ban_ghi["drug_catalog_id"],
                        lo_id,
                        ton_may,
                        thuc_te,
                        lech,
                        txn_id,
                    )
                    ket_qua.append(
                        {
                            "drug_batch_id": lo_id,
                            "ton_may": ton_may,
                            "thuc_te": thuc_te,
                            "lech": lech,
                        }
                    )
                await ghi_nhat_ky(
                    conn,
                    identity=identity,
                    event_type="pharmacy.kiem_kho",
                    aggregate_type="phieu_kho",
                    aggregate_id=phieu_id,
                    payload={
                        "ma_phieu": ma,
                        "so_dong": len(sach),
                        "so_dong_lech": sum(1 for k in ket_qua if k["lech"] != 0),
                    },
                )
    except asyncpg.UniqueViolationError as exc:
        if getattr(exc, "constraint_name", "") != "uq_phieu_kho_khoa":
            raise
        async with pool.acquire() as conn:
            cu = await _phieu_da_co(conn, identity, khoa)
        if cu is None:
            raise
        return cu
    return {
        "ok": True,
        "id": phieu_id,
        "ma_phieu": ma,
        "loai": "KIEM",
        "gui_lai": False,
        "dong": ket_qua,
    }


# ── Tách KHO / QUẦY (G7, 14/10/2026) ─────────────────────────────────────


async def tach_kho_quay_dang_bat(pool: asyncpg.Pool, identity: StaffIdentity) -> bool:
    """Như `tach_kho_quay_bat` nhưng nhận pool — cho test và chỗ không có conn."""
    async with pool.acquire() as conn:
        return await tach_kho_quay_bat(conn, identity)


async def dat_tach_kho_quay(
    pool: asyncpg.Pool, *, identity: StaffIdentity, bat: bool
) -> dict[str, Any]:
    """Bật / tắt tách kho-quầy cho CƠ SỞ đang làm. Bật không đổi dữ liệu nào:
    lô hiện có đã là hàng QUẦY, quầy bán bằng đúng tồn đang có; từ đó nhập đi
    vào KHO. Tắt chỉ khi KHO đã hết hàng — không để thuốc nằm ở nơi bán không
    tới."""
    async with pool.acquire() as conn, conn.transaction():
        cu = await conn.fetchval(
            "SELECT tach_kho_quay FROM public.clinic_location"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid FOR UPDATE",
            identity.location_id,
            identity.clinic_id,
        )
        if cu is None:
            raise NotFoundError("Không xác định được cơ sở đang làm — đăng nhập lại.")
        if bool(cu) == bat:
            return {"ok": True, "tach_kho_quay": bat, "doi": False}
        if not bat:
            con = await conn.fetchrow(
                "SELECT count(*) AS lo, coalesce(sum(quantity_on_hand), 0) AS ton"
                " FROM public.drug_batch WHERE clinic_id = $1::uuid"
                " AND location_id = $2::uuid AND noi_chua = 'KHO'"
                " AND quantity_on_hand > 0",
                identity.clinic_id,
                identity.location_id,
            )
            if con and con["lo"] > 0:
                raise ConflictError(
                    f"Kho còn {con['lo']} lô có hàng — chuyển hết sang quầy rồi mới "
                    "tắt tách kho / quầy."
                )
        await conn.execute(
            "UPDATE public.clinic_location SET tach_kho_quay = $3"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            identity.location_id,
            identity.clinic_id,
            bat,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.tach_kho_quay_doi",
            aggregate_type="clinic_location",
            aggregate_id=identity.location_id,
            payload={"before": bool(cu), "after": bat},
        )
    return {"ok": True, "tach_kho_quay": bat, "doi": True}


_NOI = {"KHO_QUAY": ("KHO", "QUAY"), "QUAY_KHO": ("QUAY", "KHO")}
_TEN_NOI = {"KHO": "kho", "QUAY": "quầy"}


async def _chuyen_cac_dong(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    huong: str,
    dong: list[tuple[str, Decimal, str | None]],
    phieu_id: str,
    ma: str,
    ly_do: str,
) -> list[dict[str, Any]]:
    """Ghi các dòng chuyển (nguồn, số lượng, đích hoặc None = hàng cùng lô ở nơi
    kia, tạo nếu chưa có) vào phiếu `phieu_id` — trong giao dịch của người gọi."""
    noi_nguon, noi_dich = _NOI[huong]
    # Khoá MỌI hàng của các lô liên quan một lượt, theo id: hai người chuyển
    # ngược chiều cùng một lô không khoá chéo nhau.
    ma_lo = await conn.fetch(
        "SELECT DISTINCT batch_code FROM public.drug_batch"
        " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
        " AND id = ANY($3::uuid[])",
        identity.clinic_id,
        identity.location_id,
        [d[0] for d in dong],
    )
    if len(ma_lo) == 0:
        raise NotFoundError("Không tìm thấy lô này trong kho của cơ sở đang làm.")
    hang = {
        r["id"]: r
        for r in await conn.fetch(
            """
            SELECT id::text, drug_catalog_id::text, batch_code, expiry_date, unit,
                   quantity_on_hand, noi_chua, ma_tem, cost_price, received_at,
                   CASE WHEN noi_chua = 'QUAY'
                        THEN public.drug_batch_kha_dung(clinic_id, id)
                        ELSE quantity_on_hand END AS kha_dung
              FROM public.drug_batch
             WHERE clinic_id = $1::uuid AND location_id = $2::uuid
               AND batch_code = ANY($3::text[])
             ORDER BY id
             FOR UPDATE
            """,
            identity.clinic_id,
            identity.location_id,
            [r["batch_code"] for r in ma_lo],
        )
    }
    ra: list[dict[str, Any]] = []
    for stt, (nguon_id, luong, dich_id) in enumerate(dong, start=1):
        nguon = hang.get(nguon_id)
        if nguon is None:
            raise NotFoundError(
                f"Dòng {stt}: không tìm thấy lô này trong kho của cơ sở đang làm."
            )
        if nguon["noi_chua"] != noi_nguon:
            raise ValidationError(
                f"Dòng {stt}: chuyển từ {noi_nguon} phải chọn hàng đang ở {noi_nguon}."
            )
        if (
            noi_dich == "QUAY"
            and nguon["expiry_date"] is not None
            and nguon["expiry_date"] < hom_nay_vn()
        ):
            raise ConflictError(
                f"Dòng {stt}: lô {nguon['batch_code']} đã hết hạn — không chuyển ra "
                "quầy. Huỷ lô hết hạn ở Tồn theo lô."
            )
        kha = Decimal(str(nguon["kha_dung"] or 0))
        if luong > kha:
            raise ConflictError(
                f"Dòng {stt}: {_TEN_NOI[noi_nguon]} chỉ còn {_so_chu_so(kha)} "
                f"{nguon['unit']} có thể rút của lô {nguon['batch_code']} — không đủ "
                f"{_so_chu_so(luong)}."
                + (
                    " (phần đã bán chưa giao ở quầy không rút lại được)"
                    if noi_nguon == "QUAY"
                    else ""
                )
            )
        dich = hang.get(dich_id) if dich_id else None
        if dich is None:
            dich = next(
                (
                    h
                    for h in hang.values()
                    if h["batch_code"] == nguon["batch_code"]
                    and h["noi_chua"] == noi_dich
                ),
                None,
            )
        if dich is None:
            moi = await conn.fetchval(
                """
                INSERT INTO public.drug_batch
                    (clinic_id, location_id, drug_catalog_id, batch_code, expiry_date,
                     quantity_on_hand, unit, cost_price, received_at, noi_chua, ma_tem)
                VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, 0, $6, $7, $8, $9, $10)
                RETURNING id::text
                """,
                identity.clinic_id,
                identity.location_id,
                nguon["drug_catalog_id"],
                nguon["batch_code"],
                nguon["expiry_date"],
                nguon["unit"],
                nguon["cost_price"],
                nguon["received_at"],
                noi_dich,
                nguon["ma_tem"],
            )
            dich_ra = str(moi)
        else:
            dich_ra = dich["id"]
        txn_ra = await PharmacyService._ghi_so_trong(
            conn,
            identity=identity,
            drug_batch_id=nguon_id,
            txn_type="CHUYEN_RA",
            quantity=-luong,
            reason=ly_do or f"Chuyển kho {ma}",
            ref_type="phieu_kho",
            ref_id=phieu_id,
        )
        txn_vao = await PharmacyService._ghi_so_trong(
            conn,
            identity=identity,
            drug_batch_id=dich_ra,
            txn_type="CHUYEN_VAO",
            quantity=luong,
            reason=ly_do or f"Chuyển kho {ma}",
            ref_type="phieu_kho",
            ref_id=phieu_id,
        )
        await conn.execute(
            """
            INSERT INTO phieu_kho_dong
                (clinic_id, phieu_kho_id, loai, stt, drug_catalog_id, drug_batch_id,
                 so_luong, inventory_txn_id, drug_batch_nguon_id,
                 inventory_txn_nguon_id)
            VALUES ($1::uuid, $2::uuid, 'CHUYEN', $3, $4::uuid, $5::uuid, $6,
                    $7::uuid, $8::uuid, $9::uuid)
            """,
            identity.clinic_id,
            phieu_id,
            stt,
            nguon["drug_catalog_id"],
            dich_ra,
            luong,
            txn_vao,
            nguon_id,
            txn_ra,
        )
        ra.append(
            {
                "drug_batch_nguon_id": nguon_id,
                "drug_batch_dich_id": dich_ra,
                "so_luong": luong,
            }
        )
    return ra


def _so_chu_so(v: Decimal) -> str:
    return f"{v.normalize():f}"


async def _gui_lai_hoac(
    pool: asyncpg.Pool, identity: StaffIdentity, khoa: str
) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        return await _phieu_da_co(conn, identity, khoa)


async def chuyen_kho(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    huong: str,
    ly_do: Any = None,
    dong: list[dict[str, Any]],
) -> dict[str, Any]:
    """Phiếu chuyển KHO → QUẦY (hoặc QUẦY → KHO): hai dòng sổ đối ứng cho mỗi
    dòng, MỘT giao dịch — dòng nào hỏng thì cả phiếu không vào. Ai làm, lúc nào,
    lý do (không bắt điền) nằm trên phiếu; hoàn tác bằng `hoan_tac_chuyen`."""
    khoa = _khoa(khoa_gui)
    if huong not in _NOI:
        raise ValidationError("Chuyển theo chiều KHO → QUẦY hoặc QUẦY → KHO.")
    if not dong:
        raise ValidationError("Chọn ít nhất một lô để chuyển.")
    if len(dong) > PHIEU_TOI_DA_DONG:
        raise ValidationError(f"Một phiếu tối đa {PHIEU_TOI_DA_DONG} dòng.")
    sach: list[tuple[str, Decimal, str | None]] = []
    thay: set[str] = set()
    for i, d in enumerate(dong, start=1):
        lo = str(d.get("drug_batch_id") or "").strip()
        if not lo:
            raise ValidationError(f"Dòng {i}: chưa chọn lô.")
        if lo in thay:
            raise ValidationError(f"Dòng {i}: lô này đã có trong phiếu.")
        thay.add(lo)
        sach.append(
            (lo, _so(d.get("so_luong"), ten=f"Dòng {i}: số lượng chuyển"), None)
        )
    ly = _chu(ly_do, 1000)
    try:
        cu = await _gui_lai_hoac(pool, identity, khoa)
        if cu is not None:
            return cu
        async with pool.acquire() as conn, conn.transaction():
            if not await tach_kho_quay_bat(conn, identity):
                raise ConflictError(
                    "Cơ sở này chưa bật tách kho / quầy — bật ở cấu hình Kho thuốc "
                    "trước khi chuyển."
                )
            phieu_id, ma = await _mo_phieu(
                conn, identity, loai="CHUYEN", khoa_gui=khoa, huong=huong, ly_do=ly
            )
            ra = await _chuyen_cac_dong(
                conn,
                identity,
                huong=huong,
                dong=sach,
                phieu_id=phieu_id,
                ma=ma,
                ly_do=ly or "",
            )
            await ghi_nhat_ky(
                conn,
                identity=identity,
                event_type="pharmacy.chuyen_kho",
                aggregate_type="phieu_kho",
                aggregate_id=phieu_id,
                payload={"ma_phieu": ma, "huong": huong, "so_dong": len(ra)},
            )
    except asyncpg.UniqueViolationError as exc:
        if getattr(exc, "constraint_name", "") != "uq_phieu_kho_khoa":
            raise
        cu = await _gui_lai_hoac(pool, identity, khoa)
        if cu is None:
            raise
        return cu
    return {
        "ok": True,
        "id": phieu_id,
        "ma_phieu": ma,
        "loai": "CHUYEN",
        "gui_lai": False,
        "dong": ra,
    }


async def hoan_tac_chuyen(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    phieu_id: str,
) -> dict[str, Any]:
    """Hoàn tác một phiếu chuyển bằng phiếu chuyển NGƯỢC (sổ chỉ thêm). Mỗi phiếu
    hoàn tác được MỘT lần (ép ở Postgres); quầy đã bán bớt thì rút lại phần còn
    được, hết thì nói rõ không rút được."""
    khoa = _khoa(khoa_gui)
    try:
        cu = await _gui_lai_hoac(pool, identity, khoa)
        if cu is not None:
            return cu
        async with pool.acquire() as conn, conn.transaction():
            goc = await conn.fetchrow(
                "SELECT id::text, ma_phieu, huong FROM public.phieu_kho"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                " AND location_id = $3::uuid AND loai = 'CHUYEN' FOR UPDATE",
                phieu_id,
                identity.clinic_id,
                identity.location_id,
            )
            if goc is None:
                raise NotFoundError("Không tìm thấy phiếu chuyển kho này.")
            if await conn.fetchval(
                "SELECT 1 FROM public.phieu_kho WHERE hoan_tac_cua = $1::uuid",
                phieu_id,
            ):
                raise ConflictError(f"Phiếu {goc['ma_phieu']} đã hoàn tác rồi.")
            if not await tach_kho_quay_bat(conn, identity):
                raise ConflictError(
                    "Cơ sở này chưa bật tách kho / quầy — không hoàn tác được."
                )
            dong = [
                (r["dich"], Decimal(str(r["so_luong"])), r["nguon"])
                for r in await conn.fetch(
                    "SELECT drug_batch_id::text AS dich,"
                    " drug_batch_nguon_id::text AS nguon, so_luong"
                    " FROM public.phieu_kho_dong WHERE phieu_kho_id = $1::uuid"
                    " ORDER BY stt",
                    phieu_id,
                )
            ]
            nguoc = "QUAY_KHO" if goc["huong"] == "KHO_QUAY" else "KHO_QUAY"
            hoan_id, ma = await _mo_phieu(
                conn,
                identity,
                loai="CHUYEN",
                khoa_gui=khoa,
                huong=nguoc,
                ly_do=f"Hoàn tác phiếu {goc['ma_phieu']}",
                hoan_tac_cua=phieu_id,
            )
            try:
                ra = await _chuyen_cac_dong(
                    conn,
                    identity,
                    huong=nguoc,
                    dong=dong,
                    phieu_id=hoan_id,
                    ma=ma,
                    ly_do=f"Hoàn tác phiếu {goc['ma_phieu']}",
                )
            except ConflictError as exc:
                raise ConflictError(f"Không hoàn tác được: {exc.message}") from exc
            await ghi_nhat_ky(
                conn,
                identity=identity,
                event_type="pharmacy.chuyen_kho_hoan_tac",
                aggregate_type="phieu_kho",
                aggregate_id=hoan_id,
                payload={"ma_phieu": ma, "hoan_tac_cua": goc["ma_phieu"]},
            )
    except asyncpg.UniqueViolationError as exc:
        ten = getattr(exc, "constraint_name", "")
        if ten == "uq_phieu_kho_hoan_tac_cua":
            raise ConflictError("Phiếu này đã hoàn tác rồi.") from exc
        if ten != "uq_phieu_kho_khoa":
            raise
        cu = await _gui_lai_hoac(pool, identity, khoa)
        if cu is None:
            raise
        return cu
    return {
        "ok": True,
        "id": hoan_id,
        "ma_phieu": ma,
        "loai": "CHUYEN",
        "gui_lai": False,
        "dong": ra,
    }
