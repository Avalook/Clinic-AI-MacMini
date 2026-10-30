"""KIỂM KÊ TIỀN MẶT ĐẦU CA – CUỐI CA (31/10/2026).

Gắn vào luồng Chốt ca có sẵn (cùng khoá: một cơ sở, một ngày, một ca; cùng cửa
quyền ``chot_so_ca_service.kiem_ca``). Khác ``kiem_ke_ca_service`` — đó là kiểm
kê HÀNG thuốc / vật tư.

* **Đầu ca**: thu ngân nhập QUỸ ĐẦU — gõ tổng, hoặc đếm theo mệnh giá (tổng do
  máy chủ cộng từ bảng đếm). Gợi ý = tiền ĐẾM CUỐI của ca trước đó (cùng cơ sở).
* **Cuối ca**: nhập tiền ĐẾM ĐƯỢC (cùng cách). Máy chủ tính
  ``du_kien = quy_dau + thực thu tiền mặt trong ca`` — thực thu tiền mặt lấy
  ĐÚNG dòng Tiền mặt của báo cáo cuối ca (``bao_cao_cuoi_ngay_service``: thu −
  huỷ − hoàn tiền mặt; ca đã chốt thì số lúc chốt) — rồi ``lech = đếm − dự
  kiến``. Lệch ≠ 0 bắt ghi lý do. Người nhận bàn giao tuỳ chọn.
* **Mở lại** sau khi đếm (bắt lý do) để đếm lại / sửa quỹ đầu; mọi lần ghi có
  vết ở ``ket_tien_mat_ca_lich_su`` (bản chụp + ai + lúc + lý do).

Postgres ép: một dòng mỗi ca, tổng khớp bảng đếm, dự kiến / lệch đúng công thức,
lệch ≠ 0 có lý do (mig 20261031125000). Hàm thuần có test không cần DB:
``tests/unit/test_ket_tien_mat.py``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.shifts import CAC_CA, NHAN_CA
from clinicai.core.tran import canh_bao_neu_day
from clinicai.services.audit import record_event
from clinicai.services.chot_so_ca_service import kiem_ca

#: Mệnh giá tiền mặt đếm được (đồng) — lớn trước.
MENH_GIA: tuple[int, ...] = (
    500_000,
    200_000,
    100_000,
    50_000,
    20_000,
    10_000,
    5_000,
    2_000,
    1_000,
)
_TOI_DA_TIEN = 100_000_000_000  # 100 tỷ — quá thì là gõ nhầm
_TOI_DA_TO = 1_000_000


def _so_nguyen(v: object) -> int | None:
    """Số nguyên ≥ 0 hữu hạn; bool / chuỗi / số lẻ / rác → None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, float) and (not math.isfinite(v) or v != int(v)):
        return None
    n = int(v)
    return n if n >= 0 else None


def doc_dem(tong: object, dem: object) -> tuple[int, dict[str, int] | None]:
    """(tổng, bảng đếm) của một lần nhập tiền. Thuần; rác → 422 câu dễ hiểu.

    Có bảng đếm ``{"500000": số tờ, …}`` → tổng = cộng bảng (gửi kèm tổng mà
    khác thì từ chối — không đoán bên nào đúng). Không có → tổng gõ tay."""
    if dem is not None:
        if not isinstance(dem, Mapping):
            raise ValidationError("Bảng đếm tiền không đúng dạng.")
        bang: dict[str, int] = {}
        for k, v in dem.items():
            try:
                mg = int(str(k))
            except ValueError:
                mg = -1
            if mg not in MENH_GIA:
                raise ValidationError(f"Mệnh giá không có: {k!r}.")
            so = _so_nguyen(v)
            if so is None or so > _TOI_DA_TO:
                raise ValidationError(
                    f"Số tờ {mg:,}đ phải là số nguyên từ 0 trở lên.".replace(",", ".")
                )
            if so:
                bang[str(mg)] = so
        cong = sum(int(k) * n for k, n in bang.items())
        if tong is not None and _so_nguyen(tong) != cong:
            raise ValidationError(
                f"Tổng gõ ({tong}) khác tổng bảng đếm ({cong:,}đ) — sửa cho khớp."
            )
        return cong, bang
    so = _so_nguyen(tong)
    if so is None or so > _TOI_DA_TIEN:
        raise ValidationError("Số tiền mặt phải là số nguyên từ 0 trở lên.")
    return so, None


