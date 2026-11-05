"""Chặng 2 — sổ thu hộ bàn xét nghiệm (kế hoạch 4.4, ca biên mục 7, "Xong chặng khi").

Bất biến ép ở Postgres (SO-LUAT Phần 6): một việc một ghi nhận còn hiệu lực (unique
có điều kiện), `so_tien = tien_mat + chuyen_khoan`, hình thức suy ra (CHECK), sổ chỉ
được huỷ (trigger so đủ cột mới), hoàn chỉ thêm.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from clinicai.core.clock import hom_nay_vn
from clinicai.services.xet_nghiem import thu_ho
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_khoa_thu_ho_doi_tac_db import (
    _cho_bi_chan_boi,
    _dem_tien_luot,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import Ca, _dung
from tests.services.test_xet_nghiem_nen_db import (
    _ca_doi_tac,
    _chi_dinh,
    _gan,
    _ma,
    _sp,
    _them_dt,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _viec(pool: asyncpg.Pool) -> tuple[Ca, str]:  # noqa: F811
    ca = await _ca_doi_tac(pool)
    a = await _them_dt(pool, ca.bac_si, _ma())
    await _gan(pool, ca.bac_si, a, await _sp(pool, ca.ma_dv), gia_goi_y=550000)
    return ca, await _chi_dinh(pool, ca)


async def _lam(
    pool: asyncpg.Pool,  # noqa: F811
    ham: Any,
    ca: Ca,
    **data: object,
) -> Any:
    async with pool.acquire() as conn, conn.transaction():
        return await ham(conn, ca.bac_si, dict(data))


async def _tien_phong_kham(pool: asyncpg.Pool, oid: str) -> dict[str, int]:  # noqa: F811
    """Đếm 4 bảng tiền phòng khám của lượt — dùng lại hàm của test khoá chặng 0."""
    v = await pool.fetchval(
        "SELECT visit_id::text FROM service_order WHERE id = $1::uuid", oid
    )
    return await _dem_tien_luot(pool, str(v))


async def _so(pool: asyncpg.Pool, ngay: object) -> list[asyncpg.Record]:  # noqa: F811
    return list(
        await pool.fetch(thu_ho.SO_THEO_NGAY_SQL, CLINIC, ngay, ngay, None, None, None)
    )


async def test_xong_chang_2_tm_ck_hom_qua_hoan_hom_nay(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    """Ghi 150k TM + 200k CK (lệch giá gợi ý 550k) "hôm qua"; hoàn 350k hôm nay ⇒
    tab ngày hôm qua có dòng thu, tab hôm nay có dòng hoàn âm; tiền phòng khám không
    đổi."""
    ca, oid = await _viec(pool)
    truoc = await _tien_phong_kham(pool, oid)
    tt_id = await _lam(
        pool,
        thu_ho.ghi_nhan,
        ca,
        order_id=oid,
        tien_mat="150.000",
        chuyen_khoan=200000,
        ma_giao_dich="FT2611050001",
    )
    # Dời mốc ghi sang hôm qua (dữ liệu test; trigger sổ cấm sửa nên tắt trong phiên).
    async with pool.acquire() as conn:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute(
            "UPDATE doi_tac_thanh_toan SET ghi_luc = ghi_luc - interval '1 day'"
            " WHERE id = $1::uuid",
            tt_id,
        )
        await conn.execute("SET session_replication_role = origin")
    dong = await pool.fetchrow(
        "SELECT so_tien, tien_mat, chuyen_khoan, hinh_thuc, gia_goi_y, ma_giao_dich"
        " FROM doi_tac_thanh_toan WHERE id = $1::uuid",
        tt_id,
    )
    assert dict(dong) == {
        "so_tien": 350000,
        "tien_mat": 150000,
        "chuyen_khoan": 200000,
        "hinh_thuc": "MIXED",
        "gia_goi_y": 550000,
        "ma_giao_dich": "FT2611050001",
    }
    await _lam(
        pool,
        thu_ho.hoan,
        ca,
        order_id=oid,
        tien_mat=150000,
        chuyen_khoan=200000,
        ly_do="bác sĩ bỏ chỉ định",
    )
    hom_nay = hom_nay_vn()
    qua = [
        r
        for r in await _so(pool, hom_nay - timedelta(days=1))
        if r["service_order_id"] == oid
    ]
    nay = [r for r in await _so(pool, hom_nay) if r["service_order_id"] == oid]
    assert [(r["loai"], r["so_tien"]) for r in qua] == [("THU", 350000)]
    assert [(r["loai"], r["so_tien"]) for r in nay] == [("HOAN", -350000)]
    assert await _tien_phong_kham(pool, oid) == truoc


async def test_0d_va_ck_chua_thay_tien_van_ghi_duoc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, oid = await _viec(pool)
    await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat="0")
    r = await pool.fetchrow(
        "SELECT so_tien, hinh_thuc FROM doi_tac_thanh_toan"
        " WHERE service_order_id = $1::uuid AND huy_luc IS NULL",
        oid,
    )
    assert (r["so_tien"], r["hinh_thuc"]) == (0, "CASH")


async def test_hai_nguoi_cung_ghi_mot_nguoi_409(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Người 1 INSERT chưa commit; người 2 ghi ⇒ chờ unique; người 1 commit ⇒ người 2
    nhận 409 tiếng Việt (KHÔNG nhờ khoá dòng — chỉ mục duy nhất có điều kiện ép)."""
    ca, oid = await _viec(pool)
    conn1 = await pool.acquire()
    try:
        tx = conn1.transaction()
        await tx.start()
        await thu_ho.ghi_dong(
            conn1,
            clinic_id=CLINIC,
            order_id=oid,
            tien_mat=100,
            chuyen_khoan=0,
            staff_id=ca.bac_si.staff_id,
        )
        nguoi_hai = asyncio.create_task(
            _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat=200)
        )
        # Chờ ĐIỀU KIỆN trong DB (người hai bị người một chặn), không chờ giờ.
        await _cho_bi_chan_boi(pool, conn1.get_server_pid())
        await tx.commit()
        with pytest.raises(ConflictError, match="đã có ghi nhận"):
            await nguoi_hai
    finally:
        await pool.release(conn1)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM doi_tac_thanh_toan WHERE service_order_id = $1::uuid"
            " AND huy_luc IS NULL",
            oid,
        )
        == 1
    )


