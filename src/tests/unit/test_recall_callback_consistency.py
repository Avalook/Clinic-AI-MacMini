"""Regression tests for recall/callback state consistency.

These rules sit at the backend boundary because the dashboard must not be able
to make a future job actionable, close only half of an operation, or claim a
result file was delivered when no delivered file exists.
"""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import pytest

from clinicai.api.exceptions import ValidationError
from clinicai.api.identity import ClinicRole, StaffIdentity
from clinicai.core.clock import CLINIC_TZ
from clinicai.services.recall_job_service import RecallJobService
from clinicai.services.tuong_tac_cskh_service import (
    GuiZaloService,
    HenGoiLaiService,
    TuongTacCskhService,
)


def _identity() -> StaffIdentity:
    return StaffIdentity(
        staff_id="d0000000-0000-4000-8000-000000000001",
        auth_user_id="u1",
        full_name="CSKH kiểm thử",
        department=ClinicRole.CSKH.value,
        role=ClinicRole.CSKH,
        clinic_id="a0000000-0000-4000-8000-000000000001",
        location_id="fe45d9f6-0d67-428d-9d16-5ba5c36befff",
        location_name="Kim Ngưu",
    )


def test_view_uses_same_effective_result_timestamp_as_services() -> None:
    migration = Path(
        "supabase/migrations/20260811000001_align_kq_chua_gui_timestamp.sql"
    ).read_text(encoding="utf-8")

    effective = "COALESCE(r.reviewed_at, r.result_received_at, r.created_at)"
    assert effective in migration
    assert "occurrences <> 1" in migration
    assert "security_invoker = true" in migration


class _Transaction:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> None:
        self.entered = True

    async def __aexit__(self, *_args: Any) -> bool:
        self.exited = True
        return False


