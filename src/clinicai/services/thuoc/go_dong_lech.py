"""Quầy gỡ DÒNG THUỐC LỆCH ngay lúc thu (kế hoạch đơn vị mẹ/con mục 12, T3 — 26/11).

Vì sao: bác sĩ kê thuốc gõ tay → máy tự thêm "thuốc rác" không giá vào danh mục →
hoá đơn thuốc của lượt không thu được (`bill_service.HoaDon.thu_duoc`). Trước đây
quầy chỉ có một đường gỡ là bỏ tick (mất doanh thu dòng đó) — 43 lượt treo / 30 ngày.

Hai đường gỡ, cả hai đi qua lệnh ĐANG CÓ, không viết đường thứ hai:
  * GÁN dòng sang thuốc đúng trong danh mục: `PharmacyService.xac_dinh_thuoc` (khoá,
    chặn đã thu / đã giao / đã chọn lô), cùng giao dịch với sự kiện gán. Tên + đơn
    vị bác sĩ gõ giữ nguyên (hồ sơ đã ký không sửa tại chỗ được). Hoàn tác được
    (`hoan_tac_gan`): đọc lại sự kiện gán.
  * ĐIỀN GIÁ cho thuốc chưa có giá: `PharmacyService.luu_thuoc` (chốt quyền
    `doi_quyen_sua_gia`, sự kiện `pharmacy.price_changed`). Ở quầy chỉ ĐIỀN giá còn
    trống; đổi giá đã có là việc của Danh mục kho.

Thu NHIỀU lần thuốc cho một lượt (T4) không làm ở đây — chỉ mục
`uq_payment_cycle_thuoc_mot_lan_song` cấm có chủ ý. Gỡ xong thì thu MỘT lần.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, cast

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.events.catalogue import ThuocQuayDaChinh
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.bill_service import THIEU_SO_LUONG, tinh_hoa_don
from clinicai.services.don_vi_thuoc import QUYEN_SUA_GIA, BangDonVi, doc_bang
from clinicai.services.payment_access_service import head_money_grant
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.tuong_tac_cskh_service import _ConnectionBoundPool

QUYEN_THU = "payment.medicine.collect"
GAN = "GAN_THUOC"
BO_GAN = "BO_GAN_THUOC"
GIA_TOI_DA = Decimal(1_000_000_000)
_MAU_GIA = re.compile(r"\d+|\d{1,3}(\.\d{3})+|\d{1,3}(,\d{3})+")
KHONG_QUYEN_GIA = (
    "Bạn không có quyền đổi giá thuốc — nhờ người có quyền Sửa giá thuốc, "
    "hoặc bỏ tick nếu khách không lấy."
)


def gia_quay(v: Any) -> Decimal | None:
    """Giá quầy điền: số nguyên dương (đồng). Rác / âm / 0 → None (không ném)."""
    if v is None or isinstance(v, bool):
        return None
    # Chữ gõ ở quầy: chỉ chữ số, hoặc dấu nghìn ĐÚNG MẪU ("35.000", "1,200,000").
    # "35000.5" / "35000,50" không đoán (bỏ dấu là nhân giá 10–100 lần) → None.
    chu = str(v).strip()
    if isinstance(v, str):
        if not _MAU_GIA.fullmatch(chu):
            return None
        chu = chu.replace(".", "").replace(",", "")
    try:
        so = Decimal(chu.strip())
    except (InvalidOperation, ValueError):
        return None
    if not so.is_finite() or so <= 0 or so > GIA_TOI_DA or so != so.to_integral():
        return None
    return so


async def _khoa_dong_quay(
    conn: asyncpg.Connection, identity: StaffIdentity, prescription_id: str
) -> asyncpg.Record:
    """visit → prescription; chặn dòng đã chốt / lượt đã thu; quyền thu tiền thuốc."""
    don = await PharmacyService._khoa_dong_chua_thu(conn, identity, prescription_id)
    if not head_money_grant(identity, "thuoc", str(don["visit_id"])):
        await doi_quyen(conn, identity, QUYEN_THU, cau="Bạn chưa được thu tiền thuốc.")
    return don


async def _ghi_gan(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    *,
    don: asyncpg.Record,
    hanh_dong: str,
    cu: dict[str, Any],
    moi: dict[str, Any],
) -> None:
    rx = str(don["id"])
    vid = str(don["visit_id"])
    await record_event(
        conn,
        event_type="pharmacy.counter_changed",
        aggregate_type="prescription",
        aggregate_id=rx,
        identity=identity,
        origin="api:quay-thuoc",
        payload={
            "visit_id": vid,
            "hanh_dong": hanh_dong,
            "nguon": don["nguon"],
            "ten_thuoc": don["drug_name_raw"],
            "cu": cu,
            "moi": moi,
        },
    )
    await emit_event(
        conn,
        ten="medicine.counter_changed",
        clinic_id=identity.clinic_id,
        aggregate_id=vid,
        payload=ThuocQuayDaChinh(
            visit_id=vid, prescription_id=rx, hanh_dong=hanh_dong, nguon=don["nguon"]
        ),
        boi=nguoi(identity),
        correlation_id=vid,
    )


def _trang(don: asyncpg.Record) -> dict[str, Any]:
    return {"thuoc": str(don["drug_catalog_id"]) if don["drug_catalog_id"] else None}


async def _doc_dong_don(
    conn: asyncpg.Connection, clinic_id: str, rx: str
) -> asyncpg.Record:
    return await conn.fetchrow(
        "SELECT id, visit_id, nguon, drug_catalog_id, drug_name_raw, unit"
        "  FROM public.prescription WHERE id = $1::uuid AND clinic_id = $2::uuid"
        "   AND removed_at IS NULL",
        rx,
        clinic_id,
    )


async def gan_thuoc_dung(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    prescription_id: str,
    drug_catalog_id: str,
) -> dict[str, Any]:
    """Gán dòng sang thuốc đúng trong danh mục — CHỈ đổi thuốc kho của dòng.

    Tên và đơn vị bác sĩ gõ là nội dung chuyên môn của hồ sơ: trigger
    `prescription_dinh_chinh_guard` chặn sửa tại chỗ khi hồ sơ đã ký (ca thật: bác
    sĩ gõ "Pricefil", ký, rồi quầy mới thu). Giá, kho, hoá đơn đã đi theo thuốc kho.
    Đơn vị bác sĩ ghi mà thuốc mới không có → trả câu nhắc quầy đổi đơn vị / số."""
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_dong_quay(conn, identity, prescription_id)
        truoc = await _doc_dong_don(conn, identity.clinic_id, prescription_id)
        if str(truoc["drug_catalog_id"] or "") == str(drug_catalog_id):
            raise ValidationError("Dòng này đã gắn đúng thuốc ấy rồi.")
        # Mượn chung kết nối → lệnh xác định thuốc là savepoint của giao dịch này.
        cung = PharmacyService(cast(asyncpg.Pool, _ConnectionBoundPool(conn)))
        await cung.xac_dinh_thuoc(
            identity=identity,
            prescription_id=prescription_id,
            drug_catalog_id=drug_catalog_id,
        )
        bang = (await doc_bang(conn, identity.clinic_id, [drug_catalog_id])).get(
            drug_catalog_id, BangDonVi()
        )
        moi = {"thuoc": drug_catalog_id}
        await _ghi_gan(
            conn, identity, don=truoc, hanh_dong=GAN, cu=_trang(truoc), moi=moi
        )
    nhac = None
    if truoc["unit"] and bang.co_goc and not bang.nhan_ra(truoc["unit"]):
        nhac = (
            f"Đơn vị “{truoc['unit']}” không có ở thuốc này — chọn đơn vị đúng ở "
            "dòng thuốc rồi soát lại số lượng."
        )
    return {"ok": True, "prescription_id": prescription_id, "nhac": nhac}


async def _lan_gan_cuoi_lo(
    conn: asyncpg.Connection, clinic_id: str, ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Lần GÁN / BỎ GÁN gần nhất của từng dòng (sổ `event_log`) — một câu SQL."""
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (aggregate_id) aggregate_id::text AS rx, payload
          FROM public.event_log
         WHERE clinic_id = $1::uuid AND aggregate_type = 'prescription'
           AND aggregate_id = ANY($2::uuid[])
           AND event_type = 'pharmacy.counter_changed'
           AND payload ->> 'hanh_dong' IN ('GAN_THUOC', 'BO_GAN_THUOC')
         ORDER BY aggregate_id, occurred_at DESC, recorded_at DESC
        """,
        clinic_id,
        ids,
    )
    return {
        r["rx"]: dict(
            json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        )
        for r in rows
    }


def bo_gan_duoc(lan: dict[str, Any] | None, hien: dict[str, Any]) -> bool:
    """Hoàn tác được lần gán khi lần cuối là GÁN và dòng chưa đổi gì từ đó. Thuần."""
    return lan is not None and lan.get("hanh_dong") == GAN and lan.get("moi") == hien


async def hoan_tac_gan(
    pool: asyncpg.Pool, *, identity: StaffIdentity, prescription_id: str
) -> dict[str, Any]:
    """Lệnh bù của đúng lần gán: trả thuốc kho cũ của dòng."""
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_dong_quay(conn, identity, prescription_id)
        hien = await _doc_dong_don(conn, identity.clinic_id, prescription_id)
        lan = (await _lan_gan_cuoi_lo(conn, identity.clinic_id, [prescription_id])).get(
            prescription_id
        )
        if not bo_gan_duoc(lan, _trang(hien)):
            raise ConflictError(
                "Không có lần gán nào để hoàn tác, hoặc dòng đã đổi sau lần gán."
            )
        if await PharmacyService._da_phan_lo(conn, identity, prescription_id) > 0:
            raise ConflictError("Dòng này đã chọn lô — bỏ lô trước khi hoàn tác.")
        cu = {"thuoc": (lan or {}).get("cu", {}).get("thuoc")}
        await conn.execute(
            "UPDATE public.prescription SET drug_catalog_id = $3::uuid,"
            " drug_mapped_by = CASE WHEN $3::uuid IS NULL THEN NULL ELSE $4::uuid END,"
            " drug_mapped_at = CASE WHEN $3::uuid IS NULL THEN NULL ELSE now() END,"
            " updated_at = now() WHERE id = $1::uuid AND clinic_id = $2::uuid",
            prescription_id,
            identity.clinic_id,
            cu["thuoc"],
            identity.staff_id,
        )
        await _ghi_gan(
            conn, identity, don=hien, hanh_dong=BO_GAN, cu=_trang(hien), moi=cu
        )
    return {"ok": True, "prescription_id": prescription_id}


async def dien_gia_thuoc(
    pool: asyncpg.Pool, *, identity: StaffIdentity, drug_catalog_id: str, gia: Any
) -> dict[str, Any]:
    """Điền giá cho thuốc CHƯA có giá, qua đúng lệnh lưu thuốc của Danh mục."""
    so = gia_quay(gia)
    if so is None:
        raise ValidationError("Giá bán phải là số đồng lớn hơn 0 (vd 35000).")
    t = await pool.fetchrow(
        "SELECT name_raw, unit_price, ma_hang, don_vi_ban, duong_dung, cach_dung,"
        "       luu_y, biet_duoc, is_active"
        "  FROM public.drug_catalog WHERE id = $1::uuid AND clinic_id = $2::uuid",
        drug_catalog_id,
        identity.clinic_id,
    )
    if t is None:
        raise NotFoundError("Không tìm thấy thuốc này trong danh mục.")
    if t["unit_price"] is not None:
        raise ConflictError(
            "Thuốc này đã có giá — đổi giá ở Kho thuốc › Danh mục thuốc, không ở quầy."
        )
    return await PharmacyService(pool).luu_thuoc(
        identity=identity,
        drug_catalog_id=drug_catalog_id,
        ten=t["name_raw"],
        gia=so,
        ma_hang=t["ma_hang"],
        don_vi_ban=t["don_vi_ban"],
        duong_dung=t["duong_dung"],
        cach_dung=t["cach_dung"],
        luu_y=t["luu_y"],
        biet_duoc=t["biet_duoc"],
        dang_dung=bool(t["is_active"]),
    )


async def doc_dong_lech(
    pool: asyncpg.Pool, *, identity: StaffIdentity, visit_id: str
) -> dict[str, Any]:
    """Dòng thuốc đang chặn thu của lượt + quầy được làm gì với từng dòng.

    Máy chủ quyết cờ, màn chỉ vẽ: `dien_gia_duoc` + `ly_do_khong_dien_gia`,
    `bo_gan_duoc`. Dòng không lỗi mà vừa gán cũng trả về để còn nút hoàn tác."""
    async with pool.acquire() as conn:
        if not head_money_grant(identity, "thuoc", visit_id):
            await doi_quyen(
                conn, identity, QUYEN_THU, cau="Bạn chưa được thu tiền thuốc."
            )
        hd = await tinh_hoa_don(
            conn, clinic_id=identity.clinic_id, visit_id=visit_id, kind="thuoc"
        )
        co_quyen_gia = await can(conn, identity, QUYEN_SUA_GIA)
        rows = await conn.fetch(
            """
            SELECT r.id::text AS id, r.drug_catalog_id, r.drug_name_raw, r.unit,
                   c.unit_price IS NULL AND r.drug_catalog_id IS NOT NULL AS chua_gia
              FROM public.prescription r
              LEFT JOIN public.drug_catalog c
                ON c.id = r.drug_catalog_id AND c.clinic_id = r.clinic_id
             WHERE r.clinic_id = $1::uuid AND r.visit_id = $2::uuid
               AND r.removed_at IS NULL
            """,
            identity.clinic_id,
            visit_id,
        )
        # Thiếu số lượng gỡ ngay ở ô số lượng của dòng (đã tô nổi) — không lặp ở đây.
        van_de = {
            d.source_id: d.van_de
            for d in hd.dong
            if d.van_de and d.van_de != THIEU_SO_LUONG
        }
        dong: list[dict[str, Any]] = []
        gan = await _lan_gan_cuoi_lo(conn, identity.clinic_id, [r["id"] for r in rows])
        for r in rows:
            lan = gan.get(r["id"])
            bo = bo_gan_duoc(lan, _trang(r))
            if r["id"] not in van_de and not bo:
                continue
            dong.append(
                {
                    "prescription_id": r["id"],
                    "van_de": van_de.get(r["id"]),
                    "drug_catalog_id": (
                        str(r["drug_catalog_id"]) if r["drug_catalog_id"] else None
                    ),
                    "dien_gia_duoc": bool(r["chua_gia"]) and co_quyen_gia,
                    "ly_do_khong_dien_gia": (
                        KHONG_QUYEN_GIA if r["chua_gia"] and not co_quyen_gia else None
                    ),
                    "thuoc_chua_gia": bool(r["chua_gia"]),
                    "bo_gan_duoc": bo,
                }
            )
    return {"visit_id": visit_id, "dong": dong}


__all__ = [
    "bo_gan_duoc",
    "dien_gia_thuoc",
    "doc_dong_lech",
    "gan_thuoc_dung",
    "gia_quay",
    "hoan_tac_gan",
]
