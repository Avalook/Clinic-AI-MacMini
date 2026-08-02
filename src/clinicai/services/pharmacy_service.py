"""Đường ghi kho thuốc: nhập, xuất, điều chỉnh, huỷ lô (B.3).

Bảng `drug_batch` / `inventory_txn` đã có từ `20260802000001`, nhưng chưa có
đường nào ghi vào: màn /pharmacy 980 dòng là read-only. Database cố ý không có
policy INSERT/UPDATE/DELETE cho `authenticated` (ADR-0004), nên mọi ghi phải đi
qua đây bằng `service_role`.

Ba luật của file này, và cả ba đều là luật về *sổ sách* chứ không phải về code:

1. **`quantity_on_hand` không bao giờ được ghi thẳng.** Nó là tổng của
   `inventory_txn`; trigger `inventory_txn_apply()` cộng dồn. Ghi tay vào cột đó
   là làm sổ và số dư lệch nhau mà không dòng nào giải thích được vì sao.

2. **FEFO — hạn gần nhất ra trước**, và lô đã hết hạn thì không ra. Cấp phát
   theo thứ tự nào là quyết định lâm sàng, không phải chi tiết cài đặt: chọn sai
   thứ tự nghĩa là thuốc hết hạn nằm lại trong kho cho tới khi có người cầm nhầm.

3. **`clinic_id` luôn lấy từ identity**, không bao giờ từ body. Batch id trong
   URL là *bộ chọn*: mọi câu lệnh đều kèm `AND clinic_id = $identity`, nên một id
   đoán được của phòng khám khác chỉ ra 404 chứ không ra dữ liệu.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity

logger = structlog.get_logger()

QUANTITY_STEP = Decimal("0.001")
MAX_QUANTITY = Decimal("1000000")
MIN_REASON_LENGTH = 5
MAX_REASON_LENGTH = 500

TXN_RECEIVE = "RECEIVE"
TXN_DISPENSE = "DISPENSE"
TXN_ADJUST = "ADJUST"
TXN_DISCARD = "DISCARD"

REF_MANUAL = "manual"
REF_PRESCRIPTION = "prescription"


# ---------------------------------------------------------------------------
# Luật thuần — không chạm database, test được bằng bảng số liệu
# ---------------------------------------------------------------------------


def normalize_quantity(value: object, *, field: str = "quantity") -> Decimal:
    """Số lượng hợp lệ: dương, hữu hạn, tối đa 3 chữ số thập phân.

    Nhận cả float lẫn Decimal vì pydantic có thể trả về một trong hai, và đi
    vòng qua ``str`` để 0.1 không trở thành 0.1000000000000000055.
    """
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"{field} không phải là một con số") from exc

    if not quantity.is_finite():
        raise ValidationError(f"{field} không phải là một con số")
    if quantity <= 0:
        raise ValidationError(f"{field} phải lớn hơn 0")
    if quantity > MAX_QUANTITY:
        raise ValidationError(f"{field} vượt quá {MAX_QUANTITY:,.0f}")
    if quantity != quantity.quantize(QUANTITY_STEP):
        raise ValidationError(f"{field} tối đa 3 chữ số thập phân")
    return quantity.quantize(QUANTITY_STEP)


def normalize_delta(value: object, *, field: str = "quantity") -> Decimal:
    """Như trên nhưng cho phép âm — điều chỉnh đi cả hai chiều, trừ số 0.

    Điều chỉnh 0 là một dòng sổ nói "không có gì thay đổi": nó không sai, nhưng
    nó làm loãng sổ kiểm kê nên bị từ chối thẳng.
    """
    try:
        delta = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(f"{field} không phải là một con số") from exc

    if not delta.is_finite():
        raise ValidationError(f"{field} không phải là một con số")
    if delta == 0:
        raise ValidationError("Điều chỉnh 0 không phải là một điều chỉnh")
    if abs(delta) > MAX_QUANTITY:
        raise ValidationError(f"{field} vượt quá {MAX_QUANTITY:,.0f}")
    if delta != delta.quantize(QUANTITY_STEP):
        raise ValidationError(f"{field} tối đa 3 chữ số thập phân")
    return delta.quantize(QUANTITY_STEP)


def normalize_reason(value: object, *, required: bool = True) -> str | None:
    """Lý do là thứ người kiểm kê sáu tháng sau đọc, nên nó phải có nội dung."""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        if required:
            raise ValidationError("Phải ghi lý do")
        return None
    if len(text) < MIN_REASON_LENGTH:
        raise ValidationError(f"Lý do phải dài ít nhất {MIN_REASON_LENGTH} ký tự")
    return text[:MAX_REASON_LENGTH]


@dataclass(frozen=True)
class BatchStock:
    """Một lô như kho nhìn thấy nó: còn bao nhiêu, hạn tới bao giờ."""

    batch_id: str
    batch_code: str
    expiry_date: date
    quantity_on_hand: Decimal


@dataclass(frozen=True)
class Allocation:
    """Lấy bao nhiêu từ lô nào."""

    batch_id: str
    batch_code: str
    quantity: Decimal


def allocate_fefo(
    batches: list[BatchStock], quantity: Decimal, *, today: date
) -> list[Allocation]:
    """Chia số lượng cần xuất theo FEFO — hạn gần nhất ra trước.

    Lô đã hết hạn KHÔNG được tính, kể cả khi vì thế mà không đủ hàng. "Không đủ
    thuốc" là câu người dược sĩ xử lý được; thuốc hết hạn đã phát cho bệnh nhân
    thì không.

    Sắp xếp phụ theo ``batch_code`` để hai lô cùng hạn luôn ra cùng một thứ tự —
    một hàm chia hàng mà chạy hai lần ra hai kết quả là thứ không ai đối soát nổi.
    """
    usable = sorted(
        (b for b in batches if b.quantity_on_hand > 0 and b.expiry_date >= today),
        key=lambda b: (b.expiry_date, b.batch_code, b.batch_id),
    )

    remaining = quantity
    allocations: list[Allocation] = []
    for batch in usable:
        if remaining <= 0:
            break
        take = min(remaining, batch.quantity_on_hand)
        allocations.append(Allocation(batch.batch_id, batch.batch_code, take))
        remaining -= take

    if remaining > 0:
        expired_units = sum(
            (b.quantity_on_hand for b in batches if b.expiry_date < today),
            Decimal(0),
        )
        message = f"Kho không đủ: còn thiếu {remaining.normalize():f}"
        if expired_units > 0:
            # Không nói câu này thì màn hình báo "không đủ" trong khi bảng tồn
            # kho ngay bên cạnh hiển thị một con số to hơn — trông như app sai.
            message += (
                f". Có {expired_units.normalize():f} ở các lô đã hết hạn, "
                "không được cấp phát"
            )
        raise ConflictError(message)

    return allocations


# ---------------------------------------------------------------------------
# Đường ghi
# ---------------------------------------------------------------------------


class PharmacyService:
    """Ghi kho thuốc. Mọi phương thức chạy trong đúng một transaction."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def receive_batch(
        self,
        *,
        identity: StaffIdentity,
        drug_catalog_id: str,
        batch_code: str,
        expiry_date: date,
        quantity: object,
        unit: str,
        cost_price: int | None = None,
        reason: object = None,
    ) -> dict[str, object]:
        """Nhập hàng: tạo lô nếu chưa có, rồi ghi một dòng RECEIVE.

        Lô mới luôn sinh ra với tồn 0 và nhận hàng bằng một dòng txn, để số dư
        của mọi lô — kể cả lô vừa tạo — đều truy được về sổ.
        """
        amount = normalize_quantity(quantity)
        note = normalize_reason(reason, required=False)
        code = batch_code.strip()
        if not code:
            raise ValidationError("Phải có mã lô")
        unit_label = unit.strip() or "viên"

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                catalog = await conn.fetchrow(
                    """
                    SELECT id, name_base, name_raw
                      FROM drug_catalog
                     WHERE id = $1::uuid AND clinic_id = $2::uuid AND is_active
                    """,
                    drug_catalog_id,
                    identity.clinic_id,
                )
                if catalog is None:
                    raise NotFoundError("Không tìm thấy thuốc trong danh mục")

                existing = await conn.fetchrow(
                    """
                    SELECT id, drug_catalog_id, expiry_date, unit
                      FROM drug_batch
                     WHERE clinic_id = $1::uuid AND batch_code = $2
                     FOR UPDATE
                    """,
                    identity.clinic_id,
                    code,
                )

                if existing is None:
                    batch_id = await conn.fetchval(
                        """
                        INSERT INTO drug_batch (
                            clinic_id, drug_catalog_id, batch_code, expiry_date,
                            quantity_on_hand, unit, cost_price
                        )
                        VALUES ($1::uuid, $2::uuid, $3, $4, 0, $5, $6)
                        RETURNING id
                        """,
                        identity.clinic_id,
                        drug_catalog_id,
                        code,
                        expiry_date,
                        unit_label,
                        cost_price,
                    )
                else:
                    # Cùng mã lô nhưng khác thuốc hoặc khác hạn là hai lô khác
                    # nhau bị gọi trùng tên. Gộp chúng lại thì hạn dùng của số
                    # thuốc đang nằm trong kho trở thành một con số bịa.
                    if str(existing["drug_catalog_id"]) != str(drug_catalog_id):
                        raise ConflictError(
                            f"Mã lô {code} đang thuộc về một thuốc khác"
                        )
                    if existing["expiry_date"] != expiry_date:
                        raise ConflictError(
                            f"Mã lô {code} đang có hạn dùng "
                            f"{existing['expiry_date']:%d/%m/%Y}"
                        )
                    batch_id = existing["id"]
                    if cost_price is not None:
                        await conn.execute(
                            """
                            UPDATE drug_batch
                               SET cost_price = $2, updated_at = now()
                             WHERE id = $1::uuid
                            """,
                            batch_id,
                            cost_price,
                        )

                txn_id = await _insert_txn(
                    conn,
                    identity=identity,
                    batch_id=str(batch_id),
                    txn_type=TXN_RECEIVE,
                    quantity=amount,
                    reason=note or "Nhập hàng",
                    ref_type=REF_MANUAL,
                    ref_id=None,
                )
                on_hand = await _current_stock(conn, identity, str(batch_id))

                await _log_inventory_event(
                    conn,
                    identity=identity,
                    event_type="pharmacy.stock_received",
                    batch_id=str(batch_id),
                    payload={
                        "batch_code": code,
                        "drug_catalog_id": str(drug_catalog_id),
                        "quantity": str(amount),
                        "unit": unit_label,
                        "expiry_date": expiry_date.isoformat(),
                        "quantity_on_hand": str(on_hand),
                        "txn_id": str(txn_id),
                    },
                )

        logger.info(
            "pharmacy_stock_received",
            batch_code=code,
            quantity=str(amount),
            clinic_id=identity.clinic_id,
        )
        return {
            "batch_id": str(batch_id),
            "batch_code": code,
            "quantity_on_hand": str(on_hand),
            "txn_ids": [str(txn_id)],
        }

    async def adjust_batch(
        self,
        *,
        identity: StaffIdentity,
        batch_id: str,
        quantity: object,
        reason: object,
    ) -> dict[str, object]:
        """Điều chỉnh tồn sau kiểm kê. Lý do bắt buộc, đi cả hai chiều."""
        delta = normalize_delta(quantity)
        note = normalize_reason(reason)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                batch = await _lock_batch(conn, identity, batch_id)
                on_hand = Decimal(str(batch["quantity_on_hand"]))
                if on_hand + delta < 0:
                    raise ConflictError(
                        f"Lô {batch['batch_code']} chỉ còn {on_hand.normalize():f}, "
                        f"không giảm được {abs(delta).normalize():f}"
                    )

                txn_id = await _insert_txn(
                    conn,
                    identity=identity,
                    batch_id=batch_id,
                    txn_type=TXN_ADJUST,
                    quantity=delta,
                    reason=note,
                    ref_type=REF_MANUAL,
                    ref_id=None,
                )
                new_stock = await _current_stock(conn, identity, batch_id)

                await _log_inventory_event(
                    conn,
                    identity=identity,
                    event_type="pharmacy.stock_adjusted",
                    batch_id=batch_id,
                    payload={
                        "batch_code": batch["batch_code"],
                        "quantity": str(delta),
                        "reason": note,
                        "quantity_before": str(on_hand),
                        "quantity_on_hand": str(new_stock),
                        "txn_id": str(txn_id),
                    },
                )

        return {
            "batch_id": batch_id,
            "quantity_on_hand": str(new_stock),
            "txn_ids": [str(txn_id)],
        }

    async def discard_batch(
        self,
        *,
        identity: StaffIdentity,
        batch_id: str,
        quantity: object | None,
        reason: object,
    ) -> dict[str, object]:
        """Huỷ hàng (hết hạn, vỡ, hỏng). ``quantity`` bỏ trống = huỷ cả lô."""
        note = normalize_reason(reason)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                batch = await _lock_batch(conn, identity, batch_id)
                on_hand = Decimal(str(batch["quantity_on_hand"]))
                if on_hand <= 0:
                    raise ConflictError(
                        f"Lô {batch['batch_code']} đã hết, không còn gì để huỷ"
                    )

                amount = on_hand if quantity is None else normalize_quantity(quantity)
                if amount > on_hand:
                    raise ConflictError(
                        f"Lô {batch['batch_code']} chỉ còn {on_hand.normalize():f}"
                    )

                txn_id = await _insert_txn(
                    conn,
                    identity=identity,
                    batch_id=batch_id,
                    txn_type=TXN_DISCARD,
                    quantity=-amount,
                    reason=note,
                    ref_type=REF_MANUAL,
                    ref_id=None,
                )
                new_stock = await _current_stock(conn, identity, batch_id)

                await _log_inventory_event(
                    conn,
                    identity=identity,
                    event_type="pharmacy.stock_discarded",
                    batch_id=batch_id,
                    payload={
                        "batch_code": batch["batch_code"],
                        "quantity": str(amount),
                        "reason": note,
                        "quantity_on_hand": str(new_stock),
                        "txn_id": str(txn_id),
                    },
                )

        return {
            "batch_id": batch_id,
            "quantity_on_hand": str(new_stock),
            "txn_ids": [str(txn_id)],
        }

    async def dispense(
        self,
        *,
        identity: StaffIdentity,
        drug_catalog_id: str,
        quantity: object,
        prescription_id: str | None = None,
        reason: object = None,
    ) -> dict[str, object]:
        """Cấp thuốc: trừ kho theo FEFO, một dòng sổ cho mỗi lô đã lấy.

        ``prescription_id`` chỉ là *tham chiếu*. `prescription.quantity` trong
        schema là text tự do ("30 viên", "1 hộp"), nên không có cách nào suy ra
        số lượng từ đơn — người dược sĩ nhập số thật đã đưa, và dòng sổ giữ lại
        đường dẫn về đơn thuốc.
        """
        amount = normalize_quantity(quantity)
        note = normalize_reason(reason, required=False)

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                if prescription_id is not None:
                    exists = await conn.fetchval(
                        """
                        SELECT 1 FROM prescription
                         WHERE id = $1::uuid AND clinic_id = $2::uuid
                        """,
                        prescription_id,
                        identity.clinic_id,
                    )
                    if not exists:
                        raise NotFoundError("Không tìm thấy đơn thuốc")

                rows = await conn.fetch(
                    """
                    SELECT id, batch_code, expiry_date, quantity_on_hand
                      FROM drug_batch
                     WHERE clinic_id = $1::uuid
                       AND drug_catalog_id = $2::uuid
                       AND quantity_on_hand > 0
                     ORDER BY expiry_date, batch_code
                     FOR UPDATE
                    """,
                    identity.clinic_id,
                    drug_catalog_id,
                )
                if not rows:
                    raise ConflictError("Kho không còn lô nào của thuốc này")

                today = await conn.fetchval("SELECT CURRENT_DATE")
                allocations = allocate_fefo(
                    [
                        BatchStock(
                            batch_id=str(r["id"]),
                            batch_code=r["batch_code"],
                            expiry_date=r["expiry_date"],
                            quantity_on_hand=Decimal(str(r["quantity_on_hand"])),
                        )
                        for r in rows
                    ],
                    amount,
                    today=today,
                )

                txn_ids: list[str] = []
                for allocation in allocations:
                    txn_id = await _insert_txn(
                        conn,
                        identity=identity,
                        batch_id=allocation.batch_id,
                        txn_type=TXN_DISPENSE,
                        quantity=-allocation.quantity,
                        reason=note or "Cấp thuốc",
                        ref_type=(REF_PRESCRIPTION if prescription_id else REF_MANUAL),
                        ref_id=prescription_id,
                    )
                    txn_ids.append(str(txn_id))

                await _log_inventory_event(
                    conn,
                    identity=identity,
                    event_type="pharmacy.dispensed",
                    batch_id=allocations[0].batch_id,
                    payload={
                        "drug_catalog_id": str(drug_catalog_id),
                        "prescription_id": prescription_id,
                        "quantity": str(amount),
                        "allocations": [
                            {
                                "batch_id": a.batch_id,
                                "batch_code": a.batch_code,
                                "quantity": str(a.quantity),
                            }
                            for a in allocations
                        ],
                        "txn_ids": txn_ids,
                    },
                )

        logger.info(
            "pharmacy_dispensed",
            quantity=str(amount),
            batches=len(allocations),
            clinic_id=identity.clinic_id,
        )
        return {
            "quantity": str(amount),
            "allocations": [
                {
                    "batch_id": a.batch_id,
                    "batch_code": a.batch_code,
                    "quantity": str(a.quantity),
                }
                for a in allocations
            ],
            "txn_ids": txn_ids,
        }


