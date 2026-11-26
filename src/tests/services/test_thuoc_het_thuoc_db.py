"""Ngày dự tính dùng hết thuốc cho quầy thu thuốc / hoá đơn in (Tuyền 26/11)."""

from __future__ import annotations

from datetime import date

import asyncpg
import pytest

from clinicai.services.phieu_kham_service import PhieuKhamService, kiem_quyen_core
from clinicai.services.thuoc.het_thuoc import (
    cach_dung_cua_dong,
    ngay_het_thuoc_cua_luot,
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


async def test_ngay_het_thuoc_cua_luot(pool: asyncpg.Pool) -> None:  # noqa: F811
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
    ds = await ngay_het_thuoc_cua_luot(pool, identity=bs, visit_id=luot["visit"])
    assert [(d["so_ngay"], d["ngay_het"]) for d in ds] == [(30, date(2026, 12, 25))]
