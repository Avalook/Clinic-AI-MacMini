"""Kiểm kê đầu / cuối ca ở QUẦY + cột tồn của "Báo cáo hàng hoá" (G6, 14/10/2026).

Đứng trên sổ kho `inventory_txn` (chỉ-thêm, trigger cộng tồn) và trên G7 (tách
KHO / QUẦY). Bốn điều Tuyền chốt (kế hoạch Q9, 2d, 2d+):

* Kiểm kê là ĐẾM tồn THẬT trên kệ QUẦY (thuốc đã thu tiền mà chưa giao vẫn nằm
  trên kệ → vẫn đếm). Phiếu NHÁP → CHỐT; kiểm một phần / đột xuất được; quên
  đầu ca chỉ NHẮC, không chặn bán.
* CHỐT ghi tồn máy ở quầy tại giờ chốt và lệch = đếm − tồn máy. KHÔNG tự sửa tồn:
  "Điều chỉnh theo kiểm kê" là bước riêng ghi `ADJUST` (có lý do), hoàn tác được.
* Lệch → chuông cho người nhận do quản lý chỉnh (`day_nhan_thong_bao`).
* Cột báo cáo: Tồn đầu · Nhập trong ca · SL bán (= số GIAO) · SL trả · Tồn cuối
  ca (sổ) · Kiểm kê · Lệch, với Tồn cuối = Tồn đầu + Nhập − Bán + Trả + Khác
  (Khác = điều chỉnh, huỷ, chuyển ra kho) và Lệch = Kiểm kê − Tồn cuối ca.

Số lượng chỉ tính từ sổ kho, theo (thuốc, đơn vị lô) — không cộng hộp với viên.
Hàm thuần (`khung_moc`, `tinh_xnt_dong`, `ghep_ton_ca`) tách riêng để test.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ, doc_ngay_xem, hom_nay_vn
from clinicai.core.shifts import CAC_CA, ca_cua_phut, ca_tu_settings, khung_chot_ca
from clinicai.events import emit_event, nguoi
from clinicai.events.catalogue import KiemKeLech
from clinicai.services.pharmacy_service import (
    DIEU_CHINH,
    PharmacyService,
    ghi_nhat_ky,
)

#: Loại dòng sổ đổi tồn VẬT LÝ (giống `kho_thuoc_service.LOAI_VAT_LY`; lặp ở đây
#: để file này không phụ thuộc vòng vào kho_thuoc_service).
_LOAI_VAT_LY = (
    "RECEIVE",
    "DISPENSE",
    "ADJUST",
    "DISCARD",
    "RETURN_RECEIVED",
    "CHUYEN_RA",
    "CHUYEN_VAO",
)

LOAI_PHIEU = ("DAU", "CUOI", "DOT_XUAT")
THU_TU_CA = {"SANG": 1, "CHIEU": 2, "TOI": 3}

#: Số dòng đếm tối đa một lệnh lưu.
DONG_TOI_DA = 500
#: Số đếm lớn nhất nhận vào (rác kiểu 1e30 bị từ chối, không ghi).
SO_TOI_DA = Decimal("1000000000")
#: Ngày phiếu cho phép: lùi tối đa một năm, tới hết ngày mai.
NGAY_LUI_TOI_DA = 366

Q3 = Decimal("0.001")


# ── Hàm thuần ────────────────────────────────────────────────────────────


def khung_moc(ngay: date, ca: Any, settings: Any) -> tuple[datetime, datetime] | None:
    """Ca của MỘT ngày → (từ lúc, tới lúc) giờ VN, nửa mở [từ, tới). Ca rỗng /
    rác → ``None``, không ném. Ba ca khít nhau phủ trọn ngày; ca TỐI kết thúc
    24:00 (= 00:00 hôm sau)."""
    ma = str(ca or "").strip().upper()
    if ma not in CAC_CA or not isinstance(ngay, date):
        return None
    phut = khung_chot_ca(ma, ca_tu_settings(settings))
    if phut is None:
        return None
    goc = datetime(ngay.year, ngay.month, ngay.day, tzinfo=CLINIC_TZ)
    return goc + timedelta(minutes=phut[0]), goc + timedelta(minutes=phut[1])


def ca_cua_gio(luc: datetime, settings: Any) -> str:
    """Ca chứa một mốc giờ (giờ VN)."""
    v = luc.astimezone(CLINIC_TZ)
    return ca_cua_phut(v.hour * 60 + v.minute, ca_tu_settings(settings))


def so_hoac_none(v: Any) -> Decimal | None:
    """Số đếm người gõ → ``Decimal`` làm tròn 3 số lẻ, hoặc ``None`` nếu rỗng /
    rác / âm / quá lớn / không hữu hạn. Không ném."""
    if v is None or isinstance(v, bool):
        return None
    try:
        d = Decimal(str(v).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not d.is_finite() or d < 0 or d > SO_TOI_DA:
        return None
    return d.quantize(Q3)


def tinh_xnt_dong(
    *,
    ton_dau: Decimal,
    nhap: Decimal,
    ban: Decimal,
    tra: Decimal,
    khac: Decimal,
    kiem_ke: Decimal | None,
) -> dict[str, Decimal | None]:
    """Tồn cuối ca (theo sổ) = đầu + nhập − bán + trả + khác; lệch = kiểm kê − tồn
    cuối (``None`` khi chưa kiểm — chưa đủ dữ liệu, không suy ra)."""
    ton_cuoi = ton_dau + nhap - ban + tra + khac
    return {
        "ton_dau": ton_dau,
        "nhap": nhap,
        "sl_ban": ban,
        "sl_tra": tra,
        "khac": khac,
        "ton_cuoi": ton_cuoi,
        "kiem_ke": kiem_ke,
        "lech": None if kiem_ke is None else kiem_ke - ton_cuoi,
    }


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def ghep_ton_ca(
    thuoc: dict[str, Any],
    xnt: list[dict[str, Any]],
    kiem: dict[tuple[str, str, str], dict[str, Any]],
    chua_giao: dict[tuple[str, str], Decimal],
    giao_chua_gan_lo: dict[str, Decimal],
    ten_thuoc: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Gắn khối ``kho`` vào từng dòng THUỐC của báo cáo hàng hoá (khoá ``khoa`` =
    drug_catalog_id). Thuốc có chuyển động kho / tồn / kiểm kê mà không bán trong
    khoảng vẫn hiện (doanh thu 0) — tồn kho là việc của báo cáo này. Không đổi
    bất kỳ số tiền hay số lượng thu cũ nào. Thuần."""
    theo_thuoc: dict[str, list[dict[str, Any]]] = {}
    for r in xnt:
        dv = r["don_vi"]
        k_dau = kiem.get((r["drug_catalog_id"], dv, "DAU"))
        k_cuoi = kiem.get((r["drug_catalog_id"], dv, "CUOI"))
        t = tinh_xnt_dong(
            ton_dau=r["ton_dau"],
            nhap=r["nhap"],
            ban=r["ban"],
            tra=r["tra"],
            khac=r["khac"],
            kiem_ke=None if k_cuoi is None else k_cuoi["dem"],
        )
        theo_thuoc.setdefault(r["drug_catalog_id"], []).append(
            {
                "don_vi": r["don_vi_hien"],
                **{k: _f(v) for k, v in t.items()},
                # Đã thu chưa giao: còn nằm trên kệ, đã có tiền (không phải lệch).
                "da_thu_chua_giao": _f(
                    chua_giao.get((r["drug_catalog_id"], dv), Decimal(0))
                ),
                # Kiểm đầu ca lệch so với tồn đầu theo sổ (check chéo với Excel).
                "kiem_dau": None if k_dau is None else _f(k_dau["dem"]),
                "lech_dau": (
                    None if k_dau is None else _f(k_dau["dem"] - r["ton_dau"])
                ),
                "phieu_dau_id": None if k_dau is None else k_dau["phieu_id"],
                "phieu_cuoi_id": None if k_cuoi is None else k_cuoi["phieu_id"],
            }
        )
    # Kiểm kê của (thuốc, đơn vị) không có chuyển động / tồn nào vẫn phải hiện.
    for (drug, dv, loai), k in kiem.items():
        if loai != "CUOI":
            continue
        if any(x["don_vi"] == k["don_vi_hien"] for x in theo_thuoc.get(drug, [])):
            continue
        if any(r["drug_catalog_id"] == drug and r["don_vi"] == dv for r in xnt):
            continue
        t = tinh_xnt_dong(
            ton_dau=Decimal(0),
            nhap=Decimal(0),
            ban=Decimal(0),
            tra=Decimal(0),
            khac=Decimal(0),
            kiem_ke=k["dem"],
        )
        theo_thuoc.setdefault(drug, []).append(
            {
                "don_vi": k["don_vi_hien"],
                **{kk: _f(v) for kk, v in t.items()},
                "da_thu_chua_giao": 0.0,
                "kiem_dau": None,
                "lech_dau": None,
                "phieu_dau_id": None,
                "phieu_cuoi_id": k["phieu_id"],
            }
        )

    dong = thuoc.get("dong", [])
    co = {d.get("khoa") for d in dong}
    for d in dong:
        d["kho"] = {
            "theo_don_vi": theo_thuoc.get(str(d.get("khoa")), []),
            "giao_chua_gan_lo": _f(giao_chua_gan_lo.get(str(d.get("khoa")))),
        }
    for drug, ds in theo_thuoc.items():
        if drug in co:
            continue
        if not any(
            x["ton_dau"]
            or x["nhap"]
            or x["sl_ban"]
            or x["sl_tra"]
            or x["khac"]
            or x["ton_cuoi"]
            or x["kiem_ke"] is not None
            for x in ds
        ):
            continue
        ten = ten_thuoc.get(drug, {})
        dong.append(
            {
                "khoa": drug,
                "ma": ten.get("ma_hang"),
                "ten": ten.get("ten") or "Không tên",
                "don_vi": ten.get("don_vi_ban"),
                "sl_ban": 0.0,
                "doanh_thu": 0,
                "sl_tra": 0.0,
                "gia_tri_tra": 0,
                "doanh_thu_thuan": 0,
                "kho": {
                    "theo_don_vi": ds,
                    "giao_chua_gan_lo": _f(giao_chua_gan_lo.get(drug)),
                },
            }
        )
    thuoc["co_ton"] = True
    return thuoc


