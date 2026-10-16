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


class _HoanLaiError(Exception):
    pass


async def test_script_bat_lai_doi_tac_chi_bat_dung_ma_da_chot(
    pool: asyncpg.Pool,
) -> None:
    """Chỉ chụp phim ngoài + HPV/Thinprep (Tuyền 16/10). Chạy trong giao dịch rồi
    hoàn lại — DB test dùng chung, cờ đối tác lật thì test khác lệch."""
    sql = (SCRIPTS / "bat-lai-doi-tac-1610.sql").read_text(encoding="utf-8")
    than = "\n".join(
        d for d in sql.splitlines() if d.strip() not in {"BEGIN;", "COMMIT;"}
    )
    hpv = ["CLS_HPV", "CLS_THINPREP", "KV_SP000169", "KV_SP000170"]
    async with pool.acquire() as conn:
        khac_truoc = await conn.fetchval(
            "SELECT count(*) FROM service_price"
            " WHERE doi_tac_lay_mau AND NOT service_code = ANY($1::text[])",
            hpv,
        )
        with pytest.raises(_HoanLaiError):
            async with conn.transaction():
                await conn.execute(than)
                assert await conn.fetchval(
                    "SELECT bool_and(lam_ben_ngoai) FROM node_definition"
                    " WHERE code = 'DICHVU-HINHANH-NGOAI'"
                ) in (True, None)
                assert not await conn.fetchval(
                    "SELECT count(*) FROM service_price WHERE \"group\" = 'dich_vu'"
                    " AND service_code = ANY($1::text[]) AND NOT doi_tac_lay_mau",
                    hpv,
                )
                # Không lật dịch vụ nào ngoài danh sách.
                assert (
                    await conn.fetchval(
                        "SELECT count(*) FROM service_price"
                        " WHERE doi_tac_lay_mau AND NOT service_code = ANY($1::text[])",
                        hpv,
                    )
                    == khac_truoc
                )
                raise _HoanLaiError
