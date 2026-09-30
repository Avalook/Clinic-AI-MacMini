"""Phân quyền = 21 LEGO theo node thanh bên (Tuyền 25/09/2026).

* Quyền theo TÀI KHOẢN: bật lego → có đủ việc; tắt → mất ngay lệnh sau.
* Tắt một lego không lấy mất khối lego khác còn cần.
* Phòng dịch vụ = lego to + lego nhỏ theo phòng (phạm vi ROOM).
* Gói mẫu theo vai giữ nguyên việc hôm nay (không ai mất việc sau migration 15).
* Cửa quản trị (tài khoản, nhân sự, báo cáo, vận hành) hỏi QUYỀN, không hỏi vai.
"""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from clinicai.api.identity import StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.permissions.can import can
from clinicai.permissions.catalogue import MAN, PRESET
from clinicai.permissions.cua_quyen import cua_quyen
from clinicai.services.permission_service import PermissionService
from tests.services.test_permission_db import (  # noqa: F401
    CLINIC,
    _nguoi,
    pool,
    quan_ly,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _co(
    pool: asyncpg.Pool,  # noqa: F811
    ident: StaffIdentity,
    quyen: str,
    phong_id: str | None = None,
) -> bool:
    async with pool.acquire() as conn:
        return await can(conn, ident, quyen, phong_id=phong_id)


def test_21_lego_theo_thu_tu_thanh_ben() -> None:
    assert len(MAN) == 21
    assert list(MAN)[:3] == ["tiep_don", "do_sinh_hieu", "tu_van"]
    assert list(MAN)[-1] == "doi_tac"
    # Lego 19 chỉ nằm trong gói mẫu Quản lý.
    assert [v for v, ks in PRESET.items() if "nhan_su" in ks] == ["MANAGEMENT"]


async def test_bat_tat_lego_co_hieu_luc_ngay(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "RECEPTION")
    svc = PermissionService(pool)
    assert not await _co(pool, x, "report.view")
    await svc.doi_lego(staff_id=x.staff_id, ma="bao_cao", bat=True, identity=quan_ly)
    assert await _co(pool, x, "report.view")
    lego = {
        m["ma"]: m
        for m in (await svc.lego_cua_nguoi(staff_id=x.staff_id, identity=quan_ly))[
            "lego"
        ]
    }
    assert lego["bao_cao"]["bat"] is True
    await svc.doi_lego(staff_id=x.staff_id, ma="bao_cao", bat=False, identity=quan_ly)
    assert not await _co(pool, x, "report.view"), "thu lego là mất ngay"


async def test_tat_phong_dich_vu_giu_khoi_ban_kham_can(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "CSKH")
    svc = PermissionService(pool)
    for ma in ("ban_kham", "phong"):
        await svc.doi_lego(staff_id=x.staff_id, ma=ma, bat=True, identity=quan_ly)
    await svc.doi_lego(staff_id=x.staff_id, ma="phong", bat=False, identity=quan_ly)
    assert not await _co(pool, x, "service.execute.start")
    assert await _co(pool, x, "clinical.record.write"), "Bàn khám còn cần Ghi bệnh án"
    assert await _co(pool, x, "result.form.fill"), "Bàn khám còn cần Kết quả"


async def test_lego_phong_dich_vu_theo_tung_phong(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "CSKH")
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at LIMIT 1",
            CLINIC,
        )
        phong = []
        for _ in range(2):
            phong.append(
                await conn.fetchval(
                    "INSERT INTO clinic_room (clinic_id, location_id, code, name,"
                    " node_code, is_active, accepting, sort) VALUES ($1::uuid,"
                    " $2::uuid, $3, 'Phòng lego thử', 'DICHVU-SIEUAM', true, true, 0)"
                    " RETURNING id::text",
                    CLINIC,
                    loc,
                    f"LG-{uuid.uuid4().hex[:6]}",
                )
            )
    svc = PermissionService(pool)
    await svc.doi_lego(
        staff_id=x.staff_id,
        ma="phong",
        bat=True,
        identity=quan_ly,
        phong_ids=[phong[0]],
    )
    assert await _co(pool, x, "service.execute.start", phong_id=phong[0])
    assert not await _co(pool, x, "service.execute.start", phong_id=phong[1])
    assert not await _co(pool, x, "service.execute.start"), "không phải toàn phòng khám"
    lego = {
        m["ma"]: m
        for m in (await svc.lego_cua_nguoi(staff_id=x.staff_id, identity=quan_ly))[
            "lego"
        ]
    }
    assert lego["phong"]["phong_ids"] == [phong[0]]
    assert lego["phong"]["tat_ca_phong"] is False
    # "Tất cả phòng" = phạm vi toàn phòng khám.
    await svc.doi_lego(staff_id=x.staff_id, ma="phong", bat=True, identity=quan_ly)
    assert await _co(pool, x, "service.execute.start", phong_id=phong[1])


