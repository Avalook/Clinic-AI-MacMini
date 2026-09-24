"""Hoàn tiền (contract tiền–thuốc CP5, 19/09/2026) — tiền thật trả lại khách.

HUỶ PHIẾU ≠ HOÀN TIỀN ≠ KHÁCH TRẢ THUỐC. Hoàn tiền:
  * tham chiếu ĐÚNG các dòng ảnh chụp hoá đơn (`payment_bill_line`) của lần
    thu gốc; số tiền do máy chủ tính = số lượng × đơn giá ảnh chụp — trình
    duyệt chỉ chọn dòng và số lượng;
  * được làm trên lần thu ĐÃ TỪNG thu (`paid_at`), kể cả khi lần thu ấy sau đó
    bị huỷ phiếu — tiền thật đã nhận thì vẫn có thể phải trả lại;
  * KHÔNG đụng kho. Nhả thuốc chưa giao là lệnh kho riêng (`huy_phan_chua_giao`)
    dùng khoản hoàn COMPLETED làm căn cứ;
  * không sửa `payment` / `payment_cycle` gốc; hoàn sau khi đóng lượt không mở
    lại lượt.

Tiền mặt: nhân viên xác nhận đã trả → COMPLETED ngay. Chuyển khoản / QR:
PENDING, rồi xác nhận kèm mã giao dịch (COMPLETED), hoặc FAILED / CANCELLED.

DB là lưới cuối: trigger khoá lần thu, kiểm luỹ kế hoàn từng dòng không vượt số
đã thu, số tiền = số lượng × đơn giá, và tiền đầu khoản = tổng dòng.
"""

from __future__ import annotations

import json
import uuid
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import DaHoanTien
from clinicai.events.emit import emit_event, nguoi
from clinicai.services.phan_lo_service import so

#: AI ĐƯỢC HOÀN TIỀN — TẠM THỜI, CHỜ DR4WOMEN DUYỆT (HOLD J4).
#: Chỉ Quản lý, để làm và thử CP5 trên PR nháp. Đây KHÔNG phải luật nghiệp vụ
#: cuối: trước khi merge / lên production phải thay bằng quyết định thật của
#: phòng khám (thu ngân tự hoàn tới mức nào, khoản nào Quản lý duyệt).
VAI_HOAN_TIEN_TAM_THOI: frozenset[ClinicRole] = frozenset({ClinicRole.MANAGEMENT})

PHUONG_THUC = frozenset({"CASH", "TRANSFER", "QR"})
DONG = frozenset({"FAILED", "CANCELLED"})


def _ly_do(raw: object) -> str:
    ly = raw.strip() if isinstance(raw, str) else ""
    if not 5 <= len(ly) <= 500:
        raise ValidationError("Lý do phải có từ 5 đến 500 ký tự.")
    return ly


def co_quyen_hoan(identity: StaffIdentity) -> bool:
    return identity.co_vai(VAI_HOAN_TIEN_TAM_THOI)


