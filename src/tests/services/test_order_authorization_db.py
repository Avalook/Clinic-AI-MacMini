"""Doctor authorization binds exact drafts to their active consultation."""

from pathlib import Path
from typing import Any

import pytest

from clinicai.core.exceptions import SafetyGateError
from clinicai.services.luot_kham_service import LuotKhamConflictError
from tests.goi_mau_cu import ve_goi_mau_cu
from tests.services.test_luot_kham_service_db import (
    KichBan,
    _cua,
    _vao_kham,
)

pytest_plugins = ["tests.services.test_luot_kham_service_db"]
pytestmark = [pytest.mark.db, pytest.mark.asyncio]


async def _draft(case: KichBan) -> tuple[str, dict[str, Any]]:
    consultation = await _vao_kham(case)
    draft = await case.svc.propose_orders(
        consultation_id=consultation,
        service_codes=[case.ma_sa],
        identity=case.thu_ky,
    )
    return consultation, draft


async def test_other_doctor_cannot_authorize(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    with pytest.raises(SafetyGateError):
        await kb.svc.authorize_orders(
            consultation_id=consultation,
            service_codes=None,
            draft_order_ids=draft["order_ids"],
            expected_versions={draft["order_ids"][0]: 1},
            identity=kb.bac_si_2,
        )


@pytest.mark.parametrize("versions", [None, {}, {"unused": 1}])
async def test_draft_approval_requires_exact_versions(
    kb: KichBan, versions: dict[str, Any] | None
) -> None:
    consultation, draft = await _draft(kb)
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.authorize_orders(
            consultation_id=consultation,
            service_codes=None,
            draft_order_ids=draft["order_ids"],
            expected_versions=versions,
            identity=kb.bac_si,
        )


async def test_stale_draft_rejected_atomically(kb: KichBan) -> None:
    consultation = await _vao_kham(kb)
    draft = await kb.svc.propose_orders(
        consultation_id=consultation,
        service_codes=[kb.ma_sa, kb.ma_mau],
        identity=kb.thu_ky,
    )
    first, second = draft["order_ids"]
    await kb.pool.execute(
        "UPDATE service_order SET version = 2 WHERE id = $1::uuid", second
    )
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.authorize_orders(
            consultation_id=consultation,
            service_codes=None,
            draft_order_ids=[first, second],
            expected_versions={first: 1, second: 1},
            identity=kb.bac_si,
        )
    statuses = await kb.pool.fetch(
        "SELECT exec_status FROM service_order WHERE id = ANY($1::uuid[])",
        draft["order_ids"],
    )
    assert {row["exec_status"] for row in statuses} == {"draft"}


async def test_approval_retries_and_does_not_finalize(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    assert draft["versions"] == {draft["order_ids"][0]: 1}
    args = dict(
        consultation_id=consultation,
        service_codes=None,
        draft_order_ids=draft["order_ids"],
        expected_versions=draft["versions"],
        identity=kb.bac_si,
        idempotency_key="authorization-retry",
    )
    first = await kb.svc.authorize_orders(**args)
    assert await kb.svc.authorize_orders(**args) == first
    assert (
        await kb.pool.fetchval(
            "SELECT status FROM visit WHERE visit_id = $1::uuid", kb.visit_id
        )
        == "OPEN"
    )


async def test_reception_and_service_roles_do_not_see_drafts(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    await ve_goi_mau_cu(
        kb.pool, kb.le_tan, kb.truong_ca, kb.bs_sieu_am
    )  # gói lego cũ (mở full lego 30/09)
    for identity in [kb.le_tan, kb.truong_ca, kb.bs_sieu_am]:
        visit = _cua(await kb.svc.bang(identity=identity), kb.visit_id)
        assert visit["chi_dinh"] == []
    # 29/09/2026: ĐD/TKYK trọn quyền (Tuyền) — điều dưỡng thấy nháp như bác sĩ.
    assert (
        len(_cua(await kb.svc.bang(identity=kb.dieu_duong), kb.visit_id)["chi_dinh"])
        == 1
    )
    # Thư ký chỉ thấy lượt của bác sĩ mình phụ trách (luật 15/09).
    await kb.pool.execute(
        "INSERT INTO thu_ky_bac_si (clinic_id, thu_ky_staff_id, bac_si_staff_id)"
        " VALUES ($1::uuid, $2::uuid, $3::uuid) ON CONFLICT DO NOTHING",
        kb.bac_si.clinic_id,
        kb.thu_ky.staff_id,
        kb.bac_si.staff_id,
    )
    assert (
        len(_cua(await kb.svc.bang(identity=kb.thu_ky), kb.visit_id)["chi_dinh"]) == 1
    )
    await kb.svc.authorize_orders(
        consultation_id=consultation,
        service_codes=None,
        draft_order_ids=draft["order_ids"],
        expected_versions={draft["order_ids"][0]: 1},
        identity=kb.bac_si,
    )
    nurse = _cua(await kb.svc.bang(identity=kb.dieu_duong), kb.visit_id)
    # Duyệt xong điều phối tự xếp phòng nên có thể đã là "assigned".
    assert nurse["chi_dinh"][0]["trang_thai"] in {"authorized", "assigned"}


async def test_inactive_doctor_cannot_authorize(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    await kb.pool.execute(
        "UPDATE staff SET is_active = false WHERE id = $1::uuid", kb.bac_si.staff_id
    )
    with pytest.raises(SafetyGateError):
        await kb.svc.authorize_orders(
            consultation_id=consultation,
            service_codes=None,
            draft_order_ids=draft["order_ids"],
            expected_versions={draft["order_ids"][0]: 1},
            identity=kb.bac_si,
        )


async def test_other_consultation_draft_cannot_be_approved(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    other = await kb.pool.fetchval(
        "INSERT INTO consultation (clinic_id, visit_id, round_no, kind, status,"
        " doctor_staff_id) VALUES ($1::uuid, $2::uuid, 2, 'REVIEW', 'queued',"
        " $3::uuid) RETURNING id::text",
        kb.bac_si.clinic_id,
        kb.visit_id,
        kb.bac_si.staff_id,
    )
    await kb.pool.execute(
        "UPDATE service_order SET consultation_id = $1::uuid WHERE id = $2::uuid",
        other,
        draft["order_ids"][0],
    )
    with pytest.raises(LuotKhamConflictError):
        await kb.svc.authorize_orders(
            consultation_id=consultation,
            service_codes=None,
            draft_order_ids=draft["order_ids"],
            expected_versions={draft["order_ids"][0]: 1},
            identity=kb.bac_si,
        )


async def test_realtime_rls_hides_unapproved_orders(kb: KichBan) -> None:
    consultation, draft = await _draft(kb)
    approved = await kb.svc.authorize_orders(
        consultation_id=consultation,
        service_codes=[kb.ma_mau],
        draft_order_ids=None,
        identity=kb.bac_si,
    )
    migration = (
        Path(__file__).resolve().parents[3]
        / "supabase/migrations/20260915000004_service_order_draft_visibility.sql"
    )
    async with kb.pool.acquire() as conn, conn.transaction():
        exists = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'"
            " AND tablename = 'service_order'"
            " AND policyname = 'service_order_draft_visibility')"
        )
        if not exists:
            await conn.execute(migration.read_text())
        for identity in [kb.dieu_duong, kb.le_tan, kb.bac_si, kb.thu_ky]:
            await conn.execute(
                "INSERT INTO auth.users (id) VALUES ($1::uuid)", identity.auth_user_id
            )
            await conn.execute(
                "UPDATE staff SET auth_user_id = $1::uuid WHERE id = $2::uuid",
                identity.auth_user_id,
                identity.staff_id,
            )
            await conn.execute(
                "SELECT set_config('request.jwt.claim.sub', $1, true)",
                identity.auth_user_id,
            )
            await conn.execute("SET LOCAL ROLE authenticated")
            rows = await conn.fetch(
                "SELECT id::text AS id FROM service_order WHERE visit_id = $1::uuid",
                kb.visit_id,
            )
            await conn.execute("RESET ROLE")
            expected = set(approved["order_ids"])
            if identity in [kb.bac_si, kb.thu_ky]:
                expected.update(draft["order_ids"])
            assert {row["id"] for row in rows} == expected
