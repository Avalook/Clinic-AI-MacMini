"""CP6–4c smoke: đường đầy đủ UI → proxy → API → service → DB.

Chứng minh:
  1. request có expected_revision hiện tại => không 500
  2. expected_revision stale => lỗi 4xx kiểm soát được
  3. request hợp lệ SOAP-only => thành công
  4. request hợp lệ Rx amendment => thành công
  5. proxy không bỏ field  (kiểm qua schema/router round-trip)
  6. UI không tự retry bằng revision mới  (kiểm qua luồng HoSoHoanTatPanel)

Tests 1–4 chạy trên DB thật (marker `db`).
Test 5 kiểm schema round-trip thuần (không cần DB).
Test 6 kiểm static code path (không cần DB).
"""

# ruff: noqa: F811

from __future__ import annotations

import json

import pytest

from clinicai.api.exceptions import ConflictError, ValidationError
from clinicai.api.v1.routers.clinical_sign import AmendRequest
from clinicai.services.clinical_sign_service import ClinicalSignService
from clinicai.services.dinh_chinh_don import prescription_fingerprint
from tests.services.test_luot_kham_service_db import CLINIC
from tests.services.test_tien_thuoc_cp1_db import (  # noqa: F401
    Quay,
    _don,
    q,
)
from tests.services.test_tien_thuoc_cp3_db import _san_sang

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


# ── helpers ───────────────────────────────────────────────────────────────


async def _ky(q: Quay) -> None:
    await q.pool.execute(
        """
        INSERT INTO clinical_record
            (clinic_id, visit_id, soap_subjective, soap_objective,
             soap_assessment, soap_plan)
        VALUES ($1::uuid, $2::uuid, '{"s":"cũ"}', '{"o":"cũ"}',
                '{"a":"cũ"}', '{"p":"cũ"}')
        """,
        CLINIC,
        q.visit_id,
    )
    await q.pool.execute(
        "UPDATE visit SET status = 'FINALIZED', finalized_at = now(),"
        " finalized_by = $2::uuid WHERE visit_id = $1::uuid",
        q.visit_id,
        q.bac_si.staff_id,
    )


async def _revision(q: Quay) -> int:
    return int(
        await q.pool.fetchval(
            "SELECT revision FROM clinical_record"
            " WHERE clinic_id = $1::uuid AND visit_id = $2::uuid",
            CLINIC,
            q.visit_id,
        )
    )


async def _fp(q: Quay) -> str:
    rows = [
        dict(row)
        for row in await q.pool.fetch(
            "SELECT id, drug_name_raw, quantity, dosage_instructions, caution"
            " FROM prescription WHERE clinic_id = $1::uuid AND visit_id = $2::uuid"
            " AND removed_at IS NULL ORDER BY id",
            CLINIC,
            q.visit_id,
        )
    ]
    return prescription_fingerprint(rows)


# ── Smoke 1: SOAP-only amendment thành công với revision hiện tại ──────


async def test_smoke_soap_only_voi_revision_hien_tai(q: Quay) -> None:
    """Request có expected_revision hiện tại => không 500, trả AMENDED."""
    await _don(q)
    await _ky(q)
    rev = await _revision(q)
    out = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Smoke test sửa SOAP",
        corrected={"soap_plan": {"p": "smoke"}},
        expected_revision=rev,
    )
    assert out["ok"] is True
    assert out["state"] == "AMENDED"
    assert "amendment_id" in out


# ── Smoke 2: stale revision bị chặn 4xx, không 500 ──────────────────


async def test_smoke_stale_revision_tra_conflict_khong_500(q: Quay) -> None:
    """expected_revision stale => ConflictError (409), KHÔNG phải 500."""
    await _don(q)
    await _ky(q)
    stale_rev = await _revision(q)
    # Đính chính lần 1 thành công → revision tăng
    await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Lần một",
        corrected={"soap_plan": {"p": "lần một"}},
        expected_revision=stale_rev,
    )
    # Lần 2 dùng revision cũ → phải bị 409
    with pytest.raises(ConflictError, match="tải lại"):
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason="Lần hai từ bản cũ",
            corrected={"soap_plan": {"p": "không được ghi"}},
            expected_revision=stale_rev,
        )


