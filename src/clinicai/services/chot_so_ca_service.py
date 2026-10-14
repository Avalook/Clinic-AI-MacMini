"""KHOÁ SỔ THEO CA (G4c — Tuyền chốt A, 14/10/2026).

Trước: báo cáo ca / ngày tính lại từ dữ liệu sống mỗi lần mở — huỷ phiếu hôm
sau trừ LÙI vào ngày thu cũ (báo cáo hôm qua in 10tr, hôm nay mở lại còn 9,2tr).

Nay:
  * **Chốt ca** (một cơ sở, một ngày, một ca): chụp lại toàn bộ báo cáo cuối ca
    lúc bấm (`chot_so_ca.so_lieu`). Xem đúng ca ấy về sau → trả bản chụp, kèm số
    "phát sinh sau khi chốt" để không gì bị giấu.
  * **Sau chốt**, huỷ phiếu / hoàn tác lần thu của ca ấy tính vào CA ĐANG LÀM
    (nhãn "điều chỉnh ca trước") — `bao_cao_cuoi_ngay_service` đọc khoá ở đây.
    Hoàn tiền, sổ nợ, xác minh CK muộn vốn đã tính theo lúc làm.
  * **Mở khoá**: Quản lý, bắt lý do, giữ dấu (không xoá, không sửa số chụp);
    mở xong chốt lại được. Luật "không khoá cứng".

Ai chốt được: ai xem được TÀI CHÍNH của đúng ca / cơ sở ấy (cùng cửa
``ReportAccessService.authorize``). Không tự chốt theo giờ — ca chưa chốt
giữ nguyên cách tính cũ.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.audit import record_event
from clinicai.services.co_so_bao_cao import KHONG_KHOP, doc_co_so
from clinicai.services.report_access_service import (
    ReportAccessService,
    ngay_hop_le,
)

#: Ca của giờ thu ``{luc}`` (cơ sở ``{co_so}``) ĐÃ CHỐT TRƯỚC giờ huỷ ``{moc}`` và
#: chưa mở khoá cho tới lúc huỷ. Xét theo TRẠNG THÁI TẠI GIỜ HUỶ, không theo
#: trạng thái hiện tại (soát #431, 14/10): khoản huỷ đã chuyển sang ca đang làm
#: thì ở yên đó dù ca cũ được mở khoá sau này — nếu không, ca cũ nhận lại khoản
#: huỷ trong khi bản chụp ca kia vẫn mang nó (hai bản cùng trừ một phiếu).
#: Huỷ xảy ra LÚC đang mở khoá (chốt ← mở ← huỷ) thì thuộc ca gốc như chưa từng chốt.
#: Một ca có thể chốt-mở-chốt nhiều lần: chỉ cần MỘT lần chốt phủ giờ huỷ.
KHOA_TRUOC_SQL = """
EXISTS (SELECT 1 FROM public.chot_so_ca k
         WHERE k.clinic_id = {clinic} AND k.location_id = {co_so}
           AND k.tu_luc <= {luc} AND {luc} < k.den_luc
           AND k.chot_luc < {moc}
           AND (k.mo_luc IS NULL OR k.mo_luc > {moc}))
"""

_KHOA_SQL = """
SELECT k.id::text AS id, k.ngay, k.ca, k.tu_luc, k.den_luc, k.chot_luc,
       k.so_lieu, k.ghi_chu, s.full_name AS chot_boi_ten
  FROM public.chot_so_ca k
  LEFT JOIN public.staff s ON s.id = k.chot_boi
 WHERE k.clinic_id = $1::uuid AND k.location_id = $2::uuid
   AND k.ngay = $3 AND k.ca = $4 AND k.mo_luc IS NULL