# ── Đọc ──────────────────────────────────────────────────────────────────


async def xnt_theo_ca(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    location_id: str | None,
    tu: datetime,
    den: datetime,
) -> list[dict[str, Any]]:
    """Tồn đầu / nhập / bán (GIAO) / trả / khác / tồn cuối của QUẦY trong [tu, den),
    mỗi (thuốc, đơn vị lô) một dòng. Tồn tại mốc T = tồn hiện tại − tổng dòng sổ
    vật lý từ T trở đi, nên đúng cả khi lô có tồn khởi điểm không qua sổ.
    `location_id` rỗng = mọi cơ sở của phòng khám. Chưa tách kho/quầy thì mọi lô
    đều ở QUẦY (mặc định cột `noi_chua`) — số cũ không đổi."""
    rows = await conn.fetch(
        """
        WITH so AS (
            SELECT t.drug_batch_id,
                   sum(t.quantity) AS tu_dau,
                   sum(t.quantity) FILTER (WHERE t.performed_at >= $4) AS tu_cuoi,
                   sum(t.quantity) FILTER (WHERE t.performed_at < $4
                       AND t.txn_type IN ('RECEIVE', 'CHUYEN_VAO')) AS nhap,
                   sum(-t.quantity) FILTER (WHERE t.performed_at < $4
                       AND t.txn_type = 'DISPENSE') AS ban,
                   sum(t.quantity) FILTER (WHERE t.performed_at < $4
                       AND t.txn_type = 'RETURN_RECEIVED') AS tra,
                   sum(t.quantity) FILTER (WHERE t.performed_at < $4
                       AND t.txn_type IN ('ADJUST', 'DISCARD', 'CHUYEN_RA')) AS khac
              FROM public.inventory_txn t
             WHERE t.clinic_id = $1::uuid AND t.performed_at >= $3
               AND t.txn_type = ANY($5::text[])
             GROUP BY t.drug_batch_id
        )
        SELECT b.drug_catalog_id::text AS drug_catalog_id,
               lower(btrim(b.unit)) AS don_vi, min(b.unit) AS don_vi_hien,
               coalesce(sum(b.quantity_on_hand - coalesce(so.tu_dau, 0)), 0) AS ton_dau,
               coalesce(sum(so.nhap), 0) AS nhap,
               coalesce(sum(so.ban), 0) AS ban,
               coalesce(sum(so.tra), 0) AS tra,
               coalesce(sum(so.khac), 0) AS khac,
               coalesce(sum(b.quantity_on_hand - coalesce(so.tu_cuoi, 0)), 0)
                   AS ton_cuoi
          FROM public.drug_batch b
          LEFT JOIN so ON so.drug_batch_id = b.id
         WHERE b.clinic_id = $1::uuid AND b.noi_chua = 'QUAY'
           AND ($2::uuid IS NULL OR b.location_id = $2::uuid)
         GROUP BY b.drug_catalog_id, lower(btrim(b.unit))
        HAVING coalesce(sum(abs(b.quantity_on_hand - coalesce(so.tu_dau, 0))
                          + abs(b.quantity_on_hand - coalesce(so.tu_cuoi, 0))
                          + abs(coalesce(so.nhap, 0)) + abs(coalesce(so.ban, 0))
                          + abs(coalesce(so.tra, 0)) + abs(coalesce(so.khac, 0))),
                        0) <> 0
        """,
        clinic_id,
        location_id,
        tu,
        den,
        list(_LOAI_VAT_LY),
    )
    return [dict(r) for r in rows]


