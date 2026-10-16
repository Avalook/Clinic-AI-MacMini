"""Hai script SQL đối tác (16/10/2026) phải CHẠY ĐƯỢC trên lược đồ thật — Tuyền chạy
chúng trên staging/prod bằng tay, sai tên cột thì chỉ biết lúc đó."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


async def test_script_kiem_doi_tac_chi_doc_va_chay_duoc(pool: asyncpg.Pool) -> None:
    sql = (SCRIPTS / "kiem-doi-tac-1610.sql").read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        try:
            await conn.execute(sql)  # lỗi cột/bảng → ném
            with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
                await conn.execute("CREATE TEMP TABLE _khong_duoc_ghi (x int)")
        finally:  # kết nối về pool — gỡ chế độ chỉ đọc của phiên
            await conn.execute("RESET default_transaction_read_only")


async def test_script_bat_lai_doi_tac_mac_dinh_khong_doi_gi(pool: asyncpg.Pool) -> None:
    sql = (SCRIPTS / "bat-lai-doi-tac-1610.sql").read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        dem = (
            "SELECT (SELECT count(*) FROM node_definition WHERE lam_ben_ngoai),"
            " (SELECT count(*) FROM service_price WHERE doi_tac_lay_mau),"
            " (SELECT count(*) FROM service_price WHERE billing_owner<>'CLINIC')"
        )
        truoc = tuple(await conn.fetchrow(dem))
        await conn.execute(sql)  # danh sách mã rỗng → không đổi gì
        assert tuple(await conn.fetchrow(dem)) == truoc
