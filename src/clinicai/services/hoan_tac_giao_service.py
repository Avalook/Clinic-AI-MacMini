"""Hoàn tác GIAO thuốc (Tuyền 31/10/2026): thuốc đã giao về quầy, sổ kho đồng bộ.

Hai cửa, một đường ghi:

* nút "Hoàn tác giao" ở từng lần giao — tiền giữ nguyên, giao lại được
  (`PharmacyService.hoan_tac_giao`, `PharmacyService.huy_dong_cho_gan_lo`);
* hoàn tác lần thu thuốc — mọi lần giao của lượt tự về quầy
  (`dao_giao_khi_huy_phieu`, gọi trong giao dịch của `void_payment`).

Sổ kho chỉ thêm: mỗi lần giao đảo bằng ĐÚNG MỘT dòng `DISPENSE_REVERSAL` trên
đúng lô đã giao (ép ở Postgres: `uq_inventory_txn_dao_giao_mot_lan`, trigger
`inventory_txn_ban_hop_le`). Phần khách đã trả đã về quầy bằng `RETURN_RECEIVED`
nên không đảo lại; thuốc trả chờ kiểm giữ nguyên.

Hai lối khác nhau một điểm: Hoàn tác giao giữ lần thu, nên phần khách đã trả vẫn
tính vào `dispensed_qty` (đã bán, đã giao một lần) — số còn phải giao = số đảo.
Hoàn tác lần thu thì không còn gì đã bán: dòng đơn về chưa giao hẳn.

Dòng đơn đã chốt được mở lại (trừ dòng khách từ chối và dòng lịch sử): còn thuốc
phải giao thì dòng phải giao được. Lô hết hạn vẫn nhận thuốc về — đó là sự thật
trên kệ; bán tiếp hay huỷ do kho quyết, không phải lệnh này.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.events import emit_event, nguoi
from clinicai.events.catalogue import ThuocHoanTacGiao


@dataclass(frozen=True)
class LanGiao:
    id: str
    prescription_id: str
    drug_batch_id: str
    allocation_id: str | None
    payment_cycle_id: str | None
    da_xuat: Decimal
    da_tra: Decimal

    @property
    def con(self) -> Decimal:
        """Phần còn ở tay khách = đã xuất − khách đã trả."""
        return self.da_xuat - self.da_tra


async def cac_lan_giao(
    conn: asyncpg.Connection, clinic_id: str, rx_ids: list[str]
) -> list[LanGiao]:
    """Các lần giao CHƯA hoàn tác của những dòng đơn này."""
    rows = await conn.fetch(
        """
        SELECT t.id::text, t.ref_id::text AS prescription_id,
               t.drug_batch_id::text, t.allocation_id::text,
               t.payment_cycle_id::text, -t.quantity AS da_xuat,
               coalesce((SELECT sum(r.returned_qty) FROM public.drug_return r
                          WHERE r.clinic_id = t.clinic_id
                            AND r.original_dispense_txn_id = t.id), 0) AS da_tra
          FROM public.inventory_txn t
         WHERE t.clinic_id = $1::uuid AND t.txn_type = 'DISPENSE'
           AND t.ref_type = 'prescription' AND t.ref_id = ANY($2::uuid[])
           AND NOT EXISTS (SELECT 1 FROM public.inventory_txn x
                            WHERE x.txn_type = 'DISPENSE_REVERSAL'
                              AND x.reverses_txn_id = t.id)
         ORDER BY t.performed_at, t.id
        """,
        clinic_id,
        rx_ids,
    )
    return [
        LanGiao(
            id=r["id"],
            prescription_id=r["prescription_id"],
            drug_batch_id=r["drug_batch_id"],
            allocation_id=r["allocation_id"],
            payment_cycle_id=r["payment_cycle_id"],
            da_xuat=Decimal(str(r["da_xuat"])),
            da_tra=Decimal(str(r["da_tra"])),
        )
        for r in rows
    ]


async def ghi_dong_dao(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    staff_id: str,
    lan: LanGiao,
    ly_do: str,
) -> None:
    """Một dòng `DISPENSE_REVERSAL` cho phần còn ở tay khách. Tồn tự cộng qua
    trigger `inventory_txn_apply`. Khách trả hết rồi thì không có gì để đảo."""
    if lan.con <= 0:
        return
    await conn.execute(
        """
        INSERT INTO public.inventory_txn
            (clinic_id, drug_batch_id, txn_type, quantity, reason, ref_type, ref_id,
             performed_by_staff_id, performed_at, payment_cycle_id, allocation_id,
             reverses_txn_id)
        VALUES ($1::uuid, $2::uuid, 'DISPENSE_REVERSAL', $3, $4, 'prescription',
                $5::uuid, $6::uuid, now(), $7::uuid, $8::uuid, $9::uuid)
        """,
        clinic_id,
        lan.drug_batch_id,
        lan.con,
        ly_do,
        lan.prescription_id,
        staff_id,
        lan.payment_cycle_id,
        lan.allocation_id,
        lan.id,
    )


async def giam_da_giao(
    conn: asyncpg.Connection, *, clinic_id: str, prescription_id: str, so: Decimal
) -> asyncpg.Record:
    """Giảm `dispensed_qty`; về 0 thì xoá dấu người / giờ giao
    (`prescription_cap_thi_co_dau_vet`). Mở lại dòng đã chốt — trừ dòng khách từ
    chối và dòng lịch sử (bất biến)."""
    moi: asyncpg.Record = await conn.fetchrow(
        """
        UPDATE public.prescription
           SET dispensed_qty = greatest(dispensed_qty - $3, 0),
               dispensed_at = CASE WHEN dispensed_qty - $3 > 0 THEN dispensed_at END,
               dispensed_by_staff_id =
                   CASE WHEN dispensed_qty - $3 > 0 THEN dispensed_by_staff_id END,
               closed_at = CASE WHEN removed_at IS NULL AND refusal_reason IS NULL
                                THEN NULL ELSE closed_at END,
               updated_at = now()
         WHERE id = $1::uuid AND clinic_id = $2::uuid
         /* rx:gom-ca-lich-su: thuốc đã giao ở dòng đã đính chính cũng về quầy */
        RETURNING dispensed_qty, dispense_status
        """,
        prescription_id,
        clinic_id,
        so,
    )
    return moi


async def huy_cho_gan_lo(
    conn: asyncpg.Connection,
    *,
    clinic_id: str,
    staff_id: str,
    ly_do: str,
    prescription_ids: list[str] | None = None,
    dong_id: str | None = None,
) -> dict[str, Decimal]:
    """Huỷ (giữ vết) dòng chờ gán lô — chúng chưa vào sổ kho nên không cần dòng
    đảo. Trả rx → tổng số đã huỷ."""
    rows = await conn.fetch(
        """
        UPDATE public.thuoc_giao_chua_gan_lo
           SET huy_luc = now(), huy_boi = $2::uuid, huy_ly_do = $3
         WHERE clinic_id = $1::uuid AND drug_batch_id IS NULL AND huy_luc IS NULL
           AND (prescription_id = ANY($4::uuid[]) OR id = $5::uuid)
        RETURNING prescription_id::text, so_luong
        """,
        clinic_id,
        staff_id,
        ly_do,
        prescription_ids or [],
        dong_id,
    )
    ra: dict[str, Decimal] = {}
    for r in rows:
        ra[r["prescription_id"]] = ra.get(r["prescription_id"], Decimal(0)) + Decimal(
            str(r["so_luong"])
        )
    return ra


async def phat_hoan_tac_giao(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    visit_id: str,
    prescription_id: str,
    so_luong: Decimal,
    so_da_giao: Any,
    ly_do: str,
) -> None:
    """`medicine.dispense_undone`: hành trình và sổ nợ đọc lại, không còn báo
    khách đã nhận thuốc."""
    await emit_event(
        conn,
        ten="medicine.dispense_undone",
        clinic_id=identity.clinic_id,
        aggregate_id=prescription_id,
        payload=ThuocHoanTacGiao(
            visit_id=visit_id,
            prescription_id=prescription_id,
            so_luong=str(so_luong),
            so_da_giao=str(so_da_giao),
            ly_do=ly_do,
        ),
        boi=nguoi(identity),
        correlation_id=visit_id,
    )


async def dao_giao_khi_huy_phieu(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    visit_id: str,
    payment_cycle_id: str,
    ly_do: str,
) -> dict[str, Any]:
    """Hoàn tác lần thu thuốc: mọi thuốc đã giao của lượt về quầy, dòng đơn về
    chưa giao. Người gọi ĐÃ khoá lượt → dòng đơn → phân lô → lô
    (`khoa_ban_thuoc`), nên không lần giao / lần trả nào chen vào được.

    Trả ``{"so_dong", "so_luong"}`` — số dòng đơn và tổng số thực sự về quầy
    (không tính phần khách đã trả từ trước)."""
    cid = identity.clinic_id
    rx_ids = [
        str(r["id"])
        for r in await conn.fetch(
            "SELECT id FROM public.prescription"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " /* rx:gom-ca-lich-su: dòng đã đính chính vẫn có thuốc đã giao */",
            cid,
            visit_id,
        )
    ]
    if not rx_ids:
        return {"so_dong": 0, "so_luong": Decimal(0)}
    cau = f"Hoàn tác lần thu: {ly_do}"[:500]
    cho = await huy_cho_gan_lo(
        conn,
        clinic_id=cid,
        staff_id=identity.staff_id,
        ly_do=cau,
        prescription_ids=rx_ids,
    )
    lan = await cac_lan_giao(conn, cid, rx_ids)
    ve: dict[str, Decimal] = dict(cho)
    for g in lan:
        await ghi_dong_dao(
            conn, clinic_id=cid, staff_id=identity.staff_id, lan=g, ly_do=cau
        )
        ve[g.prescription_id] = ve.get(g.prescription_id, Decimal(0)) + g.con
    # Không còn lần thu thì không còn nghĩa vụ giao: phân lô của lần thu này về 0
    # (kể cả phần khách đã trả) để `dao_ban` đảo trọn dòng bán và gỡ phân lô.
    await conn.execute(
        "UPDATE public.prescription_allocation SET handed_over_qty = 0"
        " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
        " AND released_at IS NULL AND handed_over_qty > 0",
        cid,
        payment_cycle_id,
    )
    con_ton = await conn.fetch(
        "SELECT id::text, dispensed_qty FROM public.prescription"
        " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND dispensed_qty > 0"
        " /* rx:gom-ca-lich-su: thuốc đã giao của dòng đã đính chính */",
        cid,
        visit_id,
    )
    for r in con_ton:
        await giam_da_giao(
            conn,
            clinic_id=cid,
            prescription_id=r["id"],
            so=Decimal(str(r["dispensed_qty"])),
        )
        await phat_hoan_tac_giao(
            conn,
            identity=identity,
            visit_id=visit_id,
            prescription_id=r["id"],
            so_luong=ve.get(r["id"], Decimal(0)),
            so_da_giao=0,
            ly_do=cau,
        )
    return {
        "so_dong": sum(1 for v in ve.values() if v > 0),
        "so_luong": sum(ve.values(), Decimal(0)),
    }
