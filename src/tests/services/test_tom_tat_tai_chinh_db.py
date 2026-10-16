import asyncpg
import pytest

from clinicai.events.catalogue import SO_NO
from clinicai.services.bao_cao_cuoi_ngay_service import BaoCaoCuoiNgayService
from clinicai.services.cong_no_service import CongNoService
from tests.chay_nguoi_dua_tin import chay_ben_nhan
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    pool,
)
from tests.services.test_mo_phong_dong_tien_db import _lam_xong, _luot, _ve
from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung
from tests.services.test_thu_truoc_lam_truoc_tick_db import day_thu_truoc

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_bo_no_trong_ky_nhung_khoan_ghi_no_van_o_khach_con_no(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    async with day_thu_truoc(pool, False):
        ca = await _dung(pool)
        v, o = await _luot(pool, ca)
        await _lam_xong(pool, ca, o)
        await CongNoService(pool).ghi(
            identity=ca.le_tan, visit_id=v, ly_do="Khách quên ví"
        )
        await _ve(pool, ca, v)
        await chay_ben_nhan(pool, SO_NO)
        bc = await BaoCaoCuoiNgayService(pool).bao_cao(identity=ca.thu_ngan)
    assert "no_chua_thu" not in bc["tai_chinh"]
    # F3: giảm giá là số thật (DB thử chung có phiếu giảm của bài khác).
    assert isinstance(bc["tai_chinh"]["giam_gia"], int)
    # Khoản nợ không mất: "Khách còn nợ" đọc sổ nợ; khối Dòng tiền có "Nợ".
    assert bc["khach_con_no"]["so_tien"] >= 300000
    dt = bc["tai_chinh"]["dong_tien"]
    assert dt["no"] >= 300000 and dt["khop"] is True