# ---------------------------------------------------------------------------
# Helper dùng chung — đều chạy BÊN TRONG transaction của phương thức gọi
# ---------------------------------------------------------------------------


async def _lock_batch(
    conn: asyncpg.Connection, identity: StaffIdentity, batch_id: str
) -> asyncpg.Record:
    """Khoá lô của CHÍNH phòng khám này. Lô phòng khám khác = không tồn tại."""
    batch = await conn.fetchrow(
        """
        SELECT id, batch_code, quantity_on_hand, expiry_date
          FROM drug_batch
         WHERE id = $1::uuid AND clinic_id = $2::uuid
         FOR UPDATE
        """,
        batch_id,
        identity.clinic_id,
    )
    if batch is None:
        raise NotFoundError("Không tìm thấy lô thuốc")
    return batch


async def _insert_txn(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    batch_id: str,
    txn_type: str,
    quantity: Decimal,
    reason: str | None,
    ref_type: str | None,
    ref_id: str | None,
) -> object:
    """Ghi một dòng sổ. Trigger `inventory_txn_apply()` lo phần cộng trừ tồn."""
    return await conn.fetchval(
        """
        INSERT INTO inventory_txn (
            clinic_id, drug_batch_id, txn_type, quantity, reason,
            ref_type, ref_id, performed_by_staff_id
        )
        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid, $8::uuid)
        RETURNING id
        """,
        identity.clinic_id,
        batch_id,
        txn_type,
        quantity,
        reason,
        ref_type,
        ref_id,
        identity.staff_id,
    )


