"""Unit tests for the work-item state machine and its role gate (W4).

The dependency gates themselves are SQL and are covered by
supabase/tests/workflow_kernel.sql; what is pinned here is the pure part — which
commands are legal from which status, and which roles the Command API admits.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from clinicai.api.exceptions import NotFoundError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.api.v1.routers.work_items import _WORK_ITEM_GUARD
from clinicai.core.exceptions import SafetyGateError
from clinicai.services.work_item_service import (
    CANCELLED,
    COMPLETED,
    IN_PROGRESS,
    PENDING,
    SKIPPED,
    WorkItemService,
    is_terminal,
    resolve_transition,
)


class TestTransitions:
    def test_start_only_from_pending(self) -> None:
        allowed, result = resolve_transition("start")
        assert allowed == frozenset({PENDING})
        assert result == IN_PROGRESS

    def test_complete_requires_work_to_have_begun(self) -> None:
        # Completing straight out of PENDING would leave started_at empty and
        # make "how long did this take" unanswerable for every report.
        allowed, result = resolve_transition("complete")
        assert allowed == frozenset({IN_PROGRESS})
        assert result == COMPLETED

    @pytest.mark.parametrize(
        ("command", "expected"), [("skip", SKIPPED), ("cancel", CANCELLED)]
    )
    def test_skip_and_cancel_available_until_finished(
        self, command: str, expected: str
    ) -> None:
        allowed, result = resolve_transition(command)
        assert allowed == frozenset({PENDING, IN_PROGRESS})
        assert result == expected

    @pytest.mark.parametrize("status", [COMPLETED, SKIPPED, CANCELLED])
    def test_nothing_moves_a_finished_item(self, status: str) -> None:
        for command in ("start", "complete", "skip", "cancel"):
            allowed, _ = resolve_transition(command)
            assert status not in allowed

    def test_terminal_statuses(self) -> None:
        assert (
            is_terminal(COMPLETED) and is_terminal(SKIPPED) and is_terminal(CANCELLED)
        )
        assert not is_terminal(PENDING) and not is_terminal(IN_PROGRESS)

    @pytest.mark.parametrize(
        "command", ["", "START", "finish", "done", "complete ", "reopen"]
    )
    def test_unknown_commands_are_refused(self, command: str) -> None:
        with pytest.raises(ValueError):
            resolve_transition(command)


class TestRouterGuard:
    def test_every_working_role_may_reach_the_command_api(self) -> None:
        # The flow is worked by everybody; the node's own actor_roles is what
        # narrows each station, so the router must not narrow it first.
        #
        # DISPLAY và PARTNER nằm ngoài: một cái là tivi phòng chờ, một cái là
        # người NGOÀI phòng khám gửi kết quả vào. Cả hai đã bị
        # `get_current_identity` từ chối trước khi tới đây — bỏ chúng khỏi danh
        # sách này chỉ để bài kiểm nói đúng điều nó muốn nói ("mọi vai LÀM VIỆC
        # TRONG PHÒNG KHÁM"), chứ không phải để mở thêm gì.
        lam_viec = frozenset(ClinicRole) - {ClinicRole.DISPLAY, ClinicRole.PARTNER}
        assert _WORK_ITEM_GUARD.allowed_roles == lam_viec


@pytest.mark.asyncio
async def test_command_is_bound_to_identity_clinic_and_membership_role() -> None:
    """A staff member's membership in clinic B must not authorize clinic A.

    The command read is the ownership boundary.  It must bind both the active
    tenant selected by ``StaffIdentity`` and the role from that exact
    membership, rather than joining any clinic membership for the staff UUID.
    """
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)

    conn.fetchrow.side_effect = [
        {
            "id": "10000000-0000-4000-8000-000000000001",
            "status": PENDING,
            "version": 1,
            "node_code": "CHECK_IN",
            "clinic_id": "a0000000-0000-4000-8000-000000000001",
            "actor_roles": ["RECEPTION"],
            "membership_role": "RECEPTION",
            "node_name": "Tiếp nhận",
        },
        {"version": 2},
    ]
    conn.fetch.return_value = []
    identity = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Lễ tân A",
        department="DOCTOR",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )

    result = await WorkItemService(pool).issue(
        work_item_id="10000000-0000-4000-8000-000000000001",
        command="start",
        identity=identity,
        expected_version=1,
    )

    assert result["status"] == IN_PROGRESS
    lookup_sql, *lookup_args = conn.fetchrow.await_args_list[0].args
    normalised_sql = " ".join(lookup_sql.split())
    assert "m.clinic_id = $3::uuid" in normalised_sql
    assert "m.role = $4" in normalised_sql
    assert "w.clinic_id = $3::uuid" in normalised_sql
    assert "m.role AS membership_role" in normalised_sql
    assert lookup_args == [
        "10000000-0000-4000-8000-000000000001",
        identity.staff_id,
        identity.clinic_id,
        identity.role.value,
    ]

    # The immutable event records the verified membership role.
    event_args = conn.execute.await_args.args
    assert event_args[1] == identity.clinic_id
    assert event_args[7] == "RECEPTION"


@pytest.mark.asyncio
async def test_an_unassigned_node_cannot_be_commanded_by_any_role() -> None:
    """The schema defines an empty actor list as \"nobody yet\", not public."""
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)
    conn.fetchrow.return_value = {
        "id": "10000000-0000-4000-8000-000000000001",
        "status": PENDING,
        "version": 1,
        "node_code": "UNASSIGNED",
        "clinic_id": "a0000000-0000-4000-8000-000000000001",
        "actor_roles": [],
        "membership_role": "RECEPTION",
        "node_name": "Chưa phân công",
    }
    identity = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Lễ tân A",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )

    with pytest.raises(SafetyGateError, match="không phụ trách"):
        await WorkItemService(pool).issue(
            work_item_id="10000000-0000-4000-8000-000000000001",
            command="start",
            identity=identity,
        )

    conn.fetch.assert_not_awaited()
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocker_read_is_bound_to_identity_clinic_and_membership() -> None:
    """The diagnostic read must enforce the same tenant boundary as commands."""
    work_item_id = "10000000-0000-4000-8000-000000000001"
    identity = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Lễ tân A",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    pool = MagicMock()
    pool.fetch = AsyncMock(
        return_value=[
            {
                "scoped_work_item_id": work_item_id,
                "node_code": "TAKE_VITALS",
                "dependency_type": "FS",
            }
        ]
    )

    result = await WorkItemService(pool).blockers(
        work_item_id=work_item_id,
        phase="start",
        identity=identity,
    )

    assert result == [{"node_code": "TAKE_VITALS", "dependency_type": "FS"}]
    assert pool.fetch.await_args is not None
    sql, *args = pool.fetch.await_args.args
    normalised_sql = " ".join(sql.split())
    assert "w.clinic_id = $3::uuid" in normalised_sql
    assert "m.staff_id = $4::uuid" in normalised_sql
    assert "m.role = $5" in normalised_sql
    assert args == [
        work_item_id,
        "start",
        identity.clinic_id,
        identity.staff_id,
        identity.role.value,
    ]


