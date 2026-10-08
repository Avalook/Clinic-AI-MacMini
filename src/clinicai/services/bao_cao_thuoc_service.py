"""Thuốc theo khách — bác sĩ KÊ vs quầy THỰC BÁN, cho báo cáo cuối ngày / cuối ca.

Khách báo 08/10/2026: báo cáo thuốc "link về thuốc bác sĩ kê chứ không phải thuốc
cuối cùng thực sự". Nguồn mỗi con số (đừng cộng theo ``prescription`` — dòng đính
chính CP6 làm đếm đôi):

* **Kê** — số bác sĩ ghi: ``so_luong_ke_goc`` nếu quầy đã sửa số (C19), không thì
  ``quantity_num``. Quầy ĐIỀN chỗ bác sĩ để trống → kê = không có (``None``).
  Dòng quầy thêm (``nguon = 'QUAY'``) → kê 0.
* **Bán / tiền** — ``payment_bill_line`` của lần thu thuốc PAID (ảnh chụp lúc thu;
  phiếu huỷ không tính). **Trả** — ``payment_refund_line`` đã hoàn xong.
  Thực bán = bán − trả.
* **Tên thuốc thật** — thuốc kho (``drug_catalog``) mà quầy đã chọn; tên bác sĩ gõ
  giữ làm dòng phụ khi khác.

Khách vào danh sách khi có lần thu thuốc trong khoảng, HOẶC lượt tạo trong khoảng
có đơn thuốc (kê mà chưa / không mua cũng phải hiện — đó chính là chênh lệch).

Hàm thuần ``gom_thuoc_theo_khach`` có test không cần DB
(``tests/unit/test_bao_cao_thuoc.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.core.tran import canh_bao_neu_day

_TRAN_KHACH = 1000
_0 = Decimal(0)


def _so(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        d = Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _ra(d: Decimal | None) -> float | None:
    """Decimal → số JSON (2 → 2, 1.5 → 1.5)."""
    return None if d is None else float(d)


def _tien(d: Decimal | None) -> int:
    return int(d or 0)


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


def _chuan(s: Any) -> str:
    return " ".join(str(s or "").lower().split())


def so_ke(don: Mapping[str, Any]) -> Decimal | None:
    """Số BÁC SĨ kê của một dòng đơn (xem docstring module). Thuần."""
    if don.get("nguon") == "QUAY":
        return Decimal(0)
    if don.get("quay_sua"):
        # Quầy đã chạm số: số gốc của bác sĩ nằm ở so_luong_ke_goc (NULL = bác
        # sĩ để trống, quầy điền — không có số kê để so).
        return _so(don.get("ke_goc_num"))
    return _so(don.get("quantity_num"))


def gom_thuoc_theo_khach(
    *,
    khach: Iterable[Mapping[str, Any]],
    don: Iterable[Mapping[str, Any]],
    bill: Iterable[Mapping[str, Any]],
    hoan: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Mỗi khách một mục (kèm các dòng thuốc) + tiêu hao theo thuốc + tổng. Thuần.

    ``khach``: visit_id, ten_khach, ma_bn, luc, ban_le, bac_si. ``don``: dòng
    ``prescription`` (kể cả dòng đã gỡ — chỉ hiện nếu đã bán). ``bill``: dòng hoá
    đơn thuốc PAID (source_id = id dòng đơn). ``hoan``: dòng hoàn đã xong, theo
    ``bill_line_id``.
    """
    tra: dict[str, tuple[Decimal, Decimal]] = {}
    for h in hoan:
        k = str(h.get("bill_line_id"))
        sl, tt = tra.get(k, (_0, _0))
        tra[k] = (
            sl + (_so(h.get("quantity")) or _0),
            tt + (_so(h.get("amount")) or _0),
        )

    bill_theo_dong: dict[str, list[Mapping[str, Any]]] = {}
    for b in bill:
        bill_theo_dong.setdefault(str(b.get("source_id")), []).append(b)

    don_theo_luot: dict[str, list[Mapping[str, Any]]] = {}
    for d in don:
        don_theo_luot.setdefault(str(d.get("visit_id")), []).append(d)

    ds_khach: list[dict[str, Any]] = []
    theo_thuoc: dict[str, dict[str, Any]] = {}
    tong = {"so_khach": 0, "so_khach_lech": 0, "so_dong_lech": 0, "tien": 0}

    for k in khach:
        vid = str(k.get("visit_id"))
        dong_ra: list[dict[str, Any]] = []
        nguoi_thu: list[str] = []
        luc_thu: str | None = None
        for d in sorted(
            don_theo_luot.get(vid, []),
            key=lambda r: (r.get("nguon") == "QUAY", str(r.get("created_at") or "")),
        ):
            bls = bill_theo_dong.get(str(d.get("id")), [])
            if d.get("removed_at") is not None and not bls:
                continue  # dòng đã đính chính, chưa từng bán — không phải sự thật bán
            ban = sum((_so(b.get("quantity")) or Decimal(0) for b in bls), Decimal(0))
            tien_ban = sum(
                (_so(b.get("line_total")) or Decimal(0) for b in bls), Decimal(0)
            )
            sl_tra = sum(
                (tra.get(str(b.get("id")), (_0, _0))[0] for b in bls), Decimal(0)
            )
            tien_tra = sum(
                (tra.get(str(b.get("id")), (_0, _0))[1] for b in bls), Decimal(0)
            )
            thuc = ban - sl_tra
            ke = so_ke(d)
            ten_kho = next((b.get("ten_kho") for b in bls if b.get("ten_kho")), None)
            ten_kho = ten_kho or d.get("ten_kho")
            ten = str(ten_kho or d.get("drug_name_raw") or "Không tên")
            ten_bs = d.get("drug_name_raw") if d.get("nguon") != "QUAY" else None
            doi_thuoc = bool(ten_kho and ten_bs and _chuan(ten_bs) != _chuan(ten_kho))
            khong_lay = bool(d.get("refusal_reason")) or _so(
                d.get("purchased_qty")
            ) == Decimal(0)
            don_gia = next(
                (_so(b.get("unit_price")) for b in reversed(bls)), None
            ) or _so(d.get("gia_kho"))
            chenh = None if ke is None else thuc - ke
            lech = bool(chenh) or doi_thuoc or d.get("nguon") == "QUAY"
            for b in bls:
                if b.get("nguoi_thu") and b["nguoi_thu"] not in nguoi_thu:
                    nguoi_thu.append(str(b["nguoi_thu"]))
                luc = _iso(b.get("paid_at"))
                if luc and (luc_thu is None or luc > luc_thu):
                    luc_thu = luc
            dong_ra.append(
                {
                    "id": str(d.get("id")),
                    "ten": ten,
                    "ten_bac_si": ten_bs if doi_thuoc else None,
                    "nguon": d.get("nguon"),
                    "don_vi": next((b.get("unit") for b in bls if b.get("unit")), None)
                    or d.get("unit")
                    or d.get("don_vi_ban"),
                    "so_ke": _ra(ke),
                    "so_ban": _ra(ban),
                    "so_tra": _ra(sl_tra),
                    "thuc_ban": _ra(thuc),
                    "chenh": _ra(chenh),
                    "don_gia": _tien(don_gia) if don_gia is not None else None,
                    "thanh_tien": _tien(tien_ban - tien_tra),
                    "da_giao": _ra(_so(d.get("dispensed_qty")) or Decimal(0)),
                    "trang_thai": "da_ban"
                    if ban > 0
                    else ("khong_lay" if khong_lay else "chua_thu"),
                    "lech": lech,
                }
            )
            t = theo_thuoc.setdefault(
                ten,
                {"ten": ten, "don_vi": dong_ra[-1]["don_vi"], "so_ke": Decimal(0)}
                | {"thuc_ban": Decimal(0), "so_tra": Decimal(0), "tien": 0},
            )
            t["so_ke"] += ke or _0
            t["thuc_ban"] += thuc
            t["so_tra"] += sl_tra
            t["tien"] += _tien(tien_ban - tien_tra)
        if not dong_ra:
            continue
        tien = sum(x["thanh_tien"] for x in dong_ra)
        so_lech = sum(1 for x in dong_ra if x["lech"])
        tong["so_khach"] += 1
        tong["tien"] += tien
        tong["so_dong_lech"] += so_lech
        tong["so_khach_lech"] += 1 if so_lech else 0
        ds_khach.append(
            {
                "visit_id": vid,
                "khach": k.get("ten_khach"),
                "ma_bn": k.get("ma_bn"),
                "ban_le": bool(k.get("ban_le")),
                "bac_si": k.get("bac_si"),
                "luc": luc_thu or _iso(k.get("luc")),
                "nguoi_thu": nguoi_thu,
                "so_dong": len(dong_ra),
                "so_lech": so_lech,
                "tien": tien,
                "dong": dong_ra,
            }
        )

    ds_khach.sort(key=lambda x: x["luc"] or "")
    tieu_hao = sorted(
        (
            {
                **t,
                "so_ke": _ra(t["so_ke"]),
                "thuc_ban": _ra(t["thuc_ban"]),
                "so_tra": _ra(t["so_tra"]),
            }
            for t in theo_thuoc.values()
            if t["thuc_ban"] or t["so_tra"]
        ),
        key=lambda t: (-t["tien"], t["ten"]),
    )
    return {"tong": tong, "khach": ds_khach, "tieu_hao": tieu_hao}


