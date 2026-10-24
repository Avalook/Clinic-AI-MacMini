from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from clinicai.services.bill_service import DongHoaDon, HoaDon
from clinicai.services.chot_0d import doc_chot_0d, ghi_chot_0d


def bill(kind: str) -> HoaDon:
    return HoaDon(
        "visit", kind,
        [DongHoaDon("prescription", "rx", "Thuốc", Decimal(2), "viên",
                    Decimal(50), Decimal(0), "CLINIC", tien_goc=Decimal(100),
                    giam=Decimal(100))],
    )


@pytest.mark.asyncio
async def test_chot_zero_audits_kind_and_snapshot() -> None:
    hd = bill("thuoc")
    with patch("clinicai.services.chot_0d.record_event", new_callable=AsyncMock) as event:
        await ghi_chot_0d(AsyncMock(), object(), "visit", hd)
    payload = event.call_args.kwargs["payload"]
    assert payload["kind"] == "thuoc"
    assert payload["tong_goc"] == 100
    assert payload["tong_giam"] == 100
    assert payload["dong"][0]["source_id"] == "rx"
    assert payload["dong"][0]["so_luong"] == 2
    assert payload["dong"][0]["giam"] == 100
    assert payload["dong"][0]["thanh_tien"] == 0


@pytest.mark.asyncio
async def test_doc_zero_defaults_services_and_filters_kind() -> None:
    conn = AsyncMock()
    conn.fetch.return_value = [{"aggregate_id": "visit", "revision": "rev"}]
    assert await doc_chot_0d(conn, "clinic", ["visit"]) == {"visit": {"rev"}}
    assert conn.fetch.call_args.args[-1] == "dich_vu"
    assert "COALESCE(payload->>'kind', 'dich_vu')" in conn.fetch.call_args.args[0]
    await doc_chot_0d(conn, "clinic", ["visit"], kind="thuoc")
    assert conn.fetch.call_args.args[-1] == "thuoc"


@pytest.mark.asyncio
async def test_doc_zero_empty_does_not_query() -> None:
    conn = AsyncMock()
    assert await doc_chot_0d(conn, "clinic", [], kind="thuoc") == {}
    conn.fetch.assert_not_called()
