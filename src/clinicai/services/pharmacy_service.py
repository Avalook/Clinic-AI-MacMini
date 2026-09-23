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
from clinicai.core.tran import canh_bao_neu_day
from clinicai.events.catalogue import ThuocDaGiao
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.moc_kham_xong import kham_xong_sql
from clinicai.services.phan_lo_service import chua_giao_cua_dong, khoa_lo, so

logger = structlog.get_logger()

# Loại giao dịch kho, đúng bốn giá trị mà `inventory_txn_type_check` canh.
# Khai lại ở đây để một lỗi gõ bị bắt ở Python, trước khi nó thành một lỗi
# ràng buộc khó đọc từ Postgres.
NHAP = "RECEIVE"
CAP = "DISPENSE"
DIEU_CHINH = "ADJUST"
HUY = "DISCARD"
# CP5: thuốc khách trả đã quay lại quầy — vật lý tăng, CHƯA bán lại được.
TRA_NHAN = "RETURN_RECEIVED"


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


def _so_chu(v: Any) -> str | None:
    return None if v is None else str(v)


#: Luật cũ "nhà thuốc đợi Khám xong" — OFF từ 24/09/2026 (xem `_bat_buoc_kham_xong`).
_CHO_KHAM_XONG = False


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
                   AND r.removed_at IS NULL
                 ORDER BY r.created_at DESC
                 LIMIT 300
                """,
                identity.clinic_id,
            )
        # Hàng đợi cấp thuốc mà cắt im lặng là có người đứng đợi mà không ai
        # thấy tên. Trần giữ nguyên; điều đổi là nó kêu lên khi chạm.
        canh_bao_neu_day("nha_thuoc.hang_doi", len(rows), 300)
        return [dict(r) for r in rows]

    async def lich_su_giao(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Dòng thuốc ĐÃ GIAO (mới nhất trước, tối đa 200) — kèm ba con số của
        một dòng: bác sĩ KÊ (`quantity_num`), khách CHỐT MUA (`purchased_qty`,
        trống = như kê) và ĐÃ GIAO (`dispensed_qty`).

        24/09/2026: trang Lịch sử bàn giao từng đọc thẳng `prescription` bằng
        Supabase và chỉ hiện số đã giao — nợ "đơn kê vs khách thực mua".
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text, r.source_ref, r.drug_name_raw,
                       r.dosage_instructions, r.quantity, r.quantity_note,
                       r.quantity_num, r.purchased_qty, r.dispensed_qty, r.unit,
                       r.dispense_status, r.dispensed_at, r.created_at,
                       p.full_name, p.phone_primary
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                   AND p.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.dispensed_qty > 0
                 -- rx:gom-ca-lich-su: thuốc ĐÃ GIAO tay khách là sự thật, kể cả
                 -- dòng bác sĩ đính chính sau khi giao — lịch sử phải còn nó.
                 ORDER BY r.dispensed_at DESC NULLS LAST
                 LIMIT 200
                """,
                identity.clinic_id,
            )
        canh_bao_neu_day(
            "nha_thuoc.lich_su", len(rows), 200, clinic_id=identity.clinic_id
        )
        return [dict(r) for r in rows]

    async def cho_tu_van(self, *, identity: StaffIdentity) -> list[dict[str, Any]]:
        """Dòng thuốc còn việc (chưa chốt, chưa bị đính chính) — màn Tư vấn dùng
        thuốc. Chuyển từ trang đọc thẳng Supabase (24/09/2026)."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT r.id::text, r.source_ref, r.drug_name_raw,
                       r.dosage_instructions, r.quantity, r.quantity_note,
                       r.caution, r.created_at, p.full_name, p.phone_primary
                  FROM public.prescription r
                  LEFT JOIN public.patient p
                    ON p.clinic_patient_id = r.clinic_patient_id
                   AND p.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid
                   AND r.closed_at IS NULL AND r.removed_at IS NULL
                 ORDER BY r.created_at DESC
                 LIMIT 100
                """,
                identity.clinic_id,
            )
        canh_bao_neu_day(
            "nha_thuoc.cho_tu_van", len(rows), 100, clinic_id=identity.clinic_id
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
                # Dòng thời gian: kê ↔ khách mua ↔ đã giao (hai bản đơn). Số kê
                # và số mua đọc từ dòng đã khoá ở trên — giao không đổi hai số ấy.
                await emit_event(
                    conn,
                    ten="medicine.dispensed",
                    clinic_id=identity.clinic_id,
                    aggregate_id=prescription_id,
                    payload=ThuocDaGiao(
                        visit_id=str(don["visit_id"]),
                        prescription_id=prescription_id,
                        so_ke=_so_chu(don.get("quantity_num")),
                        so_mua=_so_chu(don.get("purchased_qty")),
                        so_da_giao=str(moi["dispensed_qty"]),
                    ),
                    boi=nguoi(identity),
                    correlation_id=str(don["visit_id"]),
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
            da_huy = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.inventory_txn"
                " WHERE clinic_id = $1::uuid AND txn_type = 'SALE_REVERSAL'"
                " AND allocation_id = $2::uuid)",
                identity.clinic_id,
                pl["id"],
            )
            raise ConflictError(
                "Phần chưa giao của lô này đã huỷ — không giao thêm."
                if da_huy
                else "Lần thu này chưa ghi bán được cho lô này (đang cần đối soát) "
                "— chưa giao được."
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
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
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
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
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
    async def _bat_buoc_kham_xong(
        conn: asyncpg.Connection, identity: StaffIdentity, visit_id: Any
    ) -> None:
        """OFF từ 24/09/2026 — nhà thuốc KHÔNG còn đợi bác sĩ bấm Khám xong.

        Tuyền chốt: "tiền thuốc không cần khám xong"; Khám xong là mốc thời gian,
        không phải cửa khoá (luồng chuẩn bước 9–10). Đơn đổi SAU khi nhà thuốc đã
        đụng dòng thì đi đường ĐÍNH CHÍNH (dinh_chinh_don: dòng cũ giữ lịch sử,
        dòng mới thay) — không cần chặn nhà thuốc để giữ đơn đứng yên.

        Giữ hàm (không xoá, Tuyền bấm thật xong mới dọn): bật lại luật cũ =
        đổi `_CHO_KHAM_XONG` thành True.
        """
        if not _CHO_KHAM_XONG:
            return
        # Mốc chung của Nhà thuốc / Thu ngân / Payment (moc_kham_xong): trạng
        # thái của LƯỢT, không phụ thuộc lượt có lịch hẹn hay không.
        if not await conn.fetchval(
            f"""
            SELECT {kham_xong_sql("v")}
              FROM public.visit v
             WHERE v.visit_id = $1::uuid AND v.clinic_id = $2::uuid
            """,  # noqa: S608 — chỉ chèn biểu thức cố định
            visit_id,
            identity.clinic_id,
        ):
            raise ConflictError(
                "Bác sĩ chưa bấm Khám xong lượt này — nhà thuốc chỉ xem, chưa "
                "thao tác được (đơn còn có thể thay đổi)."
            )

    @staticmethod
    async def _chot_duoc_khong(
        conn: asyncpg.Connection, identity: StaffIdentity, don: asyncpg.Record
    ) -> None:
        """Chốt "không giao thêm" không được bỏ lại thuốc đã bán chưa giao.

        Review CP4 P1 #2 — trước CP5 (hoàn / trả / đảo) chưa có đường nào xử lý
        phần đã bán mà không giao, nên:
          * lần chờ xác minh → không chốt;
          * đã thu nhưng có phân lô chưa ghi bán được (cần đối soát) → không;
          * đã thu (luồng mới) → chỉ chốt khi đã giao đủ số bán.
        Chưa có lần thu, hoặc lần thu cũ (legacy): giữ nghĩa cũ.
        """
        lan = await conn.fetchrow(
            """
            SELECT payment_cycle_id, status, legacy FROM public.payment_cycle
             WHERE clinic_id = $1::uuid AND visit_id = $2::uuid AND kind = 'thuoc'
               AND status IN ('PENDING_VERIFICATION', 'PAID')
            """,
            identity.clinic_id,
            don["visit_id"],
        )
        if lan is None or lan["legacy"]:
            return
        if lan["status"] == "PENDING_VERIFICATION":
            raise ConflictError(
                "Tiền thuốc đang chờ xác minh chuyển khoản — chưa chốt dòng được."
            )
        if await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM public.prescription_allocation a
                 WHERE a.clinic_id = $1::uuid AND a.payment_cycle_id = $2::uuid
                   AND a.released_at IS NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM public.inventory_txn s
                        WHERE s.txn_type = 'SALE' AND s.allocation_id = a.id
                          AND s.payment_cycle_id = a.payment_cycle_id))
            """,
            identity.clinic_id,
            lan["payment_cycle_id"],
        ):
            raise ConflictError(
                "Lượt này đang cần đối soát (đã nhận tiền, chưa ghi bán được) — "
                "không chốt dòng; báo quản lý đối soát."
            )
        ban = (
            don["purchased_qty"]
            if don["purchased_qty"] is not None
            else (don["quantity_num"])
        )
        # CP5: phần đã "huỷ phần chưa giao" (SALE_REVERSAL) không còn là bán.
        da_dao = Decimal(
            str(
                await conn.fetchval(
                    """
                    SELECT coalesce(sum(t.quantity), 0)
                      FROM public.inventory_txn t
                      JOIN public.prescription_allocation a
                        ON a.id = t.allocation_id AND a.clinic_id = t.clinic_id
                     WHERE t.clinic_id = $1::uuid AND t.txn_type = 'SALE_REVERSAL'
                       AND t.payment_cycle_id = $2::uuid
                       AND a.prescription_id = $3::uuid
                    """,
                    identity.clinic_id,
                    lan["payment_cycle_id"],
                    don["id"],
                )
            )
        )
        ban_rong = Decimal(str(ban)) - da_dao if ban is not None else None
        da_giao = Decimal(str(don["dispensed_qty"] or 0))
        if ban_rong is None or da_giao < ban_rong:
            raise ConflictError(
                f"Đã bán {so(ban_rong or Decimal(0))}, mới giao {so(da_giao)} — "
                "chưa chốt được: phần đã bán chưa giao phải hoàn tiền rồi "
                "“Huỷ phần chưa giao” trước, không đóng dòng để bỏ lại."
            )

    @staticmethod
    async def _khoa_theo_luot(
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        prescription_id: str,
        *,
        cho_lich_su: bool = False,
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
            " WHERE id = $1::uuid AND clinic_id = $2::uuid"
            " /* rx:gom-ca-lich-su: tìm lượt theo id để khoá; removed_at kiểm"
            " ngay dưới, sau khi đã khoá */",
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
                   drug_catalog_id, closed_at, drug_name_raw, unit, removed_at
              FROM public.prescription
             WHERE id = $1::uuid AND clinic_id = $2::uuid
             /* rx:gom-ca-lich-su: khoá theo id; dòng lịch sử bị từ chối ngay
                dưới trừ lệnh đối soát (cho_lich_su) */
             FOR UPDATE
            """,
            prescription_id,
            identity.clinic_id,
        )
        if don is None or don["visit_id"] != vid:
            raise ConflictError("Dòng thuốc vừa thay đổi — tải lại rồi thử lại.")
        if don["removed_at"] is not None and not cho_lich_su:
            # CP6 Q3: dòng lịch sử không nhận tác động mới (thuốc kho, số mua,
            # lô, giao, chốt). Chỉ còn đối soát: huỷ phần chưa giao, khách trả.
            raise ConflictError(
                "Dòng thuốc này đã được bác sĩ đính chính — không thao tác mới "
                "được. Chỉ còn đối soát: huỷ phần chưa giao, khách trả thuốc."
            )
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
        """Không giao thêm dòng này nữa.

        Trước khi thu: đóng dòng (khách thôi lấy phần còn lại). Đã thu theo luồng
        mới: CHỈ khi đã giao đủ số bán — "đã thu 10, giao 5 rồi chốt" bị từ chối
        vì 5 viên đã bán sẽ không còn đường giao (chờ CP5 hoàn / trả). Lần thu
        cũ (legacy) giữ nghĩa cũ. Xem `_chot_duoc_khong`.
        """
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

    # ── Huỷ phần chưa giao / khách trả thuốc (contract tiền–thuốc CP5) ────

    async def huy_phan_chua_giao(
        self, *, identity: StaffIdentity, prescription_id: str, ly_do: str
    ) -> dict[str, Any]:
        """Nhả PHẦN ĐÃ BÁN MÀ CHƯA GIAO của dòng đơn — lệnh KHO, không phải tiền.

        Đảo đúng `bán − đã xuất` của từng phân lô còn bán (không nhận số tuỳ ý),
        mỗi dòng bán một lần. Phải có căn cứ tài chính — lần thu đã huỷ phiếu,
        hoặc đã hoàn tiền xong cho đủ phần ấy; DB kiểm lại (trigger
        `inventory_txn_ban_hop_le`). Sau đó phân lô không giao thêm được.
        """
        ly = (ly_do or "").strip()
        if not ly:
            raise ValidationError("Huỷ phần chưa giao thì ghi lý do.")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await self._khoa_theo_luot(
                    conn, identity, prescription_id, cho_lich_su=True
                )
                ban = await conn.fetch(
                    """
                    SELECT s.id::text AS sale_id, s.payment_cycle_id::text,
                           a.id::text AS allocation_id, a.drug_batch_id::text,
                           -s.quantity AS da_ban,
                           coalesce((SELECT -sum(d.quantity) FROM public.inventory_txn d
                                      WHERE d.txn_type = 'DISPENSE'
                                        AND d.allocation_id = a.id
                                        AND d.clinic_id = a.clinic_id), 0) AS da_xuat
                      FROM public.prescription_allocation a
                      JOIN public.inventory_txn s
                        ON s.allocation_id = a.id AND s.clinic_id = a.clinic_id
                       AND s.txn_type = 'SALE'
                     WHERE a.clinic_id = $1::uuid AND a.prescription_id = $2::uuid
                       AND NOT EXISTS (SELECT 1 FROM public.inventory_txn r
                                        WHERE r.txn_type = 'SALE_REVERSAL'
                                          AND r.reverses_txn_id = s.id)
                     ORDER BY a.id
                       FOR UPDATE OF a
                    """,
                    identity.clinic_id,
                    prescription_id,
                )
                dao = [
                    b
                    for b in ban
                    if Decimal(str(b["da_ban"])) > Decimal(str(b["da_xuat"]))
                ]
                if not dao:
                    raise ConflictError("Dòng này không còn phần đã bán mà chưa giao.")
                await khoa_lo(
                    conn,
                    clinic_id=identity.clinic_id,
                    lo_ids=[b["drug_batch_id"] for b in dao],
                )
                tong = Decimal(0)
                try:
                    for b in dao:
                        con = Decimal(str(b["da_ban"])) - Decimal(str(b["da_xuat"]))
                        tong += con
                        await conn.execute(
                            """
                            INSERT INTO public.inventory_txn
                                (clinic_id, drug_batch_id, txn_type, quantity, reason,
                                 ref_type, ref_id, performed_by_staff_id, performed_at,
                                 payment_cycle_id, allocation_id, reverses_txn_id)
                            VALUES ($1::uuid, $2::uuid, 'SALE_REVERSAL', $3, $4,
                                    'payment_cycle', $5::uuid, $6::uuid, now(),
                                    $5::uuid, $7::uuid, $8::uuid)
                            """,
                            identity.clinic_id,
                            b["drug_batch_id"],
                            con,
                            f"Huỷ phần chưa giao: {ly}",
                            b["payment_cycle_id"],
                            identity.staff_id,
                            b["allocation_id"],
                            b["sale_id"],
                        )
                except asyncpg.CheckViolationError as exc:
                    if "căn cứ" in str(exc):
                        raise ConflictError(
                            "Chưa có căn cứ để huỷ phần chưa giao: cần huỷ phiếu thu, "
                            "hoặc Quản lý hoàn tiền xong cho đủ phần chưa giao trước."
                        ) from exc
                    raise
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.undelivered_cancelled",
                    aggregate_type="prescription",
                    aggregate_id=prescription_id,
                    payload={
                        "quantity": str(tong),
                        "allocations": [b["allocation_id"] for b in dao],
                        "reason": ly,
                    },
                )
        return {"ok": True, "da_huy": so(tong)}

    async def khach_tra_thuoc(
        self,
        *,
        identity: StaffIdentity,
        dispense_txn_id: str,
        so_luong: Any,
        ly_do: str,
    ) -> dict[str, Any]:
        """Ghi nhận thuốc KHÁCH ĐÃ NHẬN rồi mang trả lại quầy.

        Nghĩa của lệnh chỉ là "thuốc vật lý đã quay lại" — KHÔNG phải quyết định
        bán lại / huỷ / cách ly (HOLD J1/J2), và KHÔNG tự hoàn tiền. Trỏ đúng
        DISPENSE gốc; lô trả = lô đã xuất; tổng trả không vượt số đã xuất (DB
        kiểm). Tồn vật lý tăng (`RETURN_RECEIVED`), nhưng phần trả chưa có
        quyết định xử lý không vào lượng có thể bán.
        """
        luong = _so(so_luong, ten="Số lượng trả")
        ly = (ly_do or "").strip()
        if len(ly) < 3:
            raise ValidationError("Ghi lý do khách trả thuốc (tối thiểu 3 ký tự).")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                xuat = await conn.fetchrow(
                    """
                    SELECT id::text, ref_id::text AS prescription_id,
                           drug_batch_id::text, allocation_id::text,
                           -quantity AS da_xuat
                      FROM public.inventory_txn
                     WHERE id = $1::uuid AND clinic_id = $2::uuid
                       AND txn_type = 'DISPENSE' AND ref_type = 'prescription'
                    """,
                    dispense_txn_id,
                    identity.clinic_id,
                )
                if xuat is None:
                    raise NotFoundError("Không tìm thấy lần giao thuốc gốc này.")
                don = await self._khoa_theo_luot(
                    conn, identity, xuat["prescription_id"], cho_lich_su=True
                )
                await khoa_lo(
                    conn, clinic_id=identity.clinic_id, lo_ids=[xuat["drug_batch_id"]]
                )
                da_tra = Decimal(
                    str(
                        await conn.fetchval(
                            "SELECT coalesce(sum(returned_qty), 0)"
                            " FROM public.drug_return WHERE clinic_id = $1::uuid"
                            " AND original_dispense_txn_id = $2::uuid",
                            identity.clinic_id,
                            dispense_txn_id,
                        )
                    )
                )
                con = Decimal(str(xuat["da_xuat"])) - da_tra
                if luong > con:
                    raise ValidationError(
                        f"Lần giao này xuất {so(Decimal(str(xuat['da_xuat'])))}, "
                        f"đã trả {so(da_tra)} — chỉ còn trả được {so(con)}."
                    )
                tra_id = await conn.fetchval(
                    """
                    INSERT INTO public.drug_return
                        (clinic_id, visit_id, prescription_id,
                         original_dispense_txn_id, allocation_id, drug_batch_id,
                         returned_qty, reason, returned_by)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6::uuid,
                            $7, $8, $9::uuid)
                    RETURNING id::text
                    """,
                    identity.clinic_id,
                    don["visit_id"],
                    xuat["prescription_id"],
                    dispense_txn_id,
                    xuat["allocation_id"],
                    xuat["drug_batch_id"],
                    luong,
                    ly,
                    identity.staff_id,
                )
                await self._ghi_so(
                    conn,
                    identity=identity,
                    drug_batch_id=xuat["drug_batch_id"],
                    txn_type=TRA_NHAN,
                    quantity=luong,
                    reason=ly,
                    ref_type="drug_return",
                    ref_id=tra_id,
                )
                await _log(
                    conn,
                    identity=identity,
                    event_type="pharmacy.drug_returned",
                    aggregate_type="prescription",
                    aggregate_id=xuat["prescription_id"],
                    payload={
                        "drug_return_id": tra_id,
                        "original_dispense_txn_id": dispense_txn_id,
                        "drug_batch_id": xuat["drug_batch_id"],
                        "quantity": str(luong),
                    },
                )
        return {"ok": True, "drug_return_id": tra_id}

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
                await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
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
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                    " /* rx:gom-ca-lich-su: dòng của phân lô vừa khoá qua"
                    " _khoa_phan_lo (đã chặn dòng lịch sử) */",
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
                f"Lô {lo['batch_code']} chỉ còn {so(max(kd, Decimal(0)))} có thể "
                f"phân lô lúc này — không đủ {so(luong)}."
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
                if don["closed_at"] is None:
                    await self._bat_buoc_kham_xong(conn, identity, don["visit_id"])
                    # CP5: còn phần ĐÃ BÁN mà chưa giao (ở bất kỳ lần thu nào,
                    # kể cả lần đã huỷ phiếu) thì không đóng dòng — chốt hay
                    # "khách không lấy" đều bỏ lại số thuốc ấy không ai xử lý.
                    chua_giao = await chua_giao_cua_dong(
                        conn, identity.clinic_id, prescription_id
                    )
                    if chua_giao > 0:
                        raise ConflictError(
                            f"Còn {so(chua_giao)} đã bán mà chưa giao — “Huỷ phần "
                            "chưa giao” (sau khi hoàn tiền hoặc huỷ phiếu) trước "
                            "khi đóng dòng."
                        )
                    if refusal_reason is None:
                        await self._chot_duoc_khong(conn, identity, don)
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
                        "WHERE id = $1::uuid AND clinic_id = $2::uuid"
                        " /* rx:gom-ca-lich-su: chỉ phân biệt 'không có' với"
                        " 'đã chốt từ trước' */",
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
