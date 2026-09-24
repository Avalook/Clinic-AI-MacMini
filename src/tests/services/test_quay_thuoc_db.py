"""Quầy thuốc chỉnh đơn bán trước khi thu (Tuyền 24/09/2026).

Bỏ tick / tích lại · đổi số mua (≤ số kê) · lấy thêm thuốc (dòng QUAY) · dòng quầy
không lọt vào đơn bác sĩ · lịch sử + sự kiện · ``medicine.declined`` ở bản thanh
toán cuối.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1.

from __future__ import annotations

import json
from typing import Any

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.services.pharmacy_service import PharmacyService
from clinicai.services.phieu_kham_service import PhieuKhamService
from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_tien_thuoc_cp1_db import Quay, _don, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh, _thu

pytest_plugins = ["tests.services.test_luot_kham_service_db"]


@pytest.fixture(autouse=True)
def _tat_kho_thuoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")


async def _su_kien(q: Quay, ten: str) -> list[dict[str, Any]]:
    rows = await q.pool.fetch(
        "SELECT payload FROM domain_event WHERE event_type = $1"
        " AND aggregate_id = $2::uuid ORDER BY occurred_at",
        ten,
        q.visit_id,
    )
    return [
        json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
        for r in rows
    ]


async def test_bo_tick_tich_lai_doi_so_mua(q: Quay) -> None:
    rx, _drug = await _dong_da_xac_dinh(q, 10)
    svc = QuayThuocService(q.pool)
    await svc.chon(prescription_id=rx, mua=False, identity=q.thu_ngan)
    dong = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert [(d["id"], d["mua"]) for d in dong] == [(rx, False)]
    await svc.chon(prescription_id=rx, mua=True, identity=q.thu_ngan)
    await svc.doi_so_luong(prescription_id=rx, so_luong=6, identity=q.thu_ngan)
    [d] = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert (d["mua"], d["so_ke"], d["so_mua"]) == (True, "10", "6")
    # Không vượt số kê — muốn thêm thì thêm dòng quầy.
    with pytest.raises(ValidationError, match="Lấy thêm"):
        await svc.doi_so_luong(prescription_id=rx, so_luong=12, identity=q.thu_ngan)
    hanh_dong = [e["hanh_dong"] for e in await _su_kien(q, "medicine.counter_changed")]
    assert hanh_dong == ["BO_CHON", "CHON_LAI", "SO_LUONG"]


async def test_lay_them_thuoc_khong_lot_vao_don_bac_si(q: Quay) -> None:
    rx, drug = await _dong_da_xac_dinh(q, 10)
    svc = QuayThuocService(q.pool)
    kq = await svc.luu_dong_them(
        visit_id=q.visit_id,
        dong=[
            {
                "drug_catalog_id": drug,
                "quantity": "5 viên",
                "dosage": "Uống — sáng 1 viên",
                "caution": "Sau ăn",
            }
        ],
        identity=q.thu_ngan,
    )
    [moi] = kq["them"]
    dong = (await svc.doc(visit_id=q.visit_id, identity=q.thu_ngan))["dong"]
    assert [(d["id"], d["nguon"]) for d in dong] == [(rx, "BAC_SI"), (moi, "QUAY")]
    # Sửa dòng quầy: số lượng + cách dùng.
    await svc.luu_dong_them(
        visit_id=q.visit_id,
        dong=[
            {
                "id": moi,
                "drug_catalog_id": drug,
                "quantity": "8 viên",
                "dosage": "Uống — tối 1 viên",
                "caution": "",
            }
        ],
        identity=q.thu_ngan,
    )
    r = await q.pool.fetchrow(
        "SELECT quantity_num, dosage_instructions FROM prescription"
        " WHERE id = $1::uuid",
        moi,
    )
    assert (float(r["quantity_num"]), r["dosage_instructions"]) == (
        8,
        "Uống — tối 1 viên",
    )
    # Đơn BÁC SĨ không thấy dòng quầy → bác sĩ lưu lại đơn không "xoá" nó.
    ds = await PhieuKhamService(q.pool, kiem_quyen=_cho_qua).doc_don_thuoc(
        visit_id=q.visit_id, identity=q.bac_si
    )
    assert [d["id"] for d in ds] == [rx]


async def _cho_qua(*_a: object, **_k: object) -> None:
    return None


async def test_thu_xong_phat_thuoc_bi_bo_o_ban_cuoi_va_khoa_quay(q: Quay) -> None:
    rx1, drug = await _dong_da_xac_dinh(q, 10)
    rx2 = await _don(q, 4)
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx2, drug_catalog_id=drug
    )
    svc = QuayThuocService(q.pool)
    await svc.chon(prescription_id=rx2, mua=False, identity=q.thu_ngan)
    await svc.doi_so_luong(prescription_id=rx1, so_luong=7, identity=q.thu_ngan)
    await _thu(q)
    bo = {e["prescription_id"]: e for e in await _su_kien(q, "medicine.declined")}
    assert set(bo) == {rx1, rx2}
    assert (bo[rx1]["so_ke"], bo[rx1]["so_mua"]) == ("10", "7")
    assert (bo[rx2]["so_ke"], bo[rx2]["so_mua"]) == ("4", "0")
    # Thu rồi thì quầy không chỉnh nữa.
    with pytest.raises(ConflictError):
        await svc.chon(prescription_id=rx1, mua=False, identity=q.thu_ngan)
    with pytest.raises(ConflictError):
        await svc.luu_dong_them(
            visit_id=q.visit_id,
            dong=[{"drug_catalog_id": drug, "quantity": "1 viên"}],
            identity=q.thu_ngan,
        )


async def test_lay_them_phai_chon_thuoc_danh_muc_va_co_so_luong(q: Quay) -> None:
    _rx, drug = await _dong_da_xac_dinh(q, 3)
    svc = QuayThuocService(q.pool)
    with pytest.raises(ValidationError, match="danh mục"):
        await svc.luu_dong_them(
            visit_id=q.visit_id, dong=[{"quantity": "2 viên"}], identity=q.thu_ngan
        )
    with pytest.raises(ValidationError, match="số lượng"):
        await svc.luu_dong_them(
            visit_id=q.visit_id,
            dong=[{"drug_catalog_id": drug, "quantity": "vài viên"}],
            identity=q.thu_ngan,
        )