class _Conn:
    """Small scripted asyncpg connection that records SQL and transactions."""

    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []
        self.transactions: list[_Transaction] = []

    def _next(self) -> Any:
        return self.results.pop(0) if self.results else None

    async def fetch(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetch", sql, args))
        return self._next() or []

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", sql, args))
        return self._next()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.calls.append(("fetchval", sql, args))
        return self._next()

    async def execute(self, sql: str, *args: Any) -> None:
        self.calls.append(("execute", sql, args))

    def transaction(self) -> _Transaction:
        transaction = _Transaction()
        self.transactions.append(transaction)
        return transaction


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    def acquire(self) -> Any:
        conn = self.conn

        class _Acquire:
            async def __aenter__(self) -> _Conn:
                return conn

            async def __aexit__(self, *_args: Any) -> bool:
                return False

        return _Acquire()

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        return await self.conn.fetchrow(sql, *args)

    async def fetchval(self, sql: str, *args: Any) -> Any:
        return await self.conn.fetchval(sql, *args)

    async def execute(self, sql: str, *args: Any) -> None:
        await self.conn.execute(sql, *args)


@pytest.mark.asyncio
async def test_recall_list_contains_only_jobs_whose_deadline_has_arrived() -> None:
    conn = _Conn([])

    await RecallJobService(_Pool(conn)).danh_sach(
        identity=_identity(), sinh_truoc=False
    )

    _, sql, args = conn.calls[0]
    assert "n.han_goi <= $2::date" in sql
    assert isinstance(args[1], date)


@pytest.mark.asyncio
async def test_recall_job_and_customer_care_log_share_one_transaction() -> None:
    conn = _Conn(
        {"id": "v1", "luot_goi": 2, "clinic_patient_id": "cp1"},
    )

    await RecallJobService(_Pool(conn)).ghi_ket_qua(
        identity=_identity(),
        viec_id="v1",
        ket_qua="DA_LIEN_HE",
        ghi_chu="khách đã nhận lịch",
    )

    assert len(conn.transactions) == 1
    assert conn.transactions[0].entered and conn.transactions[0].exited
    sql = "\n".join(call[1] for call in conn.calls)
    assert "UPDATE public.nhac_tai_kham" in sql
    assert "han_goi <= $6::date" in sql
    assert "INSERT INTO public.cskh_log" in sql


@pytest.mark.asyncio
async def test_future_recall_job_cannot_be_closed_by_a_stale_request() -> None:
    conn = _Conn(
        None,  # UPDATE rejects a future job
        "CHO_GOI",  # it exists and remains open
    )

    with pytest.raises(ValidationError, match="chưa tới hạn"):
        await RecallJobService(_Pool(conn)).ghi_ket_qua(
            identity=_identity(),
            viec_id="future-job",
            ket_qua="DA_LIEN_HE",
        )

    assert "han_goi <= $6::date" in conn.calls[0][1]


@pytest.mark.asyncio
async def test_cannot_record_result_delivery_without_a_delivered_file() -> None:
    conn = _Conn(
        True,  # patient belongs to this clinic
        False,  # no tep_ket_qua row has gui_luc
    )

    with pytest.raises(ValidationError, match="tệp kết quả.*đã gửi"):
        await TuongTacCskhService(_Pool(conn)).ghi(
            identity=_identity(),
            clinic_patient_id="b0000000-0000-4000-8000-000000000001",
            loai="TRA_KQ",
            kenh="TRUC_TIEP",
            ket_qua="DA_LIEN_HE",
            trang_thai_ma="KQ_CHUA_GUI",
        )

    sql = "\n".join(call[1] for call in conn.calls)
    assert "FROM public.tep_ket_qua" in sql
    assert "gui_luc IS NOT NULL" in sql
    assert "FROM public.lab_result" in sql
    assert "pending.gui_luc IS NULL" in sql
    assert "INSERT INTO public.tuong_tac_cskh" not in sql


@pytest.mark.asyncio
async def test_failed_result_call_cannot_close_the_delivery_work_item() -> None:
    conn = _Conn()

    with pytest.raises(ValidationError, match="đã liên hệ và gửi thành công"):
        await TuongTacCskhService(_Pool(conn)).ghi(
            identity=_identity(),
            clinic_patient_id="b0000000-0000-4000-8000-000000000001",
            loai="TRA_KQ",
            kenh="GOI",
            ket_qua="CHUA_NGHE_MAY",
            trang_thai_ma="KQ_CHUA_GUI",
        )

    assert conn.calls == []


@pytest.mark.asyncio
async def test_result_delivery_is_recorded_after_a_file_was_delivered() -> None:
    conn = _Conn(
        True,  # patient belongs to this clinic
        True,  # a delivered result file exists
        "interaction-1",
    )

    result = await TuongTacCskhService(_Pool(conn)).ghi(
        identity=_identity(),
        clinic_patient_id="b0000000-0000-4000-8000-000000000001",
        loai="TRA_KQ",
        kenh="TRUC_TIEP",
        ket_qua="DA_LIEN_HE",
        trang_thai_ma="KQ_CHUA_GUI",
    )

    assert result == {"ok": True, "id": "interaction-1"}


@pytest.mark.asyncio
async def test_result_delivery_guard_covers_pending_files_of_every_visit() -> None:
    """View KQ_CHUA_GUI is patient-wide, so its guard must be patient-wide too."""
    appointment_id = "c0000000-0000-4000-8000-000000000001"
    conn = _Conn(
        True,  # patient belongs to clinic
        True,  # appointment belongs to patient
        False,  # another visit still has a pending file
    )

    with pytest.raises(ValidationError, match="tệp kết quả.*đã gửi"):
        await TuongTacCskhService(_Pool(conn)).ghi(
            identity=_identity(),
            clinic_patient_id="b0000000-0000-4000-8000-000000000001",
            appointment_id=appointment_id,
            loai="TRA_KQ",
            kenh="TRUC_TIEP",
            ket_qua="DA_LIEN_HE",
            trang_thai_ma="KQ_CHUA_GUI",
        )

    guard_sql = next(
        sql
        for kind, sql, _args in conn.calls
        if kind == "fetchval" and "tep_ket_qua" in sql
    )
    assert "pending.appointment_id" not in guard_sql
    assert "t.appointment_id" not in guard_sql


@pytest.mark.asyncio
async def test_result_delivery_guard_and_insert_share_patient_lock() -> None:
    patient_id = "b0000000-0000-4000-8000-000000000001"
    conn = _Conn(True, True, "interaction-1")

    await TuongTacCskhService(_Pool(conn)).ghi(
        identity=_identity(),
        clinic_patient_id=patient_id,
        loai="TRA_KQ",
        kenh="TRUC_TIEP",
        ket_qua="DA_LIEN_HE",
        trang_thai_ma="KQ_CHUA_GUI",
    )

    sqls = [sql for _kind, sql, _args in conn.calls]
    lock_index = next(i for i, sql in enumerate(sqls) if "pg_advisory_xact_lock" in sql)
    guard_index = next(
        i for i, sql in enumerate(sqls) if "FROM public.tep_ket_qua" in sql
    )
    insert_index = next(
        i
        for i, sql in enumerate(sqls)
        if "INSERT INTO public.tuong_tac_cskh" in sql
    )
    assert lock_index < guard_index < insert_index
    lock_call = conn.calls[lock_index]
    assert lock_call[2] == (
        f"cskh-ket-qua:{_identity().clinic_id}:{patient_id}",
    )


@pytest.mark.asyncio
async def test_zns_result_notice_does_not_claim_the_file_was_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.services.providers import zalo

    async def _sent(**_kwargs: Any) -> dict[str, Any]:
        return {"da_gui": True, "msg_id": "zns-1"}

    interaction: dict[str, Any] = {}

    async def _record(_self: Any, **kwargs: Any) -> dict[str, Any]:
        interaction.update(kwargs)
        return {"ok": True, "id": "interaction-1"}

    monkeypatch.setattr(zalo, "gui_zns", _sent)
    monkeypatch.setattr(zalo, "template_cho", lambda _kind: "template-1")
    monkeypatch.setattr(TuongTacCskhService, "ghi", _record)
    conn = _Conn({"full_name": "Lan", "phone_primary": "0989862764"})

    result = await GuiZaloService(_Pool(conn)).gui(
        identity=_identity(),
        clinic_patient_id="b0000000-0000-4000-8000-000000000001",
        loai_tin="TRA_KET_QUA",
    )

    assert result["da_gui"] is True
    assert interaction["loai"] == "KHAC"


@pytest.mark.asyncio
async def test_callback_cannot_close_before_its_clinic_date_and_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.services import tuong_tac_cskh_service as module

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "_FrozenDateTime":
            moment = cls(2026, 8, 11, 16, 59, tzinfo=CLINIC_TZ)
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(module, "datetime", _FrozenDateTime)
    conn = _Conn(
        {
            "id": "h1",
            "ngay_goi": date(2026, 8, 11),
            "gio_goi": time(17, 0),
            "dong_luc": None,
        }
    )

    with pytest.raises(ValidationError, match="17:00"):
        await HenGoiLaiService(_Pool(conn)).dong(identity=_identity(), hen_id="h1")

    sql = "\n".join(call[1] for call in conn.calls)
    assert "SET dong_luc" not in sql


@pytest.mark.asyncio
async def test_callback_can_close_at_its_clinic_date_and_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from clinicai.services import tuong_tac_cskh_service as module

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "_FrozenDateTime":
            moment = cls(2026, 8, 11, 17, 0, tzinfo=CLINIC_TZ)
            return moment if tz is None else moment.astimezone(tz)

    monkeypatch.setattr(module, "datetime", _FrozenDateTime)
    conn = _Conn(
        {
            "id": "h1",
            "ngay_goi": date(2026, 8, 11),
            "gio_goi": time(17, 0),
            "dong_luc": None,
        },
        {"id": "h1"},
    )

    result = await HenGoiLaiService(_Pool(conn)).dong(identity=_identity(), hen_id="h1")

    assert result == {"ok": True}
    assert any("SET dong_luc" in call[1] for call in conn.calls)
