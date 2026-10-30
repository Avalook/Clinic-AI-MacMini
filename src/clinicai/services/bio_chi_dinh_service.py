"""Đầu dò Bio chọn ở CHỈ ĐỊNH cận lâm sàng (Tuyền chốt 14/10/2026, G9 · Q14/Q14b).

Bác sĩ chỉ định siêu âm đầu dò / tập máy Bio thì chọn luôn "Bio 1 lần / nhiều
lần" ở chính chỉ định ấy (thay vì để quầy thu thêm tay). Dòng bán vẫn là
`luot_vat_tu` (cùng bảng, cùng hoá đơn DỊCH VỤ, cùng luật khoá khi đã thu) nhưng
GẮN `order_id`:

  * **Tiền đi theo chỉ định.** Chỉ định huỷ / không làm / khách không chọn làm →
    Bio không vào hoá đơn, không thành nợ; khôi phục chỉ định → Bio quay lại.
    Suy từ TRẠNG THÁI chỉ định lúc đọc (`bill_service._VAT_TU_THEO_CHI_DINH`),
    không chép trạng thái sang dòng Bio — chép là mất đồng bộ khi hoàn tác.
  * **Cổng `thu_truoc_khi_lam`** theo chỉ định, không đổi: Bio nằm CÙNG hoá đơn
    nên thu một lần là trả cả dịch vụ lẫn Bio; Bio không tự chặn cửa làm (cửa
    làm xét giá chỉ định). Chưa thu mà làm trước = Bio cũng là nợ của chỉ định ấy.
  * **Quầy thu bỏ được** Bio trước khi thu (`VatTuService.bo`, BẮT ghi lý do);
    đã thu thì khoá — muốn đổi phải "Hoàn tác lần thu" như mọi dòng vật tư.
  * **Chọn = đặt lại, không cộng dồn.** Mỗi chỉ định tối đa một Bio sống (nút
    chọn kiểu radio: Không / 1 lần / nhiều lần). Đổi mặt hàng = bỏ dòng cũ (chưa
    thu) + thêm dòng mới.
  * Hàng `can_ql_duyet` (Mirena) KHÔNG chọn được ở đây — luật duyệt của quầy
    giữ nguyên (việc của G8b).

Quyền = lego `clinical.order.place` (ai chỉ định được thì chọn đầu dò được),
không gác theo vai.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.bill_service import _DA_PHU
from clinicai.services.lenh_kham_core import khoa_luot, luot_cua
from clinicai.services.lenh_kham_core import ma_uuid as _uuid
from clinicai.services.vat_tu_ban_service import dong_bo_ban_vat_tu
from clinicai.services.vat_tu_service import (
    SO_LUONG_TOI_DA,
    ghi_su_kien_vat_tu,
    ly_do_khong_ban,
)

QUYEN_CHI_DINH = "clinical.order.place"

LY_DO_DOI_CHON = "Bác sĩ đổi lựa chọn đầu dò ở chỉ định."
LY_DO_BO_CHON = "Bác sĩ bỏ chọn đầu dò ở chỉ định."

#: Chỉ định còn SỐNG: chưa huỷ / không làm (cùng nghĩa với hoá đơn).
_SONG = """
    o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
    AND coalesce(o.execution_status, 'PENDING') NOT IN ('CANCELLED', 'NOT_PERFORMED')
"""

#: Dòng đã nằm trong lần thu đang giữ phủ — suy từ sổ (như `luot_vat_tu_gac`).
_DA_THU = _DA_PHU.format(loai="'vat_tu'", nguon="v.id::text")

_CHI_DINH_SQL = f"""
SELECT o.id::text AS id, o.service_code, o.service_name, o.selection_status
  FROM public.service_order o
 WHERE o.clinic_id = $1::uuid AND o.visit_id = $2::uuid AND {_SONG}
 ORDER BY o.created_at, o.id