# ---------------------------------------------------------------------------
# Đọc DB
# ---------------------------------------------------------------------------

#: $2/$3 ngày VN, $4 cơ sở (NULL = tất cả), $5/$6 khung giờ ca (NULL = cả ngày).
_KHACH_SQL = """
WITH ids AS (
    SELECT pc.visit_id
      FROM payment_cycle pc
      JOIN visit v ON v.visit_id = pc.visit_id AND v.clinic_id = pc.clinic_id
      LEFT JOIN appointment ah
        ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
     WHERE pc.clinic_id = $1::uuid AND pc.kind = 'thuoc'
       AND pc.status IN ('PAID', 'VOIDED') AND pc.paid_at IS NOT NULL
       AND (pc.paid_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
       AND ($5::timestamptz IS NULL OR pc.paid_at >= $5)
       AND ($6::timestamptz IS NULL OR pc.paid_at < $6)
       AND ($4::uuid IS NULL OR coalesce(v.location_id, ah.location_id) = $4::uuid)
    UNION
    SELECT v.visit_id
      FROM visit v
      LEFT JOIN appointment ah
        ON ah.id = v.appointment_id AND ah.clinic_id = v.clinic_id
     WHERE v.clinic_id = $1::uuid
       AND (v.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date BETWEEN $2 AND $3
       AND ($5::timestamptz IS NULL OR v.created_at >= $5)
       AND ($6::timestamptz IS NULL OR v.created_at < $6)
       AND ($4::uuid IS NULL OR coalesce(v.location_id, ah.location_id) = $4::uuid)
       AND EXISTS (SELECT 1 FROM prescription r
                    WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
                      AND r.removed_at IS NULL)
)
SELECT v.visit_id::text AS visit_id, p.full_name AS ten_khach,
       p.patient_code AS ma_bn, v.created_at AS luc,
       coalesce(v.ban_le, false) AS ban_le,
       (SELECT s.full_name FROM prescription r
          JOIN staff s ON s.id = coalesce(r.bac_si_chinh_id, r.created_by)
         WHERE r.clinic_id = v.clinic_id AND r.visit_id = v.visit_id
           AND r.nguon IS DISTINCT FROM 'QUAY'
         ORDER BY r.created_at LIMIT 1) AS bac_si
  FROM ids
  JOIN visit v ON v.visit_id = ids.visit_id AND v.clinic_id = $1::uuid
  LEFT JOIN patient p
    ON p.clinic_patient_id = v.clinic_patient_id AND p.clinic_id = v.clinic_id
 ORDER BY v.created_at
 LIMIT 1000
"""