@pytest.mark.asyncio
async def test_blocker_read_hides_work_item_outside_identity_scope() -> None:
    identity = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Lễ tân A",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    pool = MagicMock()
    pool.fetch = AsyncMock(return_value=[])

    with pytest.raises(NotFoundError, match="Không tìm thấy đầu việc"):
        await WorkItemService(pool).blockers(
            work_item_id="10000000-0000-4000-8000-000000000099",
            phase="complete",
            identity=identity,
        )


@pytest.mark.asyncio
async def test_authorized_work_item_with_open_gate_has_no_blockers() -> None:
    identity = StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Lễ tân A",
        department="RECEPTION",
        role=ClinicRole.RECEPTION,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )
    pool = MagicMock()
    pool.fetch = AsyncMock(
        return_value=[
            {
                "scoped_work_item_id": "10000000-0000-4000-8000-000000000001",
                "node_code": None,
                "dependency_type": None,
            }
        ]
    )

    assert (
        await WorkItemService(pool).blockers(
            work_item_id="10000000-0000-4000-8000-000000000001",
            phase="start",
            identity=identity,
        )
        == []
    )


class TestMienHuyCanLyDoVaBacSi:
    """Tuyền chốt 15/09/2026: huỷ/miễn một bước phải ghi lý do; dịch vụ không làm
    được thì BÁC SĨ quyết. Smoke Postgres chạy đủ đường vai; đây khoá hằng số và
    cửa lý do (chặn trước khi chạm database)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("command", ["skip", "cancel"])
    @pytest.mark.parametrize("reason", [None, "", "   "])
    async def test_thieu_ly_do_bi_chan_truoc_db(
        self, command: str, reason: str | None
    ) -> None:
        from clinicai.api.exceptions import ValidationError
        from clinicai.api.identity import ClinicRole, StaffIdentity
        from clinicai.services.work_item_service import WorkItemService

        x = "a0000000-0000-4000-8000-000000000001"
        identity = StaffIdentity(
            staff_id=x,
            auth_user_id=x,
            full_name="x",
            department="DOCTOR",
            role=ClinicRole.DOCTOR,
            clinic_id=x,
            location_id=x,
            location_name="CS",
        )
        with pytest.raises(ValidationError, match="lý do"):
            await WorkItemService(None).issue(
                work_item_id=x,
                command=command,  # type: ignore[arg-type]
                identity=identity,
                reason=reason,
            )

    def test_chi_bac_si_quyet_buoc_dich_vu(self) -> None:
        from clinicai.services.work_item_service import (
            LENH_CAN_LY_DO,
            NHOM_BUOC_DICH_VU,
            VAI_QUYET_DICH_VU,
        )

        assert LENH_CAN_LY_DO == {"skip", "cancel"}
        assert NHOM_BUOC_DICH_VU == {"dich_vu", "ket_qua"}
        assert VAI_QUYET_DICH_VU == {"DOCTOR", "ULTRASOUND_DOCTOR"}


# ── S0-5 (18/09/2026): nhật ký ghi VAI ĐÃ DÙNG để qua cửa, không phải vai
# tài khoản. Một người, tài khoản Điều dưỡng, hôm nay đứng thêm Lễ tân: bước
# Lễ tân phải ghi RECEPTION, bước Điều dưỡng ghi NURSE_ULTRASOUND; vai tài
# khoản vẫn giữ trong metadata để không mất dấu ai thật sự đã bấm.
def _pool_mot_buoc(actor_roles: list[str]) -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)
    conn.fetchrow.side_effect = [
        {
            "id": "10000000-0000-4000-8000-000000000001",
            "status": PENDING,
            "version": 1,
            "node_code": "CHECK_IN",
            "clinic_id": "a0000000-0000-4000-8000-000000000001",
            "actor_roles": actor_roles,
            "membership_role": "NURSE_ULTRASOUND",
            "node_name": "Bước thử",
            "flow_group": None,
        },
        {"version": 2},
    ]
    conn.fetch.return_value = []
    return pool, conn


def _dieu_duong_dung_le_tan() -> StaffIdentity:
    return StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000001",
        auth_user_id="30000000-0000-4000-8000-000000000001",
        full_name="Minh Thư",
        department="NURSE_ULTRASOUND",
        role=ClinicRole.NURSE_ULTRASOUND,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
        vai_theo_vi_tri=frozenset({ClinicRole.RECEPTION}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "actor_roles,vai_ghi",
    [(["RECEPTION"], "RECEPTION"), (["NURSE_ULTRASOUND"], "NURSE_ULTRASOUND")],
)
async def test_nhat_ky_ghi_vai_da_dung_de_qua_cua(
    actor_roles: list[str], vai_ghi: str
) -> None:
    import json

    pool, conn = _pool_mot_buoc(actor_roles)
    await WorkItemService(pool).issue(
        work_item_id="10000000-0000-4000-8000-000000000001",
        command="start",
        identity=_dieu_duong_dung_le_tan(),
        expected_version=1,
    )
    event_args = conn.execute.await_args.args
    assert event_args[7] == vai_ghi
    assert json.loads(event_args[9])["vai_tai_khoan"] == "NURSE_ULTRASOUND"


# ── Khu do LEGO quyết: "Việc cần xử lý" hỏi worklist.handle (27/09/2026) ─────


def _pool_khu_van_hanh(actor_roles: list[str], membership_role: str) -> MagicMock:
    pool = MagicMock()
    conn = AsyncMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = conn
    pool.acquire.return_value = acquire
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=None)
    transaction.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=transaction)
    conn.fetchrow.side_effect = [
        {
            "id": "10000000-0000-4000-8000-000000000009",
            "status": PENDING,
            "version": 1,
            "node_code": "OPS-FINANCIAL-RESOLUTION",
            "clinic_id": "a0000000-0000-4000-8000-000000000001",
            "actor_roles": actor_roles,
            "membership_role": membership_role,
            "node_name": "Đối soát tiền",
            "flow_group": "van_hanh",
            "workspace": "khu_van_hanh",
        },
        {"version": 2},
    ]
    conn.fetch.return_value = []
    return pool


def _danh_tinh(vai: ClinicRole) -> StaffIdentity:
    return StaffIdentity(
        staff_id="20000000-0000-4000-8000-000000000009",
        auth_user_id="30000000-0000-4000-8000-000000000009",
        full_name="Người thử",
        department=vai.value,
        role=vai,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


@pytest.mark.asyncio
async def test_viec_can_xu_ly_lego_tat_thi_vai_dung_cung_bi_chan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quản lý có tên trong actor_roles nhưng lego "Việc cần xử lý" đã thu → chặn."""
    monkeypatch.setattr(
        "clinicai.services.work_item_service.can", AsyncMock(return_value=False)
    )
    pool = _pool_khu_van_hanh(["MANAGEMENT", "CASHIER"], "MANAGEMENT")
    with pytest.raises(SafetyGateError, match="không có quyền"):
        await WorkItemService(pool).issue(
            work_item_id="10000000-0000-4000-8000-000000000009",
            command="start",
            identity=_danh_tinh(ClinicRole.MANAGEMENT),
        )


