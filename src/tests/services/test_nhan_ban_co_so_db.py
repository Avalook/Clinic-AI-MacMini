"""scripts/nhan-ban-co-so.py — nhân bản Kim Ngưu → Hào Nam (Tuyền chốt 08/10/2026).

    scripts/test-nhanh.sh src/tests/services/test_nhan_ban_co_so_db.py

Mỗi bài dựng MỘT phòng khám riêng (mã ngẫu nhiên) có cơ sở KN + phòng / việc /
dịch vụ / ngưỡng / vị trí / vai được vào trạm / người–vị trí / quyền ROOM, chạy
hàm lõi `chay()` của script trên đó, rồi xoá sạch phòng khám ấy. Seed vẫn có
cơ sở KN ở phòng khám mặc định — nên gọi không kèm `clinic_id` phải bị từ chối.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

pytestmark = [pytest.mark.db]  # asyncio_mode=auto: bài async tự chạy

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "nhan-ban-co-so.py"


def _nap() -> ModuleType:
    spec = importlib.util.spec_from_file_location("nhan_ban_co_so", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nhan_ban_co_so"] = mod  # dataclass cần module trong sys.modules
    spec.loader.exec_module(mod)
    return mod


NB = _nap()

NODES = [
    "LUOTKHAM-01",
    "LUOTKHAM-02",
    "LUOTKHAM-03",
    "THUOC-04",
    "KHAM-NOITIET",
    "KHAM-PHUKHOA",
    "KHAM-SANKHOA",
    "DICHVU-SIEUAM",
    "DICHVU-THUTHUAT",
    "DICHVU-LAYMAU-MAU",
    "DICHVU-DXA",
]
DICH_VU = ["DV-NB-A", "DV-NB-B", "DV-NB-C"]
# mã → (việc chính, các việc, dịch vụ, bật, đối tác)
PHONG_KN: dict[str, tuple[str, list[str], list[str], bool, bool]] = {
    "KN-TIEPDON": ("LUOTKHAM-01", ["LUOTKHAM-01"], [], True, False),
    "KN-DOCHISO": ("LUOTKHAM-03", ["LUOTKHAM-03", "DICHVU-DXA"], [], True, False),
    "KN-LAYMAU": (
        "DICHVU-LAYMAU-MAU",
        ["DICHVU-LAYMAU-MAU"],
        ["DV-NB-C"],
        False,
        False,
    ),
    "KN-QUAYTHUOC": ("THUOC-04", ["THUOC-04"], [], True, False),
    "KN-TUVAN": ("LUOTKHAM-02", ["LUOTKHAM-02"], [], True, False),
    "KN-NOITIET": (
        "KHAM-NOITIET",
        ["KHAM-NOITIET", "KHAM-PHUKHOA"],
        ["DV-NB-A", "DV-NB-B"],
        True,
        False,
    ),
    "KN-SA1": ("DICHVU-SIEUAM", ["DICHVU-SIEUAM"], ["DV-NB-C"], True, False),
    "KN-SANCHAU": ("KHAM-PHUKHOA", ["KHAM-PHUKHOA"], ["DV-NB-A"], True, False),
    "KN-SAN-BIO": ("KHAM-SANKHOA", ["KHAM-SANKHOA"], [], True, False),
    "KN-THUTHUAT": ("DICHVU-THUTHUAT", ["DICHVU-THUTHUAT"], ["DV-NB-B"], True, False),
    "KN-DOITAC": ("DICHVU-LAYMAU-MAU", ["DICHVU-LAYMAU-MAU"], [], True, True),
    "KN-TTNG": ("DICHVU-THUTHUAT", ["DICHVU-THUTHUAT"], [], True, False),
}
# mã vị trí → (phòng KN | None, nhóm nghề, làn, bật)
VI_TRI_KN: dict[str, tuple[str | None, str, int | None, bool]] = {
    "T1_LETAN": ("KN-TIEPDON", "DIEU_DUONG", None, True),
    "T1_THUNGAN": ("KN-TIEPDON", "DIEU_DUONG", None, True),
    "T1_CU": ("KN-TIEPDON", "DIEU_DUONG", None, False),
    "T1_DOCHISO": ("KN-DOCHISO", "DIEU_DUONG", None, True),
    "T1_LAYMAU": ("KN-LAYMAU", "DOI_TAC", None, True),
    "T1_BS_NOITIET": ("KN-NOITIET", "BAC_SI", None, True),
    "T4_SA_BS1": ("KN-SA1", "BAC_SI", 1, True),
    "T4_SA_DD1": ("KN-SA1", "DIEU_DUONG", 1, True),
    "T1_TTNG_BS": ("KN-TTNG", "BAC_SI", None, True),
    "DIEU_PHOI": (None, "DIEU_DUONG", None, True),
}
SO_PHONG_KN_BAT = sum(1 for v in PHONG_KN.values() if v[3])


@dataclass
class PK:
    cid: str
    kn: str
    phong: dict[str, str]
    ql: str
    nguoi: list[str]
    quyen: list[str]


@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


async def _don(conn: asyncpg.Connection, cid: str) -> None:
    # Sổ kho CHỈ THÊM (trigger chặn DELETE) — dọn phòng khám thử thì tắt trigger
    # trong đúng giao dịch này (replica: bỏ qua trigger người dùng).
    async with conn.transaction():
        await conn.execute("SET LOCAL session_replication_role = replica")
        await conn.execute("DELETE FROM inventory_txn WHERE clinic_id = $1::uuid", cid)
    async with conn.transaction():
        # Lịch hẹn / khách là bảng chỉ thêm (trigger chặn DELETE) — như sổ kho.
        await conn.execute("SET LOCAL session_replication_role = replica")
        for bang in ("appointment", "patient", "service_type"):
            await conn.execute(f"DELETE FROM {bang} WHERE clinic_id = $1::uuid", cid)
    for bang in (
        "work_roster",
        "vi_tri_dong_ca",
        "drug_batch",
        "drug_catalog",
        "capability_grant",
        "staff_vi_tri",
        "vai_duoc_vao_tram",
        "vi_tri_lam_viec",
        "dispatch_threshold",
        "clinic_room_service",
        "clinic_room_node",
        "clinic_room",
        "clinic_membership",
        "service_price",
        "node_definition",
        "domain_event",
    ):
        await conn.execute(f"DELETE FROM {bang} WHERE clinic_id = $1::uuid", cid)
    await conn.execute(
        "DELETE FROM staff WHERE primary_location_id IN"
        " (SELECT id FROM clinic_location WHERE clinic_id = $1::uuid)",
        cid,
    )
    await conn.execute("DELETE FROM clinic_location WHERE clinic_id = $1::uuid", cid)
    await conn.execute("DELETE FROM clinic WHERE id = $1::uuid", cid)


async def _nguoi(conn: asyncpg.Connection, cid: str, kn: str, vai: str) -> str:
    sid = await conn.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
        f"NB {vai} {uuid.uuid4().hex[:6]}",
        vai,
        kn,
    )
    await conn.execute(
        "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
        " VALUES ($1::uuid, $2::uuid, $3, true) ON CONFLICT DO NOTHING",
        cid,
        sid,
        vai,
    )
    return str(sid)


@pytest_asyncio.fixture
async def pk(pool: asyncpg.Pool) -> AsyncIterator[PK]:
    async with pool.acquire() as conn:
        cid = await conn.fetchval(
            "INSERT INTO clinic (code, name) VALUES ($1, 'PK nhân bản (test)')"
            " RETURNING id::text",
            f"PK-NB-{uuid.uuid4().hex[:8]}",
        )
        try:
            kn = await conn.fetchval(
                "INSERT INTO clinic_location (clinic_id, code, name, address)"
                " VALUES ($1::uuid, 'KN', 'Kim Ngưu', '99 Kim Ngưu')"
                " RETURNING id::text",
                cid,
            )
            for n in NODES:
                await conn.execute(
                    "INSERT INTO node_definition (clinic_id, code, name, flow_group,"
                    " workspace) VALUES ($1::uuid, $2, $2, 'test', 'test')",
                    cid,
                    n,
                )
            for dv in DICH_VU:
                await conn.execute(
                    'INSERT INTO service_price (clinic_id, service_code, name, "group")'
                    " VALUES ($1::uuid, $2, $2, 'dich_vu')",
                    cid,
                    dv,
                )
            phong: dict[str, str] = {}
            for i, (code, (chinh, viec, dvs, bat, dt)) in enumerate(PHONG_KN.items()):
                rid = await conn.fetchval(
                    "INSERT INTO clinic_room (clinic_id, location_id, code, name,"
                    " node_code, floor, sort, is_active, la_doi_tac, capacity)"
                    " VALUES ($1::uuid, $2::uuid, $3, $3 || ' tên', $4, 'Tầng 1',"
                    " $5, $6, $7, 2) RETURNING id::text",
                    cid,
                    kn,
                    code,
                    chinh,
                    i * 10,
                    bat,
                    dt,
                )
                phong[code] = str(rid)
                for v in viec:
                    await conn.execute(
                        "INSERT INTO clinic_room_node (clinic_id, room_id, node_code)"
                        " VALUES ($1::uuid, $2::uuid, $3)",
                        cid,
                        rid,
                        v,
                    )
                for dv in dvs:
                    await conn.execute(
                        "INSERT INTO clinic_room_service (clinic_id, room_id,"
                        " service_code) VALUES ($1::uuid, $2::uuid, $3)",
                        cid,
                        rid,
                        dv,
                    )
            await conn.execute(
                "INSERT INTO dispatch_threshold (clinic_id, room_id, wait_minutes,"
                " max_waiting) VALUES ($1::uuid, $2::uuid, 15, 6)",
                cid,
                phong["KN-SA1"],
            )
            for i, (code, (ma_phong, nhom, lan, bat)) in enumerate(VI_TRI_KN.items()):
                await conn.execute(
                    "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, tang, phong,"
                    " nhom_nghe, sort, lan, is_active, room_id)"
                    " VALUES ($1::uuid, $2, $2 || ' tên', 'Tầng 1', 'P', $3, $4, $5,"
                    " $6, $7::uuid)",
                    cid,
                    code,
                    nhom,
                    i * 10,
                    lan,
                    bat,
                    phong[ma_phong] if ma_phong else None,
                )
            for tram, vai in (
                ("T1_LETAN", "RECEPTION"),
                ("T1_THUNGAN", "RECEPTION"),
                ("T1_THUNGAN", "CASHIER"),
                ("T4_SA_BS1", "DOCTOR"),
                ("DIEU_PHOI", "MANAGEMENT"),
            ):
                await conn.execute(
                    "INSERT INTO vai_duoc_vao_tram (clinic_id, tram_ma, vai, ghi_chu)"
                    " VALUES ($1::uuid, $2, $3, 'đo từ lịch')",
                    cid,
                    tram,
                    vai,
                )
            ql = await _nguoi(conn, cid, kn, "MANAGEMENT")
            a = await _nguoi(conn, cid, kn, "RECEPTION")
            b = await _nguoi(conn, cid, kn, "DOCTOR")
            for sid, vt in ((a, "T1_LETAN"), (a, "T1_THUNGAN"), (b, "T4_SA_BS1")):
                await conn.execute(
                    "INSERT INTO staff_vi_tri (clinic_id, staff_id, vi_tri_code,"
                    " la_chinh, so_ca_mau) VALUES ($1::uuid, $2::uuid, $3, true, 4)",
                    cid,
                    sid,
                    vt,
                )
            quyen = [
                str(r["ma"])
                for r in await conn.fetch(
                    "SELECT ma FROM capability WHERE ma <> 'permission.manage'"
                    " ORDER BY ma LIMIT 2"
                )
            ]
            for sid, cap, ma_phong, kieu in (
                (a, quyen[0], "KN-TIEPDON", "song"),
                (b, quyen[0], "KN-SA1", "song"),
                (b, quyen[0], "KN-DOCHISO", "song"),
                (b, quyen[1], "KN-LAYMAU", "song"),
                (a, quyen[0], "KN-NOITIET", "thu_hoi"),
                (a, quyen[1], "KN-NOITIET", "het_han"),
            ):
                await conn.execute(
                    "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                    " scope_type, scope_id, granted_by, valid_from, valid_until,"
                    " revoked_at, revoked_by)"
                    " VALUES ($1::uuid, $2::uuid, $3, 'ROOM', $4::uuid, $5::uuid,"
                    " CASE WHEN $6 = 'het_han' THEN now() - interval '2 days' END,"
                    " CASE WHEN $6 = 'het_han' THEN now() - interval '1 day' END,"
                    " CASE WHEN $6 = 'thu_hoi' THEN now() END,"
                    " CASE WHEN $6 = 'thu_hoi' THEN $5::uuid END)",
                    cid,
                    sid,
                    cap,
                    phong[ma_phong],
                    ql,
                    kieu,
                )
        except BaseException:
            await _don(conn, cid)
            raise
    yield PK(cid=cid, kn=kn, phong=phong, ql=ql, nguoi=[a, b], quyen=quyen)
    async with pool.acquire() as conn:
        await _don(conn, cid)


async def _chay(pool: asyncpg.Pool, pk: PK, **kw: Any) -> Any:
    async with pool.acquire() as conn:
        return await NB.chay(conn, clinic_id=pk.cid, **kw)


async def _hn(pool: asyncpg.Pool, pk: PK) -> str | None:
    hn = await pool.fetchval(
        "SELECT id::text FROM clinic_location"
        " WHERE clinic_id = $1::uuid AND code = 'HN'",
        pk.cid,
    )
    return None if hn is None else str(hn)


async def _dem_bang(pool: asyncpg.Pool, pk: PK) -> dict[str, int]:
    kq: dict[str, int] = {}
    for bang in NB.BANG:
        kq[bang] = int(
            await pool.fetchval(
                f"SELECT count(*) FROM {bang} WHERE clinic_id = $1::uuid", pk.cid
            )
        )
    return kq


async def _trang_thai(pool: asyncpg.Pool, pk: PK) -> dict[str, Any]:
    """Ảnh chụp mọi thứ đổi được của Hào Nam (bộ đang bật, vị trí, quyền sống)."""
    phong = await pool.fetch(
        "SELECT r.code, r.is_active FROM clinic_room r JOIN clinic_location l"
        " ON l.id = r.location_id WHERE l.clinic_id = $1::uuid AND l.code = 'HN'"
        " ORDER BY r.code",
        pk.cid,
    )
    vi_tri = await pool.fetch(
        "SELECT v.code, r.code AS phong, v.tang, v.is_active FROM vi_tri_lam_viec v"
        " LEFT JOIN clinic_room r ON r.id = v.room_id"
        " WHERE v.clinic_id = $1::uuid AND v.code LIKE 'HN\\_\\_%' ORDER BY v.code",
        pk.cid,
    )
    quyen = await pool.fetch(
        "SELECT g.staff_id::text AS s, g.capability, r.code FROM capability_grant g"
        " JOIN clinic_room r ON r.id = g.scope_id"
        " JOIN clinic_location l ON l.id = r.location_id AND l.code = 'HN'"
        " WHERE g.clinic_id = $1::uuid AND g.revoked_at IS NULL"
        " ORDER BY 1, 2, 3",
        pk.cid,
    )
    co_so = await pool.fetchval(
        "SELECT is_active FROM clinic_location WHERE clinic_id = $1::uuid"
        " AND code = 'HN'",
        pk.cid,
    )
    return {
        "co_so": co_so,
        "phong": [tuple(r) for r in phong],
        "vi_tri": [tuple(r) for r in vi_tri],
        "quyen": [tuple(r) for r in quyen],
    }


async def _van_kn(pool: asyncpg.Pool, pk: PK) -> dict[str, tuple[int, str]]:
    async with pool.acquire() as conn:
        ctx = await NB._ngu_canh(conn, pk.cid)
        van: dict[str, tuple[int, str]] = await NB.dau_van_kn(conn, ctx)
        return van


DIA_CHI_HN = (
    "Tầng 1, 2, 3 Nhà số 24 Ngõ 168 Phố Hào Nam, Phường Ô Chợ Dừa, Thành phố Hà Nội"
)


async def _kiem_thong_tin_hn(pool: asyncpg.Pool, hn: str) -> None:
    """Tên / địa chỉ / SĐT / tên in của HN (SĐT, tên in: chỉ khi có cột)."""
    dong = json.loads(
        await pool.fetchval(
            "SELECT to_jsonb(l) FROM clinic_location l WHERE id = $1::uuid", hn
        )
    )
    assert dong["name"] == "Hào Nam" and dong["is_active"] is True
    assert dong["address"] == DIA_CHI_HN
    if "phone" in dong:
        assert dong["phone"] == "0966 558 833"
    if "ten_in" in dong:
        assert dong["ten_in"] == "Phòng khám chuyên khoa - Phụ sản 4WOMEN"


async def test_chay_lai_dua_thong_tin_hn_ve_dung(pool: asyncpg.Pool, pk: PK) -> None:
    await _chay(pool, pk, that=True)
    hn = await _hn(pool, pk)
    assert hn is not None
    van_kn = await _van_kn(pool, pk)
    await pool.execute(
        "UPDATE clinic_location SET address = 'địa chỉ cũ' WHERE id = $1::uuid", hn
    )
    bc = await _chay(pool, pk, that=True)
    assert bc.dem["clinic_location"].doi == 1
    await _kiem_thong_tin_hn(pool, hn)
    assert await _van_kn(pool, pk) == van_kn


def test_ma_mau() -> None:
    assert NB.ma_mau("HN__T1_THUNGAN__2") == "T1_THUNGAN"
    assert NB.ma_mau("HN__T4_SA_BS1") == "T4_SA_BS1"
    assert NB.ma_mau("T1_LETAN") == "T1_LETAN"
    assert NB.ma_phong_a("KN-SAN-BIO") == "HN-SAN-BIO"


async def test_chay_thu_khong_ghi_gi(pool: asyncpg.Pool, pk: PK) -> None:
    truoc = await _dem_bang(pool, pk)
    bc = await _chay(pool, pk)  # mặc định: chạy thử
    assert bc.that is False
    assert bc.dem["clinic_room"].moi == SO_PHONG_KN_BAT + len(NB.BO_B)
    assert await _hn(pool, pk) is None
    assert await _dem_bang(pool, pk) == truoc


async def test_that_tao_dung_so_va_kim_nguu_khong_doi(
    pool: asyncpg.Pool, pk: PK
) -> None:
    van_truoc = await _van_kn(pool, pk)
    bc = await _chay(pool, pk, that=True)
    d = bc.dem
    assert d["clinic_location"].moi == 1
    # 11 phòng KN đang bật (bộ A) + 11 phòng sơ đồ (bộ B).
    assert d["clinic_room"].moi == SO_PHONG_KN_BAT + len(NB.BO_B) == 22
    # 8 vị trí KN đang bật có phòng (T1_CU tắt, DIEU_PHOI không phòng) + 2 thu ngân B.
    assert d["vi_tri_lam_viec"].moi == 10
    # LETAN 1 + THUNGAN 2 + SA_BS1 1 + THUNGAN__2 2 + THUNGAN__3 2; DIEU_PHOI không.
    assert d["vai_duoc_vao_tram"].moi == 8
    assert d["staff_vi_tri"].moi == 5
    # A: HN-SA1; B: HN-SA1-B + HN-SA-E10-B (cùng mẫu KN-SA1).
    assert d["dispatch_threshold"].moi == 3
    # Bộ A: TIEPDON, SA1, DOCHISO (LAYMAU tắt; thu hồi / hết hạn không chép).
    assert d["capability_grant"].moi == 3
    assert bc.bo == "A"

    hn = await _hn(pool, pk)
    assert hn is not None
    await _kiem_thong_tin_hn(pool, hn)

    tt = await _trang_thai(pool, pk)
    bat = {c for c, a in tt["phong"] if a}
    assert bat == {NB.ma_phong_a(c) for c, v in PHONG_KN.items() if v[3]}
    assert not any(a for c, a in tt["phong"] if c in NB.MA_BO_B)

    # Phòng HN-XN-B = HỢP việc + dịch vụ của DOCHISO + LAYMAU, việc chính DOCHISO.
    xn = await pool.fetchrow(
        "SELECT id, node_code, floor FROM clinic_room WHERE clinic_id = $1::uuid"
        " AND code = 'HN-XN-B'",
        pk.cid,
    )
    assert xn["node_code"] == "LUOTKHAM-03" and xn["floor"] == "Tầng 4"
    viec = {
        r[0]
        for r in await pool.fetch(
            "SELECT node_code FROM clinic_room_node WHERE room_id = $1", xn["id"]
        )
    }
    assert viec == {"LUOTKHAM-03", "DICHVU-DXA", "DICHVU-LAYMAU-MAU"}
    dv = await pool.fetchval(
        "SELECT array_agg(service_code) FROM clinic_room_service WHERE room_id = $1",
        xn["id"],
    )
    assert dv == ["DV-NB-C"]

    # Vị trí giữ làn / nhóm nghề; trỏ phòng HN; vị trí chỉ-bộ-B đang tắt.
    vt = {r[0]: r for r in tt["vi_tri"]}
    assert vt["HN__T4_SA_BS1"][1:] == ("HN-SA1", "Tầng 1", True)
    assert vt["HN__T1_LAYMAU"][3] is False
    assert vt["HN__T1_THUNGAN__2"][3] is False
    assert "HN__DIEU_PHOI" not in vt and "HN__T1_CU" not in vt
    lan = await pool.fetchval(
        "SELECT lan FROM vi_tri_lam_viec WHERE clinic_id = $1::uuid"
        " AND code = 'HN__T4_SA_BS1'",
        pk.cid,
    )
    assert lan == 1
    assert {(s, c, p) for s, c, p in tt["quyen"]} == {
        (pk.nguoi[0], pk.quyen[0], "HN-TIEPDON"),
        (pk.nguoi[1], pk.quyen[0], "HN-SA1"),
        (pk.nguoi[1], pk.quyen[0], "HN-DOCHISO"),
    }

    assert await _van_kn(pool, pk) == van_truoc
    assert bc.kn == van_truoc


async def test_chay_lai_khong_nhan_doi(pool: asyncpg.Pool, pk: PK) -> None:
    await _chay(pool, pk, that=True)
    sau_1 = await _dem_bang(pool, pk)
    tt_1 = await _trang_thai(pool, pk)
    bc = await _chay(pool, pk, that=True)
    assert all(d.moi == 0 for d in bc.dem.values()), bc.dem
    assert all(d.doi == 0 for d in bc.dem.values()), bc.dem
    assert await _dem_bang(pool, pk) == sau_1
    assert await _trang_thai(pool, pk) == tt_1


async def test_doi_bo_b_roi_a_tro_ve_nhu_cu(pool: asyncpg.Pool, pk: PK) -> None:
    await _chay(pool, pk, that=True)
    van_kn = await _van_kn(pool, pk)
    tt_a = await _trang_thai(pool, pk)

    bc = await _chay(pool, pk, viec="doi-bo", bo="B", that=True)
    assert bc.bo == "B"
    tt_b = await _trang_thai(pool, pk)
    bat = {c for c, a in tt_b["phong"] if a}
    assert bat == set(NB.MA_BO_B)
    vt = {r[0]: r for r in tt_b["vi_tri"]}
    assert vt["HN__T1_THUNGAN__2"][1:] == ("HN-TIEPDON-B", "Tầng 2", True)
    assert vt["HN__T1_THUNGAN__3"][1:] == ("HN-TIEPDON-B", "Tầng 3", True)
    assert vt["HN__T1_LAYMAU"][1:] == ("HN-XN-B", "Tầng 4", True)
    assert vt["HN__T4_SA_BS1"][1:] == ("HN-SA1-B", "Tầng 2", True)
    assert vt["HN__T1_BS_NOITIET"][1:] == ("HN-NOITIET-B", "Tầng 1", True)
    # KN-TTNG không là mẫu bộ B → vị trí tắt, không phòng, tầng gốc.
    assert vt["HN__T1_TTNG_BS"][1:] == (None, "Tầng 1", False)
    a, b = pk.nguoi
    q0, q1 = pk.quyen
    assert set(tt_b["quyen"]) == {
        (a, q0, "HN-TIEPDON-B"),
        (b, q0, "HN-SA1-B"),
        (b, q0, "HN-SA-E10-B"),
        (b, q0, "HN-XN-B"),
        (b, q1, "HN-XN-B"),
    }

    await _chay(pool, pk, viec="doi-bo", bo="A", that=True)
    assert await _trang_thai(pool, pk) == tt_a
    assert await _van_kn(pool, pk) == van_kn


async def test_go_tat_het_khong_xoa_va_mo_lai_duoc(pool: asyncpg.Pool, pk: PK) -> None:
    await _chay(pool, pk, that=True)
    tt_a = await _trang_thai(pool, pk)
    dem = await _dem_bang(pool, pk)
    van_kn = await _van_kn(pool, pk)

    bc = await _chay(pool, pk, viec="go", that=True)
    assert bc.dem["capability_grant"].doi == 3
    tt = await _trang_thai(pool, pk)
    assert tt["co_so"] is False
    assert not any(a for _c, a in tt["phong"])
    assert not any(r[3] for r in tt["vi_tri"])
    assert tt["quyen"] == []
    assert await _dem_bang(pool, pk) == dem  # không xoá dòng nào
    assert await _van_kn(pool, pk) == van_kn

    await _chay(pool, pk, viec="doi-bo", bo="A", that=True)
    assert await _trang_thai(pool, pk) == tt_a


async def test_tu_choi_khi_khong_ro_kim_nguu(pool: asyncpg.Pool, pk: PK) -> None:
    # Seed có cơ sở KN ở phòng khám mặc định + phòng khám test → hai phòng khám.
    async with pool.acquire() as conn:
        with pytest.raises(SystemExit, match="phòng khám cùng có cơ sở KN"):
            await NB.chay(conn)
        with pytest.raises(SystemExit, match="Không thấy cơ sở Kim Ngưu"):
            await NB.chay(conn, clinic_id=str(uuid.uuid4()))
    assert await _hn(pool, pk) is None


async def test_chep_kho_theo_trang_thai_migration(pool: asyncpg.Pool, pk: PK) -> None:
    """Chưa có cột `drug_batch.location_id` → bỏ qua, báo rõ. Có cột (migration
    kho 20261008710000) → lô KN sang HN cùng số lô, tồn ghi qua sổ RECEIVE."""
    co_cot = await pool.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_schema = 'public'"
        " AND table_name = 'drug_batch' AND column_name = 'location_id'"
    )
    if not co_cot:
        bc = await _chay(pool, pk, that=True, chep_kho=True)
        assert any("chưa có migration kho" in g for g in bc.ghi_chu), bc.ghi_chu
        assert bc.dem["drug_batch"].moi == 0
        return

    thuoc = await pool.fetchval(
        "INSERT INTO drug_catalog (clinic_id, name_base, name_raw, unit_price)"
        " VALUES ($1::uuid, 'Thuốc NB', 'Thuốc NB', 5000) RETURNING id::text",
        pk.cid,
    )
    ton = {"LO-NB-A": 30, "LO-NB-B": 0}
    for ma, so in ton.items():
        await pool.execute(
            "INSERT INTO drug_batch (clinic_id, location_id, drug_catalog_id,"
            " batch_code, expiry_date, quantity_on_hand, unit)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4, '2099-12-31', $5, 'viên')",
            pk.cid,
            pk.kn,
            thuoc,
            ma,
            so,
        )
    van_kn = await _van_kn(pool, pk)

    bc = await _chay(pool, pk, that=True, chep_kho=True)
    assert bc.dem["drug_batch"].moi == 2
    assert bc.dem["inventory_txn"].moi == 1  # lô tồn 0 không cần dòng sổ
    hn = await _hn(pool, pk)
    lo_hn = {
        r["batch_code"]: (int(r["quantity_on_hand"]), int(r["so"]))
        for r in await pool.fetch(
            "SELECT b.batch_code, b.quantity_on_hand,"
            " coalesce((SELECT sum(t.quantity) FROM inventory_txn t"
            "   WHERE t.drug_batch_id = b.id), 0) AS so"
            " FROM drug_batch b WHERE b.location_id = $1::uuid",
            hn,
        )
    }
    # Tồn = tổng sổ kho (thẻ kho khớp tồn).
    assert lo_hn == {ma: (so, so) for ma, so in ton.items()}
    assert await _van_kn(pool, pk) == van_kn

    bc = await _chay(pool, pk, that=True, chep_kho=True)
    assert (bc.dem["drug_batch"].moi, bc.dem["drug_batch"].co) == (0, 2)
    assert bc.dem["inventory_txn"].moi == 0


async def _lich(conn: asyncpg.Connection, pk: PK, loc: str, ngay_lech: int) -> str:
    """Một lịch hẹn lúc 18:00 (giờ VN) của ngày hôm nay + `ngay_lech`."""
    pid = await conn.fetchval(
        "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
        " VALUES ($1::uuid, $2, 'Khách chuyển', $3::uuid)"
        " RETURNING clinic_patient_id::text",
        pk.cid,
        f"NB-{uuid.uuid4().hex[:8]}",
        loc,
    )
    loai = await conn.fetchval(
        "INSERT INTO service_type (clinic_id, code, name, is_active)"
        " VALUES ($1::uuid, $2, 'Khám chuyển', true) RETURNING id::text",
        pk.cid,
        f"NBK-{uuid.uuid4().hex[:8]}",
    )
    return str(
        await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " slot_start, slot_end, status, service_type_id)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid,"
            "  ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + $4::int"
            "   + time '18:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',"
            "  ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + $4::int"
            "   + time '18:15') AT TIME ZONE 'Asia/Ho_Chi_Minh',"
            "  'CONFIRMED', $5::uuid) RETURNING id::text",
            pk.cid,
            pid,
            loc,
            ngay_lech,
            loai,
        )
    )


async def _ca(conn: asyncpg.Connection, pk: PK, tram: str, ngay_lech: int) -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO work_roster (clinic_id, week_start, work_date, shift,"
            " station, staff_id, staff_name, status)"
            " SELECT $1::uuid, d - (extract(isodow FROM d)::int - 1), d, 'TOI', $2,"
            "        $3::uuid, 'NB', 'APPROVED'"
            "   FROM (SELECT (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date"
            "                + $4::int AS d) x RETURNING id::text",
            pk.cid,
            tram,
            pk.nguoi[0],
            ngay_lech,
        )
    )


async def test_chuyen_tu_hom_nay_roi_tra_lai(pool: asyncpg.Pool, pk: PK) -> None:
    """Tuyền 08/10: Kim Ngưu tạm đóng — lịch hẹn từ hôm nay sang Hào Nam; lịch
    đã qua giữ Kim Ngưu; LỊCH LÀM VIỆC KHÔNG ĐỤNG (để trống, nhập tay); trả
    lại được."""
    async with pool.acquire() as conn:
        hen_qua = await _lich(conn, pk, pk.kn, -1)
        hen_mai = await _lich(conn, pk, pk.kn, 1)
        ca_qua = await _ca(conn, pk, "T1_LETAN", -1)
        ca_mai = await _ca(conn, pk, "T1_LETAN", 1)
        ca_dp = await _ca(conn, pk, "DIEU_PHOI", 1)
        await conn.execute(
            "INSERT INTO vi_tri_dong_ca (clinic_id, work_date, shift, station)"
            " VALUES ($1::uuid, (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + 1,"
            " 'SANG', 'T1_LETAN')",
            pk.cid,
        )
    await _chay(pool, pk, that=True)
    hn = await _hn(pool, pk)
    assert hn

    async def co_so(hen: str) -> str:
        return str(
            await pool.fetchval(
                "SELECT location_id::text FROM appointment WHERE id = $1::uuid", hen
            )
        )

    async def tram(ca: str) -> str:
        return str(
            await pool.fetchval(
                "SELECT station FROM work_roster WHERE id = $1::uuid", ca
            )
        )

    thu = await _chay(pool, pk, viec="chuyen")  # chạy thử: không đổi gì
    assert thu.dem["appointment"].doi == 1
    assert await co_so(hen_mai) == pk.kn

    bc = await _chay(pool, pk, viec="chuyen", that=True)
    assert bc.dem["appointment"].doi == 1
    assert await co_so(hen_mai) == hn
    assert await co_so(hen_qua) == pk.kn
    assert await tram(ca_mai) == "T1_LETAN"  # lịch làm việc không chuyển
    assert await tram(ca_qua) == "T1_LETAN"
    assert await tram(ca_dp) == "DIEU_PHOI"
    assert (
        await pool.fetchval(
            "SELECT station FROM vi_tri_dong_ca WHERE clinic_id = $1::uuid", pk.cid
        )
        == "T1_LETAN"
    )

    # Chạy lại không chuyển thêm gì.
    lai = await _chay(pool, pk, viec="chuyen", that=True)
    assert lai.dem["appointment"].doi == 0

    # Lịch đặt MỚI ở Hào Nam sau khi chuyển: trả lại không được kéo nó về KN.
    async with pool.acquire() as conn:
        hen_moi = await _lich(conn, pk, hn, 2)
    await _chay(pool, pk, viec="tra-lai", that=True)
    assert await co_so(hen_mai) == pk.kn
    assert await co_so(hen_moi) == hn
    assert await tram(ca_mai) == "T1_LETAN"
    assert (
        await pool.fetchval(
            "SELECT station FROM vi_tri_dong_ca WHERE clinic_id = $1::uuid", pk.cid
        )
        == "T1_LETAN"
    )
