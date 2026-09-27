"""Số booking + số check-in có ở MỌI khâu khám (Tuyền 27/09/2026).

Hai số nằm trên `appointment` (so_booking cấp lúc đặt, so_tiep_don cấp lúc
check-in). Mỗi khâu đọc qua một câu SQL riêng — sót một câu là màn ấy không có
số. Test đi một lượt thật rồi hỏi từng nguồn: thẻ khách phiếu khám, hàng chờ
bác sĩ, quầy thu, Xem lượt (kèm cờ In phiếu).
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.phieu_kham.mang_sang import doc_dau_phieu
from clinicai.services.cashier_board_service import CashierBoardService
from clinicai.services.luot_kham_doc import BangLuotKham
from clinicai.services.xem_luot_service import XemLuotService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
    _kham_va_chi_dinh,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_hai_so_co_o_moi_nguon_doc(pool: asyncpg.Pool) -> None:  # noqa: F811
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    so = await pool.fetchrow(
        "SELECT a.so_booking, a.so_tiep_don FROM visit v"
        " JOIN appointment a ON a.id = v.appointment_id WHERE v.visit_id = $1::uuid",
        visit,
    )
    assert so is not None
    assert so["so_booking"] is not None and so["so_tiep_don"] is not None
    mong = (so["so_booking"], so["so_tiep_don"])

    # Hàng chờ bác sĩ (bàn khám / phòng dùng chung câu này).
    hang = await BangLuotKham(pool).hang_cho(identity=ca.bac_si, room_id=None)
    [d] = [x for x in hang["hang_cho"] if x["visit_id"] == visit]
    assert (d["so_booking"], d["so_tiep_don"]) == mong

    _con, _don = await _kham_va_chi_dinh(pool, ca, visit)
    async with pool.acquire() as conn:
        dau = await doc_dau_phieu(conn, clinic_id=CLINIC, visit_id=visit)
    tk = dau["the_khach"]
    assert (tk["so_booking"], tk["so_tiep_don"]) == mong

    b = await CashierBoardService(pool).board(identity=ca.le_tan, modes=["dich_vu"])
    [q] = [x for x in b["items"] if x["visit_id"] == visit]
    assert (q["so_booking"], q["so_tiep_don"]) == mong

    xem = await XemLuotService(pool).doc(visit_id=visit, identity=ca.bac_si)
    assert (xem["khach"]["so_booking"], xem["khach"]["so_tiep_don"]) == mong
    # Bác sĩ đọc được hồ sơ khám → Xem lượt hiện [In phiếu khám].
    assert xem["in_phieu"] is True


async def test_quay_thu_tien_in_duoc_phieu(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Tuyền 27/09: in phiếu ở MỌI khâu — thu ngân / lễ tân đọc được để in."""
    from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core

    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    await chay_hanh_trinh(pool)
    for ai in (ca.thu_ngan, ca.le_tan):
        xem = await XemLuotService(pool).doc(visit_id=visit, identity=ai)
        assert xem["in_phieu"] is True
        dau = await PhieuKhamService(pool, kiem_quyen=kiem_quyen_core).dau_phieu(
            visit_id=visit, identity=ai
        )
        assert "the_khach" in dau
