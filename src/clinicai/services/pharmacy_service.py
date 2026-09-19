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
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import now_vn
from clinicai.services.phan_lo_service import khoa_lo, so

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


def _don_vi(value: str | None) -> str:
    """Chỉ chuẩn hoá cách viết; hộp, vỉ, viên luôn là các đơn vị khác nhau."""
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


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
        # `date | None` chứ không phải `date`: thân hàm CÓ kiểm None và trả về
        # một câu tiếng Việt. Khai là `date` thì nhánh ấy thành mã chết dưới
        # mắt mypy, và người gọi tiếp theo — một script nhập kho hàng loạt
        # chẳng hạn — vẫn truyền None vào được mà không ai chặn.
        expiry_date: date | None,
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
        """GIAO thuốc cho một dòng đơn (bàn giao vật lý). Giao một phần là bình thường.

        Contract tiền–thuốc CP3: thuốc đã BÁN lúc thu tiền thành công. Giao chỉ
        là thuốc thật rời quầy — ghi DISPENSE (tồn vật lý giảm) gắn đúng phân lô
        và lần thu, nên lượng khả dụng không giảm lần hai.

          * Chưa thu tiền thuốc → không giao.
          * Lần thu cũ (`payment_cycle.legacy`, trước CP3, không có phân lô) →
            giữ nguyên luồng cũ `_cap_phat_cu`.
          * Lần thu mới → chỉ giao từ đúng lô đã phân, không vượt phần chưa giao.

        Một thao tác, hai sổ, MỘT GIAO DỊCH: kho và số đã cấp của đơn.
        """
        luong = _so(so_luong, ten="Số lượng cấp")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # visit → dòng đơn (cùng thứ tự với lần thu / huỷ phiếu).
                don = await self._khoa_theo_luot(conn, identity, prescription_id)
                if don["closed_at"] is not None:
                    raise ConflictError(
                        "Dòng thuốc này đã chốt — không cấp thêm được nữa."
                    )
                lan = await conn.fetchrow(
                    """
                    SELECT payment_cycle_id::text, legacy FROM public.payment_cycle
                     WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                       AND kind = 'thuoc' AND status = 'PAID'
                    """,
                    identity.clinic_id,
                    don["visit_id"],
                )
                if lan is None:
                    raise ConflictError(
                        "Tiền thuốc của lượt này chưa thu — thu tiền thuốc trước "
                        "rồi mới giao thuốc."
                    )
                if lan["legacy"]:
                    moi = await self._cap_phat_cu(
                        conn,
                        identity=identity,
                        don=don,
                        prescription_id=prescription_id,
                        drug_batch_id=drug_batch_id,
                        luong=luong,
                    )
                else:
                    moi = await self._giao_theo_phan_lo(
                        conn,
                        identity=identity,
                        prescription_id=prescription_id,
                        drug_batch_id=drug_batch_id,
                        cycle_id=lan["payment_cycle_id"],
                        luong=luong,
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

    async def _giao_theo_phan_lo(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str,
        cycle_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        pl = await conn.fetchrow(
            """
            SELECT id::text, quantity, handed_over_qty
              FROM public.prescription_allocation
             WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid
               AND drug_batch_id = $3::uuid AND payment_cycle_id = $4::uuid
               AND released_at IS NULL
             FOR UPDATE
            """,
            identity.clinic_id,
            prescription_id,
            drug_batch_id,
            cycle_id,
        )
        if pl is None:
            raise ValidationError(
                "Lô này không nằm trong các lô đã bán cho dòng thuốc này — "
                "giao đúng lô đã chọn lúc thu tiền."
            )
        con = Decimal(str(pl["quantity"])) - Decimal(str(pl["handed_over_qty"]))
        if luong > con:
            raise ValidationError(
                f"Lô này đã bán {so(Decimal(str(pl['quantity'])))}, còn {so(con)} "
                "chưa giao — "
                "không giao quá số đã bán."
            )
        await khoa_lo(conn, clinic_id=identity.clinic_id, lo_ids=[drug_batch_id])
        lo = await conn.fetchrow(
            "SELECT quantity_on_hand, expiry_date FROM public.drug_batch"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            drug_batch_id,
            identity.clinic_id,
        )
        if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
            raise ValidationError(
                f"Lô này hết hạn ngày {lo['expiry_date']:%d/%m/%Y} — không giao "
                "được. Cần xử lý đổi/trả (chưa có trong bản này)."
            )
        if Decimal(str(lo["quantity_on_hand"] or 0)) < luong:
            raise ConflictError(
                f"Trên kệ lô này chỉ còn {lo['quantity_on_hand']} — không khớp số "
                "đã bán. Cần kiểm kê trước khi giao."
            )
        da_ban = await conn.fetchval(
            """
            SELECT EXISTS (SELECT 1 FROM public.inventory_txn s
                            WHERE s.clinic_id = $1::uuid AND s.txn_type = 'SALE'
                              AND s.allocation_id = $2::uuid
                              AND s.payment_cycle_id = $3::uuid
                              AND NOT EXISTS (
                                  SELECT 1 FROM public.inventory_txn r
                                   WHERE r.txn_type = 'SALE_REVERSAL'
                                     AND r.reverses_txn_id = s.id))
            """,
            identity.clinic_id,
            pl["id"],
            cycle_id,
        )
        if not da_ban:
            raise ConflictError(
                "Lần thu này chưa ghi bán được cho lô này (đang cần đối soát) — "
                "chưa giao được."
            )
        await self._ghi_so(
            conn,
            identity=identity,
            drug_batch_id=drug_batch_id,
            txn_type=CAP,
            quantity=-luong,
            reason=None,
            ref_type="prescription",
            ref_id=prescription_id,
            payment_cycle_id=cycle_id,
            allocation_id=pl["id"],
        )
        await conn.execute(
            "UPDATE public.prescription_allocation"
            " SET handed_over_qty = handed_over_qty + $3"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            pl["id"],
            identity.clinic_id,
            luong,
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
                "allocation_id": pl["id"],
                "payment_cycle_id": cycle_id,
                "quantity": str(luong),
                "dispensed_qty": str(moi["dispensed_qty"]),
                "dispense_status": moi["dispense_status"],
            },
        )
        return moi

    async def _cap_phat_cu(
        self,
        conn: asyncpg.Connection,
        *,
        identity: StaffIdentity,
        don: asyncpg.Record,
        prescription_id: str,
        drug_batch_id: str,
        luong: Decimal,
    ) -> asyncpg.Record:
        """Luồng cấp phát TRƯỚC CP3, chỉ cho lần thu cũ (`legacy`).

        Đơn có đơn vị chỉ cấp từ lô cùng đơn vị; chưa có quy đổi bao bì đã xác
        minh nên không đoán số viên/hộp. Đơn cũ thiếu đơn vị giữ hành vi cũ:
        số lượng cấp được hiểu theo đơn vị lô. Đây là giới hạn dữ liệu cũ,
        không xác nhận rằng số kê và số tồn đã có cùng đơn vị.
        """
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
            SELECT b.id, b.quantity_on_hand, b.unit, b.expiry_date,
                   c.name_base
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

        don_vi_ke = _don_vi(don.get("unit"))
        don_vi_lo = _don_vi(lo.get("unit"))
        if don_vi_ke and don_vi_ke != don_vi_lo:
            raise ValidationError(
                f"Đơn kê theo đơn vị {don['unit']}, nhưng lô thuốc theo "
                f"đơn vị {lo.get('unit') or 'chưa xác định'}. "
                "Chọn lô cùng đơn vị hoặc xác nhận lại đơn thuốc; "
                "không tự quy đổi hộp, vỉ, viên."
            )

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
        return moi

    async def xac_dinh_thuoc(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_catalog_id: str,
    ) -> dict[str, Any]:
        """Gắn dòng đơn với ĐÚNG một thuốc trong danh mục kho (contract C1).

        Bác sĩ kê bằng tên gõ tay; tên không phải bằng chứng thuốc nào trong kho.
        Chưa gắn thì dòng ấy chưa vào hoá đơn và chưa cấp được — người có quyền
        nhà thuốc chọn thuốc, hệ thống không đoán theo tên.

        Không đổi được sau khi đã thu tiền thuốc (hoá đơn đã chụp theo thuốc
        này) hoặc đã cấp (lô đã chọn theo thuốc này).
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                if Decimal(str(don["dispensed_qty"] or 0)) > 0:
                    raise ConflictError(
                        "Dòng này đã cấp thuốc — không đổi thuốc kho được nữa."
                    )
                if str(don["drug_catalog_id"] or "") != str(
                    drug_catalog_id
                ) and await self._da_phan_lo(conn, identity, prescription_id):
                    raise ConflictError(
                        "Dòng này đã chọn lô — bỏ các lô đã chọn trước khi "
                        "đổi thuốc kho."
                    )
                thuoc = await conn.fetchrow(
                    """
                    SELECT id, name_base FROM public.drug_catalog
                     WHERE id = $1::uuid AND clinic_id = $2::uuid AND is_active
                    """,
                    drug_catalog_id,
                    identity.clinic_id,
                )
                if thuoc is None:
                    raise NotFoundError("Không tìm thấy thuốc này trong danh mục kho.")
                await conn.execute(
                    """
                    UPDATE public.prescription
                       SET drug_catalog_id = $3::uuid, drug_mapped_by = $4::uuid,
                           drug_mapped_at = now(), updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    prescription_id,
                    identity.clinic_id,
                    drug_catalog_id,
                    identity.staff_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.drug_mapped",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "drug_catalog_id": drug_catalog_id,
                        "truoc_do": (
                            str(don["drug_catalog_id"])
                            if don["drug_catalog_id"]
                            else None
                        ),
                    },
                )
        return {"ok": True, "drug_catalog_id": drug_catalog_id}

    async def khai_so_luong_mua(
        self, *, identity: StaffIdentity, prescription_id: str, so_luong: Any
    ) -> dict[str, Any]:
        """Số khách đồng ý mua (contract C2) — khác số kê và số đã giao.

        0 ≤ số mua ≤ số kê, và không nhỏ hơn số đã giao. Mua một phần trên
        production là HOLD J3 — mô hình hỗ trợ, việc bật cho quầy là quyết định
        của Dr4Women. Không đổi được sau khi đã thu tiền thuốc.
        """
        try:
            mua = Decimal(str(so_luong))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("Số lượng mua phải là một con số.") from exc
        if mua < 0:
            raise ValidationError("Số lượng mua không âm.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                ke = don["quantity_num"]
                if ke is None:
                    # Không biết số kê thì không có căn cứ cho một số mua bất kỳ
                    # (review CP1 #1; DB cũng chặn: prescription_purchased_qty_check).
                    raise ValidationError(
                        "Chưa xác định số lượng bác sĩ kê cho dòng này — "
                        "cần bác sĩ ghi rõ số lượng trước khi khai số mua."
                    )
                if mua > Decimal(str(ke)):
                    raise ValidationError(f"Bác sĩ kê {ke} — không bán quá số kê.")
                da_giao = Decimal(str(don["dispensed_qty"] or 0))
                if mua < da_giao:
                    raise ValidationError(
                        f"Đã giao {da_giao} — số mua không nhỏ hơn số đã giao."
                    )
                da_phan = await self._da_phan_lo(conn, identity, prescription_id)
                if mua < da_phan:
                    raise ValidationError(
                        f"Đã chọn lô cho {so(da_phan)} — bỏ bớt lô trước khi "
                        "giảm số mua."
                    )
                await conn.execute(
                    """
                    UPDATE public.prescription
                       SET purchased_qty = $3, updated_at = now()
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    prescription_id,
                    identity.clinic_id,
                    mua,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.purchase_qty_set",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "purchased_qty": str(mua),
                        "truoc_do": (
                            str(don["purchased_qty"])
                            if don["purchased_qty"] is not None
                            else None
                        ),
                    },
                )
        return {"ok": True, "purchased_qty": mua}

    @staticmethod
    async def _khoa_theo_luot(
        conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> asyncpg.Record:
        """Khoá LƯỢT KHÁM rồi mới khoá dòng đơn — cùng thứ tự với lần thu.

        Review CP1 #3 (TOCTOU): lần thu khoá `visit` rồi tính hoá đơn; nếu lệnh
        đổi dòng thuốc chỉ khoá `prescription` thì hai giao dịch không chặn nhau
        và có thể commit hai sự thật (đơn = thuốc B, ảnh chụp hoá đơn = thuốc A).
        Thứ tự khoá DUY NHẤT cho mọi thao tác chạm hoá đơn thuốc (CP3 thêm
        phân lô và lô vào giữa — xem phan_lo_service):
            visit → prescription → prescription_allocation → drug_batch
                  → payment_cycle / payment
        Không bao giờ khoá ngược (prescription trước visit) — sẽ tắc lẫn nhau.
        """
        vid = await conn.fetchval(
            "SELECT visit_id FROM public.prescription"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            prescription_id,
            identity.clinic_id,
        )
        if vid is None:
            raise NotFoundError("Không tìm thấy dòng thuốc này trong đơn.")
        await conn.execute(
            "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid"
            " AND visit_id = $2::uuid FOR UPDATE",
            identity.clinic_id,
            vid,
        )
        don = await conn.fetchrow(
            """
            SELECT id, visit_id, quantity_num, purchased_qty, dispensed_qty,
                   drug_catalog_id, closed_at, drug_name_raw, unit
              FROM public.prescription
             WHERE id = $1::uuid AND clinic_id = $2::uuid
             FOR UPDATE
            """,
            prescription_id,
            identity.clinic_id,
        )
        if don is None or don["visit_id"] != vid:
            raise ConflictError("Dòng thuốc vừa thay đổi — tải lại rồi thử lại.")
        return don

    @staticmethod
    async def _da_thu_tien_thuoc(
        conn: asyncpg.Connection, identity: StaffIdentity, visit_id: Any
    ) -> bool:
        return bool(
            await conn.fetchval(
                """
                -- Đã thu, HOẶC đang chờ xác minh chuyển khoản/QR (CP2): hoá
                -- đơn thuốc đã chốt theo lần thu ấy.
                SELECT EXISTS (SELECT 1 FROM public.payment
                                WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                                  AND kind = 'thuoc' AND status = 'PAID')
                    OR EXISTS (SELECT 1 FROM public.payment_cycle
                                WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                                  AND kind = 'thuoc'
                                  AND status IN ('PENDING_VERIFICATION', 'PAID'))
                """,
                identity.clinic_id,
                visit_id,
            )
        )

    @classmethod
    async def _khoa_dong_chua_thu(
        cls, conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> asyncpg.Record:
        """Khoá (lượt → dòng); từ chối nếu dòng đã chốt hoặc tiền thuốc đã thu."""
        don = await cls._khoa_theo_luot(conn, identity, prescription_id)
        if don["closed_at"] is not None:
            raise ConflictError("Dòng thuốc này đã chốt — không sửa được nữa.")
        if await cls._da_thu_tien_thuoc(conn, identity, don["visit_id"]):
            raise ConflictError(
                "Tiền thuốc của lượt này đã thu theo hoá đơn cũ — huỷ phiếu thu "
                "trước rồi mới sửa dòng thuốc."
            )
        return don

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

    # ── Phân lô (contract tiền–thuốc CP3) ─────────────────────────────────

    async def phan_lo(
        self,
        *,
        identity: StaffIdentity,
        prescription_id: str,
        drug_batch_id: str,
        so_luong: Any,
    ) -> dict[str, Any]:
        """Chọn lô cho dòng đơn TRƯỚC khi thu tiền thuốc. Chưa giữ chỗ.

        Thu tiền thuốc đòi mọi dòng có đủ lô; thu xong là bán đúng các lô này.
        Hai khách có thể cùng chọn một lô — người thu sau được kiểm lại.
        """
        luong = _so(so_luong, ten="Số lượng chọn lô")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                don = await self._khoa_dong_chua_thu(conn, identity, prescription_id)
                # CP4: chọn lô khoá dòng đơn khỏi nút Lưu bệnh án — chỉ cho khi
                # bác sĩ đã bấm Khám xong (cùng mốc với "thu được tiền").
                if not await conn.fetchval(
                    """
                    SELECT a.status = 'COMPLETED'
                      FROM public.visit v
                      JOIN public.appointment a
                        ON a.id = v.appointment_id AND a.clinic_id = v.clinic_id
                     WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
                    """,
                    don["visit_id"],
                    identity.clinic_id,
                ):
                    raise ConflictError(
                        "Bác sĩ chưa bấm Khám xong lượt này — chưa chọn lô được "
                        "(đơn còn có thể thay đổi)."
                    )
                if don["drug_catalog_id"] is None:
                    raise ValidationError(
                        "Chưa xác định thuốc trong kho cho dòng này — xác định "
                        "thuốc trước khi chọn lô."
                    )
                if not _don_vi(don["unit"]):
                    raise ValidationError(
                        "Chưa xác định đơn vị thuốc được kê; cần xác nhận/chỉnh "
                        "đơn trước khi chọn lô."
                    )
                if don["quantity_num"] is None:
                    raise ValidationError(
                        "Chưa xác định số lượng bác sĩ kê cho dòng này — chưa "
                        "chọn lô được."
                    )
                ban = Decimal(
                    str(
                        don["purchased_qty"]
                        if don["purchased_qty"] is not None
                        else don["quantity_num"]
                    )
                )
                can = ban - Decimal(str(don["dispensed_qty"] or 0))
                da_phan = await self._da_phan_lo(conn, identity, prescription_id)
                if da_phan + luong > can:
                    raise ValidationError(
                        f"Dòng này cần lô cho {so(can)}, đã chọn {so(da_phan)} — "
                        "không chọn quá số bán."
                    )
                await khoa_lo(
                    conn, clinic_id=identity.clinic_id, lo_ids=[drug_batch_id]
                )
                lo = await self._kiem_lo(
                    conn, identity, don, drug_batch_id, luong, them_giu=Decimal(0)
                )
                try:
                    pl_id = await conn.fetchval(
                        """
                        INSERT INTO public.prescription_allocation
                            (clinic_id, visit_id, prescription_id, drug_catalog_id,
                             drug_batch_id, quantity, created_by)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7::uuid)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        don["visit_id"],
                        prescription_id,
                        don["drug_catalog_id"],
                        drug_batch_id,
                        luong,
                        identity.staff_id,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ConflictError(
                        f"Dòng này đã chọn lô {lo['batch_code']} — bỏ lô ấy rồi "
                        "chọn lại với số lượng mới."
                    ) from exc
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocated",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "allocation_id": pl_id,
                        "drug_batch_id": drug_batch_id,
                        "quantity": str(luong),
                    },
                )
        return {"ok": True, "allocation_id": pl_id}

    async def bo_phan_lo(
        self, *, identity: StaffIdentity, allocation_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Bỏ một lô đã chọn (chưa gắn lần thu). Dòng giữ lại làm lịch sử."""
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Bỏ lô đã chọn thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                pl = await self._khoa_phan_lo(conn, identity, allocation_id)
                if pl["released_at"] is not None:
                    return {"ok": True, "da_bo_tu_truoc": True}
                if pl["payment_cycle_id"] is not None:
                    raise ConflictError(
                        "Lô này đã gắn vào một lần thu — huỷ lần chờ / huỷ phiếu "
                        "thu, hoặc đổi lô khi đang chờ xác minh."
                    )
                await conn.execute(
                    "UPDATE public.prescription_allocation"
                    " SET released_at = now(), released_by = $3::uuid,"
                    " release_reason = $4"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    allocation_id,
                    identity.clinic_id,
                    identity.staff_id,
                    ly,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocation_released",
                    aggregate_type="prescription",
                    aggregate_id=str(pl["prescription_id"]),
                    payload={"allocation_id": allocation_id, "reason": ly},
                )
        return {"ok": True}

    async def doi_lo_khi_cho(
        self,
        *,
        identity: StaffIdentity,
        allocation_id: str,
        drug_batch_id: str,
        ly_do: str,
    ) -> dict[str, Any]:
        """Đổi lô ĐANG GIỮ cho một lần chuyển khoản/QR chờ xác minh.

        Chuyển phần giữ sang lô mới trong MỘT giao dịch: cùng thuốc, cùng số
        lượng, cùng lần thu — hoá đơn tiền không đổi. Lô mới phải còn hạn và đủ
        khả dụng; không được thì không đổi gì.
        """
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Đổi lô thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                pl = await self._khoa_phan_lo(conn, identity, allocation_id)
                if pl["released_at"] is not None:
                    raise ConflictError("Lô này đã được bỏ/đổi — tải lại.")
                if str(pl["drug_batch_id"]) == str(drug_batch_id):
                    return {"ok": True, "allocation_id": allocation_id}
                await khoa_lo(
                    conn,
                    clinic_id=identity.clinic_id,
                    lo_ids=[str(pl["drug_batch_id"]), drug_batch_id],
                )
                trang_thai = await conn.fetchval(
                    "SELECT status FROM public.payment_cycle"
                    " WHERE payment_cycle_id = $1::uuid AND clinic_id = $2::uuid",
                    pl["payment_cycle_id"],
                    identity.clinic_id,
                )
                if (
                    pl["payment_cycle_id"] is None
                    or trang_thai != "PENDING_VERIFICATION"
                ):
                    raise ConflictError(
                        "Chỉ đổi lô đang giữ cho lần chuyển khoản/QR chờ xác minh."
                    )
                don = await conn.fetchrow(
                    "SELECT id, visit_id, drug_catalog_id, unit"
                    " FROM public.prescription"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    pl["prescription_id"],
                    identity.clinic_id,
                )
                luong = Decimal(str(pl["quantity"]))
                await self._kiem_lo(
                    conn, identity, don, drug_batch_id, luong, them_giu=Decimal(0)
                )
                await conn.execute(
                    "UPDATE public.prescription_allocation"
                    " SET released_at = now(), released_by = $3::uuid,"
                    " release_reason = $4"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    allocation_id,
                    identity.clinic_id,
                    identity.staff_id,
                    f"Đổi lô khi chờ xác minh: {ly}",
                )
                try:
                    moi = await conn.fetchval(
                        """
                        INSERT INTO public.prescription_allocation
                            (clinic_id, visit_id, prescription_id, drug_catalog_id,
                             drug_batch_id, quantity, created_by, payment_cycle_id)
                        VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid,
                                $6, $7::uuid, $8::uuid)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        pl["visit_id"],
                        pl["prescription_id"],
                        pl["drug_catalog_id"],
                        drug_batch_id,
                        luong,
                        identity.staff_id,
                        pl["payment_cycle_id"],
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise ConflictError(
                        "Dòng này đã có lô ấy trong lần thu — chưa hỗ trợ gộp lô."
                    ) from exc
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.allocation_moved",
                    aggregate_type="prescription",
                    aggregate_id=str(pl["prescription_id"]),
                    payload={
                        "from_allocation_id": allocation_id,
                        "to_allocation_id": moi,
                        "drug_batch_id": drug_batch_id,
                        "payment_cycle_id": str(pl["payment_cycle_id"]),
                        "reason": ly,
                    },
                )
        return {"ok": True, "allocation_id": moi}

    async def _khoa_phan_lo(
        self, conn: asyncpg.Connection, identity: StaffIdentity, allocation_id: str
    ) -> asyncpg.Record:
        """visit → dòng đơn → phân lô (đúng thứ tự khoá chung)."""
        rx = await conn.fetchval(
            "SELECT prescription_id::text FROM public.prescription_allocation"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid",
            allocation_id,
            identity.clinic_id,
        )
        if rx is None:
            raise NotFoundError("Không tìm thấy lô đã chọn này.")
        await self._khoa_theo_luot(conn, identity, rx)
        pl = await conn.fetchrow(
            """
            SELECT id, visit_id, prescription_id, drug_catalog_id, drug_batch_id,
                   quantity, payment_cycle_id, released_at
              FROM public.prescription_allocation
             WHERE id = $1::uuid AND clinic_id = $2::uuid
             FOR UPDATE
            """,
            allocation_id,
            identity.clinic_id,
        )
        assert pl is not None
        return pl

    @staticmethod
    async def _da_phan_lo(
        conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> Decimal:
        return Decimal(
            str(
                await conn.fetchval(
                    "SELECT coalesce(sum(quantity), 0)"
                    " FROM public.prescription_allocation"
                    " WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid"
                    " AND released_at IS NULL",
                    identity.clinic_id,
                    prescription_id,
                )
            )
        )

    @staticmethod
    async def _kiem_lo(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        don: asyncpg.Record,
        drug_batch_id: str,
        luong: Decimal,
        *,
        them_giu: Decimal,
    ) -> asyncpg.Record:
        """Lô đúng thuốc, đúng đơn vị, còn hạn, đủ khả dụng — nói bằng tiếng Việt
        trước khi trigger của DB từ chối."""
        lo = await conn.fetchrow(
            """
            SELECT batch_code, drug_catalog_id, unit, expiry_date,
                   public.drug_batch_kha_dung($2::uuid, id) AS kha_dung
              FROM public.drug_batch
             WHERE id = $1::uuid AND clinic_id = $2::uuid
            """,
            drug_batch_id,
            identity.clinic_id,
        )
        if lo is None:
            raise NotFoundError("Không tìm thấy lô thuốc này trong kho.")
        if str(lo["drug_catalog_id"]) != str(don["drug_catalog_id"]):
            raise ValidationError("Lô này không phải thuốc của dòng đơn.")
        if _don_vi(lo["unit"]) != _don_vi(don["unit"]):
            raise ValidationError(
                f"Đơn kê theo đơn vị {don['unit']}, lô theo đơn vị {lo['unit']} — "
                "không tự quy đổi hộp, vỉ, viên."
            )
        if lo["expiry_date"] is not None and lo["expiry_date"] < now_vn().date():
            raise ValidationError(
                f"Lô {lo['batch_code']} hết hạn ngày {lo['expiry_date']:%d/%m/%Y}."
            )
        kd = Decimal(str(lo["kha_dung"] or 0)) + them_giu
        if kd < luong:
            raise ValidationError(
                f"Lô {lo['batch_code']} chỉ còn {so(max(kd, Decimal(0)))} khả dụng "
                f"— không đủ {so(luong)}."
            )
        return lo

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
                # Từ chối làm đổi hoá đơn thuốc → cùng thứ tự khoá với lần thu
                # (review CP1 #3), và không từ chối dòng đã thu tiền: phải huỷ
                # phiếu / hoàn tiền trước (contract D).
                don = await self._khoa_theo_luot(conn, identity, prescription_id)
                if (
                    refusal_reason is not None
                    and don["closed_at"] is None
                    and await self._da_thu_tien_thuoc(conn, identity, don["visit_id"])
                ):
                    raise ConflictError(
                        "Tiền thuốc của lượt này đã thu — khách đổi ý thì huỷ "
                        "phiếu thu / hoàn tiền trước, rồi mới ghi không lấy thuốc."
                    )
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
                if row is not None:
                    # Dòng đã chốt không bán nữa → bỏ các lô CHƯA gắn lần thu
                    # (chỉ là kế hoạch, không giữ chỗ). Lô đã bán thì giữ nguyên.
                    await conn.execute(
                        "UPDATE public.prescription_allocation"
                        " SET released_at = now(), released_by = $3::uuid,"
                        " release_reason = 'Dòng đơn đã chốt'"
                        " WHERE clinic_id = $1::uuid AND prescription_id = $2::uuid"
                        " AND released_at IS NULL AND payment_cycle_id IS NULL",
                        identity.clinic_id,
                        prescription_id,
                        identity.staff_id,
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
        payment_cycle_id: str | None = None,
        allocation_id: str | None = None,
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
                 ref_type, ref_id, performed_by_staff_id, performed_at,
                 payment_cycle_id, allocation_id)
            VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $8::uuid, now(),
                    $9::uuid, $10::uuid)
            """,
            identity.clinic_id,
            drug_batch_id,
            txn_type,
            quantity,
            reason,
            ref_type,
            ref_id,
            identity.staff_id,
            payment_cycle_id,
            allocation_id,
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
                # Vai tài khoản gốc (vai dùng có thể khác).
                "vai_tai_khoan": identity.vai_goc.value,
            }
        ),
    )
