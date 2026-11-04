"""Tab /ops "Thử luật mới": gom sổ chạy bóng (Tuyền 04/11/2026)."""

from __future__ import annotations

import pytest

from clinicai.permissions import chay_bong
from clinicai.permissions.can import doi_quyen
from clinicai.services import chay_bong_doc
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import KichBan

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_gom_theo_viec_va_phong(kb: KichBan) -> None:
    ai = kb.le_tan
    async with kb.pool.acquire() as conn:
        await ve_goi_mau_cu(conn, ai)
        # Có lego tiếp đón, chưa xếp lịch: hai lần bấm sẽ bị chặn.
        await doi_quyen(conn, ai, "reception.checkin.perform")
        await doi_quyen(conn, ai, "reception.checkin.perform")

    tong = await chay_bong_doc.tong_hop(
        kb.pool, clinic_id=ai.clinic_id, theo="viec", tu="rác", den=None
    )
    assert tong["tong"]["so_chan"] >= 2
    dong = next(r for r in tong["dong"] if r["khoa"] == "tiep_don")
    assert dong["so_chan"] >= 2 and "khong_lich" in dong["ly_do"]
    assert tong["gan_day"] and tong["gan_day"][0]["ly_do"] == "khong_lich"

    phong = await chay_bong_doc.tong_hop(kb.pool, clinic_id=ai.clinic_id, theo="phong")
    assert any(r["ten"] == "Không đứng phòng nào" for r in phong["dong"])
    nguoi = await chay_bong_doc.tong_hop(kb.pool, clinic_id=ai.clinic_id, theo="lạ")
    assert nguoi["theo"] == "nguoi"
    assert any(r["khoa"] == ai.staff_id for r in nguoi["dong"])


async def test_khoang_ngay_rac_ve_hom_nay() -> None:
    a, b = chay_bong_doc.khoang_ngay("abc", None)
    assert a == b
    a, b = chay_bong_doc.khoang_ngay("2026-11-04", "2026-11-01")
    assert a.isoformat() == "2026-11-01" and b.isoformat() == "2026-11-04"
    a, b = chay_bong_doc.khoang_ngay("2026-01-01", "2026-11-04")
    assert (b - a).days == chay_bong.GIU_NGAY
