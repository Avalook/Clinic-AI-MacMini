export interface LabReleaseDecision {
  allowed: boolean;
  label: string;
  className: string;
}

const BLOCKED_CLASS =
  "shrink-0 rounded-md bg-danger-bg px-2 py-0.5 text-xs font-semibold text-danger";

/**
 * Patient notification is a clinical safety boundary, not presentation logic.
 * Only a finalized GROUP_A result may cross it; every unknown value fails
 * closed per docs/lab_triage_spec_v1.md.
 */
export function labReleaseDecision(
  triageGroup: string | null | undefined,
  isFinalized: boolean,
): LabReleaseDecision {
  if (triageGroup === "GROUP_A" && isFinalized) {
    return {
      allowed: true,
      label: "Được báo BN",
      className:
        "shrink-0 rounded-md bg-success-bg px-2 py-0.5 text-xs font-semibold text-success",
    };
  }

  if (triageGroup === "GROUP_C") {
    return {
      allowed: false,
      label: "Khẩn cấp — KHÔNG báo BN",
      className: BLOCKED_CLASS,
    };
  }
  if (triageGroup === "GROUP_B") {
    return {
      allowed: false,
      label: "Chờ BS duyệt — KHÔNG báo BN",
      className: BLOCKED_CLASS,
    };
  }
  if (triageGroup === "GROUP_A") {
    return {
      allowed: false,
      label: "Chưa hoàn tất — KHÔNG báo BN",
      className: BLOCKED_CLASS,
    };
  }
  return {
    allowed: false,
    label: "Chưa phân loại — KHÔNG báo BN",
    className: BLOCKED_CLASS,
  };
}
