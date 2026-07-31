"use client";

/**
 * The action row for one work item, shared by every board.
 *
 * Written after Quang looked at the doctor's board and said he could not see
 * the "Bắt đầu khám" button. It was there — rendered, visible to Playwright,
 * and disabled. It was also a white outline button at 50% opacity on a white
 * card, which is indistinguishable from empty space. "The test can find it" is
 * not the same as "a person can see it".
 *
 * Two fixes, and the second matters more:
 *
 *   1. A disabled button now has a filled grey surface, so it reads as a
 *      control that is switched off rather than as nothing at all.
 *
 *   2. When the item is BLOCKED, no buttons are drawn. The screen has already
 *      said "chưa khám được, đang chờ LUOTKHAM-03" in red directly above;
 *      offering two dead controls underneath invites the reader to try them and
 *      then wonder what they did wrong. Instead it names the step that has to
 *      happen and who does it — the next useful action is somebody else's, so
 *      say whose.
 */

import type { ClinicRole } from "@/lib/roles";

export interface WorkItemActionsProps {
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "SKIPPED" | "CANCELLED";
  blocked: boolean;
  actionableByMe: boolean;
  /** Roles the node belongs to, for the "not yours" message. */
  actorRoles?: string[];
  /** Node codes still in the way, when known. */
  blockedBy?: string[];
  pending: boolean;
  error: string | null;
  onIssue: (command: "start" | "complete") => void;
  startLabel?: string;
  completeLabel?: string;
}

/** Vietnamese role names, so a message never shows a database enum to a nurse. */
const ROLE_VI: Record<string, string> = {
  DOCTOR: "bác sĩ",
  ULTRASOUND_DOCTOR: "bác sĩ siêu âm",
  NURSE_ULTRASOUND: "điều dưỡng siêu âm",
  TKYK: "thư ký y khoa",
  RECEPTION: "lễ tân",
  CSKH: "CSKH",
  CASHIER: "thu ngân",
  CASHIER_THUOC: "thu ngân thuốc",
  CASHIER_DV: "thu ngân dịch vụ",
  TRUONG_CA: "trưởng ca",
  MANAGEMENT: "quản lý",
};

const roleNames = (roles: string[]) =>
  roles.map((r) => ROLE_VI[r] ?? r.toLowerCase()).join(", ");

export default function WorkItemActions({
  status,
  blocked,
  actionableByMe,
  actorRoles = [],
  blockedBy = [],
  pending,
  error,
  onIssue,
  startLabel = "Bắt đầu",
  completeLabel = "Hoàn tất bước này",
}: WorkItemActionsProps) {
  // Blocked: the useful information is which step, not a pair of dead buttons.
  if (blocked) {
    return (
      <div className="rounded-control border border-line bg-surface-sunken px-3 py-2.5 text-sm text-ink-soft">
        <p className="font-medium text-ink">Chưa thao tác được</p>
        <p className="mt-0.5 text-xs">
          {blockedBy.length > 0
            ? `Đang chờ bước ${blockedBy.join(", ")} hoàn tất.`
            : "Còn bước phía trước chưa hoàn tất."}{" "}
          Khi bước đó xong, các nút ở đây sẽ mở.
        </p>
      </div>
    );
  }

  // Someone else's step. Say whose, rather than greying a button they will
  // never be able to press.
  if (!actionableByMe) {
    return (
      <div className="rounded-control border border-line bg-surface-sunken px-3 py-2.5 text-sm text-ink-soft">
        <p className="font-medium text-ink">Bước này không thuộc vai của bạn</p>
        <p className="mt-0.5 text-xs">
          {actorRoles.length > 0
            ? `Do ${roleNames(actorRoles)} thực hiện.`
            : "Do vai khác thực hiện."}{" "}
          Bạn xem được nhưng không thao tác.
        </p>
      </div>
    );
  }

  if (status === "COMPLETED" || status === "SKIPPED" || status === "CANCELLED") {
    return null;
  }

  const off =
    "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken " +
    "disabled:text-ink-faint disabled:shadow-none";

  return (
    <div className="flex flex-col gap-2">
      {error ? (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex flex-wrap gap-2">
        {status === "PENDING" ? (
          <button
            type="button"
            disabled={pending}
            onClick={() => onIssue("start")}
            className={`rounded-control border border-line-strong bg-surface px-4 py-2.5 text-sm font-medium text-ink hover:bg-surface-sunken ${off}`}
          >
            {startLabel}
          </button>
        ) : null}
        <button
          type="button"
          disabled={pending}
          onClick={() => onIssue("complete")}
          className={`rounded-control bg-brand-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-brand-700 ${off}`}
        >
          {pending ? "Đang lưu…" : completeLabel}
        </button>
      </div>
    </div>
  );
}

export type { ClinicRole };
