"""Kiểm kê vật tư đầu/cuối ca theo phòng, chụp số sổ khi chốt."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.clock import hom_nay_vn
from clinicai.core.tran import canh_bao_neu_day

CAC_CA = frozenset({"SANG", "CHIEU", "TOI"})
CAC_LOAI = frozenset({"DAU", "CUOI", "DOT_XUAT"})
SO_DEM_TOI_DA = Decimal(1_000_000)
Q3 = Decimal("0.001")


def so_dem(raw: Any, *, rong_duoc: bool = False) -> Decimal | None:
    """Chuẩn hoá số đếm; cho phép rỗng khi người dùng chưa đếm dòng đó."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if rong_duoc:
            return None
        raise ValidationError("Nhập số đếm thực tế.")
    if isinstance(raw, bool):
        raise ValidationError("Số đếm phải là số không âm, tối đa 3 chữ số thập phân.")
    try:
        value = Decimal(str(raw).strip().replace(",", "."))
    except (DecimalException, InvalidOperation, ValueError) as exc:
        raise ValidationError("Số đếm phải là số hợp lệ.") from exc
    if (
        not value.is_finite()
        or value < 0
        or value > SO_DEM_TOI_DA
        or value != value.quantize(Q3)
    ):
        raise ValidationError("Số đếm phải từ 0 đến 1.000.000, tối đa 3 số lẻ.")
    return value.quantize(Q3)


def tinh_lech(ton_may: Decimal, dem: Decimal) -> Decimal:
    """Lệch = số đếm thực tế − tồn sổ tại thời điểm chốt."""
    return dem - ton_may