async def _current_stock(
    conn: asyncpg.Connection, identity: StaffIdentity, batch_id: str
) -> Decimal:
    """Đọc lại tồn SAU trigger — không tự cộng trong Python rồi tin vào nó."""
    value = await conn.fetchval(
        """
        SELECT quantity_on_hand FROM drug_batch
         WHERE id = $1::uuid AND clinic_id = $2::uuid
        """,
        batch_id,
        identity.clinic_id,
    )
    return Decimal(str(value))


async def _log_inventory_event(
    conn: asyncpg.Connection,
    *,
    identity: StaffIdentity,
    event_type: str,
    batch_id: str,
    payload: dict[str, object],
) -> None:
    """Vết kiểm toán, ghi trong cùng transaction với chính biến động kho.

    Không có PHI ở đây: mã lô, số lượng, id đơn thuốc — đủ để trả lời "ai đã
    đụng vào kho" mà không kéo theo tên bệnh nhân vào một bảng mà cả phòng
    quản lý đọc được.
    """
    await conn.execute(
        """
        INSERT INTO event_log (
            clinic_id, event_type, aggregate_type, aggregate_id, payload,
            metadata, source, actor_staff_id, event_published
        )
        VALUES ($1::uuid, $2, 'drug_batch', $3::uuid, $4, $5, $6, $7::uuid, FALSE)
        """,
        identity.clinic_id,
        event_type,
        batch_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "actor_auth_user_id": identity.auth_user_id,
            }
        ),
        f"api:{event_type.replace('.', '-')}",
        identity.staff_id,
    )
