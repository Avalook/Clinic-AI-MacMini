"""Đặt cờ vật tư HÀNG LOẠT theo loại (Kho vật tư → Danh mục).

    scripts/test-nhanh.sh src/tests/services/test_vat_tu_hang_loat_db.py

DB chung có san vật tư của bài khác, nên mỗi bài chỉ khẳng định trên CÁC DÒNG MÌNH TẠO
(theo id) — không đếm tổng cả bảng. Muốn đếm "đúng bấy nhiêu dòng" thì khoanh `ids`.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from clinicai.services.vat_tu_danh_muc_service import dat_co_hang_loat
from tests.services.test_luot_kham_service_db import CLINIC, _nguoi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

URL = "/api/v1/service-prices/vat-tu/hang-loat"


async def _tao(
    pool: asyncpg.Pool,
    ten: str,
    loai: str | None,
    *,
    kinh_doanh: bool | None = None,
    can_ql_duyet: bool = False,
    can_duyet_nhap: bool = False,
    active: bool = True,
) -> str:
    return str(
        await pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " loai_vat_tu, kinh_doanh_vat_tu, can_ql_duyet,"
            " can_duyet_nhap_vat_tu, active)"
            " VALUES ($1::uuid, $2, $3, 'vat_tu', $4, $5, $6, $7, $8)"
            " RETURNING id::text",
            CLINIC,
            f"VT_HL_{uuid.uuid4().hex}",
            ten,
            loai,
            kinh_doanh,
            can_ql_duyet,
            can_duyet_nhap,
            active,
        )
    )


async def _quan_ly(pool: asyncpg.Pool, role: str = "MANAGEMENT") -> StaffIdentity:
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        return await _nguoi(conn, loc, role)


async def _khong_quyen(pool: asyncpg.Pool) -> StaffIdentity:
    """Người đăng nhập hợp lệ nhưng KHÔNG được cấp khối nào (không preset)."""
    async with pool.acquire() as conn:
        loc = await conn.fetchval(
            "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
            " AND is_active ORDER BY id LIMIT 1",
            CLINIC,
        )
        sid = await conn.fetchval(
            "INSERT INTO staff (full_name, primary_department,"
            " primary_location_id, is_active)"
            " VALUES ($1, 'DOCTOR', $2::uuid, true) RETURNING id::text",
            f"Không quyền {uuid.uuid4().hex[:6]}",
            loc,
        )
    return StaffIdentity(
        staff_id=sid,
        auth_user_id=str(uuid.uuid4()),
        full_name="Không quyền",
        department="DOCTOR",
        role=ClinicRole.DOCTOR,
        clinic_id=CLINIC,
        location_id=loc,
        location_name="Cơ sở test",
    )


async def _co(pool: asyncpg.Pool, ids: list[str], cot: str) -> dict[str, Any]:
    rows = await pool.fetch(
        f"SELECT id::text, {cot} AS v FROM service_price WHERE id = ANY($1::uuid[])",
        ids,
    )
    return {r["id"]: r["v"] for r in rows}


async def test_dung_loai_va_dung_co(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    vpp1 = await _tao(pool, "VPP một", "VPP")
    vpp2 = await _tao(pool, "VPP hai", "VPP", kinh_doanh=False)
    vpp_roi = await _tao(pool, "VPP đã bật", "VPP", kinh_doanh=True)
    vtyt = await _tao(pool, "VTYT", "VTYT")
    chua = await _tao(pool, "Chưa phân loại", None)
    moi = [vpp1, vpp2, vpp_roi, vtyt, chua]

    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=True,
        ap_dung=True,
        ids=[vpp1, vpp2, vpp_roi, vtyt, chua],
    )
    # Chỉ VPP đang khác đích bị đổi: vpp_roi đã bật sẵn; vtyt / chưa phân loại
    # nằm ngoài loại.
    assert kq["so_doi"] == 2
    assert sorted(kq["ids"]) == sorted([vpp1, vpp2])
    assert await _co(pool, moi, "kinh_doanh_vat_tu") == {
        vpp1: True,
        vpp2: True,
        vpp_roi: True,
        vtyt: None,
        chua: None,
    }
    # Chỉ đúng cờ được chọn: hai cờ kia và "Đang bán" không đổi.
    assert set((await _co(pool, moi, "can_ql_duyet")).values()) == {False}
    assert set((await _co(pool, moi, "can_duyet_nhap_vat_tu")).values()) == {False}
    assert set((await _co(pool, moi, "active")).values()) == {True}


@pytest.mark.parametrize(
    ("co", "cot"),
    [
        ("kinh_doanh", "kinh_doanh_vat_tu"),
        ("can_ql_duyet", "can_ql_duyet"),
        ("can_duyet_nhap", "can_duyet_nhap_vat_tu"),
    ],
)
async def test_ba_co_bat_roi_tat(pool: asyncpg.Pool, co: str, cot: str) -> None:
    ai = await _quan_ly(pool)
    a = await _tao(pool, "A", "VTYT")
    b = await _tao(pool, "B", "VTYT")
    for bat in (True, False):
        kq = await dat_co_hang_loat(
            pool, identity=ai, loai="VTYT", co=co, bat=bat, ap_dung=True, ids=[a, b]
        )
        assert kq["so_doi"] == 2
        assert set((await _co(pool, [a, b], cot)).values()) == {bat}


async def test_loai_rong_la_chua_phan_loai(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    chua = await _tao(pool, "Chưa 1", None)
    vpp = await _tao(pool, "VPP x", "VPP")
    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="CHUA_PHAN_LOAI",
        co="can_ql_duyet",
        bat=True,
        ap_dung=True,
        ids=[chua, vpp],
    )
    assert kq["so_doi"] == 1
    assert await _co(pool, [chua, vpp], "can_ql_duyet") == {chua: True, vpp: False}


async def test_vat_tu_tam_ngung_giu_nguyen(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    dang = await _tao(pool, "Đang bán", "VPP")
    ngung = await _tao(pool, "Tạm ngưng", "VPP", active=False)
    xem = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=True,
        ap_dung=False,
        ids=[dang, ngung],
    )
    assert xem["so_doi"] == 1
    assert xem["so_ngung_ban_bo_qua"] >= 1
    await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=True,
        ap_dung=True,
        ids=[dang, ngung],
    )
    assert await _co(pool, [dang, ngung], "kinh_doanh_vat_tu") == {
        dang: True,
        ngung: None,
    }
    assert (await _co(pool, [ngung], "active"))[ngung] is False


async def test_xem_truoc_khong_ghi_va_null_tinh_la_tat(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    nul = await _tao(pool, "Chưa tick", "VPP", kinh_doanh=None)
    bat = await _tao(pool, "Đã tick", "VPP", kinh_doanh=True)
    truoc = await pool.fetchval(
        "SELECT count(*) FROM event_log WHERE event_type='vat_tu.co_hang_loat'"
        " AND clinic_id=$1::uuid",
        CLINIC,
    )
    # NULL hiện trên màn là chưa tick = tắt → "Tắt" không đổi nó; chỉ dòng đã tick
    # đổi.
    xem = await dat_co_hang_loat(
        pool, identity=ai, loai="VPP", co="kinh_doanh", bat=False, ids=[nul, bat]
    )
    assert xem["ap_dung"] is False
    assert xem["so_doi"] == 1
    assert xem["ids"] == []
    assert await _co(pool, [nul, bat], "kinh_doanh_vat_tu") == {nul: None, bat: True}
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type='vat_tu.co_hang_loat'"
            " AND clinic_id=$1::uuid",
            CLINIC,
        )
        == truoc
    )


async def test_khong_dong_nao_khong_ghi_dau_vet(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    vt = await _tao(pool, "Đã đúng", "VTYT", can_duyet_nhap=True)
    truoc = await pool.fetchval(
        "SELECT count(*) FROM event_log WHERE event_type='vat_tu.co_hang_loat'"
        " AND clinic_id=$1::uuid",
        CLINIC,
    )
    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VTYT",
        co="can_duyet_nhap",
        bat=True,
        ap_dung=True,
        ids=[vt],
    )
    assert kq["so_doi"] == 0
    assert kq["ids"] == []
    # ids rỗng khoanh vào "không dòng nào", không phải "cả loại".
    kq0 = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VTYT",
        co="can_duyet_nhap",
        bat=False,
        ap_dung=True,
        ids=[],
    )
    assert kq0["so_doi"] == 0
    assert await _co(pool, [vt], "can_duyet_nhap_vat_tu") == {vt: True}
    assert (
        await pool.fetchval(
            "SELECT count(*) FROM event_log WHERE event_type='vat_tu.co_hang_loat'"
            " AND clinic_id=$1::uuid",
            CLINIC,
        )
        == truoc
    )


async def test_ghi_dau_vet_ai_luc_loai_co_so_dong(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    a = await _tao(pool, "Dấu vết A", "VPP")
    b = await _tao(pool, "Dấu vết B", "VPP")
    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="can_ql_duyet",
        bat=True,
        ap_dung=True,
        ids=[a, b],
    )
    dong = await pool.fetchrow(
        "SELECT payload, metadata, aggregate_type, occurred_at FROM event_log"
        " WHERE event_type='vat_tu.co_hang_loat' AND clinic_id=$1::uuid"
        " AND payload->'vat_tu_ids' @> $2::jsonb"
        " ORDER BY occurred_at DESC LIMIT 1",
        CLINIC,
        json.dumps([a]),
    )
    assert dong is not None
    payload = json.loads(dong["payload"])
    meta = json.loads(dong["metadata"])
    assert payload["loai"] == "VPP"
    assert payload["co"] == "can_ql_duyet"
    assert payload["bat"] is True
    assert payload["so_dong"] == kq["so_doi"] == 2
    assert sorted(payload["vat_tu_ids"]) == sorted([a, b])
    assert meta["clinic_staff_id"] == ai.staff_id
    assert dong["occurred_at"] is not None
    assert dong["aggregate_type"] == "vat_tu_danh_muc"


async def test_hoan_tac_bang_ids_vua_doi(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    san = await _tao(pool, "Bật san", "VPP", kinh_doanh=True)
    can_doi = await _tao(pool, "Tắt san", "VPP", kinh_doanh=False)
    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=True,
        ap_dung=True,
        ids=[san, can_doi],
    )
    assert kq["ids"] == [can_doi]
    # Hoàn tác = giá trị ngược trên đúng những dòng vừa đổi: dòng bật san KHÔNG
    # bị tắt lây.
    await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=False,
        ap_dung=True,
        ids=kq["ids"],
    )
    assert await _co(pool, [san, can_doi], "kinh_doanh_vat_tu") == {
        san: True,
        can_doi: False,
    }


async def test_ca_loai_khong_ids_doi_cac_dong_cua_minh(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    a = await _tao(pool, "Cả loại A", "VTYT")
    b = await _tao(pool, "Cả loại B", "VTYT", kinh_doanh=True)
    khac = await _tao(pool, "Loại khác", "VPP")
    xem = await dat_co_hang_loat(
        pool, identity=ai, loai="VTYT", co="kinh_doanh", bat=True
    )
    assert xem["so_doi"] >= 1
    assert xem["so_trong_loai"] >= 2
    kq = await dat_co_hang_loat(
        pool, identity=ai, loai="VTYT", co="kinh_doanh", bat=True, ap_dung=True
    )
    assert a in kq["ids"]
    assert b not in kq["ids"]
    assert khac not in kq["ids"]
    assert (await _co(pool, [khac], "kinh_doanh_vat_tu"))[khac] is None


@pytest.mark.parametrize(
    "tham_so",
    [
        {"loai": "LA", "co": "kinh_doanh", "bat": True},
        {"loai": "", "co": "kinh_doanh", "bat": True},
        {"loai": None, "co": "kinh_doanh", "bat": True},
        {"loai": "vpp", "co": "kinh_doanh", "bat": True},
        {"loai": "VPP", "co": "active", "bat": True},
        {"loai": "VPP", "co": "chon_nhanh", "bat": True},
        {"loai": "VPP", "co": "unit_price; DROP", "bat": True},
        {"loai": "VPP", "co": None, "bat": True},
        {"loai": "VPP", "co": "kinh_doanh", "bat": "true"},
        {"loai": "VPP", "co": "kinh_doanh", "bat": 1},
        {"loai": "VPP", "co": "kinh_doanh", "bat": None},
        {"loai": "VPP", "co": "kinh_doanh", "bat": True, "ids": "abc"},
        {"loai": "VPP", "co": "kinh_doanh", "bat": True, "ids": ["không-phải-uuid"]},
    ],
)
async def test_dau_vao_rac_422_khong_ghi(
    pool: asyncpg.Pool, tham_so: dict[str, Any]
) -> None:
    ai = await _quan_ly(pool)
    vt = await _tao(pool, "Không được đụng", "VPP")
    for ap in (False, True):
        with pytest.raises(ValidationError):
            await dat_co_hang_loat(pool, identity=ai, ap_dung=ap, **tham_so)
    assert (await _co(pool, [vt], "kinh_doanh_vat_tu"))[vt] is None


async def test_dich_vu_khong_bi_dung_toi(pool: asyncpg.Pool) -> None:
    ai = await _quan_ly(pool)
    dv = str(
        await pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " loai_vat_tu) VALUES ($1::uuid, $2, 'Dịch vụ lạc loại', 'dich_vu', 'VPP')"
            " RETURNING id::text",
            CLINIC,
            f"DV_HL_{uuid.uuid4().hex}",
        )
    )
    kq = await dat_co_hang_loat(
        pool,
        identity=ai,
        loai="VPP",
        co="kinh_doanh",
        bat=True,
        ap_dung=True,
        ids=[dv],
    )
    assert kq["so_doi"] == 0
    # Mặc định cột của dòng dịch vụ là false: không thành true.
    assert (await _co(pool, [dv], "kinh_doanh_vat_tu"))[dv] is not True


# ── Đường HTTP: cùng quyền sửa thuộc tính, 422 cho rác ──────────────────────────


def _dat_nguoi(pool: asyncpg.Pool, ai: StaffIdentity) -> None:
    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[get_current_identity] = lambda: ai


async def test_http_quyen_va_ma_loi(pool: asyncpg.Pool) -> None:
    quan_ly = await _quan_ly(pool, "MANAGEMENT")
    khong_quyen = await _khong_quyen(pool)
    vt = await _tao(pool, "HTTP", "VPP")
    thien = {"loai": "VPP", "co": "kinh_doanh", "bat": True, "ids": [vt]}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # Không có quyền Bảng giá → 403, không ghi (kể cả xem trước).
            _dat_nguoi(pool, khong_quyen)
            r = await c.post(URL, json={**thien, "ap_dung": True})
            assert r.status_code == 403
            assert (await _co(pool, [vt], "kinh_doanh_vat_tu"))[vt] is None

            _dat_nguoi(pool, quan_ly)
            xem = await c.post(URL, json=thien)
            assert xem.status_code == 200
            assert xem.json()["so_doi"] == 1
            assert xem.json()["ap_dung"] is False
            assert (await _co(pool, [vt], "kinh_doanh_vat_tu"))[vt] is None
            ap = await c.post(URL, json={**thien, "ap_dung": True})
            assert ap.status_code == 200
            assert ap.json()["ids"] == [vt]
            assert (await _co(pool, [vt], "kinh_doanh_vat_tu"))[vt] is True

            # Rác → 4xx rõ, không 500.
            for rac in (
                {**thien, "loai": "LA"},
                {**thien, "co": "active"},
                {**thien, "bat": "true"},
                {"loai": "VPP", "co": "kinh_doanh"},
                {**thien, "ids": ["x"]},
            ):
                r = await c.post(URL, json=rac)
                assert r.status_code == 422, rac
    finally:
        app.dependency_overrides.pop(get_db_pool, None)
        app.dependency_overrides.pop(get_current_identity, None)
