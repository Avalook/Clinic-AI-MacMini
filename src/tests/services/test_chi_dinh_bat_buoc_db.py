"""Dịch vụ BẮT BUỘC (Tuyền 25/09/2026 — P2).

Bác sĩ tick "Bắt buộc" khi chỉ định → quầy thu không bỏ được dịch vụ ấy. Muốn bỏ
phải quay lại người chỉ định bỏ tick (chỉ khi chưa thu tiền). Mặc định KHÔNG tick.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.lenh_kham_core import LuotKhamConflictError
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.service_selection_service import cho_khach_quyet
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    Ca,
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _chi_dinh_bat_buoc(
    pool: asyncpg.Pool,  # noqa: F811
    ca: Ca,
    visit: str,
    bat_buoc: bool,
) -> str:
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    await LuotKhamService(pool).start_consultation(
        consultation_id=con, identity=ca.bac_si
    )
    kq = await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],
        identity=ca.bac_si,
        idempotency_key=_khoa(),
        bat_buoc_codes=[ca.ma_dv] if bat_buoc else [],
    )
    return str(kq["order_ids"][0])


async def _bat_buoc(pool: asyncpg.Pool, order: str) -> bool:  # noqa: F811
    return bool(
        await pool.fetchval(
            "SELECT bat_buoc FROM service_order WHERE id = $1::uuid", order
        )
    )


async def test_mac_dinh_khong_bat_buoc_quay_bo_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh_bat_buoc(pool, ca, visit, bat_buoc=False)
    assert not await _bat_buoc(pool, order)
    await _chon(pool, ca, visit, [])  # quầy thu bỏ — được


async def test_bat_buoc_quay_thu_khong_bo_duoc_bo_tick_thi_bo_duoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh_bat_buoc(pool, ca, visit, bat_buoc=True)
    assert await _bat_buoc(pool, order)
    async with pool.acquire() as conn:
        cho = (await cho_khach_quyet(conn, CLINIC, [visit]))[visit]
    assert [c["bat_buoc"] for c in cho["chi_dinh"]] == [True]

    with pytest.raises(LuotKhamConflictError) as loi:
        await _chon(pool, ca, visit, [])
    assert loi.value.error_code == "SERVICE_REQUIRED"

    await ChiDinhService(pool).doi_bat_buoc(
        order_id=order, bat_buoc=False, identity=ca.bac_si
    )
    assert not await _bat_buoc(pool, order)
    ev = await pool.fetchval(
        "SELECT count(*) FROM domain_event WHERE event_type ="
        " 'service_order.required_changed' AND aggregate_id = $1::uuid",
        order,
    )
    assert ev == 1
    await _chon(pool, ca, visit, [])


async def test_da_thu_tien_thi_khong_doi_bat_buoc(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    order = await _chi_dinh_bat_buoc(pool, ca, visit, bat_buoc=True)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    with pytest.raises(LuotKhamConflictError) as loi:
        await ChiDinhService(pool).doi_bat_buoc(
            order_id=order, bat_buoc=False, identity=ca.bac_si
        )
    assert loi.value.error_code == "SERVICE_ALREADY_PAID"


@pytest.mark.parametrize("rac", ["", "abc", "1; DROP TABLE x", "0" * 40])
async def test_ma_chi_dinh_rac_khong_500(
    pool: asyncpg.Pool,  # noqa: F811
    rac: str,
) -> None:
    ca = await _dung(pool)
    with pytest.raises(ValidationError):
        await ChiDinhService(pool).doi_bat_buoc(
            order_id=rac, bat_buoc=True, identity=ca.bac_si
        )


async def test_ma_chi_dinh_khong_ton_tai(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    with pytest.raises(NotFoundError):
        await ChiDinhService(pool).doi_bat_buoc(
            order_id=str(uuid.uuid4()), bat_buoc=True, identity=ca.bac_si
        )
