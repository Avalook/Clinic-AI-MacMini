"""Sổ vật tư riêng: phiếu bất biến, gửi lại an toàn, phiếu đảo đối ứng."""

from __future__ import annotations

from decimal import Decimal, DecimalException, InvalidOperation
from typing import Any
from uuid import UUID

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.services.kho_thuoc_service import _khoa

LOAI = frozenset(
    {"NHAP", "XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "KIEM", "DIEU_CHINH", "HUY"}
)


def tinh_tieu_hao(
    dau: Any, nhan: Any, tra: Any, cuoi: Any, gia: Any
) -> dict[str, Decimal] | None:
    """Tiêu hao từ hai số đếm thật; thiếu/rác trả rỗng, giữ chênh âm để soát."""
    try:
        if any(isinstance(v, bool) for v in (dau, nhan, tra, cuoi, gia)):
            return None
        a, b, c, d, g = (Decimal(str(v)) for v in (dau, nhan, tra, cuoi, gia))
        if not all(v.is_finite() for v in (a, b, c, d, g)) or min(b, c, g) < 0:
            return None
        so = a + b - c - d
        return {"so_luong": so, "gia_tri": so * g}
    except (DecimalException, ValueError, TypeError):
        return None


def _uuid(v: Any) -> str:
    try:
        return str(UUID(str(v)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("Mã mặt hàng/phòng/phiếu không hợp lệ.") from exc


def _so(v: Any, *, cho_0: bool = False, le: int = 3) -> Decimal:
    try:
        so = Decimal(str(v))
    except (ValueError, InvalidOperation) as exc:
        raise ValidationError("Số lượng/giá nhập phải là số hợp lệ.") from exc
    if not so.is_finite() or so < 0 or (not cho_0 and so == 0):
        raise ValidationError("Số lượng/giá nhập không hợp lệ.")
    if so >= Decimal(10) ** (18 - le) or so != so.quantize(Decimal(10) ** -le):
        raise ValidationError(f"Số vượt độ chính xác lưu trữ ({le} chữ số thập phân).")
    return so


def _dong(loai: str, d: dict[str, Any]) -> dict[str, Any]:
    vt = _uuid(d.get("vat_tu_id"))
    tu = _uuid(d["tu_room_id"]) if d.get("tu_room_id") else None
    den = _uuid(d["den_room_id"]) if d.get("den_room_id") else None
    if loai == "CHUYEN_PHONG" and (not tu or not den or tu == den):
        raise ValidationError("Chọn hai phòng khác nhau để chuyển vật tư.")
    if loai == "XUAT_PHONG" and (tu or not den):
        raise ValidationError("Xuất kho cần phòng nhận.")
    if loai == "TRA_KHO" and (not tu or den):
        raise ValidationError("Trả kho cần phòng trả.")
    if (loai == "NHAP" and tu) or (loai in {"KIEM", "DIEU_CHINH", "HUY"} and den):
        raise ValidationError("Nơi chứa không đúng loại phiếu.")
    return {
        "vat_tu_id": vt,
        "tu": tu,
        "den": den,
        "so": _so(d.get("so_luong"), cho_0=loai in {"KIEM", "DIEU_CHINH"}),
        # None = người lập không gõ giá → lấy giá danh mục tại LÚC lập (bản chụp).
        "gia": None
        if d.get("gia_nhap") in (None, "")
        else _so(d["gia_nhap"], cho_0=True, le=0),
    }


async def _khoa_co_so(conn: asyncpg.Connection, identity: StaffIdentity) -> None:
    # Cả phiếu, kiểm và đảo lấy cùng khoá: không đọc tồn cũ giữa hai lần ghi.
    await conn.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
        f"vat_tu:{identity.clinic_id}:{identity.location_id}",
    )


async def _phieu_da_co(
    conn: asyncpg.Connection, identity: StaffIdentity, khoa: str
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT id::text, ma_phieu, loai FROM public.vat_tu_phieu"
        " WHERE clinic_id=$1::uuid AND location_id=$2::uuid AND khoa_gui=$3",
        identity.clinic_id,
        identity.location_id,
        khoa,
    )
    return {**dict(row), "ok": True, "gui_lai": True} if row else None


async def _mo_phieu(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    loai: str,
    khoa: str,
    ghi_chu: str | None,
    dao: str | None = None,
) -> dict[str, Any]:
    code = await conn.fetchval(
        "SELECT upper(btrim(code)) FROM clinic_location WHERE"
        " clinic_id=$1::uuid AND id=$2::uuid",
        identity.clinic_id,
        identity.location_id,
    )
    if not code:
        raise NotFoundError("Không xác định được cơ sở đang làm.")
    so = await conn.fetchval(
        "SELECT count(*) FROM vat_tu_phieu WHERE clinic_id=$1::uuid AND"
        " location_id=$2::uuid",
        identity.clinic_id,
        identity.location_id,
    )
    ma = f"VT-{code}-{int(so) + 1:04d}"
    row = await conn.fetchrow(
        "INSERT INTO vat_tu_phieu (clinic_id, location_id, ma_phieu, loai,"
        " khoa_gui, tao_boi, ghi_chu, dao_phieu_id)"
        " VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6::uuid,$7,$8::uuid)"
        " RETURNING id::text, ma_phieu, loai",
        identity.clinic_id,
        identity.location_id,
        ma,
        loai,
        khoa,
        identity.staff_id,
        ghi_chu,
        dao,
    )
    return {**dict(row), "ok": True, "gui_lai": False}


async def _ton(
    conn: asyncpg.Connection, identity: StaffIdentity, vt: str, room: str | None
) -> Any:
    if not await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM service_price WHERE id=$1::uuid AND"
        " clinic_id=$2::uuid AND \"group\"='vat_tu')",
        vt,
        identity.clinic_id,
    ):
        raise NotFoundError("Không tìm thấy vật tư của phòng khám.")
    if room and not await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM clinic_room WHERE id=$1::uuid AND"
        " clinic_id=$2::uuid AND location_id=$3::uuid)",
        room,
        identity.clinic_id,
        identity.location_id,
    ):
        raise NotFoundError("Không tìm thấy phòng của cơ sở đang làm.")
    await conn.execute(
        "INSERT INTO vat_tu_ton (clinic_id,location_id,vat_tu_id,room_id)"
        " VALUES ($1::uuid,$2::uuid,$3::uuid,$4::uuid)"
        " ON CONFLICT ON CONSTRAINT vat_tu_ton_noi DO NOTHING",
        identity.clinic_id,
        identity.location_id,
        vt,
        room,
    )
    return await conn.fetchrow(
        "SELECT id::text, so_luong FROM vat_tu_ton WHERE"
        " clinic_id=$1::uuid AND location_id=$2::uuid"
        " AND vat_tu_id=$3::uuid AND room_id IS NOT DISTINCT FROM $4::uuid FOR UPDATE",
        identity.clinic_id,
        identity.location_id,
        vt,
        room,
    )


