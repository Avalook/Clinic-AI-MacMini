"""Ngày dự tính dùng hết thuốc cho quầy thu thuốc / hoá đơn in (Tuyền 26/11)."""

from __future__ import annotations

from datetime import date

import asyncpg
import pytest

from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thuoc.het_thuoc import (
    cach_dung_cua_dong,
    ngay_het_thuoc_cua_luot,
    ngay_het_tung_dong,
    tach_so_luong,
)
from tests.services.test_phieu_kham_db import _luot, _nguoi, pool  # noqa: F401
from tests.services.test_thuoc_cach_dung_db import _ecanix, _ngay_luot

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


def test_tach_dong_don() -> None:
    assert tach_so_luong("2 hộp") == ("2", "hộp")
    assert tach_so_luong("10") == ("10", "")
    assert tach_so_luong("uống hết") == ("", "")
    assert cach_dung_cua_dong("Uống — Ngày 2 lần") == "Ngày 2 lần"
    assert cach_dung_cua_dong("Ngày 2 lần") == "Ngày 2 lần"


@pytest.fixture
def hom_nay(monkeypatch: pytest.MonkeyPatch) -> date:
    """Khách mua 28/11, hai ngày sau ngày khám 26/11 (Tuyền: tính từ ngày mua)."""
    d = date(2026, 11, 28)
    monkeypatch.setattr("clinicai.services.thuoc.het_thuoc.hom_nay_vn", lambda: d)
    return d


async def test_ngay_het_thuoc_cua_luot(
    pool: asyncpg.Pool,  # noqa: F811
    hom_nay: date,
) -> None:
    async with pool.acquire() as conn:
        bs = await _nguoi(conn, "DOCTOR")
        luot = await _luot(conn, bs)
        await _ngay_luot(conn, luot["visit"], "2026-11-26")
        t = await _ecanix(conn)
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen_core)
    await svc.luu_don_thuoc(
        visit_id=luot["visit"],
        identity=bs,
        ly_do=None,
        dong=[
            {
                "drug_catalog_id": t,
                "drug_name": "Ecanix thử",
                "quantity": "1 hộp",
                "dosage": "Uống — Ngày uống 2 lần, mỗi lần 1 viên",
            },
            # Không ghi số lượng → không tính, không hiện.
            {
                "drug_catalog_id": t,
                "drug_name": "Ecanix 2",
                "quantity": "",
                "dosage": "x",
            },
        ],
    )
    # Chưa thu: tính từ hôm nay (ngày khách đứng ở quầy mua) 28/11, không từ ngày khám.
    ds = await ngay_het_thuoc_cua_luot(pool, identity=bs, visit_id=luot["visit"])
    assert [(d["so_ngay"], d["ngay_het"]) for d in ds] == [(30, date(2026, 12, 27))]

    # Đã thu 29/11: hoá đơn in tính từ ngày của lần thu đó.
    async with pool.acquire() as conn:
        phieu = await conn.fetchval(
            "INSERT INTO public.payment_cycle"
            " (payment_cycle_id, clinic_id, visit_id, kind, amount, status, legacy,"
            "  paid_at)"
            " SELECT gen_random_uuid(), clinic_id, visit_id, 'thuoc', 550000, 'PAID',"
            "        true, '2026-11-29 10:00+07'"
            "   FROM public.visit WHERE visit_id = $1::uuid"
            " RETURNING payment_cycle_id::text",
            luot["visit"],
        )
    for theo in ({"visit_id": luot["visit"]}, {"phieu_id": phieu}):
        ds = await ngay_het_thuoc_cua_luot(pool, identity=bs, **theo)
        assert [(d["so_ngay"], d["ngay_het"]) for d in ds] == [(30, date(2026, 12, 28))]

    # Quầy bán 2 hộp (khác số kê) → theo số ĐANG BÁN: 60 ngày, từ hôm nay 28/11.
    theo_dong = await ngay_het_tung_dong(
        pool,
        identity=bs,
        visit_id=luot["visit"],
        dong=[
            {
                "id": "a",
                "drug_catalog_id": t,
                "so_luong": "2",
                "don_vi": "hộp",
                "chu": "Uống — Ngày uống 2 lần, mỗi lần 1 viên",
            },
            {"id": "b", "drug_catalog_id": t, "so_luong": "", "don_vi": "", "chu": ""},
        ],
    )
    assert theo_dong == {
        "a": {"so_ngay": 60, "ngay_het": date(2027, 1, 26), "bat_dau": None}
    }
