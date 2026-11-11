"""File Excel địa chỉ khách (chị Hoài, kế toán, 11/11/2026) qua HTTP thật.

Kế toán tải danh sách (mã BN, họ tên, SĐT, địa chỉ) để rà địa chỉ sai rồi vào phần
mềm sửa. Đây là xuất HÀNG LOẠT SĐT + địa chỉ ⇒ chỉ Kế toán / Quản lý (quyền
`accounting.finance.full`), mỗi lần tải ghi nhật ký — KHÔNG ghi chữ trong ô tìm (có
thể là tên / SĐT khách) vào nhật ký.
"""

from __future__ import annotations

import io
import json
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg
import httpx
import pytest
from openpyxl import load_workbook

from clinicai.services import xuat_dia_chi_khach as xdc
from clinicai.services.danh_sach_benh_nhan_service import DanhSachBenhNhanService
from clinicai.services.xuat_dia_chi_khach import COT
from tests.services.test_quyen_lego_man_db import (  # noqa: F401
    CLINIC,
    _goi,
    _nguoi,
    http,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

DUONG = "/patients/danh-sach-xlsx"


async def _ba_khach(pool: asyncpg.Pool) -> str:  # noqa: F811
    """Ba khách cùng một dấu riêng trong tên (ô tìm lọc đúng ba người này)."""
    dau = f"XDC{uuid.uuid4().hex[:8]}"
    loc = await pool.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
        " AND is_active ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    cu = ("12 Kim Ngưu", "Phường Vĩnh Tuy", "Hà Nội")
    for ten, sdt, dia_chi, cau_truc in (
        # Vừa sửa ở hồ sơ: ô tự do mới, phần có cấu trúc còn bản lúc tạo.
        (f"Sửa rồi {dau}", "0901000001", "5 Láng Hạ", cu),
        # Khách cũ chỉ có phần có cấu trúc.
        (f"Chỉ cấu trúc {dau}", "0901000002", None, cu),
        # Tên bắt đầu bằng "=" — không được thành công thức trong Excel.
        (f"=1+1 {dau}", None, "  Thanh Xuân  ", (None, None, None)),
    ):
        await pool.execute(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary, address, address_detail, ward_name, province_name)"
            " VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7, $8, $9)",
            CLINIC,
            f"XDC-{uuid.uuid4().hex[:8]}",
            ten,
            loc,
            sdt,
            dia_chi,
            *cau_truc,
        )
    return dau


def _doc(noi_dung: bytes) -> list[list[Any]]:
    ws = load_workbook(io.BytesIO(noi_dung)).active
    assert ws is not None
    return [[c.value for c in hang] for hang in ws.iter_rows()]