"""

_GOI_Y_SQL = """
SELECT dv.service_code, sp.id::text AS id, sp.name, sp.don_vi, sp.unit_price,
       sp.active, sp.can_ql_duyet, sp.kinh_doanh_vat_tu
  FROM public.vat_tu_goi_y g
  JOIN public.service_price dv
    ON dv.id = g.dich_vu_id AND dv.clinic_id = g.clinic_id
   AND dv."group" = 'dich_vu'
  JOIN public.service_price sp
    ON sp.id = g.vat_tu_id AND sp.clinic_id = g.clinic_id AND sp."group" = 'vat_tu'
 WHERE g.clinic_id = $1::uuid AND dv.service_code = ANY($2::text[])
 ORDER BY sp.unit_price NULLS LAST, sp.name
"""

_DONG_SQL = f"""
SELECT v.id::text AS id, v.order_id::text AS order_id,
       v.service_price_id::text AS service_price_id, v.ten, v.don_vi, v.don_gia,
       v.so_luong, {_DA_THU} AS da_thu
  FROM public.luot_vat_tu v
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid AND v.bo_luc IS NULL
   AND v.order_id IS NOT NULL
 ORDER BY v.chon_luc, v.id
"""


def _so_luong(raw: Any) -> int:
    """Số lượng 1..99. Rác (chữ, rỗng, số lẻ, true/false) → 422, không làm tròn."""
    if isinstance(raw, bool) or raw is None:
        raise ValidationError("Số lượng không hợp lệ.")
    if isinstance(raw, float) and not raw.is_integer():
        raise ValidationError("Số lượng không hợp lệ.")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("Số lượng không hợp lệ.") from None
    if not 1 <= n <= SO_LUONG_TOI_DA:
        raise ValidationError(f"Số lượng từ 1 đến {SO_LUONG_TOI_DA}.")
    return n


async def bio_da_thu_cua_chi_dinh(
    conn: asyncpg.Connection, clinic_id: str, order_id: str
) -> int:
    """Tổng tiền vật tư đi kèm chỉ định mà khách ĐÃ TRẢ (dòng sống nằm trong lần
    thu đang giữ phủ). Dùng để báo khi bỏ chỉ định đã thu: khoản này không tự
    thành "tiền thừa" — hoàn ở quầy thu như mọi dòng vật tư đã thu."""
    v = await conn.fetchval(
        f"SELECT coalesce(sum(v.don_gia * v.so_luong), 0)"
        f" FROM public.luot_vat_tu v"
        f" WHERE v.clinic_id = $1::uuid AND v.order_id = $2::uuid"
        f"   AND v.bo_luc IS NULL AND {_DA_THU}",
        clinic_id,
        order_id,
    )
    return int(v or 0)


async def chuyen_bio_chua_thu(
    conn: asyncpg.Connection, clinic_id: str, tu_order: str, sang_order: str
) -> int:
    """Chỉ định được ĐẶT LẠI thành chỉ định MỚI (hoàn tác bỏ sau khi đã hoàn
    tiền): Bio còn sống mà chưa thu đi theo sang chỉ định mới. Trả số dòng."""
    kq = await conn.execute(
        "UPDATE public.luot_vat_tu v SET order_id = $3::uuid"
        " WHERE v.clinic_id = $1::uuid AND v.order_id = $2::uuid"
        f"   AND v.bo_luc IS NULL AND NOT {_DA_THU}",
        clinic_id,
        tu_order,
        sang_order,
    )
    return int(kq.split()[-1])


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    chi_dinh = await conn.fetch(_CHI_DINH_SQL, clinic_id, visit_id)
    ma = sorted({r["service_code"] for r in chi_dinh})
    goi_y_theo_ma: dict[str, list[dict[str, Any]]] = {}
    for r in await conn.fetch(_GOI_Y_SQL, clinic_id, ma):
        # Chỉ hàng bán được và KHÔNG cần quản lý duyệt (luật duyệt ở quầy).
        if (
            ly_do_khong_ban(
                active=r["active"],
                don_gia=r["unit_price"],
                kinh_doanh=r["kinh_doanh_vat_tu"],
            )
            or r["can_ql_duyet"]
        ):
            continue
        goi_y_theo_ma.setdefault(r["service_code"], []).append(
            {
                "service_price_id": r["id"],
                "ten": r["name"],
                "don_vi": r["don_vi"],
                "don_gia": int(r["unit_price"]),
            }
        )
    dong_theo_don: dict[str, dict[str, Any]] = {}
    for r in await conn.fetch(_DONG_SQL, clinic_id, visit_id):
        dong_theo_don[r["order_id"]] = {
            "dong_id": r["id"],
            "service_price_id": r["service_price_id"],
            "ten": r["ten"],
            "so_luong": int(r["so_luong"]),
            "don_gia": int(r["don_gia"]),
            "thanh_tien": int(r["don_gia"]) * int(r["so_luong"]),
            "da_thu": bool(r["da_thu"]),
        }
    out = []
    for r in chi_dinh:
        goi_y = goi_y_theo_ma.get(r["service_code"], [])
        da_chon = dong_theo_don.get(r["id"])
        if not goi_y and da_chon is None:
            continue  # chỉ định này không đi kèm đầu dò — không vẽ gì
        out.append(
            {
                "order_id": r["id"],
                "ten": r["service_name"],
                "chon_lam": r["selection_status"] != "NOT_SELECTED",
                "goi_y": goi_y,
                "da_chon": da_chon,
            }
        )
    return {"visit_id": visit_id, "chi_dinh": out}


class BioChiDinhService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Đầu dò gợi ý + đã chọn theo từng chỉ định của lượt (màn chỉ định CLS)."""
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        async with self._pool.acquire() as conn:
            if not await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM public.visit"
                " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid)",
                identity.clinic_id,
                vid,
            ):
                raise NotFoundError("Không tìm thấy lượt khám này.")
            kq = await _doc(conn, identity.clinic_id, vid)
            kq["duoc_sua"] = await can(conn, identity, QUYEN_CHI_DINH)
            return kq

    async def chon(
        self,
        *,
        order_id: str,
        service_price_id: str | None,
        so_luong: Any = 1,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """ĐẶT đầu dò của một chỉ định (radio): `service_price_id` = mặt hàng,
        None = không dùng đầu dò. Gọi lại với cùng giá trị là không đổi gì.

        Đã thu → khoá (ConflictError): hoàn tác lần thu rồi mới đổi.
        """
        oid = _uuid(order_id, "Mã chỉ định không hợp lệ.")
        spid = (
            None
            if service_price_id is None
            else _uuid(service_price_id, "Mã đầu dò không hợp lệ.")
        )
        sl = _so_luong(so_luong)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await doi_quyen(
                conn,
                identity,
                QUYEN_CHI_DINH,
                cau="Bạn không có quyền chỉ định dịch vụ nên không chọn được đầu dò.",
            )
            vid = await luot_cua(conn, "service_order", cid, oid)
            await khoa_luot(conn, cid, vid, cho_phep_da_ky=True)
            o = await conn.fetchrow(
                f"SELECT o.service_name, ({_SONG}) AS song"
                " FROM public.service_order o"
                " WHERE o.clinic_id = $1::uuid AND o.id = $2::uuid FOR UPDATE",
                cid,
                oid,
            )
            assert o is not None
            hien = list(
                await conn.fetch(
                    "SELECT v.id::text AS id, v.service_price_id::text AS spid,"
                    " v.ten, v.don_gia, v.so_luong,"
                    " v.duyet_boi IS NOT NULL AS co_duyet,"
                    f" {_DA_THU} AS da_thu"
                    " FROM public.luot_vat_tu v"
                    " WHERE v.clinic_id = $1::uuid AND v.order_id = $2::uuid"
                    "   AND v.bo_luc IS NULL ORDER BY v.chon_luc FOR UPDATE OF v",
                    cid,
                    oid,
                )
            )
            moi = None
            if spid is not None:
                if not o["song"]:
                    raise ConflictError(
                        f"“{o['service_name']}” đã bỏ / không làm — không chọn"
                        " đầu dò cho chỉ định này."
                    )
                moi = await conn.fetchrow(
                    "SELECT name, don_vi, unit_price, active, can_ql_duyet,"
                    " kinh_doanh_vat_tu"
                    " FROM public.service_price WHERE clinic_id = $1::uuid"
                    " AND id = $2::uuid AND \"group\" = 'vat_tu'",
                    cid,
                    spid,
                )
                if moi is None:
                    raise NotFoundError("Không tìm thấy đầu dò / vật tư này.")
                khong_ban = ly_do_khong_ban(
                    active=moi["active"],
                    don_gia=moi["unit_price"],
                    kinh_doanh=moi["kinh_doanh_vat_tu"],
                )
                if khong_ban:
                    raise ValidationError(f"“{moi['name']}” {khong_ban}.")
                if moi["can_ql_duyet"]:
                    raise ValidationError(
                        f"“{moi['name']}” cần quản lý duyệt — thêm ở quầy thu"
                        " dịch vụ (Mua thêm vật tư), không chọn ở chỉ định."
                    )

            giu = None  # dòng sống đúng mặt hàng đã chọn (giữ, chỉ đổi số lượng)
            for d in hien:
                if spid is not None and d["spid"] == spid:
                    giu = d
                    continue
                if d["da_thu"]:
                    raise ConflictError(
                        f"“{d['ten']}” đã thu tiền — hoàn tác lần thu trước khi đổi."
                    )
            # Bỏ dòng khác (chọn lại / "không dùng đầu dò") — đóng dấu, không xoá.
            for d in hien:
                if d is giu:
                    continue
                ly = LY_DO_DOI_CHON if spid is not None else LY_DO_BO_CHON
                await conn.execute(
                    "UPDATE public.luot_vat_tu SET bo_luc = now(),"
                    " bo_boi = $2::uuid, bo_ly_do = $3 WHERE id = $1::uuid",
                    d["id"],
                    identity.staff_id,
                    ly,
                )
                await ghi_su_kien_vat_tu(
                    conn,
                    identity,
                    vid,
                    d["id"],
                    d["spid"],
                    d["ten"],
                    "bo",
                    int(d["so_luong"]),
                    Decimal(str(d["don_gia"])),
                    bool(d["co_duyet"]),
                    order_id=oid,
                    ly_do=ly,
                )
            if moi is not None and spid is not None:
                gia = Decimal(str(moi["unit_price"]))
                if giu is None:
                    dong_id = str(
                        await conn.fetchval(
                            "INSERT INTO public.luot_vat_tu (clinic_id, visit_id,"
                            " service_price_id, ten, don_vi, don_gia, so_luong,"
                            " chon_boi, order_id)"
                            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7,"
                            " $8::uuid, $9::uuid) RETURNING id",
                            cid,
                            vid,
                            spid,
                            moi["name"],
                            moi["don_vi"],
                            gia,
                            sl,
                            identity.staff_id,
                            oid,
                        )
                    )
                    await ghi_su_kien_vat_tu(
                        conn,
                        identity,
                        vid,
                        dong_id,
                        spid,
                        moi["name"],
                        "them",
                        sl,
                        gia,
                        False,
                        order_id=oid,
                    )
                elif int(giu["so_luong"]) != sl:
                    if giu["da_thu"]:
                        raise ConflictError(
                            f"“{giu['ten']}” đã thu tiền — hoàn tác lần thu"
                            " trước khi đổi."
                        )
                    await conn.execute(
                        "UPDATE public.luot_vat_tu SET so_luong = $2"
                        " WHERE id = $1::uuid",
                        giu["id"],
                        sl,
                    )
                    await ghi_su_kien_vat_tu(
                        conn,
                        identity,
                        vid,
                        giu["id"],
                        spid,
                        giu["ten"],
                        "sua",
                        sl,
                        Decimal(str(giu["don_gia"])),
                        False,
                        order_id=oid,
                    )
            # Chỉ định đã làm thì đầu dò đã trừ dù chưa thu: đổi loại / số phải về
            # đúng chỗ ngay. Đã thu thì các nhánh trên đã khoá, lệnh này không đổi gì.
            await dong_bo_ban_vat_tu(
                conn, identity, vid, ly_do="Bác sĩ đổi đầu dò ở chỉ định."
            )
            return await _doc(conn, cid, vid)


__all__ = ["BioChiDinhService", "bio_da_thu_cua_chi_dinh", "chuyen_bio_chua_thu"]
