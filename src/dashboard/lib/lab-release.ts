export interface LabReleaseDecision {
  allowed: boolean;
  label: string;
  className: string;
}

const BLOCKED_CLASS =
  "shrink-0 rounded-md bg-[#fee2e2] px-2 py-0.5 text-xs font-semibold text-[#dc2626]";

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
        "shrink-0 rounded-md bg-[#dcfce7] px-2 py-0.5 text-xs font-semibold text-[#16a34a]",
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
