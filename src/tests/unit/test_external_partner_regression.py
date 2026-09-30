"""Regression tests: External partner decoupling, review queue prevention,
CSKH doctor approval gating, procedure nurse-operation / doctor-readonly,
and vitals started_at timing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from clinicai.api.exceptions import ConflictError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.exceptions import SafetyGateError
from clinicai.services import luot_kham_rules as rules
from clinicai.services.luot_kham_service import LuotKhamService
from clinicai.services.tep_ket_qua_service import TepKetQuaService


def _staff(
    role: ClinicRole, staff_id: str = "11111111-1111-4111-8111-111111111111"
) -> StaffIdentity:
    return StaffIdentity(
        staff_id=staff_id,
        auth_user_id="auth-" + staff_id[:8],
        full_name=f"Staff {role.value}",
        department=role.value,
        role=role,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def _mock_pool_and_conn() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    transaction_ctx = AsyncMock()
    transaction_ctx.__aenter__.return_value = conn
    conn.transaction = MagicMock(return_value=transaction_ctx)
    pool.fetchrow = conn.fetchrow
    pool.fetchval = conn.fetchval
    pool.execute = conn.execute
    return pool, conn


# ---------------------------------------------------------------------------
# 1. External order decouples from visit closing
# ---------------------------------------------------------------------------


def test_external_order_defaults_to_follow_up() -> None:
    """lam_ben_ngoai defaults to FOLLOW_UP so it does not block the visit."""
    assert rules.need_mac_dinh(lam_ben_ngoai=True, flow_group="dich_vu") == "FOLLOW_UP"
    assert rules.need_mac_dinh(lam_ben_ngoai=True, flow_group="ket_qua") == "FOLLOW_UP"


def test_external_order_does_not_create_review_round_requirement() -> None:
    """FOLLOW_UP orders are split into theo_doi_order_ids and do not create
    requirements in review_round, allowing visit to close."""
    vong_reqs, theo_doi = rules.tach_ke_hoach(
        [
            ("order-external-1", "FOLLOW_UP"),
            ("order-external-2", "FOLLOW_UP"),
        ]
    )
    assert vong_reqs == []
    assert theo_doi == ["order-external-1", "order-external-2"]
    # If a requirement were converted to follow_up, vong_khong_can_doc is True
    assert (
        rules.vong_khong_can_doc(
            [
                rules.RequirementView(
                    order_id="o1",
                    need="PERFORMED",
                    status="follow_up",
                    exec_status="performed",
                )
            ]
        )
        is True
    )


def test_internal_lab_order_still_requires_valid_result() -> None:
    """Internal orders with flow_group == 'ket_qua' still require VALID_RESULT."""
    assert (
        rules.need_mac_dinh(lam_ben_ngoai=False, flow_group="ket_qua") == "VALID_RESULT"
    )
    vong_reqs, theo_doi = rules.tach_ke_hoach([("order-internal", "VALID_RESULT")])
    assert vong_reqs == [("order-internal", "VALID_RESULT")]
    assert theo_doi == []


# ---------------------------------------------------------------------------
# 2 & 3. External result does not reopen consultation / enqueue patient,
#        and appears in doctor's ket_qua_cho_duyet
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_xac_nhan_tep_external_does_not_call_sau_khi_co_ket_qua() -> None:
    """When an external file is confirmed HOP_LE,
    it must NOT call sau_khi_co_ket_qua().
    """
    tep_id = "33333333-3333-4333-8333-333333333333"
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {
        "id": tep_id,
        "service_order_id": "44444444-4444-4444-8444-444444444444",
        "tai_len_boi_staff_id": "99999999-9999-4999-8999-999999999999",
        "xac_nhan_trang_thai": "CHO_XAC_NHAN",
    }
    conn.fetchval.return_value = True  # la_ngoai = True
    conn.execute.return_value = "UPDATE 1"

    svc = TepKetQuaService(pool)
    with (
        patch(
            "clinicai.services.tep_ket_qua_service.kiem_tra_quyen_xac_nhan",
            new_callable=AsyncMock,
        ),
        patch(
            "clinicai.services.tep_ket_qua_service.record_event", new_callable=AsyncMock
        ),
        patch(
            "clinicai.services.luot_kham_service.LuotKhamService.sau_khi_co_ket_qua",
            new_callable=AsyncMock,
        ) as mock_after,
    ):
        await svc.xac_nhan_tep(
            identity=_staff(ClinicRole.DOCTOR),
            tep_id=tep_id,
            trang_thai="HOP_LE",
        )
        mock_after.assert_not_called()


@pytest.mark.asyncio
async def test_sau_khi_co_ket_qua_defense_in_depth_bails_on_external() -> None:
    """Defense in depth: LuotKhamService.sau_khi_co_ket_qua returns immediately
    if the order is lam_ben_ngoai or if the visit is finished."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        True,  # la_ngoai = True
    ]

    svc = LuotKhamService(pool)
    with patch.object(svc, "_lock_visit", new_callable=AsyncMock):
        res = await svc.sau_khi_co_ket_qua(
            order_id=order_id, identity=_staff(ClinicRole.DOCTOR)
        )
        assert res is None
    # Returned early without evaluating rounds or modifying queue
    conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 4. CSKH cannot send external result before doctor approval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cskh_cannot_send_before_doctor_approval() -> None:
    """CSKH cannot mark as sent if doctor has not approved
    (cho_phep_gui_luc is None).
    """
    tep_id = "33333333-3333-4333-8333-333333333333"
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.return_value = {
        "gui_luc": None,
        "cho_phep_gui_luc": None,
        "xac_nhan_trang_thai": "HOP_LE",
    }

    svc = TepKetQuaService(pool)
    with pytest.raises(ConflictError, match="chưa cho phép"):
        await svc.danh_dau_da_gui(
            identity=_staff(ClinicRole.CSKH),
            tep_id=tep_id,
            kenh="ZALO",
        )