def tien_mat_trong_ca(bc: Mapping[str, Any]) -> dict[str, int]:
    """Dòng Tiền mặt của báo cáo cuối ca → {thu, huy, hoan, thuc_thu}. Thuần.
    Không có dòng (chưa thu gì) → toàn 0."""
    o: Mapping[str, Any] = next(
        (r for r in bc.get("theo_hinh_thuc") or [] if r.get("ma") == "CASH"), {}
    )
    return {k: int(o.get(k) or 0) for k in ("thu", "huy", "hoan", "thuc_thu")}


def tinh_cuoi(quy_dau: int, thuc_thu_tm: int, dem_cuoi: int) -> dict[str, int]:
    """Dự kiến trong két và lệch. Thuần — cùng công thức Postgres ép."""
    du_kien = quy_dau + thuc_thu_tm
    return {"du_kien": du_kien, "lech": dem_cuoi - du_kien}


def doc_ly_do(raw: object, *, bat_buoc: bool, ten: str = "lý do") -> str | None:
    s = " ".join(raw.split()) if isinstance(raw, str) else ""
    if not s:
        if bat_buoc:
            raise ValidationError(f"Ghi {ten} (3–500 ký tự).")
        return None
    if not 3 <= len(s) <= 500:
        raise ValidationError(f"{ten.capitalize()}: 3–500 ký tự.")
    return s


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def _json(v: Any) -> Any:
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return str(v)


