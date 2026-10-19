"""Bất biến sổ vật tư, chạy DB thật trước khi triển khai Q1."""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from decimal import Decimal
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError, NotFoundError, ValidationError
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _bo(pool: asyncpg.Pool) -> tuple[Any, str, list[str]]:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        identity = await _nguoi(conn, loc, "PHARMACIST")
        vt = await conn.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group", don_vi)'
            " VALUES ($1::uuid, $2, 'Gạc mô phỏng', 'vat_tu', 'cái')"
            " RETURNING id::text",
            CLINIC,
            f"VT_TEST_{uuid.uuid4().hex}",
        )
        rooms = []
        for _ in range(2):
            rooms.append(
                await conn.fetchval(
                    "INSERT INTO clinic_room (clinic_id, location_id,"
                    " code, name, node_code)"
                    " VALUES ($1::uuid, $2::uuid, $3, 'Phòng vật tư', 'DICHVU-SIEUAM')"
                    " RETURNING id::text",
                    CLINIC,
                    loc,
                    f"VT-{uuid.uuid4().hex}",
                )
            )
    return identity, vt, rooms


async def _ghi(
    pool: asyncpg.Pool,
    identity: Any,
    vt: str,
    loai: str,
    *,
    tu: str | None = None,
    den: str | None = None,
    so: Any = 3,
    khoa: str | None = None,
    nha_cung_cap: str | None = None,
    ghi_chu: str | None = "Bài mô phỏng",
) -> dict[str, Any]:
    from clinicai.services.vat_tu_kho_service import tao_phieu

    return await tao_phieu(
        pool,
        identity=identity,
        khoa_gui=khoa or uuid.uuid4().hex,
        loai=loai,
        ghi_chu=ghi_chu,
        nha_cung_cap=nha_cung_cap,
        dong=[{"vat_tu_id": vt, "tu_room_id": tu, "den_room_id": den, "so_luong": so}],
    )


async def _bat_bien(pool: asyncpg.Pool, identity: Any, vt: str) -> None:
    rows = await pool.fetch(
        "SELECT t.so_luong, coalesce(sum(x.so_luong),0) AS so"
        " FROM vat_tu_ton t LEFT JOIN vat_tu_txn x ON x.ton_id=t.id"
        " AND x.clinic_id=t.clinic_id WHERE t.clinic_id=$1::uuid"
        " AND t.vat_tu_id=$2::uuid GROUP BY t.id",
        identity.clinic_id,
        vt,
    )
    assert all(r["so_luong"] == r["so"] for r in rows)
    from clinicai.services.vat_tu_kho_service import doc_ton

    ton = await doc_ton(pool, identity=identity)
    for r in ton:
        if r["vat_tu_id"] == vt and r["so_luong"] < 0:
            assert "tồn âm" in r["canh_bao"]


