"""Đổi hình thức thu (TM / CK / QR) SAU KHI ĐÃ THU — V7, Tuyền chốt 30/09/2026.

"Thu nhầm tiền mặt mà khách chuyển khoản" là chuyện hằng ngày ở quầy; trước đây
chỉ còn cách huỷ phiếu rồi thu lại (mất phiếu, lệch báo cáo huỷ). Nay:

* ``payment_cycle.method`` giữ nguyên — hình thức GHI LÚC THU, bất biến (trigger
  ``trg_payment_cycle_guard``). Mỗi lần đổi là một dòng trong sổ CHỈ THÊM
  ``payment_cycle_doi_hinh_thuc``; hình thức HIỆU LỰC = dòng mới nhất, đọc qua
  hàm SQL ``hinh_thuc_hieu_luc(clinic, cycle, goc)`` ở MỌI chỗ đọc hình thức.
* AI CŨNG ĐỔI ĐƯỢC ("mở hết", 30/09): mọi người giữ một trong hai khối thu tiền
  (dịch vụ hoặc thuốc), không phân biệt loại phiếu, không cần là người đã thu.
* Không đổi: phiếu đã huỷ (không còn là tiền đã thu), phiếu có khoản hoàn đang
  chờ / đã hoàn (tiền hoàn đã đi theo hình thức cũ). Luật này ép ở trigger của
  sổ; service kiểm trước chỉ để có câu dễ hiểu.
* Mã giao dịch tuỳ chọn (như lúc thu, mig 20260925000007). Lý do tuỳ chọn.
* Đổi hình thức KHÔNG phải huỷ: báo cáo cuối ngày có mục riêng "Đổi hình thức".

Hàm thuần có test không cần DB (``tests/unit/test_doi_hinh_thuc.py``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

import asyncpg
import structlog

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import HinhThucThuDaDoi
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.audit import record_event

logger = structlog.get_logger()

HINH_THUC = ("CASH", "TRANSFER", "QR")
TEN_HINH_THUC = {"CASH": "Tiền mặt", "TRANSFER": "Chuyển khoản", "QR": "QR"}
#: Người giữ MỘT trong hai khối thu tiền là đổi được — không theo loại phiếu.
QUYEN_DOI = ("payment.service.collect", "payment.medicine.collect")

KHONG_DOI_DA_HUY = "Phiếu đã huỷ — không đổi hình thức."
KHONG_DOI_CO_HOAN = "Phiếu đã có khoản hoàn — không đổi hình thức."
KHONG_DOI_CHUA_THU = "Phiếu chưa thu xong — không đổi hình thức."


def ly_do_khong_doi(status: object, co_hoan: object) -> str | None:
    """Vì sao phiếu này KHÔNG đổi được hình thức; ``None`` = đổi được. Thuần.

    Cùng luật với trigger ``payment_cycle_doi_hinh_thuc_guard`` (DB là lưới cuối).
    """
    if status == "VOIDED":
        return KHONG_DOI_DA_HUY
    if status != "PAID":
        return KHONG_DOI_CHUA_THU
    if co_hoan:
        return KHONG_DOI_CO_HOAN
    return None


def doc_ma_gd(raw: object) -> str | None:
    """Mã giao dịch tuỳ chọn: bỏ khoảng trắng, rỗng → None. Quá 100 ký tự → 422."""
    if not isinstance(raw, str):
        return None
    ma = raw.strip()
    if not ma:
        return None
    if len(ma) > 100:
        raise ValidationError("Mã giao dịch tối đa 100 ký tự.")
    return ma


def doc_ly_do(raw: object) -> str | None:
    """Lý do tuỳ chọn: rỗng → None. Quá 500 ký tự → 422."""
    if not isinstance(raw, str):
        return None
    ly = raw.strip()
    if not ly:
        return None
    if len(ly) > 500:
        raise ValidationError("Lý do tối đa 500 ký tự.")
    return ly


def _iso(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, datetime) else None


def dung_trang_thai(
    lan: Iterable[Mapping[str, Any]], doi: Iterable[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Mỗi phiếu → cờ đổi được + lịch sử đổi (cũ trước). Thuần.

    ``lan``: id, status, method (GỐC lúc thu), co_hoan. ``doi``: các dòng sổ đổi
    (cycle_id, method_cu, method_moi, reference, ly_do, boi, luc) theo thứ tự ghi.
    """
    lich: dict[str, list[dict[str, Any]]] = {}
    for d in doi:
        lich.setdefault(str(d["cycle_id"]), []).append(
            {
                "tu": d.get("method_cu"),
                "sang": d.get("method_moi"),
                "ma_gd": d.get("reference"),
                "ly_do": d.get("ly_do"),
                "boi": d.get("boi"),
                "luc": _iso(d.get("luc")),
            }
        )
    out: dict[str, dict[str, Any]] = {}
    for c in lan:
        cid = str(c["id"])
        ly = ly_do_khong_doi(c.get("status"), c.get("co_hoan"))
        out[cid] = {
            "duoc": ly is None,
            "ly_do_khong": ly,
            "hinh_thuc_goc": c.get("method"),
            "lan_doi": lich.get(cid, []),
        }
    return out