class HoanTienService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    def _cong(self, identity: StaffIdentity) -> None:
        if not co_quyen_hoan(identity):
            raise SafetyGateError(
                "Hoàn tiền tạm thời chỉ Quản lý làm được (chờ phòng khám chốt quyền)."
            )

    async def tao(
        self,
        *,
        identity: StaffIdentity,
        payment_cycle_id: str,
        visit_id: str,
        kind: str,
        dong: list[dict[str, Any]],
        method: str,
        reason: object,
    ) -> dict[str, Any]:
        """Một khoản hoàn cho các dòng của ảnh chụp hoá đơn lần thu gốc."""
        self._cong(identity)
        if method not in PHUONG_THUC:
            raise ValidationError(f"Phương thức hoàn không hợp lệ: {method!r}")
        ly_do = _ly_do(reason)
        yeu_cau: dict[str, Decimal] = {}
        for d in dong:
            try:
                sl = Decimal(str(d.get("so_luong")))
            except Exception as exc:  # noqa: BLE001
                raise ValidationError("Số lượng hoàn phải là một con số.") from exc
            if sl <= 0:
                raise ValidationError("Số lượng hoàn phải lớn hơn 0.")
            ma = str(d.get("payment_bill_line_id") or "")
            yeu_cau[ma] = yeu_cau.get(ma, Decimal(0)) + sl
        if not yeu_cau:
            raise ValidationError("Chọn ít nhất một dòng để hoàn.")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await _khoa_luot(conn, identity, visit_id)
                lan = await conn.fetchrow(
                    """
                    SELECT payment_cycle_id, paid_at FROM public.payment_cycle
                     WHERE payment_cycle_id = $1::uuid AND clinic_id = $2::uuid
                       AND visit_id = $3::uuid AND kind = $4
                     FOR UPDATE
                    """,
                    payment_cycle_id,
                    identity.clinic_id,
                    visit_id,
                    kind,
                )
                if lan is None:
                    raise NotFoundError("Không tìm thấy lần thu này của lượt khám.")
                if lan["paid_at"] is None:
                    raise ConflictError(
                        "Lần thu này chưa từng thu tiền — không có gì để hoàn."
                    )
                con = {
                    r["id"]: r
                    for r in await _con_hoan(conn, identity, payment_cycle_id)
                }
                tong = 0
                ghi: list[tuple[str, Decimal, int]] = []
                for ma, sl in yeu_cau.items():
                    r = con.get(ma)
                    if r is None:
                        raise ValidationError(
                            "Dòng hoàn không thuộc hoá đơn đã thu của lần thu này."
                        )
                    if r["don_gia"] is None or r["billing_owner"] != "CLINIC":
                        raise ValidationError(
                            f"“{r['ten']}” không phải khoản phòng khám đã thu "
                            "— không hoàn."
                        )
                    if sl > r["con_hoan"]:
                        raise ConflictError(
                            f"“{r['ten']}” đã thu {so(r['so_luong'])}, đã hoàn "
                            f"{so(r['da_hoan'])} — chỉ còn hoàn được "
                            f"{so(r['con_hoan'])}."
                        )
                    tien = int(
                        (sl * r["don_gia"]).quantize(Decimal(1), rounding=ROUND_HALF_UP)
                    )
                    if tien <= 0:
                        raise ValidationError(
                            f"“{r['ten']}” thu 0đ — không có tiền để hoàn."
                        )
                    ghi.append((ma, sl, tien))
                    tong += tien
                refund_id = str(uuid.uuid4())
                tien_mat = method == "CASH"
                await conn.execute(
                    """
                    INSERT INTO public.payment_refund (
                        refund_id, clinic_id, visit_id, kind, payment_cycle_id,
                        amount, status, method, reason, created_by,
                        completed_by, completed_at)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5::uuid, $6, $7, $8,
                            $9, $10::uuid,
                            CASE WHEN $7 = 'COMPLETED' THEN $10::uuid END,
                            CASE WHEN $7 = 'COMPLETED' THEN now() END)
                    """,
                    refund_id,
                    identity.clinic_id,
                    visit_id,
                    kind,
                    payment_cycle_id,
                    tong,
                    "COMPLETED" if tien_mat else "PENDING",
                    method,
                    ly_do,
                    identity.staff_id,
                )
                await conn.executemany(
                    """
                    INSERT INTO public.payment_refund_line (
                        clinic_id, refund_id, payment_cycle_id, payment_bill_line_id,
                        quantity, amount)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6)
                    """,
                    [
                        (identity.clinic_id, refund_id, payment_cycle_id, ma, sl, tien)
                        for ma, sl, tien in ghi
                    ],
                )
                if tien_mat:
                    await _phat_da_hoan(conn, identity, visit_id, refund_id, int(tong))
                await _log(
                    conn,
                    identity,
                    "payment.refunded" if tien_mat else "payment.refund_pending",
                    refund_id,
                    {
                        "refund_id": refund_id,
                        "payment_cycle_id": payment_cycle_id,
                        "visit_id": visit_id,
                        "kind": kind,
                        "amount": tong,
                        "method": method,
                        "lines": [
                            {"payment_bill_line_id": ma, "quantity": str(sl)}
                            for ma, sl, _ in ghi
                        ],
                    },
                )
        return {
            "refund_id": refund_id,
            "status": "COMPLETED" if tien_mat else "PENDING",
            "amount": tong,
        }

    async def xac_nhan(
        self, *, identity: StaffIdentity, refund_id: str, reference: object
    ) -> dict[str, Any]:
        """Khoản hoàn chuyển khoản / QR đã chuyển xong, kèm mã giao dịch."""
        self._cong(identity)
        ma = reference.strip() if isinstance(reference, str) else ""
        if not 3 <= len(ma) <= 100:
            raise ValidationError("Nhập mã giao dịch ngân hàng (3–100 ký tự).")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                hoan = await _khoa_hoan(conn, identity, refund_id)
                if hoan["status"] == "COMPLETED":
                    if hoan["reference"] == ma or hoan["method"] == "CASH":
                        return {"refund_id": refund_id, "status": "COMPLETED"}
                    raise ConflictError("Khoản hoàn này đã xác nhận với mã khác.")
                if hoan["status"] != "PENDING":
                    raise ConflictError("Khoản hoàn này đã đóng — không xác nhận được.")
                await conn.execute(
                    """
                    UPDATE public.payment_refund
                       SET status = 'COMPLETED', reference = $3,
                           completed_by = $4::uuid, completed_at = now()
                     WHERE refund_id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    refund_id,
                    identity.clinic_id,
                    ma,
                    identity.staff_id,
                )
                vid_hoan = await conn.fetchval(
                    "SELECT visit_id::text FROM public.payment_refund"
                    " WHERE refund_id = $1::uuid AND clinic_id = $2::uuid",
                    refund_id,
                    identity.clinic_id,
                )
                await _phat_da_hoan(
                    conn, identity, str(vid_hoan), refund_id, int(hoan["amount"])
                )
                await _log(
                    conn,
                    identity,
                    "payment.refunded",
                    refund_id,
                    {
                        "refund_id": refund_id,
                        "payment_cycle_id": str(hoan["payment_cycle_id"]),
                        "amount": int(hoan["amount"]),
                        "method": hoan["method"],
                        "reference": ma,
                    },
                )
        return {"refund_id": refund_id, "status": "COMPLETED"}

    async def dong(
        self,
        *,
        identity: StaffIdentity,
        refund_id: str,
        trang_thai: str,
        reason: object,
    ) -> dict[str, Any]:
        """Khoản hoàn đang chờ: thử mà không thành (FAILED) hoặc chủ động huỷ
        yêu cầu chưa làm (CANCELLED). Hai sự thật khác nhau, giữ riêng."""
        self._cong(identity)
        if trang_thai not in DONG:
            raise ValidationError("Chỉ đóng khoản hoàn thành FAILED hoặc CANCELLED.")
        ly_do = _ly_do(reason)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                hoan = await _khoa_hoan(conn, identity, refund_id)
                if hoan["status"] == trang_thai:
                    return {"refund_id": refund_id, "status": trang_thai}
                if hoan["status"] != "PENDING":
                    raise ConflictError(
                        "Chỉ đóng được khoản hoàn đang chờ — khoản này đã "
                        + ("hoàn xong." if hoan["status"] == "COMPLETED" else "đóng.")
                    )
                await conn.execute(
                    """
                    UPDATE public.payment_refund
                       SET status = $3, closed_by = $4::uuid, closed_at = now(),
                           closed_reason = $5
                     WHERE refund_id = $1::uuid AND clinic_id = $2::uuid
                    """,
                    refund_id,
                    identity.clinic_id,
                    trang_thai,
                    identity.staff_id,
                    ly_do,
                )
                await _log(
                    conn,
                    identity,
                    "payment.refund_failed"
                    if trang_thai == "FAILED"
                    else "payment.refund_cancelled",
                    refund_id,
                    {
                        "refund_id": refund_id,
                        "payment_cycle_id": str(hoan["payment_cycle_id"]),
                        "amount": int(hoan["amount"]),
                        "reason": ly_do,
                    },
                )
        return {"refund_id": refund_id, "status": trang_thai}


async def _phat_da_hoan(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    refund_id: str,
    so_tien: int,
) -> None:
    """`payment.refunded` vào sổ sự kiện khi tiền hoàn đã thật sự trả khách."""
    await emit_event(
        conn,
        ten="payment.refunded",
        clinic_id=identity.clinic_id,
        aggregate_id=refund_id,
        payload=DaHoanTien(visit_id=visit_id, refund_id=refund_id, so_tien=so_tien),
        boi=nguoi(identity),
        correlation_id=visit_id,
    )


async def _khoa_luot(
    conn: asyncpg.Connection, identity: StaffIdentity, visit_id: str
) -> None:
    if not await conn.fetchval(
        "SELECT 1 FROM public.visit WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
        " FOR UPDATE",
        identity.clinic_id,
        visit_id,
    ):
        raise NotFoundError("Không tìm thấy lượt khám này.")


async def _khoa_hoan(
    conn: asyncpg.Connection, identity: StaffIdentity, refund_id: str
) -> asyncpg.Record:
    """visit → lần thu → khoản hoàn (cùng thứ tự khoá chung)."""
    goc = await conn.fetchrow(
        "SELECT visit_id::text, payment_cycle_id::text FROM public.payment_refund"
        " WHERE refund_id = $1::uuid AND clinic_id = $2::uuid",
        refund_id,
        identity.clinic_id,
    )
    if goc is None:
        raise NotFoundError("Không tìm thấy khoản hoàn này.")
    await _khoa_luot(conn, identity, goc["visit_id"])
    await conn.execute(
        "SELECT 1 FROM public.payment_cycle WHERE payment_cycle_id = $1::uuid"
        " AND clinic_id = $2::uuid FOR UPDATE",
        goc["payment_cycle_id"],
        identity.clinic_id,
    )
    hoan = await conn.fetchrow(
        """
        SELECT refund_id, payment_cycle_id, status, method, amount, reference
          FROM public.payment_refund
         WHERE refund_id = $1::uuid AND clinic_id = $2::uuid
         FOR UPDATE
        """,
        refund_id,
        identity.clinic_id,
    )
    assert hoan is not None
    return hoan


async def _con_hoan(
    conn: asyncpg.Connection, identity: StaffIdentity, payment_cycle_id: str
) -> list[asyncpg.Record]:
    """Các dòng ảnh chụp của lần thu, kèm số đã hoàn / còn hoàn được."""
    return list(
        await conn.fetch(
            """
            SELECT b.id::text AS id, b.name_snapshot AS ten, b.source_type,
                   b.source_id, b.quantity AS so_luong, b.unit AS don_vi,
                   b.unit_price AS don_gia, b.billing_owner,
                   coalesce(h.da_hoan, 0) AS da_hoan,
                   b.quantity - coalesce(h.da_hoan, 0) AS con_hoan
              FROM public.payment_bill_line b
              LEFT JOIN LATERAL (
                   SELECT sum(l.quantity) AS da_hoan
                     FROM public.payment_refund_line l
                     JOIN public.payment_refund r
                       ON r.refund_id = l.refund_id AND r.clinic_id = l.clinic_id
                    WHERE l.clinic_id = b.clinic_id AND l.payment_bill_line_id = b.id
                      AND r.status IN ('PENDING', 'COMPLETED')) h ON true
             WHERE b.clinic_id = $1::uuid AND b.payment_cycle_id = $2::uuid
             ORDER BY b.source_type, b.created_at, b.id
            """,
            identity.clinic_id,
            payment_cycle_id,
        )
    )


async def hoan_cua_cac_lan_thu(
    conn: asyncpg.Connection, identity: StaffIdentity, cycle_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Cho lịch sử giao dịch: khoản hoàn + dòng còn hoàn được, theo lần thu."""
    if not cycle_ids:
        return {}
    hoan = await conn.fetch(
        """
        SELECT r.refund_id::text, r.payment_cycle_id::text, r.amount, r.status,
               r.method, r.reason, r.reference, r.created_at, r.completed_at,
               r.closed_at, r.closed_reason,
               -- D4: hoàn sau khi lượt đã đóng — lượt KHÔNG mở lại, nhưng lịch
               -- sử phải nói rõ đây là giao dịch phát sinh sau.
               (v.closed_at IS NOT NULL AND r.created_at > v.closed_at)
                   AS sau_khi_dong_luot
          FROM public.payment_refund r
          JOIN public.visit v
            ON v.visit_id = r.visit_id AND v.clinic_id = r.clinic_id
         WHERE r.clinic_id = $1::uuid AND r.payment_cycle_id = ANY($2::uuid[])
         ORDER BY r.created_at
        """,
        identity.clinic_id,
        cycle_ids,
    )
    ket_qua: dict[str, dict[str, Any]] = {
        c: {"khoan_hoan": [], "dong_hoan_duoc": []} for c in cycle_ids
    }
    for r in hoan:
        ket_qua[r["payment_cycle_id"]]["khoan_hoan"].append(dict(r))
    for c in cycle_ids:
        for d in await _con_hoan(conn, identity, c):
            if d["billing_owner"] == "CLINIC" and d["don_gia"] is not None:
                ket_qua[c]["dong_hoan_duoc"].append(
                    {
                        "payment_bill_line_id": d["id"],
                        "ten": d["ten"],
                        "so_luong": d["so_luong"],
                        "don_vi": d["don_vi"],
                        "don_gia": d["don_gia"],
                        "da_hoan": d["da_hoan"],
                        "con_hoan": d["con_hoan"],
                    }
                )
    return ket_qua


async def _log(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    event_type: str,
    refund_id: str,
    payload: dict[str, Any],
) -> None:
    await conn.execute(
        """
        INSERT INTO event_log (clinic_id, event_type, aggregate_type, aggregate_id,
                               payload, metadata, source, event_published)
        VALUES ($1::uuid, $2, 'payment_refund', $3::uuid, $4, $5, $6, FALSE)
        """,
        identity.clinic_id,
        event_type,
        refund_id,
        json.dumps(payload),
        json.dumps(
            {
                "clinic_role": identity.role.value,
                "vai_tai_khoan": identity.vai_goc.value,
                "clinic_staff_id": identity.staff_id,
                "actor_auth_user_id": identity.auth_user_id,
            }
        ),
        f"api:{event_type.replace('.', '-')}",
    )
