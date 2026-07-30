# Supabase production schema drift report

Generated: 2026-07-23

## Scope and method

- Source: schema-only snapshot in `docs/database/schema.sql`.
- Expected state: all files in `supabase/migrations/*.sql`, applied in filename order to a disposable PostgreSQL 17 database.
- Comparison: PostgreSQL catalog objects (tables, columns, constraints, indexes, functions, triggers, policies, and RLS flags).
- No application rows were read or compared. The snapshot contains no `COPY`, `INSERT INTO`, sequence-value, or data-section statements.
- The four tables in the `langgraph` schema are excluded from public-schema drift because ADR-0007 explicitly treats them as runtime-managed disposable state.

## Summary

Production is not aligned with the tracked migrations.

| Object | Expected | Production | Main difference |
|---|---:|---:|---|
| Public tables | 33 | 35 | 1 expected table missing; 3 retired tables remain |
| User-defined public functions | 19 | 9 | 11 expected functions missing; 1 retired function remains |
| Public indexes | 117 | 120 | 6 expected indexes missing; 9 indexes belong to retired tables |
| Public triggers | 21 | 21 | 2 expected appointment triggers missing; 2 retired-table triggers remain |
| Public policies | 23 | 23 | Event-log policy is the old broad policy |
| RLS-enabled public tables | 32 | 35 | The 3 retired tables still have RLS enabled |

Shared columns, constraints, indexes, triggers, and policies have matching definitions unless called out below.

## Missing from production

### Table

- `public.idempotency_key`

This means the idempotency migrations have not reached the live schema:

- `20260714000003_idempotency_key.sql`
- `20260714000005_idempotency_scope_and_reservation.sql`

### Functions

- `assign_appointment_queue_number()`
- `check_in_appointment(uuid, text[])`
- `current_staff_department()`
- `enforce_slot_capacity()`
- `event_log_append_only_guard()`
- `generate_lab_result_code()`
- `generate_patient_code()`
- `kb_page_update_search_vector()`
- `kb_version_append_only_guard()`
- `prevent_dead_letter_modification()`
- `set_updated_at_timestamp()`

The most operationally important gaps are the atomic queue/check-in functions, slot-capacity guard, idempotency support, and least-privilege event-log authorization.

### Triggers

- `appointment_assign_queue_number`
- `trg_enforce_slot_capacity`

### Indexes

- `appointment.idx_appointment_doctor_slot`
- `appointment.idx_appointment_slot_start_status`
- `idempotency_key.idempotency_key_pkey`
- `idempotency_key.idx_idempotency_key_created`
- `visit.idx_visit_appointment_id`
- `visit.idx_visit_created_at`

### Policy

- Expected: `event_log_select_management`
- Live instead: `event_log_select_authenticated`

Production therefore still permits every authenticated user to select from `event_log`, while the tracked migration narrows access to management staff.

## Extra retired objects still in production

### Tables

- `patient_contact_channel`
- `patient_next_of_kin`
- `visit_amendment`

These are the three tables documented as removed from the consolidated baseline. Their nine indexes, three RLS flags, the `visit_amendment_append_only()` function, and two `visit_amendment` triggers remain live.

Do not drop these tables until their live contents and any external consumers have been reviewed. A schema-only comparison cannot establish whether deleting them is operationally safe.

## Changed shared function

`public.f_unaccent(text)` is not the hardened migration version.

- Expected: schema-qualified `public.unaccent('public.unaccent'::regdictionary, ...)`
- Live: unqualified `unaccent('unaccent', ...)`

The production form depends on `search_path`; the tracked form is explicit and safer.

`enforce_append_only()` has only whitespace differences after PostgreSQL normalization and is not treated as semantic drift.

## Recommended next action

Do not run the consolidated baseline blindly against production. Create and review a forward-only reconciliation migration that:

1. Adds the missing idempotency, capacity, queue, index, and authorization objects.
2. Replaces `f_unaccent(text)` with the schema-qualified implementation.
3. Verifies the three retired tables have no required data or consumers before removing them in a separate migration.
4. Applies and validates the reconciliation on staging before production.