def gan_vao_lich_su(
    khach: Sequence[dict[str, Any]], tt: Mapping[str, Mapping[str, Any]]
) -> None:
    """Gắn ``doi_hinh_thuc`` vào từng phiếu + sự kiện "thu" của sổ gom theo
    khách (``quay_thu_service.gom_theo_khach``). Thuần, sửa tại chỗ."""
    for g in khach:
        for p in g.get("phieu") or []:
            p["doi_hinh_thuc"] = tt.get(str(p.get("id")))
        for s in g.get("su_kien") or []:
            if s.get("loai") == "thu":
                s["doi_hinh_thuc"] = tt.get(str(s.get("id")))


_LAN_SQL = """
SELECT pc.payment_cycle_id::text AS id, pc.status, pc.method,
       EXISTS (SELECT 1 FROM payment_refund r
                WHERE r.clinic_id = pc.clinic_id
                  AND r.payment_cycle_id = pc.payment_cycle_id
                  AND r.status IN ('PENDING', 'COMPLETED')) AS co_hoan
  FROM payment_cycle pc
 WHERE pc.clinic_id = $1::uuid AND pc.payment_cycle_id = ANY($2::uuid[])
"""

_DOI_SQL = """
SELECT d.cycle_id::text AS cycle_id, d.method_cu, d.method_moi, d.reference,
       d.ly_do, s.full_name AS boi, d.luc
  FROM payment_cycle_doi_hinh_thuc d
  LEFT JOIN staff s ON s.id = d.boi
 WHERE d.clinic_id = $1::uuid AND d.cycle_id = ANY($2::uuid[])
 ORDER BY d.id
"""


async def trang_thai_doi(
    conn: asyncpg.Connection, clinic_id: str, cycle_ids: Sequence[str]
) -> dict[str, dict[str, Any]]:
    """Cờ đổi được + lịch sử đổi của các phiếu (cho màn quầy thu)."""
    ids = sorted({str(c) for c in cycle_ids})
    if not ids:
        return {}
    lan = await conn.fetch(_LAN_SQL, clinic_id, ids)
    doi = await conn.fetch(_DOI_SQL, clinic_id, ids)
    return dung_trang_thai([dict(r) for r in lan], [dict(r) for r in doi])


