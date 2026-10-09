"""Chữ cột Phòng / Tầng của vị trí KHÔNG gắn phòng thật (09/10/2026).

Phòng khám: *"Vị trí Trưởng ca trên lịch làm việc: cột Phòng đang trống; thêm
tên 'Quản lý ca khám' vào cột Phòng, đổi luôn ở cột Tầng."* Không tạo phòng
thật (Trưởng ca không nhận khách, dùng chung mọi cơ sở) — màn sửa vị trí ghi
được `vi_tri_lam_viec.phong` / `.tang`, bảng lịch (`/me/vi-tri-hom-nay`) in chữ
ấy khi vị trí không gắn phòng; gắn phòng thật thì vẫn in tên + tầng phòng thật.
"""

from __future__ import annotations

from typing import Any, cast

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import StaffIdentity
from clinicai.api.v1.routers.identity import vi_tri_hom_nay
from clinicai.services.day_noi_service import DayNoiService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

CHU = "Quản lý ca khám"


async def _ql_va_phong(pool: asyncpg.Pool) -> tuple[StaffIdentity, asyncpg.Record]:  # noqa: F811
    async with pool.acquire() as conn:
        phong = await conn.fetchrow(
            "SELECT id::text AS id, name, floor, location_id::text AS loc"
            "  FROM clinic_room WHERE clinic_id = $1::uuid AND is_active"
            " ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
        assert phong is not None
        return await _nguoi(conn, phong["loc"], "MANAGEMENT"), phong


async def _dong_lich(
    pool: asyncpg.Pool,  # noqa: F811
    ql: StaffIdentity,
    vi_tri_id: str,
) -> dict[str, Any]:
    code = await pool.fetchval(
        "SELECT code FROM vi_tri_lam_viec WHERE id = $1::uuid", vi_tri_id
    )
    kq = await vi_tri_hom_nay(identity=ql, pool=pool)
    danh_muc = cast(list[dict[str, Any]], kq["danh_muc"])
    return next(d for d in danh_muc if d["code"] == code)


async def test_vi_tri_khong_gan_phong_hien_chu_phong_va_tang(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ql, _ = await _ql_va_phong(pool)
    svc = DayNoiService(pool)
    vid = (
        await svc.tao_vi_tri(identity=ql, ten="Trưởng ca thử chữ", nhom_nghe="CHUNG")
    )["id"]
    try:
        assert (await _dong_lich(pool, ql, vid))["phong"] == ""

        kq = await svc.sua_vi_tri(
            identity=ql, vi_tri_id=vid, phong=f"  {CHU}  ", tang=CHU
        )
        assert (kq["phong"], kq["tang"]) == (CHU, CHU), "cắt khoảng trắng"
        dong = await _dong_lich(pool, ql, vid)
        assert (dong["phong"], dong["tang"]) == (CHU, CHU)

        # Màn sửa đọc lại được chữ đang lưu.
        dl = await svc.doc(identity=ql)
        vt = next(v for v in dl["vi_tri"] if v["id"] == vid)
        assert (vt["phong"], vt["tang"], vt["room_id"]) == (CHU, CHU, None)

        # Sửa trường khác (None = giữ nguyên) không xoá chữ, không gắn phòng.
        await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, ten="Trưởng ca thử 2")
        r = await pool.fetchrow(
            "SELECT ten, phong, tang, room_id FROM vi_tri_lam_viec WHERE id = $1::uuid",
            vid,
        )
        assert (r["ten"], r["phong"], r["tang"], r["room_id"]) == (
            "Trưởng ca thử 2",
            CHU,
            CHU,
            None,
        )

        # Chuỗi trắng = xoá chữ (NULL), bảng lịch về "".
        await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, phong="   ", tang="")
        r = await pool.fetchrow(
            "SELECT phong, tang FROM vi_tri_lam_viec WHERE id = $1::uuid", vid
        )
        assert (r["phong"], r["tang"]) == (None, None)
        dong = await _dong_lich(pool, ql, vid)
        assert (dong["phong"], dong["tang"]) == ("", "")

        # Quá dài → từ chối, không ghi gì.
        with pytest.raises(ValidationError):
            await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, phong="x" * 121)
        with pytest.raises(ValidationError):
            await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, tang="x" * 61)
        assert (
            await pool.fetchval(
                "SELECT phong FROM vi_tri_lam_viec WHERE id = $1::uuid", vid
            )
            is None
        )
    finally:
        await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, is_active=False)


async def test_vi_tri_gan_phong_that_van_hien_ten_phong_that(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ql, phong = await _ql_va_phong(pool)
    svc = DayNoiService(pool)
    vid = (
        await svc.tao_vi_tri(
            identity=ql, ten="Vị trí có phòng", nhom_nghe="CHUNG", room_id=phong["id"]
        )
    )["id"]
    try:
        await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, phong=CHU, tang=CHU)
        dong = await _dong_lich(pool, ql, vid)
        assert dong["phong"] == phong["name"]
        assert dong["tang"] == (phong["floor"] or CHU)
        assert (
            await pool.fetchval(
                "SELECT room_id::text FROM vi_tri_lam_viec WHERE id = $1::uuid", vid
            )
            == phong["id"]
        ), "ghi chữ không gỡ phòng thật"
    finally:
        await svc.sua_vi_tri(identity=ql, vi_tri_id=vid, is_active=False)
