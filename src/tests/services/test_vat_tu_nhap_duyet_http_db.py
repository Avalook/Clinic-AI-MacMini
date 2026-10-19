"""G8b — đường HTTP của phiếu nhập vật tư chờ duyệt (lõi: test_vat_tu_nhap_duyet_db.py).

    scripts/test-nhanh.sh src/tests/services/test_vat_tu_nhap_duyet_http_db.py

Kiểm cửa quyền (xem theo `vat_tu.manage`, duyệt / từ chối theo `vat_tu.approve`),
mã trạng thái (422 rác, 409 đã quyết, 404 la) và cả chuỗi lập → xem → duyệt → hoàn tác
đi qua FastAPI thật.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient

from clinicai.api.identity import StaffIdentity, get_current_identity
from clinicai.api.v1.routers import vat_tu_kho as kho_rt
from clinicai.api.v1.routers import vat_tu_nhap_duyet as rt
from clinicai.core.database import get_db_pool
from clinicai.main import app
from tests.services.test_vat_tu_nhap_duyet_db import _bo

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]

V1 = "/api/v1/vat-tu-kho"


def _dat_nguoi(pool: asyncpg.Pool, ai: StaffIdentity) -> None:
    """Đóng vai một người: bỏ cửa quyền (lego kiểm riêng ở bài lõi), đặt danh tính."""

    async def _pool() -> AsyncIterator[asyncpg.Pool]:
        yield pool

    app.dependency_overrides[get_db_pool] = _pool
    app.dependency_overrides[get_current_identity] = lambda: ai
    for cua in (rt._QL, rt._DUYET, kho_rt._QL):
        app.dependency_overrides[cua] = lambda ai=ai: ai


async def test_http_lap_xem_duyet_tu_choi_rut_lai(pool: asyncpg.Pool) -> None:
    b = await _bo(pool)
    don_vi = await pool.fetchval(
        "SELECT don_vi FROM service_price WHERE id=$1::uuid", b.vt_can
    )

    def dong(so: str) -> dict[str, Any]:
        return {"vat_tu_id": b.vt_can, "don_vi": don_vi, "so_luong": so}

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # Người lập (không lego duyệt) gửi phiếu NHẬP hàng cần duyệt → 201, chờ.
            _dat_nguoi(pool, b.lap)
            gui = await c.post(
                f"{V1}/phieu",
                json={"loai": "NHAP", "dong": [dong("6")]},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            )
            assert gui.status_code == 201
            yc = gui.json()["yeu_cau_id"]
            assert gui.json()["cho_duyet"] is True
            ds = (await c.get(f"{V1}/cho-duyet")).json()
            assert ds["duoc_duyet"] is False
            mine = [x for x in ds["items"] if x["id"] == yc]
            assert mine[0]["trang_thai"] == "CHO_DUYET"
            assert mine[0]["dong"][0]["ten"] == "Găng cần duyệt nhập"
            # Màn vẽ "của bạn" + nút Rút lại từ cờ này; thành tiền do máy chủ tính.
            assert mine[0]["cua_toi"] is True
            assert float(mine[0]["dong"][0]["thanh_tien"]) == float(
                mine[0]["dong"][0]["so_luong"]
            ) * float(mine[0]["dong"][0]["gia_nhap"])
            assert float(mine[0]["tong_tien"]) == float(
                mine[0]["dong"][0]["thanh_tien"]
            )
            # Người lập rút lai được; số rác ở lý do → 422.
            rac = await c.post(f"{V1}/cho-duyet/{yc}/rut-lai", json={"ly_do": "ab"})
            assert rac.status_code == 422
            # Không phải UUID → 422 của FastAPI.
            assert (await c.post(f"{V1}/cho-duyet/abc/duyet")).status_code == 422

            # Người có lego: thấy nút (duoc_duyet), từ chối thiếu lý do → 422.
            _dat_nguoi(pool, b.ql)
            ds = (await c.get(f"{V1}/cho-duyet")).json()
            assert ds["duoc_duyet"] is True
            assert [x["cua_toi"] for x in ds["items"] if x["id"] == yc] == [False]
            thieu = await c.post(f"{V1}/cho-duyet/{yc}/tu-choi", json={})
            assert thieu.status_code == 422
            ok = await c.post(
                f"{V1}/cho-duyet/{yc}/tu-choi", json={"ly_do": "Không cần nhập nữa"}
            )
            assert ok.status_code == 200 and ok.json()["trang_thai"] == "TU_CHOI"
            # Đã quyết → duyệt = 409; yêu cầu la → 404.
            assert (await c.post(f"{V1}/cho-duyet/{yc}/duyet")).status_code == 409
            la = await c.post(f"{V1}/cho-duyet/{uuid.uuid4()}/duyet")
            assert la.status_code == 404

            # Gửi mới → duyệt → có phiếu NHẬP thật, tồn tăng.
            _dat_nguoi(pool, b.lap)
            gui2 = await c.post(
                f"{V1}/phieu",
                json={"loai": "NHAP", "dong": [dong("4")]},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            )
            yc2 = gui2.json()["yeu_cau_id"]
            _dat_nguoi(pool, b.ql)
            duyet = await c.post(f"{V1}/cho-duyet/{yc2}/duyet")
            assert duyet.status_code == 201 and duyet.json()["phieu_id"]
            lai = await c.post(f"{V1}/cho-duyet/{yc2}/duyet")
            assert lai.json()["already"] is True
            ton = (await c.get(f"{V1}/ton")).json()
            mine_ton = [x for x in ton["items"] if x["vat_tu_id"] == b.vt_can]
            assert sum(float(x["so_luong"]) for x in mine_ton) == 4

            # Người có lego tự lập: kết quả cho màn nói "đã tự duyệt và nhập kho".
            tu = await c.post(
                f"{V1}/phieu",
                json={"loai": "NHAP", "dong": [dong("2")]},
                headers={"Idempotency-Key": uuid.uuid4().hex},
            )
            kq = tu.json()
            assert tu.status_code == 201
            assert kq["cho_duyet"] is False and kq["trang_thai"] == "DA_DUYET"
            assert kq["phieu_id"] and kq["ma_phieu"] and kq["ma_yeu_cau"]
    finally:
        app.dependency_overrides.clear()
