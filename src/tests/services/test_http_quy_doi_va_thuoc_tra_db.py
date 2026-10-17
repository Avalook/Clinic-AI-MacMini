"""Đường HTTP của hai việc mới (17/10/2026): quyền, mã lỗi, rác → 4xx rõ (không 500).

    scripts/test-nhanh.sh src/tests/services/test_http_quy_doi_va_thuoc_tra_db.py

Service đã có test riêng; ở đây canh LỚP NGOÀI: người không có quyền kho bị 403 và không
đổi gì; thân rác → 422; lần trả không tồn tại → 404; quyết hai lần → 409.
"""

# ruff: noqa: F811 — fixture q được import.
from __future__ import annotations

import dataclasses
import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import ClinicRole, StaffIdentity, get_current_identity
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _kd, _ton
from tests.services.test_tien_thuoc_cp5_db import _da_thu_giao, _tra, _xuat

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

API = "/api/v1/pharmacy"


@pytest.fixture(autouse=True)
def _bat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")


async def _khong_quyen(pool: asyncpg.Pool) -> StaffIdentity:
    """Người đăng nhập hợp lệ nhưng KHÔNG được cấp khối nào (không preset)."""
    loc = await pool.fetchval(
        "SELECT id::text FROM clinic_location WHERE clinic_id=$1::uuid"
        " AND is_active ORDER BY id LIMIT 1",
        CLINIC,
    )
    sid = await pool.fetchval(
        "INSERT INTO staff (full_name, primary_department, primary_location_id,"
        " is_active) VALUES ($1, 'DOCTOR', $2::uuid, true) RETURNING id::text",
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


async def _chi_xem_kho(pool: asyncpg.Pool, location_id: str) -> StaffIdentity:
    """Được cấp ĐÚNG khối `xem_nha_thuoc` (pharmacy.view), không có `nha_thuoc`
    (pharmacy.dispense) — vai mà các tài khoản mẫu không có (cùng fixture
    supabase/fixtures/tai_khoan_chi_xem_kho.sql)."""
    ai = dataclasses.replace(await _khong_quyen(pool), location_id=location_id)
    await pool.execute(
        "INSERT INTO capability_grant (clinic_id, staff_id, capability, scope_type,"
        " tu_khoi, ly_do) SELECT $1::uuid, $2::uuid, c.ma, 'CLINIC', 'xem_nha_thuoc',"
        " 'test chỉ xem' FROM capability c WHERE c.work_pack = 'xem_nha_thuoc'",
        CLINIC,
        ai.staff_id,
    )
    return ai


def _dat_nguoi(pool: asyncpg.Pool, ai: StaffIdentity) -> None:
    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[get_current_identity] = lambda: ai


def _bo_ghi_de() -> None:
    app.dependency_overrides.pop(get_db_pool, None)
    app.dependency_overrides.pop(get_current_identity, None)


async def _lan_tra(q: Quay, so: int = 3) -> tuple[str, str]:
    rx, lo, _ = await _da_thu_giao(q, 5)
    await _tra(q, await _xuat(q, rx), so)
    tra = await q.pool.fetchval(
        "SELECT id::text FROM drug_return WHERE prescription_id = $1::uuid", rx
    )
    return str(tra), lo


async def test_nguoi_khong_quyen_bi_403_va_khong_doi_gi(q: Quay) -> None:
    tra, lo = await _lan_tra(q)
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    thuoc = await q.pool.fetchval(
        "SELECT drug_catalog_id::text FROM drug_batch WHERE id = $1::uuid", lo
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            _dat_nguoi(q.pool, await _khong_quyen(q.pool))
            r = await c.get(f"{API}/thuoc-tra-cho-kiem")
            assert r.status_code == 403
            r = await c.get(f"{API}/quy-doi", params={"drug_catalog_id": thuoc})
            assert r.status_code == 403
            r = await c.post(
                f"{API}/xu-ly-thuoc-tra",
                json={"drug_return_id": tra, "quyet_dinh": "BAN_LAI"},
            )
            assert r.status_code == 403
            r = await c.post(
                f"{API}/receive",
                json={
                    "drug_catalog_id": thuoc,
                    "so_luong": 1,
                    "batch_code": "KHONG-QUYEN",
                    "unit": "hộp",
                    "he_so": "10",
                },
            )
            assert r.status_code == 403
    finally:
        _bo_ghi_de()
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)
    assert (
        await q.pool.fetchval(
            "SELECT disposition FROM drug_return WHERE id=$1::uuid", tra
        )
        is None
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE batch_code = 'KHONG-QUYEN'"
        )
        == 0
    )


