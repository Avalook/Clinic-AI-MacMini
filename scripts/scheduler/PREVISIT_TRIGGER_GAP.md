# GAP REPORT — T-WIRE-SCHEDULER-PREVISIT-01 (FALLBACK, no code shipped)

**Date:** 2026-05-26 · **Branch:** feat/t-transform-01 · **Base HEAD:** 3d95585

The packet asked to wire an `event_type="previsit.trigger"` entry that **bypasses
classify** and injects `patient_id` + `work_session_id`, copying a supposed
lab_triage bypass pattern. Read-only survey (Step 1) shows the required
foundations do **not** exist, and building them needs edits the boundary forbids.
Per Step 2C, this gap report is committed **instead of wrong code**.

## What the code actually shows (verified, not assumed)

1. **No scheduler/cron daemon.** Only comment references to "cron/P13" in
   `orchestrator/stubs.py` + `api/v1/routers/brief.py`. No apscheduler/celery/beat.

2. **`OrchestratorState` (state.py) has NO `event_type` / `source` field.**
   Present: `trace_id, user_message, patient_id, route, response, error,
   handled_by`, scheduling mirror fields, and lab fields (`lab_result_id,
   triage_group, requires_doctor_review, escalation_note`). There is **no
   `work_session_id`** either.

3. **No bypass-classify pattern exists to copy.** Graph entry is a single
   `add_edge(START, "classify_intent")`; then `route_by_intent` fans out by the
   classifier's `route` string. **lab_triage does NOT bypass classify** — it is
   reached via `route=="lab"` and the wrapper reads `lab_result_id` from state.
   The packet's premise ("lab vào graph KHÔNG qua classify") is false.

4. **Even the route path for previsit is unreachable** (compounding gap from the
   79aab1e wiring): `"previsit"` is absent from `llm_nodes.VALID_ROUTES`,
   `nodes.py` rule-based classify, and `state.RouteType`. The classifier rejects
   `"previsit"` → falls back to `"general"`. (Router edge + wrapper exist and are
   correct; they're just not reachable.)

5. **previsit sub-graph input:** `PreVisitBriefState` requires only
   `clinic_patient_id` (maps from `patient_id`) + optional `trace_id`.
   `work_session_id` is **not** consumed by the sub-graph.

## Why FALLBACK (no code)

- Adding `event_type` / `source` / `work_session_id` ⇒ editing `OrchestratorState`
  TypedDict — **boundary: "KHÔNG sửa State TypedDict".**
- A START→event-type conditional that skips classify ⇒ a **new routing pattern**
  — packet: "KHÔNG phát minh pattern mới."
- A CLI `trigger_previsit.py` built on `event_type` would call a path that does
  not exist ⇒ "code sai." Not shipped.

## What a proper follow-up task must do (needs State edit + design sign-off)

1. `state.py`: add `event_type: NotRequired[str]`, `source`, `work_session_id`,
   and extend `RouteType` with `"previsit"`/`"task"`.
2. `llm_nodes.VALID_ROUTES` + classify system prompt + `nodes.py` rule-based:
   allow `"previsit"`/`"task"` (close the 79aab1e classifier gap).
3. `orchestrator/graph.py`: a conditional START edge —
   `event_type set → route straight to that node; else → classify_intent`.
   Define this pattern once for all event-driven sub-graphs (previsit, future cron).
4. Then: CLI `scripts/scheduler/trigger_previsit.py` + (later) the cron daemon.

Items 1–3 cross the current boundary (`state.py`, classify logic) → must be their
own packet, not folded into this one.
