/**
 * Priority, which is not a status.
 *
 * This exists because the reception board was drawing "★ Ưu tiên" with
 * StatusChip tone="on_hold" — borrowing a work-item status colour for something
 * that is not a work-item status at all. It worked, so nobody would have
 * noticed until on_hold was dropped and a priority marker silently lost its
 * colour.
 *
 * The design keeps the two apart on purpose: status is the loud signal (what is
 * happening to this item), priority is the quiet one beside it (how it sorts
 * against its neighbours). Rendering priority in a status palette makes an
 * ordinary urgent patient look like a state machine event.
 */

export type Priority = "P0" | "P1" | "P2";

const TONE: Record<Priority, string> = {
  P0: "text-priority-p0 border-priority-p0",
  P1: "text-priority-p1 border-priority-p1",
  P2: "text-priority-p2 border-priority-p2",
};

const LABEL: Record<Priority, string> = {
  P0: "Ưu tiên",
  P1: "Cần sớm",
  P2: "Thường",
};

export default function PriorityChip({
  priority,
  label,
}: {
  priority: Priority;
  /** Override when the screen has its own wording. */
  label?: string;
}) {
  // Outline rather than filled: a quiet marker next to the loud status chip.
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-chip border bg-surface px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap ${TONE[priority]}`}
    >
      {label ?? LABEL[priority]}
    </span>
  );
}