async def kiem_trong_khoang(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    location_id: str | None,
    tu_ngay: date,
    den_ngay: date,
    ca: str | None = None,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    """Số đếm ĐÃ CHỐT trong [tu_ngay, den_ngay]: phiếu DAU sớm nhất và phiếu CUOI
    muộn nhất (mỗi cơ sở một phiếu mỗi loại; nhiều cơ sở thì cộng). Khoá
    (thuốc, đơn vị, 'DAU'|'CUOI'). Thiếu phiếu = không có khoá → "chưa kiểm"."""
    rows = await conn.fetch(
        """
        WITH ch AS (
            SELECT k.id, k.location_id, k.loai, k.ngay, k.ca,
                   row_number() OVER (
                       PARTITION BY k.location_id, k.loai
                       ORDER BY CASE WHEN k.loai = 'DAU' THEN 1 ELSE -1 END
                                * (k.ngay - date '2020-01-01') * 10
                                + CASE WHEN k.loai = 'DAU' THEN 1 ELSE -1 END
                                * (CASE k.ca WHEN 'SANG' THEN 1 WHEN 'CHIEU' THEN 2
                                             ELSE 3 END)) AS thu_tu
              FROM public.kiem_ke_ca k
             WHERE k.clinic_id = $1::uuid AND k.trang_thai = 'CHOT'
               AND k.loai IN ('DAU', 'CUOI')
               AND k.ngay BETWEEN $3 AND $4
               AND ($2::uuid IS NULL OR k.location_id = $2::uuid)
               AND ($5::text IS NULL OR k.ca = $5)
        )
        SELECT d.drug_catalog_id::text AS drug_catalog_id, d.don_vi,
               ch.loai, sum(d.dem) AS dem, min(ch.id::text) AS phieu_id
          FROM ch
          JOIN public.kiem_ke_ca_dong d
            ON d.kiem_ke_ca_id = ch.id AND d.clinic_id = $1::uuid
         WHERE ch.thu_tu = 1
         GROUP BY d.drug_catalog_id, d.don_vi, ch.loai
        """,
        clinic_id,
        location_id,
        tu_ngay,
        den_ngay,
        ca,
    )
    kq: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in rows:
        kq[(r["drug_catalog_id"], r["don_vi"], r["loai"])] = {
            "dem": r["dem"],
            "phieu_id": r["phieu_id"],
            "don_vi_hien": r["don_vi"],
        }
    return kq


async def da_thu_chua_giao(
    conn: asyncpg.Connection, *, clinic_id: str, location_id: str | None
) -> dict[tuple[str, str], Decimal]:
    """Thuốc ĐÃ BÁN (SALE chưa đảo) mà CHƯA GIAO, theo (thuốc, đơn vị) ở QUẦY — hiện
    tại, không theo ca. Vẫn nằm trên kệ nên vẫn đếm; đây là chỗ giải thích vì sao
    doanh thu (theo tiền thu) khác SL bán (theo số giao)."""
    rows = await conn.fetch(
        """
        SELECT b.drug_catalog_id::text AS drug_catalog_id,
               lower(btrim(b.unit)) AS don_vi,
               sum(greatest(-s.quantity - coalesce((
                   SELECT -sum(d.quantity) FROM public.inventory_txn d
                    WHERE d.txn_type = 'DISPENSE' AND d.allocation_id = s.allocation_id
                      AND d.clinic_id = s.clinic_id), 0), 0)) AS chua_giao
          FROM public.inventory_txn s
          JOIN public.drug_batch b ON b.id = s.drug_batch_id
         WHERE s.clinic_id = $1::uuid AND s.txn_type = 'SALE'
           AND s.allocation_id IS NOT NULL AND b.noi_chua = 'QUAY'
           AND ($2::uuid IS NULL OR b.location_id = $2::uuid)
           AND NOT EXISTS (SELECT 1 FROM public.inventory_txn r
                            WHERE r.txn_type = 'SALE_REVERSAL'
                              AND r.reverses_txn_id = s.id)
         GROUP BY b.drug_catalog_id, lower(btrim(b.unit))
        HAVING sum(greatest(-s.quantity - coalesce((
                   SELECT -sum(d.quantity) FROM public.inventory_txn d
                    WHERE d.txn_type = 'DISPENSE' AND d.allocation_id = s.allocation_id
                      AND d.clinic_id = s.clinic_id), 0), 0)) > 0
        """,
        clinic_id,
        location_id,
    )
    return {(r["drug_catalog_id"], r["don_vi"]): r["chua_giao"] for r in rows}


async def giao_chua_gan_lo_theo_thuoc(
    conn: asyncpg.Connection, *, clinic_id: str, location_id: str | None
) -> dict[str, Decimal]:
    """Thuốc đã GIAO mà chưa gắn lô (giao không lô, 28/09): sổ kho chưa trừ nên tồn
    máy cao hơn kệ thật. Báo riêng — KHÔNG tính là lệch đếm."""
    rows = await conn.fetch(
        """
        SELECT g.drug_catalog_id::text AS drug_catalog_id, sum(g.so_luong) AS so
          FROM public.thuoc_giao_chua_gan_lo g
          JOIN public.prescription p ON p.id = g.prescription_id
         WHERE g.clinic_id = $1::uuid AND g.drug_batch_id IS NULL
           AND g.drug_catalog_id IS NOT NULL
           AND ($2::uuid IS NULL
                OR coalesce(public.co_so_cua_luot(g.clinic_id, p.visit_id), $2::uuid)
                   = $2::uuid)
         GROUP BY g.drug_catalog_id
        """,
        clinic_id,
        location_id,
    )
    return {r["drug_catalog_id"]: r["so"] for r in rows}


async def ghep_vao_bao_cao(
    conn: asyncpg.Connection,
    thuoc: dict[str, Any],
    *,
    clinic_id: str,
    location_id: str | None,
    tu_ngay: date,
    den_ngay: date,
    tu: datetime | None,
    den: datetime | None,
    ca: str | None,
) -> None:
    """Điểm gắn DUY NHẤT với báo cáo cuối ngày: thêm khối `kho` vào mỗi dòng
    thuốc của `hang_hoa`. Mốc giờ: ca (nếu chọn một ca của một ngày) hoặc cả khoảng
    ngày VN. Lỗi đọc kho không được làm sập báo cáo tiền → chỉ bỏ khối `kho`."""
    moc_tu = tu or datetime(tu_ngay.year, tu_ngay.month, tu_ngay.day, tzinfo=CLINIC_TZ)
    moc_den = den or (
        datetime(den_ngay.year, den_ngay.month, den_ngay.day, tzinfo=CLINIC_TZ)
        + timedelta(days=1)
    )
    try:
        xnt = await xnt_theo_ca(
            conn, clinic_id=clinic_id, location_id=location_id, tu=moc_tu, den=moc_den
        )
        kiem = await kiem_trong_khoang(
            conn,
            clinic_id=clinic_id,
            location_id=location_id,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
            ca=ca,
        )
        chua = await da_thu_chua_giao(
            conn, clinic_id=clinic_id, location_id=location_id
        )
        gan_lo = await giao_chua_gan_lo_theo_thuoc(
            conn, clinic_id=clinic_id, location_id=location_id
        )
        can_ten = {r["drug_catalog_id"] for r in xnt} | {k[0] for k in kiem}
        ten_thuoc = {
            r["id"]: dict(r)
            for r in await conn.fetch(
                "SELECT id::text AS id, name_raw AS ten, ma_hang, don_vi_ban"
                " FROM public.drug_catalog WHERE clinic_id = $1::uuid"
                " AND id = ANY($2::uuid[])",
                clinic_id,
                list(can_ten),
            )
        }
    except asyncpg.PostgresError:
        return
    ghep_ton_ca(thuoc, xnt, kiem, chua, gan_lo, ten_thuoc)


# ── Ghi ──────────────────────────────────────────────────────────────────


def _co_so(identity: StaffIdentity) -> str:
    if not identity.location_id:
        raise ConflictError("Chưa biết bạn đang làm ở cơ sở nào — chọn cơ sở trước.")
    return str(identity.location_id)


def _doc_ngay(v: Any) -> date:
    d = doc_ngay_xem(v)
    if d is None:
        raise ValidationError("Ngày kiểm kê không hợp lệ (cần dạng YYYY-MM-DD).")
    hom_nay = hom_nay_vn()
    if d > hom_nay + timedelta(days=1) or d < hom_nay - timedelta(days=NGAY_LUI_TOI_DA):
        raise ValidationError(
            "Ngày kiểm kê quá xa — chỉ nhận từ một năm trước tới ngày mai."
        )
    return d


def _doc_ca(v: Any) -> str:
    ca = str(v or "").strip().upper()
    if ca not in CAC_CA:
        raise ValidationError("Ca không hợp lệ (SANG, CHIEU hoặc TOI).")
    return ca


def _doc_loai(v: Any) -> str:
    loai = str(v or "").strip().upper()
    if loai not in LOAI_PHIEU:
        raise ValidationError("Loại phiếu không hợp lệ (DAU, CUOI hoặc DOT_XUAT).")
    return loai


def _doc_uuid(v: Any, ten: str) -> str:
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValidationError(f"{ten} không hợp lệ.") from exc


_PHIEU_SQL = """
    SELECT k.id::text AS id, k.location_id::text AS location_id, k.ngay, k.ca,
           k.loai, k.trang_thai, k.mot_phan, k.dung_so_ca_truoc, k.ghi_chu,
           k.tao_luc, k.chot_luc, k.dieu_chinh_luc, k.dieu_chinh_ly_do,
           k.hoan_tac_luc, s.full_name AS nguoi_tao, sc.full_name AS nguoi_chot,
           sd.full_name AS nguoi_dieu_chinh
      FROM public.kiem_ke_ca k
      LEFT JOIN public.staff s ON s.id = k.tao_boi
      LEFT JOIN public.staff sc ON sc.id = k.chot_boi
      LEFT JOIN public.staff sd ON sd.id = k.dieu_chinh_boi
     WHERE k.id = $1::uuid AND k.clinic_id = $2::uuid AND k.location_id = $3::uuid
"""


async def doc_phieu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    async with pool.acquire() as conn:
        return await _doc_phieu(conn, identity, pid)


async def _doc_phieu(
    conn: asyncpg.Connection, identity: StaffIdentity, pid: str
) -> dict[str, Any]:
    p = await conn.fetchrow(_PHIEU_SQL, pid, identity.clinic_id, _co_so(identity))
    if p is None:
        raise NotFoundError("Không tìm thấy phiếu kiểm kê này.")
    dong = await conn.fetch(
        """
        SELECT d.drug_catalog_id::text AS drug_catalog_id, c.name_raw AS ten,
               c.ma_hang, d.don_vi, d.dem, d.ton_may, d.lech, d.giao_chua_gan_lo
          FROM public.kiem_ke_ca_dong d
          JOIN public.drug_catalog c ON c.id = d.drug_catalog_id
         WHERE d.kiem_ke_ca_id = $1::uuid AND d.clinic_id = $2::uuid
         ORDER BY lower(c.name_raw), d.don_vi
        """,
        pid,
        identity.clinic_id,
    )
    return {**dict(p), "dong": [dict(r) for r in dong]}


async def danh_sach(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ngay: Any = None
) -> list[dict[str, Any]]:
    """Phiếu kiểm kê gần nhất của cơ sở (60 phiếu); `ngay` hợp lệ thì chỉ ngày ấy.
    Ngày rác → như không lọc, không ném (đây là đường ĐỌC)."""
    d = doc_ngay_xem(ngay) if ngay not in (None, "") else None
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT k.id::text AS id, k.ngay, k.ca, k.loai, k.trang_thai, k.mot_phan,
                   k.tao_luc, k.chot_luc, k.dieu_chinh_luc, k.hoan_tac_luc,
                   s.full_name AS nguoi_tao,
                   (SELECT count(*) FROM public.kiem_ke_ca_dong d
                     WHERE d.kiem_ke_ca_id = k.id) AS so_dong,
                   (SELECT count(*) FROM public.kiem_ke_ca_dong d
                     WHERE d.kiem_ke_ca_id = k.id AND d.lech IS NOT NULL
                       AND d.lech <> 0) AS so_lech
              FROM public.kiem_ke_ca k
              LEFT JOIN public.staff s ON s.id = k.tao_boi
             WHERE k.clinic_id = $1::uuid AND k.location_id = $2::uuid
               AND ($3::date IS NULL OR k.ngay = $3::date)
             ORDER BY k.ngay DESC, k.tao_luc DESC
             LIMIT 60
            """,
            identity.clinic_id,
            _co_so(identity),
            d,
        )
    return [dict(r) for r in rows]


async def nhac_thieu_kiem(
    pool: asyncpg.Pool, *, identity: StaffIdentity, ngay: Any = None, ca: Any = None
) -> dict[str, Any]:
    """Nhắc (KHÔNG chặn bán): ca này chưa kiểm đầu ca / ca trước chưa kiểm cuối ca.
    Ngày / ca rác → hôm nay / ca hiện tại, không ném."""
    d = doc_ngay_xem(ngay) or hom_nay_vn()
    async with pool.acquire() as conn:
        settings = await conn.fetchval(
            "SELECT settings FROM clinic WHERE id = $1::uuid", identity.clinic_id
        )
        ma = str(ca or "").strip().upper()
        if ma not in CAC_CA:
            ma = ca_cua_gio(datetime.now(CLINIC_TZ), settings)
        thu_tu = THU_TU_CA[ma]
        truoc_ngay, truoc_ca = (
            (d, [k for k, v in THU_TU_CA.items() if v == thu_tu - 1][0])
            if thu_tu > 1
            else (d - timedelta(days=1), "TOI")
        )
        rows = await conn.fetch(
            """
            SELECT ngay, ca, loai, trang_thai FROM public.kiem_ke_ca
             WHERE clinic_id = $1::uuid AND location_id = $2::uuid
               AND ((ngay = $3 AND ca = $4 AND loai = 'DAU')
                 OR (ngay = $5 AND ca = $6 AND loai = 'CUOI'))
            """,
            identity.clinic_id,
            _co_so(identity),
            d,
            ma,
            truoc_ngay,
            truoc_ca,
        )
    chot = {(r["loai"]): r["trang_thai"] == "CHOT" for r in rows}
    return {
        "ngay": d.isoformat(),
        "ca": ma,
        "thieu_dau_ca": not chot.get("DAU", False),
        "ca_truoc": {"ngay": truoc_ngay.isoformat(), "ca": truoc_ca},
        "thieu_cuoi_ca_truoc": not chot.get("CUOI", False),
    }


async def mo_phieu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ngay: Any,
    ca: Any,
    loai: Any,
    ghi_chu: str | None = None,
) -> dict[str, Any]:
    """Mở phiếu kiểm. Đầu / cuối ca: hai người mở cùng ca → MỘT phiếu (UNIQUE từng
    phần ép ở Postgres; người thứ hai nhận lại đúng phiếu ấy). Đột xuất: phiếu mới."""
    d, c, lo = _doc_ngay(ngay), _doc_ca(ca), _doc_loai(loai)
    co_so = _co_so(identity)
    ghi = (ghi_chu or "").strip()[:500] or None
    async with pool.acquire() as conn, conn.transaction():
        if lo == "DOT_XUAT":
            pid = await conn.fetchval(
                "INSERT INTO public.kiem_ke_ca (clinic_id, location_id, ngay, ca,"
                " loai, ghi_chu, tao_boi) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
                " $6, $7::uuid) RETURNING id::text",
                identity.clinic_id,
                co_so,
                d,
                c,
                lo,
                ghi,
                identity.staff_id,
            )
            moi = True
        else:
            pid = await conn.fetchval(
                "INSERT INTO public.kiem_ke_ca (clinic_id, location_id, ngay, ca,"
                " loai, ghi_chu, tao_boi) VALUES ($1::uuid, $2::uuid, $3, $4, $5,"
                " $6, $7::uuid) ON CONFLICT (location_id, ngay, ca, loai)"
                " WHERE loai IN ('DAU', 'CUOI') DO NOTHING RETURNING id::text",
                identity.clinic_id,
                co_so,
                d,
                c,
                lo,
                ghi,
                identity.staff_id,
            )
            moi = pid is not None
            if pid is None:
                pid = await conn.fetchval(
                    "SELECT id::text FROM public.kiem_ke_ca WHERE location_id ="
                    " $1::uuid AND ngay = $2 AND ca = $3 AND loai = $4",
                    co_so,
                    d,
                    c,
                    lo,
                )
        if moi:
            await ghi_nhat_ky(
                conn,
                identity=identity,
                event_type="pharmacy.kiem_ke_ca_mo",
                aggregate_type="kiem_ke_ca",
                aggregate_id=pid,
                payload={"ngay": d.isoformat(), "ca": c, "loai": lo},
            )
        kq = await _doc_phieu(conn, identity, str(pid))
    return {**kq, "moi_mo": moi}


async def _khoa_phieu_nhap(
    conn: asyncpg.Connection, identity: StaffIdentity, pid: str
) -> asyncpg.Record:
    p = await conn.fetchrow(
        "SELECT id::text, loai, ngay, ca, trang_thai FROM public.kiem_ke_ca"
        " WHERE id = $1::uuid AND clinic_id = $2::uuid AND location_id = $3::uuid"
        " FOR UPDATE",
        pid,
        identity.clinic_id,
        _co_so(identity),
    )
    if p is None:
        raise NotFoundError("Không tìm thấy phiếu kiểm kê này.")
    if p["trang_thai"] != "NHAP":
        raise ConflictError("Phiếu đã chốt — không sửa số đếm được.")
    return p


async def luu_dem(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    phieu_id: Any,
    dong: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lưu số đếm (nháp, ghi đè theo từng thuốc + đơn vị). `dem` rỗng / null = bỏ
    dòng ấy khỏi phiếu. Số rác (âm, chữ, quá lớn) → 422, KHÔNG ghi gì (cả lệnh)."""
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    if not dong or len(dong) > DONG_TOI_DA:
        raise ValidationError(f"Gửi từ 1 đến {DONG_TOI_DA} dòng mỗi lần.")
    ghi: list[tuple[str, str, Decimal | None]] = []
    for i, d in enumerate(dong, 1):
        thuoc = _doc_uuid(d.get("drug_catalog_id"), f"Thuốc ở dòng {i}")
        dv = str(d.get("don_vi") or "").strip().lower()
        if not dv or len(dv) > 50:
            raise ValidationError(f"Dòng {i}: thiếu đơn vị.")
        raw = d.get("dem")
        if raw is None or str(raw).strip() == "":
            ghi.append((thuoc, dv, None))
            continue
        so = so_hoac_none(raw)
        if so is None:
            raise ValidationError(f"Dòng {i}: số đếm phải là số không âm, hợp lý.")
        ghi.append((thuoc, dv, so))
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_phieu_nhap(conn, identity, pid)
        for thuoc, dv, so in ghi:
            if so is None:
                await conn.execute(
                    "DELETE FROM public.kiem_ke_ca_dong WHERE kiem_ke_ca_id ="
                    " $1::uuid AND drug_catalog_id = $2::uuid AND don_vi = $3",
                    pid,
                    thuoc,
                    dv,
                )
                continue
            try:
                await conn.execute(
                    "INSERT INTO public.kiem_ke_ca_dong (clinic_id, kiem_ke_ca_id,"
                    " drug_catalog_id, don_vi, dem) VALUES ($1::uuid, $2::uuid,"
                    " $3::uuid, $4, $5) ON CONFLICT (kiem_ke_ca_id, drug_catalog_id,"
                    " don_vi) DO UPDATE SET dem = EXCLUDED.dem",
                    identity.clinic_id,
                    pid,
                    thuoc,
                    dv,
                    so,
                )
            except asyncpg.ForeignKeyViolationError as exc:
                raise NotFoundError("Có thuốc không có trong danh mục kho.") from exc
        return await _doc_phieu(conn, identity, pid)


async def dung_so_cuoi_ca_truoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    """Phiếu ĐẦU ca: lấy số đếm của phiếu CUỐI ca gần nhất đã chốt (trước ca này)
    làm số đếm đầu ca — dòng nào đã gõ tay thì giữ nguyên."""
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    async with pool.acquire() as conn, conn.transaction():
        p = await _khoa_phieu_nhap(conn, identity, pid)
        if p["loai"] != "DAU":
            raise ConflictError("Chỉ phiếu ĐẦU ca mới dùng số cuối ca trước.")
        truoc = await conn.fetchval(
            """
            SELECT id::text FROM public.kiem_ke_ca
             WHERE clinic_id = $1::uuid AND location_id = $2::uuid
               AND loai = 'CUOI' AND trang_thai = 'CHOT'
               AND (ngay, CASE ca WHEN 'SANG' THEN 1 WHEN 'CHIEU' THEN 2 ELSE 3 END)
                   < ($3::date, $4::int)
             ORDER BY ngay DESC,
                      CASE ca WHEN 'SANG' THEN 1 WHEN 'CHIEU' THEN 2 ELSE 3 END DESC
             LIMIT 1
            """,
            identity.clinic_id,
            _co_so(identity),
            p["ngay"],
            THU_TU_CA[p["ca"]],
        )
        if truoc is None:
            raise ConflictError("Chưa có phiếu cuối ca nào đã chốt trước ca này.")
        await conn.execute(
            "INSERT INTO public.kiem_ke_ca_dong (clinic_id, kiem_ke_ca_id,"
            " drug_catalog_id, don_vi, dem) SELECT clinic_id, $2::uuid,"
            " drug_catalog_id, don_vi, dem FROM public.kiem_ke_ca_dong WHERE"
            " kiem_ke_ca_id = $1::uuid ON CONFLICT (kiem_ke_ca_id, drug_catalog_id,"
            " don_vi) DO NOTHING",
            truoc,
            pid,
        )
        await conn.execute(
            "UPDATE public.kiem_ke_ca SET dung_so_ca_truoc = true WHERE id = $1::uuid",
            pid,
        )
        return await _doc_phieu(conn, identity, pid)


async def chot(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    """CHỐT phiếu: ghi tồn máy ở quầy TẠI GIỜ CHỐT và lệch = đếm − tồn máy (bán
    giữa lúc đếm không làm lệch tính theo giờ đếm — ghi rõ giờ chốt). Chốt lần
    hai trả lại đúng phiếu đã chốt. Có lệch → chuông. KHÔNG sửa tồn."""
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    co_so = _co_so(identity)
    async with pool.acquire() as conn, conn.transaction():
        p = await conn.fetchrow(
            "SELECT id::text, ngay, ca, loai, trang_thai FROM public.kiem_ke_ca"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid AND location_id ="
            " $3::uuid FOR UPDATE",
            pid,
            identity.clinic_id,
            co_so,
        )
        if p is None:
            raise NotFoundError("Không tìm thấy phiếu kiểm kê này.")
        if p["trang_thai"] == "CHOT":
            return {**await _doc_phieu(conn, identity, pid), "gui_lai": True}
        dong = await conn.fetch(
            "SELECT drug_catalog_id::text AS thuoc, don_vi, dem FROM"
            " public.kiem_ke_ca_dong WHERE kiem_ke_ca_id = $1::uuid FOR UPDATE",
            pid,
        )
        if not dong:
            raise ValidationError(
                "Phiếu chưa đếm thuốc nào — nhập số đếm rồi mới chốt."
            )
        ton = {
            (r["thuoc"], r["don_vi"]): r["ton"]
            for r in await conn.fetch(
                "SELECT drug_catalog_id::text AS thuoc, lower(btrim(unit)) AS don_vi,"
                " sum(quantity_on_hand) AS ton FROM public.drug_batch"
                " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
                " AND noi_chua = 'QUAY' GROUP BY 1, 2",
                identity.clinic_id,
                co_so,
            )
        }
        gan_lo = await giao_chua_gan_lo_theo_thuoc(
            conn, clinic_id=identity.clinic_id, location_id=co_so
        )
        so_lech = 0
        da_dem = set()
        for r in dong:
            khoa = (r["thuoc"], r["don_vi"])
            da_dem.add(khoa)
            may = Decimal(str(ton.get(khoa, 0)))
            lech = r["dem"] - may
            if lech != 0:
                so_lech += 1
            await conn.execute(
                "UPDATE public.kiem_ke_ca_dong SET ton_may = $4, lech = $5,"
                " giao_chua_gan_lo = $6 WHERE kiem_ke_ca_id = $1::uuid AND"
                " drug_catalog_id = $2::uuid AND don_vi = $3",
                pid,
                r["thuoc"],
                r["don_vi"],
                may,
                lech,
                gan_lo.get(r["thuoc"]),
            )
        # Kiểm một phần: còn (thuốc, đơn vị) có tồn ở quầy mà phiếu không đếm.
        mot_phan = any(Decimal(str(v)) != 0 and k not in da_dem for k, v in ton.items())
        await conn.execute(
            "UPDATE public.kiem_ke_ca SET trang_thai = 'CHOT', mot_phan = $2,"
            " chot_boi = $3::uuid, chot_luc = now() WHERE id = $1::uuid",
            pid,
            mot_phan,
            identity.staff_id,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.kiem_ke_ca_chot",
            aggregate_type="kiem_ke_ca",
            aggregate_id=pid,
            payload={
                "loai": p["loai"],
                "so_dong": len(dong),
                "so_lech": so_lech,
                "mot_phan": mot_phan,
            },
        )
        if so_lech:
            await emit_event(
                conn,
                ten="pharmacy.stocktake_mismatch",
                clinic_id=identity.clinic_id,
                aggregate_id=pid,
                payload=KiemKeLech(
                    ngay=p["ngay"], ca=p["ca"], loai=p["loai"], so_dong_lech=so_lech
                ),
                boi=nguoi(identity),
            )
        return {**await _doc_phieu(conn, identity, pid), "gui_lai": False}


async def _khoa_lo_quay(
    conn: asyncpg.Connection, identity: StaffIdentity, thuoc: list[str]
) -> None:
    """Khoá mọi lô QUẦY của các thuốc, theo id (hai người không khoá chéo)."""
    await conn.fetch(
        "SELECT id FROM public.drug_batch WHERE clinic_id = $1::uuid AND location_id"
        " = $2::uuid AND noi_chua = 'QUAY' AND drug_catalog_id = ANY($3::uuid[])"
        " ORDER BY id FOR UPDATE",
        identity.clinic_id,
        _co_so(identity),
        thuoc,
    )


async def dieu_chinh_theo_kiem_ke(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any, ly_do: Any
) -> dict[str, Any]:
    """Bước RIÊNG sau chốt: đưa tồn máy về số đếm — ghi `ADJUST` đúng bằng LỆCH đã
    chốt (không tính lại theo bán sau đó), có lý do, hoàn tác được. Lệch dương
    cộng vào lô QUẦY nhập gần nhất; lệch âm trừ lô gần hết hạn trước (FEFO), không
    trừ quá tồn lô — phần không áp được trả về `bo_qua` (không lặng lẽ cắt)."""
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    ly = str(ly_do or "").strip()
    if not ly:
        raise ValidationError("Điều chỉnh theo kiểm kê thì phải ghi lý do.")
    async with pool.acquire() as conn, conn.transaction():
        p = await conn.fetchrow(
            "SELECT id::text, trang_thai, dieu_chinh_luc FROM public.kiem_ke_ca"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid AND location_id ="
            " $3::uuid FOR UPDATE",
            pid,
            identity.clinic_id,
            _co_so(identity),
        )
        if p is None:
            raise NotFoundError("Không tìm thấy phiếu kiểm kê này.")
        if p["trang_thai"] != "CHOT":
            raise ConflictError("Phải chốt phiếu trước khi điều chỉnh.")
        if p["dieu_chinh_luc"] is not None:
            raise ConflictError(
                "Phiếu này đã điều chỉnh rồi (hoàn tác trước nếu cần làm lại)."
            )
        lech = await conn.fetch(
            "SELECT drug_catalog_id::text AS thuoc, don_vi, lech FROM"
            " public.kiem_ke_ca_dong WHERE kiem_ke_ca_id = $1::uuid AND lech <> 0",
            pid,
        )
        if not lech:
            raise ConflictError("Phiếu không có lệch nào để điều chỉnh.")
        await _khoa_lo_quay(conn, identity, sorted({r["thuoc"] for r in lech}))
        ap_dung: list[dict[str, Any]] = []
        bo_qua: list[dict[str, Any]] = []
        for r in lech:
            can = Decimal(str(r["lech"]))
            lo = await conn.fetch(
                "SELECT id::text, batch_code, quantity_on_hand FROM public.drug_batch"
                " WHERE clinic_id = $1::uuid AND location_id = $2::uuid AND noi_chua"
                " = 'QUAY' AND drug_catalog_id = $3::uuid AND lower(btrim(unit)) = $4"
                " ORDER BY expiry_date NULLS LAST, received_at, id",
                identity.clinic_id,
                _co_so(identity),
                r["thuoc"],
                r["don_vi"],
            )
            if can > 0:
                if not lo:
                    bo_qua.append(
                        {
                            **_dong_bo(r),
                            "ly_do": "Quầy chưa có lô nào của thuốc này để cộng",
                        }
                    )
                    continue
                # Cộng vào lô QUẦY nhập gần nhất (thuốc thừa nhiều khả năng là
                # hàng vừa về); `lo` đã xếp theo hạn nên lấy theo ngày nhập riêng.
                dich = await conn.fetchrow(
                    "SELECT id::text, batch_code FROM public.drug_batch WHERE id ="
                    " ANY($1::uuid[]) ORDER BY received_at DESC NULLS LAST, id DESC"
                    " LIMIT 1",
                    [b["id"] for b in lo],
                )
                assert dich is not None
                await _ghi_adjust(conn, identity, dich["id"], can, pid, ly)
                ap_dung.append(
                    {**_dong_bo(r), "lo": dich["batch_code"], "so_luong": float(can)}
                )
                continue
            con = -can
            for b in lo:
                if con <= 0:
                    break
                lay = min(Decimal(str(b["quantity_on_hand"])), con)
                if lay <= 0:
                    continue
                await _ghi_adjust(conn, identity, b["id"], -lay, pid, ly)
                ap_dung.append(
                    {**_dong_bo(r), "lo": b["batch_code"], "so_luong": float(-lay)}
                )
                con -= lay
            if con > 0:
                bo_qua.append(
                    {
                        **_dong_bo(r),
                        "con_thieu": float(con),
                        "ly_do": "Quầy không còn đủ tồn để trừ hết phần lệch",
                    }
                )
        await conn.execute(
            "UPDATE public.kiem_ke_ca SET dieu_chinh_boi = $2::uuid, dieu_chinh_luc"
            " = now(), dieu_chinh_ly_do = $3 WHERE id = $1::uuid",
            pid,
            identity.staff_id,
            ly,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.kiem_ke_ca_dieu_chinh",
            aggregate_type="kiem_ke_ca",
            aggregate_id=pid,
            payload={
                "ly_do": ly,
                "so_dong_ap_dung": len(ap_dung),
                "so_bo_qua": len(bo_qua),
            },
        )
        return {"ok": True, "phieu_id": pid, "ap_dung": ap_dung, "bo_qua": bo_qua}


def _dong_bo(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "drug_catalog_id": r["thuoc"],
        "don_vi": r["don_vi"],
        "lech": float(r["lech"]),
    }


async def _ghi_adjust(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    lo_id: str,
    so: Decimal,
    phieu_id: str,
    ly: str,
    *,
    ref_type: str = "kiem_ke_ca",
) -> None:
    await PharmacyService._ghi_so_trong(
        conn,
        identity=identity,
        drug_batch_id=lo_id,
        txn_type=DIEU_CHINH,
        quantity=so,
        reason=f"Điều chỉnh theo kiểm kê: {ly}",
        ref_type=ref_type,
        ref_id=phieu_id,
    )


async def hoan_tac_dieu_chinh(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    """Hoàn tác điều chỉnh: mỗi dòng ADJUST của phiếu có một dòng ADJUST ngược (sổ
    chỉ-thêm). Nếu phần cộng đã bán mất thì không trừ lại được → 409 nói rõ."""
    pid = _doc_uuid(phieu_id, "Mã phiếu")
    async with pool.acquire() as conn, conn.transaction():
        p = await conn.fetchrow(
            "SELECT id::text, dieu_chinh_luc, hoan_tac_luc FROM public.kiem_ke_ca"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid AND location_id ="
            " $3::uuid FOR UPDATE",
            pid,
            identity.clinic_id,
            _co_so(identity),
        )
        if p is None:
            raise NotFoundError("Không tìm thấy phiếu kiểm kê này.")
        if p["dieu_chinh_luc"] is None:
            raise ConflictError("Phiếu này chưa điều chỉnh — không có gì để hoàn tác.")
        if p["hoan_tac_luc"] is not None:
            raise ConflictError("Phiếu này đã hoàn tác điều chỉnh rồi.")
        txn = await conn.fetch(
            "SELECT drug_batch_id::text AS lo, quantity FROM public.inventory_txn"
            " WHERE clinic_id = $1::uuid AND ref_type = 'kiem_ke_ca' AND ref_id ="
            " $2::uuid AND txn_type = 'ADJUST' ORDER BY drug_batch_id, performed_at",
            identity.clinic_id,
            pid,
        )
        if not txn:
            raise ConflictError("Không tìm thấy dòng sổ của điều chỉnh này.")
        await conn.fetch(
            "SELECT id FROM public.drug_batch WHERE id = ANY($1::uuid[]) ORDER BY id"
            " FOR UPDATE",
            sorted({t["lo"] for t in txn}),
        )
        for t in txn:
            moi = -Decimal(str(t["quantity"]))
            hien = Decimal(
                str(
                    await conn.fetchval(
                        "SELECT quantity_on_hand FROM public.drug_batch"
                        " WHERE id = $1::uuid",
                        t["lo"],
                    )
                )
            )
            if hien + moi < 0:
                raise ConflictError(
                    "Không hoàn tác được: phần thuốc đã cộng thêm sau kiểm kê giờ đã"
                    " bán / xuất hết khỏi lô — xử lý bằng một lần điều chỉnh mới."
                )
            await _ghi_adjust(
                conn,
                identity,
                t["lo"],
                moi,
                pid,
                "hoàn tác điều chỉnh theo kiểm kê",
                ref_type="kiem_ke_ca_hoan",
            )
        await conn.execute(
            "UPDATE public.kiem_ke_ca SET hoan_tac_boi = $2::uuid, hoan_tac_luc = now()"
            " WHERE id = $1::uuid",
            pid,
            identity.staff_id,
        )
        await ghi_nhat_ky(
            conn,
            identity=identity,
            event_type="pharmacy.kiem_ke_ca_hoan_tac",
            aggregate_type="kiem_ke_ca",
            aggregate_id=pid,
            payload={"so_dong": len(txn)},
        )
        return {"ok": True, "phieu_id": pid, "so_dong": len(txn)}
