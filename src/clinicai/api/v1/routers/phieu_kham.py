"""Bảy phiếu khám — các đường ĐỌC: định nghĩa, tham chiếu, mang sang, kết quả CLS.

Router mỏng, đã mount (CI đòi mọi router phải mount) nhưng CHƯA dùng được:
hai thứ phải nối trước (INTEGRATION_POINT, xem `docs/phieu-kham/TICH-HOP.md`):

* **Quyền.** `lay_kiem_quyen` mặc định CHẶN TẤT — hệ phân quyền của CORE thay
  nó (sửa hàm, hoặc `app.dependency_overrides`). Gói này không tự thêm
  capability.
* **Đường ghi.** Không có: phiếu khám gắn vào consultation/visit, chỗ lưu chưa
  có (INTEGRATION_BLOCKER). Clinical shell ghi thì gọi
  `PhieuKhamService.kiem_luu` trước.

Định nghĩa và tham chiếu là dữ liệu tĩnh trong gói (không có dữ liệu bệnh nhân),
nên không hỏi quyền phiếu.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.phieu_kham.khung import FORM_IDS, dinh_nghia, tham_chieu_nguon
from clinicai.services.phieu_kham_service import (
    KiemQuyen,
    PhieuKhamService,
    chua_noi_quyen,
)

router = APIRouter()


def lay_kiem_quyen() -> KiemQuyen:
    """Điểm cắm hệ phân quyền. Chưa nối = chặn tất."""
    return chua_noi_quyen


@router.get("/phieu-kham/dinh-nghia")
async def danh_sach(
    identity: StaffIdentity = Depends(get_current_identity),
) -> dict[str, Any]:
    """Bảy phiếu và tên — không kèm khung (nhẹ)."""
    ds = [dinh_nghia(f) for f in FORM_IDS]
    return {"phieu": [{"form_id": d["form_id"], "ten": d["ten"]} for d in ds]}


@router.get("/phieu-kham/dinh-nghia/{form_id}")
async def mot_dinh_nghia(
    form_id: str,
    version: int | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Khung của một phiên bản — phiếu đã điền ghim phiên bản của nó."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).khung_theo_ban(
        form_id=form_id, version=version, identity=identity
    )


@router.get("/phieu-kham/tham-chieu")
async def tham_chieu(
    identity: StaffIdentity = Depends(get_current_identity),
) -> dict[str, Any]:
    """Danh mục C / F / thuốc của NGUỒN — nhãn chờ ánh xạ mã, chưa phải định danh."""
    return tham_chieu_nguon()


@router.get("/phieu-kham/luot/{visit_id}/dau-phieu")
async def dau_phieu(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Hành chính + sinh hiệu + ghi chú tư vấn ban đầu — chỉ đọc."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).dau_phieu(
        visit_id=str(visit_id), identity=identity
    )


@router.get("/phieu-kham/luot/{visit_id}/ket-qua-chi-dinh")
async def ket_qua_chi_dinh(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Kết quả CLS của từng chỉ định trong lượt — gắn bằng `service_order_id`."""
    svc = PhieuKhamService(pool, kiem_quyen=kiem_quyen)
    return {
        "chi_dinh": await svc.ket_qua_chi_dinh(
            visit_id=str(visit_id), identity=identity
        )
    }