def _uuid(raw: Any) -> str:
    try:
        return str(UUID(str(raw)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Mã phòng/vật tư/phiếu không hợp lệ.") from exc


def _ngay(raw: Any) -> date:
    try:
        value = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
    except (ValueError, TypeError) as exc:
        raise ValidationError("Ngày kiểm kê không hợp lệ (cần YYYY-MM-DD).") from exc
    today = hom_nay_vn()
    if value < today - timedelta(days=366) or value > today + timedelta(days=1):
        raise ValidationError(
            "Ngày kiểm kê chỉ nhận trong một năm gần đây tới ngày mai."
        )
    return value


def _tham_so(ngay: Any, ca: Any, loai: Any) -> tuple[date, str, str]:
    d = _ngay(ngay)
    c = str(ca or "").strip().upper()
    kind = str(loai or "").strip().upper()
    if c not in CAC_CA or kind not in CAC_LOAI:
        raise ValidationError("Chọn đúng ngày, ca và loại kiểm kê.")
    return d, c, kind


async def _khoa_co_so(conn: asyncpg.Connection, identity: StaffIdentity) -> None:
    """Dùng cùng advisory lock với mọi phiếu kho để chụp tồn nhất quán."""
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
        f"vat_tu:{identity.clinic_id}:{identity.location_id}",
    )


async def _phieu_json(
    conn: asyncpg.Connection, identity: StaffIdentity, phieu_id: str
) -> dict[str, Any]:
    header = await conn.fetchrow(
        "SELECT k.id::text, k.location_id::text, k.room_id::text, r.name AS phong,"
        " k.ngay, k.ca, k.loai, k.trang_thai, k.tao_boi::text, k.tao_luc,"
        " k.chot_boi::text, k.chot_luc, k.mot_phan"
        " FROM public.vat_tu_kiem_ke_ca k"
        " JOIN public.clinic_room r ON r.id=k.room_id AND r.clinic_id=k.clinic_id"
        " WHERE k.id=$1::uuid AND k.clinic_id=$2::uuid AND k.location_id=$3::uuid",
        phieu_id,
        identity.clinic_id,
        identity.location_id,
    )
    if not header:
        raise NotFoundError("Không tìm thấy phiếu kiểm kê của phòng này.")
    rows = await conn.fetch(
        "SELECT d.vat_tu_id::text, s.name AS ten, s.don_vi, d.dem, d.ton_may, d.lech"
        " FROM public.vat_tu_kiem_ke_ca_dong d"
        " JOIN public.service_price s ON s.id=d.vat_tu_id AND s.clinic_id=d.clinic_id"
        " WHERE d.kiem_ke_ca_id=$1::uuid AND d.clinic_id=$2::uuid"
        " ORDER BY s.name, d.vat_tu_id",
        phieu_id,
        identity.clinic_id,
    )
    result = dict(header)
    result["ngay"] = header["ngay"].isoformat()
    result["so_dong"] = len(rows)
    result["so_da_dem"] = sum(row["dem"] is not None for row in rows)
    result["so_lech"] = sum(
        row["lech"] is not None and row["lech"] != 0 for row in rows
    )
    result["dong"] = [dict(row) for row in rows]
    return result


async def danh_sach(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    ngay: Any,
    room_id: Any,
) -> list[dict[str, Any]]:
    d = _ngay(ngay)
    room = _uuid(room_id)
    rows = await pool.fetch(
        "SELECT k.id::text, k.ngay, k.ca, k.loai, k.trang_thai, k.room_id::text,"
        " r.name AS phong, k.tao_luc, k.chot_luc, k.mot_phan,"
        " count(x.id)::int AS so_dong, count(x.dem)::int AS so_da_dem,"
        " count(*) FILTER (WHERE x.lech IS NOT NULL AND x.lech<>0)::int AS so_lech"
        " FROM public.vat_tu_kiem_ke_ca k"
        " JOIN public.clinic_room r ON r.id=k.room_id AND r.clinic_id=k.clinic_id"
        " LEFT JOIN public.vat_tu_kiem_ke_ca_dong x"
        " ON x.kiem_ke_ca_id=k.id AND x.clinic_id=k.clinic_id"
        " WHERE k.clinic_id=$1::uuid AND k.location_id=$2::uuid"
        " AND k.room_id=$3::uuid AND k.ngay=$4"
        " GROUP BY k.id, r.name ORDER BY k.ca, k.loai, k.tao_luc DESC LIMIT 100",
        identity.clinic_id,
        identity.location_id,
        room,
        d,
    )
    canh_bao_neu_day(
        "vat_tu_kiem_ke_ca",
        len(rows),
        100,
        clinic_id=identity.clinic_id,
        location_id=identity.location_id,
        room_id=room,
        ngay=d.isoformat(),
    )
    return [{**dict(row), "ngay": row["ngay"].isoformat()} for row in rows]


async def mo_phieu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    room_id: Any,
    ngay: Any,
    ca: Any,
    loai: Any,
) -> dict[str, Any]:
    room = _uuid(room_id)
    d, shift, kind = _tham_so(ngay, ca, loai)
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        valid_room = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM public.clinic_room WHERE id=$1::uuid"
            " AND clinic_id=$2::uuid AND location_id=$3::uuid AND is_active)",
            room,
            identity.clinic_id,
            identity.location_id,
        )
        if not valid_room:
            raise NotFoundError("Không tìm thấy phòng đang hoạt động tại cơ sở này.")
        existing = (
            await conn.fetchval(
                "SELECT id::text FROM public.vat_tu_kiem_ke_ca WHERE clinic_id=$1::uuid"
                " AND location_id=$2::uuid AND room_id=$3::uuid AND ngay=$4"
                " AND ca=$5 AND loai=$6 AND loai IN ('DAU','CUOI')",
                identity.clinic_id,
                identity.location_id,
                room,
                d,
                shift,
                kind,
            )
            if kind in {"DAU", "CUOI"}
            else None
        )
        if existing:
            return await _phieu_json(conn, identity, existing)
        row = await conn.fetchrow(
            "INSERT INTO public.vat_tu_kiem_ke_ca"
            " (clinic_id,location_id,room_id,ngay,ca,loai,tao_boi)"
            " VALUES ($1::uuid,$2::uuid,$3::uuid,$4,$5,$6,$7::uuid)"
            " RETURNING id::text",
            identity.clinic_id,
            identity.location_id,
            room,
            d,
            shift,
            kind,
            identity.staff_id,
        )
        pid = row["id"]
        await conn.execute(
            "INSERT INTO public.vat_tu_kiem_ke_ca_dong"
            " (clinic_id,kiem_ke_ca_id,ton_id,vat_tu_id)"
            " SELECT $1::uuid,$2::uuid,t.id,t.vat_tu_id"
            " FROM public.vat_tu_ton t JOIN public.service_price s"
            " ON s.id=t.vat_tu_id AND s.clinic_id=t.clinic_id AND s.\"group\"='vat_tu'"
            " WHERE t.clinic_id=$1::uuid AND t.location_id=$3::uuid"
            " AND t.room_id=$4::uuid"
            " ON CONFLICT (kiem_ke_ca_id,ton_id) DO NOTHING",
            identity.clinic_id,
            pid,
            identity.location_id,
            room,
        )
        return await _phieu_json(conn, identity, pid)


