"""Xếp phòng ở quầy thu lúc nào cũng được, trưởng ca đè được (Tuyền 25/09 — P3).

Sáu ca của prompt: quầy thu xếp trước thu (phòng dự kiến) / sau thu / đổi lần 2;
trưởng ca đè quầy thu; quầy thu đổi sau trưởng ca → ĐƯỢC (Tuyền 29/09/2026 bỏ
khoá "trưởng ca đã xếp" — thay bằng lịch sử ở Hành trình khách); trưởng ca đổi
sau trưởng ca → được. Nguồn theo LỆNH (quyền của lego gọi), không theo vai.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.services.service_routing_service import ServiceRoutingService
from tests.chay_nguoi_dua_tin import chay_hanh_trinh
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_check_in_lai_sau_hoan_tac_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
)
from tests.services.test_thu_tien_xep_phong_mang_sang_db import (
    NODE,
    _benh_nhan,
    _check_in,
    _chon,
    _don,
    _dung,
    _kham_va_chi_dinh,
    _khoa,
    _thu,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _phong_thu_hai(pool: asyncpg.Pool, loc: str) -> str:  # noqa: F811
    async with pool.acquire() as conn:
        phong = str(
            await conn.fetchval(
                "INSERT INTO clinic_room (clinic_id, location_id, code, name,"
                " node_code, is_active, accepting, sort) VALUES ($1::uuid,"
                " $2::uuid, $3, 'Phòng hai', $4, true, true, 0) RETURNING id::text",
                CLINIC,
                loc,
                f"P2-{uuid.uuid4().hex[:6]}",
                NODE,
            )
        )
        await conn.execute(
            "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
            " VALUES ($1::uuid, $2::uuid, $3)",
            CLINIC,
            phong,
            NODE,
        )
    return phong


async def _nguon(pool: asyncpg.Pool, order: str) -> tuple[str, str | None]:  # noqa: F811
    r = await pool.fetchrow(
        "SELECT room_id::text AS room_id, routing_nguon FROM service_order"
        " WHERE id = $1::uuid",
        order,
    )
    assert r is not None
    return str(r["room_id"]), r["routing_nguon"]


async def test_sau_ca_xep_phong_quay_thu_va_truong_ca(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ca = await _dung(pool)
    phong_hai = await _phong_thu_hai(pool, ca.loc)
    async with pool.acquire() as conn:
        truong_ca = await _nguoi(conn, ca.loc, "TRUONG_CA")
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    svc = ServiceRoutingService(pool)

    # 1. Quầy thu chọn phòng DỰ KIẾN trước khi thu → thu xong H4 xếp đúng phòng.
    await svc.dat_phong_du_kien(order_id=order, room_id=phong_hai, identity=ca.le_tan)
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    assert await _nguon(pool, order) == (phong_hai, "tu_dong")

    async def xep(ai: object, phong: str, nguon: str) -> None:
        rev = int((await _don(pool, order))["routing_revision"])
        await svc.assign(
            order_id=order,
            room_id=phong,
            expected_routing_revision=rev,
            reason_code="MANUAL_CORRECTION",
            identity=ai,  # type: ignore[arg-type]
            idempotency_key=_khoa(),
            nguon=nguon,
        )

    # 2. Quầy thu đổi SAU khi thu.
    await xep(ca.le_tan, ca.phong, "quay_thu")
    assert await _nguon(pool, order) == (ca.phong, "quay_thu")
    # 3. Quầy thu đổi lần 2 (nhầm lần đầu).
    await xep(ca.le_tan, phong_hai, "quay_thu")
    assert await _nguon(pool, order) == (phong_hai, "quay_thu")
    # 4. Trưởng ca đè quầy thu.
    await xep(truong_ca, ca.phong, "truong_ca")
    assert await _nguon(pool, order) == (ca.phong, "truong_ca")
    # 5. Quầy thu đổi sau trưởng ca → ĐƯỢC (29/09/2026, cả hai ô của quầy).
    await xep(ca.le_tan, phong_hai, "quay_thu")
    assert await _nguon(pool, order) == (phong_hai, "quay_thu")
    await svc.dat_phong_du_kien(order_id=order, room_id=ca.phong, identity=ca.le_tan)
    assert await _nguon(pool, order) == (ca.phong, "quay_thu")
    # 6. Trưởng ca đổi lại → được.
    await xep(truong_ca, phong_hai, "truong_ca")
    assert await _nguon(pool, order) == (phong_hai, "truong_ca")


async def test_nguon_hoi_quyen_cua_lego_goi(pool: asyncpg.Pool) -> None:  # noqa: F811
    """Điều dưỡng có quyền xếp phòng chung, nhưng không có lego Thanh toán dịch vụ
    hay Điều phối khách → không xưng được nguồn quầy thu / trưởng ca."""
    ca = await _dung(pool)
    visit = await _check_in(pool, ca, await _benh_nhan(pool, ca), ca.loai_kham)
    _con, order = await _kham_va_chi_dinh(pool, ca, visit)
    await _chon(pool, ca, visit, [order])
    await _thu(pool, visit, ca.le_tan)
    await chay_hanh_trinh(pool)
    rev = int((await _don(pool, order))["routing_revision"])
    await ve_goi_mau_cu(pool, ca.dd)  # gói lego cũ (mở full lego 30/09)
    for nguon in ("quay_thu", "truong_ca"):
        with pytest.raises(SafetyGateError):
            await ServiceRoutingService(pool).assign(
                order_id=order,
                room_id=ca.phong,
                expected_routing_revision=rev,
                reason_code="MANUAL_CORRECTION",
                identity=ca.dd,
                idempotency_key=_khoa(),
                nguon=nguon,
            )
