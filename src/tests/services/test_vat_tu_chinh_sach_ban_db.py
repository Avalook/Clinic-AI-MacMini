"""Tắt kinh doanh chặn thêm/tăng lượng, vẫn giữ lịch sử và cho bỏ dòng."""

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.vat_tu_service import VatTuService
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_vat_tu_ban_them_db import _vt

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_tat_kinh_doanh_an_chon_moi_giu_dong_cu_va_cho_bo(
    pool: asyncpg.Pool,
) -> None:
    q = await tao_quay(pool)
    vt = await _vt(q, "Vật tư ngừng kinh doanh", 300000)
    svc = VatTuService(pool)
    kq = await svc.them(visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan)
    did = kq["dong"][0]["id"]
    await pool.execute(
        "UPDATE service_price SET kinh_doanh_vat_tu=false WHERE id=$1::uuid", vt
    )
    kq = await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan)
    assert vt not in {d["id"] for d in kq["danh_muc"]}
    assert did in {d["id"] for d in kq["dong"]}
    with pytest.raises(ValidationError, match="không được phép kinh doanh"):
        await svc.them(visit_id=q.visit_id, service_price_id=vt, identity=q.thu_ngan)
    with pytest.raises(ValidationError, match="không được phép kinh doanh"):
        await svc.dat_so_luong(dong_id=did, so_luong=2, identity=q.thu_ngan)
    kq = await svc.bo(dong_id=did, identity=q.thu_ngan)
    assert did not in {d["id"] for d in kq["dong"]}


async def test_bio_khong_duoc_chon_vat_tu_khong_kinh_doanh(pool: asyncpg.Pool) -> None:
    from tests.services.test_bio_chi_dinh_db import _bio, _luot
    from tests.services.test_thu_tien_xep_phong_mang_sang_db import _dung

    lt = await _luot(pool, await _dung(pool))
    await pool.execute(
        "UPDATE service_price SET kinh_doanh_vat_tu=false WHERE id=$1::uuid", lt.bio1
    )
    with pytest.raises(ValidationError, match="không được phép kinh doanh"):
        await _bio(pool, lt, lt.a, lt.bio1)