async def _ghi(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    phieu: str,
    vt: str,
    ton: Any,
    so: Decimal,
    gia: Decimal,
    dem: Decimal | None = None,
    dao: str | None = None,
) -> None:
    await conn.execute(
        "INSERT INTO vat_tu_txn"
        " (clinic_id,phieu_id,ton_id,vat_tu_id,so_luong,ton_may,gia_nhap,th"
        "uc_te,dao_txn_id)"
        " VALUES ($1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,$6,$7,$8,$9::uuid)",
        identity.clinic_id,
        phieu,
        ton["id"],
        vt,
        so,
        ton["so_luong"],
        gia,
        dem,
        dao,
    )


async def tao_phieu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    khoa_gui: str | None,
    loai: str,
    dong: list[dict[str, Any]],
    ghi_chu: str | None = None,
) -> dict[str, Any]:
    """Ghi nguyên phiếu; KIEM chỉ chụp số đếm, DIEU_CHINH mới đổi tồn."""
    khoa = _khoa(khoa_gui)
    if loai not in LOAI or not dong:
        raise ValidationError("Chọn loại phiếu và ít nhất một vật tư.")
    ds = [_dong(loai, d) for d in dong]
    keys = [(d["vat_tu_id"], d["tu"], d["den"]) for d in ds]
    if len(set(keys)) != len(keys):
        raise ValidationError("Một vật tư/nơi chứa chỉ có một dòng trên phiếu.")
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        cu = await _phieu_da_co(conn, identity, khoa)
        if cu:
            return cu
        p = await _mo_phieu(conn, identity, loai, khoa, ghi_chu)
        for d in ds:
            vt, so = d["vat_tu_id"], d["so"]
            gia = d["gia"]
            if gia is None:
                gia = Decimal(
                    await conn.fetchval(
                        "SELECT coalesce(gia_nhap_vat_tu,0) FROM service_price"
                        " WHERE id=$1::uuid AND clinic_id=$2::uuid",
                        vt,
                        identity.clinic_id,
                    )
                    or 0
                )
            if loai in {"XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG"}:
                tu = await _ton(conn, identity, vt, d["tu"])
                den = await _ton(conn, identity, vt, d["den"])
                await _ghi(conn, identity, p["id"], vt, tu, -so, gia)
                await _ghi(conn, identity, p["id"], vt, den, so, gia)
            else:
                ton = await _ton(
                    conn, identity, vt, d["den"] if loai == "NHAP" else d["tu"]
                )
                dem = so if loai in {"KIEM", "DIEU_CHINH"} else None
                lech = so - ton["so_luong"] if loai == "DIEU_CHINH" else Decimal(0)
                delta = lech if dem is not None else (-so if loai == "HUY" else so)
                await _ghi(conn, identity, p["id"], vt, ton, delta, gia, dem)
        return p


