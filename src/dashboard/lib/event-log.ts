// Append one row to the append-only `event_log` (migration 013/014) — the
// immutable audit trail for state changes. Call AFTER a successful business
// write, with the same service-role client (event_log INSERT is allowed;
// UPDATE/DELETE/TRUNCATE are blocked by enforce_append_only()).
//
// Best-effort by design: the business row is already committed, so a logging
// failure must NOT turn a successful create into an error. We log + return the
// failure instead of throwing. (PostgREST has no cross-table transaction here;
// for guaranteed atomicity the next step would be a DB AFTER-INSERT trigger or
// an RPC that writes both rows in one transaction.)

import type { SupabaseClient } from "@supabase/supabase-js";

export interface EventInput {
  /** '<aggregate>.<verb>', lowercase snake_case — e.g. 'patient.created'. */
  event_type: string;
  /** e.g. 'patient', 'appointment'. */
  aggregate_type: string;
  /** id of the affected entity (patient.clinic_patient_id, appointment.id). */
  aggregate_id: string;
  /** Snapshot of the change, enough to replay state. */
  payload: Record<string, unknown>;
  /** Actor / request context (clinic_role, staff id, auth user, origin). */
  metadata?: Record<string, unknown>;
  /** Provenance tag; defaults to 'dashboard'. */
  source?: string;
}

export async function logEvent(
  db: SupabaseClient,
  e: EventInput,
): Promise<{ ok: boolean; error?: string }> {
  const { error } = await db.from("event_log").insert({
    event_type: e.event_type,
    aggregate_type: e.aggregate_type,
    aggregate_id: e.aggregate_id,
    payload: e.payload,
    metadata: e.metadata ?? {},
    source: e.source ?? "dashboard",
  });

  if (error) {
    // Surface for ops, but do not fail the already-committed business write.
    console.error("event_log insert failed", {
      event_type: e.event_type,
      aggregate_id: e.aggregate_id,
      error: error.message,
    });
    return { ok: false, error: error.message };
  }
  return { ok: true };
}