async def test_hoan_qua_so_da_thu_bi_chan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, oid = await _viec(pool)
    await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, chuyen_khoan=300000)
    await _lam(
        pool, thu_ho.hoan, ca, order_id=oid, chuyen_khoan=200000, ly_do="trả bớt"
    )
    with pytest.raises(ConflictError, match="100.000"):
        await _lam(
            pool, thu_ho.hoan, ca, order_id=oid, tien_mat=100001, ly_do="lần hai"
        )


async def test_huy_roi_ghi_lai_huy_sau_hoan_bi_chan(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, oid = await _viec(pool)
    await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat=500000)
    with pytest.raises(ValidationError):
        await _lam(pool, thu_ho.huy, ca, order_id=oid, ly_do="x")
    await _lam(pool, thu_ho.huy, ca, order_id=oid, ly_do="ghi nhầm số")
    await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat=550000)
    await _lam(pool, thu_ho.hoan, ca, order_id=oid, tien_mat=50000, ly_do="giảm giá")
    with pytest.raises(ConflictError, match="hoàn tiền"):
        await _lam(pool, thu_ho.huy, ca, order_id=oid, ly_do="ghi nhầm lần hai")


async def test_so_khong_sua_duoc_cot_moi_hoan_chi_them(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, oid = await _viec(pool)
    tt = await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat=1000)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute(
            "UPDATE doi_tac_thanh_toan SET ma_giao_dich = 'sua' WHERE id = $1::uuid", tt
        )
    h = await _lam(pool, thu_ho.hoan, ca, order_id=oid, tien_mat=1000, ly_do="hoàn đủ")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await pool.execute("DELETE FROM doi_tac_hoan_tien WHERE id = $1::uuid", h)


async def test_db_ep_tach_khop_va_hinh_thuc_suy_ra(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca, oid = await _viec(pool)
    sai = (
        "INSERT INTO doi_tac_thanh_toan (clinic_id, service_order_id, so_tien,"
        " tien_mat, chuyen_khoan, hinh_thuc, ghi_boi)"
        " VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::uuid)"
    )
    for so, tm, ck, ht in [(300, 100, 100, "MIXED"), (100, 100, 0, "TRANSFER")]:
        with pytest.raises(asyncpg.CheckViolationError):
            await pool.execute(sai, CLINIC, oid, so, tm, ck, ht, ca.bac_si.staff_id)


async def test_viec_khong_phai_xet_nghiem_doi_tac_404(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)  # dịch vụ phòng khám, không gán đối tác
    oid = await _chi_dinh(pool, ca)
    with pytest.raises(NotFoundError):
        await _lam(pool, thu_ho.ghi_nhan, ca, order_id=oid, tien_mat=1)


@pytest.mark.parametrize(
    ("tm", "ck"), [(None, None), ("", "  "), ("abc", None), ("-5", None)]
)
def test_o_tien_rac_422(tm: object, ck: object) -> None:
    with pytest.raises(ValidationError):
        thu_ho.doc_hai_so(tm, ck)


def test_hinh_thuc_suy_ra() -> None:
    assert [thu_ho.hinh_thuc_cua(*x) for x in [(1, 0), (0, 1), (1, 1), (0, 0)]] == [
        "CASH",
        "TRANSFER",
        "MIXED",
        "CASH",
    ]
