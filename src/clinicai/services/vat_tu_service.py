"""Bán thêm vật tư ở QUẦY THU DỊCH VỤ (Tuyền 01/10/2026, việc C13).

"Ở quầy thu dịch vụ tick / thêm 'Mua thêm vật tư' vào hoá đơn khách" — trước hết
hai đầu dò Bio (1 lần 300.000đ, nhiều lần 900.000đ) chọn nhanh bằng một cú bấm,
hàng khác tìm theo tên.

Danh mục = `service_price` nhóm ``vat_tu`` (migration 20261003000000; nạp từ file
KiotViet 01/10: giá 0 = KHÔNG được bán → nạp NULL "chưa có giá"). Dòng bán cho
một khách = ``luot_vat_tu`` (theo LƯỢT, không gắn chỉ định): tên / đơn vị / đơn
giá chốt lúc thêm, số lượng 1..99, bỏ = đóng dấu. Tiền vào hoá đơn DỊCH VỤ
(dòng ``vat_tu`` của `payment_bill_line`) — KHÔNG phải tiền thuốc: quầy thuốc
không thêm / không thu được (cùng cửa quyền thu dịch vụ với món kèm).

Dòng ĐI KÈM CHỈ ĐỊNH (``order_id``): đầu dò Bio bác sĩ chọn ở chỉ định CLS —
`bio_chi_dinh_service.py` (G9, 14/10/2026). Quầy thấy dòng ấy, bỏ thì bắt ghi lý do;
tiền theo chỉ định (huỷ / khách không làm thì không tính).

Hàng ``can_ql_duyet`` (vòng Mirena — đã nằm trong giá dịch vụ đặt vòng, chỉ bán
khi sự cố cần vòng thứ 2): mỗi lần thêm phải có NGƯỜI DUYỆT + lý do. Người duyệt
là người có lego "Duyệt vật tư" (`vat_tu.approve`, G8b 14/10/2026): mặc định Quản
lý, Quản lý cấp thêm cho Trưởng ca — KHÔNG theo vai. Người có lego tự thêm thì
chính họ là người duyệt; nhân sự khác chọn người đã duyệt (đang làm việc, đang có
lego). Postgres ép lại (trigger `luot_vat_tu_gac`).

NGUYÊN NHÂN BÁN THÊM (`ly_do_ban`, G8b): luôn ghi khi có gửi (5–500 ký tự, rác →
422); dây `vat_tu_bat_ly_do_ban` BẬT thì dòng MỚI thêm ở quầy phải có (TẮT = tuỳ
chọn, mặc định — quầy bấm nhanh như cũ). Đầu dò bác sĩ chọn ở chỉ định không đòi.

Đã thu (lần thu đang giữ phủ dòng ấy) → khoá; muốn đổi thì "Hoàn tác lần thu"
(dòng tự trở lại chờ thu vì tiền suy từ sổ lần thu, không lưu cờ riêng).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import VatTuDaDoi
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can
from clinicai.services.audit import record_event
from clinicai.services.bill_service import _DA_PHU
from clinicai.services.day_noi import doc_day
from clinicai.services.lenh_kham_core import khoa_luot
from clinicai.services.lenh_kham_core import ma_uuid as _uuid

#: Quầy thu dịch vụ / chọn dịch vụ cho khách — KHÔNG gồm quyền thu thuốc.
QUYEN_VAT_TU = ("payment.service.collect", "service_selection.confirm")

#: Quyền DUYỆT hàng cần duyệt — lego "Duyệt vật tư" (G8b), không theo vai.
QUYEN_DUYET = "vat_tu.approve"

#: Dây: BẮT ghi nguyên nhân bán thêm (mặc định TẮT).
DAY_BAT_LY_DO_BAN = "vat_tu_bat_ly_do_ban"

#: Số lượng một dòng (khớp CHECK của bảng).
SO_LUONG_TOI_DA = 99

KHONG_BAN_CHUA_GIA = "chưa có giá — không bán"
KHONG_BAN_NGUNG = "đã ngưng bán"
CAN_QL_DUYET = "cần người có quyền duyệt"

#: Dòng đã nằm trong lần thu đang giữ phủ (chờ xác minh / đã thu) — suy từ sổ.
_DA_THU = _DA_PHU.format(loai="'vat_tu'", nguon="v.id::text")

_DANH_MUC_SQL = """
SELECT sp.id::text AS id, sp.name, sp.don_vi, sp.unit_price, sp.active,
       sp.can_ql_duyet, sp.chon_nhanh,
       EXISTS (
           SELECT 1
             FROM public.vat_tu_goi_y g
             JOIN public.service_order o
               ON o.clinic_id = g.clinic_id
              AND o.visit_id = $2::uuid
             JOIN public.service_price dv
               ON dv.id = g.dich_vu_id AND dv.service_code = o.service_code
              AND dv.clinic_id = o.clinic_id
            WHERE g.vat_tu_id = sp.id
              AND o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
              AND coalesce(o.selection_status, 'SELECTED') <> 'NOT_SELECTED'
       ) AS goi_y
  FROM public.service_price sp
 WHERE sp.clinic_id = $1::uuid AND sp."group" = 'vat_tu'
 ORDER BY sp.chon_nhanh DESC, (sp.unit_price IS NULL), sp.name
