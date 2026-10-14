"""Cảnh báo hạn lô: ngày VN, dây nhận và chống réo lặp trong ngày."""

from __future__ import annotations

from datetime import timedelta

import asyncpg
import pytest

from clinicai.core.clock import hom_nay_vn
from clinicai.events.catalogue import CHUONG
from clinicai.services import canh_gac
from clinicai.services.thong_bao_service import ThongBaoService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_tien_thuoc_cp1_db import Quay, _nhap_lo, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_han_lo_dem_va_chuong_mot_lan_trong_ngay(q: Quay) -> None:  # noqa: F811
    _, drug = await _dong_da_xac_dinh(q, 3)
    los = [await _nhap_lo(q, drug, 5) for _ in range(4)]
    for lo, han in zip(
        los,
        [
            None,
            hom_nay_vn() - timedelta(days=1),
            hom_nay_vn(),
            hom_nay_vn() + timedelta(days=61),
        ],
        strict=True,
    ):
        await q.pool.execute(
            "UPDATE drug_batch SET expiry_date=$2 WHERE id=$1::uuid", lo, han
        )
    await q.pool.execute(
        "INSERT INTO day_nhan_thong_bao (clinic_id,su_kien,vai,bac_si_chinh,bat) "
        "VALUES ($1::uuid,'pharmacy.expiry_checked',ARRAY['PHARMACIST'],false,true) "
        "ON CONFLICT (clinic_id,su_kien) DO UPDATE SET vai=EXCLUDED.vai,bat=true",
        q.duoc_si.clinic_id,
    )
    async with q.pool.acquire() as conn:
        so = await canh_gac.do_so(conn)
        assert so["lo_sap_het_han"] >= 1
        assert so["lo_het_han"] >= 1
        async with conn.transaction():
            await canh_gac.bao_han_hang_ngay(conn, so["han_lo"])
            await canh_gac.bao_han_hang_ngay(conn, so["han_lo"])
    await chay_ben_nhan(q.pool, CHUONG)
    chuong = await q.pool.fetch(
        "SELECT * FROM thong_bao WHERE clinic_id=$1::uuid AND nguon='lo_thuoc_han'",
        q.duoc_si.clinic_id,
    )
    assert len(chuong) == 1
    assert chuong[0]["vai_nhan"] == "PHARMACIST"
    assert chuong[0]["nguoi_goi_staff_id"] is None
    assert chuong[0]["duong_dan"] == "/pharmacy/inventory"
    assert "lô" in chuong[0]["noi_dung"]
    thong_bao = await ThongBaoService(q.pool).cua_toi(identity=q.duoc_si)
    han_lo = next(t for t in thong_bao if t["nguon"] == "lo_thuoc_han")
    assert han_lo["nguoi_goi"] is None
    assert han_lo["nhan_nguon"] == "Hệ thống — hạn lô"
    with pytest.raises(asyncpg.CheckViolationError):
        await q.pool.execute(
            "INSERT INTO thong_bao (clinic_id,vai_nhan,tieu_de,noi_dung,nguon) "
            "VALUES ($1::uuid,'PHARMACIST','a','b','ket_qua_ve')",
            q.duoc_si.clinic_id,
        )
