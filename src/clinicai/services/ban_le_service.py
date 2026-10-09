"""Khách CHỈ ĐẾN MUA THUỐC — lượt Bán lẻ (V8, Tuyền 30/09/2026).

Mọi thứ ở quầy thuốc bám vào một lượt: đơn bán, hoá đơn, lần thu, phân lô. Lượt
bán lẻ là một ``visit`` có cờ ``ban_le``:

* KHÔNG lịch hẹn, KHÔNG loại khám, KHÔNG bác sĩ → không có dòng tiền khám.
* KHÔNG check-in (``checked_in_at`` rỗng), KHÔNG phát ``visit.checked_in`` → khối
  Hành trình không xếp đường đi, không vào hàng chờ bác sĩ / tư vấn, không qua
  điều phối. Các màn đếm "lượt khám" loại ``ban_le`` ra.
* Kê bằng đúng đường quầy thuốc đã có (``quay_thuoc_service.luu_dong_them`` —
  dòng QUAY), thu bằng đúng lệnh thu tiền thuốc (``PaymentService``), giao / gán
  lô bằng đúng màn Nhà thuốc. File này chỉ MỞ lượt, TÌM khách, đọc hoá đơn cho
  màn, và ĐÓNG lượt khi tiền thuốc đã thu.

HƯỚNG "MỞ HẾT" (Tuyền 30/09 chiều): ai giữ lego nhà thuốc hoặc thu tiền đều mở
được lượt bán lẻ, kể cả tạo hồ sơ khách mới ngay tại quầy — không đòi thêm lego
"Thêm bệnh nhân".
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import asyncpg
from pydantic import ValidationError as PydanticValidationError

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.schemas.patient import PatientCreateDTO
from clinicai.services.audit import record_event
from clinicai.services.ban_theo_don_service import (
    doc_don,
    doc_don_khach,
    noi_don_conn,
)
from clinicai.services.bill_service import tinh_hoa_don
from clinicai.services.phan_thu import doc_phan_db

#: Ai mở được lượt bán lẻ — có MỘT trong các lego này (hướng "MỞ HẾT").
QUYEN_MO = ("pharmacy.dispense", "payment.medicine.collect", "payment.service.collect")
#: Kê thêm thuốc + thu tiền thuốc — đúng quyền của hai lệnh được dùng lại.
QUYEN_THU_THUOC = "payment.medicine.collect"
_TRAN_TIM = 10


async def co_quyen_mo(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_MO:
        if await can(conn, identity, q):
            return True
    return False


async def _doi_quyen_mo(conn: asyncpg.Connection, identity: StaffIdentity) -> None:
    if not await co_quyen_mo(conn, identity):
        raise SafetyGateError(
            "Bạn chưa được mở lượt khách mua thuốc (cần lego Nhà thuốc hoặc Thu tiền)."
        )


def chuan_tu_khoa(q: Any) -> str:
    """Từ khoá tìm khách: gọn khoảng trắng, tối đa 100 ký tự. Rác → rỗng."""
    if not isinstance(q, str):
        return ""
    return " ".join(q.split())[:100]


def nam_sinh(v: Any) -> int | None:
    """Năm sinh người dùng gõ: số 1900–2100, còn lại (rác, rỗng) → None. Không ném."""
    if isinstance(v, bool):
        return None
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return n if 1900 <= n <= 2100 else None


class BanLeService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Tìm khách ─────────────────────────────────────────────────────────
    async def tim_khach(self, *, q: Any, identity: StaffIdentity) -> dict[str, Any]:
        """Tìm theo SĐT (chữ số), mã khách, hoặc tên (không dấu). < 2 ký tự → rỗng."""
        tu = chuan_tu_khoa(q)
        if len(tu) < 2:
            return {"items": []}
        so = re.sub(r"\D", "", tu)
        async with self._pool.acquire() as conn:
            await _doi_quyen_mo(conn, identity)
            rows = await conn.fetch(
                """
                SELECT p.clinic_patient_id::text AS clinic_patient_id, p.full_name,
                       p.patient_code, p.phone_primary, p.birth_year, p.gender
                  FROM patient p
                 WHERE p.clinic_id = $1::uuid AND p.is_active
                   AND ((length($3) >= 3
                         AND (p.phone_primary LIKE '%' || $3 || '%'
                              OR p.phone_secondary LIKE '%' || $3 || '%'))
                        OR upper(p.patient_code) = upper($2)
                        OR p.full_name_unaccent LIKE '%' || lower(replace(replace(
                               public.f_unaccent($2), 'đ', 'd'), 'Đ', 'D')) || '%')
                 ORDER BY (upper(p.patient_code) = upper($2)) DESC, p.full_name,
                          p.clinic_patient_id
                 LIMIT $4
                """,
                identity.clinic_id,
                tu,
                so,
                _TRAN_TIM,
            )
        return {"items": [dict(r) for r in rows]}

    # ── Mở lượt ───────────────────────────────────────────────────────────
    async def mo_luot(
        self,
        *,
        identity: StaffIdentity,
        clinic_patient_id: str | None = None,
        khach_moi: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Mở (hoặc lấy lại) lượt bán lẻ đang mở của khách.

        ``khach_moi`` = ``{ho_ten, sdt, nam_sinh, gioi_tinh, force}``: tạo hồ sơ
        trước (cùng luật chống trùng SĐT của quầy tiếp đón). Trùng SĐT mà chưa
        ``force`` → trả ``{"trung": True, "matches": [...]}``, không tạo gì.

        Mỗi khách chỉ MỘT lượt bán lẻ đang mở (chỉ mục duy nhất ở Postgres):
        bấm hai lần, hay hai người cùng bấm, đều ra cùng một lượt.
        """
        async with self._pool.acquire() as conn:
            await _doi_quyen_mo(conn, identity)
        pid = clinic_patient_id
        if not pid:
            if not khach_moi:
                raise ValidationError("Chọn khách có sẵn hoặc nhập khách mới.")
            tao = await self._tao_khach(identity, khach_moi)
            if "trung" in tao:
                return tao
            pid = tao["clinic_patient_id"]
        async with self._pool.acquire() as conn, conn.transaction():
            return await _mo_hoac_lay(conn, identity, str(pid))

    async def don_gan_nhat(
        self, *, clinic_patient_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Vừa CHỌN khách ở quầy (chưa mở lượt) → đơn gần nhất để xem."""
        async with self._pool.acquire() as conn:
            await _doi_quyen_mo(conn, identity)
            don = await doc_don_khach(
                conn, identity, clinic_patient_id=clinic_patient_id
            )
        return {"don": don}

    async def mo_theo_don(
        self, *, clinic_patient_id: str, don_goc_visit_id: str, identity: StaffIdentity
    ) -> dict[str, Any]:
        """ "Bán theo đơn này" từ khung chọn khách: MỘT giao dịch mở (hoặc lấy lại)
        lượt bán lẻ + nối đơn gốc + thêm dòng. Lỗi ở bước nào thì không còn gì."""
        async with self._pool.acquire() as conn, conn.transaction():
            await _doi_quyen_mo(conn, identity)
            luot = await _mo_hoac_lay(conn, identity, clinic_patient_id)
            kq = await noi_don_conn(
                conn,
                self._pool,
                identity,
                visit_id=luot["visit_id"],
                don_goc_visit_id=don_goc_visit_id,
            )
        return {**kq, "visit_id": luot["visit_id"]}

    async def _tao_khach(
        self, identity: StaffIdentity, khach: dict[str, Any]
    ) -> dict[str, Any]:
        from clinicai.services.patient_service import PatientService

        ho_ten = " ".join(str(khach.get("ho_ten") or "").split())[:200]
        if not ho_ten:
            raise ValidationError("Nhập tên khách.")
        try:
            dto = PatientCreateDTO(
                full_name=ho_ten,
                phone_primary=(str(khach.get("sdt") or "").strip() or None),
                birth_year=nam_sinh(khach.get("nam_sinh")),
                gender=khach.get("gioi_tinh"),
                location_id=UUID(identity.location_id),
                force=bool(khach.get("force")),
            )
        except PydanticValidationError as exc:
            # Trường phụ (năm sinh, giới) đã được nới ở DTO; còn lại chỉ có SĐT.
            raise ValidationError(
                "Số điện thoại không đúng — số di động Việt Nam 10 số (vd 0912345678)."
            ) from exc
        kq = await PatientService(self._pool).create_patient(dto, identity)
        if kq.patient is None:
            return {
                "trung": True,
                "cccd_trung": kq.cccd_trung,
                "matches": [m.model_dump(mode="json") for m in kq.matches],
            }
        return {"clinic_patient_id": str(kq.patient.clinic_patient_id)}

    # ── Đọc cho màn Nhà thuốc ─────────────────────────────────────────────
    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Hoá đơn thuốc của lượt bán lẻ + lần thu đang chờ/đã thu + cờ quyền.

        Hoá đơn là ĐÚNG thứ ``PaymentService`` tính lại lúc thu
        (``bill_service.tinh_hoa_don``) — màn không tự cộng."""
        async with self._pool.acquire() as conn:
            await _doi_quyen_mo(conn, identity)
            luot = await conn.fetchrow(
                """
                SELECT v.visit_id::text AS visit_id, v.ban_le, v.closed_at,
                       v.clinic_patient_id::text AS clinic_patient_id,
                       p.full_name, p.patient_code
                  FROM visit v
                  JOIN patient p
                    ON p.clinic_patient_id = v.clinic_patient_id
                   AND p.clinic_id = v.clinic_id
                 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
                """,
                identity.clinic_id,
                visit_id,
            )
            if luot is None or not luot["ban_le"]:
                raise NotFoundError("Không tìm thấy lượt bán lẻ này.")
            lan = await conn.fetchrow(
                """
                SELECT payment_cycle_id::text AS payment_cycle_id, status, method,
                       amount, created_at,
                       phan_thu_hieu_luc(clinic_id, payment_cycle_id, method, amount)
                           AS phan
                  FROM payment_cycle
                 WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
                   AND kind = 'thuoc'
                   AND status IN ('PENDING_VERIFICATION', 'PAID')
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                identity.clinic_id,
                visit_id,
            )
            hd = await tinh_hoa_don(
                conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind="thuoc"
            )
            duoc_thu = await can(conn, identity, QUYEN_THU_THUOC)
            # Đơn gần nhất / đơn đã nối — "Bán theo đơn này" (09/10/2026).
            don = await doc_don(conn, identity, ban_le_visit_id=visit_id)
        cho = None
        if lan is not None and lan["status"] == "PENDING_VERIFICATION":
            cho = {
                "payment_cycle_id": lan["payment_cycle_id"],
                "visit_id": visit_id,
                "kind": "thuoc",
                "so_tien": int(lan["amount"]),
                "phuong_thuc": lan["method"],
                "luc": lan["created_at"].isoformat(),
                "phan": doc_phan_db(lan["phan"]),
                "anh_ck": [],
            }
        return {
            "visit_id": visit_id,
            "clinic_patient_id": luot["clinic_patient_id"],
            "ten_khach": luot["full_name"],
            "patient_code": luot["patient_code"],
            "da_dong": luot["closed_at"] is not None,
            "da_thu": lan is not None and lan["status"] == "PAID",
            # Lần thu đã thu — nút "Hoàn tác lần thu" (01/10/2026).
            "lan_da_thu": (
                lan["payment_cycle_id"]
                if lan is not None and lan["status"] == "PAID"
                else None
            ),
            "cho_xac_minh": cho,
            "hoa_don": hd.cho_api(),
            # Kê thêm + thu = quyền "Thu tiền thuốc" (đúng hai lệnh dùng lại).
            "duoc_thu": duoc_thu,
            "don_goc": don,
        }


async def _mo_hoac_lay(
    conn: asyncpg.Connection, identity: StaffIdentity, pid: str
) -> dict[str, Any]:
    """Mở (hoặc lấy lại) lượt bán lẻ đang mở của khách, trong giao dịch của người
    gọi. Chỉ mục duy nhất ở Postgres: hai lần bấm ra cùng một lượt."""
    khach = await conn.fetchrow(
        "SELECT full_name, patient_code FROM patient"
        " WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid",
        identity.clinic_id,
        pid,
    )
    if khach is None:
        raise NotFoundError("Không tìm thấy khách này.")
    moi = await conn.fetchval(
        """
        INSERT INTO visit (clinic_patient_id, clinic_id, location_id,
                           status, ban_le)
        VALUES ($2::uuid, $1::uuid, $3::uuid, 'OPEN', true)
        ON CONFLICT (clinic_id, clinic_patient_id)
            WHERE ban_le AND closed_at IS NULL
        DO NOTHING
        RETURNING visit_id::text
        """,
        identity.clinic_id,
        pid,
        identity.location_id,
    )
    if moi is not None:
        visit_id = moi
        await record_event(
            conn,
            event_type="visit.ban_le_opened",
            aggregate_type="visit",
            aggregate_id=visit_id,
            identity=identity,
            origin="api:pharmacy-ban-le",
            payload={"clinic_patient_id": pid},
            correlation_id=visit_id,
        )
    else:
        # Đã có lượt đang mở: lấy lại, và chạm updated_at để màn Nhà
        # thuốc (đọc lượt bán lẻ "trong ngày") thấy nó hôm nay.
        visit_id = await conn.fetchval(
            """
            UPDATE visit SET updated_at = now()
             WHERE clinic_id = $1::uuid AND clinic_patient_id = $2::uuid
               AND ban_le AND closed_at IS NULL
            RETURNING visit_id::text
            """,
            identity.clinic_id,
            pid,
        )
        if visit_id is None:
            raise ValidationError("Lượt vừa thay đổi — bấm lại “Khách mua thuốc”.")
    return {
        "visit_id": visit_id,
        "clinic_patient_id": pid,
        "ten_khach": khach["full_name"],
        "patient_code": khach["patient_code"],
        "moi": moi is not None,
    }


async def dong_luot_ban_le(
    conn: asyncpg.Connection, *, identity: StaffIdentity, visit_id: str
) -> bool:
    """Tiền thuốc của lượt BÁN LẺ đã thu → tự đóng lượt. Lượt thường: không làm gì.

    Gọi trong CHÍNH giao dịch ghi "đã thu" (tiền mặt, hoặc chuyển khoản/QR vừa
    xác minh). Không đụng ``visit.status`` (khoá hồ sơ bệnh án — xem
    ``checkout_service``); đóng = ``closed_at`` như check-out, cùng con trỏ
    bước đóng lượt để bảng điều phối / hàng chờ không bao giờ đếm lượt này.
    Trả True khi vừa đóng.
    """
    dong = await conn.fetchval(
        """
        UPDATE visit
           SET closed_at = now(), closed_by_staff_id = $3::uuid,
               current_room_id = NULL, current_node_code = 'LUOTKHAM-15',
               current_node_since = now(), updated_at = now()
         WHERE clinic_id = $1::uuid AND visit_id = $2::uuid
           AND ban_le AND closed_at IS NULL
        RETURNING visit_id
        """,
        identity.clinic_id,
        visit_id,
        identity.staff_id,
    )
    if dong is None:
        return False
    await record_event(
        conn,
        event_type="visit.ban_le_closed",
        aggregate_type="visit",
        aggregate_id=visit_id,
        identity=identity,
        origin="api:payment",
        payload={"ly_do": "Đã thu tiền thuốc"},
        correlation_id=visit_id,
    )
    return True


async def mo_lai_luot_ban_le(
    conn: asyncpg.Connection, *, identity: StaffIdentity, visit_id: str
) -> bool:
    """HOÀN TÁC lần thu tiền thuốc của lượt BÁN LẺ (01/10/2026) → mở lại lượt
    đã tự đóng lúc thu (``dong_luot_ban_le``), để quầy thuốc thu lại được. Lượt
    thường / lượt chưa đóng: không làm gì. Khách đã có lượt bán lẻ KHÁC đang mở
    thì giữ nguyên (mỗi khách một lượt bán lẻ mở — chỉ mục duy nhất). Gọi trong
    CHÍNH giao dịch huỷ phiếu. Trả True khi vừa mở lại."""
    mo = await conn.fetchval(
        """
        UPDATE visit v
           SET closed_at = NULL, closed_by_staff_id = NULL,
               current_node_code = NULL, current_node_since = NULL,
               updated_at = now()
         WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid
           AND v.ban_le AND v.closed_at IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM visit k
                WHERE k.clinic_id = v.clinic_id
                  AND k.clinic_patient_id = v.clinic_patient_id
                  AND k.ban_le AND k.closed_at IS NULL)
        RETURNING v.visit_id
        """,
        identity.clinic_id,
        visit_id,
    )
    if mo is None:
        return False
    await record_event(
        conn,
        event_type="visit.ban_le_reopened",
        aggregate_type="visit",
        aggregate_id=visit_id,
        identity=identity,
        origin="api:payment",
        payload={"ly_do": "Hoàn tác lần thu tiền thuốc"},
        correlation_id=visit_id,
    )
    return True


__all__ = [
    "BanLeService",
    "mo_lai_luot_ban_le",
    "chuan_tu_khoa",
    "co_quyen_mo",
    "dong_luot_ban_le",
    "nam_sinh",
]
