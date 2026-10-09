"""Danh mục vị trí trực đọc từ DATABASE (CORE-C4, 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_vi_tri_tu_database_db.py

Trước hôm nay 34 vị trí viết cứng trong `src/dashboard/lib/roster.ts`, song song
với bảng `vi_tri_lam_viec`. Nay bảng lịch đọc danh mục từ `/me/vi-tri-hom-nay`
→ `danh_muc`. Ba bài kiểm "mọi vị trí đều có màn / có nhóm / không có mã ma"
trước đọc mảng TSX ấy — nay đọc database, vì đó là nguồn thật.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, cast

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.identity import vi_tri_hom_nay
from tests.services.test_phong_la_tai_nguyen_db import CLINIC, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

DASHBOARD = Path(__file__).resolve().parents[2] / "dashboard"
NAV = (DASHBOARD / "app" / "(dashboard)" / "nav-items.ts").read_text(encoding="utf-8")


def _khoi(bat_dau: str, ket_thuc: str) -> str:
    return NAV[NAV.index(bat_dau) : NAV.index(ket_thuc)]


MAN = set(
    re.findall(
        r"^\s+([A-Z0-9_]+):\s*\[",
        _khoi("export const MAN_THEO_VI_TRI", "// ── NHÓM VAI TRÊN THANH BÊN"),
        re.M,
    )
)
NHOM = set(
    re.findall(
        r"^\s+([A-Z0-9_]+):\s*\"",
        _khoi("export const NHOM_THEO_VI_TRI", "const THU_TU_NHOM"),
        re.M,
    )
)
# "Lịch khám" là cột bác sĩ trực, không phải vị trí (VI_TRI_LICH_KHAM ở roster.ts).
NGOAI_DANH_MUC = {"LICH_KHAM"}


def _ai() -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="Test vị trí",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=CLINIC,
        location_id="",
        location_name="",
    )


async def _goi(pool: asyncpg.Pool) -> list[dict[str, Any]]:  # noqa: F811
    kq = await vi_tri_hom_nay(identity=_ai(), pool=pool)
    return cast(list[dict[str, Any]], kq["danh_muc"])


async def _danh_muc(pool: asyncpg.Pool) -> set[str]:  # noqa: F811
    """Vị trí thật của phòng khám (bỏ dòng các bài kiểm khác tạo: mã `T-…`, và
    `VT-…` của test_chon_bac_si_trong_phong_db — mã thật không có dấu gạch)."""
    rows = await pool.fetch(
        "SELECT code FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid AND is_active"
        " AND code !~ '^(T|VT)-'",
        CLINIC,
    )
    return {r["code"] for r in rows}


async def test_moi_vi_tri_trong_database_deu_co_man_va_nhom(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Thiếu một mã thì người đứng vị trí ấy hôm đó nhận thanh bên trống."""
    ma = await _danh_muc(pool)
    assert ma, "database thử chưa có danh mục vị trí"
    assert sorted(ma - MAN) == [], "vị trí chưa khai màn trong MAN_THEO_VI_TRI"
    assert sorted(ma - NHOM) == [], "vị trí chưa có nhóm trong NHOM_THEO_VI_TRI"


