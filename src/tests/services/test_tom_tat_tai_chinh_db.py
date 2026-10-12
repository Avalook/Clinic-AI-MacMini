from datetime import timedelta
from uuid import uuid4

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.tom_tat_tai_chinh_service import doc_no_trong_khoang
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_no_chi_cua_ngay_ca_co_so_va_loai_da_chon(pool: asyncpg.Pool):  # noqa: F811
    q = await tao_quay(pool)
    visit = q.visit_id
    ca = q
    await pool.execute(
        """INSERT INTO cong_no(clinic_id,visit_id,clinic_patient_id,so_tien,dong,
                              ly_do,ghi_boi)
           SELECT v.clinic_id,v.visit_id,v.clinic_patient_id,300000,
                  '[{"loai":"dich_vu","so_tien":300000}]'::jsonb,
                  'Khách quên ví',$2::uuid
             FROM visit v WHERE v.visit_id=$1::uuid""",
        visit, q.thu_ngan.staff_id,
    )
    ghi_luc = await pool.fetchval(
        "SELECT ghi_luc FROM cong_no WHERE visit_id=$1::uuid", visit
    )
    ngay = ghi_luc.astimezone(CLINIC_TZ).date()
    async with pool.acquire() as conn:
        assert (
            await doc_no_trong_khoang(conn, ca.thu_ngan.clinic_id, ngay, ngay) == 300000
        )
        assert (
            await doc_no_trong_khoang(
                conn, ca.thu_ngan.clinic_id, ngay, ngay, loai="thuoc"
            )
            == 0
        )
        assert (
            await doc_no_trong_khoang(
                conn, ca.thu_ngan.clinic_id, ngay, ngay, loai="dich_vu"
            )
            == 300000
        )
        assert (
            await doc_no_trong_khoang(
                conn, ca.thu_ngan.clinic_id, ngay, ngay, co_so=str(uuid4())
            )
            == 0
        )
        assert await doc_no_trong_khoang(conn, str(uuid4()), ngay, ngay) == 0
        assert (
            await doc_no_trong_khoang(
                conn,
                ca.thu_ngan.clinic_id,
                ngay,
                ngay,
                tu_luc=ghi_luc + timedelta(seconds=1),
            )
            == 0
        )
        assert (
            await doc_no_trong_khoang(
                conn,
                ca.thu_ngan.clinic_id,
                ngay,
                ngay,
                den_luc=ghi_luc,
            )
            == 0
        )
        assert (
            await doc_no_trong_khoang(
                conn,
                ca.thu_ngan.clinic_id,
                ngay - timedelta(days=1),
                ngay - timedelta(days=1),
            )
            == 0
        )
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ca.thu_ngan)
    assert bc["tai_chinh"]["no_chua_thu"] == 300000
    assert bc["tai_chinh"]["giam_gia"] is None
