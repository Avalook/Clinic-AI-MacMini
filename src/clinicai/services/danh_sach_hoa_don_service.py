"""Read-only paid bill register: historical snapshots and real cash movement."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any

import asyncpg

from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.bao_cao_cuoi_ngay_service import khung_ca
from clinicai.services.cashier_board_service import doc_khoang_ngay
from clinicai.services.co_so_bao_cao import doc_co_so
from clinicai.services.hoa_don_excel import xlsx_hoa_don as xlsx_hoa_don
from clinicai.services.hoa_don_projection import gom_hoa_don as gom_hoa_don
from clinicai.services.hoa_don_projection import gom_viec_ton
from clinicai.services.hoan_tac_service import tien_thua_cua_luot
from clinicai.services.quay_thu_service import _DONG_SQL
from clinicai.services.report_access_service import ReportAccessService

_BILLS = """
SELECT pc.payment_cycle_id::text id, pc.visit_id::text visit_id, pc.kind,
 pc.amount, pc.status, pc.created_at, pc.paid_at, pc.closed_at, pc.close_reason,
 pc.original_amount, pc.discount_amount, pc.discount_type, pc.discount_value,
 pc.discount_reason, discount_staff.full_name nguoi_giam,
 pc.can_doi_soat, p.clinic_patient_id::text patient_id, p.full_name ten,
 p.patient_code ma_bn, p.phone_primary so_dien_thoai,
 creator.full_name nguoi_lap, confirmer.full_name nguoi_thu, closer.full_name nguoi_huy,
 hinh_thuc_hieu_luc(pc.clinic_id,pc.payment_cycle_id,pc.method) method,
 (pc.paid_at >= $2 AND pc.paid_at < $3) trong_ky,
 (pc.status='VOIDED' AND pc.closed_at >= $2 AND pc.closed_at < $3) huy_trong_ky
FROM payment_cycle pc
JOIN visit v ON v.visit_id=pc.visit_id AND v.clinic_id=pc.clinic_id
LEFT JOIN appointment a ON a.id=v.appointment_id AND a.clinic_id=v.clinic_id
LEFT JOIN patient p ON p.clinic_patient_id=v.clinic_patient_id
 AND p.clinic_id=v.clinic_id
LEFT JOIN staff creator ON creator.id=pc.created_by
LEFT JOIN staff confirmer ON confirmer.id=pc.confirmed_by
LEFT JOIN staff closer ON closer.id=pc.closed_by
LEFT JOIN staff discount_staff ON discount_staff.id=pc.discount_by
WHERE pc.clinic_id=$1::uuid AND pc.paid_at IS NOT NULL
 AND ($4::uuid IS NULL OR coalesce(v.location_id,a.location_id)=$4::uuid)
 AND ($5::text IS NULL OR pc.kind=$5)
 AND ((pc.paid_at >= $2 AND pc.paid_at < $3)
   OR (pc.closed_at >= $2 AND pc.closed_at < $3)
   OR EXISTS(SELECT 1 FROM payment_refund r WHERE r.clinic_id=pc.clinic_id
     AND r.payment_cycle_id=pc.payment_cycle_id
     AND ((r.status='COMPLETED' AND r.completed_at >= $2 AND r.completed_at < $3)
       OR (r.status='PENDING' AND r.created_at >= $2 AND r.created_at < $3)
       OR (r.status IN ('FAILED','CANCELLED')
         AND r.closed_at >= $2 AND r.closed_at < $3))))
ORDER BY pc.paid_at DESC,pc.payment_cycle_id
"""
_REFUNDS = """
SELECT r.refund_id::text id,r.payment_cycle_id::text cycle_id,r.amount,r.status,
 r.method,r.reason,r.created_at,r.completed_at,r.closed_at,r.closed_reason,
 c.full_name nguoi_lap,s.full_name nguoi_hoan,x.full_name nguoi_huy,
 (CASE WHEN r.status='COMPLETED' THEN r.completed_at
 WHEN r.status IN ('FAILED','CANCELLED') THEN r.closed_at ELSE r.created_at END >= $3
 AND CASE WHEN r.status='COMPLETED' THEN r.completed_at
 WHEN r.status IN ('FAILED','CANCELLED') THEN r.closed_at ELSE r.created_at END < $4)
 AS trong_ky