async def doc_phieu(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    pid = _uuid(phieu_id)
    async with pool.acquire() as conn:
        return await _phieu_json(conn, identity, pid)


async def luu_dem(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    phieu_id: Any,
    dong: list[dict[str, Any]],
) -> dict[str, Any]:
    pid = _uuid(phieu_id)
    if len(dong) > 500:
        raise ValidationError("Một lần lưu tối đa 500 dòng kiểm kê.")
    parsed: list[tuple[str, Decimal | None]] = []
    for item in dong:
        vat_tu = _uuid(item.get("vat_tu_id"))
        dem = so_dem(item.get("dem"), rong_duoc=True)
        if dem is not None:
            parsed.append((vat_tu, dem))
    if len({v for v, _ in parsed}) != len(parsed):
        raise ValidationError("Mỗi vật tư chỉ được có một số đếm trong phiếu.")
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        header = await conn.fetchrow(
            "SELECT trang_thai FROM public.vat_tu_kiem_ke_ca WHERE id=$1::uuid"
            " AND clinic_id=$2::uuid AND location_id=$3::uuid FOR UPDATE",
            pid,
            identity.clinic_id,
            identity.location_id,
        )
        if not header:
            raise NotFoundError("Không tìm thấy phiếu kiểm kê của phòng này.")
        if header["trang_thai"] != "NHAP":
            raise ConflictError("Phiếu đã chốt; mở phiếu đính chính để sửa số đếm.")
        if parsed:
            allowed = await conn.fetch(
                "SELECT vat_tu_id::text FROM public.vat_tu_kiem_ke_ca_dong"
                " WHERE kiem_ke_ca_id=$1::uuid AND clinic_id=$2::uuid"
                " AND vat_tu_id=ANY($3::uuid[])",
                pid,
                identity.clinic_id,
                [v for v, _ in parsed],
            )
            if {r["vat_tu_id"] for r in allowed} != {v for v, _ in parsed}:
                raise NotFoundError("Vật tư không thuộc phòng trong phiếu kiểm kê.")
        await conn.execute(
            "UPDATE public.vat_tu_kiem_ke_ca_dong SET dem=NULL"
            " WHERE kiem_ke_ca_id=$1::uuid AND clinic_id=$2::uuid",
            pid,
            identity.clinic_id,
        )
        for vat_tu, dem in parsed:
            await conn.execute(
                "UPDATE public.vat_tu_kiem_ke_ca_dong SET dem=$4"
                " WHERE kiem_ke_ca_id=$1::uuid AND clinic_id=$2::uuid"
                " AND vat_tu_id=$3::uuid",
                pid,
                identity.clinic_id,
                vat_tu,
                dem,
            )
        return await _phieu_json(conn, identity, pid)


async def chot(
    pool: asyncpg.Pool, *, identity: StaffIdentity, phieu_id: Any
) -> dict[str, Any]:
    pid = _uuid(phieu_id)
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        header = await conn.fetchrow(
            "SELECT trang_thai FROM public.vat_tu_kiem_ke_ca WHERE id=$1::uuid"
            " AND clinic_id=$2::uuid AND location_id=$3::uuid FOR UPDATE",
            pid,
            identity.clinic_id,
            identity.location_id,
        )
        if not header:
            raise NotFoundError("Không tìm thấy phiếu kiểm kê của phòng này.")
        if header["trang_thai"] == "CHOT":
            return await _phieu_json(conn, identity, pid)
        so_da_dem = await conn.fetchval(
            "SELECT count(*) FROM public.vat_tu_kiem_ke_ca_dong"
            " WHERE kiem_ke_ca_id=$1::uuid AND clinic_id=$2::uuid AND dem IS NOT NULL",
            pid,
            identity.clinic_id,
        )
        if not so_da_dem:
            raise ValidationError("Nhập số đếm ít nhất một mặt hàng trước khi chốt.")
        await conn.execute(
            "UPDATE public.vat_tu_kiem_ke_ca_dong d"
            " SET ton_may=t.so_luong, lech=d.dem-t.so_luong"
            " FROM public.vat_tu_ton t"
            " WHERE d.kiem_ke_ca_id=$1::uuid AND d.clinic_id=$2::uuid"
            " AND d.dem IS NOT NULL AND t.id=d.ton_id AND t.clinic_id=d.clinic_id",
            pid,
            identity.clinic_id,
        )
        await conn.execute(
            "UPDATE public.vat_tu_kiem_ke_ca SET trang_thai='CHOT', chot_boi=$3::uuid,"
            " chot_luc=clock_timestamp(), mot_phan=(SELECT count(*) FROM"
            " public.vat_tu_kiem_ke_ca_dong WHERE kiem_ke_ca_id=$1::uuid"
            " AND clinic_id=$2::uuid AND dem IS NOT NULL) < (SELECT count(*) FROM"
            " public.vat_tu_kiem_ke_ca_dong WHERE kiem_ke_ca_id=$1::uuid"
            " AND clinic_id=$2::uuid) WHERE id=$1::uuid AND clinic_id=$2::uuid",
            pid,
            identity.clinic_id,
            identity.staff_id,
        )
        return await _phieu_json(conn, identity, pid)