"""


def _json(v: Any) -> Any:
    """Bản chụp báo cáo → JSON giữ số là số (Decimal → int/float)."""
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    raise TypeError(f"không chụp được kiểu {type(v).__name__}")


def thong_tin_khoa(r: asyncpg.Record | dict[str, Any] | None) -> dict[str, Any] | None:
    """Phần "đã chốt" gắn vào báo cáo / trạng thái. Thuần."""
    if r is None:
        return None
    return {
        "id": r["id"],
        "ngay": r["ngay"].isoformat() if isinstance(r["ngay"], date) else r["ngay"],
        "ca": r["ca"],
        "chot_luc": (
            r["chot_luc"].isoformat()
            if isinstance(r["chot_luc"], datetime)
            else r["chot_luc"]
        ),
        "chot_boi": r.get("chot_boi_ten") if hasattr(r, "get") else None,
        "ghi_chu": r["ghi_chu"],
    }


async def khoa_dang_co(
    conn: asyncpg.Connection, clinic_id: str, co_so: str, ngay: date, ca: str
) -> asyncpg.Record | None:
    return await conn.fetchrow(_KHOA_SQL, clinic_id, co_so, ngay, ca)


def _so_lieu(r: asyncpg.Record) -> dict[str, Any]:
    v = r["so_lieu"]
    return json.loads(v) if isinstance(v, str) else dict(v)


def chenh_sau_chot(chup: dict[str, Any], song: dict[str, Any]) -> dict[str, int]:
    """Số "phát sinh sau khi chốt" của đúng ca: sống − chụp (thu / huỷ / hoàn /
    thực thu). Toàn 0 = không có gì sau chốt. Thuần."""
    a = chup.get("tong") or {}
    b = song.get("tong") or {}
    return {
        k: int(b.get(k) or 0) - int(a.get(k) or 0)
        for k in ("thu", "huy", "hoan", "thuc_thu")
    }


class ChotSoCaService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _kiem(
        self, identity: StaffIdentity, ngay: object, ca: object, co_so: object
    ) -> tuple[date, str, str, dict[str, Any]]:
        d = ngay_hop_le(ngay if isinstance(ngay, str) else None)
        if d is None:
            raise ValidationError("Chọn đúng ngày của ca cần chốt (YYYY-MM-DD).")
        ma = str(ca or "").strip().upper()
        if ma not in ("SANG", "CHIEU", "TOI"):
            raise ValidationError("Chọn ca cần chốt: sáng, chiều hoặc tối.")
        cs = doc_co_so(co_so)
        if cs is None or cs == KHONG_KHOP:
            raise ValidationError("Chọn một cơ sở để chốt ca — mỗi cơ sở chốt riêng.")
        access, chon = await ReportAccessService(self._pool).authorize(
            identity, tu=d.isoformat(), den=d.isoformat(), ca=ma, co_so=cs
        )
        if not access["tai_chinh"] or chon != cs:
            raise SafetyGateError(
                "Bạn chưa được xem tài chính của ca này nên không chốt / mở khoá được."
            )
        return d, ma, cs, access

    async def trang_thai(
        self, *, identity: StaffIdentity, ngay: object, ca: object, co_so: object
    ) -> dict[str, Any]:
        d, ma, cs, _ = await self._kiem(identity, ngay, ca, co_so)
        async with self._pool.acquire() as conn:
            k = await khoa_dang_co(conn, identity.clinic_id, cs, d, ma)
        return {
            "khoa": thong_tin_khoa(k),
            "mo_khoa_duoc": ReportAccessService.quan_ly(identity),
        }

    async def chot(
        self,
        *,
        identity: StaffIdentity,
        ngay: object,
        ca: object,
        co_so: object,
        ghi_chu: object = None,
    ) -> dict[str, Any]:
        from clinicai.services.bao_cao_cuoi_ngay_service import (
            BaoCaoCuoiNgayService,
            khung_ca,
        )

        d, ma, cs, _ = await self._kiem(identity, ngay, ca, co_so)
        gc = (
            ghi_chu.strip()[:500]
            if isinstance(ghi_chu, str) and ghi_chu.strip()
            else None
        )
        async with self._pool.acquire() as conn:
            if await khoa_dang_co(conn, identity.clinic_id, cs, d, ma) is not None:
                raise ConflictError(
                    "Ca này đã chốt rồi — xem số đã chốt, hoặc nhờ Quản lý mở khoá."
                )
            settings = await conn.fetchval(
                "SELECT settings FROM public.clinic WHERE id = $1::uuid",
                identity.clinic_id,
            )
        khung = khung_ca(d, ma, settings)
        if khung is None:
            raise ValidationError("Phòng khám chưa cài giờ ca này — không chốt được.")
        # Chụp ĐÚNG báo cáo mà người xem ca này thấy (cả dịch vụ + thuốc).
        bc = await BaoCaoCuoiNgayService(self._pool).bao_cao(
            identity=identity, tu=d.isoformat(), den=d.isoformat(), co_so=cs, ca=ma
        )
        so_lieu = json.dumps(bc, default=_json, ensure_ascii=False)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                try:
                    kid = await conn.fetchval(
                        """
                        INSERT INTO public.chot_so_ca
                            (clinic_id, location_id, ngay, ca, tu_luc, den_luc,
                             chot_boi, so_lieu, ghi_chu)
                        VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid,
                                $8::jsonb, $9)
                        RETURNING id::text
                        """,
                        identity.clinic_id,
                        cs,
                        d,
                        ma,
                        khung[0],
                        khung[1],
                        identity.staff_id,
                        so_lieu,
                        gc,
                    )
                except asyncpg.UniqueViolationError:
                    # Hai người bấm cùng lúc — Postgres giữ đúng một lần chốt.
                    raise ConflictError(
                        "Ca này vừa được người khác chốt — tải lại để xem số đã chốt."
                    ) from None
                await record_event(
                    conn,
                    event_type="report.shift_closed",
                    aggregate_type="chot_so_ca",
                    aggregate_id=str(kid),
                    identity=identity,
                    origin="api:reports-chot-ca",
                    payload={
                        "ngay": d.isoformat(),
                        "ca": ma,
                        "co_so": cs,
                        "thuc_thu": int((bc.get("tong") or {}).get("thuc_thu") or 0),
                        "ghi_chu": gc,
                    },
                )
        return {"ok": True, "id": kid, "ngay": d.isoformat(), "ca": ma}

    async def mo_khoa(
        self, *, identity: StaffIdentity, chot_id: object, ly_do: object
    ) -> dict[str, Any]:
        if not ReportAccessService.quan_ly(identity):
            raise SafetyGateError("Chỉ Quản lý mở khoá được ca đã chốt.")
        ly = ly_do.strip() if isinstance(ly_do, str) else ""
        if not 3 <= len(ly) <= 500:
            raise ValidationError("Mở khoá ca thì ghi lý do (3–500 ký tự).")
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                try:
                    r = await conn.fetchrow(
                        """
                        UPDATE public.chot_so_ca
                           SET mo_luc = now(), mo_boi = $3::uuid, ly_do_mo = $4
                         WHERE clinic_id = $1::uuid AND id = $2::uuid
                           AND mo_luc IS NULL
                        RETURNING id::text, ngay, ca, location_id::text
                        """,
                        identity.clinic_id,
                        str(chot_id),
                        identity.staff_id,
                        ly,
                    )
                except asyncpg.DataError:
                    raise NotFoundError("Không tìm thấy lần chốt ca này.") from None
                if r is None:
                    raise NotFoundError(
                        "Không tìm thấy lần chốt còn hiệu lực — có thể đã mở khoá rồi."
                    )
                await record_event(
                    conn,
                    event_type="report.shift_reopened",
                    aggregate_type="chot_so_ca",
                    aggregate_id=r["id"],
                    identity=identity,
                    origin="api:reports-chot-ca",
                    payload={
                        "ngay": r["ngay"].isoformat(),
                        "ca": r["ca"],
                        "co_so": r["location_id"],
                        "ly_do": ly,
                    },
                )
        return {"ok": True, "id": r["id"]}


__all__ = [
    "KHOA_TRUOC_SQL",
    "ChotSoCaService",
    "chenh_sau_chot",
    "khoa_dang_co",
    "thong_tin_khoa",
]
