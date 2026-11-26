"""Khối "Đơn vị con và tính số ngày dùng hết thuốc" của Danh mục & giá (Tuyền 26/11)."""

from __future__ import annotations

from decimal import Decimal

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.thuoc import cach_dung_db, don_vi_con
from tests.services.test_phieu_kham_db import CLINIC, _nguoi, pool  # noqa: F401
from tests.services.test_thuoc_cach_dung_db import _dong, _thuoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _hop_30(conn: asyncpg.Connection) -> str:
    t = await _thuoc(conn, "Hộp thử đơn vị con", "hộp", 300000)
    await conn.execute(
        "UPDATE drug_catalog SET cach_dung = 'Ngày 2 viên, sáng 1, tối 1, sau ăn'"
        " WHERE id = $1::uuid",
        t,
    )
    return t


async def test_khai_don_vi_con_xem_truoc_va_tinh_ngay(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "PHARMACIST")
        bs = await _nguoi(conn, "DOCTOR")
        t = await _hop_30(conn)

    truoc = await don_vi_con.doc_don_vi_con(pool, identity=ql, thuoc_id=t)
    assert truoc["don_vi_con"] is None and truoc["so_con"] is None
    assert "Khai “1 hộp có bao nhiêu viên”" in truoc["xem_truoc"]

    sau = await don_vi_con.luu_don_vi_con(
        pool,
        identity=ql,
        thuoc_id=t,
        don_vi_con="viên",
        so_con=Decimal(30),
        gia_con=None,
    )
    assert (sau["don_vi_con"], sau["so_con"]) == ("viên", Decimal(30))
    assert sau["gia_con_tu_tinh"] == 10000 and sau["gia_con"] is None
    assert sau["xem_truoc"].endswith("1 hộp (30 viên) dùng được 15 ngày.")

    # Bàn khám: kê 1 hộp, cách dùng lấy chữ danh mục → đủ 15 ngày.
    kq = await cach_dung_db.tinh_don(
        pool,
        identity=bs,
        visit_id=None,
        dong=[_dong(t, "1", "hộp", "Ngày 2 viên, sáng 1, tối 1, sau ăn")],
        kinh_lan_cuoi=None,
        chu_ky=None,
    )
    assert kq["dong"][0]["so_ngay"] == 15


@pytest.mark.parametrize(
    ("con", "so"),
    [("viên", None), (None, Decimal(30)), ("hộp 30 viên", Decimal(30))],
)
async def test_tu_choi_khai_thieu_hoac_ten_co_so(
    pool: asyncpg.Pool,  # noqa: F811
    con: str | None,
    so: Decimal | None,
) -> None:
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, "PHARMACIST")
        t = await _hop_30(conn)
    with pytest.raises(ValidationError):
        await don_vi_con.luu_don_vi_con(
            pool, identity=ql, thuoc_id=t, don_vi_con=con, so_con=so, gia_con=None
        )
    assert CLINIC
