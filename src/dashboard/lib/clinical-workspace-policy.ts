// Small, pure UI policies for clinical workspaces. These prevent a missing
// backend value from being presented as a medical or financial fact.

export const SA_WORKFLOW_STATUSES = [
  "WAITING",
  "IN_PROGRESS",
  "DONE",
  "CANCELLED",
] as const;

export type SaWorkflowStatus = (typeof SA_WORKFLOW_STATUSES)[number];
export type CashierPaymentKind = "thuoc" | "dich_vu";

export interface CashierPaymentSource {
  visit_id: string;
  kind: string;
  status: string | null;
}

export function resolveSaWorkflowStatus(
  status: string | null | undefined,
): SaWorkflowStatus | null {
  return SA_WORKFLOW_STATUSES.includes(status as SaWorkflowStatus)
    ? (status as SaWorkflowStatus)
    : null;
}

export function sonoPatientDisplayName(
  fullName: string | null | undefined,
): string {
  const name = fullName?.trim();
  return name || "Chưa gắn người bệnh";
}

export function paidCashierPaymentSeeds(
  payments: readonly CashierPaymentSource[],
): { visit_id: string; kind: CashierPaymentKind }[] {
  const paid: { visit_id: string; kind: CashierPaymentKind }[] = [];
  for (const payment of payments) {
    if (
      payment.status !== "PAID" ||
      (payment.kind !== "thuoc" && payment.kind !== "dich_vu")
    ) {
      continue;
    }
    paid.push({ visit_id: payment.visit_id, kind: payment.kind });
  }
  return paid;
}

export function cashierAmountState(
  hasItems: boolean,
  hasMissingPriceOrQuantity: boolean,
): "empty" | "incomplete" | "ready" {
  if (!hasItems) return "empty";
  return hasMissingPriceOrQuantity ? "incomplete" : "ready";
}

export function canFinishService(startedAt: string | null): boolean {
  return Boolean(startedAt);
}