async def test_bam_lon_xon_40_luot_10_buoc(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_kho_service import hoan_phieu

    for seed in range(40):
        rng = random.Random(seed)
        identity, vt, rooms = await _bo(pool)
        da_tao: list[str] = []
        chuoi: list[Any] = []
        for _ in range(10):
            loai = rng.choice(
                [
                    "NHAP",
                    "XUAT_PHONG",
                    "TRA_KHO",
                    "CHUYEN_PHONG",
                    "KIEM",
                    "DIEU_CHINH",
                    "HUY",
                    "GUI_LAI",
                    "HOAN",
                ]
            )
            a, b = rng.sample(rooms, 2)
            so = rng.randint(0 if loai in {"KIEM", "DIEU_CHINH"} else 1, 12)
            chuoi.append((loai, a, b, so))
            try:
                truoc = await pool.fetchval(
                    "SELECT coalesce(sum(so_luong),0) FROM vat_tu_ton"
                    " WHERE clinic_id=$1::uuid AND vat_tu_id=$2::uuid",
                    CLINIC,
                    vt,
                )
                if loai == "HOAN" and da_tao:
                    await hoan_phieu(
                        pool,
                        identity=identity,
                        phieu_id=da_tao.pop(),
                        khoa_gui=uuid.uuid4().hex,
                        ghi_chu="Đảo mô phỏng",
                    )
                elif loai == "GUI_LAI":
                    key = uuid.uuid4().hex
                    p = await _ghi(pool, identity, vt, "NHAP", so=so, khoa=key)
                    q = await _ghi(pool, identity, vt, "NHAP", so=so, khoa=key)
                    assert p["id"] == q["id"] and q["gui_lai"]
                    da_tao.append(p["id"])
                elif loai != "HOAN":
                    tu = (
                        a
                        if loai
                        in {"TRA_KHO", "CHUYEN_PHONG", "KIEM", "DIEU_CHINH", "HUY"}
                        else None
                    )
                    den = b if loai in {"NHAP", "XUAT_PHONG", "CHUYEN_PHONG"} else None
                    p = await _ghi(pool, identity, vt, loai, tu=tu, den=den, so=so)
                    da_tao.append(p["id"])
                if loai in {"XUAT_PHONG", "TRA_KHO", "CHUYEN_PHONG", "KIEM"}:
                    sau = await pool.fetchval(
                        "SELECT coalesce(sum(so_luong),0) FROM vat_tu_ton"
                        " WHERE clinic_id=$1::uuid AND vat_tu_id=$2::uuid",
                        CLINIC,
                        vt,
                    )
                    assert sau == truoc
                await _bat_bien(pool, identity, vt)
            except Exception as exc:
                raise AssertionError(f"seed={seed}; chuỗi={chuoi}") from exc


async def test_hoan_phieu_va_gui_trung_dong_thoi(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_kho_service import hoan_phieu

    identity, vt, rooms = await _bo(pool)
    key = uuid.uuid4().hex
    ps = await asyncio.gather(
        *[
            _ghi(pool, identity, vt, "XUAT_PHONG", den=rooms[0], khoa=key)
            for _ in range(4)
        ]
    )
    assert len({p["id"] for p in ps}) == 1
    await hoan_phieu(
        pool, identity=identity, phieu_id=ps[0]["id"], khoa_gui=uuid.uuid4().hex
    )
    assert (
        await pool.fetchval(
            "SELECT sum(so_luong) FROM vat_tu_ton WHERE vat_tu_id=$1::uuid", vt
        )
        == 0
    )
    await _bat_bien(pool, identity, vt)
    with pytest.raises(ConflictError):
        await hoan_phieu(
            pool, identity=identity, phieu_id=ps[0]["id"], khoa_gui=uuid.uuid4().hex
        )


@pytest.mark.parametrize("so", [None, "rác", "NaN", "Infinity", -1, "", True, "1.2345"])
async def test_so_rac_khong_ghi(pool: asyncpg.Pool, so: Any) -> None:
    identity, vt, _ = await _bo(pool)
    with pytest.raises(ValidationError):
        await _ghi(pool, identity, vt, "NHAP", so=so)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM vat_tu_txn WHERE vat_tu_id=$1::uuid", vt
        )
        == 0
    )