async def test_khong_co_ma_vi_tri_ma_trong_bang_man(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Mã khai trong nav mà không có trong database là dấu vết một lần đổi mã."""
    ma = await _danh_muc(pool) | NGOAI_DANH_MUC
    assert sorted(MAN - ma) == []
    assert sorted(NHOM - ma) == []


async def test_danh_muc_tra_theo_thu_tu_excel_kem_nhan_hang(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ds = [d for d in await _goi(pool) if not d["code"].startswith("T-")]
    ma = [d["code"] for d in ds]
    # Thứ tự dòng Excel: Lễ tân trước Thu ngân, tầng 1 trước tầng 4.
    assert ma.index("T1_LETAN") < ma.index("T1_THUNGAN") < ma.index("T4_SA_BS1")
    theo = {d["code"]: d for d in ds}
    # Nhãn hàng ngắn kiểu Excel (migration 20260923000019); trống thì = tên.
    assert theo["T1_TT_BS"]["ten_ngan"] == "BS"
    assert theo["T1_LETAN"]["ten_ngan"] == theo["T1_LETAN"]["ten"]
    # Tầng = tầng của phòng thật (cột Tầng của bảng lịch, 01/10/2026).
    assert theo["T1_TT_BS"]["tang"] == "Tầng 1"
    # Tên phòng = TÊN PHÒNG HIỆN TẠI theo room_id, không phải chữ `v.phong`.
    ten_phong = await pool.fetchval(
        "SELECT name FROM clinic_room"
        " WHERE clinic_id = $1::uuid AND code = 'KN-THUTHUAT'",
        CLINIC,
    )
    assert theo["T1_TT_BS"]["phong"] == ten_phong
    assert theo["T1_TT_BS"]["ma_phong"] == "KN-THUTHUAT"
    # Vị trí không gắn phòng thật (Trưởng ca) VẪN có trong danh mục — bảng lịch
    # có hàng cho nó (27/09 đợt 3: bản cũ lọc bỏ vị trí không tầng). Tầng/Phòng
    # là chữ hiển thị của vị trí (Tuyền 09/10: "Quản lý ca khám"), không phải phòng.
    assert theo["DIEU_PHOI"]["tang"] == "Quản lý ca khám"
    assert theo["DIEU_PHOI"]["phong"] == "Quản lý ca khám"
    assert theo["DIEU_PHOI"]["ma_phong"] == ""


async def test_doi_ten_phong_o_cau_hinh_thi_lich_doi_theo(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """A5 (27/09 đợt 3): "Phòng thủ thuật" → "Thủ thuật/Sàn chậu" ở Cấu hình
    phòng khám. Bảng lịch đọc tên phòng từ đây — phải đổi theo, mã màu giữ."""
    rid = await pool.fetchval(
        "SELECT id::text FROM clinic_room"
        " WHERE clinic_id = $1::uuid AND code = 'KN-THUTHUAT'",
        CLINIC,
    )
    cu = await pool.fetchval("SELECT name FROM clinic_room WHERE id = $1::uuid", rid)
    try:
        await pool.execute(
            "UPDATE clinic_room SET name = 'Thủ thuật/Sàn chậu' WHERE id = $1::uuid",
            rid,
        )
        theo = {d["code"]: d for d in await _goi(pool)}
        assert theo["T1_TT_BS"]["phong"] == "Thủ thuật/Sàn chậu"
        assert theo["T1_TT_DD"]["phong"] == "Thủ thuật/Sàn chậu"
        assert theo["T1_TT_BS"]["ma_phong"] == "KN-THUTHUAT"
    finally:
        await pool.execute(
            "UPDATE clinic_room SET name = $2 WHERE id = $1::uuid", rid, cu
        )


async def test_vi_tri_khong_gan_phong_giu_chu_cu(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Vị trí không gắn phòng (hoặc phòng đã tắt) → rơi về chữ `v.phong`."""
    ma = f"T-{uuid.uuid4().hex[:6]}"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, phong, sort)"
        " VALUES ($1::uuid, $2, 'Không phòng', 'Chữ cũ', 998)",
        CLINIC,
        ma,
    )
    moi = [d for d in await _goi(pool) if d["code"] == ma]
    assert moi[0]["phong"] == "Chữ cũ" and moi[0]["ma_phong"] == ""


async def test_vi_tri_moi_them_trong_database_hien_ngay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Quản lý thêm một vị trí → bảng lịch có hàng mới, không ai sửa TSX."""
    ma = f"T-{uuid.uuid4().hex[:6]}"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, tang, phong, sort)"
        " VALUES ($1::uuid, $2, 'Vị trí mới', 'Tầng 3', 'Phòng mới', 999)",
        CLINIC,
        ma,
    )
    moi = [d for d in await _goi(pool) if d["code"] == ma]
    assert moi == [
        {
            "code": ma,
            "ten": "Vị trí mới",
            "ten_ngan": "Vị trí mới",
            "tang": "Tầng 3",
            "phong": "Phòng mới",
            "ma_phong": "",
            "nhom": "DIEU_DUONG",
        }
    ]
