"""Chuông thông báo nhận tin qua dòng SSE chung — trigger trên `thong_bao`.

Trước 27/09/2026 chuông nghe `postgres_changes` của Supabase Realtime, đường
chết vì Postgres từ chối plugin wal2json; cuộc gọi KHẨN của trưởng ca chờ tới
nhịp poll 20 giây. Migration 20260927000002 gắn `trg_notify_thong_bao`.

Hai điều phải giữ: tin bắn SAU COMMIT, và tin CHỈ gồm tên bảng + phòng khám —
`thong_bao` có thể gọi tới một người, còn broker phát theo phòng khám tới mọi
màn đang mở, nên tiêu đề hay nội dung lọt vào tin là lộ cho người không được gọi.
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from clinicai.core.change_broker import CHANNEL, ChangeBroker
from tests.services.test_luot_kham_service_db import CLINIC

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase/migrations/20260927000002_notify_realtime_con_lai.sql"
)

#: AFTER + FOR EACH ROW + INSERT + DELETE + UPDATE (bit của pg_trigger.tgtype).
_TGTYPE_AFTER_ROW_IUD = 1 | 4 | 8 | 16

_BI_MAT = "Bệnh nhân Nguyễn Thị Bí Mật — phòng siêu âm 3"


async def test_thong_bao_bao_tin_sau_commit_khong_kem_noi_dung(
    pool: asyncpg.Pool,
) -> None:
    await pool.execute(_MIGRATION.read_text(encoding="utf-8"))
    tgtype = await pool.fetchval(
        "SELECT t.tgtype FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
        " JOIN pg_proc p ON p.oid = t.tgfoid"
        " WHERE c.relname = 'thong_bao' AND t.tgname = 'trg_notify_thong_bao'"
        " AND p.proname = 'notify_row_change' AND NOT t.tgisinternal"
    )
    assert tgtype == _TGTYPE_AFTER_ROW_IUD

    nguoi_goi = await pool.fetchval(
        "SELECT staff_id::text FROM clinic_membership WHERE clinic_id = $1::uuid"
        " ORDER BY staff_id LIMIT 1",
        CLINIC,
    )
    assert nguoi_goi, "seed phải có ít nhất một nhân sự trong phòng khám thử"

    broker = ChangeBroker("postgresql://unused")
    own = broker.subscribe(CLINIC)
    other = broker.subscribe(str(uuid4()))
    nguon_id = f"kiem-notify-{uuid4()}"
    tb_id: str | None = None

    async def nhan_tin() -> dict[str, str]:
        tin: dict[str, str] = json.loads(await asyncio.wait_for(own.get(), timeout=2))
        return tin

    async with pool.acquire() as listener:
        await listener.add_listener(CHANNEL, broker._on_notify)
        try:
            # INSERT — chuông đỏ mới phải tới ngay, và chỉ sau COMMIT.
            async with pool.acquire() as writer, writer.transaction():
                tb_id = await writer.fetchval(
                    "INSERT INTO thong_bao (clinic_id, vai_nhan, muc_do, tieu_de,"
                    " noi_dung, nguon, nguon_id, nguoi_goi_staff_id)"
                    " VALUES ($1::uuid, 'RECEPTION', 'KHAN', $2, $2, 'KIEM_THU', $3,"
                    " $4::uuid) RETURNING id::text",
                    CLINIC,
                    _BI_MAT,
                    nguon_id,
                    nguoi_goi,
                )
                await asyncio.sleep(0.05)
                assert own.empty(), "tin không được đi trước COMMIT"
            assert tb_id is not None
            tho = await asyncio.wait_for(own.get(), timeout=2)
            assert json.loads(tho) == {"t": "thong_bao", "c": CLINIC}
            assert "Bí Mật" not in tho and tb_id not in tho
            assert other.empty(), "phòng khám khác không được nghe tin này"

            # UPDATE — một người nhận việc thì chuông người cùng vai thôi đỏ.
            await pool.execute(
                "UPDATE thong_bao SET da_doc_luc = now() WHERE id = $1::uuid", tb_id
            )
            assert await nhan_tin() == {"t": "thong_bao", "c": CLINIC}
        finally:
            if tb_id is not None:
                await pool.execute("DELETE FROM thong_bao WHERE id = $1::uuid", tb_id)
            await listener.remove_listener(CHANNEL, broker._on_notify)
