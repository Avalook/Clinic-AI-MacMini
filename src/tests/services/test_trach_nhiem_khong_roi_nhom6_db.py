"""NHÓM 6 — rà quyền + trách nhiệm không rơi (24/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_trach_nhiem_khong_roi_nhom6_db.py

* Dược sĩ thu tiền thuốc (bảng "màn mặc định theo vai" Tuyền chốt 23/09).
* Một bước tự động hỏng hẳn (DEAD) → chuông người trực (trưởng ca, quản lý):
  với khối Hành trình, DEAD nghĩa là một khách đứng kẹt.
* Đã trả tiền mà chưa có phòng → bảng hành trình nói thẳng.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.identity import ClinicRole
from clinicai.events import worker as nguoi_dua_tin
from clinicai.events.catalogue import HANH_TRINH
from clinicai.services.bang_hanh_trinh_service import BangHanhTrinhService
from clinicai.services.payment_service import allowed_kinds
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _chon,
    _dung,
    _kham_va_chi_dinh,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def test_duoc_si_thu_tien_thuoc_khong_thu_tien_dich_vu() -> None:
    assert allowed_kinds(ClinicRole.PHARMACIST) == frozenset({"thuoc"})


async def test_thu_ngan_da_thu_ma_chua_co_phong_bang_noi_thang(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
) -> None:
    import clinicai.services.bang_hanh_trinh_service as bht

    monkeypatch.setattr(bht, "_TRAN_LUOT", 100_000)
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.thu_ngan)  # thu ngân không có quyền điều phối
    await chay_hanh_trinh(pool)
    b = await BangHanhTrinhService(pool).hom_nay(identity=ca.le_tan)
    [luot] = [x for x in b["luot"] if x["visit_id"] == visit]
    assert any(c.startswith("ĐÃ TRẢ TIỀN — chờ xếp phòng") for c in luot["con_cho"])


async def test_buoc_tu_dong_hong_han_thi_reo_nguoi_truc(
    pool: asyncpg.Pool,  # noqa: F811
    monkeypatch: Any,
) -> None:
    ca = await _dung(pool)

    async def hong(conn: asyncpg.Connection, su_kien: Any) -> None:
        raise RuntimeError("hỏng thử")

    monkeypatch.setitem(nguoi_dua_tin._BO_XU_LY, HANH_TRINH, hong)
    monkeypatch.setattr(nguoi_dua_tin, "SO_LAN_THU_TOI_DA", 1)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    # _check_in đã chạy một vòng (lần thử 1 → DEAD vì trần 1 lần).
    ev = await pool.fetchval(
        "SELECT e.event_id::text FROM domain_event e"
        " WHERE e.event_type = 'visit.checked_in' AND e.aggregate_id = $1::uuid",
        visit,
    )
    assert (
        await pool.fetchval(
            "SELECT status FROM event_delivery WHERE event_id = $1::uuid"
            " AND consumer = $2",
            ev,
            HANH_TRINH,
        )
        == "DEAD"
    )
    vai = {
        r["vai_nhan"]
        for r in await pool.fetch(
            "SELECT vai_nhan FROM thong_bao WHERE nguon = 'su_kien_hong'"
            " AND nguon_id = $1",
            f"{HANH_TRINH}:{ev}",
        )
    }
    assert vai == {"TRUONG_CA", "MANAGEMENT"}
    # Dọn: không để dòng DEAD chặn sự kiện sau của lượt thử này.
    await pool.execute(
        "UPDATE event_delivery SET status = 'DONE', processed_at = now()"
        " WHERE event_id = $1::uuid"
        " AND consumer = $2",
        ev,
        HANH_TRINH,
    )
    assert uuid.UUID(ev)