async def hoan_phieu(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    phieu_id: str,
    khoa_gui: str | None,
    ghi_chu: str | None = None,
) -> dict[str, Any]:
    """Đảo mỗi dòng gốc đúng một lần; không viết lại lịch sử kiểm đếm."""
    pid, khoa = _uuid(phieu_id), _khoa(khoa_gui)
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        cu = await _phieu_da_co(conn, identity, khoa)
        if cu:
            return cu
        p = await conn.fetchrow(
            "SELECT id,loai FROM vat_tu_phieu WHERE clinic_id=$1::uuid AND"
            " location_id=$2::uuid AND id=$3::uuid",
            identity.clinic_id,
            identity.location_id,
            pid,
        )
        if not p:
            raise NotFoundError("Không tìm thấy phiếu vật tư của cơ sở.")
        if p["loai"] == "HOAN" or await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM vat_tu_phieu WHERE"
            " clinic_id=$1::uuid AND dao_phieu_id=$2::uuid)",
            identity.clinic_id,
            pid,
        ):
            raise ConflictError("Phiếu đã đảo hoặc là phiếu đảo.")
        dao = await _mo_phieu(conn, identity, "HOAN", khoa, ghi_chu, pid)
        rows = await conn.fetch(
            "SELECT x.id::text AS"
            " txn_id,x.vat_tu_id::text,x.so_luong,x.gia_nhap,t.id::text,t.s"
            "o_luong AS ton"
            " FROM vat_tu_txn x JOIN vat_tu_ton t ON t.id=x.ton_id AND"
            " t.clinic_id=x.clinic_id"
            " WHERE x.clinic_id=$1::uuid AND x.phieu_id=$2::uuid ORDER BY x.id",
            identity.clinic_id,
            pid,
        )
        for r in rows:
            await _ghi(
                conn,
                identity,
                dao["id"],
                r["vat_tu_id"],
                {"id": r["id"], "so_luong": r["ton"]},
                -r["so_luong"],
                r["gia_nhap"],
                dao=r["txn_id"],
            )
        return dao


async def doc_ton(
    pool: asyncpg.Pool, *, identity: StaffIdentity
) -> list[dict[str, Any]]:
    """Hiện cả phòng đã tắt; tồn âm luôn có cảnh báo dù mức tối thiểu bằng 0."""
    rows = await pool.fetch(
        "SELECT t.id::text,t.vat_tu_id::text,t.room_id::text,s.name AS ten,s.don_vi,"
        " coalesce(r.name,'Kho cơ sở') AS noi_chua,r.is_active AS phong_dang_bat,"
        " t.so_luong,t.ton_toi_thieu FROM vat_tu_ton t"
        " JOIN service_price s ON s.id=t.vat_tu_id AND s.clinic_id=t.clinic_id"
        " LEFT JOIN clinic_room r ON r.id=t.room_id AND r.clinic_id=t.clinic_id"
        " WHERE t.clinic_id=$1::uuid AND t.location_id=$2::uuid ORDER BY"
        " s.name,t.room_id NULLS FIRST",
        identity.clinic_id,
        identity.location_id,
    )
    return [
        {
            **dict(r),
            "canh_bao": "tồn âm — cần kiểm đếm"
            if r["so_luong"] < 0
            else ("Dưới mức tối thiểu" if r["so_luong"] < r["ton_toi_thieu"] else ""),
        }
        for r in rows
    ]
