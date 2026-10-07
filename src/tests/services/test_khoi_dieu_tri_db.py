"""Khối 4 "Điều trị" của hồ sơ khám (T6, Tuyền chốt 07/10/2026) — Postgres thật.

Mỗi lần lưu một phiên bản (không đè), hiện bản mới nhất; màn cầm bản cũ → 409;
bảng chỉ thêm (trigger chặn sửa / xoá). Dùng được cả lượt không phiếu.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services import khoi_dieu_tri
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_doi_dich_vu_kham_db import _check_in, _dung

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_moi_lan_luu_mot_phien_ban_hien_ban_moi_nhat(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca)
    bs = ca["bs"]
    assert (await khoi_dieu_tri.doc(pool, identity=bs, visit_id=visit)) == {
        "dieu_tri": None
    }
    a = await khoi_dieu_tri.luu(
        pool, identity=bs, visit_id=visit, cam_nhan="Đỡ đau", van_de_sau="", phien_ban=0
    )
    assert a["dieu_tri"]["phien_ban"] == 1
    b = await khoi_dieu_tri.luu(
        pool,
        identity=bs,
        visit_id=visit,
        cam_nhan="Đỡ đau nhiều",
        van_de_sau="Hơi rát",
        phien_ban=1,
    )
    assert b["dieu_tri"]["phien_ban"] == 2
    moi = await khoi_dieu_tri.doc(pool, identity=bs, visit_id=visit)
    assert moi["dieu_tri"]["cam_nhan"] == "Đỡ đau nhiều"
    assert moi["dieu_tri"]["van_de_sau"] == "Hơi rát"
    assert moi["dieu_tri"]["ghi_boi"]

    # Gửi lại y hệt (tự lưu lặp): không thêm bản rác.
    c = await khoi_dieu_tri.luu(
        pool,
        identity=bs,
        visit_id=visit,
        cam_nhan="Đỡ đau nhiều",
        van_de_sau="Hơi rát",
        phien_ban=2,
    )
    assert c["doi"] is False

    # Màn cầm bản cũ → 409, không đè.
    with pytest.raises(ConflictError):
        await khoi_dieu_tri.luu(
            pool, identity=bs, visit_id=visit, cam_nhan="x", van_de_sau="", phien_ban=1
        )
    rows = await pool.fetch(
        "SELECT phien_ban, cam_nhan FROM luot_dieu_tri_ghi"
        " WHERE visit_id = $1::uuid ORDER BY phien_ban",
        visit,
    )
    assert [(r["phien_ban"], r["cam_nhan"]) for r in rows] == [
        (1, "Đỡ đau"),
        (2, "Đỡ đau nhiều"),
    ]


async def test_bang_chi_them_khong_sua_khong_xoa(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca)
    await khoi_dieu_tri.luu(
        pool,
        identity=ca["bs"],
        visit_id=visit,
        cam_nhan="a",
        van_de_sau="",
        phien_ban=0,
    )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "UPDATE luot_dieu_tri_ghi SET cam_nhan = 'sửa' WHERE visit_id = $1::uuid",
            visit,
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "DELETE FROM luot_dieu_tri_ghi WHERE visit_id = $1::uuid", visit
        )


async def test_ma_luot_rac_bao_loi_ro(pool: asyncpg.Pool) -> None:  # noqa: F811
    from clinicai.api.exceptions import ValidationError

    ca = await _dung(pool)
    with pytest.raises(ValidationError):
        await khoi_dieu_tri.luu(
            pool,
            identity=ca["bs"],
            visit_id="khong-phai-uuid",
            cam_nhan="x",
            van_de_sau="",
            phien_ban=0,
        )
