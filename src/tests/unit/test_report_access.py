from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.services.report_access_service import (
    DEFAULT_SETTINGS,
    ReportAccessService,
    doc_thiet_lap,
    gioi_han_ban_hang,
    gioi_han_tai_chinh_ca,
    ngay_hop_le,
    pham_vi_lich,
)


def test_settings_and_bad_dates():
    assert doc_thiet_lap("bad") == DEFAULT_SETTINGS
    assert (
        doc_thiet_lap({"bao_cao_theo_ca": {"nhan_vien_theo_ca": "true"}})
        == DEFAULT_SETTINGS
    )
    assert ngay_hop_le("nonsense") is None


def test_roster_full_pending_and_head():
    rows = [
        dict(status="APPROVED", shift="SANG", station="T1_LETAN", location_id="a"),
        dict(status="PENDING", shift="TOI", station="T1_LETAN", location_id="a"),
    ]
    assert pham_vi_lich(rows, head=False) == {"SANG": ["a"]}
    assert pham_vi_lich(rows, head=True) == {}
    full = [dict(status="APPROVED", shift="FULL", station="T1_LETAN", location_id="a")]
    assert len(pham_vi_lich(full, head=False)) == 4
    head = [dict(status="APPROVED", shift="TOI", station="DIEU_PHOI", location_id="a")]
    assert len(pham_vi_lich(head, head=True)) == 4


def test_sales_allowlist_removes_finance_and_customers():
    assert gioi_han_ban_hang(
        {
            "tu": "2026-10-12",
            "hang_hoa": {},
            "khach_con_no": {},
            "tong": {},
            "ten_khach": "secret",
        }
    ) == {"tu": "2026-10-12", "hang_hoa": {}}


def test_shift_finance_excludes_outstanding_balances():
    assert gioi_han_tai_chinh_ca(
        {
            "tai_chinh": {"no": 10},
            "tong": {},
            "khach_con_no": "outside",
            "can_xu_ly": "outside",
            "tien_thua": "outside",
            "thuoc_theo_khach": "names",
        }
    ) == {"tai_chinh": {"no": 10}, "tong": {}}


@pytest.mark.asyncio
async def test_scope_tampering():
    service = ReportAccessService(None)
    service.access = AsyncMock(
        return_value={
            "legacy": False,
            "cac_ca": ["SANG"],
            "co_so_theo_ca": {"SANG": ["a"]},
        }
    )
    for den, ca, location in [
        ("2026-10-13", "SANG", "a"),
        ("2026-10-12", "TOI", "a"),
        ("2026-10-12", None, "a"),
        ("2026-10-12", "SANG", "b"),
    ]:
        with pytest.raises(SafetyGateError):
            await service.authorize(
                SimpleNamespace(), tu="2026-10-12", den=den, ca=ca, co_so=location
            )
    _, location = await service.authorize(
        SimpleNamespace(), tu="2026-10-12", den="2026-10-12", ca="SANG", co_so=None
    )
    assert location == "a"


@pytest.mark.asyncio
async def test_json_and_csv_share_authorization(monkeypatch):
    from clinicai.api.v1.routers import reports

    authorize = AsyncMock(return_value=({"tai_chinh": False}, "a"))
    report = AsyncMock(
        return_value={
            "tu": "2026-10-12",
            "den": "2026-10-12",
            "hang_hoa": {},
            "khach_con_no": "secret",
        }
    )
    monkeypatch.setattr(
        reports, "ReportAccessService", lambda _: SimpleNamespace(authorize=authorize)
    )
    monkeypatch.setattr(
        reports, "BaoCaoCuoiNgayService", lambda _: SimpleNamespace(bao_cao=report)
    )
    identity = SimpleNamespace()
    data = await reports.bao_cao_cuoi_ngay(
        tu="2026-10-12",
        den="2026-10-12",
        loai=None,
        co_so="a",
        ca="SANG",
        identity=identity,
        pool=None,
    )
    assert "khach_con_no" not in data
    with pytest.raises(SafetyGateError):
        await reports.bao_cao_cuoi_ngay_csv(
            tu="2026-10-12",
            den="2026-10-12",
            loai=None,
            co_so="a",
            ca="SANG",
            mau=None,
            identity=identity,
            pool=None,
        )
    assert authorize.await_count == 2
    assert report.await_count == 1