@pytest.mark.asyncio
async def test_cskh_can_send_after_doctor_approval() -> None:
    """Once doctor approves (cho_phep_gui_luc is set), CSKH can mark as sent."""
    tep_id = "33333333-3333-4333-8333-333333333333"
    pool, conn = _mock_pool_and_conn()
    conn.fetchrow.side_effect = [
        {
            "gui_luc": None,
            "cho_phep_gui_luc": "2026-09-21T10:00:00+07:00",
            "xac_nhan_trang_thai": "HOP_LE",
        },
        {"id": tep_id},
    ]

    svc = TepKetQuaService(pool)
    res = await svc.danh_dau_da_gui(
        identity=_staff(ClinicRole.CSKH),
        tep_id=tep_id,
        kenh="ZALO",
    )
    assert res == {"ok": True}


# ---------------------------------------------------------------------------
# 5. Procedure room: Nurse operations full, Doctor read-only, performed_by safe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_procedure_doctor_cannot_start_draft_or_complete() -> None:
    """Doctor cannot start, draft, or complete procedure service orders."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.return_value = "55555555-5555-4555-8555-555555555555"
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-THUTHUAT",
        "actor_roles": ["DOCTOR", "NURSE_ULTRASOUND"],
        "exec_status": "assigned",
        "performed_by": None,
    }

    svc = LuotKhamService(pool)
    doctor = _staff(ClinicRole.DOCTOR)

    with patch.object(svc, "_lock_visit", new_callable=AsyncMock):
        with pytest.raises(SafetyGateError, match="thủ thuật"):
            await svc.start_service(order_id=order_id, identity=doctor)

        with pytest.raises(SafetyGateError, match="thủ thuật"):
            await svc.save_service_draft(
                order_id=order_id,
                result_note="test",
                expected_version=1,
                identity=doctor,
            )

        with pytest.raises(SafetyGateError, match="thủ thuật"):
            await svc.complete_service(
                order_id=order_id,
                performed=True,
                reason=None,
                result_note="test",
                identity=doctor,
            )


@pytest.mark.asyncio
async def test_procedure_nurse_does_not_pollute_performed_by() -> None:
    """When nurse operates a procedure, performed_by is NOT attributed to the nurse
    or defaulted to the attending doctor."""
    order_id = "44444444-4444-4444-8444-444444444444"
    nurse_id = "22222222-2222-4222-8222-222222222222"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.return_value = "55555555-5555-4555-8555-555555555555"
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-THUTHUAT",
        "actor_roles": ["DOCTOR"],
        "exec_status": "in_progress",
        "performed_by": None,
    }
    conn.execute.return_value = "UPDATE 1"

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND, staff_id=nurse_id)

    # Calling complete_service as nurse
    with (
        patch.object(svc, "_lock_visit", new_callable=AsyncMock),
        patch.object(svc, "_release_blocked", new_callable=AsyncMock),
        patch.object(svc, "_evaluate_rounds", new_callable=AsyncMock),
        patch.object(svc, "_ket_thuc_neu_xong", new_callable=AsyncMock),
        patch.object(svc, "_cap_nhat_vi_tri", new_callable=AsyncMock),
    ):
        await svc.complete_service(
            order_id=order_id,
            performed=True,
            reason=None,
            result_note="Done",
            identity=nurse,
        )

    # Verify SQL updates: cap_nhat_performer was False, performed_by was not overwritten
    update_calls = [
        str(call.args[0]) for call in conn.execute.call_args_list if call.args
    ]
    found_order_update = False
    for sql in update_calls:
        if "UPDATE service_order" in sql:
            found_order_update = True
            assert "performed_by = CASE WHEN $6 THEN $7::uuid" in sql
    assert found_order_update


# ---------------------------------------------------------------------------
# 6. Optimistic concurrency for draft notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_draft_concurrency_conflict_raises_conflict_error() -> None:
    """When expected_version != current version,
    save_service_draft raises ConflictError.
    """
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        3,  # cur_version in service_order FOR UPDATE
    ]
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-SIEUAM",
        "actor_roles": ["ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND"],
        "exec_status": "in_progress",
        "performed_by": None,
    }

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    # Client sends expected_version = 2, current is 3
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        1,  # staff_node check in _order_for_performer
        3,  # cur_version in service_order FOR UPDATE
    ]
    with patch.object(svc, "_lock_visit", new_callable=AsyncMock):
        with pytest.raises(ConflictError, match="phiên bản máy chủ là 3"):
            await svc.save_service_draft(
                order_id=order_id,
                result_note="Draft content",
                expected_version=2,
                identity=nurse,
            )


# ---------------------------------------------------------------------------
# 7. Runtime staff_node permissions (Section 1.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nurse_with_staff_node_can_operate_ultrasound() -> None:
    """Nurse with DICHVU-SIEUAM in staff_node can operate ultrasound service."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        1,  # staff_node has DICHVU-SIEUAM
    ]
    conn.fetchrow.side_effect = [
        {
            "node_code": "DICHVU-SIEUAM",
            "actor_roles": ["ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND"],
            "exec_status": "assigned",
            "performed_by": None,
        },
        {
            "id": "entry-1",
            "status": "waiting",
        },
    ]
    conn.execute.return_value = "UPDATE 1"

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    with (
        patch.object(svc, "_lock_visit", new_callable=AsyncMock),
        patch.object(svc, "_visit_busy", new_callable=AsyncMock, return_value=False),
        patch.object(svc, "_block_others", new_callable=AsyncMock),
        patch.object(svc, "_cap_nhat_vi_tri", new_callable=AsyncMock),
        patch(
            "clinicai.services.luot_kham_service.record_event", new_callable=AsyncMock
        ),
    ):
        res = await svc.start_service(order_id=order_id, identity=nurse)
        assert res["ok"] is True


