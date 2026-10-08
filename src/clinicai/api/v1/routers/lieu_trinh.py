"""Liệu trình điều trị nhiều buổi (08/10/2026) — router mỏng.

Quyền và mọi luật nằm trong ``services/lieu_trinh_service.py`` (Python) và
migration 20261008100000 (Postgres: gắn / gỡ buổi, trạng thái suy ra, lịch sử).
Lệnh ghi mang ``idempotency_key`` (bấm hai lần = một lần) và ``expected_revision``
(màn cầm bản cũ → 409 ``STALE_LIEU_TRINH``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.services.lieu_trinh_service import LieuTrinhService

router = APIRouter()

_KHOA = Field(min_length=8, max_length=200)


# ── đọc ────────────────────────────────────────────────────────────────────


@router.get("/lieu-trinh/theo-luot/{visit_id}")
async def theo_luot(
    visit_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Thẻ liệu trình ở hồ sơ khám: liệu trình + chỉ định điều trị của lượt."""
    return await LieuTrinhService(pool).theo_luot(identity=identity, visit_id=visit_id)


@router.get("/lieu-trinh/theo-khach/{clinic_patient_id}")
async def theo_khach(
    clinic_patient_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Khung khách / quầy: mọi liệu trình của khách."""
    return await LieuTrinhService(pool).theo_khach(
        identity=identity, clinic_patient_id=clinic_patient_id
    )


@router.get("/lieu-trinh/chip")
async def chip(
    luot: str = Query("", max_length=12000),
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chip "Buổi k/N · đã trả trước" theo chỉ định + "còn N buổi đã trả" theo
    lượt (``luot`` = mã lượt cách nhau dấu phẩy)."""
    return await LieuTrinhService(pool).chip(identity=identity, visit_ids=luot)


@router.get("/lieu-trinh/cskh")
async def cskh(
    loai: str = Query(..., max_length=20),
    qua_ngay: str | None = Query(None, max_length=10),
    ca_co_lich: bool = False,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """CSKH: ``de_xuat`` (chưa đăng ký) | ``dang_do`` (quá X ngày chưa quay lại)."""
    return await LieuTrinhService(pool).cskh(
        identity=identity, loai=loai, qua_ngay=qua_ngay, ca_co_lich=ca_co_lich
    )


@router.get("/lieu-trinh/{lieu_trinh_id}")
async def chi_tiet(
    lieu_trinh_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LieuTrinhService(pool).chi_tiet(
        identity=identity, lieu_trinh_id=lieu_trinh_id
    )


@router.get("/lieu-trinh/{lieu_trinh_id}/lich-su")
async def lich_su(
    lieu_trinh_id: UUID,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Lịch sử sửa (kế hoạch + gắn/gỡ buổi), dòng nào hoàn tác được."""
    return await LieuTrinhService(pool).lich_su(
        identity=identity, lieu_trinh_id=lieu_trinh_id
    )


# ── ghi ────────────────────────────────────────────────────────────────────


class TaoBody(BaseModel):
    visit_id: UUID
    so_buoi: int = Field(ge=1, le=200)
    service_order_id: UUID | None = None
    service_code: str | None = Field(default=None, max_length=64)
    ghi_chu: str | None = Field(default=None, max_length=1000)
    tach_khoi_lieu_trinh_cu: bool = False
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh")
async def tao(
    body: TaoBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đề xuất liệu trình — kèm chỉ định hôm nay (buổi 1) hoặc chỉ đề xuất."""
    return await LieuTrinhService(pool).tao(
        identity=identity,
        visit_id=body.visit_id,
        so_buoi=body.so_buoi,
        service_order_id=body.service_order_id,
        service_code=body.service_code,
        ghi_chu=body.ghi_chu,
        tach_khoi_lieu_trinh_cu=body.tach_khoi_lieu_trinh_cu,
        idempotency_key=body.idempotency_key,
    )


class DieuChinhBody(BaseModel):
    expected_revision: int = Field(ge=1)
    so_buoi: int | None = Field(default=None, ge=1, le=200)
    ghi_chu: str | None = Field(default=None, max_length=1000)
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/{lieu_trinh_id}/dieu-chinh")
async def dieu_chinh(
    lieu_trinh_id: UUID,
    body: DieuChinhBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Đổi số buổi và/hoặc ghi chú (gửi ``ghi_chu: ""`` để xoá ghi chú)."""
    co = body.model_fields_set
    kw: dict[str, Any] = {}
    if "so_buoi" in co and body.so_buoi is not None:
        kw["so_buoi"] = body.so_buoi
    if "ghi_chu" in co:
        kw["ghi_chu"] = body.ghi_chu
    return await LieuTrinhService(pool).dieu_chinh(
        identity=identity,
        lieu_trinh_id=lieu_trinh_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        **kw,
    )


class DangKyBody(BaseModel):
    expected_revision: int = Field(ge=1)
    so_buoi: int | None = Field(default=None, ge=1, le=200)
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/{lieu_trinh_id}/dang-ky")
async def dang_ky(
    lieu_trinh_id: UUID,
    body: DangKyBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """CSKH [Đăng ký] 1 buổi / N buổi → đang làm."""
    return await LieuTrinhService(pool).dang_ky(
        identity=identity,
        lieu_trinh_id=lieu_trinh_id,
        expected_revision=body.expected_revision,
        so_buoi=body.so_buoi,
        idempotency_key=body.idempotency_key,
    )


class DungBody(BaseModel):
    expected_revision: int = Field(ge=1)
    ly_do: str | None = Field(default=None, max_length=500)
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/{lieu_trinh_id}/dung")
async def dung(
    lieu_trinh_id: UUID,
    body: DungBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LieuTrinhService(pool).dung(
        identity=identity,
        lieu_trinh_id=lieu_trinh_id,
        expected_revision=body.expected_revision,
        ly_do=body.ly_do,
        idempotency_key=body.idempotency_key,
    )


class RevisionBody(BaseModel):
    expected_revision: int = Field(ge=1)
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/{lieu_trinh_id}/mo-lai")
async def mo_lai(
    lieu_trinh_id: UUID,
    body: RevisionBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    return await LieuTrinhService(pool).mo_lai(
        identity=identity,
        lieu_trinh_id=lieu_trinh_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
    )


class HoanTacBody(BaseModel):
    lich_su_id: UUID
    expected_revision: int = Field(ge=1)
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/{lieu_trinh_id}/hoan-tac")
async def hoan_tac(
    lieu_trinh_id: UUID,
    body: HoanTacBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Hoàn tác lần sửa mới nhất (dòng lịch sử ``hoan_tac_duoc``)."""
    return await LieuTrinhService(pool).hoan_tac(
        identity=identity,
        lieu_trinh_id=lieu_trinh_id,
        lich_su_id=body.lich_su_id,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
    )


class GanBody(BaseModel):
    service_order_id: UUID
    lieu_trinh_id: UUID
    expected_lieu_trinh_id: UUID | None = None
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/buoi/gan")
async def gan(
    body: GanBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Chọn liệu trình cho một chỉ định (chuyển nếu đang thuộc liệu trình khác)."""
    return await LieuTrinhService(pool).gan(
        identity=identity,
        service_order_id=body.service_order_id,
        lieu_trinh_id=body.lieu_trinh_id,
        expected_lieu_trinh_id=body.expected_lieu_trinh_id,
        idempotency_key=body.idempotency_key,
    )


class GoBody(BaseModel):
    service_order_id: UUID
    expected_lieu_trinh_id: UUID
    idempotency_key: str = _KHOA


@router.post("/lieu-trinh/buoi/go")
async def go(
    body: GoBody,
    identity: StaffIdentity = Depends(get_current_identity),
    pool: asyncpg.Pool = Depends(get_db_pool),
) -> dict[str, Any]:
    """Gỡ chỉ định khỏi liệu trình (thành buổi lẻ)."""
    return await LieuTrinhService(pool).go(
        identity=identity,
        service_order_id=body.service_order_id,
        expected_lieu_trinh_id=body.expected_lieu_trinh_id,
        idempotency_key=body.idempotency_key,
    )
