"""[Nhận] ở Bàn khám và [Đổi bác sĩ] chỉ đưa khách cho BÁC SĨ (18/11/2026).

Ca tối 16/11: điều dưỡng/thư ký Sàn chậu (vai TKYK) có đủ quyền "Khám bệnh" +
"Hoàn tất khám" (để bấm Hoàn tất thay bác sĩ), bấm [Nhận] ở Bàn khám → máy ghi
chị là bác sĩ của lượt → vòng đọc kết quả xếp cho "bác sĩ" mà không bàn khám nào
hiện → lễ tân phải tự đánh đơn. Trên prod mọi vai đều có hai quyền ấy (30 ngày:
14 lượt mang tên 9 người không phải bác sĩ), nên quyền một mình không đủ: phải
thêm VAI bác sĩ.
"""

from __future__ import annotations

import asyncpg
import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.services.doi_bac_si_service import DoiBacSiService
from clinicai.services.permission_service import PermissionService
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    _benh_nhan,
    _check_in,
    _dung,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _bac_si_cua_luot(pool: asyncpg.Pool, visit: str) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            "SELECT attending_doctor_id::text FROM visit WHERE visit_id = $1::uuid",
            visit,
        )
    )


@pytest.mark.parametrize("vai", ["TKYK", "NURSE_ULTRASOUND", "RECEPTION"])
async def test_nguoi_khong_phai_bac_si_bam_nhan_thi_khong_thanh_bac_si(
    pool: asyncpg.Pool,  # noqa: F811
    vai: str,
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
        nguoi = await _nguoi(conn, ca.loc, vai)
    for khoi in ("kham", "hoan_tat_kham"):  # đủ quyền như trên prod
        await PermissionService(pool).cap_khoi(
            identity=ql, staff_id=nguoi.staff_id, khoi=khoi
        )
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)

    with pytest.raises(ValidationError):
        await DoiBacSiService(pool).nhan_khach(identity=nguoi, visit_id=visit)
    assert await _bac_si_cua_luot(pool, visit) == ca.bac_si.staff_id


async def test_doi_bac_si_khong_cho_chon_dieu_duong(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    async with pool.acquire() as conn:
        ql = await _nguoi(conn, ca.loc, "MANAGEMENT")
        tc = await _nguoi(conn, ca.loc, "TRUONG_CA")
        dd = await _nguoi(conn, ca.loc, "NURSE_ULTRASOUND")
    for khoi in ("kham", "hoan_tat_kham"):
        await PermissionService(pool).cap_khoi(
            identity=ql, staff_id=dd.staff_id, khoi=khoi
        )
    svc = DoiBacSiService(pool)
    ds = {r["id"] for r in await svc.bac_si_trong_phong_kham(identity=tc)}
    assert dd.staff_id not in ds
    assert tc.staff_id not in ds  # trưởng ca có đủ quyền nhưng không phải bác sĩ
    assert ca.bac_si.staff_id in ds

    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    with pytest.raises(ValidationError):
        await svc.doi(
            identity=tc, visit_id=visit, bac_si_moi_id=dd.staff_id, ly_do="quá tải"
        )
    assert await _bac_si_cua_luot(pool, visit) == ca.bac_si.staff_id