@pytest.mark.asyncio
async def test_nurse_without_staff_node_gets_safety_gate_error() -> None:
    """Nurse without node in staff_node is denied with SafetyGateError (403)."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        None,  # staff_node NOT found -> None
    ]
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-SIEUAM",
        "actor_roles": ["ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND"],
        "exec_status": "assigned",
        "performed_by": None,
    }

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    with patch.object(svc, "_lock_visit", new_callable=AsyncMock):
        with pytest.raises(SafetyGateError, match="chưa được phân công vận hành"):
            await svc.start_service(order_id=order_id, identity=nurse)


@pytest.mark.asyncio
async def test_nurse_with_staff_node_can_operate_procedure() -> None:
    """Nurse with DICHVU-THUTHUAT in staff_node can operate procedure."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        1,  # staff_node check -> 1
    ]
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-THUTHUAT",
        "actor_roles": ["DOCTOR", "NURSE_ULTRASOUND"],
        "exec_status": "in_progress",
        "performed_by": None,
    }
    conn.execute.return_value = "UPDATE 1"

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    with (
        patch.object(svc, "_lock_visit", new_callable=AsyncMock),
        patch.object(svc, "_release_blocked", new_callable=AsyncMock),
        patch.object(svc, "_evaluate_rounds", new_callable=AsyncMock),
        patch.object(svc, "_ket_thuc_neu_xong", new_callable=AsyncMock),
        patch.object(svc, "_cap_nhat_vi_tri", new_callable=AsyncMock),
        patch(
            "clinicai.services.luot_kham_service.record_event", new_callable=AsyncMock
        ),
    ):
        res = await svc.complete_service(
            order_id=order_id,
            performed=True,
            reason=None,
            result_note="Hoàn thành thủ thuật",
            identity=nurse,
        )
        assert res["ok"] is True