async def test_nguoi_chi_xem_doc_duoc_nhung_lenh_ghi_bi_403(q: Quay) -> None:
    tra, lo = await _lan_tra(q)
    ton, kd = await _ton(q, lo), await _kd(q, lo)
    thuoc = await q.pool.fetchval(
        "SELECT drug_catalog_id::text FROM drug_batch WHERE id = $1::uuid", lo
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            _dat_nguoi(q.pool, await _chi_xem_kho(q.pool, q.duoc_si.location_id))
            ds = await c.get(f"{API}/thuoc-tra-cho-kiem")
            assert ds.status_code == 200
            assert tra in [d["id"] for d in ds.json()["dong"]]
            r = await c.get(f"{API}/quy-doi", params={"drug_catalog_id": thuoc})
            assert r.status_code == 200
            for lenh in ("BAN_LAI", "HUY"):
                r = await c.post(
                    f"{API}/xu-ly-thuoc-tra",
                    json={
                        "drug_return_id": tra,
                        "quyet_dinh": lenh,
                        "ly_do": "Hỏng nắp",
                    },
                )
                assert r.status_code == 403, lenh
            r = await c.post(
                f"{API}/receive",
                json={
                    "drug_catalog_id": thuoc,
                    "so_luong": 1,
                    "batch_code": "CHI-XEM",
                    "unit": "viên",
                },
            )
            assert r.status_code == 403
    finally:
        _bo_ghi_de()
    assert (await _ton(q, lo), await _kd(q, lo)) == (ton, kd)
    assert (
        await q.pool.fetchval(
            "SELECT disposition FROM drug_return WHERE id=$1::uuid", tra
        )
        is None
    )
    assert (
        await q.pool.fetchval(
            "SELECT count(*) FROM drug_batch WHERE batch_code='CHI-XEM'"
        )
        == 0
    )


async def test_quyet_dinh_qua_http_thanh_cong_thieu_ly_do_rac_va_lan_hai(
    q: Quay,
) -> None:
    tra, lo = await _lan_tra(q)
    ton0, kd0 = await _ton(q, lo), await _kd(q, lo)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            _dat_nguoi(q.pool, q.duoc_si)
            ds = await c.get(f"{API}/thuoc-tra-cho-kiem")
            assert ds.status_code == 200
            assert tra in [d["id"] for d in ds.json()["dong"]]
            # Thân rác → 4xx rõ, không 500.
            for rac in (
                {},
                {"drug_return_id": "khong-phai-uuid", "quyet_dinh": "HUY"},
                {"drug_return_id": tra, "ly_do": "x" * 501},
            ):
                r = await c.post(f"{API}/xu-ly-thuoc-tra", json=rac)
                assert r.status_code == 422, rac
            # Thiếu / sai quyết định → câu tiếng Việt.
            for quyet in (None, "RESTOCK", ""):
                r = await c.post(
                    f"{API}/xu-ly-thuoc-tra",
                    json={"drug_return_id": tra, "quyet_dinh": quyet},
                )
                assert r.status_code == 422, quyet
                assert "nhập lại bán được" in r.json()["message"]
            # Huỷ thiếu lý do.
            r = await c.post(
                f"{API}/xu-ly-thuoc-tra",
                json={"drug_return_id": tra, "quyet_dinh": "HUY", "ly_do": "ab"},
            )
            assert r.status_code == 422 and "ghi lý do" in r.json()["message"]
            # Lần trả không tồn tại → 404.
            r = await c.post(
                f"{API}/xu-ly-thuoc-tra",
                json={"drug_return_id": str(uuid.uuid4()), "quyet_dinh": "BAN_LAI"},
            )
            assert r.status_code == 404
            assert (await _ton(q, lo), await _kd(q, lo)) == (ton0, kd0)  # chưa đổi gì
            # Thành công, rồi quyết lần hai → 409.
            ok = await c.post(
                f"{API}/xu-ly-thuoc-tra",
                json={"drug_return_id": tra, "quyet_dinh": "BAN_LAI"},
            )
            assert ok.status_code == 200 and ok.json()["quyet_dinh"] == "BAN_LAI"
            assert (await _ton(q, lo), await _kd(q, lo)) == (ton0, kd0 + 3)
            lai = await c.post(
                f"{API}/xu-ly-thuoc-tra",
                json={"drug_return_id": tra, "quyet_dinh": "HUY", "ly_do": "Đổi ý nhé"},
            )
            assert lai.status_code == 409
            assert (await _ton(q, lo), await _kd(q, lo)) == (ton0, kd0 + 3)
    finally:
        _bo_ghi_de()


async def test_xem_truoc_quy_doi_qua_http_rac_khong_500(q: Quay) -> None:
    _, lo = await _lan_tra(q)
    thuoc = await q.pool.fetchval(
        "SELECT drug_catalog_id::text FROM drug_batch WHERE id = $1::uuid", lo
    )
    await q.pool.execute(
        "UPDATE drug_catalog SET don_vi_ban = 'viên' WHERE id = $1::uuid", thuoc
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            _dat_nguoi(q.pool, q.duoc_si)
            ok = await c.get(
                f"{API}/quy-doi",
                params={
                    "drug_catalog_id": thuoc,
                    "unit": "hộp",
                    "he_so": "10",
                    "so_luong": "6",
                },
            )
            assert ok.status_code == 200, ok.text
            j: dict[str, Any] = ok.json()
            assert j["can_doi"] is True and float(j["so_luong_quy_doi"]) == 60
            # Số lượng rác → vẫn 200, không có dòng "= N"; hệ số rác → 422 câu rõ.
            r = await c.get(
                f"{API}/quy-doi",
                params={
                    "drug_catalog_id": thuoc,
                    "unit": "hộp",
                    "he_so": "10",
                    "so_luong": "x",
                },
            )
            assert r.status_code == 200 and r.json()["so_luong_quy_doi"] is None
            for he in ("abc", "-5", "0", "1e12", "99999"):
                r = await c.get(
                    f"{API}/quy-doi",
                    params={"drug_catalog_id": thuoc, "unit": "hộp", "he_so": he},
                )
                assert r.status_code == 422, he
                assert r.json()["message"], he
            # id không phải uuid → 422, không 500.
            r = await c.get(f"{API}/quy-doi", params={"drug_catalog_id": "x"})
            assert r.status_code == 422
    finally:
        _bo_ghi_de()
