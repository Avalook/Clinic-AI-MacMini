"""Kho vật tư: phiếu kho, tồn theo nơi chứa, mức tối thiểu, nhắc.

Quyền = lego "Kho vật tư" (`vat_tu.manage`), không gác theo vai và không dùng
quyền kho thuốc. Mọi luật nằm ở `vat_tu_kho_service` / `vat_tu_kho_man_service`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field

from clinicai.api.idempotency import (
    IdempotencyGuard,
    idempotency_guard,
    tra_khoa_neu_bi_tu_choi,
)
from clinicai.api.identity import StaffIdentity
from clinicai.core.database import get_db_pool
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services import vat_tu_ban_service as ban
from clinicai.services import vat_tu_kho_man_service as man
from clinicai.services import vat_tu_kho_service as kho
from clinicai.services import vat_tu_tieu_hao_service as tieu_hao

router = APIRouter()
_QL = cua_quyen("vat_tu.manage")


@router.get("/vat-tu-kho/ton")
async def ton(
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tồn từng nơi chứa kèm cảnh báo (tồn âm / dưới mức tối thiểu)."""
    kq: dict[str, Any] = jsonable_encoder(
        {
            "items": await kho.doc_ton(pool, identity=identity),
            "noi_chua": await man.doc_noi_chua(pool, identity=identity),
            "vat_tu": await man.doc_vat_tu_chon(pool, identity=identity),
        }
    )
    return kq


@router.get("/vat-tu-kho/canh-bao")
async def canh_bao(
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        {"items": await man.doc_canh_bao(pool, identity=identity)}
    )
    return kq