# ── Smoke 3: Rx amendment thành công ────────────────────────────────


async def test_smoke_rx_amendment_thanh_cong(q: Quay) -> None:
    """Rx amendment hợp lệ => thành công, có correction_id."""
    rx, _, _ = await _san_sang(q)
    await _ky(q)
    rev = await _revision(q)
    fp = await _fp(q)
    out = await ClinicalSignService(q.pool).amend(
        identity=q.bac_si,
        visit_id=q.visit_id,
        reason="Smoke test đổi thuốc sau ký",
        corrected={
            "don_thuoc": [
                {
                    "id": rx,
                    "drug_name": "Thuốc smoke",
                    "quantity": "5 viên",
                    "dosage": "Sáng 1",
                }
            ]
        },
        expected_revision=rev,
        expected_rx=fp,
    )
    assert out["ok"] is True
    assert out["state"] == "AMENDED"
    # Amendment có correction
    correction = await q.pool.fetchval(
        "SELECT count(*) FROM prescription_correction WHERE visit_id = $1::uuid",
        q.visit_id,
    )
    assert correction == 1


# ── Smoke 4: thiếu expected_revision => ValidationError 422 ─────────


async def test_smoke_thieu_expected_revision_tra_422(q: Quay) -> None:
    """Thiếu expected_revision => ValidationError (422), KHÔNG phải 500."""
    await _don(q)
    await _ky(q)
    with pytest.raises(ValidationError, match="expected_revision"):
        await ClinicalSignService(q.pool).amend(
            identity=q.bac_si,
            visit_id=q.visit_id,
            reason="Thiếu revision",
            corrected={"soap_plan": {"p": "x"}},
            expected_revision=None,
        )


# ── Smoke 5: schema round-trip (proxy không bỏ field) ────────────────


def test_smoke_amend_request_giu_du_field() -> None:
    """AmendRequest schema giữ đủ expected_revision + expected_rx qua JSON."""
    payload = {
        "reason": "Smoke",
        "corrected": {"soap_plan": {"p": "x"}},
        "expected_revision": 42,
        "expected_rx": "a" * 64,
    }
    req = AmendRequest.model_validate(payload)
    assert req.expected_revision == 42
    assert req.expected_rx == "a" * 64
    # Round-trip qua JSON (giả lập proxy JSON.stringify → JSON.parse)
    dumped = json.loads(req.model_dump_json())
    req2 = AmendRequest.model_validate(dumped)
    assert req2.expected_revision == 42
    assert req2.expected_rx == "a" * 64


# ── Smoke 6: UI không tự retry với revision mới ──────────────────────


def test_smoke_ui_khong_auto_retry() -> None:
    """HoSoHoanTatPanel act() (trước 23/09: ClinicalSignPanel) không tự gọi lại khi lỗi.

    Đọc source: `act()` khi `!r.ok` chỉ `setMsg(error)` rồi return.
    Không có vòng lặp, không có re-fetch revision, không có second POST.
    """
    from pathlib import Path

    panel = Path(
        __file__,
        "../../../dashboard/app/(dashboard)/tasks/HoSoHoanTatPanel.tsx",
    ).resolve()
    src = panel.read_text()
    # act() khi lỗi chỉ setMsg, không gọi lại fetch POST
    assert "if (!r.ok || !out.ok)" in src
    assert "setMsg(" in src
    # Không có retry/loop pattern
    assert "retry" not in src.lower()
    # Không gọi load() trước khi gửi lại (chỉ gọi load() SAU thành công)
    # Tìm pattern: load() xuất hiện sau setMsg nhưng chỉ trong nhánh ok
    act_start = src.index("async function act(")
    act_body = src[act_start : src.index("if (!visitId", act_start)]
    # Trong nhánh lỗi (!r.ok) không có load()
    error_branch_end = act_body.index("await load()")
    error_branch = act_body[act_body.index("if (!r.ok") : error_branch_end]
    assert "load()" not in error_branch