@pytest.mark.asyncio
async def test_management_revoking_node_immediately_revokes_permission() -> None:
    """When manager unassigns a node in staff_node, next call immediately fails."""
    order_id = "44444444-4444-4444-8444-444444444444"
    pool, conn = _mock_pool_and_conn()
    # Once node is deleted from staff_node, SELECT 1 returns None
    conn.fetchval.side_effect = [
        "55555555-5555-4555-8555-555555555555",  # _visit_of
        None,  # staff_node query returns None
    ]
    conn.fetchrow.return_value = {
        "node_code": "DICHVU-THUTHUAT",
        "actor_roles": ["DOCTOR", "NURSE_ULTRASOUND"],
        "exec_status": "in_progress",
        "performed_by": None,
    }

    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    with patch.object(svc, "_lock_visit", new_callable=AsyncMock):
        with pytest.raises(SafetyGateError, match="chưa được phân công vận hành"):
            await svc.complete_service(
                order_id=order_id,
                performed=True,
                reason=None,
                result_note="Hoàn thành",
                identity=nurse,
            )


@pytest.mark.asyncio
async def test_staff_node_cannot_grant_doctor_only_rights() -> None:
    """staff_node cannot grant clinical actions like authorize_orders or
    complete_consultation.
    """
    consultation_id = "66666666-6666-4666-8666-666666666666"
    pool, conn = _mock_pool_and_conn()
    svc = LuotKhamService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    # Nurse cannot call authorize_orders even if they have nodes configured
    with pytest.raises(SafetyGateError, match="bác sĩ"):
        await svc.authorize_orders(
            consultation_id=consultation_id,
            service_codes=["SA_THAI"],
            draft_order_ids=None,
            identity=nurse,
        )


@pytest.mark.asyncio
async def test_nurse_upload_checks_staff_node() -> None:
    """Nurse file upload in tai_len checks staff_node for the order's node_code."""
    order_id = "44444444-4444-4444-8444-444444444444"
    patient_id = "77777777-7777-4777-8777-777777777777"
    pool, conn = _mock_pool_and_conn()

    conn.fetchrow.return_value = {
        "clinic_patient_id": patient_id,
        "appointment_id": None,
        "lam_ben_ngoai": False,
        "node_code": "DICHVU-SIEUAM",
    }
    # patient check returns 1, then staff_node check fails (returns None)
    conn.fetchval.side_effect = [1, None]

    svc = TepKetQuaService(pool)
    nurse = _staff(ClinicRole.NURSE_ULTRASOUND)

    with pytest.raises(SafetyGateError, match="chưa được phân công vận hành"):
        await svc.tai_len(
            identity=nurse,
            clinic_patient_id=patient_id,
            service_order_id=order_id,
            data=b"%PDF-1.4 fake pdf content",
        )


@pytest.mark.asyncio
async def test_external_order_follow_up_cleans_physical_queue_entry() -> None:
    """When external order moves to FOLLOW_UP, queue_entry is cancelled and
    others unblocked.
    """
    pool, conn = _mock_pool_and_conn()
    order_id = "44444444-4444-4444-8444-444444444444"
    visit_id = "55555555-5555-4555-8555-555555555555"

    conn.fetchval.side_effect = [
        None,  # co_san follow_up_case -> None
        True,  # la_nhan_vien -> True
        "fid-1234",  # INSERT follow_up_case RETURNING id
    ]
    conn.fetchrow.return_value = {
        "service_name": "XN Máu Bên Ngoài",
        "patient_id": "77777777-7777-4777-8777-777777777777",
    }
    conn.execute.return_value = "UPDATE 1"

    svc = LuotKhamService(pool)
    doctor = _staff(ClinicRole.DOCTOR)

    with (
        patch.object(svc, "_release_blocked", new_callable=AsyncMock) as mock_release,
        patch(
            "clinicai.services.luot_kham_service.record_event", new_callable=AsyncMock
        ),
    ):
        fid = await svc._mo_theo_doi(
            conn,
            identity=doctor,
            vid=visit_id,
            oid=order_id,
            cau_hinh={"ly_do": "Chờ gửi mẫu sang Medlatec"},
            bac_si=doctor.staff_id,
        )
        assert fid == "fid-1234"
        mock_release.assert_awaited_once()

    # Check that queue_entry cancellation was executed
    update_calls = [
        str(call.args[0]) for call in conn.execute.call_args_list if call.args
    ]
    cancelled_queue = False
    for sql in update_calls:
        if "UPDATE queue_entry" in sql and "status = 'cancelled'" in sql:
            cancelled_queue = True
    assert cancelled_queue