@pytest.mark.parametrize(
    ("vai", "phai_co", "khong_co"),
    [
        # Mở full lego (30/09/2026): CSKH có cả Vận hành; chỉ 4 khối Quản lý giữ.
        (
            "CSKH",
            ["crm.manage", "audit.view", "roster.view", "ops.view"],
            ["account.manage"],
        ),
        ("RECEPTION", ["patient.create", "crm.manage"], ["account.manage"]),
        ("TRUONG_CA", ["dispatch.manage", "report.view"], ["staff.manage"]),
        ("MANAGEMENT", ["account.manage", "staff.manage", "ops.view"], []),
        ("PARTNER", ["partner.work"], ["crm.manage"]),
    ],
)
async def test_goi_mau_giu_viec_hom_nay(
    pool: asyncpg.Pool,  # noqa: F811
    vai: str,
    phai_co: list[str],
    khong_co: list[str],
) -> None:
    async with pool.acquire() as conn:
        x = await _nguoi(conn, vai)
        await conn.fetch(
            "SELECT public.cap_quyen_theo_preset($1::uuid, $2::uuid, $3, $4::text[])",
            CLINIC,
            x.staff_id,
            vai,
            list(PRESET[vai]),
        )
    for q in phai_co:
        assert await _co(pool, x, q), f"{vai} phải còn {q}"
    for q in khong_co:
        assert not await _co(pool, x, q), f"{vai} không được có {q}"


async def test_thu_lego_nhan_su_la_mat_quyen_tai_khoan(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    """Cửa tài khoản hỏi QUYỀN: người không mang vai quản lý được bật lego 19 thì
    qua; thu lego thì bị chặn ngay lệnh sau (bản nhớ quyền quên tức thì)."""
    async with pool.acquire() as conn:
        x = await _nguoi(conn, "RECEPTION")
    cua = cua_quyen("account.manage")
    with pytest.raises(SafetyGateError):
        await cua(identity=x, pool=pool)
    svc = PermissionService(pool)
    await svc.doi_lego(staff_id=x.staff_id, ma="nhan_su", bat=True, identity=quan_ly)
    assert await cua(identity=x, pool=pool) is x
    await svc.doi_lego(staff_id=x.staff_id, ma="nhan_su", bat=False, identity=quan_ly)
    with pytest.raises(SafetyGateError):
        await cua(identity=x, pool=pool)


# ── Ba lego từng "chỉ là nhãn" (kiểm toán 27/09/2026) ──────────────────────


@pytest.mark.parametrize("vai", ["PARTNER", "RECEPTION"])
async def test_lego_doi_tac_la_cua_that(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
    vai: str,
) -> None:
    """`partner.work` nay là cửa của đường đối tác: không lego thì 403 — kể cả
    tài khoản đối tác; bật lego thì vào, bất kể vai; thu lại thì mất ngay."""
    from fastapi import HTTPException

    from clinicai.api.identity import get_partner_identity

    async with pool.acquire() as conn:
        x = await _nguoi(conn, vai)
    with pytest.raises(HTTPException) as loi:
        await get_partner_identity(identity=x, pool=pool)
    assert loi.value.status_code == 403
    svc = PermissionService(pool)
    await svc.doi_lego(staff_id=x.staff_id, ma="doi_tac", bat=True, identity=quan_ly)
    assert await get_partner_identity(identity=x, pool=pool) is x
    await svc.doi_lego(staff_id=x.staff_id, ma="doi_tac", bat=False, identity=quan_ly)
    with pytest.raises(HTTPException):
        await get_partner_identity(identity=x, pool=pool)


async def test_lego_lich_lam_viec_la_cua_doc_lich(
    pool: asyncpg.Pool,  # noqa: F811
    quan_ly: StaffIdentity,  # noqa: F811
) -> None:
    """`roster.view` gác màn Lịch làm việc (trước chỉ cần đăng nhập)."""
    from clinicai.api.v1.routers.config import _ROSTER_READ_GUARD

    async with pool.acquire() as conn:
        x = await _nguoi(conn, "CSKH")
    with pytest.raises(SafetyGateError):
        await _ROSTER_READ_GUARD(identity=x, pool=pool)
    svc = PermissionService(pool)
    await svc.doi_lego(
        staff_id=x.staff_id, ma="lich_lam_viec", bat=True, identity=quan_ly
    )
    assert await _ROSTER_READ_GUARD(identity=x, pool=pool) is x
