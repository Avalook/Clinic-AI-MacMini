"""Đóng một việc chăm sóc khách hàng (B.4).

Trước B.4 nút "Đã gọi" chỉ giấu dòng trong trình duyệt. Giờ nó ghi xuống, nên
những thứ trước đây không thể sai thì bây giờ có thể: ghi nhầm phòng khám, ghi
đè mất ghi chú cũ, và chép lời bệnh nhân vào sổ audit.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from clinicai.api.exceptions import NotFoundError, ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.services.cskh_service import RESOLUTIONS, CskhService

CLINIC_ID = str(uuid4())
OTHER_CLINIC_ID = str(uuid4())
STAFF_ID = str(uuid4())
ACTION_ID = str(uuid4())


def _cskh(clinic_id: str = CLINIC_ID) -> StaffIdentity:
    return StaffIdentity(
        staff_id=STAFF_ID,
        auth_user_id=str(uuid4()),
        full_name="Nguyễn Thị CSKH",
        department="CSKH",
        role=ClinicRole.CSKH,
        clinic_id=clinic_id,
    )


def _pool() -> tuple[MagicMock, AsyncMock]:
    pool = MagicMock()
    conn = AsyncMock()
    acquire_ctx = AsyncMock()
    acquire_ctx.__aenter__.return_value = conn
    pool.acquire.return_value = acquire_ctx
    transaction_ctx = AsyncMock()
    conn.transaction = MagicMock(return_value=transaction_ctx)
    return pool, conn


@pytest.mark.asyncio
async def test_outcome_vocabulary_is_closed() -> None:
    # Bảng lọc việc đang chờ theo nhãn trạng thái. Một khoá lạ lọt qua sẽ ghi
    # được một trạng thái thứ ba mà bộ lọc không biết — việc biến mất khỏi cả
    # hai danh sách.
    pool, conn = _pool()

    with pytest.raises(ValidationError):
        await CskhService(pool).resolve_action(
            action_id=ACTION_ID,
            outcome="done",
            note=None,
            identity=_cskh(),
        )

    conn.fetchrow.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_is_tenant_scoped_and_locks_the_row() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = None

    with pytest.raises(NotFoundError):
        await CskhService(pool).resolve_action(
            action_id=ACTION_ID,
            outcome="called",
            note=None,
            identity=_cskh(),
        )

    sql, action_id, clinic_id = conn.fetchrow.await_args.args
    assert "clinic_id = $2::uuid" in sql
    assert "FOR UPDATE" in sql
    assert (action_id, clinic_id) == (ACTION_ID, CLINIC_ID)
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_work_item_from_another_clinic_is_simply_not_found() -> None:
    # Cùng một câu trả lời cho "không tồn tại" và "của phòng khám khác": khác
    # nhau thì mã việc trở thành một máy dò xem phòng khám bên cạnh có gì.
    pool, conn = _pool()
    conn.fetchrow.return_value = None

    with pytest.raises(NotFoundError, match="Không tìm thấy việc CSKH"):
        await CskhService(pool).resolve_action(
            action_id=ACTION_ID,
            outcome="called",
            note=None,
            identity=_cskh(OTHER_CLINIC_ID),
        )

    assert conn.fetchrow.await_args.args[2] == OTHER_CLINIC_ID


@pytest.mark.asyncio
async def test_double_click_changes_nothing_and_says_so() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": RESOLUTIONS["called"]}

    outcome = await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="called",
        note=None,
        identity=_cskh(),
    )

    assert outcome.changed is False
    assert outcome.status == RESOLUTIONS["called"]
    conn.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_called_then_closed_is_progress_not_a_double_click() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": RESOLUTIONS["called"]}

    outcome = await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="closed",
        note=None,
        identity=_cskh(),
    )

    assert outcome.changed is True
    assert outcome.status == RESOLUTIONS["closed"]
    assert "UPDATE cskh_action" in conn.execute.await_args_list[0].args[0]


@pytest.mark.asyncio
async def test_repeating_an_outcome_with_a_new_note_still_records_it() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": RESOLUTIONS["called"]}

    outcome = await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="called",
        note="Gọi lần 2, hẹn gọi lại chiều mai",
        identity=_cskh(),
    )

    assert outcome.changed is True
    update_sql, *args = conn.execute.await_args_list[0].args
    assert "clinic_id = $5::uuid" in update_sql
    assert args[2] == "Gọi lần 2, hẹn gọi lại chiều mai"
    assert args[4] == CLINIC_ID


@pytest.mark.asyncio
async def test_an_empty_note_never_erases_the_previous_one() -> None:
    # COALESCE giữ ghi chú cũ khi lần này không có gì mới. Truyền "" xuống thay
    # vì NULL sẽ xoá sạch cái người trực ca trước đã viết.
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": "Mới"}

    await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="closed",
        note="   ",
        identity=_cskh(),
    )

    update_sql, *args = conn.execute.await_args_list[0].args
    assert "result_text = COALESCE($3, result_text)" in update_sql
    assert args[2] is None


@pytest.mark.asyncio
async def test_the_audit_event_points_at_the_row_instead_of_copying_it() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": "Mới"}
    note = "BN nói đang điều trị ở nơi khác, không tái khám"

    await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="closed",
        note=note,
        identity=_cskh(),
    )

    audit_sql, *audit_args = conn.execute.await_args_list[1].args
    assert "INSERT INTO event_log" in audit_sql
    assert json.loads(audit_args[4]) == {
        "id": ACTION_ID,
        "status": RESOLUTIONS["closed"],
    }
    # Ghi chú có thể là lời bệnh nhân kể về bệnh của họ. Nó ở lại trong hàng mà
    # phòng khám đọc, không vào sổ sự kiện.
    assert note not in audit_args[4]
    assert audit_args[0] == CLINIC_ID
    assert audit_args[-1] == STAFF_ID


@pytest.mark.asyncio
async def test_a_very_long_note_is_truncated_rather_than_rejected() -> None:
    pool, conn = _pool()
    conn.fetchrow.return_value = {"id": ACTION_ID, "status": "Mới"}

    await CskhService(pool).resolve_action(
        action_id=ACTION_ID,
        outcome="called",
        note="x" * 5000,
        identity=_cskh(),
    )

    args = conn.execute.await_args_list[0].args
    assert len(args[3]) == 2000
