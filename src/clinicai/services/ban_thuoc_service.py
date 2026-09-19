"""Màn Nhà thuốc (contract tiền–thuốc CP4, 19/09/2026) — đọc, và quyết định
thao tác nào được phép cho từng lượt / từng dòng đơn.

Giao diện KHÔNG tự suy luật từ các cột: nó nhận `giai_doan` của lượt và
`thao_tac` của từng dòng / từng phân lô rồi vẽ đúng các nút ấy. Máy chủ vẫn
kiểm lại từng lệnh ghi — đây chỉ là để màn hình không mời bấm một nút chắc
chắn bị từ chối.

GIAI ĐOẠN CỦA LƯỢT (tiền thuốc):
  CHUA_SAN_SANG  bác sĩ chưa bấm Khám xong — chỉ xem. Chọn lô sớm sẽ khoá
                 dòng đơn trong khi bác sĩ còn sửa bệnh án.
  SAN_SANG       đã khám xong, chưa có lần thu thuốc — xác định thuốc kho,
                 khai số mua, chọn / bỏ lô.
  CHO_XAC_MINH   chuyển khoản/QR đang chờ — lô đang GIỮ; chỉ đổi lô.
  DA_THU         đã thu (lần thu mới) — giao từ đúng lô đã bán.
  CAN_DOI_SOAT   đã thu nhưng có phân lô chưa ghi bán được — không giao.
  DA_THU_CU      lần thu trước CP3 (legacy) — giao theo luồng cũ.

Ba con số lô trả kèm — `ton_vat_ly` (trên kệ) và `co_the_phan_lo` (số hệ thống
dùng để chống bán trùng). Tên hiển thị chính thức của con số thứ hai chưa chốt
(HOLD J6): màn hình KHÔNG gọi nó là "tồn khả dụng".
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ, now_vn

CHUA_SAN_SANG = "CHUA_SAN_SANG"
SAN_SANG = "SAN_SANG"
CHO_XAC_MINH = "CHO_XAC_MINH"
DA_THU = "DA_THU"
CAN_DOI_SOAT = "CAN_DOI_SOAT"
DA_THU_CU = "DA_THU_CU"

#: Vai được GHI ở nhà thuốc — router dùng đúng tập này cho mọi lệnh ghi, và màn
#: đọc AND nó vào mọi nút (review CP4 P2): người chỉ đọc (thu ngân thuốc,
#: trưởng ca) thấy dữ liệu nhưng không thấy nút sẽ bị 403.
VAI_GHI_NHA_THUOC: frozenset[ClinicRole] = frozenset(
    {ClinicRole.RECEPTION, ClinicRole.PHARMACIST, ClinicRole.MANAGEMENT}
)


def _don_vi(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


def _so(v: Any) -> Decimal:
    return Decimal(str(v if v is not None else 0))


@dataclass(frozen=True)
class LanThu:
    payment_cycle_id: str
    status: str
    method: str | None
    legacy: bool
    can_doi_soat: bool


def giai_doan(
    *, kham_xong: bool, lan_thu: LanThu | None, co_phan_lo_chua_ban: bool
) -> str:
    """Giai đoạn tiền thuốc của một lượt — hàm thuần, test không cần DB."""
    if lan_thu is not None and lan_thu.status == "PENDING_VERIFICATION":
        return CHO_XAC_MINH
    if lan_thu is not None and lan_thu.status == "PAID":
        if lan_thu.legacy:
            return DA_THU_CU
        return CAN_DOI_SOAT if co_phan_lo_chua_ban else DA_THU
    return SAN_SANG if kham_xong else CHUA_SAN_SANG


def thao_tac_dong(
    *,
    gd: str,
    dong_da_chot: bool,
    da_giao: Decimal,
    co_thuoc_kho: bool,
    co_don_vi: bool,
    co_so_ke: bool,
    can_lo: Decimal,
    da_chon: Decimal,
    co_phan_lo: bool,
    so_ban: Decimal | None,
    co_quyen_ghi: bool = True,
) -> dict[str, bool]:
    """Nút nào được hiện cho một dòng đơn — cùng luật với lệnh ghi ở
    pharmacy_service (Khám xong, chốt không bỏ lại thuốc đã bán chưa giao)."""
    mo = not dong_da_chot
    san_sang = gd == SAN_SANG and mo
    nut = {
        "xac_dinh_thuoc": san_sang and da_giao == 0 and not co_phan_lo,
        "khai_so_mua": san_sang and co_so_ke,
        "chon_lo": san_sang
        and co_thuoc_kho
        and co_don_vi
        and co_so_ke
        and da_chon < can_lo,
        "giao_luong_cu": gd == DA_THU_CU and mo,
        # Khách không lấy: sau Khám xong, trước khi có lần thu (sau đó phải
        # huỷ phiếu). Chốt / từ chối trước Khám xong cũng khoá dòng khỏi nút
        # Lưu bệnh án — đúng thứ màn này không được làm khi bác sĩ còn sửa đơn.
        "tu_choi": san_sang,
        # Chờ xác minh / cần đối soát: không bao giờ. Đã thu (luồng mới): chỉ
        # khi đã giao đủ số bán — trước CP5 không có đường xử lý phần còn lại.
        "chot": mo
        and (
            gd in (SAN_SANG, DA_THU_CU)
            or (gd == DA_THU and so_ban is not None and da_giao >= so_ban)
        ),
    }
    return {k: v and co_quyen_ghi for k, v in nut.items()}


def thao_tac_phan_lo(
    *,
    gd: str,
    dong_da_chot: bool,
    gan_lan_thu: bool,
    da_ban: bool,
    con_giao: Decimal,
    co_quyen_ghi: bool = True,
) -> dict[str, bool]:
    """Nút nào được hiện cho một phân lô (một lô đã chọn của dòng đơn)."""
    nut = {
        "bo": gd == SAN_SANG and not gan_lan_thu and not dong_da_chot,
        "doi": gd == CHO_XAC_MINH and gan_lan_thu,
        "giao": gd == DA_THU
        and gan_lan_thu
        and da_ban
        and con_giao > 0
        and not dong_da_chot,
    }
    return {k: v and co_quyen_ghi for k, v in nut.items()}


async def man_nha_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> dict[str, Any]:
    hom_nay = now_vn().date()
    co_quyen_ghi = identity.co_vai(VAI_GHI_NHA_THUOC)
    dau_ngay = datetime.combine(hom_nay, time.min, tzinfo=CLINIC_TZ)
    async with pool.acquire() as conn:
        dong = await conn.fetch(
            """
            SELECT r.id::text, r.visit_id::text, r.drug_name_raw, r.quantity,
                   r.quantity_num, r.unit, r.purchased_qty, r.dispensed_qty,
                   r.dispense_status, r.closed_at, r.refusal_reason,
                   r.dosage_instructions, r.drug_catalog_id::text,
                   c.name_base AS ten_thuoc_kho, r.created_at,
                   p.full_name AS ten_khach, p.patient_code, p.phone_primary,
                   (a.status = 'COMPLETED') AS kham_xong
              FROM public.prescription r
              JOIN public.visit v
                ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
              LEFT JOIN public.appointment a
                ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
              LEFT JOIN public.patient p
                ON p.clinic_patient_id = r.clinic_patient_id
               AND p.clinic_id = r.clinic_id
              LEFT JOIN public.drug_catalog c
                ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
             WHERE r.clinic_id = $1::uuid
               AND (r.closed_at IS NULL OR r.closed_at >= $2)
             ORDER BY r.created_at DESC, r.id
             LIMIT 300
            """,
            identity.clinic_id,
            dau_ngay,
        )
        luot_ids = sorted({r["visit_id"] for r in dong})
        rx_ids = [r["id"] for r in dong]
        lan_thu_rows = await conn.fetch(
            """
            SELECT DISTINCT ON (visit_id)
                   visit_id::text, payment_cycle_id::text, status, method, legacy,
                   can_doi_soat
              FROM public.payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = ANY($2::uuid[])
               AND kind = 'thuoc'
               AND status IN ('PENDING_VERIFICATION', 'PAID')
             ORDER BY visit_id, created_at DESC
            """,
            identity.clinic_id,
            luot_ids,
        )
        phan_lo = await conn.fetch(
            """
            SELECT a.id::text, a.prescription_id::text, a.drug_batch_id::text,
                   a.quantity, a.handed_over_qty, a.payment_cycle_id::text,
                   b.batch_code, b.expiry_date,
                   EXISTS (SELECT 1 FROM public.inventory_txn s
                            WHERE s.clinic_id = a.clinic_id
                              AND s.txn_type = 'SALE' AND s.allocation_id = a.id
                              AND s.payment_cycle_id = a.payment_cycle_id
                              AND NOT EXISTS (
                                  SELECT 1 FROM public.inventory_txn r
                                   WHERE r.txn_type = 'SALE_REVERSAL'
                                     AND r.reverses_txn_id = s.id)) AS da_ban
              FROM public.prescription_allocation a
              JOIN public.drug_batch b
                ON b.id = a.drug_batch_id AND b.clinic_id = a.clinic_id
             WHERE a.clinic_id = $1::uuid AND a.prescription_id = ANY($2::uuid[])
               AND a.released_at IS NULL
             ORDER BY a.created_at, a.id
            """,
            identity.clinic_id,
            rx_ids,
        )
        thuoc_ids = sorted({r["drug_catalog_id"] for r in dong if r["drug_catalog_id"]})
        lo_rows = await conn.fetch(
            """
            SELECT id::text, drug_catalog_id::text, batch_code, expiry_date, unit,
                   quantity_on_hand,
                   public.drug_batch_kha_dung($1::uuid, id) AS co_the_phan_lo
              FROM public.drug_batch
             WHERE clinic_id = $1::uuid AND drug_catalog_id = ANY($2::uuid[])
               AND expiry_date >= $3
             ORDER BY expiry_date, batch_code
            """,
            identity.clinic_id,
            thuoc_ids,
            hom_nay,
        )
        # Lượt thu trước CP3 mà dòng đơn chưa từng được xác định thuốc kho:
        # luồng cũ gợi ý lô theo TÊN (đúng như màn cũ) — dược sĩ vẫn là người
        # chọn. Chỉ đọc khi thật sự có lượt như vậy.
        lo_cu: list[asyncpg.Record] = []
        if any(r["legacy"] for r in lan_thu_rows):
            lo_cu = await conn.fetch(
                """
                SELECT b.id::text, b.drug_catalog_id::text, b.batch_code,
                       b.expiry_date, b.unit, b.quantity_on_hand,
                       b.quantity_on_hand AS co_the_phan_lo,
                       lower(coalesce(c.name_base, '')) AS ten_a,
                       lower(coalesce(c.name_raw, '')) AS ten_b
                  FROM public.drug_batch b
                  JOIN public.drug_catalog c
                    ON c.id = b.drug_catalog_id AND c.clinic_id = b.clinic_id
                 WHERE b.clinic_id = $1::uuid AND b.quantity_on_hand > 0
                   AND b.expiry_date >= $2
                 ORDER BY b.expiry_date, b.batch_code
                """,
                identity.clinic_id,
                hom_nay,
            )
        danh_muc = await conn.fetch(
            """
            SELECT id::text, name_base, variant FROM public.drug_catalog
             WHERE clinic_id = $1::uuid AND is_active
             ORDER BY name_base, variant NULLS FIRST
            """,
            identity.clinic_id,
        )

    lan_thu = {
        r["visit_id"]: LanThu(
            payment_cycle_id=r["payment_cycle_id"],
            status=r["status"],
            method=r["method"],
            legacy=bool(r["legacy"]),
            can_doi_soat=bool(r["can_doi_soat"]),
        )
        for r in lan_thu_rows
    }
    pl_theo_dong: dict[str, list[asyncpg.Record]] = {}
    for p in phan_lo:
        pl_theo_dong.setdefault(p["prescription_id"], []).append(p)
    lo_theo_thuoc: dict[str, list[asyncpg.Record]] = {}
    for b in lo_rows:
        lo_theo_thuoc.setdefault(b["drug_catalog_id"], []).append(b)

    luot: dict[str, dict[str, Any]] = {}
    for r in dong:
        vid = r["visit_id"]
        lt = lan_thu.get(vid)
        if vid not in luot:
            luot[vid] = {
                "visit_id": vid,
                "ten_khach": r["ten_khach"],
                "patient_code": r["patient_code"],
                "phone": r["phone_primary"],
                "kham_xong": bool(r["kham_xong"]),
                "lan_thu": (
                    {
                        "payment_cycle_id": lt.payment_cycle_id,
                        "status": lt.status,
                        "method": lt.method,
                        "can_doi_soat": lt.can_doi_soat,
                    }
                    if lt
                    else None
                ),
                "dong": [],
                "_rows": [],
            }
        luot[vid]["_rows"].append(r)

    for vid, g in luot.items():
        lt = lan_thu.get(vid)
        bound = [
            p
            for r in g["_rows"]
            for p in pl_theo_dong.get(r["id"], [])
            if lt is not None and p["payment_cycle_id"] == lt.payment_cycle_id
        ]
        gd = giai_doan(
            kham_xong=g["kham_xong"],
            lan_thu=lt,
            co_phan_lo_chua_ban=any(not p["da_ban"] for p in bound),
        )
        g["giai_doan"] = gd
        for r in g.pop("_rows"):
            g["dong"].append(
                _dong(r, gd, lt, pl_theo_dong, lo_theo_thuoc, lo_cu, co_quyen_ghi)
            )
    return {
        "luot": list(luot.values()),
        "danh_muc": [dict(d) for d in danh_muc],
        "hom_nay": hom_nay.isoformat(),
        "co_quyen_ghi": co_quyen_ghi,
    }


def _dong(
    r: asyncpg.Record,
    gd: str,
    lt: LanThu | None,
    pl_theo_dong: dict[str, list[asyncpg.Record]],
    lo_theo_thuoc: dict[str, list[asyncpg.Record]],
    lo_cu: list[asyncpg.Record],
    co_quyen_ghi: bool,
) -> dict[str, Any]:
    ke = r["quantity_num"]
    ban = r["purchased_qty"] if r["purchased_qty"] is not None else ke
    da_giao = _so(r["dispensed_qty"])
    # Phần phải có lô = số bán − phần đã cấp theo luồng cũ (xem
    # phan_lo_service.can_theo_hoa_don). Chỉ có nghĩa trước khi thu.
    can_lo = max(_so(ban) - da_giao, Decimal(0)) if ban is not None else Decimal(0)
    cac_pl = pl_theo_dong.get(r["id"], [])
    da_chon = sum((_so(p["quantity"]) for p in cac_pl), Decimal(0))
    da_chot = r["closed_at"] is not None
    ds_pl = []
    for p in cac_pl:
        gan = p["payment_cycle_id"] is not None
        con = _so(p["quantity"]) - _so(p["handed_over_qty"])
        ds_pl.append(
            {
                "allocation_id": p["id"],
                "drug_batch_id": p["drug_batch_id"],
                "batch_code": p["batch_code"],
                "expiry_date": p["expiry_date"],
                "quantity": _so(p["quantity"]),
                "handed_over_qty": _so(p["handed_over_qty"]),
                "con_giao": con,
                "dang_giu": gan and gd == CHO_XAC_MINH,
                "da_ban": bool(p["da_ban"]),
                "thao_tac": thao_tac_phan_lo(
                    gd=gd,
                    dong_da_chot=da_chot,
                    gan_lan_thu=gan
                    and lt is not None
                    and p["payment_cycle_id"] == lt.payment_cycle_id,
                    da_ban=bool(p["da_ban"]),
                    con_giao=con,
                    co_quyen_ghi=co_quyen_ghi,
                ),
            }
        )
    lo_goi_y = []
    ung_vien: list[asyncpg.Record] = []
    if r["drug_catalog_id"]:
        ung_vien = lo_theo_thuoc.get(r["drug_catalog_id"], [])
    elif gd == DA_THU_CU:
        ten = (r["drug_name_raw"] or "").strip().lower()
        ung_vien = [
            b
            for b in lo_cu
            if ten
            and any(x and (x in ten or ten in x) for x in (b["ten_a"], b["ten_b"]))
        ]
    if ung_vien:
        dv = _don_vi(r["unit"])
        for b in ung_vien:
            # Luồng mới: chỉ lô cùng đơn vị kê. Luồng cũ (legacy) giữ luật cũ:
            # đơn thiếu đơn vị thì hiểu theo đơn vị lô.
            if dv and _don_vi(b["unit"]) != dv:
                continue
            lo_goi_y.append(
                {
                    "drug_batch_id": b["id"],
                    "batch_code": b["batch_code"],
                    "expiry_date": b["expiry_date"],
                    "unit": b["unit"],
                    "ton_vat_ly": _so(b["quantity_on_hand"]),
                    "co_the_phan_lo": _so(b["co_the_phan_lo"]),
                }
            )
    return {
        "id": r["id"],
        "drug_name_raw": r["drug_name_raw"],
        "quantity_text": r["quantity"],
        "quantity_num": ke,
        "unit": r["unit"],
        "purchased_qty": r["purchased_qty"],
        "dispensed_qty": da_giao,
        "dispense_status": r["dispense_status"],
        "closed": da_chot,
        "refusal_reason": r["refusal_reason"],
        "dosage_instructions": r["dosage_instructions"],
        "drug_catalog_id": r["drug_catalog_id"],
        "ten_thuoc_kho": r["ten_thuoc_kho"],
        "can_lo": can_lo,
        "da_chon": da_chon,
        "phan_lo": ds_pl,
        "lo_goi_y": lo_goi_y,
        "thao_tac": thao_tac_dong(
            gd=gd,
            dong_da_chot=da_chot,
            da_giao=da_giao,
            co_thuoc_kho=r["drug_catalog_id"] is not None,
            co_don_vi=bool(_don_vi(r["unit"])),
            co_so_ke=ke is not None,
            can_lo=can_lo,
            da_chon=da_chon,
            co_phan_lo=bool(cac_pl),
            so_ban=_so(ban) if ban is not None else None,
            co_quyen_ghi=co_quyen_ghi,
        ),
    }


__all__ = ["man_nha_thuoc", "giai_doan", "thao_tac_dong", "thao_tac_phan_lo"]
