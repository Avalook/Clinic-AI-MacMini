"""Các hợp đồng sự kiện kho thuốc đang thiếu, tái hiện trên DB cô lập."""

# ruff: noqa: F811
import pytest

from tests.services.test_kho_kiotviet_db import _thuoc_moi
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _tao_lo_test(q: Quay) -> str:
    """Tạo lô mới bằng đúng luồng nhập kho của dịch vụ."""
    return await _nhap_lo(q, await _thuoc_moi(q), 1)


@pytest.mark.xfail(
    strict=True,
    reason="PharmacyService.nhap_lo chưa ghi domain event vào event_log",
)
async def test_nhap_lo_ghi_domain_event_cho_lo_vua_tao(q: Quay) -> None:
    batch_id = await _tao_lo_test(q)

    event_count = await q.pool.fetchval(
        "SELECT count(*) FROM event_log WHERE aggregate_id=$1::uuid",
        batch_id,
    )

    assert event_count > 0, "Nhập lô cần ghi ít nhất một domain event cho lô đó"


@pytest.mark.xfail(
    strict=True,
    reason="Ba bảng kho chưa có trigger trg_notify_* để làm mới dữ liệu trực tiếp",
)
async def test_ba_bang_kho_co_trigger_notify(q: Quay) -> None:
    await _tao_lo_test(q)

    triggers = await q.pool.fetch(
        "WITH expected(table_name, trigger_name) AS (VALUES "
        " ('drug_batch', 'trg_notify_drug_batch'),"
        " ('inventory_txn', 'trg_notify_inventory_txn'),"
        " ('phieu_kho', 'trg_notify_phieu_kho')) "
        "SELECT expected.table_name, expected.trigger_name "
        "FROM expected "
        "JOIN pg_class AS tbl ON tbl.relname=expected.table_name "
        "JOIN pg_namespace AS ns ON ns.oid=tbl.relnamespace "
        "JOIN pg_trigger AS trg ON trg.tgrelid=tbl.oid "
        " AND trg.tgname=expected.trigger_name AND NOT trg.tgisinternal "
        "WHERE ns.nspname='public'"
    )

    assert {(row["table_name"], row["trigger_name"]) for row in triggers} == {
        ("drug_batch", "trg_notify_drug_batch"),
        ("inventory_txn", "trg_notify_inventory_txn"),
        ("phieu_kho", "trg_notify_phieu_kho"),
    }
