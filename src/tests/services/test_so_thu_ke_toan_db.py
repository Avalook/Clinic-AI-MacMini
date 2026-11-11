"""Kế toán xem TOÀN BỘ lịch sử thu dịch vụ / thuốc — chỉ đọc (chị Hoài, 11/11/2026).

Trước: hai màn "Lịch sử thu" chỉ mở cho VAI Quản lý hoặc người có ca trực ở quầy
thu ⇒ kế toán (lego Kế toán, `accounting.finance.full`) không đối chiếu được con
số. Giờ lego Kế toán mở sổ thu mọi ngày / ca / cơ sở, NHƯNG lối ghi
(`authorize_active` — thu, huỷ, hoàn) vẫn đòi ca trực đang mở: đọc không biến
thành quyền ghi.
"""

from __future__ import annotations

from datetime import timedelta

import asyncpg
import httpx
import pytest

from clinicai.core.clock import now_vn
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.cashier_scope_service import CashierScopeService
from tests.services.test_quyen_lego_man_db import (  # noqa: F401
    _goi,
    _nguoi,
    http,
    pool,
)
from tests.services.test_tien_thuoc_cp1_db import tao_quay
from tests.services.test_tien_thuoc_cp3_db import _san_sang, _thu

pytestmark = [pytest.mark.db, pytest.mark.asyncio]

HOM_NAY = now_vn().date().isoformat()
TU = (now_vn().date() - timedelta(days=10)).isoformat()


async def test_ke_toan_mo_duoc_so_thu_nhieu_ngay_moi_quay(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan"])
    for kind in ("dich_vu", "thuoc"):
        r = await _goi(
            http, ke_toan, "GET", "/cashier/ngay-truc", params={"quay": kind}
        )
        assert r.status_code == 200, r.text[:300]
        # quan_ly = màn mở thanh chọn ngày tự do; thao_tac = KHÔNG có nút thu.
        assert r.json()["quan_ly"] is True
        assert r.json()["thao_tac"] is False
        tham_so = {"tu": TU, "den": HOM_NAY, "kind": kind}
        for duong in ("/cashier/lich-su", "/cashier/lich-su.xlsx"):
            r = await _goi(http, ke_toan, "GET", duong, params=tham_so)
            assert r.status_code == 200, f"{duong} {kind}: {r.text[:300]}"
    r = await _goi(
        http, ke_toan, "GET", "/cashier/giao-dich", params={"tu": TU, "den": HOM_NAY}
    )
    assert r.status_code == 200, r.text[:300]
    # Thanh bên: có hai mục Lịch sử thu, KHÔNG có màn thu tiền.
    r = await _goi(http, ke_toan, "GET", "/phan-quyen/toi")
    assert r.status_code == 200, r.text[:300]
    quyen = set(r.json()["quyen"])
    assert {"payment.service.history", "payment.medicine.history"} <= quyen
    assert not {"payment.service.collect", "payment.medicine.collect"} & quyen


async def test_khong_lego_ke_toan_van_chi_xem_ca_minh(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
) -> None:
    # Có Báo cáo nhưng không có lego Kế toán, không ca trực ⇒ như cũ: bị chặn.
    nguoi = await _nguoi(pool, "DOCTOR", ["bao_cao"])
    r = await _goi(http, nguoi, "GET", "/cashier/ngay-truc", params={"quay": "dich_vu"})
    assert r.status_code == 200
    assert r.json()["quan_ly"] is False
    r = await _goi(
        http,
        nguoi,
        "GET",
        "/cashier/lich-su",
        params={"tu": TU, "den": HOM_NAY, "kind": "dich_vu"},
    )
    assert r.status_code != 200


async def test_doc_khong_thanh_quyen_ghi(
    pool: asyncpg.Pool,  # noqa: F811
) -> None:
    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan"])
    svc = CashierScopeService(pool)
    for kind in ("dich_vu", "thuoc"):
        with pytest.raises(SafetyGateError):
            await svc.authorize_active(ke_toan, kind=kind)
    with pytest.raises(SafetyGateError):
        await svc.authorize_any_active(ke_toan)


async def test_ke_toan_mo_duoc_phieu_thu_nguoi_khac_khong(
    pool: asyncpg.Pool,  # noqa: F811
    http: httpx.AsyncClient,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "1")
    q = await tao_quay(pool)
    await _san_sang(q, so=10)
    da_thu = await _thu(q)
    phieu = f"/cashier/phieu/{da_thu['payment_cycle_id']}"

    ke_toan = await _nguoi(pool, "ACCOUNTANT", ["ke_toan"])
    r = await _goi(http, ke_toan, "GET", phieu, params={"loai": "thu"})
    assert r.status_code == 200, r.text[:300]

    nguoi = await _nguoi(pool, "DOCTOR", ["bao_cao"])
    r = await _goi(http, nguoi, "GET", phieu, params={"loai": "thu"})
    assert r.status_code != 200
