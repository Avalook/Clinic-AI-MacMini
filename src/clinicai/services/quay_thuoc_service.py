"""Quầy thuốc chỉnh ĐƠN BÁN trước khi thu tiền (Tuyền 24/09/2026).

"Ở màn thu tiền thuốc cho thêm ô lấy thêm thuốc, có cả số lượng, hướng dẫn sử
dụng… như ở phiếu khám của bác sĩ để thu ngân thuốc chỉnh được, bỏ tick thuốc
được nếu bệnh nhân không muốn, và lưu hết lại lịch sử, có event phát ra là đã
bỏ thuốc này ở bản cuối cùng thanh toán."

Hai loại dòng (cột ``prescription.nguon``):
  * BAC_SI — bác sĩ kê. Quầy chỉ được bỏ tick / tích lại / đổi SỐ MUA (không quá
    số kê — luật C2 của nhà thuốc). Cách dùng là quyết định chuyên môn: chỉ xem.
  * QUAY — quầy thêm lúc bán ("lấy thêm thuốc"): sửa được số lượng, cách dùng,
    lưu ý. Không nằm trong đơn bác sĩ (phiếu khám / đính chính / ký bỏ qua).

KHÔNG GỠ DÒNG NÀO. "Bỏ" = bỏ tick (số mua 0): dòng còn nguyên, tích lại được, và
lúc thu tiền trở thành sự kiện ``medicine.declined`` ở bản thanh toán cuối. Mọi
thay đổi ghi nhật ký (event_log) + phát ``medicine.counter_changed``.

Thứ tự khoá như mọi thao tác chạm hoá đơn thuốc: visit → prescription.
Thu tiền thuốc rồi thì khoá — huỷ phiếu thu trước rồi mới chỉnh (như nhà thuốc).
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import ThuocQuayDaChinh
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.pharmacy_service import PharmacyService

QUYEN = "payment.medicine.collect"
BAC_SI = "BAC_SI"
QUAY = "QUAY"


def _chu(v: Any, toi_da: int = 500) -> str | None:
    s = " ".join(str(v or "").split())[:toi_da]
    return s or None


def _so(v: Any) -> Decimal:
    try:
        d = Decimal(str(v).replace(",", "."))
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError("Số lượng phải là một con số.") from exc
    if not d.is_finite() or d <= 0:
        raise ValidationError("Số lượng phải lớn hơn 0.")
    return d


def _chuoi_so(d: Decimal) -> str:
    return format(d.normalize(), "f")


class QuayThuocService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    # ── Đọc ────────────────────────────────────────────────────────────────
    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        async with self._pool.acquire() as conn:
            await doi_quyen(conn, identity, QUYEN, cau="Bạn chưa được thu tiền thuốc.")
            rows = await conn.fetch(
                """
                SELECT r.id::text AS id, r.nguon, r.drug_name_raw AS ten,
                       r.drug_catalog_id::text AS drug_catalog_id, r.quantity,
                       r.quantity_num, r.unit, r.purchased_qty, r.dispensed_qty,
                       r.dosage_instructions, r.caution, r.refusal_reason,
                       r.closed_at IS NOT NULL AS da_chot, c.unit_price AS gia
                  FROM prescription r
                  LEFT JOIN drug_catalog c
                    ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
                 WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
                   AND r.removed_at IS NULL
                 ORDER BY (r.nguon = 'QUAY'), r.created_at, r.id
                """,
                identity.clinic_id,
                visit_id,
            )
            da_thu = await PharmacyService._da_thu_tien_thuoc(conn, identity, visit_id)
        dong = []
        for r in rows:
            mua = r["purchased_qty"]
            dong.append(
                {
                    "id": r["id"],
                    "nguon": r["nguon"],
                    "ten": r["ten"],
                    "drug_catalog_id": r["drug_catalog_id"],
                    "quantity": r["quantity"],
                    "so_ke": _chuoi_so(r["quantity_num"])
                    if r["quantity_num"]
                    else None,
                    "so_mua": _chuoi_so(mua) if mua is not None else None,
                    "don_vi": r["unit"],
                    "cach_dung": r["dosage_instructions"],
                    "luu_y": r["caution"],
                    # Tích = khách lấy: không từ chối, không chốt 0.
                    "mua": r["refusal_reason"] is None and (mua is None or mua > 0),
                    "da_chot": bool(r["da_chot"]),
                    "da_giao": _chuoi_so(r["dispensed_qty"] or Decimal(0)),
                    "gia": int(r["gia"]) if r["gia"] is not None else None,
                }
            )
        return {"visit_id": visit_id, "da_thu": da_thu, "dong": dong}

    # ── Ghi ────────────────────────────────────────────────────────────────
    async def _ghi_su_kien(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        *,
        visit_id: str,
        prescription_id: str,
        hanh_dong: str,
        nguon: str,
        so_luong: str | None = None,
    ) -> None:
        await record_event(
            conn,
            event_type="pharmacy.counter_changed",
            aggregate_type="prescription",
            aggregate_id=prescription_id,
            identity=identity,
            origin="api:quay-thuoc",
            payload={
                "visit_id": visit_id,
                "hanh_dong": hanh_dong,
                "nguon": nguon,
                "so_luong": so_luong,
            },
        )
        await emit_event(
            conn,
            ten="medicine.counter_changed",
            clinic_id=identity.clinic_id,
            aggregate_id=visit_id,
            payload=ThuocQuayDaChinh(
                visit_id=visit_id,
                prescription_id=prescription_id,
                hanh_dong=hanh_dong,
                nguon=nguon,
                so_luong=so_luong,
            ),
            boi=nguoi(identity),
            correlation_id=visit_id,
        )

    async def _khoa_dong(
        self, conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
    ) -> dict[str, Any]:
        await doi_quyen(conn, identity, QUYEN, cau="Bạn chưa được thu tiền thuốc.")
        # visit → prescription; từ chối nếu dòng đã chốt / tiền thuốc đã thu.
        don = await PharmacyService._khoa_dong_chua_thu(conn, identity, prescription_id)
        r = await conn.fetchrow(
            "SELECT nguon, refusal_reason FROM prescription"
            " WHERE id = $1::uuid AND clinic_id = $2::uuid AND removed_at IS NULL",
            prescription_id,
            identity.clinic_id,
        )
        if r is None:
            raise ConflictError("Dòng thuốc vừa thay đổi — tải lại rồi thử lại.")
        return {**dict(don), "nguon": r["nguon"], "refusal_reason": r["refusal_reason"]}

    async def chon(
        self, *, prescription_id: str, mua: bool, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Tích (khách lấy) / bỏ tick (khách không lấy). Bỏ tick = số mua 0."""
        async with self._pool.acquire() as conn, conn.transaction():
            don = await self._khoa_dong(conn, identity, prescription_id)
            if don["refusal_reason"] is not None:
                raise ConflictError(
                    "Dòng này nhà thuốc đã ghi 'khách không lấy' (đã chốt) — "
                    "không tích lại ở quầy được."
                )
            if don["quantity_num"] is None:
                raise ValidationError(
                    "Dòng này chưa có số lượng — sửa số lượng trước rồi mới bỏ tick."
                )
            if not mua:
                da_giao = Decimal(str(don["dispensed_qty"] or 0))
                da_phan = await PharmacyService._da_phan_lo(
                    conn, identity, prescription_id
                )
                if da_giao > 0 or da_phan > 0:
                    raise ConflictError(
                        "Kho đã chọn lô / giao thuốc dòng này — nhờ kho bỏ lô trước."
                    )
            await conn.execute(
                "UPDATE prescription SET purchased_qty = $3, updated_at = now()"
                " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                prescription_id,
                identity.clinic_id,
                None if mua else Decimal(0),
            )
            await self._ghi_su_kien(
                conn,
                identity,
                visit_id=str(don["visit_id"]),
                prescription_id=prescription_id,
                hanh_dong="CHON_LAI" if mua else "BO_CHON",
                nguon=don["nguon"],
            )
        return {"ok": True, "prescription_id": prescription_id, "mua": mua}

    async def doi_so_luong(
        self, *, prescription_id: str, so_luong: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đơn bác sĩ: đổi SỐ MUA (≤ số kê). Dòng quầy thêm: đổi chính số lượng."""
        so = _so(so_luong)
        async with self._pool.acquire() as conn, conn.transaction():
            don = await self._khoa_dong(conn, identity, prescription_id)
            if don["nguon"] == BAC_SI:
                ke = don["quantity_num"]
                if ke is None:
                    raise ValidationError(
                        "Bác sĩ chưa ghi số lượng cho dòng này — nhờ bác sĩ ghi rõ."
                    )
                if so > Decimal(str(ke)):
                    raise ValidationError(
                        f"Bác sĩ kê {_chuoi_so(Decimal(str(ke)))} — muốn lấy thêm "
                        "thì thêm một dòng ở ô 'Lấy thêm thuốc'."
                    )
                if so < Decimal(str(don["dispensed_qty"] or 0)):
                    raise ValidationError("Số mua không nhỏ hơn số kho đã giao.")
                if so < await PharmacyService._da_phan_lo(
                    conn, identity, prescription_id
                ):
                    raise ValidationError(
                        "Kho đã chọn lô nhiều hơn — nhờ kho bỏ bớt lô."
                    )
                await conn.execute(
                    "UPDATE prescription SET purchased_qty = $3, updated_at = now()"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    prescription_id,
                    identity.clinic_id,
                    None if so == Decimal(str(ke)) else so,
                )
            else:
                if so < Decimal(str(don["dispensed_qty"] or 0)):
                    raise ValidationError("Số lượng không nhỏ hơn số kho đã giao.")
                don_vi = (don["unit"] or "").strip()
                chu = f"{_chuoi_so(so)} {don_vi}".strip()
                await conn.execute(
                    "UPDATE prescription SET quantity = $3,"
                    " quantity_num = public.so_luong_tu_van_ban($3),"
                    " unit = public.don_vi_tu_van_ban($3),"
                    " purchased_qty = NULL, updated_at = now()"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    prescription_id,
                    identity.clinic_id,
                    chu,
                )
            await self._ghi_su_kien(
                conn,
                identity,
                visit_id=str(don["visit_id"]),
                prescription_id=prescription_id,
                hanh_dong="SO_LUONG",
                nguon=don["nguon"],
                so_luong=_chuoi_so(so),
            )
        return {
            "ok": True,
            "prescription_id": prescription_id,
            "so_luong": _chuoi_so(so),
        }

    async def luu_dong_them(
        self, *, visit_id: str, dong: list[dict[str, Any]], identity: StaffIdentity
    ) -> dict[str, Any]:
        """Lưu các dòng "lấy thêm thuốc" của quầy: dòng mới thì thêm, dòng quầy đã
        có (kèm ``id``) thì sửa. Không xoá dòng nào — bỏ thì bỏ tick (``chon``).

        Mỗi dòng: ``drug_catalog_id`` (bắt buộc — không có giá thì không thu được),
        ``quantity`` ("10 viên"), ``dosage``, ``caution``.
        """
        if not isinstance(dong, list) or len(dong) > 50:
            raise ValidationError("Danh sách thuốc thêm không hợp lệ.")
        cid = identity.clinic_id
        them: list[str] = []
        sua: list[str] = []
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(conn, identity, QUYEN, cau="Bạn chưa được thu tiền thuốc.")
            luot = await conn.fetchrow(
                "SELECT clinic_patient_id::text AS pid, status FROM visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid FOR UPDATE",
                cid,
                visit_id,
            )
            if luot is None:
                raise NotFoundError("Không tìm thấy lượt khám.")
            if await PharmacyService._da_thu_tien_thuoc(conn, identity, visit_id):
                raise ConflictError(
                    "Tiền thuốc của lượt này đã thu — huỷ phiếu thu trước rồi mới "
                    "thêm / sửa thuốc."
                )
            for d in dong:
                if not isinstance(d, dict):
                    raise ValidationError("Dòng thuốc không hợp lệ.")
                catalog = _chu(d.get("drug_catalog_id"), 64)
                so_luong = _chu(d.get("quantity"), 64)
                cach_dung = _chu(d.get("dosage"))
                luu_y = _chu(d.get("caution"))
                if not catalog:
                    raise ValidationError(
                        "Chọn thuốc từ danh mục (có giá) — thuốc ngoài danh mục "
                        "không thu tiền được."
                    )
                ten = await conn.fetchval(
                    "SELECT coalesce(name_base, name_raw) FROM drug_catalog"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    catalog,
                    cid,
                )
                if ten is None:
                    raise ValidationError(
                        "Thuốc này không có trong danh mục của phòng khám."
                    )
                if (
                    not so_luong
                    or await conn.fetchval(
                        "SELECT public.so_luong_tu_van_ban($1)", so_luong
                    )
                    is None
                ):
                    raise ValidationError(f"“{ten}”: ghi số lượng (vd “10 viên”).")
                pid = _chu(d.get("id"), 64)
                if pid:
                    cu = await conn.fetchrow(
                        "SELECT nguon, drug_catalog_id::text AS c, quantity,"
                        " dosage_instructions, caution, dispensed_qty, closed_at"
                        "  FROM prescription"
                        " WHERE id = $1::uuid AND clinic_id = $2::uuid"
                        "   AND visit_id = $3::uuid AND removed_at IS NULL FOR UPDATE",
                        pid,
                        cid,
                        visit_id,
                    )
                    if cu is None or cu["nguon"] != QUAY:
                        raise ValidationError("Chỉ sửa được dòng quầy thêm.")
                    if (
                        cu["c"],
                        cu["quantity"],
                        cu["dosage_instructions"],
                        cu["caution"],
                    ) == (
                        catalog,
                        so_luong,
                        cach_dung,
                        luu_y,
                    ):
                        continue
                    if cu["closed_at"] is not None or (cu["dispensed_qty"] or 0) > 0:
                        raise ConflictError(
                            f"“{ten}”: kho đã giao / chốt — không sửa được."
                        )
                    await conn.execute(
                        """
                        UPDATE prescription
                           SET drug_catalog_id = $3::uuid, drug_name_raw = $4,
                               quantity = $5,
                               quantity_num = public.so_luong_tu_van_ban($5),
                               unit = public.don_vi_tu_van_ban($5),
                               dosage_instructions = $6, caution = $7,
                               purchased_qty = NULL,
                               drug_mapped_by = $8::uuid, drug_mapped_at = now(),
                               updated_at = now()
                         WHERE id = $1::uuid AND clinic_id = $2::uuid
                        """,
                        pid,
                        cid,
                        catalog,
                        ten,
                        so_luong,
                        cach_dung,
                        luu_y,
                        identity.staff_id,
                    )
                    sua.append(pid)
                    await self._ghi_su_kien(
                        conn,
                        identity,
                        visit_id=visit_id,
                        prescription_id=pid,
                        hanh_dong="SUA",
                        nguon=QUAY,
                        so_luong=so_luong,
                    )
                    continue
                moi = str(uuid.uuid4())
                await conn.execute(
                    """
                    INSERT INTO prescription (
                        id, source_ref, clinic_patient_id, visit_id, drug_name_raw,
                        quantity, dosage_instructions, caution, clinic_id,
                        quantity_num, unit, created_by, nguon,
                        drug_catalog_id, drug_mapped_by, drug_mapped_at
                    )
                    VALUES ($1::uuid, $2, $3::uuid, $4::uuid, $5, $6, $7, $8,
                            $9::uuid, public.so_luong_tu_van_ban($6),
                            public.don_vi_tu_van_ban($6), $10::uuid, 'QUAY',
                            $11::uuid, $10::uuid, now())
                    """,
                    moi,
                    f"quay-rx-{visit_id}-{uuid.uuid4().hex}",
                    luot["pid"],
                    visit_id,
                    ten,
                    so_luong,
                    cach_dung,
                    luu_y,
                    cid,
                    identity.staff_id,
                    catalog,
                )
                them.append(moi)
                await self._ghi_su_kien(
                    conn,
                    identity,
                    visit_id=visit_id,
                    prescription_id=moi,
                    hanh_dong="THEM",
                    nguon=QUAY,
                    so_luong=so_luong,
                )
        return {"ok": True, "them": them, "sua": sua}


__all__ = ["QuayThuocService"]
