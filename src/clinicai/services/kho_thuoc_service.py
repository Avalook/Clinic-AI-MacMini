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
)

#: Loại dòng sổ đổi tồn VẬT LÝ (khác SALE / SALE_REVERSAL).
LOAI_VAT_LY = ("RECEIVE", "DISPENSE", "ADJUST", "DISCARD", "RETURN_RECEIVED")

#: Khoảng XNT dài nhất (ngày) — một năm là đủ cho báo cáo quý / năm.
XNT_TOI_DA_NGAY = 366

#: Số dòng tối đa một phiếu.
PHIEU_TOI_DA_DONG = 200

_TIEN_TO = {"NHAP": "PN", "KIEM": "KK"}


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
                                  AND b.drug_catalog_id = c.id
                                GROUP BY lower(btrim(b.unit))
                               HAVING sum(b.quantity_on_hand) <> 0) dv
                   ), '[]'::jsonb) AS ton_theo_don_vi
              FROM public.drug_catalog c
             WHERE c.clinic_id = $1::uuid AND c.id = $2::uuid
            """,
            identity.clinic_id,
            drug_catalog_id,
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
                 WHERE b.clinic_id = $1::uuid
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
        )
    return {"tu": a.isoformat(), "den": b.isoformat(), "dong": [dict(r) for r in rows]}


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
                   coalesce((
                       SELECT jsonb_agg(jsonb_build_object(
                                  'stt', d.stt, 'ten', c.name_raw,
                                  'so_lo', b.batch_code, 'han_dung', b.expiry_date,
                                  'don_vi', b.unit, 'so_luong', d.so_luong,
                                  'gia_nhap', d.gia_nhap, 'ton_may', d.ton_may,
                                  'thuc_te', d.thuc_te, 'lech', d.lech)
                              ORDER BY d.stt)
                         FROM public.phieu_kho_dong d
                         JOIN public.drug_catalog c ON c.id = d.drug_catalog_id
                         JOIN public.drug_batch b ON b.id = d.drug_batch_id
                        WHERE d.clinic_id = pk.clinic_id AND d.phieu_kho_id = pk.id
                   ), '[]'::jsonb) AS dong
              FROM public.phieu_kho pk
              LEFT JOIN public.staff s ON s.id = pk.tao_boi
             WHERE pk.clinic_id = $1::uuid AND pk.loai = $2
             ORDER BY pk.tao_luc DESC
             LIMIT 100
            """,
            identity.clinic_id,
            loai,
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
) -> tuple[str, str]:
    """Tạo đầu phiếu với mã kế tiếp. Khoá tư vấn theo (phòng khám, loại) để hai
    phiếu cùng lúc không tranh một mã; UNIQUE (clinic_id, ma_phieu) là chốt cuối."""
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtext($1))",
        f"phieu_kho:{identity.clinic_id}:{loai}",
    )
    so = await conn.fetchval(
        "SELECT count(*) FROM public.phieu_kho"
        " WHERE clinic_id = $1::uuid AND loai = $2",
        identity.clinic_id,
        loai,
    )
    ma = f"{_TIEN_TO[loai]}{int(so) + 1:06d}"
    phieu_id = await conn.fetchval(
        """
        INSERT INTO phieu_kho
            (clinic_id, loai, ma_phieu, nha_cung_cap, so_hoa_don, ngay_chung_tu,
             ghi_chu, tao_boi, khoa_gui)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::uuid, $9)
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
                        lo_id, txn_id = await nhap_vao_lo(
                            conn,
                            identity=identity,
                            drug_catalog_id=x["drug_catalog_id"],
                            so_luong=x["so_luong"],
                            batch_code=x["ma_lo"],
                            expiry_date=x["han"],
                            unit=don_vi,
                            cost_price=x["gia"],
                            ly_do=f"Phiếu nhập {ma}",
                            ref_type="phieu_kho",
                            ref_id=phieu_id,
                        )
                    except (NotFoundError, ConflictError) as exc:
                        raise type(exc)(f"Dòng {stt}: {exc.message}") from exc
                    await conn.execute(
                        """
                        INSERT INTO phieu_kho_dong
                            (clinic_id, phieu_kho_id, loai, stt, drug_catalog_id,
                             drug_batch_id, so_luong, gia_nhap, inventory_txn_id)
                        VALUES ($1::uuid, $2::uuid, 'NHAP', $3, $4::uuid, $5::uuid,
                                $6, $7, $8::uuid)
                        """,
                        identity.clinic_id,
                        phieu_id,
                        stt,
                        x["drug_catalog_id"],
                        lo_id,
                        x["so_luong"],
                        x["gia"],
                        txn_id,
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
                los = await conn.fetch(
                    """
                    SELECT id::text, drug_catalog_id::text, quantity_on_hand
                      FROM public.drug_batch
                     WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
                     ORDER BY id
                     FOR UPDATE
                    """,
                    identity.clinic_id,
                    list(sach),
                )
                theo_id = {r["id"]: r for r in los}
                for stt, (lo_id, thuc_te) in enumerate(sach.items(), start=1):
                    ban_ghi = theo_id.get(lo_id)
                    if ban_ghi is None:
                        raise NotFoundError(
                            f"Dòng {stt}: không tìm thấy lô này trong kho."
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
