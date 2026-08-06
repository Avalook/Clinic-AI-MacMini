"""Đường GHI của nhà thuốc: nhập lô, cấp phát, điều chỉnh, huỷ.

VÌ SAO FILE NÀY ĐƯỢC VIẾT.

Nhà thuốc là một cái kho xây xong vỏ mà chưa có cửa vào. Lược đồ đầy đủ và chặt
— `drug_batch`, `inventory_txn` chỉ-thêm, trigger cộng dồn tồn, CHECK chặn tồn
âm — bốn màn hình chạy được, vai PHARMACIST có tài khoản thật. Nhưng đo trên
production ngày 07/08/2026: **không một dòng Python nào chạm tới ba bảng ấy**,
không router nào tên pharmacy, và RLS chỉ cấp SELECT cho `authenticated`. Kết
quả: dược sĩ mở màn kho thấy một cái bảng rỗng và không có nút nào để nhập
hàng. `drug_batch` 0 dòng, `inventory_txn` 0 dòng — vĩnh viễn.

BA TÌNH HUỐNG QUANG MÔ TẢ, MỘT MÔ HÌNH.

Bệnh nhân mua thuốc, không mua, hoặc mua một phần. Cả ba đi qua cùng một đường:
`cap_phat()` cộng vào `prescription.dispensed_qty` và ghi một dòng DISPENSE vào
sổ kho. "Không mua" là `tu_choi()`. "Lấy 5 rồi thôi" là cấp 5 rồi `chot()`.
Trạng thái không phải một cột ghi tay mà được TÍNH từ hai con số ấy
(`dispense_status`, migration 20260807000004) — nên không có trạng thái nào tồn
tại mà lệch với số liệu.

RANH GIỚI VỚI DATABASE.

Database đã chặn những điều không được phép: tồn không xuống âm
(`drug_batch_qty_non_negative`), sổ không sửa được (`inventory_txn_append_only`),
lô phải cùng phòng khám (trigger `inventory_txn_apply` ném lỗi), dấu của số
lượng phải khớp loại giao dịch. File này KHÔNG dựng lại những chốt ấy — nó nói
trước chúng, bằng tiếng Việt, để dược sĩ đọc được câu từ chối thay vì một lỗi
ràng buộc Postgres.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

# Loại giao dịch kho, đúng bốn giá trị mà `inventory_txn_type_check` canh.
# Khai lại ở đây để một lỗi gõ bị bắt ở Python, trước khi nó thành một lỗi
# ràng buộc khó đọc từ Postgres.
NHAP = "RECEIVE"
CAP = "DISPENSE"
DIEU_CHINH = "ADJUST"
HUY = "DISCARD"


def _so(value: Any, *, ten: str) -> Decimal:
    """Ép về số dương. Câu từ chối nói rõ ô nào sai, không nói 'invalid input'."""
    try:
        so = Decimal(str(value))
    except Exception as exc:  # noqa: BLE001 — mọi kiểu rác đều về một câu
        raise ValidationError(f"{ten} phải là một con số.") from exc
    if so <= 0:
        raise ValidationError(f"{ten} phải lớn hơn 0.")
    return so


class PharmacyService:
    """Kho thuốc và cấp phát theo đơn. Mọi ghi đi qua đây."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────────

    async def hang_doi(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Đơn thuốc CHƯA CHỐT, gom theo lượt khám.

        Lọc theo `closed_at IS NULL` chứ không theo `dispense_status`: một đơn
        đã cấp một phần vẫn còn việc, còn một đơn khách từ chối thì đã xong.
        Trạng thái trả kèm để màn hình vẽ, không dùng để lọc.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text,
                       r.visit_id::text,
                       r.clinic_patient_id::text,
                       p.full_name      AS patient_name,
                       p.patient_code,
                       r.drug_name_raw,
                       r.quantity       AS quantity_text,
                       r.quantity_num,
                       r.unit,
                       r.dispensed_qty,
                       r.dispense_status,
                       r.dosage_instructions,
                       r.caution,
                       r.created_at
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                 WHERE r.clinic_id = $1::uuid
                   AND r.closed_at IS NULL
                 ORDER BY r.created_at DESC
                 LIMIT 300
                """,
                identity.clinic_id,
            )
        return [dict(r) for r in rows]

    async def ton_kho(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Tồn theo lô, kèm hạn dùng. Lô hết sạch vẫn hiện — nó là lịch sử."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT b.id::text,
                       b.drug_catalog_id::text,
                       c.name_base,
                       c.variant,
                       c.group_label,
                       b.batch_code,
                       b.expiry_date,
                       b.quantity_on_hand,
                       b.unit,
                       b.cost_price,
                       b.received_at,
                       (b.expiry_date IS NOT NULL
                        AND b.expiry_date < current_date) AS het_han
                  FROM public.drug_batch b
                  LEFT JOIN public.drug_catalog c
                    ON c.id = b.drug_catalog_id
                 WHERE b.clinic_id = $1::uuid
                 ORDER BY b.expiry_date NULLS LAST, c.name_base
                """,
                identity.clinic_id,
            )
        return [dict(r) for r in rows]

    # ── Ghi ────────────────────────────────────────────────────────────────

    async def nhap_lo(
        self,
        *,
        identity: StaffIdentity,
        drug_catalog_id: str,
        so_luong: Any,
        batch_code: str,
        expiry_date: date,
        unit: str,
        cost_price: Any = None,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        """Nhập một lô vào kho. Tạo lô nếu chưa có, rồi ghi một dòng RECEIVE.

        SỐ LÔ, HẠN DÙNG VÀ ĐƠN VỊ ĐỀU BẮT BUỘC — `drug_batch` khai cả ba là
        NOT NULL. Không phải thủ tục giấy tờ: thuốc không có hạn dùng trong sổ
        là thuốc không ai biết khi nào phải bỏ, và một lô không có số thì lúc
        thu hồi không tra ra được đã cấp cho ai.

        Tồn kho KHÔNG được cộng thẳng vào `drug_batch`: trigger
        `inventory_txn_apply` làm việc đó từ dòng sổ. Cộng tay ở đây sẽ cho ra
        một số dư mà sổ không giải thích được — đúng thứ mà cả thiết kế kho này
        dựng ra để tránh.
        """
        ma_lo = (batch_code or "").strip()
        don_vi = (unit or "").strip()
        if not ma_lo:
            raise ValidationError("Nhập số lô — không có số lô thì không thu hồi được.")
        if not don_vi:
            raise ValidationError("Nhập đơn vị (viên, vỉ, hộp, ống…).")
        if expiry_date is None:
            raise ValidationError("Nhập hạn dùng của lô.")
        luong = _so(so_luong, ten="Số lượng nhập")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                thuoc = await conn.fetchrow(
                    """
                    SELECT id, name_base FROM public.drug_catalog
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    drug_catalog_id,
                    identity.clinic_id,
                )
                if thuoc is None:
                    raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")

                # SỐ LÔ LÀ DUY NHẤT THEO PHÒNG KHÁM, không theo từng thuốc:
                # `uq_drug_batch_clinic_code UNIQUE (clinic_id, batch_code)`.
                # Nên tra theo đúng cặp ấy. Tra theo (thuốc, lô, hạn) sẽ không
                # tìm thấy dòng đã có rồi đâm vào ràng buộc duy nhất — và dược
                # sĩ nhận một lỗi Postgres thay vì một câu tiếng Việt.
                lo = await conn.fetchrow(
                    """
                    SELECT id, drug_catalog_id, expiry_date
                      FROM public.drug_batch
                     WHERE clinic_id = $1::uuid AND batch_code = $2
                    """,
                    identity.clinic_id,
                    ma_lo,
                )
                if lo is not None:
                    # Cùng số lô mà khác thuốc hoặc khác hạn thì KHÔNG phải một
                    # lô — đó là gõ nhầm số lô. Nhập tiếp vào đấy là trộn hai
                    # thứ thuốc vào một dòng tồn.
                    if str(lo["drug_catalog_id"]) != str(drug_catalog_id):
                        raise ConflictError(
                            f"Số lô {ma_lo} đã dùng cho một thuốc khác. "
                            "Kiểm tra lại số lô trên vỏ hộp."
                        )
                    if lo["expiry_date"] != expiry_date:
                        raise ConflictError(
                            f"Số lô {ma_lo} đã có trong kho với hạn dùng "
                            f"{lo['expiry_date']:%d/%m/%Y}, khác hạn vừa nhập. "
                            "Kiểm tra lại."
                        )
                    lo_id = lo["id"]
                else:
                    lo_id = await conn.fetchval(
                        """
                        INSERT INTO public.drug_batch
                            (clinic_id, drug_catalog_id, batch_code, expiry_date,
                             quantity_on_hand, unit, cost_price, received_at)
                        VALUES ($1::uuid, $2::uuid, $3, $4::date, 0, $5, $6, now())
                        RETURNING id
                        """,
                        identity.clinic_id,
                        drug_catalog_id,
                        ma_lo,
                        expiry_date,
                        don_vi,
                        cost_price,
                    )

                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=str(lo_id),
                    txn_type=NHAP,
                    quantity=luong,
                    reason=ly_do,
                    ref_type="manual",
                    ref_id=None,
                )
                ton = await self._ton_cua_lo(conn, identity, str(lo_id))

        logger.info(
            "pharmacy_batch_received",
            batch_id=str(lo_id),
            quantity=str(luong),
            by_staff_id=identity.staff_id,
        )
        return {"ok": True, "drug_batch_id": str(lo_id), "quantity_on_hand": ton}

    async def cap_phat(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str,
        so_luong: Any,
    ) -> dict[str, Any]:
        """Cấp thuốc cho một dòng đơn. Cấp một phần là chuyện bình thường.

        Một thao tác, hai sổ, MỘT GIAO DỊCH: trừ kho và cộng vào số đã cấp của
        đơn. Tách ra hai lần gọi sẽ có lúc kho trừ rồi mà đơn chưa ghi — và
        không ai đối soát lại được.
        """
        luong = _so(so_luong, ten="Số lượng cấp")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # FOR UPDATE: hai dược sĩ cùng bấm trên một đơn thì người sau
                # đọc được số người trước vừa ghi. Không khoá thì cả hai đọc
                # cùng một `dispensed_qty` và tổng cấp vượt số kê.
                don = await conn.fetchrow(
                    """
                    SELECT id, drug_name_raw, quantity_num, dispensed_qty,
                           closed_at, refusal_reason
                      FROM public.prescription
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                     FOR UPDATE
                    """,
                    prescription_id,
                    identity.clinic_id,
                )
                if don is None:
                    raise NotFoundError("Không tìm thấy dòng thuốc này trong đơn.")
                if don["closed_at"] is not None:
                    raise ConflictError(
                        "Dòng thuốc này đã chốt — không cấp thêm được nữa."
                    )

                da_cap = Decimal(str(don["dispensed_qty"] or 0))
                ke = don["quantity_num"]
                if ke is not None and da_cap + luong > Decimal(str(ke)):
                    con = Decimal(str(ke)) - da_cap
                    raise ValidationError(
                        f"Đơn kê {ke} {don['drug_name_raw']}, đã cấp {da_cap} — "
                        f"chỉ còn {con}. Không cấp quá số bác sĩ kê."
                    )

                lo = await conn.fetchrow(
                    """
                    SELECT b.id, b.quantity_on_hand, b.expiry_date, c.name_base
                      FROM public.drug_batch b
                      LEFT JOIN public.drug_catalog c ON c.id = b.drug_catalog_id
                     WHERE b.id = $1::uuid AND b.clinic_id = $2::uuid
                     FOR UPDATE OF b
                    """,
                    drug_batch_id,
                    identity.clinic_id,
                )
                if lo is None:
                    raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")

                ton = Decimal(str(lo["quantity_on_hand"] or 0))
                if ton < luong:
                    # Nói TRƯỚC ràng buộc `drug_batch_qty_non_negative`. Để
                    # Postgres từ chối thì dược sĩ đọc được một câu tiếng Anh
                    # về CHECK constraint và không biết còn bao nhiêu.
                    raise ValidationError(
                        f"Lô này chỉ còn {ton} {lo['name_base'] or ''}".rstrip()
                        + f" — không đủ để cấp {luong}. Chọn lô khác hoặc nhập thêm."
                    )
                if lo["expiry_date"] is not None and lo["expiry_date"] < date.today():
                    raise ValidationError(
                        f"Lô này hết hạn ngày {lo['expiry_date']:%d/%m/%Y} — "
                        "không cấp được. Huỷ lô rồi chọn lô khác."
                    )

                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=drug_batch_id,
                    txn_type=CAP,
                    # DISPENSE mang dấu ÂM (inventory_txn_qty_sign_check).
                    quantity=-luong,
                    reason=None,
                    ref_type="prescription",
                    ref_id=prescription_id,
                )

                moi = await conn.fetchrow(
                    """
                    UPDATE public.prescription
                       SET dispensed_qty = dispensed_qty + $3,
                           dispensed_at = now(),
                           dispensed_by_staff_id = $4::uuid,
                           updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    RETURNING dispensed_qty, dispense_status
                    """,
                    prescription_id,
                    identity.clinic_id,
                    luong,
                    identity.staff_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.dispensed",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "drug_batch_id": drug_batch_id,
                        "quantity": str(luong),
                        "dispensed_qty": str(moi["dispensed_qty"]),
                        "dispense_status": moi["dispense_status"],
                    },
                )

        logger.info(
            "pharmacy_dispensed",
            prescription_id=prescription_id,
            quantity=str(luong),
            by_staff_id=identity.staff_id,
        )
        return {
            "ok": True,
            "dispensed_qty": moi["dispensed_qty"],
            "dispense_status": moi["dispense_status"],
        }

    async def tu_choi(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Khách không mua. Lý do BẮT BUỘC — CSKH còn gọi lại để hỏi."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError(
                "Ghi rõ vì sao khách không lấy thuốc — hết tiền, đã có thuốc ở "
                "nhà, hay đổi ý sau khi nghe tư vấn."
            )
        return await self._chot_dong(
            identity=identity,
            prescription_id=prescription_id,
            refusal_reason=ly,
            event_type="pharmacy.refused",
        )

    async def chot(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str | None = None
    ) -> dict[str, Any]:
        """Không cấp thêm nữa. Dùng cho "lấy 5 rồi thôi" và cho đơn đã cấp đủ."""
        return await self._chot_dong(
            identity=identity,
            prescription_id=prescription_id,
            refusal_reason=None,
            ly_do=(ly_do or "").strip() or None,
            event_type="pharmacy.line_closed",
        )

    async def dieu_chinh(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        so_luong: Any,
        ly_do: str,
    ) -> dict[str, Any]:
        """Kiểm kê lệch. `so_luong` mang dấu: âm là bớt, dương là thêm."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Điều chỉnh tồn kho thì phải ghi lý do.")
        try:
            lech = Decimal(str(so_luong))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("Số lượng điều chỉnh phải là một con số.") from exc
        if lech == 0:
            raise ValidationError("Điều chỉnh 0 thì không phải một điều chỉnh.")
        return await self._ghi_kho_don_gian(
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=DIEU_CHINH,
            quantity=lech,
            ly_do=ly,
            event_type="pharmacy.adjusted",
        )

    async def huy(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        so_luong: Any,
        ly_do: str,
    ) -> dict[str, Any]:
        """Huỷ thuốc hỏng / hết hạn. Ra khỏi kho nhưng không ra khỏi sổ."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Huỷ thuốc thì phải ghi lý do.")
        return await self._ghi_kho_don_gian(
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=HUY,
            quantity=-_so(so_luong, ten="Số lượng huỷ"),
            ly_do=ly,
            event_type="pharmacy.discarded",
        )

    # ── Bên trong ──────────────────────────────────────────────────────────

    async def _chot_dong(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        refusal_reason: str | None,
        event_type: str,
        ly_do: str | None = None,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    UPDATE public.prescription
                       SET closed_at = coalesce(closed_at, now()),
                           refusal_reason = coalesce($3, refusal_reason),
                           updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND closed_at IS NULL
                    RETURNING dispensed_qty, dispense_status
                    """,
                    prescription_id,
                    identity.clinic_id,
                    refusal_reason,
                )
                if row is None:
                    # Hai người cùng bấm, hoặc bấm lại sau khi mạng lag. Không
                    # phải lỗi — nhưng phải nói rõ là KHÔNG CÓ GÌ ĐỔI, chứ không
                    # trả "ok" trống khiến người dùng tưởng vừa ghi được.
                    ton_tai = await conn.fetchval(
                        "SELECT 1 FROM public.prescription "
                        "WHERE id = $1::uuid AND clinic_id = $2::uuid",
                        prescription_id,
                        identity.clinic_id,
                    )
                    if not ton_tai:
                        raise NotFoundError("Không tìm thấy dòng thuốc này.")
                    return {"ok": True, "da_chot_tu_truoc": True}

                await _log(
                    conn,
                    identity=identity,
                    event_type=event_type,
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "refusal_reason": refusal_reason,
                        "note": ly_do,
                        "dispensed_qty": str(row["dispensed_qty"]),
                        "dispense_status": row["dispense_status"],
                    },
                )
        return {
            "ok": True,
            "dispensed_qty": row["dispensed_qty"],
            "dispense_status": row["dispense_status"],
        }

    async def _ghi_kho_don_gian(
        self,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        txn_type: str,
        quantity: Decimal,
        ly_do: str,
        event_type: str,
    ) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                lo = await conn.fetchrow(
                    """
                    SELECT id, quantity_on_hand FROM public.drug_batch
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                     FOR UPDATE
                    """,
                    drug_batch_id,
                    identity.clinic_id,
                )
                if lo is None:
                    raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")

                ton = Decimal(str(lo["quantity_on_hand"] or 0))
                if quantity < 0 and ton < -quantity:
                    raise ValidationError(
                        f"Lô này chỉ còn {ton} — không bớt được {-quantity}."
                    )

                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=drug_batch_id,
                    txn_type=txn_type,
                    quantity=quantity,
                    reason=ly_do,
                    ref_type="manual",
                    ref_id=None,
                )
                con = await self._ton_cua_lo(conn, identity, drug_batch_id)
                await _log(
                    conn,
                    identity=identity,
                    event_type=event_type,
                    aggregate_type="drug_batch",
                    aggregate_id=drug_batch_id,
                    payload={
                        "quantity": str(quantity),
                        "reason": ly_do,
                        "quantity_on_hand": str(con),
                    },
                )
        return {"ok": True, "quantity_on_hand": con}

    async def _ghi_so(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        drug_batch_id: str,
        txn_type: str,
        quantity: Decimal,
        reason: str | None,
        ref_type: str | None,
        ref_id: str | None,
    ) -> None:
        """Một dòng vào sổ kho. Trigger tự cộng vào tồn của lô.

        `performed_by_staff_id` luôn đặt: `inventory_txn_manual_needs_actor`
        chỉ đòi nó khi `ref_type` là 'manual' hoặc trống, nhưng một dòng sổ
        không biết ai làm thì về sau không đối soát được với ai cả.
        """
        await conn.execute(
            """
            INSERT INTO public.inventory_txn
                (clinic_id, drug_batch_id, txn_type, quantity, reason,
                 ref_type, ref_id, performed_by_staff_id, performed_at)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $8::uuid, now())
            """,
            identity.clinic_id,
            drug_batch_id,
            txn_type,
            quantity,
            reason,
            ref_type,
            ref_id,
            identity.staff_id,
        )

    @staticmethod
    async def _ton_cua_lo(
        conn: asyncpg.Connection, identity: StaffIdentity, drug_batch_id: str
    ) -> Any:
        return await conn.fetchval(
            "SELECT quantity_on_hand FROM public.drug_batch "
            "WHERE id = $1::uuid AND clinic_id = $2::uuid",
            drug_batch_id,
            identity.clinic_id,
        )


async def _log(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        """
        INSERT INTO public.event_log
            (clinic_id, event_type, aggregate_type, aggregate_id, payload,
             metadata, source, event_published)
        VALUES ($1::uuid, $2, $3, $4::uuid, $5::jsonb, $6::jsonb,
                'api:pharmacy', FALSE)
        """,
        identity.clinic_id,
        event_type,
        aggregate_type,
        aggregate_id,
        json.dumps(payload, ensure_ascii=False),
        json.dumps(
            {
                "actor_auth_user_id": identity.auth_user_id,
                "clinic_staff_id": identity.staff_id,
                "clinic_role": identity.role.value,
            }
        ),
    )
