from datetime import date, datetime, timedelta
from uuid import uuid4

import asyncpg
import pytest

from clinicai.core.clock import CLINIC_TZ
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.tom_tat_tai_chinh_service import doc_no_trong_khoang
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_no_chi_cua_ngay_ca_co_so_va_loai_da_chon(
    pool: asyncpg.Pool,
) -> None:  # noqa: F811
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
        visit,
        q.thu_ngan.staff_id,
    )
    ghi_luc = await pool.fetchval(
        "SELECT ghi_luc FROM cong_no WHERE visit_id=$1::uuid", visit
    )
    ngay = ghi_luc.astimezone(CLINIC_TZ).date()
    # DB test dùng chung: test khác cũng ghi nợ trong ngày → cộng cả ngày thì đỏ
    # theo thứ tự chạy (CI 13/10: 700000 ≠ 300000). Khoanh đúng micro-giây của
    # khoản nợ này; mốc đầu / mốc cuối / loại / cơ sở vẫn được kiểm như cũ.
    mot = timedelta(microseconds=1)

    async def no(
        *,
        tu: date | None = None,
        den: date | None = None,
        loai: str | None = None,
        co_so: str | None = None,
        tu_luc: datetime | None = ghi_luc,
        den_luc: datetime | None = ghi_luc + mot,
    ) -> int:
        async with pool.acquire() as conn:
            return await doc_no_trong_khoang(
                conn,
                ca.thu_ngan.clinic_id,
                tu or ngay,
                den or ngay,
                loai=loai,
                co_so=co_so,
                tu_luc=tu_luc,
                den_luc=den_luc,
            )

    assert await no() == 300000
    assert await no(loai="thuoc") == 0
    assert await no(loai="dich_vu") == 300000
    assert await no(co_so=str(uuid4())) == 0
    async with pool.acquire() as conn:
        assert await doc_no_trong_khoang(conn, str(uuid4()), ngay, ngay) == 0
    assert await no(tu_luc=ghi_luc + mot, den_luc=ghi_luc + 2 * mot) == 0
    assert await no(tu_luc=ghi_luc - mot, den_luc=ghi_luc) == 0
    yesterday = ngay - timedelta(days=1)
    assert await no(tu=yesterday, den=yesterday, tu_luc=None, den_luc=None) == 0
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ca.thu_ngan)
    # Báo cáo cả ngày của cả phòng khám: có ít nhất khoản này (test khác cũng ghi nợ).
    assert bc["tai_chinh"]["no_chua_thu"] >= 300000
    assert bc["tai_chinh"]["giam_gia"] is None
