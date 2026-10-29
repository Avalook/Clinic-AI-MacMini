"""Chỉ định được khi lượt còn mở — máy tự mở phiên khám (chốt 29/10/2026).

Log prod 22–28/10: 46 lần "Phiên khám chưa bắt đầu hoặc đã kết thúc" khi bác sĩ
chỉ định; 28/30 phiên là phiên ĐÃ bấm "Khám xong" (khám xong mới nhớ chỉ định
thêm). Nay: khách chưa check-out → phiên tự mở lại rồi chỉ định; phiên chưa bắt
đầu → tự bắt đầu; khách đã check-out → vẫn chặn (không tự mở cả lượt).
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.chi_dinh_service import ChiDinhService
from clinicai.services.luot_kham_service import LuotKhamService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dong_luot,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _trang_thai(pool: asyncpg.Pool, con: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval("SELECT status FROM consultation WHERE id = $1::uuid", con)
    )


async def _ke(pool: asyncpg.Pool, ca: object, con: str) -> dict[str, object]:  # noqa: F811
    return await ChiDinhService(pool).dat_chi_dinh(
        consultation_id=con,
        service_codes=[ca.ma_dv],  # type: ignore[attr-defined]
        identity=ca.bac_si,  # type: ignore[attr-defined]
        idempotency_key=str(uuid.uuid4()),
    )


async def test_kham_xong_roi_chi_dinh_them_thi_tu_mo_lai_phien(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, _order = await _kham_va_chi_dinh(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=str(uuid.uuid4())
    )
    assert await _trang_thai(pool, con) == "completed"

    kq = await _ke(pool, ca, con)
    assert kq["order_ids"]
    # Khách về "đang khám" — bác sĩ bấm Khám xong lại như thường.
    assert await _trang_thai(pool, con) == "in_progress"


async def test_phien_chua_bat_dau_chi_dinh_thi_tu_bat_dau(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con = str(
        await pool.fetchval(
            "SELECT id::text FROM consultation WHERE visit_id = $1::uuid"
            " AND kind = 'PRIMARY'",
            visit,
        )
    )
    assert await _trang_thai(pool, con) == "queued"
    kq = await _ke(pool, ca, con)
    assert kq["order_ids"]
    assert await _trang_thai(pool, con) == "in_progress"


async def test_khach_da_check_out_thi_van_chan(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    con, _order = await _kham_va_chi_dinh(pool, ca, visit)
    await LuotKhamService(pool).kham_xong(
        consultation_id=con, identity=ca.bac_si, idempotency_key=str(uuid.uuid4())
    )
    await _dong_luot(pool, visit)
    with pytest.raises(ConflictError):
        await _ke(pool, ca, con)
    assert await _trang_thai(pool, con) == "completed"
