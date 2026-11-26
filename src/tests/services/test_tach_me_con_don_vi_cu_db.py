"""Migration 20261126500200 (Tuyền 26/11): "hộp 60 viên" → đơn vị tính "hộp" + con.

Ca thật trên prod: Kofio đếm hộp thật (chỉ đổi chữ); Ecanix nhập quy ra viên
(305 × 60 = 18300) rồi bán / chuyển quầy trừ theo hộp → lô kho về 305 − 73 = 232 hộp.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest

from tests.services.test_phieu_kham_db import CLINIC, pool  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

SQL = (
    Path(__file__).resolve().parents[3]
    / "supabase/migrations/20261126500200_tach_me_con_don_vi_cu.sql"
).read_text()


async def _thuoc(conn: asyncpg.Connection, dv: str) -> str:
    ten = f"Tách mẹ con {uuid.uuid4().hex[:6]}"
    return str(
        await conn.fetchval(
            "INSERT INTO drug_catalog (clinic_id, name_raw, name_base, unit_price,"
            " don_vi_ban) VALUES ($1::uuid, $2, $2, 550000, $3) RETURNING id::text",
            CLINIC,
            ten,
            dv,
        )
    )


Dong = list[tuple[str, int, str]]


async def _lo(
    conn: asyncpg.Connection,
    thuoc: str,
    dv: str,
    noi: str,
    ds: Dong,
    cung_lo: str | None = None,
) -> str:
    """`cung_lo` = id lô KHO: tạo hàng QUẦY cùng mã lô + mã tem (như prod) — để
    kiểm `drug_batch_hang_khop` (hai hàng cùng lô phải cùng đơn vị) chạy thật."""
    cs = await conn.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid LIMIT 1",
        CLINIC,
    )
    lo = str(
        await conn.fetchval(
            "INSERT INTO drug_batch (clinic_id, location_id, drug_catalog_id,"
            " batch_code, expiry_date, quantity_on_hand, unit, noi_chua, received_at,"
            " ma_tem) SELECT $1::uuid, $2::uuid, $3::uuid,"
            " coalesce(k.batch_code, $4), '2099-12-31', 0, $5, $6, now(),"
            " coalesce(k.ma_tem,"
            "  'LT' || lpad(nextval('drug_batch_tem_seq')::text, 8, '0'))"
            " FROM (SELECT 1) x LEFT JOIN drug_batch k ON k.id = $7::uuid"
            " RETURNING id::text",
            CLINIC,
            cs,
            thuoc,
            f"LO-{uuid.uuid4().hex[:6]}",
            dv,
            noi,
            cung_lo,
        )
    )
    for loai, so, ly_do in ds:
        await conn.execute(
            "INSERT INTO inventory_txn (clinic_id, drug_batch_id, txn_type, quantity,"
            " reason, ref_type) VALUES ($1::uuid, $2::uuid, $3, $4, $5, 'phieu_kho')",
            CLINIC,
            lo,
            loai,
            so,
            ly_do,
        )
    return lo


async def test_tach_me_con(pool: asyncpg.Pool) -> None:  # noqa: F811
    async with pool.acquire() as conn:
        kofio = await _thuoc(conn, "hộp 15 viên")
        lo_k = await _lo(conn, kofio, "hộp 15 viên", "KHO", [("RECEIVE", 135, "Nhập")])
        eca = await _thuoc(conn, "hộp 60 viên")
        await conn.execute(
            "INSERT INTO thuoc_quy_doi (clinic_id, drug_catalog_id, don_vi, he_so)"
            " VALUES ($1::uuid, $2::uuid, 'hộp', 60)",
            CLINIC,
            eca,
        )
        dv = "hộp 60 viên"
        lo_kho = await _lo(
            conn,
            eca,
            dv,
            "KHO",
            [
                ("RECEIVE", 18300, "Phiếu nhập · Quy đổi 305 hộp × 60 = 18300 " + dv),
                # Prod: 62 hộp giao thẳng từ kho; ở đây thay bằng ADJUST (cùng nghĩa
                # "trừ theo hộp", không cần dựng lượt khám).
                ("ADJUST", -62, "Giao từ kho"),
                ("CHUYEN_RA", -11, "Chuyển kho"),
            ],
        )
        lo_quay = await _lo(
            conn, eca, dv, "QUAY", [("CHUYEN_VAO", 3, "Chuyển kho")], cung_lo=lo_kho
        )

        # Một giao dịch như lúc áp migration: kiểm hoãn tới commit phải qua.
        async with conn.transaction():
            await conn.execute(SQL)
        await conn.execute(SQL)  # chạy lại: không đổi gì thêm

        ton = dict(
            await conn.fetch(
                "SELECT id::text, quantity_on_hand FROM drug_batch WHERE id = ANY($1)",
                [uuid.UUID(x) for x in (lo_k, lo_kho, lo_quay)],
            )
        )
        assert ton == {lo_k: 135, lo_kho: 232, lo_quay: 3}
        r = await conn.fetch(
            "SELECT id::text, don_vi_ban, don_vi_con, so_lieu_moi_don_vi_goc"
            " FROM drug_catalog WHERE id = ANY($1)",
            [uuid.UUID(kofio), uuid.UUID(eca)],
        )
        assert {x["id"]: tuple(x)[1:] for x in r} == {
            kofio: ("hộp", "viên", Decimal(15)),
            eca: ("hộp", "viên", Decimal(60)),
        }
        assert not await conn.fetchval(
            "SELECT count(*) FROM thuoc_quy_doi WHERE drug_catalog_id = $1::uuid", eca
        )
        assert {
            x["unit"]
            for x in await conn.fetch(
                "SELECT unit FROM drug_batch WHERE drug_catalog_id = ANY($1)",
                [uuid.UUID(kofio), uuid.UUID(eca)],
            )
        } == {"hộp"}