async def test_cung_phong_va_khac_co_so(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    with pytest.raises(ValidationError):
        await _ghi(pool, identity, vt, "CHUYEN_PHONG", tu=rooms[0], den=rooms[0])
    loc = await pool.fetchval(
        "INSERT INTO clinic_location (clinic_id, code, name)"
        " VALUES ($1::uuid, $2, 'Cơ sở khác') RETURNING id::text",
        CLINIC,
        uuid.uuid4().hex,
    )
    await pool.execute(
        "UPDATE clinic_room SET location_id=$1::uuid WHERE id=$2::uuid", loc, rooms[0]
    )
    with pytest.raises(NotFoundError):
        await _ghi(pool, identity, vt, "NHAP", den=rooms[0])


async def test_phong_tat_con_ton_va_kiem_khong_doi_ton(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    await _ghi(pool, identity, vt, "NHAP", den=rooms[0], so=5)
    await pool.execute(
        "UPDATE clinic_room SET is_active=false WHERE id=$1::uuid", rooms[0]
    )
    p = await _ghi(pool, identity, vt, "KIEM", tu=rooms[0], so=2)
    row = await pool.fetchrow(
        "SELECT so_luong, ton_may, thuc_te FROM vat_tu_txn WHERE phieu_id=$1::uuid",
        p["id"],
    )
    assert tuple(row.values()) == (Decimal(0), Decimal(5), Decimal(2))
    await _ghi(pool, identity, vt, "DIEU_CHINH", tu=rooms[0], so=2)
    await _bat_bien(pool, identity, vt)


async def test_tra_nha_san_xuat_giam_ton_va_hoan_tac_dung_so(
    pool: asyncpg.Pool,
) -> None:
    from clinicai.services.vat_tu_kho_service import hoan_phieu

    identity, vt, _ = await _bo(pool)
    await _ghi(pool, identity, vt, "NHAP", so=5)
    with pytest.raises(ValidationError):
        await _ghi(pool, identity, vt, "TRA_NCC", so=2, ghi_chu="Thiếu NCC")
    p = await _ghi(
        pool,
        identity,
        vt,
        "TRA_NCC",
        so=2,
        khoa=uuid.uuid4().hex,
        nha_cung_cap="Nhà cung cấp thử",
    )
    phieu = await pool.fetchrow(
        "SELECT loai, nha_cung_cap FROM vat_tu_phieu WHERE id=$1::uuid", p["id"]
    )
    assert tuple(phieu.values()) == ("TRA_NCC", "Nhà cung cấp thử")
    assert (
        await pool.fetchval(
            "SELECT so_luong FROM vat_tu_ton WHERE vat_tu_id=$1::uuid", vt
        )
        == 3
    )
    await hoan_phieu(
        pool, identity=identity, phieu_id=p["id"], khoa_gui=uuid.uuid4().hex
    )
    assert (
        await pool.fetchval(
            "SELECT so_luong FROM vat_tu_ton WHERE vat_tu_id=$1::uuid", vt
        )
        == 5
    )
    await _bat_bien(pool, identity, vt)


async def test_sql_chot_so_chi_them_va_ton_khong_sua_tay(pool: asyncpg.Pool) -> None:
    identity, vt, _ = await _bo(pool)
    p = await _ghi(pool, identity, vt, "NHAP")
    for sql in [
        "UPDATE vat_tu_txn SET so_luong=9 WHERE phieu_id=$1::uuid",
        "DELETE FROM vat_tu_txn WHERE phieu_id=$1::uuid",
        "UPDATE vat_tu_phieu SET ghi_chu='đè' WHERE id=$1::uuid",
        "UPDATE vat_tu_ton SET so_luong=90 WHERE id IN (SELECT ton_id FROM"
        " vat_tu_txn WHERE phieu_id=$1::uuid)",
    ]:
        with pytest.raises(asyncpg.CheckViolationError):
            await pool.execute(sql, p["id"])
    await _bat_bien(pool, identity, vt)


async def test_ben_nhan_notify_chay_xen_giua_phieu(pool: asyncpg.Pool) -> None:
    """LISTEN thật và đọc lại sau mỗi phiếu, không chỉ gom sự kiện ở cuối."""
    from clinicai.services.vat_tu_kho_service import doc_ton, hoan_phieu

    identity, vt, rooms = await _bo(pool)
    tin: asyncio.Queue[str] = asyncio.Queue()

    def nhan(conn: Any, pid: int, channel: str, payload: str) -> None:
        if json.loads(payload).get("t") in {"vat_tu_phieu", "vat_tu_ton", "vat_tu_txn"}:
            tin.put_nowait(payload)

    async with pool.acquire() as receiver:
        await receiver.add_listener("clinicai_changes", nhan)
        try:
            p = await _ghi(pool, identity, vt, "NHAP", so=7)
            await asyncio.wait_for(tin.get(), timeout=3)
            assert any(
                r["vat_tu_id"] == vt and r["so_luong"] == 7
                for r in await doc_ton(pool, identity=identity)
            )
            while not tin.empty():
                tin.get_nowait()
            await _ghi(pool, identity, vt, "XUAT_PHONG", den=rooms[0], so=9)
            await asyncio.wait_for(tin.get(), timeout=3)
            ton = await doc_ton(pool, identity=identity)
            assert any(
                r["vat_tu_id"] == vt and r["so_luong"] == -2 and r["canh_bao"]
                for r in ton
            )
            while not tin.empty():
                tin.get_nowait()
            await hoan_phieu(
                pool, identity=identity, phieu_id=p["id"], khoa_gui=uuid.uuid4().hex
            )
            await asyncio.wait_for(tin.get(), timeout=3)
            await _bat_bien(pool, identity, vt)
        finally:
            await receiver.remove_listener("clinicai_changes", nhan)


@pytest.mark.parametrize(
    "loai,delta,dem",
    [
        ("NHAP", -5, None),
        ("HUY", 5, None),
        ("DIEU_CHINH", 9, 2),
        ("XUAT_PHONG", -3, None),
    ],
)
async def test_sql_khong_ghi_sai_nghia_phieu(
    pool: asyncpg.Pool, loai: str, delta: int, dem: int | None
) -> None:
    identity, vt, _ = await _bo(pool)
    await _ghi(pool, identity, vt, "NHAP", so=5)
    ton_id = await pool.fetchval(
        "SELECT id::text FROM vat_tu_ton WHERE vat_tu_id=$1::uuid", vt
    )
    with pytest.raises(asyncpg.CheckViolationError):
        async with pool.acquire() as conn, conn.transaction():
            p = await conn.fetchval(
                "INSERT INTO vat_tu_phieu"
                "(clinic_id,location_id,ma_phieu,loai,khoa_gui,tao_boi)"
                " VALUES($1::uuid,$2::uuid,$3,$4,$3,$5::uuid) RETURNING id::text",
                CLINIC,
                identity.location_id,
                uuid.uuid4().hex,
                loai,
                identity.staff_id,
            )
            await conn.execute(
                "INSERT INTO vat_tu_txn"
                "(clinic_id,phieu_id,ton_id,vat_tu_id,so_luong,ton_may,thuc_te)"
                " VALUES($1::uuid,$2::uuid,$3::uuid,$4::uuid,$5,0,$6)",
                CLINIC,
                p,
                ton_id,
                vt,
                delta,
                dem,
            )
    await _bat_bien(pool, identity, vt)


async def test_sql_khong_them_dong_sau_khi_luu(pool: asyncpg.Pool) -> None:
    identity, vt, _ = await _bo(pool)
    p = await _ghi(pool, identity, vt, "NHAP")
    with pytest.raises(asyncpg.CheckViolationError):
        await pool.execute(
            "INSERT INTO vat_tu_txn"
            "(clinic_id,phieu_id,ton_id,vat_tu_id,so_luong,ton_may)"
            " SELECT clinic_id,phieu_id,ton_id,vat_tu_id,1,0 FROM vat_tu_txn"
            " WHERE phieu_id=$1::uuid",
            p["id"],
        )
    await _bat_bien(pool, identity, vt)


async def test_sql_chuyen_khong_lech_khi_constraint_immediate(
    pool: asyncpg.Pool,
) -> None:
    from clinicai.services.vat_tu_kho_service import _ghi as ghi_so
    from clinicai.services.vat_tu_kho_service import _khoa_co_so, _mo_phieu, _ton

    identity, vt, rooms = await _bo(pool)
    with pytest.raises(asyncpg.CheckViolationError):
        async with pool.acquire() as conn, conn.transaction():
            await _khoa_co_so(conn, identity)
            p = await _mo_phieu(conn, identity, "CHUYEN_PHONG", uuid.uuid4().hex, None)
            a = await _ton(conn, identity, vt, rooms[0])
            b = await _ton(conn, identity, vt, rooms[1])
            await ghi_so(conn, identity, p["id"], vt, a, Decimal(-3), Decimal(0))
            await ghi_so(conn, identity, p["id"], vt, b, Decimal(3), Decimal(0))
            await conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            await ghi_so(conn, identity, p["id"], vt, b, Decimal(1), Decimal(0))
    await _bat_bien(pool, identity, vt)
