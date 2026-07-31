/**
 * The one status renderer.
 *
 * ClinicAI has three separate status vocabularies — appointment.status (8),
 * work_item.status (5 stored, 12 named in the design), and visit.status — and
 * before this they were drawn by whichever component happened to be nearby,
 * with hex codes pasted inline. One renderer means a status looks the same
 * wherever it appears; the per-domain mapping stays in lib/*-status.ts.
 *
 * Two rules from the icon system are enforced here rather than trusted to
 * callers: the label is always rendered (colour is never the only signal), and
 * the tone token drives both fill and text so contrast cannot be broken by
 * picking a nice-looking pair.
 *
 * Four tones the icon system named — draft, on_hold, rejected, failed — are
 * deliberately absent: the kernel has no command that produces them (decision
 * 2026-08-01). A tone that cannot occur is a tone somebody eventually uses for
 * something else, which is exactly what happened here when the priority chip
 * borrowed on_hold.
 *
 * The shape is a soft rectangle (6px), not a pill. I had it as rounded-full
 * from memory of the screenshots; the design set uses a small radius, and at
 * chip size the two read as different products.
 */

import type { ReactNode } from "react";

export type StatusTone =
  | "ready"
  | "assigned"
  | "called"
  | "in_progress"
  | "blocked"
  | "completed"
  | "skipped"
  | "cancelled"
  | "overdue";

/** Fill + text per tone. Both come from the same token pair in globals.css. */
const TONE: Record<StatusTone, string> = {
  ready: "bg-status-ready-bg text-status-ready",
  assigned: "bg-status-assigned-bg text-status-assigned",
  called: "bg-status-called-bg text-status-called",
  in_progress:
    "bg-status-in-progress-bg text-status-in-progress",
  blocked: "bg-status-blocked-bg text-status-blocked",
  completed: "bg-status-completed-bg text-status-completed",
  skipped: "bg-status-cancelled-bg text-status-cancelled",
  cancelled: "bg-status-cancelled-bg text-status-cancelled",
  overdue: "bg-status-overdue-bg text-status-overdue",
};

export interface StatusChipProps {
  tone: StatusTone;
  /** Vietnamese label. Required — a chip with no label is not allowed. */
  label: string;
  /** Optional leading icon from the 61-symbol set. */
  icon?: ReactNode;
  /** Denser variant for inside table rows. */
  size?: "sm" | "md";
  /** Extra detail read by assistive tech, e.g. "quá hạn 45 phút". */
  title?: string;
}

export default function StatusChip({
  tone,
  label,
  icon,
  size = "sm",
  title,
}: StatusChipProps) {
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip font-medium whitespace-nowrap ${pad} ${TONE[tone]}`}
      title={title}
    >
      {icon}
      {label}
    </span>
  );
}