"""

_DONG_SQL = """
SELECT v.id::text AS id, v.service_price_id::text AS service_price_id, v.ten,
       v.don_vi, v.don_gia, v.so_luong, v.duyet_ly_do,
       v.order_id::text AS order_id, o.service_name AS ten_chi_dinh,
       v.ly_do_ban,
       sd.full_name AS nguoi_duyet,
       {da_thu} AS da_thu,
       -- Vật tư đi kèm chỉ định (đầu dò Bio, G9): chỉ tính khi khách làm dịch vụ.
       (v.order_id IS NULL
        OR o.selection_status IS DISTINCT FROM 'NOT_SELECTED') AS chon_lam
  FROM public.luot_vat_tu v
  LEFT JOIN public.service_order o
    ON o.id = v.order_id AND o.clinic_id = v.clinic_id
  LEFT JOIN public.staff sd ON sd.id = v.duyet_boi
 WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid AND v.bo_luc IS NULL
   -- Chỉ định đã huỷ / không làm → Bio đi kèm ẨN (khôi phục thì hiện lại);
   -- riêng dòng ĐÃ THU luôn hiện để quầy còn thấy khoản đã nhận.
   AND (v.order_id IS NULL OR {da_thu}
        OR (o.exec_status NOT IN ('draft', 'cancelled', 'not_performed')
            AND coalesce(o.execution_status, 'PENDING')
                NOT IN ('CANCELLED', 'NOT_PERFORMED')))
 ORDER BY v.chon_luc, v.id
"""

#: Người duyệt hợp lệ = đang làm việc + CÓ lego Duyệt vật tư (phạm vi toàn phòng
#: khám). Hai câu hỏi dùng cùng điều kiện: danh sách chọn ($2 rỗng) và kiểm một
#: người ($2 = mã người). Cùng điều kiện với trigger `luot_vat_tu_gac`.
_NGUOI_DUYET_SQL = """
SELECT DISTINCT s.id::text AS id, s.full_name AS ten
  FROM public.v_quyen_thuc_te q
  JOIN public.clinic_membership m
    ON m.clinic_id = q.clinic_id AND m.staff_id = q.staff_id AND m.is_active
  JOIN public.staff s ON s.id = q.staff_id AND s.is_active
 WHERE q.clinic_id = $1::uuid AND q.capability = 'vat_tu.approve'
   AND q.scope_type = 'CLINIC'
   AND ($2::uuid IS NULL OR q.staff_id = $2::uuid)
 ORDER BY ten
