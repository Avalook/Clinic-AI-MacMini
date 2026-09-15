/** Protect local typing when a shared, persisted chart changes. */
export function clinicalSyncDecision(
  local: string,
  baseline: string,
  remote: string,
  saving: boolean,
): "apply" | "conflict" | "unchanged" {
  if (remote === baseline) return "unchanged";
  if (saving || local !== baseline) return "conflict";
  return "apply";
}
