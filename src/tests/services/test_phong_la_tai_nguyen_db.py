"""Phòng là TÀI NGUYÊN — định danh bằng room_id, tên đổi tự do (CORE-C, 23/09/2026).

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55500/postgres \\
        poetry run pytest src/tests/services/test_phong_la_tai_nguyen_db.py

Ví dụ Tuyền: hôm nay "Siêu âm 1", mai quản lý đổi thành "Phòng Hoa" — lịch trực,
hàng chờ, quyền không được hỏng. Tên là dữ liệu hiển thị, không phải định danh.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.clinic_config_service import ClinicConfigService

CLINIC = "a0000000-0000-4000-8000-000000000001"

pytestmark = [pytest.mark.db, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def pool() -> Any:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    yield p
    await p.close()


def _quan_ly() -> StaffIdentity:
    return StaffIdentity(
        staff_id=str(uuid.uuid4()),
        auth_user_id=str(uuid.uuid4()),
        full_name="QL test",
        department="MANAGEMENT",
        role=ClinicRole.MANAGEMENT,
        clinic_id=CLINIC,
        location_id="",
        location_name="",
    )


async def _co_so(pool: asyncpg.Pool) -> str:
    return str(
        await pool.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )


async def _tao(pool: asyncpg.Pool, ten: str) -> str:
    kq = await ClinicConfigService(pool).create_room(
        identity=_quan_ly(),
        location_id=await _co_so(pool),
        name=ten,
        node_code="DICHVU-SIEUAM",
        floor="2",
    )
    return str(kq["room_id"])


async def test_tao_phong_ten_tu_do_ma_noi_bo_tu_sinh(pool: asyncpg.Pool) -> None:
    rid = await _tao(pool, "Phòng ABC")
    r = await pool.fetchrow(
        "SELECT name, code, node_code, floor, is_active FROM clinic_room"
        " WHERE id = $1::uuid",
        rid,
    )
    assert r["name"] == "Phòng ABC" and r["floor"] == "2" and r["is_active"]
    assert r["node_code"] == "DICHVU-SIEUAM"
    assert r["code"].startswith("P-")  # mã nội bộ, không ai phải gõ
    phuc_vu = await pool.fetchval(
        "SELECT array_agg(node_code) FROM clinic_room_node WHERE room_id = $1::uuid",
        rid,
    )
    assert phuc_vu == ["DICHVU-SIEUAM"]


async def test_doi_ten_giu_nguyen_room_id_lich_truc_va_hang_cho(
    pool: asyncpg.Pool,
) -> None:
    """Nghiệm thu 6: "Phòng ABC" → "Phòng Hoa" vẫn cùng room_id; phân công
    (vị trí trực → phòng) và khách đang chờ trong phòng không mất."""
    rid = await _tao(pool, "Phòng ABC")
    vi_tri = await pool.fetchval(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, 'Siêu âm — test', $3::uuid) RETURNING id::text",
        CLINIC,
        f"T-{uuid.uuid4().hex[:6]}",
        rid,
    )

    kq = await ClinicConfigService(pool).rename_room(
        identity=_quan_ly(), room_id=rid, name="Phòng Hoa"
    )
    assert kq["room_id"] == rid

    assert (
        await pool.fetchval("SELECT name FROM clinic_room WHERE id = $1::uuid", rid)
        == "Phòng Hoa"
    )
    assert (
        await pool.fetchval(
            "SELECT room_id::text FROM vi_tri_lam_viec WHERE id = $1::uuid", vi_tri
        )
        == rid
    )
    ov = await ClinicConfigService(pool).overview(identity=_quan_ly())
    ten = {
        r["room_id"]: r["name"]
        for loc in ov["locations"]
        for f in loc["floors"]
        for r in f["rooms"]
    }
    assert ten[rid] == "Phòng Hoa"


async def test_ten_rong_bi_tu_choi(pool: asyncpg.Pool) -> None:
    rid = await _tao(pool, "Phòng ABC")
    with pytest.raises(ValidationError):
        await ClinicConfigService(pool).rename_room(
            identity=_quan_ly(), room_id=rid, name="   "
        )


async def test_tat_phong_con_khach_bi_chan_het_khach_thi_tat_duoc(
    pool: asyncpg.Pool,
) -> None:
    rid = await _tao(pool, "Phòng tắt thử")
    loc = await _co_so(pool)
    async with pool.acquire() as conn:
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id)"
            " VALUES ($1::uuid, $2, 'BN phòng', $3::uuid)"
            " RETURNING clinic_patient_id::text",
            CLINIC,
            f"PH-{uuid.uuid4().hex[:8]}",
            loc,
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, location_id, status)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, 'OPEN') RETURNING visit_id::text",
            CLINIC,
            pid,
            loc,
        )
        qid = await conn.fetchval(
            "INSERT INTO queue_entry (clinic_id, visit_id, lane, reason, ref_id,"
            " status, room_id, eligible_at)"
            " VALUES ($1::uuid, $2::uuid, 'ROOM', 'SERVICE', gen_random_uuid(),"
            " 'waiting', $3::uuid, now()) RETURNING id::text",
            CLINIC,
            vid,
            rid,
        )

    with pytest.raises(ValidationError, match="đang chờ"):
        await ClinicConfigService(pool).set_room_active(
            identity=_quan_ly(), room_id=rid, is_active=False
        )

    await pool.execute(
        "UPDATE queue_entry SET status = 'done' WHERE id = $1::uuid", qid
    )
    await ClinicConfigService(pool).set_room_active(
        identity=_quan_ly(), room_id=rid, is_active=False
    )
    assert not await pool.fetchval(
        "SELECT is_active FROM clinic_room WHERE id = $1::uuid", rid
    )


async def test_buoc_chua_co_phong_bao_config_missing(pool: asyncpg.Pool) -> None:
    """DXA / tinh dịch đồ chưa có phòng: báo CONFIG_MISSING, không tự tạo phòng."""
    ov = await ClinicConfigService(pool).overview(identity=_quan_ly())
    thieu = {t["code"] for t in ov["config_missing"]}
    assert "DICHVU-DXA" in thieu
    assert all(t["loi"] == "CONFIG_MISSING" for t in ov["config_missing"])
    assert "DICHVU-SIEUAM" not in thieu


async def test_thanh_ben_nhan_ten_phong_moi_theo_room_id(pool: asyncpg.Pool) -> None:
    """C2/C3: `/me/vi-tri-hom-nay` trả phòng của từng vị trí theo room_id — đổi
    tên là thanh bên đổi theo; tắt phòng là vị trí ấy không còn trỏ vào nó."""
    from clinicai.api.v1.routers.identity import vi_tri_hom_nay

    rid = await _tao(pool, "Siêu âm 1")
    ma = f"T-{uuid.uuid4().hex[:6]}"
    await pool.execute(
        "INSERT INTO vi_tri_lam_viec (clinic_id, code, ten, room_id)"
        " VALUES ($1::uuid, $2, 'Siêu âm — test', $3::uuid)",
        CLINIC,
        ma,
        rid,
    )
    await ClinicConfigService(pool).rename_room(
        identity=_quan_ly(), room_id=rid, name="Phòng Hoa"
    )
    kq = await vi_tri_hom_nay(identity=_quan_ly(), pool=pool)
    assert kq["phong"][ma] == {"room_id": rid, "ten": "Phòng Hoa"}  # type: ignore[index]

    await ClinicConfigService(pool).set_room_active(
        identity=_quan_ly(), room_id=rid, is_active=False
    )
    kq = await vi_tri_hom_nay(identity=_quan_ly(), pool=pool)
    assert ma not in kq["phong"]  # type: ignore[operator]


# ── API cấu hình thêm 24/09/2026 (mô phỏng buổi khám: chỉ sửa được bằng SQL) ──


async def test_co_phong_doi_tac_va_tam_ngung_nhan_khach(pool: asyncpg.Pool) -> None:
    from clinicai.services.service_routing_service import eligible_rooms

    rid = await _tao(pool, f"Phòng cờ {uuid.uuid4().hex[:4]}")
    svc = ClinicConfigService(pool)

    async def duoc_xep() -> bool:
        async with pool.acquire() as conn:
            ds = await eligible_rooms(conn, CLINIC, "DICHVU-SIEUAM")
        return rid in {r.room_id for r in ds}

    assert await duoc_xep()
    kq = await svc.set_room_flags(identity=_quan_ly(), room_id=rid, accepting=False)
    assert (kq["accepting"], kq["la_doi_tac"]) == (False, False)
    assert not await duoc_xep()  # tạm ngừng: tự xếp bỏ qua
    await svc.set_room_flags(
        identity=_quan_ly(), room_id=rid, accepting=True, la_doi_tac=True
    )
    assert not await duoc_xep()  # phòng đối tác: tự xếp không đưa khách vào
    await svc.set_room_flags(identity=_quan_ly(), room_id=rid, la_doi_tac=False)
    assert await duoc_xep()
    with pytest.raises(ValidationError):
        await svc.set_room_flags(identity=_quan_ly(), room_id=rid)


async def test_them_sua_tat_co_so(pool: asyncpg.Pool) -> None:
    svc = ClinicConfigService(pool)
    kq = await svc.create_location(identity=_quan_ly(), name="  Cơ sở   Thử  ")
    loc = kq["location_id"]
    r = await pool.fetchrow(
        "SELECT name, code, is_active FROM clinic_location WHERE id = $1::uuid", loc
    )
    assert r["name"] == "Cơ sở Thử" and r["code"].startswith("CS-") and r["is_active"]
    await svc.update_location(
        identity=_quan_ly(), location_id=loc, name="Cơ sở Hoa", address="12 Láng"
    )
    # Còn phòng đang bật thì không tắt được cơ sở.
    await svc.create_room(
        identity=_quan_ly(), location_id=loc, name="P1", node_code="DICHVU-SIEUAM"
    )
    with pytest.raises(ValidationError, match="phòng đang bật"):
        await svc.update_location(identity=_quan_ly(), location_id=loc, is_active=False)
    await pool.execute(
        "UPDATE clinic_room SET is_active = false WHERE location_id = $1::uuid", loc
    )
    kq = await svc.update_location(
        identity=_quan_ly(), location_id=loc, is_active=False
    )
    assert (kq["name"], kq["address"], kq["is_active"]) == (
        "Cơ sở Hoa",
        "12 Láng",
        False,
    )


async def test_them_sua_tat_loai_kham(pool: asyncpg.Pool) -> None:
    svc = ClinicConfigService(pool)
    kq = await svc.create_service_type(
        identity=_quan_ly(), name="Khám thử API", default_duration_minutes=20
    )
    st = kq["service_type_id"]
    kq = await svc.update_service_type(
        identity=_quan_ly(), service_type_id=st, name="Khám đổi tên", is_active=False
    )
    assert kq == {
        "ok": True,
        "service_type_id": st,
        "name": "Khám đổi tên",
        "default_duration_minutes": 20,
        "is_active": False,
    }
    with pytest.raises(ValidationError):
        await svc.update_service_type(
            identity=_quan_ly(), service_type_id=str(uuid.uuid4()), name="x"
        )
