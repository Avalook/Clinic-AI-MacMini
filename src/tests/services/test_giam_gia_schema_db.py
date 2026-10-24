"""Bất biến giảm giá ở Postgres: sổ chỉ thêm và ảnh chụp khớp khi commit."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import asyncpg
import pytest

from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay

pytest_plugins = [
    "tests.services.test_luot_kham_service_db",
    "tests.services.test_tien_thuoc_cp1_db",
]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _giam(conn, quay, **changes):
    values = {
        "kind": "dich_vu",
        "pham_vi": "HOA_DON",
        "kieu": "SO_TIEN",
        "gia_tri": Decimal(10),
        "source_type": None,
        "source_id": None,
        **changes,
    }
    return await conn.fetchval(
        "INSERT INTO giam_gia (clinic_id, visit_id, kind, pham_vi, kieu, gia_tri,"
        " source_type, source_id, ly_do, tao_boi)"
        " VALUES ($1::uuid,$2::uuid,$3,$4,$5,$6,$7,$8,'Thử giảm',$9::uuid)"
        " RETURNING id",
        CLINIC,
        quay.visit_id,
        values["kind"],
        values["pham_vi"],
        values["kieu"],
        values["gia_tri"],
        values["source_type"],
        values["source_id"],
        quay.thu_ngan.staff_id,
    )


async def _cycle(conn, quay, status="PAID", kind="dich_vu"):
    cycle = uuid.uuid4()
    await conn.execute(
        "INSERT INTO payment_cycle (payment_cycle_id, clinic_id, visit_id, kind,"
        " amount, status, legacy, paid_at) VALUES"
        " ($1,$2::uuid,$3::uuid,$4,90,$5,true,now())",
        cycle,
        CLINIC,
        quay.visit_id,
        kind,
        status,
    )
    return cycle


async def _line(conn, quay, cycle, *, discount=10, total=90, owner="CLINIC"):
    patient = await conn.fetchval(
        "SELECT clinic_patient_id FROM visit WHERE visit_id=$1::uuid", quay.visit_id
    )
    payment = await conn.fetchval(
        "INSERT INTO payment (clinic_id,visit_id,clinic_patient_id,kind,"
        "status,amount,paid_at)"
        " VALUES ($1::uuid,$2::uuid,$3,'dich_vu','PAID',90,now()) RETURNING id",
        CLINIC,
        quay.visit_id,
        patient,
    )
    await conn.execute(
        "INSERT INTO payment_bill_line (clinic_id,payment_id,payment_cycle_id,"
        "visit_id,kind,"
        " source_type,source_id,name_snapshot,quantity,unit_price,"
        "line_total,billing_owner,giam)"
        " VALUES ($1::uuid,$2,$3,$4::uuid,'dich_vu','exam',$4,'Thử',1,100,$5,$6,$7)",
        CLINIC,
        payment,
        cycle,
        quay.visit_id,
        total,
        owner,
        discount,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"gia_tri": Decimal(-1)},
        {"gia_tri": Decimal(0)},
        {"kieu": "PHAN_TRAM", "gia_tri": Decimal(150)},
        {"gia_tri": Decimal("1.25")},
        {"pham_vi": "DONG"},
        {"source_id": "x"},
    ],
)
async def test_check_gia_tri_va_nguon(q: Quay, changes):
    async with q.pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError):
            await _giam(conn, q, **changes)


async def test_chi_them_va_mot_giam_dang_cho(q: Quay):
    async with q.pool.acquire() as conn:
        gid = await _giam(conn, q)
        with pytest.raises(asyncpg.UniqueViolationError):
            await _giam(conn, q)
        for sql in (
            "DELETE FROM giam_gia WHERE id=$1",
            "UPDATE giam_gia SET ly_do='khác' WHERE id=$1",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(sql, gid)
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute("UPDATE giam_gia SET so_tien_ap=10 WHERE id=$1", gid)
        await conn.execute(
            "UPDATE giam_gia SET"
            " huy_luc=now(),huy_boi=$2::uuid,ly_do_huy='Bỏ' WHERE id=$1",
            gid,
            q.thu_ngan.staff_id,
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.execute(
                "UPDATE giam_gia SET huy_luc=NULL,huy_boi=NULL WHERE id=$1", gid
            )
        await _giam(conn, q)


async def test_gan_sai_loai_lan_thu_bi_chan(q: Quay):
    async with q.pool.acquire() as conn:
        gid = await _giam(conn, q)
        cycle = await _cycle(conn, q, kind="thuoc")
        with pytest.raises(asyncpg.CheckViolationError, match="cùng lượt"):
            async with conn.transaction():
                await conn.execute(
                    "UPDATE giam_gia SET payment_cycle_id=$2,so_tien_ap=0 WHERE id=$1",
                    gid,
                    cycle,
                )


@pytest.mark.parametrize(
    "status,next_status", [("PAID", "VOIDED"), ("PENDING_VERIFICATION", "CANCELLED")]
)
async def test_tong_hoan_den_commit_va_huy_tra_ve(q: Quay, status, next_status):
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            gid = await _giam(conn, q)
            cycle = await _cycle(conn, q, status)
            await _line(conn, q, cycle)
            await conn.execute(
                "UPDATE giam_gia SET payment_cycle_id=$2,so_tien_ap=10 WHERE id=$1",
                gid,
                cycle,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await conn.execute(
                "UPDATE giam_gia SET huy_luc=now(),huy_boi=$2::uuid WHERE id=$1",
                gid,
                q.thu_ngan.staff_id,
            )
        await conn.execute(
            "UPDATE payment_cycle SET status=$2,closed_at=now(),closed_by=$3::uuid,"
            "close_reason='Thử huỷ'"
            " WHERE payment_cycle_id=$1",
            cycle,
            next_status,
            q.thu_ngan.staff_id,
        )
        row = await conn.fetchrow(
            "SELECT payment_cycle_id,so_tien_ap,huy_luc FROM giam_gia WHERE id=$1", gid
        )
        assert tuple(row) == (None, None, None)


async def test_tong_lech_bi_chan_o_commit(q: Quay):
    async with q.pool.acquire() as conn:
        with pytest.raises(asyncpg.CheckViolationError, match="tổng giảm"):
            async with conn.transaction():
                cycle = await _cycle(conn, q)
                await _line(conn, q, cycle)


@pytest.mark.parametrize(
    "discount,total,owner",
    [(-1, 101, "CLINIC"), (10, 80, "CLINIC"), (10, 90, "EXTERNAL_PARTNER")],
)
async def test_anh_chup_check(q: Quay, discount, total, owner):
    async with q.pool.acquire() as conn:
        cycle = await _cycle(conn, q)
        with pytest.raises(asyncpg.CheckViolationError):
            await _line(conn, q, cycle, discount=discount, total=total, owner=owner)


async def test_don_khach_thu_xoa_va_luu_so_giam(q: Quay):
    async with q.pool.acquire() as conn:
        gid = await _giam(conn, q)
        patient = await conn.fetchval(
            "SELECT clinic_patient_id FROM visit WHERE visit_id=$1::uuid", q.visit_id
        )
        for real in (False, True):
            result = await conn.fetchval(
                "SELECT don_khach_thu($1::uuid,ARRAY[$2::uuid],$3)",
                CLINIC,
                patient,
                real,
            )
            result = json.loads(result) if isinstance(result, str) else result
            assert result["so_dong"]["giam_gia"] == 1
        assert not await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM giam_gia WHERE id=$1)", gid
        )
        assert await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM du_lieu_da_xoa WHERE"
            " bang='giam_gia' AND du_lieu->>'id'=$1)",
            str(gid),
        )


async def test_rls_khong_grant_ghi_cho_authenticated(q: Quay):
    async with q.pool.acquire() as conn:
        assert await conn.fetchval(
            "SELECT relrowsecurity FROM pg_class WHERE oid='giam_gia'::regclass"
        )
        roles = await conn.fetchval(
            "SELECT roles FROM pg_policies WHERE tablename='giam_gia' AND cmd='SELECT'"
        )
        assert roles == ["authenticated"]
        assert not await conn.fetchval(
            "SELECT has_table_privilege('authenticated','giam_gia','UPDATE')"
        )
