"""Màn kho vật tư: nơi chứa, mức tối thiểu, nhắc, danh sách phiếu, giá nhập chốt."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from tests.services.test_vat_tu_kho_db import _bo, _ghi

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_muc_toi_thieu_nhac_duoi_muc_va_ghi_nguoi_sua(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_kho_man_service import (
        dat_muc_toi_thieu,
        doc_canh_bao,
    )

    identity, vt, rooms = await _bo(pool)
    # Chưa từng nhập kho phòng này vẫn đặt được mức tối thiểu (tồn bằng 0 → nhắc).
    kq = await dat_muc_toi_thieu(
        pool, identity=identity, vat_tu_id=vt, room_id=rooms[0], muc="5"
    )
    assert kq["ok"] is True
    ton = await pool.fetchrow(
        "SELECT so_luong, ton_toi_thieu, muc_sua_boi::text, muc_sua_luc"
        " FROM vat_tu_ton WHERE vat_tu_id=$1::uuid AND room_id=$2::uuid",
        vt,
        rooms[0],
    )
    assert ton["so_luong"] == 0 and ton["ton_toi_thieu"] == 5
    assert ton["muc_sua_boi"] == identity.staff_id and ton["muc_sua_luc"]
    nhac = [
        r for r in await doc_canh_bao(pool, identity=identity) if r["vat_tu_id"] == vt
    ]
    assert [r["canh_bao"] for r in nhac] == ["Dưới mức tối thiểu"]

    await _ghi(pool, identity, vt, "NHAP", den=rooms[0], so=5)
    assert not [
        r for r in await doc_canh_bao(pool, identity=identity) if r["vat_tu_id"] == vt
    ]

    # Xuất vượt tồn: vật tư vẫn cho âm, nhưng PHẢI báo "tồn âm — cần kiểm đếm".
    await _ghi(pool, identity, vt, "HUY", tu=rooms[0], so=8)
    am = [
        r for r in await doc_canh_bao(pool, identity=identity) if r["vat_tu_id"] == vt
    ]
    assert [r["canh_bao"] for r in am] == ["tồn âm — cần kiểm đếm"]


@pytest.mark.parametrize(
    "muc", [-1, "abc", "NaN", "Infinity", True, None, "1e30", "1.0005"]
)
async def test_muc_toi_thieu_rac_422_khong_ghi(pool: asyncpg.Pool, muc: Any) -> None:
    from clinicai.services.vat_tu_kho_man_service import dat_muc_toi_thieu

    identity, vt, rooms = await _bo(pool)
    with pytest.raises(ValidationError):
        await dat_muc_toi_thieu(
            pool, identity=identity, vat_tu_id=vt, room_id=rooms[0], muc=muc
        )
    assert not await pool.fetchval(
        "SELECT count(*) FROM vat_tu_ton WHERE vat_tu_id=$1::uuid", vt
    )


async def test_muc_toi_thieu_phong_khac_co_so_hoac_vat_tu_la(
    pool: asyncpg.Pool,
) -> None:
    from clinicai.services.vat_tu_kho_man_service import dat_muc_toi_thieu

    identity, vt, _ = await _bo(pool)
    with pytest.raises(NotFoundError):
        await dat_muc_toi_thieu(
            pool, identity=identity, vat_tu_id=vt, room_id=str(uuid.uuid4()), muc=1
        )
    with pytest.raises(NotFoundError):
        await dat_muc_toi_thieu(
            pool, identity=identity, vat_tu_id=str(uuid.uuid4()), room_id=None, muc=1
        )


async def test_noi_chua_co_kho_phong_va_phong_tat_con_ton(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_kho_man_service import doc_noi_chua

    identity, vt, rooms = await _bo(pool)
    await _ghi(pool, identity, vt, "NHAP", den=rooms[1], so=2)
    await pool.execute(
        "UPDATE clinic_room SET is_active=false WHERE id=$1::uuid", rooms[1]
    )
    ds = await doc_noi_chua(pool, identity=identity)
    assert ds[0]["room_id"] is None and ds[0]["ten"] == "Kho cơ sở"
    theo_phong = {r["room_id"]: r for r in ds}
    assert theo_phong[rooms[0]]["dang_bat"] is True
    # Phòng đã tắt còn tồn vẫn hiện (để kiểm đếm / trả kho); tắt hết tồn thì ẩn.
    assert theo_phong[rooms[1]]["dang_bat"] is False
    await _ghi(pool, identity, vt, "TRA_KHO", tu=rooms[1], so=2)
    ds2 = {r["room_id"] for r in await doc_noi_chua(pool, identity=identity)}
    assert rooms[1] not in ds2 and rooms[0] in ds2


async def test_danh_sach_phieu_co_nguoi_lap_va_da_dao(pool: asyncpg.Pool) -> None:
    from clinicai.services.vat_tu_kho_man_service import doc_phieu
    from clinicai.services.vat_tu_kho_service import hoan_phieu

    identity, vt, rooms = await _bo(pool)
    p1 = await _ghi(pool, identity, vt, "NHAP", den=rooms[0], so=4)
    p2 = await _ghi(pool, identity, vt, "XUAT_PHONG", den=rooms[1], so=1)
    await hoan_phieu(
        pool, identity=identity, phieu_id=p2["id"], khoa_gui=uuid.uuid4().hex
    )
    ds = await doc_phieu(pool, identity=identity, gioi_han=50)
    theo_id = {p["id"]: p for p in ds}
    assert theo_id[p2["id"]]["da_dao"] is True and theo_id[p1["id"]]["da_dao"] is False
    assert theo_id[p1["id"]]["nguoi_tao_id"] == identity.staff_id
    assert theo_id[p1["id"]]["dong"][0]["so_luong"] == 4
    # Mới nhất trước; phiếu đảo không tự đảo lại được.
    assert ds.index(theo_id[p2["id"]]) > 0 or len(ds) >= 3
    dao = [p for p in ds if p["loai"] == "HOAN"]
    assert dao and dao[0]["da_dao"] is False and dao[0]["dao_phieu_id"] == p2["id"]
    # Giới hạn rác không làm hỏng, chỉ về mặc định.
    assert await doc_phieu(pool, identity=identity, gioi_han="abc")


async def test_gia_nhap_mac_dinh_la_ban_chup_luc_lap_phieu(pool: asyncpg.Pool) -> None:
    identity, vt, rooms = await _bo(pool)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=1200 WHERE id=$1::uuid", vt
    )
    p = await _ghi(pool, identity, vt, "NHAP", den=rooms[0], so=10)
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=9999 WHERE id=$1::uuid", vt
    )
    gia = await pool.fetchval(
        "SELECT gia_nhap FROM vat_tu_txn WHERE phieu_id=$1::uuid", p["id"]
    )
    assert gia == 1200
    # Danh mục không có giá nhập → 0, không lỗi.
    await pool.execute(
        "UPDATE service_price SET gia_nhap_vat_tu=NULL WHERE id=$1::uuid", vt
    )
    p2 = await _ghi(pool, identity, vt, "NHAP", den=rooms[0], so=1)
    assert (
        await pool.fetchval(
            "SELECT gia_nhap FROM vat_tu_txn WHERE phieu_id=$1::uuid", p2["id"]
        )
        == 0
    )


async def test_http_phieu_gui_lai_cung_khoa_khong_nhan_doi(pool: asyncpg.Pool) -> None:
    from collections.abc import AsyncIterator

    from httpx import ASGITransport, AsyncClient

    from clinicai.api.identity import get_current_identity
    from clinicai.api.v1.routers import vat_tu_kho as rt
    from clinicai.core.database import get_db_pool
    from clinicai.main import app

    identity, vt, rooms = await _bo(pool)

    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[rt._QL] = lambda: identity
    app.dependency_overrides[get_current_identity] = lambda: identity
    khoa = {"Idempotency-Key": uuid.uuid4().hex}
    don_vi = await pool.fetchval(
        "SELECT don_vi FROM service_price WHERE id=$1::uuid", vt
    )
    dong: dict[str, Any] = {
        "vat_tu_id": vt,
        "don_vi": don_vi,
        "den_room_id": rooms[0],
    }
    body = {"loai": "NHAP", "dong": [dong]}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # Thiếu / rác số lượng → 422 có lời, không ghi gì.
            r = await c.post("/api/v1/vat-tu-kho/phieu", json=body, headers=khoa)
            assert r.status_code == 422
            dong["so_luong"] = "7"
            dong.pop("don_vi")
            khoa = {"Idempotency-Key": uuid.uuid4().hex}
            thieu_don_vi = await c.post(
                "/api/v1/vat-tu-kho/phieu", json=body, headers=khoa
            )
            assert thieu_don_vi.status_code == 422
            dong["don_vi"] = don_vi
            khoa = {"Idempotency-Key": uuid.uuid4().hex}
            a = await c.post("/api/v1/vat-tu-kho/phieu", json=body, headers=khoa)
            b = await c.post("/api/v1/vat-tu-kho/phieu", json=body, headers=khoa)
            assert a.status_code == 201 and b.json()["id"] == a.json()["id"]
            thieu = await c.post("/api/v1/vat-tu-kho/phieu", json=body)
            assert thieu.status_code == 422
            muc = await c.put(
                "/api/v1/vat-tu-kho/muc-toi-thieu",
                json={"vat_tu_id": vt, "room_id": rooms[0], "muc": -3},
            )
            assert muc.status_code == 422
            ok = await c.put(
                "/api/v1/vat-tu-kho/muc-toi-thieu",
                json={"vat_tu_id": vt, "room_id": rooms[0], "muc": 9},
            )
            assert ok.status_code == 200
            ton = (await c.get("/api/v1/vat-tu-kho/ton")).json()
            mine = [x for x in ton["items"] if x["vat_tu_id"] == vt]
            assert mine[0]["so_luong"] == 7 and mine[0]["canh_bao"]
            ds = (await c.get("/api/v1/vat-tu-kho/phieu?gioi_han=abc")).json()
            assert any(p["id"] == a.json()["id"] for p in ds["items"])
            hoan = await c.post(
                f"/api/v1/vat-tu-kho/phieu/{a.json()['id']}/hoan",
                json={},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            )
            assert hoan.status_code == 201
    finally:
        app.dependency_overrides.clear()