FROM payment_refund r
LEFT JOIN staff c ON c.id=r.created_by
LEFT JOIN staff s ON s.id=r.completed_by
LEFT JOIN staff x ON x.id=r.closed_by
WHERE r.clinic_id=$1::uuid AND r.payment_cycle_id=ANY($2::uuid[])
ORDER BY r.created_at,r.refund_id
"""
# Thêm mốc giờ bỏ / không làm chỉ định (dòng "Bỏ dịch vụ sau thu" trong phiếu).
_LINES = _DONG_SQL.replace(
    "AS da_bo",
    "AS da_bo,"
    " CASE WHEN o.exec_status IN ('cancelled', 'not_performed')"
    " THEN o.updated_at END AS bo_luc",
)
assert "bo_luc" in _LINES, "_DONG_SQL đổi dạng — sửa lại chỗ chèn bo_luc"

_DOI_HINH_THUC = """
SELECT d.cycle_id::text cycle_id, d.method_cu, d.method_moi, d.ly_do, d.luc,
 s.full_name nguoi
FROM payment_cycle_doi_hinh_thuc d
LEFT JOIN staff s ON s.id=d.boi
WHERE d.clinic_id=$1::uuid AND d.cycle_id=ANY($2::uuid[])
ORDER BY d.luc
"""

# ── Việc còn tồn của MỌI ngày (không theo kỳ) — lọc cơ sở ($2) + loại ($3) ──
_KHACH_CUA_LUOT = """
 JOIN visit v ON v.visit_id={luot} AND v.clinic_id={clinic}
 LEFT JOIN appointment a ON a.id=v.appointment_id AND a.clinic_id=v.clinic_id
 LEFT JOIN patient p ON p.clinic_patient_id=v.clinic_patient_id
  AND p.clinic_id=v.clinic_id
"""
_LOC = "($2::uuid IS NULL OR coalesce(v.location_id,a.location_id)=$2::uuid)"
_KHACH_PC = _KHACH_CUA_LUOT.format(luot="pc.visit_id", clinic="pc.clinic_id")
_TON_HOAN = f"""
SELECT r.refund_id::text refund_id, r.visit_id::text visit_id, r.kind, r.amount,
 r.status, r.reason, r.created_at, r.closed_at, s.full_name nguoi,
 p.clinic_patient_id::text patient_id, p.full_name ten, p.patient_code ma_bn
FROM payment_refund r {_KHACH_CUA_LUOT.format(luot="r.visit_id", clinic="r.clinic_id")}
LEFT JOIN staff s ON s.id=r.created_by
WHERE r.clinic_id=$1::uuid AND r.status='PENDING' AND {_LOC}
 AND ($3::text IS NULL OR r.kind=$3)
"""
_TON_CK = f"""
SELECT pc.payment_cycle_id::text payment_cycle_id, pc.visit_id::text visit_id,
 pc.kind, pc.amount, pc.created_at, s.full_name nguoi,
 p.clinic_patient_id::text patient_id, p.full_name ten, p.patient_code ma_bn
FROM payment_cycle pc {_KHACH_PC}
LEFT JOIN staff s ON s.id=pc.created_by
WHERE pc.clinic_id=$1::uuid AND pc.status='PENDING_VERIFICATION' AND {_LOC}
 AND ($3::text IS NULL OR pc.kind=$3)
"""
_TON_NO = f"""
SELECT n.id::text id, n.visit_id::text visit_id, n.so_tien, n.ly_do, n.ghi_luc,
 s.full_name nguoi, p.clinic_patient_id::text patient_id, p.full_name ten,
 p.patient_code ma_bn
FROM cong_no n {_KHACH_CUA_LUOT.format(luot="n.visit_id", clinic="n.clinic_id")}
LEFT JOIN staff s ON s.id=n.ghi_boi
WHERE n.clinic_id=$1::uuid AND n.trang_thai='CHUA_THU' AND {_LOC}
 AND $3::text IS NULL
"""
#: Tiền thừa chỉ dò trong lượt có thu dịch vụ 90 ngày gần nhất — đủ cho việc
#: tồn thật, không quét cả lịch sử mỗi lần mở màn.
TIEN_THUA_SO_NGAY = 90
_TON_THUA_LUOT = f"""
SELECT v.visit_id::text visit_id, p.clinic_patient_id::text patient_id,
 p.full_name ten, p.patient_code ma_bn,
 coalesce(max(o.updated_at), max(pc.paid_at)) luc
FROM payment_cycle pc {_KHACH_PC}
LEFT JOIN service_order o ON o.clinic_id=v.clinic_id AND o.visit_id=v.visit_id
 AND o.exec_status IN ('cancelled','not_performed')
WHERE pc.clinic_id=$1::uuid AND pc.kind='dich_vu' AND pc.status='PAID'
 AND pc.paid_at >= now() - interval '{TIEN_THUA_SO_NGAY} days' AND {_LOC}
 AND ($3::text IS NULL OR $3='dich_vu')
