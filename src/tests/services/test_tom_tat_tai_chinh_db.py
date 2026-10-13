import asyncpg
import pytest

from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from tests.services.test_tien_thuoc_cp1_db import tao_quay

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_bo_no_trong_ky_nhung_khoan_ghi_no_van_o_khach_con_no(
    pool: asyncpg.Pool,
) -> None:  # noqa: F811
    q = await tao_quay(pool)
    await pool.execute(
        """INSERT INTO cong_no(clinic_id,visit_id,clinic_patient_id,so_tien,dong,
                              ly_do,ghi_boi)
           SELECT v.clinic_id,v.visit_id,v.clinic_patient_id,300000,
                  '[{"loai":"dich_vu","so_tien":300000}]'::jsonb,
                  'Khách quên ví',$2::uuid
             FROM visit v WHERE v.visit_id=$1::uuid""",
        q.visit_id,
        q.thu_ngan.staff_id,
    )
    bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=q.thu_ngan)
    assert "no_chua_thu" not in bc["tai_chinh"]
    assert bc["tai_chinh"]["giam_gia"] is None
    # Khoản ghi nợ không mất: vẫn đếm ở "Khách còn nợ".
    assert bc["khach_con_no"]["so_tien"] >= 300000
