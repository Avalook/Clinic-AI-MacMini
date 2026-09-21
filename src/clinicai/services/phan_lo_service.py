"""Phân lô và BÁN thuốc theo lần thu (contract tiền–thuốc CP3, 19/09/2026).

Thuốc được BÁN lúc lần thu tiền thuốc thành PAID — theo đúng các lô hệ thống đã
phân (`prescription_allocation`), đúng một lần theo `payment_cycle_id`.

Ba con số, không đổi nghĩa con số cũ:
  * `drug_batch.quantity_on_hand` — VẬT LÝ, chỉ đổi khi thuốc thật vào/ra
    (RECEIVE / DISPENSE / ADJUST / DISCARD).
  * `SALE` / `SALE_REVERSAL` — cam kết bán; không đổi tồn vật lý.
  * `drug_batch_kha_dung()` = vật lý − giữ cho lần chờ xác minh − đã bán chưa
    giao. Chỉ dùng để CHẶN BÁN QUÁ, chưa phải nhãn hiển thị (HOLD J6).

THỨ TỰ KHOÁ cho mọi thao tác chạm tiền thuốc hoặc phân lô:
    visit → prescription (theo id) → prescription_allocation (theo id)
          → drug_batch (theo id) → payment_cycle / payment
Hai lượt khác nhau chỉ gặp nhau ở `drug_batch`, và luôn khoá lô theo id tăng
dần trong MỘT câu lệnh — nên không khoá chéo nhau.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ValidationError


def so(d: Decimal) -> str:
    """Số lượng cho người đọc: `numeric(12,3)` in thẳng ra "6.000" — người
    Việt đọc thành sáu nghìn. Bỏ phần thập phân thừa."""
    t = format(d.normalize(), "f")
    return t


def _don_vi(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


@dataclass(frozen=True)
class PhanLo:
    id: str
    prescription_id: str
    drug_batch_id: str
    quantity: Decimal
    handed_over_qty: Decimal
    payment_cycle_id: str | None


def _pl(r: asyncpg.Record) -> PhanLo:
    return PhanLo(
        id=str(r["id"]),
        prescription_id=str(r["prescription_id"]),
        drug_batch_id=str(r["drug_batch_id"]),
        quantity=Decimal(str(r["quantity"])),
        handed_over_qty=Decimal(str(r["handed_over_qty"])),
        payment_cycle_id=(
            str(r["payment_cycle_id"]) if r["payment_cycle_id"] is not None else None
        ),
    )


async def khoa_lo(
    conn: asyncpg.Connection, *, clinic_id: str, lo_ids: list[str]
) -> None:
    """Khoá các lô theo id tăng dần, trong một câu lệnh."""
    if lo_ids:
        await conn.execute(
            "SELECT 1 FROM public.drug_batch WHERE clinic_id = $1::uuid"
            " AND id = ANY($2::uuid[]) ORDER BY id FOR UPDATE",
            clinic_id,
            sorted(set(lo_ids)),
        )


async def khoa_ban_thuoc(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    payment_cycle_id: str | None,
    khoa_cac_lo: bool = True,
) -> list[PhanLo]:
    """Người gọi ĐÃ khoá `visit`. Khoá tiếp dòng đơn → phân lô → lô.

    ``payment_cycle_id`` rỗng: phân lô còn hiệu lực CHƯA gắn lần thu (sắp thu).
    Có: phân lô còn hiệu lực đã gắn đúng lần thu ấy.
    """
    await conn.execute(
        "SELECT 1 FROM public.prescription WHERE clinic_id = $1::uuid"
        " AND visit_id = $2::uuid ORDER BY id FOR UPDATE"
        " /* rx:gom-ca-lich-su: khoá mọi dòng của lượt theo id (thứ tự khoá"
        " chung) — phân lô gắn lần thu của dòng đã đính chính cũng dưới khoá */",
        clinic_id,
        visit_id,
    )
    rows = await conn.fetch(
        """
        SELECT id, prescription_id, drug_batch_id, quantity, handed_over_qty,
               payment_cycle_id
          FROM public.prescription_allocation
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND released_at IS NULL
           AND payment_cycle_id IS NOT DISTINCT FROM $3::uuid
         ORDER BY id
           FOR UPDATE
        """,
        clinic_id,
        visit_id,
        payment_cycle_id,
    )
    phan_lo = [_pl(r) for r in rows]
    if khoa_cac_lo:
        await khoa_lo(
            conn, clinic_id=clinic_id, lo_ids=[p.drug_batch_id for p in phan_lo]
        )
    return phan_lo


async def van_de_phan_lo(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    can: dict[str, tuple[str, Decimal]],
    phan_lo: list[PhanLo],
    da_giu: bool,
    hom_nay: date,
) -> list[str]:
    """Vì sao chưa bán được theo các phân lô này (rỗng = bán được).

    ``can``: prescription_id → (tên thuốc, số phải có lô). ``da_giu``: các phân
    lô đang là phần giữ của chính lần thu này (đã trừ trong khả dụng).
    """
    van_de: list[str] = []
    theo_dong: dict[str, Decimal] = {}
    for p in phan_lo:
        if p.prescription_id in can:
            theo_dong[p.prescription_id] = (
                theo_dong.get(p.prescription_id, Decimal(0)) + p.quantity
            )
    for rx, (ten, can_so) in can.items():
        co = theo_dong.get(rx, Decimal(0))
        if co != can_so:
            van_de.append(
                f"“{ten}” mới phân lô {so(co)}/{so(can_so)} — chưa đủ lô để bán"
            )

    dung = [p for p in phan_lo if p.prescription_id in can]
    can_lo: dict[str, Decimal] = {}
    for p in dung:
        can_lo[p.drug_batch_id] = can_lo.get(p.drug_batch_id, Decimal(0)) + p.quantity
    if not can_lo:
        return van_de
    lo_rows = await conn.fetch(
        """
        SELECT id::text, batch_code, expiry_date,
               public.drug_batch_kha_dung($1::uuid, id) AS kha_dung
          FROM public.drug_batch
         WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
        """,
        clinic_id,
        list(can_lo),
    )
    for lo in lo_rows:
        can_so = can_lo[lo["id"]]
        if lo["expiry_date"] is not None and lo["expiry_date"] < hom_nay:
            van_de.append(f"lô {lo['batch_code']} đã hết hạn — chọn lô khác")
        kd = Decimal(str(lo["kha_dung"] or 0)) + (can_so if da_giu else Decimal(0))
        if kd < can_so:
            van_de.append(
                f"lô {lo['batch_code']} chỉ còn {so(max(kd, Decimal(0)))} có thể "
                "phân lô lúc này, "
                f"cần {so(can_so)} — chọn lô khác"
            )
    return van_de


async def can_theo_hoa_don(
    conn: asyncpg.Connection, *, clinic_id: str, dong: list[tuple[str, str, Decimal]]
) -> dict[str, tuple[str, Decimal]]:
    """Số phải có lô của từng dòng = số bán − số ĐÃ cấp theo luồng cũ.

    Trước CP3 thuốc được cấp (trừ tồn vật lý) không cần thu tiền trước. Phần
    ấy đã rời kho, bán nó không cần giữ lô nữa. Sau CP3 chưa thu thì không cấp
    được, nên với dòng chưa thu `dispensed_qty` chỉ có thể là phần cũ.
    """
    if not dong:
        return {}
    da_cap = {
        str(r["id"]): Decimal(str(r["dispensed_qty"] or 0))
        for r in await conn.fetch(
            "SELECT id, dispensed_qty FROM public.prescription"
            " WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])"
            " /* rx:gom-ca-lich-su: đọc theo id của hoá đơn / ảnh chụp lần thu —"
            " ảnh chụp có thể chứa dòng nay đã đính chính */",
            clinic_id,
            [rx for rx, _, _ in dong],
        )
    }
    ket_qua: dict[str, tuple[str, Decimal]] = {}
    for rx, ten, so in dong:
        con = so - da_cap.get(rx, Decimal(0))
        if con > 0:
            ket_qua[rx] = (ten, con)
    return ket_qua


async def tu_phan_lo(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    visit_id: str,
    staff_id: str,
    can: dict[str, tuple[str, Decimal]],
    phan_lo: list[PhanLo],
    hom_nay: date,
) -> list[PhanLo]:
    """Tự phân đủ lô FEFO cho các dòng của hoá đơn trong giao dịch hiện tại.

    Dòng đơn và ``prescription_allocation`` đã được người gọi khoá. Hàm khoá
    toàn bộ lô ứng viên theo ID trước khi đọc khả dụng, tái dùng phân lô đang
    sống và chỉ ghi sau khi đã lập được kế hoạch đủ cho mọi dòng.
    """
    if not can:
        return []

    don_rows = await conn.fetch(
        """
        SELECT id::text, drug_catalog_id::text, unit
          FROM public.prescription
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND id = ANY($3::uuid[])
         ORDER BY id
        """,
        clinic_id,
        visit_id,
        list(can),
    )
    don = {r["id"]: r for r in don_rows}
    for rx, (ten, _) in can.items():
        row = don.get(rx)
        if row is None or row["drug_catalog_id"] is None:
            raise ValidationError(
                f"“{ten}” chưa gắn đúng thuốc catalog — chưa tự phân lô được."
            )
        if not _don_vi(row["unit"]):
            raise ValidationError(
                f"“{ten}” chưa có đơn vị kê — không tự quy đổi đơn vị."
            )

    catalog_ids = sorted({r["drug_catalog_id"] for r in don_rows})
    ung_vien_ids = [
        str(batch_id)
        for batch_id in await conn.fetchval(
            """
            SELECT coalesce(array_agg(id ORDER BY id), ARRAY[]::uuid[])
              FROM public.drug_batch
             WHERE clinic_id = $1::uuid
               AND drug_catalog_id = ANY($2::uuid[])
               AND expiry_date >= $3
            """,
            clinic_id,
            catalog_ids,
            hom_nay,
        )
    ]
    tat_ca_lo = ung_vien_ids + [p.drug_batch_id for p in phan_lo]
    await khoa_lo(conn, clinic_id=clinic_id, lo_ids=tat_ca_lo)

    lo_rows = await conn.fetch(
        """
        SELECT id::text, drug_catalog_id::text, batch_code, expiry_date, unit,
               public.drug_batch_kha_dung($1::uuid, id) AS kha_dung
          FROM public.drug_batch
         WHERE clinic_id = $1::uuid AND id = ANY($2::uuid[])
         ORDER BY expiry_date, batch_code
        """,
        clinic_id,
        sorted(set(tat_ca_lo)),
    )
    lo_theo_id = {r["id"]: r for r in lo_rows}
    dang_dung = [p for p in phan_lo if p.prescription_id in can]
    da_phan: dict[str, Decimal] = {}
    da_dung_lo: dict[str, Decimal] = {}
    allocation_theo_dong_lo: dict[tuple[str, str], PhanLo] = {}

    for p in dang_dung:
        row = don[p.prescription_id]
        lo = lo_theo_id.get(p.drug_batch_id)
        ten = can[p.prescription_id][0]
        if (
            lo is None
            or lo["drug_catalog_id"] != row["drug_catalog_id"]
            or _don_vi(lo["unit"]) != _don_vi(row["unit"])
            or lo["expiry_date"] is None
            or lo["expiry_date"] < hom_nay
        ):
            raise ValidationError(
                f"Phân lô hiện tại của “{ten}” không còn hợp lệ về thuốc, "
                "hạn dùng hoặc đơn vị."
            )
        da_phan[p.prescription_id] = (
            da_phan.get(p.prescription_id, Decimal(0)) + p.quantity
        )
        da_dung_lo[p.drug_batch_id] = (
            da_dung_lo.get(p.drug_batch_id, Decimal(0)) + p.quantity
        )
        allocation_theo_dong_lo[(p.prescription_id, p.drug_batch_id)] = p

    con_lai = {
        r["id"]: Decimal(str(r["kha_dung"] or 0)) - da_dung_lo.get(r["id"], Decimal(0))
        for r in lo_rows
    }
    ke_hoach: list[tuple[str, str, Decimal]] = []
    thay_phan_lo: dict[str, tuple[str, str, Decimal]] = {}
    for rx in sorted(can):
        ten, can_so = can[rx]
        co = da_phan.get(rx, Decimal(0))
        if co > can_so:
            raise ValidationError(
                f"“{ten}” đã phân lô {so(co)}, vượt số cần bán {so(can_so)}."
            )
        thieu = can_so - co
        row = don[rx]
        cung_thuoc_con_han = [
            lo
            for lo in lo_rows
            if lo["drug_catalog_id"] == row["drug_catalog_id"]
            and lo["expiry_date"] is not None
            and lo["expiry_date"] >= hom_nay
        ]
        cung_don_vi = [
            lo
            for lo in cung_thuoc_con_han
            if _don_vi(lo["unit"]) == _don_vi(row["unit"])
        ]
        for lo in cung_don_vi:
            if thieu <= 0:
                break
            co_the_dung = max(con_lai[lo["id"]], Decimal(0))
            lay = min(thieu, co_the_dung)
            if lay > 0:
                hien_co = allocation_theo_dong_lo.get((rx, lo["id"]))
                if hien_co is None:
                    ke_hoach.append((rx, lo["id"], lay))
                else:
                    # Allocation là sổ bất biến. Nếu kế hoạch cũ mới có một
                    # phần trên chính lô này, đóng dòng cũ rồi tạo một dòng
                    # sống thay thế đủ số; allocation đã đủ được reuse nguyên.
                    thay_phan_lo[hien_co.id] = (
                        rx,
                        lo["id"],
                        hien_co.quantity + lay,
                    )
                con_lai[lo["id"]] -= lay
                thieu -= lay
        if thieu > 0:
            if not cung_thuoc_con_han:
                ly_do = "không có lô còn hạn"
            elif not cung_don_vi:
                ly_do = f"không có lô cùng đơn vị {row['unit']}"
            else:
                ly_do = f"không đủ tồn còn bán được, thiếu {so(thieu)}"
            raise ValidationError(f"“{ten}” {ly_do}.")

    if thay_phan_lo:
        await conn.execute(
            "UPDATE public.prescription_allocation"
            " SET released_at = now(), released_by = $2::uuid,"
            " release_reason = 'Hệ thống hoàn tất tự phân lô'"
            " WHERE clinic_id = $1::uuid AND id = ANY($3::uuid[])"
            " AND payment_cycle_id IS NULL AND released_at IS NULL",
            clinic_id,
            staff_id,
            list(thay_phan_lo),
        )
    tao = ke_hoach + list(thay_phan_lo.values())
    if tao:
        await conn.executemany(
            """
            INSERT INTO public.prescription_allocation
                (clinic_id, visit_id, prescription_id, drug_catalog_id,
                 drug_batch_id, quantity, created_by)
            SELECT $1::uuid, $2::uuid, r.id, r.drug_catalog_id, $4::uuid, $5,
                   $6::uuid
              FROM public.prescription r
             WHERE r.id = $3::uuid AND r.clinic_id = $1::uuid
            """,
            [
                (clinic_id, visit_id, rx, batch_id, quantity, staff_id)
                for rx, batch_id, quantity in tao
            ],
        )
    rows = await conn.fetch(
        """
        SELECT id, prescription_id, drug_batch_id, quantity, handed_over_qty,
               payment_cycle_id
          FROM public.prescription_allocation
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND prescription_id = ANY($3::uuid[])
           AND released_at IS NULL AND payment_cycle_id IS NULL
         ORDER BY id
           FOR UPDATE
        """,
        clinic_id,
        visit_id,
        list(can),
    )
    return [_pl(r) for r in rows]


async def gan_lan_thu(
    conn: asyncpg.Connection, *, clinic_id: str, cycle_id: str, phan_lo: list[PhanLo]
) -> None:
    if phan_lo:
        await conn.execute(
            "UPDATE public.prescription_allocation SET payment_cycle_id = $2::uuid"
            " WHERE clinic_id = $1::uuid AND id = ANY($3::uuid[])"
            " AND payment_cycle_id IS NULL AND released_at IS NULL",
            clinic_id,
            cycle_id,
            [p.id for p in phan_lo],
        )


async def ghi_ban(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    cycle_id: str,
    staff_id: str,
    phan_lo: list[PhanLo],
) -> None:
    """Một dòng SALE cho mỗi phân lô của lần thu. Chỉ mục duy nhất ở DB đảm bảo
    đúng một lần; ON CONFLICT để lần gọi lại là không đổi gì, không phải lỗi."""
    await conn.executemany(
        """
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
             ref_id, performed_by_staff_id, performed_at, payment_cycle_id,
             allocation_id)
        VALUES ($1::uuid, $2::uuid, 'SALE', $3, NULL, 'payment_cycle',
                $4::uuid, $5::uuid, now(), $4::uuid, $6::uuid)
        ON CONFLICT (payment_cycle_id, allocation_id) WHERE txn_type = 'SALE'
        DO NOTHING
        """,
        [
            (clinic_id, p.drug_batch_id, -p.quantity, cycle_id, staff_id, p.id)
            for p in phan_lo
        ],
    )


async def go_va_giu_ke_hoach(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    staff_id: str,
    ly_do: str,
    phan_lo: list[PhanLo],
) -> None:
    """Gỡ các phân lô đã gắn lần thu (dòng cũ giữ làm lịch sử) và chép lại thành
    phân lô CHƯA gắn — để lần thu sau không phải chọn lại lô. Dòng đơn đã chốt
    thì không chép."""
    if not phan_lo:
        return
    ids = [p.id for p in phan_lo]
    await conn.execute(
        "UPDATE public.prescription_allocation"
        " SET released_at = now(), released_by = $2::uuid, release_reason = $3"
        " WHERE clinic_id = $1::uuid AND id = ANY($4::uuid[]) AND released_at IS NULL",
        clinic_id,
        staff_id,
        ly_do,
        ids,
    )
    await conn.execute(
        """
        INSERT INTO public.prescription_allocation
            (clinic_id, visit_id, prescription_id, drug_catalog_id, drug_batch_id,
             quantity, created_by)
        SELECT a.clinic_id, a.visit_id, a.prescription_id, a.drug_catalog_id,
               a.drug_batch_id, a.quantity, $2::uuid
          FROM public.prescription_allocation a
          JOIN public.prescription r
            ON r.id = a.prescription_id AND r.clinic_id = a.clinic_id
         WHERE a.clinic_id = $1::uuid AND a.id = ANY($3::uuid[])
           AND r.closed_at IS NULL
           -- CP6: dòng đã đính chính (lịch sử) không nhận kế hoạch lô mới —
           -- nhả hẳn, không chép lại.
           AND r.removed_at IS NULL
           AND r.drug_catalog_id = a.drug_catalog_id
         ORDER BY a.id
        """,
        clinic_id,
        staff_id,
        ids,
    )


async def dao_ban(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    cycle_id: str,
    staff_id: str,
    ly_do: str,
    phan_lo: list[PhanLo],
) -> list[str]:
    """Huỷ phiếu thu thuốc: đảo bán những dòng đơn CHƯA giao gì.

    Dòng đã giao một phần/toàn bộ: KHÔNG cộng lại kho, không gỡ phân lô — trả
    về prescription_id để ghi "cần xử lý trả thuốc" (CP5). Trả danh sách ấy.
    """
    da_giao = {p.prescription_id for p in phan_lo if p.handed_over_qty > 0}
    dao = [p for p in phan_lo if p.prescription_id not in da_giao]
    if dao:
        await conn.execute(
            """
            INSERT INTO public.inventory_txn
                (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type,
                 ref_id, performed_by_staff_id, performed_at, payment_cycle_id,
                 allocation_id, reverses_txn_id)
            SELECT s.clinic_id, s.drug_batch_id, 'SALE_REVERSAL', -s.quantity, $4,
                   'payment_cycle', s.payment_cycle_id, $3::uuid, now(),
                   s.payment_cycle_id, s.allocation_id, s.id
              FROM public.inventory_txn s
             WHERE s.clinic_id = $1::uuid AND s.payment_cycle_id = $2::uuid
               AND s.txn_type = 'SALE' AND s.allocation_id = ANY($5::uuid[])
               AND NOT EXISTS (SELECT 1 FROM public.inventory_txn r
                                WHERE r.txn_type = 'SALE_REVERSAL'
                                  AND r.reverses_txn_id = s.id)
             ORDER BY s.id
            """,
            clinic_id,
            cycle_id,
            staff_id,
            ly_do,
            [p.id for p in dao],
        )
        await go_va_giu_ke_hoach(
            conn, clinic_id=clinic_id, staff_id=staff_id, ly_do=ly_do, phan_lo=dao
        )
    return sorted(da_giao)


def gom_loi(van_de: list[str]) -> str:
    return "; ".join(van_de)


def tom_tat(phan_lo: list[PhanLo]) -> list[dict[str, Any]]:
    return [
        {
            "allocation_id": p.id,
            "prescription_id": p.prescription_id,
            "drug_batch_id": p.drug_batch_id,
            "quantity": str(p.quantity),
        }
        for p in phan_lo
    ]


async def ban_chua_giao(
    conn: asyncpg.Connection, clinic_id: str, prescription_ids: list[str]
) -> dict[str, dict[str, Decimal]]:
    """Phần ĐÃ BÁN MÀ CHƯA GIAO theo dòng đơn, và phần còn thiếu căn cứ để huỷ.

    Trả prescription_id → {"chua_giao", "can_hoan"}. `can_hoan` = phần chưa
    giao mà chưa có căn cứ tài chính (lần thu chưa huỷ phiếu và chưa hoàn tiền
    xong đủ) — cùng luật với trigger `inventory_txn_ban_hop_le`.
    """
    if not prescription_ids:
        return {}
    rows = await conn.fetch(
        """
        WITH ban AS (
            SELECT a.prescription_id, s.payment_cycle_id,
                   -s.quantity - coalesce((
                       SELECT -sum(d.quantity) FROM public.inventory_txn d
                        WHERE d.txn_type = 'DISPENSE' AND d.allocation_id = a.id
                          AND d.clinic_id = a.clinic_id), 0) AS chua_giao
              FROM public.prescription_allocation a
              JOIN public.inventory_txn s
                ON s.allocation_id = a.id AND s.clinic_id = a.clinic_id
               AND s.txn_type = 'SALE'
             WHERE a.clinic_id = $1::uuid AND a.prescription_id = ANY($2::uuid[])
               AND NOT EXISTS (SELECT 1 FROM public.inventory_txn r
                                WHERE r.txn_type = 'SALE_REVERSAL'
                                  AND r.reverses_txn_id = s.id)
        ), theo_lan AS (
            SELECT prescription_id, payment_cycle_id, sum(chua_giao) AS chua_giao
              FROM ban WHERE chua_giao > 0
             GROUP BY prescription_id, payment_cycle_id
        )
        SELECT t.prescription_id::text, t.chua_giao,
               CASE WHEN c.status = 'VOIDED' THEN 0
                    ELSE greatest(t.chua_giao - (
                        coalesce((
                            SELECT sum(l.quantity)
                              FROM public.payment_refund_line l
                              JOIN public.payment_refund r
                                ON r.refund_id = l.refund_id
                               AND r.clinic_id = l.clinic_id
                              JOIN public.payment_bill_line b
                                ON b.id = l.payment_bill_line_id
                               AND b.clinic_id = l.clinic_id
                             WHERE l.clinic_id = $1::uuid
                               AND l.payment_cycle_id = t.payment_cycle_id
                               AND r.status = 'COMPLETED'
                               AND b.source_type = 'prescription'
                               AND b.source_id = t.prescription_id::text), 0)
                        - coalesce((
                            SELECT sum(x.quantity) FROM public.inventory_txn x
                              JOIN public.prescription_allocation a2
                                ON a2.id = x.allocation_id
                               AND a2.clinic_id = x.clinic_id
                             WHERE x.clinic_id = $1::uuid
                               AND x.txn_type = 'SALE_REVERSAL'
                               AND x.payment_cycle_id = t.payment_cycle_id
                               AND a2.prescription_id = t.prescription_id), 0)), 0)
               END AS can_hoan
          FROM theo_lan t
          JOIN public.payment_cycle c
            ON c.payment_cycle_id = t.payment_cycle_id AND c.clinic_id = $1::uuid
        """,
        clinic_id,
        prescription_ids,
    )
    ket_qua: dict[str, dict[str, Decimal]] = {}
    for r in rows:
        k = ket_qua.setdefault(
            r["prescription_id"], {"chua_giao": Decimal(0), "can_hoan": Decimal(0)}
        )
        k["chua_giao"] += Decimal(str(r["chua_giao"]))
        k["can_hoan"] += Decimal(str(r["can_hoan"]))
    return ket_qua


async def chua_giao_cua_dong(
    conn: asyncpg.Connection, clinic_id: str, prescription_id: str
) -> Decimal:
    k = (await ban_chua_giao(conn, clinic_id, [prescription_id])).get(prescription_id)
    return k["chua_giao"] if k else Decimal(0)
