"""Diễn tập hai script dọn lô mẫu trên DB test (Tuyền 27/10/2026).

`scripts/kho-dua-lo-mau-ve-0.sql` đưa lô `DEMO1709-*` về 0 bằng dòng ADJUST;
`scripts/kho-hoan-tac-lo-mau-ve-0.sql` cộng lại đúng số đã bớt. Cả hai chạy bằng
psql thật (có biến `ket_thuc`), đúng cách người vận hành chạy trên prod.

Bất biến:
  S1  thử khô (ROLLBACK) không đổi gì;
  S2  chạy thật đưa MỌI lô mẫu về 0, mỗi lô một dòng sổ ADJUST, lô khác y nguyên;
  S3  chạy lại không ghi thêm;
  S4  lùi cộng đủ đúng số đã bớt; lùi lần hai không cộng thêm;

Chỉ đụng lô mang tiền tố riêng của bài (`DEMO1709-T…`) — seed không có lô
DEMO1709 nên các bài khác cùng worker không thấy gì đổi.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest

from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
DUA_VE_0 = _SCRIPTS / "kho-dua-lo-mau-ve-0.sql"
HOAN_TAC = _SCRIPTS / "kho-hoan-tac-lo-mau-ve-0.sql"


def _psql(script: Path, ket_thuc: str) -> subprocess.CompletedProcess[str]:
    exe = shutil.which("psql")
    assert exe, "thiếu psql — brew install libpq"
    return subprocess.run(
        [
            exe,
            os.environ["DATABASE_URL_TEST"],
            "-v",
            "ON_ERROR_STOP=1",
            "-v",
            f"ket_thuc={ket_thuc}",
            "-q",
            "-f",
            str(script),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class Kho:
    def __init__(self, pool: asyncpg.Pool, mau: dict[str, int], khac: str) -> None:
        self.pool = pool
        self.mau = mau  # batch_code → tồn ban đầu
        self.khac = khac  # mã lô KHÔNG phải lô mẫu

    async def ton(self, ma: str) -> int:
        return int(
            await self.pool.fetchval(
                "SELECT quantity_on_hand FROM drug_batch WHERE batch_code = $1", ma
            )
        )

    async def dong_so(self) -> list[asyncpg.Record]:
        """Dòng sổ của MỌI lô bài này tạo (lô mẫu + lô khác), cũ → mới."""
        return list(
            await self.pool.fetch(
                "SELECT b.batch_code, t.quantity, t.reason, t.txn_type"
                "  FROM inventory_txn t JOIN drug_batch b ON b.id = t.drug_batch_id"
                " WHERE b.batch_code = ANY($1::text[]) ORDER BY t.performed_at, t.id",
                [*self.mau, self.khac],
            )
        )

    async def su_kien(self) -> int:
        return int(
            await self.pool.fetchval(
                "SELECT count(*) FROM event_log e"
                " JOIN drug_batch b ON b.id = e.aggregate_id"
                " WHERE e.event_type = 'pharmacy.adjusted'"
                " AND b.batch_code = ANY($1::text[])",
                list(self.mau),
            )
        )


async def _lo(
    pool: asyncpg.Pool, loc: str, thuoc: str, ma: str, ton: int
) -> asyncpg.Record:
    return await pool.fetchrow(
        "INSERT INTO drug_batch (clinic_id, location_id, drug_catalog_id,"
        " batch_code, expiry_date, quantity_on_hand, unit)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, '2099-12-31', $5, 'viên')"
        " RETURNING id::text, batch_code",
        CLINIC,
        loc,
        thuoc,
        ma,
        ton,
    )


@pytest.fixture
async def kho(pool: asyncpg.Pool) -> Kho:
    duoi = uuid.uuid4().hex[:8]
    loc = await pool.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
        " AND is_active ORDER BY created_at, id LIMIT 1",
        CLINIC,
    )
    # Script đòi một Quản lý đang hoạt động để đứng tên dòng điều chỉnh tay.
    sid = await pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, 'MANAGEMENT', $2::uuid, true) RETURNING id::text",
        f"Quản lý thử {duoi}",
        loc,
    )
    await pool.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, 'MANAGEMENT', true)"
        " ON CONFLICT (clinic_id, staff_id, role) DO NOTHING",
        CLINIC,
        sid,
    )
    thuoc = await pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
        " VALUES ($1::uuid, $2, $2, 1000) RETURNING id::text",
        CLINIC,
        f"Thuốc lô mẫu {duoi}",
    )
    mau = {
        f"DEMO1709-T{duoi}-A": 40,
        f"DEMO1709-T{duoi}-B": 25,
        f"DEMO1709-T{duoi}-C": 0,
    }
    for ma, ton in mau.items():
        await _lo(pool, loc, thuoc, ma, ton)
    khac = f"LO-THAT-{duoi}"
    await _lo(pool, loc, thuoc, khac, 7)
    return Kho(pool, mau, khac)


async def _ton_tat_ca(k: Kho) -> dict[str, int]:
    return {ma: await k.ton(ma) for ma in (*k.mau, k.khac)}


async def test_thu_kho_khong_ghi_gi(kho: Kho) -> None:
    truoc = await _ton_tat_ca(kho)
    r = _psql(DUA_VE_0, "ROLLBACK")
    assert r.returncode == 0, r.stderr
    assert await _ton_tat_ca(kho) == truoc
    assert await kho.dong_so() == []
    assert await kho.su_kien() == 0


async def test_chay_that_ve_0_chay_lai_khong_ghi_them(kho: Kho) -> None:
    r = _psql(DUA_VE_0, "COMMIT")
    assert r.returncode == 0, r.stderr
    assert await _ton_tat_ca(kho) == {**dict.fromkeys(kho.mau, 0), kho.khac: 7}

    # Hai lô có tồn → hai dòng ADJUST âm đúng số; lô đã 0 và lô khác không có dòng.
    dong = {d["batch_code"]: d for d in await kho.dong_so()}
    ma_a, ma_b, ma_c = kho.mau
    assert set(dong) == {ma_a, ma_b}
    assert (dong[ma_a]["quantity"], dong[ma_b]["quantity"]) == (-40, -25)
    assert {d["txn_type"] for d in dong.values()} == {"ADJUST"}
    assert await kho.su_kien() == 2
    assert await kho.ton(ma_c) == 0

    r = _psql(DUA_VE_0, "COMMIT")
    assert r.returncode == 0, r.stderr
    assert len(await kho.dong_so()) == 2
    assert await kho.su_kien() == 2


async def test_lui_cong_du_lui_lan_hai_khong_cong_them(kho: Kho) -> None:
    ban_dau = await _ton_tat_ca(kho)
    assert _psql(DUA_VE_0, "COMMIT").returncode == 0

    r = _psql(HOAN_TAC, "ROLLBACK")  # thử khô lùi cũng không ghi
    assert r.returncode == 0, r.stderr
    assert len(await kho.dong_so()) == 2

    r = _psql(HOAN_TAC, "COMMIT")
    assert r.returncode == 0, r.stderr
    assert await _ton_tat_ca(kho) == ban_dau
    dong = await kho.dong_so()
    assert len(dong) == 4  # sổ chỉ thêm: 2 dòng gốc giữ nguyên + 2 dòng lùi
    assert sum(d["quantity"] for d in dong) == 0

    r = _psql(HOAN_TAC, "COMMIT")
    assert r.returncode == 0, r.stderr
    assert await _ton_tat_ca(kho) == ban_dau
    assert len(await kho.dong_so()) == 4