class DoiHinhThucService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doi(
        self,
        *,
        identity: StaffIdentity,
        payment_cycle_id: str,
        hinh_thuc: str,
        hinh_thuc_cu: str | None = None,
        reference: object = None,
        ly_do: object = None,
    ) -> dict[str, Any]:
        """Ghi hình thức mới cho một phiếu đã thu. Một dòng sổ + sự kiện.

        ``hinh_thuc_cu``: hình thức màn đang thấy — khác hình thức hiệu lực (người
        khác vừa đổi) → 409, không đè. Bỏ trống = không đối chiếu.
        Gửi lại đúng hình thức hiện hành → thành công, không ghi thêm dòng.
        """
        if hinh_thuc not in HINH_THUC:
            raise ValidationError(f"Hình thức không hợp lệ: {hinh_thuc!r}")
        if hinh_thuc_cu is not None and hinh_thuc_cu not in HINH_THUC:
            raise ValidationError(f"Hình thức cũ không hợp lệ: {hinh_thuc_cu!r}")
        ma = doc_ma_gd(reference) if hinh_thuc != "CASH" else None
        ly = doc_ly_do(ly_do)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn:
            if not any([await can(conn, identity, q) for q in QUYEN_DOI]):
                raise SafetyGateError(
                    "Bạn không có quyền thu tiền nên không đổi được hình thức thu."
                )
            async with conn.transaction():
                lan = await conn.fetchrow(
                    """
                    SELECT pc.payment_cycle_id::text AS id,
                           pc.visit_id::text AS visit_id, pc.kind, pc.status,
                           pc.amount, pc.method,
                           hinh_thuc_hieu_luc(pc.clinic_id, pc.payment_cycle_id,
                                              pc.method) AS hieu_luc
                      FROM payment_cycle pc
                     WHERE pc.clinic_id = $1::uuid AND pc.payment_cycle_id = $2::uuid
                     FOR UPDATE
                    """,
                    cid,
                    payment_cycle_id,
                )
                if lan is None:
                    raise NotFoundError("Không tìm thấy phiếu thu này.")
                co_hoan = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM payment_refund"
                    " WHERE clinic_id = $1::uuid AND payment_cycle_id = $2::uuid"
                    " AND status IN ('PENDING', 'COMPLETED'))",
                    cid,
                    payment_cycle_id,
                )
                khong = ly_do_khong_doi(lan["status"], co_hoan)
                if khong is not None:
                    raise ConflictError(khong)
                hien = lan["hieu_luc"]
                if hien == hinh_thuc:
                    return {
                        "payment_cycle_id": payment_cycle_id,
                        "hinh_thuc": hien,
                        "da_la_hinh_thuc_nay": True,
                    }
                if hinh_thuc_cu is not None and hinh_thuc_cu != hien:
                    raise ConflictError(
                        "Hình thức của phiếu vừa được người khác đổi sang "
                        f"{TEN_HINH_THUC.get(str(hien), 'khác')} — tải lại rồi đổi."
                    )
                try:
                    await conn.execute(
                        """
                        INSERT INTO payment_cycle_doi_hinh_thuc
                            (clinic_id, cycle_id, method_cu, method_moi, reference,
                             ly_do, boi)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid)
                        """,
                        cid,
                        payment_cycle_id,
                        hien,
                        hinh_thuc,
                        ma,
                        ly,
                        identity.staff_id,
                    )
                except asyncpg.CheckViolationError as exc:
                    # Lưới cuối ở DB (tranh chấp lọt qua kiểm trên) — câu của trigger.
                    raise ConflictError(str(exc).split("\n")[0]) from exc
                await emit_event(
                    conn,
                    ten="payment.method_changed",
                    clinic_id=cid,
                    aggregate_id=payment_cycle_id,
                    payload=HinhThucThuDaDoi(
                        visit_id=lan["visit_id"],
                        payment_cycle_id=payment_cycle_id,
                        kind=lan["kind"],
                        so_tien=int(lan["amount"]),
                        tu=hien,
                        sang=hinh_thuc,
                    ),
                    boi=nguoi(identity),
                    correlation_id=lan["visit_id"],
                )
                await record_event(
                    conn,
                    event_type="payment.method_changed",
                    aggregate_type="payment_cycle",
                    aggregate_id=payment_cycle_id,
                    identity=identity,
                    origin="api:payment-doi-hinh-thuc",
                    correlation_id=lan["visit_id"],
                    payload={
                        "payment_cycle_id": payment_cycle_id,
                        "visit_id": lan["visit_id"],
                        "kind": lan["kind"],
                        "amount": int(lan["amount"]),
                        "method_cu": hien,
                        "method_moi": hinh_thuc,
                        "reference": ma,
                        "ly_do": ly,
                    },
                )
        logger.info(
            "payment_method_changed",
            payment_cycle_id=payment_cycle_id,
            tu=hien,
            sang=hinh_thuc,
            by_staff_id=identity.staff_id,
        )
        return {
            "payment_cycle_id": payment_cycle_id,
            "hinh_thuc": hinh_thuc,
            "hinh_thuc_cu": hien,
        }
