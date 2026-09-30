"""Dọn dữ liệu khách thử (30/09/2026) — qua HTTP thật (router + service + hàm SQL
`don_khach_thu`), chỉ thay bước JWT.

    DATABASE_URL_TEST=postgresql://postgres:postgres@127.0.0.1:55583/postgres \\
        .venv/bin/pytest src/tests/services/test_don_du_lieu_thu_db.py

Khách thử đặt ở ngày 2001-03-10 để không đụng dữ liệu của bài khác.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from datetime import date
from typing import Any

import asyncpg
import httpx
import pytest
import pytest_asyncio

from clinicai.api.identity import (
    ClinicRole,
    StaffIdentity,
    _resolve_identity,
    doc_vai_theo_lego,
)
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.permissions import cache
from clinicai.permissions.catalogue import quyen_cua_khoi
from clinicai.services.don_du_lieu_thu_service import (
    che_sdt,
    chuan_khach,
    doc_ngay,
    ngay_mac_dinh,
    nhom_so_dong,
    xac_nhan_dung,
)

CLINIC = "a0000000-0000-4000-8000-000000000001"
NGAY = "2001-03-10"

HIEN_TAI: dict[str, StaffIdentity] = {}


# ── Hàm thuần ───────────────────────────────────────────────────────────────
def test_che_sdt() -> None:
    assert che_sdt("0334567897") == "0334***897"
    assert che_sdt(None) == ""
    assert che_sdt("12345") == "12345"


@pytest.mark.parametrize(
    "rac", [None, "", "hôm qua", "2026-13-40", "2026-9-1", "x" * 50]
)
def test_doc_ngay_rac_tra_rong(rac: str | None) -> None:
    assert doc_ngay(rac) is None


def test_doc_ngay_va_mac_dinh() -> None:
    assert doc_ngay("2026-09-29") == date(2026, 9, 29)
    assert ngay_mac_dinh(date(2026, 9, 30)) == date(2026, 9, 29)


def test_chuan_khach() -> None:
    a = str(uuid.uuid4())
    assert chuan_khach([a, a.upper()]) == [a]
    for sai in ([], None, ["khong-phai-uuid"], "abc"):
        with pytest.raises(Exception):
            chuan_khach(sai)


def test_nhom_so_dong_va_xac_nhan() -> None:
    nhom = nhom_so_dong({"patient": 2, "visit": 3, "work_item": 5, "event_log": 1})
    assert [n["ma"] for n in nhom] == ["khach", "luot", "khac"]
    assert nhom[-1]["so"] == 6
    assert xac_nhan_dung("XOA") and xac_nhan_dung(" XOA ")
    assert not xac_nhan_dung("xoa") and not xac_nhan_dung(None)


# ── Qua HTTP + database ─────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def pool() -> AsyncIterator[asyncpg.Pool]:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        pytest.skip("cần DATABASE_URL_TEST trỏ tới database dùng một lần")
    dsn = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    p = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=4)
    app.dependency_overrides[get_db_pool] = lambda: p
    app.dependency_overrides[_resolve_identity] = lambda: HIEN_TAI["ai"]
    try:
        yield p
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(_resolve_identity, None)
        await p.close()


@pytest_asyncio.fixture
async def http(pool: asyncpg.Pool) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://don"
    ) as c:
        yield c


async def _loc(conn: asyncpg.Connection) -> str:
    return str(
        await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id = $1::uuid"
            " AND is_active ORDER BY created_at, id LIMIT 1",
            CLINIC,
        )
    )


async def _nguoi(pool: asyncpg.Pool, vai: str, khoi: list[str]) -> StaffIdentity:
    async with pool.acquire() as conn:
        loc = await _loc(conn)
        ten = f"Dọn thử {vai} {uuid.uuid4().hex[:5]}"
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department, primary_location_id,"
            " is_active) VALUES ($1, $2, $3::uuid, true) RETURNING id::text",
            ten,
            vai,
            loc,
        )
        await conn.execute(
            "INSERT INTO clinic_membership (clinic_id, staff_id, role, is_active)"
            " VALUES ($1::uuid, $2::uuid, $3, true) ON CONFLICT DO NOTHING",
            CLINIC,
            sid,
            vai,
        )
        for k in khoi:
            for q in quyen_cua_khoi(k):
                await conn.execute(
                    "INSERT INTO capability_grant (clinic_id, staff_id, capability,"
                    " tu_khoi) VALUES ($1::uuid, $2::uuid, $3, $4)"
                    " ON CONFLICT DO NOTHING",
                    CLINIC,
                    sid,
                    q,
                    k,
                )
    cache.quen(CLINIC, sid)
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name=ten,
        department=vai,
        role=ClinicRole(vai),
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
        vai_theo_lego=await doc_vai_theo_lego(pool, CLINIC, sid, ClinicRole(vai)),
    )


async def _khach(
    pool: asyncpg.Pool, ten: str, *, mo_hom_nay: bool = False
) -> dict[str, str]:
    """Một khách: lịch 09:00 ngày NGAY + lượt của lịch ấy (+ lượt mở hôm nay)."""
    async with pool.acquire() as conn:
        loc = await _loc(conn)
        st = await conn.fetchval(
            "SELECT id::text FROM service_type WHERE clinic_id = $1::uuid"
            " ORDER BY code LIMIT 1",
            CLINIC,
        )
        pid = await conn.fetchval(
            "INSERT INTO patient (clinic_id, patient_code, full_name, location_id,"
            " phone_primary, created_at) VALUES ($1::uuid, $2, $3, $4::uuid,"
            " '0901234567', $5::date) RETURNING clinic_patient_id::text",
            CLINIC,
            f"DT-{uuid.uuid4().hex[:10]}",
            ten,
            loc,
            date.fromisoformat(NGAY),
        )
        aid = await conn.fetchval(
            "INSERT INTO appointment (clinic_id, clinic_patient_id, location_id,"
            " service_type_id, slot_start, slot_end, status, created_at)"
            " VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid,"
            " ($5::date + time '09:00') AT TIME ZONE 'Asia/Ho_Chi_Minh',"
            " ($5::date + time '09:15') AT TIME ZONE 'Asia/Ho_Chi_Minh',"
            " 'COMPLETED', $5::date) RETURNING id::text",
            CLINIC,
            pid,
            loc,
            st,
            date.fromisoformat(NGAY),
        )
        vid = await conn.fetchval(
            "INSERT INTO visit (clinic_id, clinic_patient_id, appointment_id, status,"
            " checked_in_at, created_at) VALUES ($1::uuid, $2::uuid, $3::uuid,"
            " 'IN_PROGRESS', ($4::date + time '09:05') AT TIME ZONE 'Asia/Ho_Chi_Minh',"
            " $4::date) RETURNING visit_id::text",
            CLINIC,
            pid,
            aid,
            date.fromisoformat(NGAY),
        )
        mo = ""
        if mo_hom_nay:
            mo = str(
                await conn.fetchval(
                    "INSERT INTO visit (clinic_id, clinic_patient_id, status,"
                    " checked_in_at) VALUES ($1::uuid, $2::uuid, 'OPEN', now())"
                    " RETURNING visit_id::text",
                    CLINIC,
                    pid,
                )
            )
    return {"id": str(pid), "lich": str(aid), "luot": str(vid), "mo": mo}


async def _goi(
    http: httpx.AsyncClient, ai: StaffIdentity, method: str, path: str, **kw: Any
) -> httpx.Response:
    HIEN_TAI["ai"] = ai
    headers = {"Idempotency-Key": "don-" + uuid.uuid4().hex}
    return await http.request(
        method, "/api/v1/quan-tri/don-du-lieu-thu" + path, headers=headers, **kw
    )


async def _xoa(
    http: httpx.AsyncClient, ai: StaffIdentity, khach_id: str, chu: str
) -> httpx.Response:
    return await _goi(
        http, ai, "POST", "/xoa", json={"khach": [khach_id], "xac_nhan": chu}
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_khong_phai_quan_tri_bi_chan(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    le_tan = await _nguoi(pool, "RECEPTION", ["tiep_don"])
    a = await _khach(pool, "Khách thử chặn quyền")
    for method, path, kw in (
        ("GET", f"?ngay={NGAY}", {}),
        ("POST", "/xem-truoc", {"json": {"khach": [a["id"]]}}),
        ("POST", "/xoa", {"json": {"khach": [a["id"]], "xac_nhan": "XOA"}}),
    ):
        r = await _goi(http, le_tan, method, path, **kw)
        assert r.status_code == 403, (path, r.text)
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM patient WHERE clinic_patient_id = $1::uuid", a["id"]
        )
        == 1
    )


@pytest.mark.db
@pytest.mark.asyncio
async def test_xoa_khach_chon_giu_khach_khac(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    ql = await _nguoi(pool, "MANAGEMENT", ["quan_tri_quyen"])
    a = await _khach(pool, "Khách thử bị xoá")
    b = await _khach(pool, "Khách thật được giữ")

    r = await _goi(http, ql, "GET", f"?ngay={NGAY}")
    assert r.status_code == 200, r.text
    ds = {d["khach"]["id"]: d for d in r.json()["dong"]}
    assert a["id"] in ds and b["id"] in ds
    assert ds[a["id"]]["khach"]["sdt"] == "0901***567"
    assert ds[a["id"]]["gio"] == "09:00"

    r = await _goi(http, ql, "POST", "/xem-truoc", json={"khach": [a["id"]]})
    assert r.status_code == 200, r.text
    nhom = {n["ma"]: n["so"] for n in r.json()["nhom"]}
    assert nhom["khach"] == 1 and nhom["lich"] == 1 and nhom["luot"] == 1
    assert r.json()["bi_chan"] == []
    # Xem trước không đổi gì.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM visit WHERE visit_id = $1::uuid", a["luot"]
        )
        == 1
    )

    r = await _xoa(http, ql, a["id"], "xoa")
    assert r.status_code == 422, r.text

    r = await _xoa(http, ql, a["id"], "XOA")
    assert r.status_code == 200, r.text
    kq = r.json()
    assert [k["ten"] for k in kq["khach"]] == ["Khách thử bị xoá"]
    lan = kq["lan_id"]

    for bang, cot, v in (
        ("patient", "clinic_patient_id", a["id"]),
        ("appointment", "id", a["lich"]),
        ("visit", "visit_id", a["luot"]),
    ):
        assert (
            await pool.fetchval(
                f"SELECT count(*) FROM {bang} WHERE {cot} = $1::uuid", v
            )
            == 0
        ), bang
    # Khách kia còn nguyên.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM visit WHERE visit_id = $1::uuid", b["luot"]
        )
        == 1
    )
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM appointment WHERE id = $1::uuid", b["lich"]
        )
        == 1
    )
    # Nhật ký + bản lưu để khôi phục tay.
    nk = await pool.fetchrow(
        "SELECT boi_staff_id::text AS boi, khach::text AS khach, tep_da_chuyen"
        " FROM lan_don_du_lieu_thu WHERE id = $1::uuid",
        lan,
    )
    assert nk["boi"] == ql.staff_id and "Khách thử bị xoá" in nk["khach"]
    assert nk["tep_da_chuyen"] is not None
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM du_lieu_da_xoa WHERE lan_id = $1::uuid"
            " AND bang = 'patient' AND du_lieu->>'clinic_patient_id' = $2",
            lan,
            a["id"],
        )
        == 1
    )
    # Nhật ký không xoá được.
    with pytest.raises(asyncpg.PostgresError):
        await pool.execute("DELETE FROM lan_don_du_lieu_thu WHERE id = $1::uuid", lan)
    # Không trigger nào bị bỏ tắt.
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
            " WHERE NOT t.tgisinternal AND t.tgenabled = 'D'"
            "   AND c.relnamespace = 'public'::regnamespace"
        )
        == 0
    )

    # Xoá lại khách đã xoá → báo rõ, không lỗi 500.
    r = await _xoa(http, ql, a["id"], "XOA")
    assert r.status_code == 422, r.text

    # Dọn khách giữ của bài này.
    r = await _xoa(http, ql, b["id"], "XOA")
    assert r.status_code == 200, r.text


@pytest.mark.db
@pytest.mark.asyncio
async def test_chan_khach_co_luot_dang_mo_hom_nay(
    pool: asyncpg.Pool, http: httpx.AsyncClient
) -> None:
    ql = await _nguoi(pool, "MANAGEMENT", ["quan_tri_quyen"])
    c = await _khach(pool, "Khách đang khám", mo_hom_nay=True)

    r = await _goi(http, ql, "POST", "/xem-truoc", json={"khach": [c["id"]]})
    assert r.status_code == 200 and r.json()["bi_chan"][0]["id"] == c["id"]

    r = await _xoa(http, ql, c["id"], "XOA")
    assert r.status_code == 422, r.text
    assert "đang có lượt khám MỞ" in r.text
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM patient WHERE clinic_patient_id = $1::uuid", c["id"]
        )
        == 1
    )

    # Khách về (đóng lượt) thì xoá được.
    await pool.execute(
        "UPDATE visit SET closed_at = now() WHERE visit_id = $1::uuid", c["mo"]
    )
    r = await _xoa(http, ql, c["id"], "XOA")
    assert r.status_code == 200, r.text