GROUP BY v.visit_id, p.clinic_patient_id, p.full_name, p.patient_code
"""

_REFUND_LINES = """
SELECT rl.refund_id::text refund_id,bl.name_snapshot ten,rl.quantity so_luong,
 rl.amount thanh_tien,bl.id::text id
FROM payment_refund_line rl
JOIN payment_bill_line bl ON bl.id=rl.payment_bill_line_id AND bl.clinic_id=rl.clinic_id
WHERE rl.clinic_id=$1::uuid AND rl.refund_id=ANY($2::uuid[])
ORDER BY rl.created_at,bl.id
"""


class DanhSachHoaDonService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def xem(
        self,
        *,
        identity: StaffIdentity,
        tu: str | None = None,
        den: str | None = None,
        tim: str | None = None,
        loai: str | None = None,
        trang_thai: str | None = None,
        co_so: str | None = None,
        ca: str | None = None,
        can_kiem_tra: bool = False,
    ) -> dict[str, Any]:
        a, b = doc_khoang_ngay(tu, den)
        access, location = await ReportAccessService(self.pool).authorize(
            identity, tu=a.isoformat(), den=b.isoformat(), ca=ca, co_so=co_so
        )
        if not access["tai_chinh"]:
            raise SafetyGateError(
                "Bạn chưa được phân quyền xem chi tiết hoá đơn tài chính."
            )
        start = datetime.combine(a, time.min, tzinfo=CLINIC_TZ)
        end = datetime.combine(b + timedelta(days=1), time.min, tzinfo=CLINIC_TZ)
        async with self.pool.acquire() as conn:
            settings = await conn.fetchval(
                "SELECT settings FROM clinic WHERE id=$1::uuid", identity.clinic_id
            )
            shift = khung_ca(a, ca, settings) if a == b else None
            if shift:
                start, end = shift[:2]
            rows = [
                dict(r)
                for r in await conn.fetch(
                    _BILLS,
                    identity.clinic_id,
                    start,
                    end,
                    doc_co_so(location),
                    loai if loai in ("thuoc", "dich_vu") else None,
                )
            ]
            ids = [r["id"] for r in rows]
            refunds = [
                dict(r)
                for r in await conn.fetch(_REFUNDS, identity.clinic_id, ids, start, end)
            ]
            lines = [dict(r) for r in await conn.fetch(_LINES, identity.clinic_id, ids)]
            refund_lines = [
                dict(r)
                for r in await conn.fetch(
                    _REFUND_LINES, identity.clinic_id, [r["id"] for r in refunds]
                )
            ]
            doi_ht = [
                dict(r)
                for r in await conn.fetch(_DOI_HINH_THUC, identity.clinic_id, ids)
            ]
            vids = sorted({r["visit_id"] for r in rows if r.get("visit_id")})
            tien_thua = await tien_thua_cua_luot(conn, identity.clinic_id, vids)
            ton = await self._viec_ton(
                conn,
                identity.clinic_id,
                doc_co_so(location),
                loai if loai in ("thuoc", "dich_vu") else None,
            )
        return {
            "tu": a.isoformat(),
            "den": b.isoformat(),
            "access": access,
            "ca": ca,
            "co_so": location,
            **gom_hoa_don(
                rows,
                refunds,
                lines,
                refund_lines,
                tim=tim,
                trang_thai=trang_thai,
                can_kiem_tra=can_kiem_tra,
                doi_hinh_thuc=doi_ht,
                tien_thua=tien_thua,
                viec_ton=ton,
            ),
        }

    @staticmethod
    async def _viec_ton(
        conn: asyncpg.Connection, clinic_id: str, co_so: str | None, loai: str | None
    ) -> list[dict[str, Any]]:
        """Việc còn tồn của mọi ngày: hoàn đang chờ, CK chưa về, ghi nợ chưa
        thu, tiền thừa chưa trả. Quầy / CSKH xử lý bằng nút có sẵn thì tự hết."""
        args = (clinic_id, co_so, loai)
        hoan = [dict(r) for r in await conn.fetch(_TON_HOAN, *args)]
        ck = [dict(r) for r in await conn.fetch(_TON_CK, *args)]
        no = [dict(r) for r in await conn.fetch(_TON_NO, *args)]
        luot = {r["visit_id"]: dict(r) for r in await conn.fetch(_TON_THUA_LUOT, *args)}
        thua = await tien_thua_cua_luot(conn, clinic_id, sorted(luot))
        return gom_viec_ton(hoan=hoan, ck=ck, no=no, tien_thua=thua, luot=luot)
