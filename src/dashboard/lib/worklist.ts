/**
 * Types and pure helpers for a workspace queue.
 *
 * No session, no fetch, no server-only imports — the queue board is a client
 * component and importing this must not pull cookies() into the browser
 * bundle. The fetch lives in lib/worklist-server.ts.
 */

export interface WorklistPatient {
  clinic_patient_id: string | null;
  patient_code: string | null;
  full_name: string | null;
  date_of_birth: string | null;
  gender: string | null;
  phone_primary: string | null;
}

export interface WorklistItem {
  id: string;
  node_code: string;
  node_name: string | null;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "SKIPPED" | "CANCELLED";
  priority: string;
  version: number;
  visit_id: string | null;
  appointment_id: string | null;
  assigned_to: string | null;
  assigned_role: string | null;
  actor_roles: string[];
  actionable_by_me: boolean;
  blocked: boolean;
  due_at: string | null;
  created_at: string | null;
  started_at: string | null;
  patient: WorklistPatient;
  queue_number: string | null;
  slot_start: string | null;
  booking_channel: string | null;
  is_priority_slot: boolean;
  checked_in_at: string | null;
}

/** Minutes waited so far. Uses check-in time when there is one, else creation. */
export function waitedMinutes(item: WorklistItem, now: Date = new Date()): number {
  const from = item.checked_in_at ?? item.created_at;
  if (!from) return 0;
  return Math.max(0, Math.round((now.getTime() - new Date(from).getTime()) / 60000));
}

/** "1994 · Nữ · 32 tuổi", the subtitle used on every patient card in the design. */
export function patientLine(p: WorklistPatient): string {
  const bits: string[] = [];
  if (p.date_of_birth) {
    const year = new Date(p.date_of_birth).getFullYear();
    bits.push(String(year));
    const age = new Date().getFullYear() - year;
    if (p.gender) bits.push(p.gender);
    bits.push(`${age} tuổi`);
  } else if (p.gender) {
    bits.push(p.gender);
  }
  return bits.join(" · ");
}
