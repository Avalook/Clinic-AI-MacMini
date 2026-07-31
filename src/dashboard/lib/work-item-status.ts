/**
 * The status vocabulary, reconciled.
 *
 * Section 05 of the icon system names TWELVE work-item statuses. The kernel
 * stores FIVE (PENDING, IN_PROGRESS, COMPLETED, SKIPPED, CANCELLED). That gap
 * is not a mistake in either one — most of the design's statuses are things you
 * can work out from what the kernel already stores, and a status you can derive
 * is better than a status you have to remember to write.
 *
 * This module is the single place that mapping lives. Every screen that draws a
 * status goes through `resolveStatus`, so the board, the queue and the
 * reconciliation screen cannot drift into three different vocabularies.
 *
 * What is DERIVED (kernel already has everything needed):
 *   ready      PENDING, nothing blocking it            → the gate is open
 *   assigned   PENDING and assigned_to is set
 *   blocked    PENDING with a shut gate                → API returns `blocked`
 *   overdue    due_at has passed and it is still open  → overlays the others
 *
 * What the kernel CANNOT express today — deliberately listed rather than faked:
 *   draft, on-hold, rejected, failed, called
 *
 * `called` is not a work-item state at all: calling a patient's number belongs
 * to the queue (appointment.queue_number), and the icon system's own rule 2
 * says a node's capability is not the same thing as a work item. The other four
 * would need real kernel commands (hold/resume, reject, fail) and a decision
 * about what they do to downstream gates. Until that decision is made, nothing
 * in the UI may claim an item is on hold, because the kernel would not agree.
 *
 * Conversely the design has no chip for SKIPPED, which the kernel really does
 * store, so one is added here — a skipped step must be visible or the board
 * silently lies about what happened.
 */

/** What the kernel actually stores in work_item.status. */
export type KernelStatus =
  | "PENDING"
  | "IN_PROGRESS"
  | "COMPLETED"
  | "SKIPPED"
  | "CANCELLED";

/** What a screen draws. Superset of the kernel, minus what we cannot honour. */
export type DisplayStatus =
  | "ready"
  | "assigned"
  | "in_progress"
  | "blocked"
  | "completed"
  | "skipped"
  | "cancelled"
  | "overdue";

/** Statuses the design names but the kernel cannot back yet. */
export const UNSUPPORTED_BY_KERNEL = [
  "draft",
  "called",
  "on_hold",
  "rejected",
  "failed",
] as const;

export interface StatusPresentation {
  /** Vietnamese label. Always rendered — colour is never the only signal. */
  label: string;
  /** Icon name from the 61-symbol set, `status-*` family. */
  icon: string;
  /** CSS custom-property suffix, e.g. `blocked` → var(--color-status-blocked). */
  token: DisplayStatus;
}

export const STATUS_PRESENTATION: Record<DisplayStatus, StatusPresentation> = {
  ready: { label: "Sẵn sàng", icon: "status-ready", token: "ready" },
  assigned: { label: "Đã phân công", icon: "status-assigned", token: "assigned" },
  in_progress: {
    label: "Đang thực hiện",
    icon: "status-in-progress",
    token: "in_progress",
  },
  blocked: { label: "Bị chặn", icon: "status-blocked", token: "blocked" },
  completed: { label: "Hoàn thành", icon: "status-completed", token: "completed" },
  skipped: { label: "Bỏ qua", icon: "status-cancelled", token: "skipped" },
  cancelled: { label: "Đã huỷ", icon: "status-cancelled", token: "cancelled" },
  overdue: { label: "Quá SLA", icon: "status-overdue", token: "overdue" },
};

/** The shape GET /api/v1/visits/{id}/work-items returns, as far as this needs. */
export interface WorkItemLike {
  status: KernelStatus;
  blocked?: boolean;
  assigned_to?: string | null;
  due_at?: string | null;
}

/**
 * Turn a kernel row into the status a screen should draw.
 *
 * Overdue WINS over everything still open, matching the designs: on the CSKH
 * list Lê Thu Trang shows "Quá SLA" where the others show their real status.
 * A breached deadline is the thing the reader has to act on, and burying it
 * behind "Đang thực hiện" is how a breach gets missed. It never overrides a
 * finished item — a step completed late is completed, and the lateness belongs
 * in the history, not on the board as an open alarm.
 */
export function resolveStatus(
  item: WorkItemLike,
  now: Date = new Date(),
): DisplayStatus {
  switch (item.status) {
    case "COMPLETED":
      return "completed";
    case "SKIPPED":
      return "skipped";
    case "CANCELLED":
      return "cancelled";
  }

  if (isOverdue(item, now)) return "overdue";

  if (item.status === "IN_PROGRESS") return "in_progress";

  // PENDING. Blocked is checked before assigned: knowing an item cannot start
  // matters more to the reader than knowing whose it is.
  if (item.blocked) return "blocked";
  if (item.assigned_to) return "assigned";
  return "ready";
}

/** Past its deadline and still open. Items without a due_at are never overdue. */
export function isOverdue(item: WorkItemLike, now: Date = new Date()): boolean {
  if (!item.due_at) return false;
  if (item.status !== "PENDING" && item.status !== "IN_PROGRESS") return false;
  return new Date(item.due_at).getTime() < now.getTime();
}

/**
 * How late, in whole minutes. Negative means still within the deadline, which
 * the queue screens use to show "còn 8 phút" as well as "quá hạn 45 phút".
 */
export function minutesPastDue(
  item: WorkItemLike,
  now: Date = new Date(),
): number | null {
  if (!item.due_at) return null;
  return Math.round((now.getTime() - new Date(item.due_at).getTime()) / 60000);
}
