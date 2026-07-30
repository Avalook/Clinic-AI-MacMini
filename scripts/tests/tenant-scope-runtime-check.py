#!/usr/bin/env python3
"""Run every tenant-scoped statement against the LOCAL Supabase Postgres.

The companion to scripts/tests/tenant-scope-audit.py, which is static: it reads
the SQL as text and can only see whether clinic_id is mentioned. This one
executes the statements. A misspelled column, a clinic_id bolted onto the wrong
table or a parameter left at the wrong position is invisible to the audit and to
the unit tests — those mock the pool, so they pass on SQL Postgres would reject.

It also proves the scope is real rather than decorative: it writes a row under
one clinic and checks the other clinic cannot read it back.

It creates the second clinic it needs and removes it again, so it leaves the
database as it found it.

Prerequisite:  npx supabase start.  Run:  PYTHONPATH=src poetry run python \
    scripts/tests/tenant-scope-runtime-check.py
"""

import asyncio
import uuid
from datetime import date, datetime, timezone

import asyncpg

DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

async def main() -> int:
    from clinicai.graphs.lab_triage.nodes import _FETCH_BY_ID_SQL
    from clinicai.services.staff_service import get_staff_by_capability
    from clinicai.tools._common.context import new_trace
    from clinicai.tools.lab.query_lab_result import (
        QueryLabResultFilter,
        query_lab_result,
    )
    from clinicai.tools.scheduling.find_work_sessions import (
        FindWorkSessionsInput,
        find_work_sessions,
    )
    from clinicai.tools.task.create_task import CreateTaskInput, create_task
    from clinicai.tools.task.query_tasks import QueryTasksFilter, query_tasks

    pool = await asyncpg.create_pool(DSN, min_size=1, max_size=3)
    assert pool is not None
    ok = fail = 0

    async def check(label, coro):
        nonlocal ok, fail
        try:
            await coro
            print(f"  PASS  {label}")
            ok += 1
        except Exception as exc:
            print(f"  FAIL  {label}\n        {type(exc).__name__}: {exc}")
            fail += 1

    # A second clinic is the whole point: with one, default_clinic_id() papers
    # over a missing tenant filter. This creates its own rather than depending
    # on one being left behind by something else, and removes it at the end.
    clinic_id = await pool.fetchval("SELECT id FROM clinic WHERE code = 'DR4WOMEN'")
    other = await pool.fetchval(
        "INSERT INTO clinic (code, name) VALUES ('W8PROBE', 'W8 scope probe') "
        "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name RETURNING id"
    )
    patient = await pool.fetchval(
        "SELECT clinic_patient_id FROM patient WHERE clinic_id = $1 LIMIT 1", clinic_id)
    loc = await pool.fetchval(
        "SELECT id FROM clinic_location WHERE clinic_id = $1 LIMIT 1", clinic_id)
    lab_id = await pool.fetchval(
        "SELECT lab_result_id FROM lab_result WHERE clinic_id = $1 LIMIT 1", clinic_id)
    session_type = await pool.fetchval(
        "SELECT session_type FROM work_session WHERE clinic_id = $1 LIMIT 1", clinic_id)
    print(f"clinic={clinic_id}  other={other}  default_clinic_id()="
          f"{await pool.fetchval('SELECT public.default_clinic_id()')}\n")

    print("=== statements execute ===")
    await check("query_lab_result", query_lab_result(
        pool, QueryLabResultFilter(clinic_patient_id=patient, clinic_id=clinic_id),
        new_trace()))
    await check("query_lab_result (every optional filter)", query_lab_result(
        pool, QueryLabResultFilter(
            clinic_patient_id=patient, clinic_id=clinic_id, test_code="CBC",
            group="GROUP_A", date_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            date_to=datetime(2030, 1, 1, tzinfo=timezone.utc), is_finalized=True,
            limit=5),
        new_trace()))
    await check("query_tasks (tenant only)", query_tasks(
        pool, QueryTasksFilter(clinic_id=clinic_id), new_trace()))
    await check("query_tasks (all filters)", query_tasks(
        pool, QueryTasksFilter(
            clinic_id=clinic_id, location_id=loc, status="PENDING",
            task_type="LAB_REVIEW", source_type="LAB_RESULT",
            source_id=uuid.uuid4(), overdue_only=True),
        new_trace()))
    await check("find_work_sessions", find_work_sessions(
        FindWorkSessionsInput(location_id=loc, session_date=date.today(),
                              session_type=session_type or "EVENING",
                              clinic_id=clinic_id), pool))
    await check("get_staff_by_capability", get_staff_by_capability(
        pool, capability="SIEU_AM", location_id=loc, clinic_id=str(clinic_id)))
    if lab_id:
        await check("lab_triage fetch-by-id", pool.fetchrow(
            _FETCH_BY_ID_SQL, lab_id, clinic_id))

    print("\n=== the scope actually holds ===")
    task = await create_task(pool, CreateTaskInput(
        task_type="W8_PROBE", title="W8 scope probe", clinic_id=other), new_trace())
    mine = await query_tasks(pool, QueryTasksFilter(
        clinic_id=other, task_type="W8_PROBE"), new_trace())
    theirs = await query_tasks(pool, QueryTasksFilter(
        clinic_id=clinic_id, task_type="W8_PROBE"), new_trace())
    # There is no "unscoped caller" left to test: clinic_id is a required field,
    # so a query without a tenant does not reach the database — it does not
    # compile. Assert that instead, since it is the stronger guarantee.
    try:
        QueryTasksFilter(task_type="W8_PROBE")  # type: ignore[call-arg]
        unscoped_refused = False
    except Exception:
        unscoped_refused = True
    labs_other = await query_lab_result(pool, QueryLabResultFilter(
        clinic_patient_id=patient, clinic_id=other), new_trace())
    labs_mine = await query_lab_result(pool, QueryLabResultFilter(
        clinic_patient_id=patient, clinic_id=clinic_id), new_trace())
    for label, cond in [
        ("create_task filed the row under the clinic it was given",
         len(mine) == 1 and mine[0].task_id == task.task_id),
        ("the other clinic cannot see it", theirs == []),
        ("a query cannot even be built without a tenant", unscoped_refused),
        ("a patient's labs are invisible to the wrong clinic", labs_other == []),
        ("and visible to the right one", len(labs_mine) > 0),
    ]:
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)

    await pool.execute("DELETE FROM staff_task WHERE task_type = 'W8_PROBE'")
    await pool.execute(
        "DELETE FROM clinical_form_catalogue WHERE clinic_id = $1", other)
    await pool.execute("DELETE FROM clinic WHERE code = 'W8PROBE'")
    await pool.close()
    print(f"\n=== {ok} passed, {fail} failed ===")
    return 1 if fail else 0

raise SystemExit(asyncio.run(main()))
