"""Quyền Xem bảng giá (11/11/2026): kế toán XEM được bảng giá dịch vụ & phòng mà
không sửa được gì. Trước đó muốn mở màn `/cashier/dich-vu` chỉ có lego Bảng giá —
tức quyền SỬA giá (`price.service.manage`).

Cửa ghi giá dịch vụ chỉ nằm ở router (`PriceListService.update` không tự hỏi quyền
cho nhóm dịch vụ), nên các bài chặn ở đây đi qua HTTP thật, không gọi thẳng service.
"""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import httpx
import pytest

from clinicai.permissions.catalogue import KHOI_MO_FULL, MAN, PRESET, QUYEN
from tests.services.test_quyen_lego_man_db import (  # noqa: F401
    CLINIC,
    _goi,
    _nguoi,
    http,
    pool,
)

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

XEM = "price.service.view"


async def _gia(pool: asyncpg.Pool) -> str:  # noqa: F811
    return str(
        await pool.fetchval(
            'INSERT INTO service_price (clinic_id, service_code, name, "group",'
            " unit_price) VALUES ($1::uuid, $2, $3, 'dich_vu', 1000)"
            " RETURNING id::text",
            CLINIC,
            f"XG{uuid.uuid4().hex[:10]}",
            f"Giá xem {uuid.uuid4().hex[:8]}",
        )
    )


async def _don_gia(pool: asyncpg.Pool, ma: str) -> Any:  # noqa: F811
    return await pool.fetchval(
        "SELECT unit_price FROM service_price WHERE id = $1::uuid", ma
    )


async def test_chi_xem_doc_duoc_bang_gia_va_co_bao_khong_sua(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["xem_bang_gia"])
    for p in (
        "/service-prices/danh-muc",
        "/service-prices/phong-lam",
        "/service-prices?group=dich_vu",
    ):
        r = await _goi(http, ke_toan, "GET", p)
        assert r.status_code == 200, f"GET {p} → {r.status_code} {r.text[:200]}"
    goi = (await _goi(http, ke_toan, "GET", "/service-prices/danh-muc")).json()
    assert goi["sua_gia_duoc"] is False
    assert goi["sua_phong_duoc"] is False


async def test_chi_xem_moi_lenh_ghi_bi_chan_gia_giu_nguyen(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["xem_bang_gia"])
    ma = await _gia(pool)
    lenh: list[tuple[str, str, dict[str, Any]]] = [
        ("PATCH", f"/service-prices/{ma}", {"unit_price": 999_999}),
        ("PATCH", f"/service-prices/{ma}", {"active": False}),
        ("PATCH", f"/service-prices/{ma}", {"billing_owner": "EXTERNAL_PARTNER"}),
        (
            "POST",
            "/service-prices",
            {"name": "Dịch vụ lén thêm", "group": "dich_vu", "unit_price": 1},
        ),
        (
            "PUT",
            "/clinic-config/service-rooms",
            {"service_code": "KHONG_CO", "room_ids": []},
        ),
    ]
    for method, p, than in lenh:
        r = await _goi(http, ke_toan, method, p, json=than)
        assert r.status_code == 403, f"{method} {p} → {r.status_code} {r.text[:200]}"
    assert await _don_gia(pool, ma) == 1000
    assert not await pool.fetchval(
        "SELECT 1 FROM service_price WHERE clinic_id = $1::uuid"
        " AND name = 'Dịch vụ lén thêm'",
        CLINIC,
    )


async def test_co_lego_bang_gia_thi_sua_duoc_nhu_cu(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    sua = await _nguoi(pool, "CSKH", ["bang_gia"])
    goi = (await _goi(http, sua, "GET", "/service-prices/danh-muc")).json()
    assert goi["sua_gia_duoc"] is True
    ma = await _gia(pool)
    r = await _goi(
        http, sua, "PATCH", f"/service-prices/{ma}", json={"unit_price": 2000}
    )
    assert r.status_code == 200, r.text
    assert await _don_gia(pool, ma) == 2000


async def test_khong_lego_gia_nao_thi_khong_doc_duoc(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    ai = await _nguoi(pool, "ACCOUNTANT", ["ke_toan", "bao_cao"])
    r = await _goi(http, ai, "GET", "/service-prices/danh-muc")
    assert r.status_code == 403, r.text


async def test_thu_ngan_van_tra_gia_nhung_khong_sua(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    """Đường đọc cũ của quầy thu không đổi: tra giá được, cờ sửa vẫn tắt."""
    thu_ngan = await _nguoi(pool, "CASHIER", ["thu_tien_dv"])
    r = await _goi(http, thu_ngan, "GET", "/service-prices/danh-muc")
    assert r.status_code == 200, r.text
    assert r.json()["sua_gia_duoc"] is False


async def test_danh_muc_quyen_va_nhom_mau_trong_database(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    assert QUYEN[XEM].khoi == "xem_bang_gia"
    assert (
        await pool.fetchval("SELECT work_pack FROM capability WHERE ma = $1", XEM)
        == "xem_bang_gia"
    )
    rows = await pool.fetch(
        "SELECT ma, khoi FROM quyen_preset WHERE clinic_id = $1::uuid AND he_thong"
        " AND ma = ANY($2::text[])",
        CLINIC,
        ["KE_TOAN", "ACCOUNTANT", "MANAGEMENT"],
    )
    assert {r["ma"] for r in rows if "xem_bang_gia" in r["khoi"]} == {
        "KE_TOAN",
        "ACCOUNTANT",
        "MANAGEMENT",
    }


def test_lego_xem_bang_gia_mo_dung_man_va_khong_mo_cho_moi_nguoi() -> None:
    """Có dòng MAN thì màn Phân quyền có công tắc; không vào "mở full" nên nhân viên
    khác không tự dưng thấy thêm màn."""
    assert list(MAN["xem_bang_gia"].khoi) == ["xem_bang_gia"]
    assert list(MAN["xem_bang_gia"].cac_duong) == ["/cashier/dich-vu"]
    assert "xem_bang_gia" not in KHOI_MO_FULL
    assert "xem_bang_gia" in PRESET["KE_TOAN"]
    assert PRESET["ACCOUNTANT"] == PRESET["KE_TOAN"]