@router.get("/vat-tu-kho/phieu")
async def danh_sach_phieu(
    gioi_han: str | None = None,
    bo_qua: str | None = None,
    vat_tu_id: str | None = None,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    kq: dict[str, Any] = jsonable_encoder(
        {
            "items": await man.doc_phieu(
                pool,
                identity=identity,
                gioi_han=gioi_han,
                bo_qua=bo_qua,
                vat_tu_id=vat_tu_id,
            )
        }
    )
    return kq


@router.get("/vat-tu-kho/ban")
async def ban_cho_khach(
    tu: str | None = None,
    den: str | None = None,
    noi: str | None = None,
    trang_thai: str | None = None,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Danh sách đối soát vật tư bán cho khách."""
    kq: dict[str, Any] = jsonable_encoder(
        await ban.doc_ban(
            pool, identity=identity, tu=tu, den=den, noi=noi, trang_thai=trang_thai
        )
    )
    return kq


@router.get("/vat-tu-kho/ban/tim-khach")
async def ban_tim_khach(
    q: str | None = None,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tìm khách để nhập bù."""
    return await ban.tim_khach(pool, identity=identity, q=q)


class GanNoiRequest(BaseModel):
    # Rỗng = Kho cơ sở.
    room_id: UUID | None = None
    ly_do: Any = None


@router.post("/vat-tu-kho/ban/{ban_id}/gan-phong")
async def ban_gan_phong(
    ban_id: UUID,
    body: GanNoiRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Gán / đổi nơi lấy: trừ ngay ở nơi đó. Đổi = đảo chỗ cũ + trừ chỗ mới."""
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq: dict[str, Any] = await ban.gan_noi_lay(
            pool,
            identity=identity,
            ban_id=str(ban_id),
            room_id=str(body.room_id) if body.room_id else None,
            ly_do=body.ly_do,
        )
        await idem.save(pool, kq, status_code=200)
    return kq


class NhanLaiRequest(BaseModel):
    # Any: số rác phải tới service để trả 422 có lời.
    so_luong: Any = None
    ly_do: Any = None


@router.post("/vat-tu-kho/ban/{ban_id}/nhan-lai")
async def ban_nhan_lai(
    ban_id: UUID,
    body: NhanLaiRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Nhận lại hàng khách trả: số về đúng nơi đã lấy."""
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq: dict[str, Any] = await ban.nhan_lai_hang(
            pool,
            identity=identity,
            ban_id=str(ban_id),
            so_luong=body.so_luong,
            ly_do=body.ly_do,
        )
        await idem.save(pool, kq, status_code=200)
    return kq


class LyDoRequest(BaseModel):
    ly_do: Any = None


@router.post("/vat-tu-kho/ban/{ban_id}/khong-nhan-lai")
async def ban_khong_nhan_lai(
    ban_id: UUID,
    body: LyDoRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đã hoàn tiền nhưng hàng không về: đóng phần chờ xử lý, tồn giữ nguyên."""
    return await ban.khong_nhan_lai(
        pool, identity=identity, ban_id=str(ban_id), ly_do=body.ly_do
    )


@router.post("/vat-tu-kho/ban/{ban_id}/hoan-tac")
async def ban_hoan_tac(
    ban_id: UUID,
    body: LyDoRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác dòng nhập bù. Gửi lại thì không đảo lần hai."""
    return await ban.hoan_tac_nhap_bu(
        pool, identity=identity, ban_id=str(ban_id), ly_do=body.ly_do
    )


class NhapBuRequest(BaseModel):
    clinic_patient_id: UUID
    vat_tu_id: UUID
    # Rỗng = Kho cơ sở.
    room_id: UUID | None = None
    so_luong: Any = None
    ly_do: Any = None


@router.post("/vat-tu-kho/ban/nhap-bu", status_code=201)
async def ban_nhap_bu(
    body: NhapBuRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Nhập bù dòng quầy quên ghi: chỉ trừ kho, không phát sinh tiền."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        kq: dict[str, Any] = await ban.nhap_bu(
            pool,
            identity=identity,
            khoa_gui=khoa,
            clinic_patient_id=str(body.clinic_patient_id),
            vat_tu_id=str(body.vat_tu_id),
            so_luong=body.so_luong,
            room_id=str(body.room_id) if body.room_id else None,
            ly_do=body.ly_do,
        )
        await idem.save(pool, kq, status_code=201)
    return kq


@router.get("/vat-tu-kho/tieu-hao")
async def bao_cao_tieu_hao(
    ky: str | None = None,
    tu: str | None = None,
    den: str | None = None,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Tiêu hao theo phòng × kỳ (tuần / tháng / tự chọn), tính từ số đếm thật."""
    kq: dict[str, Any] = jsonable_encoder(
        await tieu_hao.doc_tieu_hao(pool, identity=identity, ky=ky, tu=tu, den=den)
    )
    return kq


class DongPhieu(BaseModel):
    vat_tu_id: UUID
    # Bản chụp đơn vị lúc mở danh mục, để server từ chối phiếu từ màn đã cũ.
    don_vi: str | None = Field(..., max_length=40)
    tu_room_id: UUID | None = None
    den_room_id: UUID | None = None
    # Any: số rác phải đi tới service để trả 422 có lời, không bị pydantic 422 trơn.
    so_luong: Any = None
    gia_nhap: Any = None


class PhieuRequest(BaseModel):
    loai: str = Field(max_length=20)
    ghi_chu: str | None = Field(default=None, max_length=1000)
    nha_cung_cap: str | None = Field(default=None, max_length=200)
    dong: list[DongPhieu] = Field(min_length=1, max_length=200)


@router.post("/vat-tu-kho/phieu", status_code=201)
async def lap_phieu(
    body: PhieuRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Một phiếu = một giao dịch. Bắt buộc `Idempotency-Key`: gửi lại = cùng phiếu."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho.tao_phieu(
                pool,
                identity=identity,
                khoa_gui=khoa,
                loai=body.loai,
                ghi_chu=body.ghi_chu,
                nha_cung_cap=body.nha_cung_cap,
                dong=[d.model_dump(mode="json") for d in body.dong],
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class HoanRequest(BaseModel):
    ghi_chu: str | None = Field(default=None, max_length=1000)


@router.post("/vat-tu-kho/phieu/{phieu_id}/hoan", status_code=201)
async def hoan_phieu(
    phieu_id: UUID,
    body: HoanRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
    idem: IdempotencyGuard = Depends(idempotency_guard),
) -> dict[str, Any]:
    """Hoàn tác = lập phiếu đảo (sổ chỉ thêm), mỗi phiếu đảo được một lần."""
    khoa = idem.key
    idem = await idem.acquire(pool, actor_id=identity.auth_user_id)
    if idem.is_replay:
        return idem.cached_response  # type: ignore[return-value]
    async with tra_khoa_neu_bi_tu_choi(idem, pool):
        ket_qua: dict[str, Any] = jsonable_encoder(
            await kho.hoan_phieu(
                pool,
                identity=identity,
                phieu_id=str(phieu_id),
                khoa_gui=khoa,
                ghi_chu=body.ghi_chu,
            )
        )
        await idem.save(pool, ket_qua, status_code=201)
    return ket_qua


class MucRequest(BaseModel):
    vat_tu_id: UUID
    room_id: UUID | None = None
    muc: Any = None


@router.put("/vat-tu-kho/muc-toi-thieu")
async def muc_toi_thieu(
    body: MucRequest,
    identity: StaffIdentity = Depends(_QL),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Quản lý chỉnh mức tối thiểu từng nơi chứa — dữ liệu, không viết cứng."""
    kq: dict[str, Any] = jsonable_encoder(
        await man.dat_muc_toi_thieu(
            pool,
            identity=identity,
            vat_tu_id=str(body.vat_tu_id),
            room_id=str(body.room_id) if body.room_id else None,
            muc=body.muc,
        )
    )
    return kq