async def test_ke_toan_tai_duoc_dung_cot_dia_chi_theo_luat_chung(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    dau = await _ba_khach(pool)
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    r = await _goi(http, ke_toan, "GET", DUONG, params={"q": dau})
    assert r.status_code == 200, r.text[:300]
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "attachment" in r.headers["content-disposition"]
    hang = _doc(r.content)
    assert hang[0] == list(COT)
    theo_ten = {h[1]: h for h in hang[1:]}
    assert len(theo_ten) == 3
    assert theo_ten[f"Sửa rồi {dau}"][2:4] == ["0901000001", "5 Láng Hạ"]
    assert theo_ten[f"Chỉ cấu trúc {dau}"][3] == "12 Kim Ngưu, Phường Vĩnh Tuy, Hà Nội"
    assert theo_ten[f"=1+1 {dau}"][3] == "Thanh Xuân"
    # Cột cuối để trống cho chị đánh dấu.
    assert all(h[-1] is None for h in hang[1:])
    # Ô tên bắt đầu bằng "=" là CHỮ, không phải công thức.
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws is not None
    o = next(c for c in ws["B"] if c.value == f"=1+1 {dau}")
    assert o.data_type == "s"


async def test_loc_khop_dung_man_danh_sach(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    dau = await _ba_khach(pool)
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    for loc, mong in (("chua-kham", 3), ("tai-kham", 0), ("lan-dau", 0), ("rac", 3)):
        r = await _goi(http, ke_toan, "GET", DUONG, params={"q": dau, "loc": loc})
        assert r.status_code == 200, f"loc={loc} → {r.status_code}"
        so_dong = len(_doc(r.content)) - 1
        man = await DanhSachBenhNhanService(pool).lay(identity=ke_toan, q=dau, loc=loc)
        assert so_dong == mong == man["so_khop"], f"loc={loc}"


async def test_khong_co_quyen_ke_toan_thi_bi_chan(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    for vai, legos in (
        ("RECEPTION", ["tiep_don", "ds_benh_nhan", "cham_soc_khach"]),
        ("CSKH", ["cham_soc_khach", "ds_benh_nhan"]),
        ("ACCOUNTANT", ["bao_cao", "ds_benh_nhan"]),
    ):
        ai = await _nguoi(pool, vai, legos)
        r = await _goi(http, ai, "GET", DUONG)
        assert r.status_code == 403, f"{vai} {legos} → {r.status_code}"


async def test_moi_lan_tai_ghi_nhat_ky_khong_lo_chu_tim(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    dau = await _ba_khach(pool)
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    r = await _goi(http, ke_toan, "GET", DUONG, params={"q": dau, "loc": "chua-kham"})
    assert r.status_code == 200
    dong = await pool.fetchrow(
        "SELECT payload FROM event_log WHERE event_type = 'patient.list_exported'"
        " AND metadata->>'clinic_staff_id' = $1 ORDER BY recorded_at DESC LIMIT 1",
        ke_toan.staff_id,
    )
    assert dong is not None, "không có dòng nhật ký"
    payload = dong["payload"]
    payload = json.loads(payload) if isinstance(payload, str) else payload
    assert payload == {"so_dong": 3, "co_tim": True, "loc": "chua-kham"}
    assert dau not in json.dumps(payload, ensure_ascii=False)


async def test_quan_ly_tai_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    dau = await _ba_khach(pool)
    quan_ly = await _nguoi(pool, "MANAGEMENT", ["ke_toan", "ds_benh_nhan", "cai_dat"])
    r = await _goi(http, quan_ly, "GET", DUONG, params={"q": dau})
    assert r.status_code == 200, r.text[:300]
    assert len(_doc(r.content)) - 1 == 3


async def test_thu_ky_chi_xuat_khach_cua_bac_si_minh(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    """Phạm vi thư ký y khoa giữ nguyên khi xuất — cùng `khach_duoc_xem` với màn."""
    dau = await _ba_khach(pool)
    thu_ky = await _nguoi(pool, "TKYK", ["ke_toan", "ds_benh_nhan"])
    bac_si = await _nguoi(pool, "DOCTOR", ["ban_kham"])
    await pool.execute(
        "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid)",
        CLINIC,
        thu_ky.staff_id,
        bac_si.staff_id,
    )
    r = await _goi(http, thu_ky, "GET", DUONG, params={"q": dau})
    assert r.status_code == 200, r.text[:300]
    so_dong = len(_doc(r.content)) - 1
    man = await DanhSachBenhNhanService(pool).lay(identity=thu_ky, q=dau)
    # Ba khách thử không thuộc bác sĩ của thư ký ⇒ không lọt vào file.
    assert so_dong == man["so_khop"] == 0


async def test_cham_tran_thi_file_co_dong_bao(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dau = await _ba_khach(pool)
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    monkeypatch.setattr(xdc, "TRAN", 2)
    hang = _doc(await xdc.xuat_dia_chi_khach(pool, identity=ke_toan, q=dau, loc=None))
    assert len(hang) == 1 + 2 + 1, "tiêu đề + 2 dòng + 1 dòng báo"
    assert str(hang[-1][1]).startswith("Đã cắt ở 2 dòng")


async def test_hoat_dong_gan_nhat_theo_gio_viet_nam(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    """Khách vừa tạo: mốc = giờ tạo hồ sơ — Excel ra giờ Việt Nam (không lệch 7h)."""
    dau = await _ba_khach(pool)
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    r = await _goi(http, ke_toan, "GET", DUONG, params={"q": dau})
    ws = load_workbook(io.BytesIO(r.content)).active
    assert ws is not None
    gio_vn = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).replace(tzinfo=None)
    for o in [c for c in ws["E"]][1:]:
        assert isinstance(o.value, datetime), o.value
        assert abs((o.value - gio_vn).total_seconds()) < 600, (o.value, gio_vn)
        assert o.number_format == "dd/mm/yyyy hh:mm:ss"


async def test_tham_so_rac_khong_500(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "ds_benh_nhan"])
    for params in ({"q": "%_\\(),*" * 30}, {"loc": "x" * 300}, {"q": "", "loc": ""}):
        r = await _goi(http, ke_toan, "GET", DUONG, params=params)
        assert r.status_code in (200, 422), f"{params} → {r.status_code}"
