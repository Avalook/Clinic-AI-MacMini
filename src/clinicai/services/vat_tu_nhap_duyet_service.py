"""Phiếu NHẬP vật tư chờ duyệt (Tuyền chốt 14/10/2026, G8b — Q11 + 2e).

Mặt hàng có cờ "cần duyệt nhập" (`service_price.can_duyet_nhap_vat_tu`, Quản lý đặt ở
danh mục): phiếu NHẬP có ít nhất một dòng như vậy KHÔNG ghi sổ ngay mà thành YÊU CẦU
(`vat_tu_nhap_cho_duyet`). Nội dung yêu cầu bất biến (giá nhập chụp lúc xin). Người có
lego **Duyệt vật tư** (`vat_tu.approve`) duyệt thì hệ thống lập phiếu NHẬP thật đúng số
đã xin (sổ chỉ thêm); từ chối (bắt lý do) hoặc người lập rút lại thì không có gì vào
sổ. Người có lego tự lập = tự duyệt (cùng luật với bán thêm vật tư). Yêu cầu chỉ quyết
MỘT lần; hoàn tác một lần nhập đã duyệt = phiếu đảo như mọi phiếu.

Phiếu hỗn hợp (một dòng cần duyệt, một dòng thường): CẢ phiếu chờ — không ghi nửa phiếu.
Quyền = lego, không theo vai; Postgres ép lại (trigger `vat_tu_nhap_cho_duyet_gac`).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import asyncpg

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.events.catalogue import VatTuNhapChoDuyet, VatTuNhapDaQuyet
from clinicai.events.emit import emit_event, nguoi
from clinicai.permissions.can import can, doi_quyen
from clinicai.services.audit import record_event
from clinicai.services.vat_tu_kho_service import (
    _dong,
    _ghi_phieu,
    _khoa_co_so,
    _khoa_va_kiem_don_vi,
    _uuid,
)

QUYEN_DUYET = "vat_tu.approve"

#: Nhãn hiển thị cho từng trạng thái (màn chỉ vẽ lại chữ này).
NHAN = {
    "CHO_DUYET": "Chờ duyệt",
    "DA_DUYET": "Đã duyệt",
    "TU_CHOI": "Đã từ chối",
    "RUT_LAI": "Đã rút lại",
}

_LY_DO_TOI_THIEU = 5
_LY_DO_TOI_DA = 500


def _ly_do(raw: Any, *, bat_buoc: bool) -> str | None:
    """Lý do từ chối / rút lại. Bắt buộc → 5–500 ký tự; không bắt buộc thì bỏ trống
    được nhưng đã gửi phải hợp lệ — không ghi rác."""
    if raw is None and not bat_buoc:
        return None
    ly = raw.strip() if isinstance(raw, str) else ""
    if not _LY_DO_TOI_THIEU <= len(ly) <= _LY_DO_TOI_DA:
        raise ValidationError(f"Lý do từ {_LY_DO_TOI_THIEU} đến {_LY_DO_TOI_DA} ký tự.")
    return ly


def _ra(r: asyncpg.Record, **them: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "yeu_cau_id": str(r["id"]),
        "ma_yeu_cau": r["ma_yeu_cau"],
        "trang_thai": r["trang_thai"],
        "phieu_id": str(r["phieu_id"]) if r["phieu_id"] else None,
        **them,
    }


async def _lay(
    conn: asyncpg.Connection, identity: StaffIdentity, yeu_cau_id: str
) -> asyncpg.Record:
    """Khoá dòng yêu cầu của CƠ SỞ đang làm (cơ sở khác = không thấy)."""
    r = await conn.fetchrow(
        "SELECT * FROM public.vat_tu_nhap_cho_duyet WHERE clinic_id = $1::uuid"
        " AND location_id = $2::uuid AND id = $3::uuid FOR UPDATE",
        identity.clinic_id,
        identity.location_id,
        yeu_cau_id,
    )
    if r is None:
        raise NotFoundError("Không tìm thấy yêu cầu nhập vật tư của cơ sở này.")
    return r


def _dong_cua(r: asyncpg.Record) -> list[dict[str, Any]]:
    d = r["dong"]
    return json.loads(d) if isinstance(d, str) else list(d)


async def xu_ly_nhap_can_duyet(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    khoa: str,
    ds: list[dict[str, Any]],
    ghi_chu: str | None,
) -> dict[str, Any] | None:
    """Gọi từ `tao_phieu` (đã giữ khoá cơ sở, đã kiểm gửi lại phiếu). Trả None nếu
    phiếu không có dòng cần duyệt → đi đường ghi sổ như cũ."""
    # Khoá đã dùng phải tiếp tục trỏ vào yêu cầu cũ dù quản lý vừa bỏ cờ duyệt.
    # Nếu kiểm cờ trước, retry có thể ghi NHAP trực tiếp rồi yêu cầu cũ lại được
    # duyệt, làm tăng tồn hai lần cho cùng một lần gửi.
    cu = await conn.fetchrow(
        "SELECT * FROM public.vat_tu_nhap_cho_duyet WHERE clinic_id = $1::uuid"
        " AND location_id = $2::uuid AND khoa_gui = $3",
        identity.clinic_id,
        identity.location_id,
        khoa,
    )
    if cu is not None:
        return _ra(cu, cho_duyet=cu["trang_thai"] == "CHO_DUYET", gui_lai=True)

    can_duyet = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM public.service_price WHERE clinic_id = $1::uuid"
        " AND id = ANY($2::uuid[]) AND can_duyet_nhap_vat_tu)",
        identity.clinic_id,
        [d["vat_tu_id"] for d in ds],
    )
    if not can_duyet:
        return None

    dong: list[dict[str, Any]] = []
    for d in ds:
        gia = d["gia"]
        if gia is None:  # bản chụp giá danh mục LÚC XIN
            gia = Decimal(
                await conn.fetchval(
                    "SELECT coalesce(gia_nhap_vat_tu, 0) FROM public.service_price"
                    " WHERE id = $1::uuid AND clinic_id = $2::uuid",
                    d["vat_tu_id"],
                    identity.clinic_id,
                )
                or 0
            )
        dong.append(
            {
                "vat_tu_id": d["vat_tu_id"],
                "don_vi": d["don_vi"],
                "den_room_id": d["den"],
                "so_luong": str(d["so"]),
                "gia_nhap": str(gia),
            }
        )
    code = await conn.fetchval(
        "SELECT upper(btrim(code)) FROM clinic_location WHERE clinic_id = $1::uuid"
        " AND id = $2::uuid",
        identity.clinic_id,
        identity.location_id,
    )
    if not code:
        raise NotFoundError("Không xác định được cơ sở đang làm.")
    so = await conn.fetchval(
        "SELECT count(*) FROM public.vat_tu_nhap_cho_duyet WHERE clinic_id = $1::uuid"
        " AND location_id = $2::uuid",
        identity.clinic_id,
        identity.location_id,
    )
    yc = await conn.fetchrow(
        "INSERT INTO public.vat_tu_nhap_cho_duyet (clinic_id, location_id, ma_yeu_cau,"
        " khoa_gui, dong, ghi_chu, tao_boi)"
        " VALUES ($1::uuid, $2::uuid, $3, $4, $5::jsonb, $6, $7::uuid) RETURNING *",
        identity.clinic_id,
        identity.location_id,
        f"YC-{code}-{int(so) + 1:04d}",
        khoa,
        json.dumps(dong),
        ghi_chu,
        identity.staff_id,
    )
    assert yc is not None
    await emit_event(
        conn,
        ten="vat_tu.nhap_cho_duyet",
        clinic_id=identity.clinic_id,
        aggregate_id=str(yc["id"]),
        so_ke_tiep=True,
        payload=VatTuNhapChoDuyet(
            yeu_cau_id=str(yc["id"]),
            ma_yeu_cau=yc["ma_yeu_cau"],
            location_id=identity.location_id,
            so_dong=len(dong),
        ),
        boi=nguoi(identity),
        correlation_id=str(yc["id"]),
    )
    await record_event(
        conn,
        event_type="vat_tu.nhap_cho_duyet",
        aggregate_type="vat_tu_nhap",
        aggregate_id=str(yc["id"]),
        identity=identity,
        origin="api:vat-tu-nhap",
        payload={"ma_yeu_cau": yc["ma_yeu_cau"], "so_dong": len(dong)},
        correlation_id=str(yc["id"]),
    )
    # Người có lego Duyệt vật tư tự lập = tự duyệt, ghi sổ luôn.
    if await can(conn, identity, QUYEN_DUYET):
        return await _duyet_tren_conn(conn, identity, yc, tu_dong=True)
    return _ra(yc, cho_duyet=True, gui_lai=False, loai="NHAP")


async def _duyet_tren_conn(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    yc: asyncpg.Record,
    *,
    tu_dong: bool,
) -> dict[str, Any]:
    ds = [_dong("NHAP", d) for d in _dong_cua(yc)]
    # Phiếu chờ duyệt phải dùng đúng đơn vị đã chụp khi gửi. Các yêu cầu cũ
    # không có đơn vị sẽ được gắn đơn vị hiện tại sau khi đã khóa mặt hàng.
    await _khoa_va_kiem_don_vi(conn, identity, ds)
    nguoi_lap = await conn.fetchval(
        "SELECT full_name FROM public.staff WHERE id = $1::uuid", yc["tao_boi"]
    )
    ghi_chu = (
        f"Yêu cầu {yc['ma_yeu_cau']} — lập bởi {nguoi_lap}, "
        + ("tự duyệt" if tu_dong else f"duyệt bởi {identity.full_name}")
        + (f". {yc['ghi_chu']}" if yc["ghi_chu"] else "")
    )
    phieu = await _ghi_phieu(
        conn, identity, f"duyet-{yc['id']}", "NHAP", ds, ghi_chu[:1000]
    )
    cap_nhat = await conn.fetchrow(
        "UPDATE public.vat_tu_nhap_cho_duyet SET trang_thai = 'DA_DUYET',"
        " quyet_boi = $2::uuid, quyet_luc = now(), phieu_id = $3::uuid"
        " WHERE id = $1::uuid RETURNING *",
        yc["id"],
        identity.staff_id,
        phieu["id"],
    )
    assert cap_nhat is not None
    await _ghi_quyet(conn, identity, cap_nhat, "DUYET")
    return {
        **phieu,
        **_ra(cap_nhat, cho_duyet=False, gui_lai=False),
        "id": phieu["id"],
        "phieu_id": phieu["id"],
    }


async def _ghi_quyet(
    conn: asyncpg.Connection,
    identity: StaffIdentity,
    yc: asyncpg.Record,
    hanh_dong: str,
) -> None:
    await emit_event(
        conn,
        ten="vat_tu.nhap_da_quyet",
        clinic_id=identity.clinic_id,
        aggregate_id=str(yc["id"]),
        so_ke_tiep=True,
        payload=VatTuNhapDaQuyet(
            yeu_cau_id=str(yc["id"]),
            ma_yeu_cau=yc["ma_yeu_cau"],
            hanh_dong=hanh_dong,
            phieu_id=str(yc["phieu_id"]) if yc["phieu_id"] else None,
        ),
        boi=nguoi(identity),
        correlation_id=str(yc["id"]),
    )
    await record_event(
        conn,
        event_type="vat_tu.nhap_da_quyet",
        aggregate_type="vat_tu_nhap",
        aggregate_id=str(yc["id"]),
        identity=identity,
        origin="api:vat-tu-nhap",
        payload={
            "ma_yeu_cau": yc["ma_yeu_cau"],
            "hanh_dong": hanh_dong,
            **({"phieu_id": str(yc["phieu_id"])} if yc["phieu_id"] else {}),
            **({"ly_do": yc["quyet_ly_do"]} if yc["quyet_ly_do"] else {}),
        },
        correlation_id=str(yc["id"]),
    )


async def duyet(
    pool: asyncpg.Pool, *, identity: StaffIdentity, yeu_cau_id: Any
) -> dict[str, Any]:
    """Duyệt → lập phiếu NHẬP thật. Gọi lại / hai máy cùng bấm: không nhân đôi."""
    yid = _uuid(yeu_cau_id)
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen(
            conn, identity, QUYEN_DUYET, cau="Bạn không có quyền Duyệt vật tư."
        )
        await _khoa_co_so(conn, identity)
        yc = await _lay(conn, identity, yid)
        if yc["trang_thai"] == "DA_DUYET":
            return _ra(yc, already=True)
        if yc["trang_thai"] != "CHO_DUYET":
            raise ConflictError(
                f"Yêu cầu {yc['ma_yeu_cau']} đã {NHAN[yc['trang_thai']].lower()}"
                " — không duyệt được."
            )
        return await _duyet_tren_conn(conn, identity, yc, tu_dong=False)


async def tu_choi(
    pool: asyncpg.Pool, *, identity: StaffIdentity, yeu_cau_id: Any, ly_do: Any
) -> dict[str, Any]:
    """Từ chối (bắt lý do) — không có gì vào sổ."""
    yid = _uuid(yeu_cau_id)
    async with pool.acquire() as conn, conn.transaction():
        await doi_quyen(
            conn, identity, QUYEN_DUYET, cau="Bạn không có quyền Duyệt vật tư."
        )
        ly = _ly_do(ly_do, bat_buoc=True)
        await _khoa_co_so(conn, identity)
        yc = await _lay(conn, identity, yid)
        if yc["trang_thai"] == "TU_CHOI":
            return _ra(yc, already=True)
        if yc["trang_thai"] != "CHO_DUYET":
            raise ConflictError(
                f"Yêu cầu {yc['ma_yeu_cau']} đã {NHAN[yc['trang_thai']].lower()}"
                " — không từ chối được."
            )
        cap_nhat = await conn.fetchrow(
            "UPDATE public.vat_tu_nhap_cho_duyet SET trang_thai = 'TU_CHOI',"
            " quyet_boi = $2::uuid, quyet_luc = now(), quyet_ly_do = $3"
            " WHERE id = $1::uuid RETURNING *",
            yc["id"],
            identity.staff_id,
            ly,
        )
        assert cap_nhat is not None
        await _ghi_quyet(conn, identity, cap_nhat, "TU_CHOI")
        return _ra(cap_nhat)


async def rut_lai(
    pool: asyncpg.Pool,
    *,
    identity: StaffIdentity,
    yeu_cau_id: Any,
    ly_do: Any = None,
) -> dict[str, Any]:
    """Rút lại khi còn chờ — người lập hoặc người có lego Duyệt vật tư."""
    yid = _uuid(yeu_cau_id)
    ly = _ly_do(ly_do, bat_buoc=False)
    async with pool.acquire() as conn, conn.transaction():
        await _khoa_co_so(conn, identity)
        yc = await _lay(conn, identity, yid)
        if str(yc["tao_boi"]) != identity.staff_id and not await can(
            conn, identity, QUYEN_DUYET
        ):
            raise SafetyGateError(
                "Chỉ người lập hoặc người có quyền Duyệt vật tư mới rút lại được."
            )
        if yc["trang_thai"] == "RUT_LAI":
            return _ra(yc, already=True)
        if yc["trang_thai"] != "CHO_DUYET":
            raise ConflictError(
                f"Yêu cầu {yc['ma_yeu_cau']} đã {NHAN[yc['trang_thai']].lower()}"
                " — không rút lại được."
            )
        cap_nhat = await conn.fetchrow(
            "UPDATE public.vat_tu_nhap_cho_duyet SET trang_thai = 'RUT_LAI',"
            " quyet_boi = $2::uuid, quyet_luc = now(), quyet_ly_do = $3"
            " WHERE id = $1::uuid RETURNING *",
            yc["id"],
            identity.staff_id,
            ly,
        )
        assert cap_nhat is not None
        await _ghi_quyet(conn, identity, cap_nhat, "RUT_LAI")
        return _ra(cap_nhat)


async def doc_cho_duyet(
    pool: asyncpg.Pool, *, identity: StaffIdentity, gioi_han: int = 100
) -> list[dict[str, Any]]:
    """Yêu cầu nhập của CƠ SỞ đang làm — chờ duyệt lên đầu, rồi mới nhất."""
    gioi_han = max(1, min(int(gioi_han), 200))
    rows = await pool.fetch(
        "SELECT y.*, s.full_name AS ten_lap, q.full_name AS ten_quyet"
        " FROM public.vat_tu_nhap_cho_duyet y"
        " JOIN public.staff s ON s.id = y.tao_boi"
        " LEFT JOIN public.staff q ON q.id = y.quyet_boi"
        " WHERE y.clinic_id = $1::uuid AND y.location_id = $2::uuid"
        " ORDER BY (y.trang_thai = 'CHO_DUYET') DESC, y.tao_luc DESC, y.id"
        " LIMIT $3",
        identity.clinic_id,
        identity.location_id,
        gioi_han,
    )
    ten_vt = {
        r["id"]: r
        for r in await pool.fetch(
            "SELECT id::text, name, don_vi FROM public.service_price"
            " WHERE clinic_id = $1::uuid AND \"group\" = 'vat_tu'",
            identity.clinic_id,
        )
    }
    out = []
    for r in rows:
        dong = []
        tong = Decimal(0)
        for d in _dong_cua(r):
            vt = ten_vt.get(d["vat_tu_id"])
            # Thành tiền tính ở đây (Decimal, giá nhập đã chụp lúc xin) để màn chỉ vẽ.
            thanh_tien = Decimal(d["so_luong"]) * Decimal(d["gia_nhap"])
            tong += thanh_tien
            dong.append(
                {
                    "vat_tu_id": d["vat_tu_id"],
                    "ten": vt["name"] if vt else None,
                    "don_vi": vt["don_vi"] if vt else None,
                    "den_room_id": d.get("den_room_id"),
                    "so_luong": d["so_luong"],
                    "gia_nhap": d["gia_nhap"],
                    "thanh_tien": str(thanh_tien),
                }
            )
        out.append(
            {
                "id": str(r["id"]),
                "ma_yeu_cau": r["ma_yeu_cau"],
                "trang_thai": r["trang_thai"],
                "nhan": NHAN[r["trang_thai"]],
                "nguoi_lap": r["ten_lap"],
                # Màn cần biết "của tôi" để hiện nút Rút lại (máy chủ vẫn kiểm lại).
                "cua_toi": str(r["tao_boi"]) == identity.staff_id,
                "tao_luc": r["tao_luc"],
                "ghi_chu": r["ghi_chu"],
                "dong": dong,
                "tong_tien": str(tong),
                "nguoi_quyet": r["ten_quyet"],
                "quyet_luc": r["quyet_luc"],
                "quyet_ly_do": r["quyet_ly_do"],
                "phieu_id": str(r["phieu_id"]) if r["phieu_id"] else None,
            }
        )
    return out


__all__ = [
    "doc_cho_duyet",
    "duyet",
    "rut_lai",
    "tu_choi",
    "xu_ly_nhap_can_duyet",
]