_DON_SQL = """
SELECT r.id::text AS id, r.visit_id::text AS visit_id, r.nguon, r.drug_name_raw,
       r.unit, r.quantity_num,
       public.so_luong_tu_van_ban(r.so_luong_ke_goc) AS ke_goc_num,
       r.so_luong_dien_boi IS NOT NULL AS quay_sua,
       r.purchased_qty, r.dispensed_qty, r.refusal_reason, r.removed_at, r.created_at,
       c.name_raw AS ten_kho, c.unit_price AS gia_kho, c.don_vi_ban
  FROM prescription r
  LEFT JOIN drug_catalog c ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
 WHERE r.clinic_id = $1::uuid AND r.visit_id = ANY($2::uuid[])
"""

#: Dòng hoá đơn thuốc của lần thu PAID tới hết khung ($3) — ảnh chụp lúc thu.
_BILL_SQL = """
SELECT bl.id::text AS id, bl.source_id, bl.quantity, bl.unit, bl.unit_price,
       bl.line_total, c.name_raw AS ten_kho, pc.paid_at,
       coalesce(xn.full_name, cb.full_name) AS nguoi_thu
  FROM payment_bill_line bl
  JOIN payment_cycle pc
    ON pc.payment_cycle_id = bl.payment_cycle_id AND pc.clinic_id = bl.clinic_id
  LEFT JOIN drug_catalog c ON c.id = bl.drug_catalog_id AND c.clinic_id = bl.clinic_id
  LEFT JOIN staff cb ON cb.id = pc.created_by
  LEFT JOIN staff xn ON xn.id = pc.confirmed_by
 WHERE bl.clinic_id = $1::uuid AND bl.visit_id = ANY($2::uuid[])
   AND bl.source_type = 'prescription' AND pc.kind = 'thuoc' AND pc.status = 'PAID'
   AND pc.paid_at < $3
"""

