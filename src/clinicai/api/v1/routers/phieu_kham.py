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
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.permissions.y_khoa import ghi_mo_ho_so
from clinicai.phieu_kham.khung import FORM_IDS, dinh_nghia
from clinicai.services.phieu_kham_service import (
    KiemQuyen,
    PhieuKhamService,
    kiem_quyen_core,
)

router = APIRouter()


def lay_kiem_quyen() -> KiemQuyen:
    """Điểm cắm hệ phân quyền — đã nối capability của CORE (IP-2, 23/09/2026)."""
    return kiem_quyen_core


class DongDon(BaseModel):
    id: str | None = None
    drug_catalog_id: str | None = None
    drug_name: str = Field(max_length=300)
    quantity: str = Field(default="", max_length=100)
    dosage: str = Field(default="", max_length=2000)
    caution: str = Field(default="", max_length=2000)


class LuuDon(BaseModel):
    dong: list[DongDon] = Field(max_length=100)
    ly_do: str | None = Field(default=None, max_length=500)


class LuuPhieu(BaseModel):
    form_id: str = Field(min_length=1, max_length=40)
    #: Cả gói (cách cũ) — kèm `expected_revision`, lệch là 409.
    du_lieu: dict[str, Any] | None = None
    expected_revision: int = Field(default=0, ge=0)
    #: CHỈ các ô vừa đổi (26/09/2026, lát 2): máy chủ gộp vào dưới khoá dòng —
    #: hai người sửa hai ô khác nhau không còn 409 / mất chữ đang gõ. Xoá ô =
    #: gửi ô ấy với giá trị rỗng.
    thay_doi: dict[str, Any] | None = None


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
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Danh mục C / F / thuốc của nguồn, gắn mã + giá THẬT của phòng khám."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).tham_chieu_that(
        identity=identity
    )


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


@router.get("/phieu-kham/luot/{visit_id}/hanh-trinh")
async def hanh_trinh(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Dải mốc hành trình + "đang ở đâu" ở đầu phiếu khám — chỉ đọc."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).hanh_trinh(
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
        ),
        "mau_du_phong": await svc.mau_du_phong(identity=identity),
        # Tệp cùng khách + cùng lịch hẹn nhưng chưa gắn chỉ định (đợt 3).
        "tep_chua_gan": await svc.tep_chua_gan(
            visit_id=str(visit_id), identity=identity
        ),
    }


@router.get("/phieu-kham/luot/{visit_id}/phieu")
async def phieu_cua_luot(
    visit_id: UUID,
    form_id: str | None = None,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Phiếu khám của lượt: khung đúng bản đã ghim + dữ liệu + revision."""
    data = await PhieuKhamService(pool, kiem_quyen=kiem_quyen).doc_luot(
        visit_id=str(visit_id), form_id=form_id, identity=identity
    )
    await ghi_mo_ho_so(pool, identity, noi="phieu-kham", visit_id=str(visit_id))
    return data


@router.put("/phieu-kham/luot/{visit_id}/phieu")
async def luu_phieu_cua_luot(
    visit_id: UUID,
    body: LuuPhieu,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Tự lưu — không có nút Lưu; 409 khi người khác vừa lưu."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).luu_luot(
        visit_id=str(visit_id),
        form_id=body.form_id,
        du_lieu=body.du_lieu,
        expected_revision=body.expected_revision,
        identity=identity,
        thay_doi=body.thay_doi,
    )


@router.get("/phieu-kham/luot/{visit_id}/lich-su")
async def lich_su_phieu(
    visit_id: UUID,
    form_id: str | None = Query(default=None, pattern=r"^[A-Z][A-Z_]{1,31}$"),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Lịch sử sửa phiếu (P4A): ai · lúc nào · ô nào · trước → sau."""
    return {
        "lich_su": await PhieuKhamService(pool, kiem_quyen=kiem_quyen).lich_su(
            visit_id=str(visit_id), form_id=form_id, identity=identity
        )
    }


@router.get("/phieu-kham/luot/{visit_id}/don-thuoc")
async def don_thuoc(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    return {
        "dong": await PhieuKhamService(pool, kiem_quyen=kiem_quyen).doc_don_thuoc(
            visit_id=str(visit_id), identity=identity
        )
    }


@router.put("/phieu-kham/luot/{visit_id}/don-thuoc")
async def luu_don_thuoc(
    visit_id: UUID,
    body: LuuDon,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
    kiem_quyen: KiemQuyen = Depends(lay_kiem_quyen),
) -> dict[str, Any]:
    """Đơn thuốc mục E — đi thẳng tới nhà thuốc như đơn bệnh án cũ."""
    return await PhieuKhamService(pool, kiem_quyen=kiem_quyen).luu_don_thuoc(
        visit_id=str(visit_id),
        dong=[d.model_dump() for d in body.dong],
        ly_do=body.ly_do,
        identity=identity,
    )