def _ra(r: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = {k: _iso(v) for k, v in dict(r).items()}
    for k in ("quy_dau_dem", "dem_cuoi_dem"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    d["ten_ca"] = NHAN_CA.get(str(d.get("ca")), d.get("ca"))
    d["da_dem"] = d.get("dem_cuoi") is not None
    return d


_COT = """
SELECT k.id::text AS id, k.location_id::text AS location_id, l.name AS ten_co_so,
       k.ngay, k.ca, k.quy_dau, k.quy_dau_dem, k.quy_dau_luc,
       qd.full_name AS quy_dau_boi_ten,
       k.dem_cuoi, k.dem_cuoi_dem, k.thu_tien_mat, k.du_kien, k.lech, k.ly_do_lech,
       k.nguoi_nhan, k.dem_luc, dm.full_name AS dem_boi_ten
  FROM public.ket_tien_mat_ca k
  LEFT JOIN public.clinic_location l
    ON l.id = k.location_id AND l.clinic_id = k.clinic_id
  LEFT JOIN public.staff qd ON qd.id = k.quy_dau_boi
  LEFT JOIN public.staff dm ON dm.id = k.dem_boi
"""
_MOT_SQL = (
    _COT + " WHERE k.clinic_id = $1::uuid AND k.location_id = $2::uuid"
    " AND k.ngay = $3 AND k.ca = $4"
)
_THU_TU_CA = "CASE k.ca WHEN 'SANG' THEN 0 WHEN 'CHIEU' THEN 1 ELSE 2 END"
#: Ca gần nhất TRƯỚC (ngày, ca) của cùng cơ sở mà đã đếm cuối — gợi ý quỹ đầu.
_GOI_Y_SQL = (
    _COT
    + f""" WHERE k.clinic_id = $1::uuid AND k.location_id = $2::uuid
   AND k.dem_cuoi IS NOT NULL
   AND (k.ngay < $3 OR (k.ngay = $3 AND {_THU_TU_CA} < $4))
 ORDER BY k.ngay DESC, {_THU_TU_CA} DESC
 LIMIT 1"""
)
#: Báo cáo cuối ngày: các ca trong khoảng (lọc cơ sở / ca nếu có).
_NGAY_SQL = (
    _COT
    + f""" WHERE k.clinic_id = $1::uuid AND k.ngay BETWEEN $2 AND $3
   AND ($4::uuid IS NULL OR k.location_id = $4::uuid)
   AND ($5::text IS NULL OR k.ca = $5)
 ORDER BY k.ngay, l.name, {_THU_TU_CA}
 LIMIT 500"""
)
_LICH_SU_SQL = """
SELECT h.hanh_dong, h.ban_chup, h.ly_do, h.luc, s.full_name AS boi_ten
  FROM public.ket_tien_mat_ca_lich_su h
  LEFT JOIN public.staff s ON s.id = h.boi
 WHERE h.clinic_id = $1::uuid AND h.ket_id = $2::uuid
 ORDER BY h.id
"""


async def doc_ket_trong_khoang(
    conn: asyncpg.Connection,
    clinic_id: str,
    tu: date,
    den: date,
    *,
    co_so: str | None,
    ca: str | None,
) -> list[dict[str, Any]]:
    """Khối "Tiền mặt két" của báo cáo cuối ngày: quỹ đầu / dự kiến / đếm / lệch
    từng ca đã nhập (dự kiến + lệch là số CHỤP lúc đếm cuối)."""
    rows = await conn.fetch(_NGAY_SQL, clinic_id, tu, den, co_so, ca)
    canh_bao_neu_day("bao_cao_cuoi_ngay.ket_tien_mat", len(rows), 500, tu=tu, den=den)
    return [r for r in (_ra(x) for x in rows) if r is not None]


def tong_ket(ds: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Cộng các ca đã đếm (dòng Tổng của khối két). Thuần."""
    da = [r for r in ds if r.get("da_dem")]
    return {
        "so_ca": len(da),
        **{
            k: sum(int(r.get(k) or 0) for r in da)
            for k in ("quy_dau", "thu_tien_mat", "du_kien", "dem_cuoi", "lech")
        },
    }


class KetTienMatService:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _tien_mat_song(
        self, identity: StaffIdentity, d: date, ma: str, cs: str
    ) -> dict[str, int]:
        from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService

        bc = await BaoCaoCuoiNgayService(self._pool).bao_cao(
            identity=identity, tu=d.isoformat(), den=d.isoformat(), co_so=cs, ca=ma
        )
        return tien_mat_trong_ca(bc)

    async def xem(
        self, *, identity: StaffIdentity, ngay: object, ca: object, co_so: object
    ) -> dict[str, Any]:
        """Két của đúng một ca: dòng đã nhập + tiền mặt trong ca (số sống) + dự
        kiến hiện tại + gợi ý quỹ đầu + vết."""
        d, ma, cs, _ = await kiem_ca(self._pool, identity, ngay, ca, co_so)
        tm = await self._tien_mat_song(identity, d, ma, cs)
        async with self._pool.acquire() as conn:
            ket = _ra(await conn.fetchrow(_MOT_SQL, identity.clinic_id, cs, d, ma))
            goi_y = _ra(
                await conn.fetchrow(
                    _GOI_Y_SQL, identity.clinic_id, cs, d, CAC_CA.index(ma)
                )
            )
            lich_su = (
                [
                    {
                        "hanh_dong": r["hanh_dong"],
                        "ban_chup": json.loads(r["ban_chup"])
                        if isinstance(r["ban_chup"], str)
                        else r["ban_chup"],
                        "ly_do": r["ly_do"],
                        "luc": _iso(r["luc"]),
                        "boi": r["boi_ten"],
                    }
                    for r in await conn.fetch(
                        _LICH_SU_SQL, identity.clinic_id, ket["id"]
                    )
                ]
                if ket
                else []
            )
        return {
            "ngay": d.isoformat(),
            "ca": ma,
            "ten_ca": NHAN_CA[ma],
            "co_so": cs,
            "menh_gia": list(MENH_GIA),
            "ket": ket,
            "tien_mat": tm,
            # Dự kiến NẾU đếm ngay bây giờ (quỹ đầu + thực thu TM hiện tại).
            "du_kien_song": (int(ket["quy_dau"]) + tm["thuc_thu"]) if ket else None,
            "goi_y_quy_dau": (
                {
                    "so_tien": goi_y["dem_cuoi"],
                    "ngay": goi_y["ngay"],
                    "ca": goi_y["ca"],
                    "ten_ca": goi_y["ten_ca"],
                }
                if goi_y
                else None
            ),
            "lich_su": lich_su,
        }

    async def _ghi_vet(
        self,
        conn: asyncpg.Connection,
        identity: StaffIdentity,
        ket_id: str,
        hanh_dong: str,
        ban_chup: Mapping[str, Any] | None,
        ly_do: str | None,
        *,
        event_type: str,
    ) -> None:
        await conn.execute(
            "INSERT INTO public.ket_tien_mat_ca_lich_su"
            " (clinic_id, ket_id, hanh_dong, ban_chup, ly_do, boi)"
            " VALUES ($1::uuid, $2::uuid, $3, $4::jsonb, $5, $6::uuid)",
            identity.clinic_id,
            ket_id,
            hanh_dong,
            json.dumps(dict(ban_chup or {}), default=_json, ensure_ascii=False),
            ly_do,
            identity.staff_id,
        )
        await record_event(
            conn,
            event_type=event_type,
            aggregate_type="ket_tien_mat_ca",
            aggregate_id=ket_id,
            identity=identity,
            origin="api:reports-ket-tien-mat",
            payload={"hanh_dong": hanh_dong, "ly_do": ly_do},
        )

    async def quy_dau(
        self,
        *,
        identity: StaffIdentity,
        ngay: object,
        ca: object,
        co_so: object,
        tong: object = None,
        dem: object = None,
        ly_do: object = None,
    ) -> dict[str, Any]:
        """Nhập quỹ đầu ca; đã có thì SỬA (bắt lý do). Đã đếm cuối → mở lại trước."""
        d, ma, cs, _ = await kiem_ca(self._pool, identity, ngay, ca, co_so)
        so, bang = doc_dem(tong, dem)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            moi = await conn.fetchval(
                """
                INSERT INTO public.ket_tien_mat_ca
                    (clinic_id, location_id, ngay, ca, quy_dau, quy_dau_dem,
                     quy_dau_boi)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, $7::uuid)
                ON CONFLICT (clinic_id, location_id, ngay, ca) DO NOTHING
                RETURNING id::text
                """,
                cid,
                cs,
                d,
                ma,
                so,
                json.dumps(bang) if bang is not None else None,
                identity.staff_id,
            )
            if moi is not None:
                ket_id, hanh_dong, ly = moi, "QUY_DAU", None
            else:
                cu = await conn.fetchrow(
                    "SELECT id::text AS id, quy_dau, dem_cuoi"
                    " FROM public.ket_tien_mat_ca"
                    " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
                    " AND ngay = $3 AND ca = $4 FOR UPDATE",
                    cid,
                    cs,
                    d,
                    ma,
                )
                assert cu is not None
                if cu["dem_cuoi"] is not None:
                    raise ConflictError(
                        "Ca này đã đếm cuối ca — bấm “Mở lại” (ghi lý do) rồi mới sửa"
                        " quỹ đầu."
                    )
                ly = doc_ly_do(ly_do, bat_buoc=True, ten="lý do sửa quỹ đầu")
                await conn.execute(
                    "UPDATE public.ket_tien_mat_ca SET quy_dau = $2,"
                    " quy_dau_dem = $3::jsonb, quy_dau_boi = $4::uuid,"
                    " quy_dau_luc = now() WHERE id = $1::uuid",
                    cu["id"],
                    so,
                    json.dumps(bang) if bang is not None else None,
                    identity.staff_id,
                )
                ket_id, hanh_dong = cu["id"], "SUA_QUY_DAU"
            ban = await conn.fetchrow(_MOT_SQL, cid, cs, d, ma)
            await self._ghi_vet(
                conn,
                identity,
                ket_id,
                hanh_dong,
                _ra(ban),
                ly,
                # Nhập hay sửa: `hanh_dong` trong payload.
                event_type="report.cash_drawer_float_saved",
            )
        return {"ok": True, "id": ket_id, "quy_dau": so}

    async def dem_cuoi(
        self,
        *,
        identity: StaffIdentity,
        ngay: object,
        ca: object,
        co_so: object,
        tong: object = None,
        dem: object = None,
        ly_do_lech: object = None,
        nguoi_nhan: object = None,
    ) -> dict[str, Any]:
        """Kiểm kê cuối ca: đếm được bao nhiêu → dự kiến, lệch (máy chủ tính)."""
        d, ma, cs, _ = await kiem_ca(self._pool, identity, ngay, ca, co_so)
        so, bang = doc_dem(tong, dem)
        nhan = (
            " ".join(nguoi_nhan.split())[:120]
            if isinstance(nguoi_nhan, str) and nguoi_nhan.strip()
            else None
        )
        tm = await self._tien_mat_song(identity, d, ma, cs)
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            cu = await conn.fetchrow(
                "SELECT id::text AS id, quy_dau, dem_cuoi"
                " FROM public.ket_tien_mat_ca"
                " WHERE clinic_id = $1::uuid AND location_id = $2::uuid"
                " AND ngay = $3 AND ca = $4 FOR UPDATE",
                cid,
                cs,
                d,
                ma,
            )
            if cu is None:
                raise ValidationError("Nhập quỹ đầu ca trước khi kiểm kê cuối ca.")
            if cu["dem_cuoi"] is not None:
                raise ConflictError(
                    "Ca này vừa được kiểm kê cuối ca — tải lại; muốn đếm lại thì"
                    " bấm “Mở lại”."
                )
            so_lieu = tinh_cuoi(int(cu["quy_dau"]), tm["thuc_thu"], so)
            ly = doc_ly_do(
                ly_do_lech, bat_buoc=so_lieu["lech"] != 0, ten="lý do lệch tiền"
            )
            await conn.execute(
                """
                UPDATE public.ket_tien_mat_ca
                   SET dem_cuoi = $2, dem_cuoi_dem = $3::jsonb, thu_tien_mat = $4,
                       du_kien = $5, lech = $6, ly_do_lech = $7, nguoi_nhan = $8,
                       dem_boi = $9::uuid, dem_luc = now()
                 WHERE id = $1::uuid
                """,
                cu["id"],
                so,
                json.dumps(bang) if bang is not None else None,
                tm["thuc_thu"],
                so_lieu["du_kien"],
                so_lieu["lech"],
                ly,
                nhan,
                identity.staff_id,
            )
            ban = await conn.fetchrow(_MOT_SQL, cid, cs, d, ma)
            await self._ghi_vet(
                conn,
                identity,
                cu["id"],
                "DEM_CUOI",
                _ra(ban),
                ly,
                event_type="report.cash_drawer_counted",
            )
        return {"ok": True, "id": cu["id"], **so_lieu, "thu_tien_mat": tm["thuc_thu"]}

    async def mo_lai(
        self,
        *,
        identity: StaffIdentity,
        ngay: object,
        ca: object,
        co_so: object,
        ly_do: object,
    ) -> dict[str, Any]:
        """Mở lại két đã đếm để đếm lại / sửa quỹ đầu. Số cũ giữ trong vết."""
        d, ma, cs, _ = await kiem_ca(self._pool, identity, ngay, ca, co_so)
        ly = doc_ly_do(ly_do, bat_buoc=True, ten="lý do mở lại")
        cid = identity.clinic_id
        async with self._pool.acquire() as conn, conn.transaction():
            truoc = await conn.fetchrow(_MOT_SQL + " FOR UPDATE OF k", cid, cs, d, ma)
            if truoc is None or truoc["dem_cuoi"] is None:
                raise ConflictError(
                    "Ca này chưa kiểm kê cuối ca — không có gì để mở lại."
                )
            await conn.execute(
                """
                UPDATE public.ket_tien_mat_ca
                   SET dem_cuoi = NULL, dem_cuoi_dem = NULL, thu_tien_mat = NULL,
                       du_kien = NULL, lech = NULL, ly_do_lech = NULL,
                       nguoi_nhan = NULL, dem_boi = NULL, dem_luc = NULL
                 WHERE id = $1::uuid
                """,
                truoc["id"],
            )
            # Bản chụp TRƯỚC khi mở: số đếm cũ không mất.
            await self._ghi_vet(
                conn,
                identity,
                truoc["id"],
                "MO_LAI",
                _ra(truoc),
                ly,
                event_type="report.cash_drawer_reopened",
            )
        return {"ok": True, "id": truoc["id"]}


__all__ = [
    "MENH_GIA",
    "KetTienMatService",
    "doc_dem",
    "doc_ket_trong_khoang",
    "tien_mat_trong_ca",
    "tinh_cuoi",
    "tong_ket",
]
