"""Contract tiền–thuốc CP2 (19/09/2026).

Đầu CP2 — lỗi review CP1 #8: bác sĩ lưu lại bệnh án sau khi tiền thuốc đã thu
làm `_replace_prescriptions` xoá rồi chèn lại dòng đơn chưa cấp. Ảnh chụp hoá
đơn còn, nhưng dòng đơn gốc — nguồn để nhà thuốc giao — biến mất.
"""

# ruff: noqa: F811 — fixture `q` được IMPORT từ CP1 (khai qua pytest_plugins thì
# không nạp khi chạy trọn bộ); tham số `q` của từng test là chính fixture ấy.

from __future__ import annotations

from typing import Any

import asyncpg
import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.services.clinical_record_service import ClinicalRecordService
from clinicai.services.pharmacy_service import PharmacyService
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (
    Quay,
    _don,
    _hd,
    _thu,
    _thuoc,
    q,  # noqa: F401
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _luu_don(q: Quay, dong: list[dict[str, Any]]) -> None:
    """Đúng như `save()`: khoá dòng visit trước, rồi thay đơn thuốc."""
    async with q.pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "SELECT 1 FROM visit WHERE visit_id = $1::uuid FOR UPDATE",
                q.visit_id,
            )
            pid = await conn.fetchval(
                "SELECT clinic_patient_id::text FROM visit WHERE visit_id = $1::uuid",
                q.visit_id,
            )
            await ClinicalRecordService(q.pool)._replace_prescriptions(
                conn,
                visit_id=q.visit_id,
                clinic_patient_id=pid,
                prescriptions=dong,
                clinic_id=CLINIC,
                created_by=q.bac_si.staff_id,
            )


async def _don_da_thu(q: Quay) -> tuple[str, str]:
    rx = await _don(q, 10, ten="Thuốc đã thu")
    await PharmacyService(q.pool).xac_dinh_thuoc(
        identity=q.duoc_si, prescription_id=rx, drug_catalog_id=await _thuoc(q)
    )
    await _thu(q, "thuoc", bill_revision=(await _hd(q, "thuoc")).revision)
    return rx, "10 viên"


async def _cac_dong(q: Quay) -> list[asyncpg.Record]:
    return list(
        await q.pool.fetch(
            "SELECT id::text, drug_name_raw, quantity, dosage_instructions"
            " FROM prescription WHERE visit_id = $1::uuid ORDER BY created_at",
            q.visit_id,
        )
    )


async def test_da_thu_tien_luu_lai_giu_nguyen_dong_chi_doi_lieu_dung(q: Quay) -> None:
    rx, sl = await _don_da_thu(q)
    await _luu_don(
        q,
        [{"id": rx, "drug_name": "Thuốc đã thu", "quantity": sl, "dosage": "Sáng 1"}],
    )
    dong = await _cac_dong(q)
    assert [(d["id"], d["dosage_instructions"]) for d in dong] == [(rx, "Sáng 1")]


async def test_da_thu_tien_khong_xoa_dong_duoc(q: Quay) -> None:
    rx, _ = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="đã thu tiền"):
        await _luu_don(q, [])
    assert [d["id"] for d in await _cac_dong(q)] == [rx]


async def test_da_thu_tien_khong_doi_so_luong_duoc(q: Quay) -> None:
    rx, _ = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="đã thu tiền"):
        await _luu_don(
            q, [{"id": rx, "drug_name": "Thuốc đã thu", "quantity": "20 viên"}]
        )
    assert (await _cac_dong(q))[0]["quantity"] == "10 viên"


async def test_da_thu_tien_khong_them_thuoc_duoc(q: Quay) -> None:
    rx, sl = await _don_da_thu(q)
    with pytest.raises(ConflictError, match="không thêm thuốc"):
        await _luu_don(
            q,
            [
                {"id": rx, "drug_name": "Thuốc đã thu", "quantity": sl},
                {"id": None, "drug_name": "Thuốc thêm", "quantity": "5 viên"},
            ],
        )
    assert [d["id"] for d in await _cac_dong(q)] == [rx]


async def test_chua_thu_tien_van_thay_don_nhu_cu(q: Quay) -> None:
    rx = await _don(q, 10, ten="Nháp")
    await _luu_don(q, [{"id": None, "drug_name": "Thuốc khác", "quantity": "3 viên"}])
    dong = await _cac_dong(q)
    assert [d["drug_name_raw"] for d in dong] == ["Thuốc khác"]
    assert rx not in {d["id"] for d in dong}