@pytest.mark.asyncio
async def test_viec_can_xu_ly_co_lego_thi_lam_duoc_du_vai_khong_co_ten(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lễ tân không có trong actor_roles (người dự phòng), nhưng có lego → làm được."""
    can = AsyncMock(return_value=True)
    monkeypatch.setattr("clinicai.services.work_item_service.can", can)
    pool = _pool_khu_van_hanh(["MANAGEMENT", "CASHIER"], "RECEPTION")
    ket = await WorkItemService(pool).issue(
        work_item_id="10000000-0000-4000-8000-000000000009",
        command="start",
        identity=_danh_tinh(ClinicRole.RECEPTION),
    )
    assert ket["status"] == IN_PROGRESS
    assert can.await_args is not None
    assert can.await_args.args[2] == "worklist.handle"


@pytest.mark.asyncio
async def test_doc_khu_van_hanh_hoi_quyen_ke_ca_quan_ly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cửa ĐỌC khu cũng hỏi lego — quản lý/trưởng ca không còn đi tắt theo vai."""
    from clinicai.api.v1.routers import work_items

    doi = AsyncMock(side_effect=SafetyGateError("Bạn không có quyền"))
    monkeypatch.setattr(work_items, "doi_quyen", doi)
    pool = MagicMock()
    acquire = AsyncMock()
    acquire.__aenter__.return_value = AsyncMock()
    pool.acquire.return_value = acquire
    with pytest.raises(SafetyGateError):
        await work_items.require_workspace_read_access(
            workspace="khu_van_hanh",
            identity=_danh_tinh(ClinicRole.MANAGEMENT),
            pool=pool,
        )
    assert doi.await_args is not None
    assert doi.await_args.args[2] == "worklist.handle"