"""


def ly_do_khong_ban(*, active: bool, don_gia: Decimal | int | None) -> str | None:
    """Vì sao một vật tư KHÔNG bán được — None = bán được. Hàm thuần.

    Luật file KiotViet 01/10: "giá 0 = không được phép bán" (nạp NULL).
    """
    if not active:
        return KHONG_BAN_NGUNG
    if don_gia is None or Decimal(str(don_gia)) <= 0:
        return KHONG_BAN_CHUA_GIA
    return None


def _ly_do_duyet(raw: Any) -> str:
    ly = raw.strip() if isinstance(raw, str) else ""
    if not 5 <= len(ly) <= 500:
        raise ValidationError(
            "Hàng này cần người có quyền duyệt — ghi lý do duyệt (5 đến 500 ký tự)."
        )
    return ly


def _ly_do_bo(raw: Any, *, bat_buoc: bool) -> str | None:
    """Lý do bỏ dòng vật tư. Dòng đi kèm chỉ định: BẮT BUỘC (5–500 ký tự).
    Dòng quầy: bỏ trống được; đã gửi thì phải hợp lệ — không ghi rác."""
    ly = raw.strip() if isinstance(raw, str) else ""
    if not ly and not bat_buoc and raw in (None, ""):
        return None
    if not 5 <= len(ly) <= 500:
        raise ValidationError(
            "Đầu dò do bác sĩ chọn ở chỉ định — ghi lý do bỏ (5 đến 500 ký tự)."
            if bat_buoc
            else "Lý do bỏ từ 5 đến 500 ký tự."
        )
    return ly


def _ly_do_ban(raw: Any, *, bat_buoc: bool) -> str | None:
    """Nguyên nhân bán thêm. Không gửi (None) → None, trừ khi dây BẮT. Đã gửi thì
    phải là chữ 5–500 ký tự — rỗng / số / danh sách → 422, không ghi rác."""
    if raw is None:
        if bat_buoc:
            raise ValidationError(
                "Ghi nguyên nhân bán thêm vật tư (5 đến 500 ký tự) rồi mới thêm được."
            )
        return None
    ly = raw.strip() if isinstance(raw, str) else ""
    if not 5 <= len(ly) <= 500:
        raise ValidationError("Nguyên nhân bán thêm từ 5 đến 500 ký tự.")
    return ly


def _so_luong(raw: Any) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("Số lượng không hợp lệ.") from None
    if not 1 <= n <= SO_LUONG_TOI_DA:
        raise ValidationError(f"Số lượng từ 1 đến {SO_LUONG_TOI_DA}.")
    return n


async def _duoc_duyet(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    return await can(conn, identity, QUYEN_DUYET)


async def _duoc(conn: asyncpg.Connection, identity: StaffIdentity) -> bool:
    for q in QUYEN_VAT_TU:
        if await can(conn, identity, q):
            return True
    return False


async def _doc(
    conn: asyncpg.Connection, clinic_id: str, visit_id: str
) -> dict[str, Any]:
    danh_muc = []
    for r in await conn.fetch(_DANH_MUC_SQL, clinic_id, visit_id):
        khong_ban = ly_do_khong_ban(active=r["active"], don_gia=r["unit_price"])
        danh_muc.append(
            {
                "id": r["id"],
                "ten": r["name"],
                "don_vi": r["don_vi"],
                "don_gia": int(r["unit_price"])
                if r["unit_price"] is not None
                else None,
                "ban_duoc": khong_ban is None,
                "ly_do_khong_ban": khong_ban,
                "can_ql_duyet": bool(r["can_ql_duyet"]),
                "chon_nhanh": bool(r["chon_nhanh"]),
                # Lượt có dịch vụ cần món này (Tập máy Bio → đầu dò): nổi lên đầu.
                "goi_y": bool(r["goi_y"]),
            }
        )
    # Nút chọn nhanh trước, trong đó vật tư lượt này CẦN (gợi ý) lên đầu; rồi hàng
    # bán được; còn lại theo tên. Màn chỉ vẽ theo thứ tự này.
    danh_muc.sort(
        key=lambda m: (
            not m["chon_nhanh"],
            not m["goi_y"],
            not m["ban_duoc"],
            m["ten"].lower(),
        )
    )
    dong = []
    for r in await conn.fetch(
        _DONG_SQL.format(da_thu=_DA_THU),
        clinic_id,
        visit_id,
    ):
        da_thu = bool(r["da_thu"])
        dong.append(
            {
                "id": r["id"],
                "service_price_id": r["service_price_id"],
                "ten": r["ten"],
                "don_vi": r["don_vi"],
                "don_gia": int(r["don_gia"]),
                "so_luong": int(r["so_luong"]),
                "thanh_tien": int(r["don_gia"]) * int(r["so_luong"]),
                "da_thu": da_thu,
                "nguoi_duyet": r["nguoi_duyet"],
                "ly_do_duyet": r["duyet_ly_do"],
                # Nguyên nhân bán thêm (G8b): vì sao quầy thêm vật tư này.
                "ly_do_ban": r["ly_do_ban"],
                # Đi kèm chỉ định (G9): bác sĩ chọn ở chỉ định CLS; bỏ thì bắt lý do.
                "order_id": r["order_id"],
                "ten_chi_dinh": r["ten_chi_dinh"],
                # Khách không làm dịch vụ ấy → dòng hiện nhưng KHÔNG tính tiền.
                "tinh_tien": bool(r["chon_lam"]) or da_thu,
            }
        )
    return {
        "danh_muc": danh_muc,
        "dong": dong,
        "tong": sum(d["thanh_tien"] for d in dong if d["tinh_tien"]),
    }


class VatTuService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def doc(self, *, visit_id: str, identity: StaffIdentity) -> dict[str, Any]:
        """Danh mục vật tư + dòng đã thêm của lượt + ai sửa được."""
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
            kq["duoc_sua"] = await _duoc(conn, identity)
            # Tên khoá giữ nguyên cho màn quầy: `la_quan_ly` = người xem CÓ quyền
            # duyệt (tự duyệt được), `quan_ly` = những người có thể chọn làm
            # người duyệt (có lego Duyệt vật tư) — không còn nghĩa "vai Quản lý".
            kq["la_quan_ly"] = await _duoc_duyet(conn, identity)
            kq["quan_ly"] = [
                {"id": r["id"], "ten": r["ten"]}
                for r in await conn.fetch(_NGUOI_DUYET_SQL, identity.clinic_id, None)
            ]
            kq["bat_ly_do_ban"] = bool(
                await doc_day(conn, identity.clinic_id, DAY_BAT_LY_DO_BAN)
            )
            return kq

    async def _cong(self, conn: asyncpg.Connection, identity: StaffIdentity) -> None:
        if not await _duoc(conn, identity):
            raise SafetyGateError(
                "Bán thêm vật tư là việc của quầy Thu tiền dịch vụ — "
                "bạn không có quyền này."
            )

    async def _nguoi_duyet(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        duyet_boi: Any,
        ly_do: Any,
    ) -> tuple[str, str]:
        """(người duyệt, lý do) cho hàng cần duyệt. Người có lego Duyệt vật tư tự
        thêm = tự duyệt."""
        ly = _ly_do_duyet(ly_do)
        if await _duoc_duyet(conn, identity):
            return identity.staff_id, ly
        if not duyet_boi:
            raise ValidationError(
                "Hàng này cần người có quyền duyệt bán — chọn người đã duyệt và"
                " ghi lý do."
            )
        qid = _uuid(duyet_boi, "Mã người duyệt không hợp lệ.")
        if not await conn.fetchrow(_NGUOI_DUYET_SQL, identity.clinic_id, qid):
            raise ValidationError(
                "Người duyệt phải đang làm việc và có quyền Duyệt vật tư."
            )
        return qid, ly

    async def them(
        self,
        *,
        visit_id: str,
        service_price_id: str,
        so_luong: Any = 1,
        cong_don: bool = True,
        duyet_boi: Any = None,
        ly_do_duyet: Any = None,
        ly_do_ban: Any = None,
        identity: StaffIdentity,
    ) -> dict[str, Any]:
        """Thêm một vật tư vào hoá đơn dịch vụ của lượt.

        Mặt hàng đã có dòng chờ thu: `cong_don` (mặc định — nút chọn nhanh bấm
        lần nữa) cộng thêm số lượng, ngược lại đặt đúng số lượng đã gửi.
        `ly_do_ban` = nguyên nhân bán thêm (G8b): ghi khi có gửi; dây BẬT thì dòng
        mới (hoặc dòng cũ chưa có nguyên nhân) bắt buộc phải có.
        """
        vid = _uuid(visit_id, "Mã lượt khám không hợp lệ.")
        spid = _uuid(service_price_id, "Mã vật tư không hợp lệ.")
        sl = _so_luong(so_luong)
        _ly_do_ban(ly_do_ban, bat_buoc=False)  # rác thì 422 trước khi chạm DB
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            await self._cong(conn, identity)
            await khoa_luot(conn, cid, vid, cho_phep_da_ky=True)
            sp = await conn.fetchrow(
                "SELECT name, don_vi, unit_price, active, can_ql_duyet"
                " FROM public.service_price WHERE clinic_id = $1::uuid"
                " AND id = $2::uuid AND \"group\" = 'vat_tu'",
                cid,
                spid,
            )
            if sp is None:
                raise NotFoundError("Không tìm thấy vật tư này.")
            khong_ban = ly_do_khong_ban(active=sp["active"], don_gia=sp["unit_price"])
            if khong_ban:
                raise ValidationError(f"“{sp['name']}” {khong_ban}.")
            duyet: tuple[str, str] | None = None
            if sp["can_ql_duyet"]:
                duyet = await self._nguoi_duyet(conn, identity, duyet_boi, ly_do_duyet)

            hien = await conn.fetchrow(
                "SELECT v.id::text AS id, v.so_luong, v.don_gia, v.ly_do_ban,"
                f" {_DA_THU} AS da_thu"
                " FROM public.luot_vat_tu v"
                " WHERE v.clinic_id = $1::uuid AND v.visit_id = $2::uuid"
                "   AND v.service_price_id = $3::uuid AND v.bo_luc IS NULL"
                # Dòng đi kèm chỉ định (Bio bác sĩ chọn, G9) là dòng RIÊNG — quầy
                # bấm thêm không cộng vào đó, không nuốt nó.
                "   AND v.order_id IS NULL",
                cid,
                vid,
                spid,
            )
            if hien is not None and hien["da_thu"]:
                raise ConflictError(
                    f"“{sp['name']}” đã thu tiền — hoàn tác lần thu trước khi đổi."
                )
            gia = Decimal(str(sp["unit_price"]))
            bat = bool(await doc_day(conn, cid, DAY_BAT_LY_DO_BAN))
            ly_ban = _ly_do_ban(
                ly_do_ban, bat_buoc=bat and (hien is None or hien["ly_do_ban"] is None)
            )
            if hien is None:
                dong_id = str(
                    await conn.fetchval(
                        "INSERT INTO public.luot_vat_tu (clinic_id, visit_id,"
                        " service_price_id, ten, don_vi, don_gia, so_luong,"
                        " chon_boi, duyet_boi, duyet_ly_do, ly_do_ban)"
                        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, $5, $6, $7,"
                        " $8::uuid, $9::uuid, $10, $11) RETURNING id",
                        cid,
                        vid,
                        spid,
                        sp["name"],
                        sp["don_vi"],
                        gia,
                        sl,
                        identity.staff_id,
                        duyet[0] if duyet else None,
                        duyet[1] if duyet else None,
                        ly_ban,
                    )
                )
                moi = sl
                hanh_dong = "them"
            else:
                dong_id = hien["id"]
                moi = (
                    min(int(hien["so_luong"]) + sl, SO_LUONG_TOI_DA) if cong_don else sl
                )
                await conn.execute(
                    "UPDATE public.luot_vat_tu SET so_luong = $2, don_gia = $3,"
                    " duyet_boi = coalesce($4::uuid, duyet_boi),"
                    " duyet_ly_do = coalesce($5, duyet_ly_do),"
                    " ly_do_ban = coalesce($6, ly_do_ban)"
                    " WHERE id = $1::uuid",
                    dong_id,
                    moi,
                    gia,
                    duyet[0] if duyet else None,
                    duyet[1] if duyet else None,
                    ly_ban,
                )
                hanh_dong = "sua"
            await ghi_su_kien_vat_tu(
                conn,
                identity,
                vid,
                dong_id,
                spid,
                sp["name"],
                hanh_dong,
                moi,
                gia,
                bool(sp["can_ql_duyet"]),
                ly_do=ly_ban,
            )
            return await _doc(conn, cid, vid)

    async def _dong_song(
        self, conn: asyncpg.Connection, identity: StaffIdentity, dong_id: str
    ) -> asyncpg.Record:
        r = await conn.fetchrow(
            "SELECT v.id::text AS id, v.visit_id::text AS visit_id,"
            " v.service_price_id::text AS spid, v.ten, v.don_gia, v.so_luong,"
            " (v.duyet_boi IS NOT NULL) AS co_duyet,"
            " v.order_id::text AS order_id,"
            f" {_DA_THU} AS da_thu"
            " FROM public.luot_vat_tu v"
            " WHERE v.clinic_id = $1::uuid AND v.id = $2::uuid AND v.bo_luc IS NULL"
            " FOR UPDATE OF v",
            identity.clinic_id,
            dong_id,
        )
        if r is None:
            raise NotFoundError("Không tìm thấy dòng vật tư này (có thể đã được bỏ).")
        return r

    async def dat_so_luong(
        self, *, dong_id: str, so_luong: Any, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Đặt lại số lượng một dòng vật tư chưa thu."""
        did = _uuid(dong_id, "Mã dòng vật tư không hợp lệ.")
        sl = _so_luong(so_luong)
        async with self._pool.acquire() as conn, conn.transaction():
            await self._cong(conn, identity)
            r = await self._dong_song(conn, identity, did)
            await khoa_luot(
                conn, identity.clinic_id, r["visit_id"], cho_phep_da_ky=True
            )
            if r["da_thu"]:
                raise ConflictError(
                    f"“{r['ten']}” đã thu tiền — hoàn tác lần thu trước khi đổi."
                )
            if int(r["so_luong"]) != sl:
                await conn.execute(
                    "UPDATE public.luot_vat_tu SET so_luong = $2 WHERE id = $1::uuid",
                    did,
                    sl,
                )
                await ghi_su_kien_vat_tu(
                    conn,
                    identity,
                    r["visit_id"],
                    did,
                    r["spid"],
                    r["ten"],
                    "sua",
                    sl,
                    Decimal(str(r["don_gia"])),
                    bool(r["co_duyet"]),
                    order_id=r["order_id"],
                )
            return await _doc(conn, identity.clinic_id, r["visit_id"])

    async def bo(
        self, *, dong_id: str, ly_do: Any = None, identity: StaffIdentity
    ) -> dict[str, Any]:
        """Bỏ một dòng vật tư chưa thu khỏi hoá đơn (đóng dấu, không xoá).

        Dòng ĐI KÈM CHỈ ĐỊNH (đầu dò Bio bác sĩ chọn, G9 14/10/2026) bỏ ở quầy
        thì BẮT ghi lý do (khách không mua nữa…); dòng quầy tự thêm bỏ như cũ,
        lý do tuỳ chọn nhưng đã gửi thì phải hợp lệ (5 đến 500 ký tự).
        """
        did = _uuid(dong_id, "Mã dòng vật tư không hợp lệ.")
        async with self._pool.acquire() as conn, conn.transaction():
            await self._cong(conn, identity)
            r = await self._dong_song(conn, identity, did)
            ly = _ly_do_bo(ly_do, bat_buoc=r["order_id"] is not None)
            await khoa_luot(
                conn, identity.clinic_id, r["visit_id"], cho_phep_da_ky=True
            )
            if r["da_thu"]:
                raise ConflictError(
                    f"“{r['ten']}” đã thu tiền — hoàn tác lần thu trước khi bỏ."
                )
            await conn.execute(
                "UPDATE public.luot_vat_tu SET bo_luc = now(), bo_boi = $2::uuid,"
                " bo_ly_do = $3 WHERE id = $1::uuid",
                did,
                identity.staff_id,
                ly,
            )
            await ghi_su_kien_vat_tu(
                conn,
                identity,
                r["visit_id"],
                did,
                r["spid"],
                r["ten"],
                "bo",
                int(r["so_luong"]),
                Decimal(str(r["don_gia"])),
                bool(r["co_duyet"]),
                order_id=r["order_id"],
                ly_do=ly,
            )
            return await _doc(conn, identity.clinic_id, r["visit_id"])


