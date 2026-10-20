"""Audit FIN-003: invariant probe, expected RED before a command receipt fix."""

# ruff: noqa: F811 — imported pytest fixture follows this repository's convention.

from __future__ import annotations

import pytest

from clinicai.services.quay_thuoc_service import QuayThuocService
from tests.services.test_tien_thuoc_cp1_db import Quay, q  # noqa: F401
from tests.services.test_tien_thuoc_cp3_db import _dong_da_xac_dinh

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def test_retry_after_lost_response_does_not_duplicate_added_rx(
    q: Quay,
    monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    monkeypatch.setenv("CLINICAI_DRUG_PAYMENT_REQUIRES_INVENTORY", "0")
    _, drug = await _dong_da_xac_dinh(q, 10)
    payload = [{"drug_catalog_id": drug, "quantity": "5 viên"}]
    service = QuayThuocService(q.pool)
    # First call commits; its response is deliberately ignored, as if lost.
    await service.luu_dong_them(visit_id=q.visit_id, dong=payload, identity=q.thu_ngan)
    # The browser still has the same draft without IDs and retries it.
    await service.luu_dong_them(visit_id=q.visit_id, dong=payload, identity=q.thu_ngan)
    count = await q.pool.fetchval(
        "SELECT count(*) FROM prescription WHERE clinic_id=$1::uuid"
        " AND visit_id=$2::uuid AND nguon='QUAY' AND removed_at IS NULL",
        q.thu_ngan.clinic_id,
        q.visit_id,
    )
    assert count == 1, f"One retried intent produced {count} QUAY rows"
