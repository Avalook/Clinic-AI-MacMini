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


async def test_script_go_dich_vu_thua_phong_doi_tac(pool: asyncpg.Pool) -> None:
    """Phòng đối tác chỉ còn dịch vụ đối tác; dịch vụ đối tác giữ nguyên; dịch vụ
    thường vẫn gắn ở phòng thường. Chạy trong giao dịch rồi hoàn lại."""
    sql = (SCRIPTS / "go-dich-vu-thua-phong-doi-tac-1610.sql").read_text(
        encoding="utf-8"
    )
    than = "\n".join(
        d for d in sql.splitlines() if d.strip() not in {"BEGIN;", "COMMIT;"}
    )
    la_doi_tac = (
        "(sp.billing_owner = 'EXTERNAL_PARTNER' OR sp.doi_tac_lay_mau"
        " OR coalesce(nd.lam_ben_ngoai, false))"
    )
    dem = f"""
        SELECT count(*) FILTER (WHERE {la_doi_tac}) AS doi_tac,
               count(*) FILTER (WHERE NOT coalesce({la_doi_tac}, false)) AS thuong
          FROM clinic_room_service rs
          JOIN clinic_room r ON r.id = rs.room_id AND r.la_doi_tac
          LEFT JOIN service_price sp ON sp.clinic_id = rs.clinic_id
               AND sp.service_code = rs.service_code AND sp."group" = 'dich_vu'
          LEFT JOIN node_definition nd ON nd.clinic_id = sp.clinic_id
               AND nd.code = sp.node_code"""
    # Tình huống 01/10: một dịch vụ thường (đang gắn ở phòng thường) bị gắn vào mọi
    # phòng đối tác.
    gan_thua = """
        INSERT INTO clinic_room_service (clinic_id, room_id, service_code)
        SELECT r.clinic_id, r.id, x.service_code
          FROM clinic_room r
          JOIN LATERAL (
               SELECT rs.service_code FROM clinic_room_service rs
                 JOIN clinic_room r2 ON r2.id = rs.room_id
                  AND r2.is_active AND NOT r2.la_doi_tac
                 JOIN service_price sp ON sp.clinic_id = rs.clinic_id
                  AND sp.service_code = rs.service_code
                  AND sp.billing_owner = 'CLINIC'
                WHERE rs.clinic_id = r.clinic_id LIMIT 1) x ON true
         WHERE r.la_doi_tac
        ON CONFLICT DO NOTHING"""
    async with pool.acquire() as conn:
        with pytest.raises(_HoanLaiError):
            async with conn.transaction():  # ném ở cuối → hoàn lại hết
                await conn.execute(gan_thua)
                truoc = await conn.fetchrow(dem)
                assert truoc["thuong"] > 0
                await conn.execute(than)
                sau = await conn.fetchrow(dem)
                assert sau["thuong"] == 0
                assert sau["doi_tac"] == truoc["doi_tac"]
                raise _HoanLaiError


async def test_script_go_dich_vu_doi_tac_khoi_phong_thuong(
    pool: asyncpg.Pool,
) -> None:
    """Dịch vụ thuộc nhóm việc làm bên ngoài bị gắn vào phòng thường (01/10) → gỡ khỏi
    phòng thường, giữ ở phòng đối tác; dịch vụ thường không đụng. Hoàn lại cuối."""
    sql = (SCRIPTS / "go-dich-vu-doi-tac-khoi-phong-thuong-1610.sql").read_text(
        encoding="utf-8"
    )
    than = "\n".join(
        d for d in sql.splitlines() if d.strip() not in {"BEGIN;", "COMMIT;"}
    )
    async with pool.acquire() as conn:
        with pytest.raises(_HoanLaiError):
            async with conn.transaction():  # ném ở cuối → hoàn lại hết
                dv = await conn.fetchrow(
                    """
                    SELECT sp.clinic_id, sp.service_code, sp.node_code
                      FROM service_price sp
                     WHERE sp."group" = 'dich_vu' AND sp.active
                       AND sp.node_code IS NOT NULL AND NOT sp.doi_tac_lay_mau
                     ORDER BY sp.service_code LIMIT 1
                    """
                )
                assert dv is not None
                # Cô lập: chỉ dịch vụ đang thử là việc đối tác làm trọn.
                await conn.execute("UPDATE service_price SET doi_tac_lay_mau = false")
                await conn.execute("UPDATE node_definition SET lam_ben_ngoai = false")
                await conn.execute(
                    "UPDATE node_definition SET lam_ben_ngoai = true"
                    " WHERE clinic_id = $1 AND code = $2",
                    dv["clinic_id"],
                    dv["node_code"],
                )
                # Gắn dịch vụ ấy vào MỌI phòng đang bật (thường + đối tác) như 01/10.
                await conn.execute(
                    "INSERT INTO clinic_room_service (clinic_id, room_id, service_code)"
                    " SELECT r.clinic_id, r.id, $2 FROM clinic_room r"
                    " WHERE r.clinic_id = $1 AND r.is_active ON CONFLICT DO NOTHING",
                    dv["clinic_id"],
                    dv["service_code"],
                )
                # Như staging: phòng đối tác có nhóm việc ấy (dịch vụ cùng nhóm không
                # gắn tên phòng nào vẫn làm được ở phòng đối tác).
                await conn.execute(
                    "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
                    " SELECT r.clinic_id, r.id, $2 FROM clinic_room r"
                    " WHERE r.clinic_id = $1 AND r.is_active AND r.la_doi_tac"
                    " ON CONFLICT DO NOTHING",
                    dv["clinic_id"],
                    dv["node_code"],
                )
                dem = (
                    "SELECT count(*) FILTER (WHERE NOT r.la_doi_tac) thuong,"
                    " count(*) FILTER (WHERE r.la_doi_tac) doi_tac"
                    " FROM clinic_room_service rs"
                    " JOIN clinic_room r ON r.id = rs.room_id"
                    " WHERE rs.clinic_id = $1 AND rs.service_code = $2"
                )
                truoc = await conn.fetchrow(dem, dv["clinic_id"], dv["service_code"])
                assert truoc["thuong"] > 0 and truoc["doi_tac"] > 0
                # Dịch vụ NGOÀI nhóm việc ấy (không phải việc đối tác làm trọn).
                khac = (
                    "SELECT count(*) FROM clinic_room_service rs"
                    " JOIN service_price sp ON sp.clinic_id = rs.clinic_id"
                    "  AND sp.service_code = rs.service_code"
                    " WHERE rs.clinic_id = $1"
                    "   AND sp.node_code IS DISTINCT FROM $2"
                )
                tong_khac = await conn.fetchval(khac, dv["clinic_id"], dv["node_code"])
                await conn.execute(than)
                sau = await conn.fetchrow(dem, dv["clinic_id"], dv["service_code"])
                assert sau["thuong"] == 0
                assert sau["doi_tac"] == truoc["doi_tac"]
                # Dịch vụ ngoài nhóm việc đối tác: không mất dòng nào.
                assert (
                    await conn.fetchval(khac, dv["clinic_id"], dv["node_code"])
                    == tong_khac
                )
                raise _HoanLaiError