async def ghi_su_kien_vat_tu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    visit_id: str,
    dong_id: str,
    service_price_id: str,
    ten: str,
    hanh_dong: str,
    so_luong: int,
    don_gia: Decimal,
    can_duyet: bool,
    *,
    order_id: str | None = None,
    ly_do: str | None = None,
) -> None:
    """Sổ sự kiện (domain_event — các màn nghe) + nhật ký thao tác (event_log),
    CÙNG giao dịch với thay đổi dòng. Dùng chung với `BioChiDinhService`."""
    await emit_event(
        conn,
        ten="visit.supply_changed",
        clinic_id=identity.clinic_id,
        aggregate_id=visit_id,
        so_ke_tiep=True,
        payload=VatTuDaDoi(
            visit_id=visit_id,
            luot_vat_tu_id=dong_id,
            service_price_id=service_price_id,
            ten=ten,
            hanh_dong=hanh_dong,
            so_luong=so_luong,
            don_gia=int(don_gia),
            can_ql_duyet=can_duyet,
            service_order_id=order_id,
            ly_do=ly_do,
        ),
        boi=nguoi(identity),
        correlation_id=visit_id,
    )
    await record_event(
        conn,
        event_type="visit.supply_changed",
        aggregate_type="visit",
        aggregate_id=visit_id,
        identity=identity,
        origin="api:vat-tu",
        payload={
            "luot_vat_tu_id": dong_id,
            "hanh_dong": hanh_dong,
            "so_luong": so_luong,
            "don_gia": str(don_gia),
            **({"service_order_id": order_id} if order_id else {}),
            **({"ly_do": ly_do} if ly_do else {}),
        },
        correlation_id=visit_id,
    )


__all__ = [
    "QUYEN_VAT_TU",
    "SO_LUONG_TOI_DA",
    "VatTuService",
    "ghi_su_kien_vat_tu",
    "ly_do_khong_ban",
]