_HOAN_SQL = """
SELECT rl.payment_bill_line_id::text AS bill_line_id, rl.quantity, rl.amount
  FROM payment_refund_line rl
  JOIN payment_refund r ON r.refund_id = rl.refund_id AND r.clinic_id = rl.clinic_id
 WHERE rl.clinic_id = $1::uuid AND r.status = 'COMPLETED'
   AND rl.payment_bill_line_id = ANY($2::uuid[]) AND r.created_at < $3
"""


async def doc_thuoc_theo_khach(
    conn: asyncpg.Connection,
    clinic_id: str,
    *,
    tu: date,
    den: date,
    co_so: str | None,
    tu_luc: datetime | None,
    den_luc: datetime | None,
    het_khung: datetime,
) -> dict[str, Any]:
    """Đọc + gom. ``het_khung`` = mốc cuối (hết ca / hết ngày ``den``): bán và
    trả sau mốc này chưa tính."""
    khach = await conn.fetch(_KHACH_SQL, clinic_id, tu, den, co_so, tu_luc, den_luc)
    canh_bao_neu_day("bao_cao_thuoc.khach", len(khach), _TRAN_KHACH, tu=tu, den=den)
    ids = [r["visit_id"] for r in khach]
    don = await conn.fetch(_DON_SQL, clinic_id, ids) if ids else []
    bill = await conn.fetch(_BILL_SQL, clinic_id, ids, het_khung) if ids else []
    hoan = (
        await conn.fetch(_HOAN_SQL, clinic_id, [b["id"] for b in bill], het_khung)
        if bill
        else []
    )
    return gom_thuoc_theo_khach(
        khach=[dict(r) for r in khach],
        don=[dict(r) for r in don],
        bill=[dict(r) for r in bill],
        hoan=[dict(r) for r in hoan],
    )
