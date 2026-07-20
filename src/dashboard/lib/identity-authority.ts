/** Pure identity validation shared by login and server-side authorization. */

export interface LinkedStaffIdentity {
  id: string;
  auth_user_id: string | null;
  primary_department: string;
  is_active: boolean;
}

/**
 * Accept a staff identity only when it is active and linked to the verified
 * Supabase Auth user. A posted staff id or a role cookie is never authority.
 */
export function resolveLinkedStaffAuthority<T extends LinkedStaffIdentity>(
  authenticatedUserId: string | null | undefined,
  staff: T | null | undefined,
): T | null {
  if (
    !authenticatedUserId ||
    !staff ||
    !staff.is_active ||
    staff.auth_user_id !== authenticatedUserId
  ) {
    return null;
  }
  return { ...staff };
}

/** MANAGEMENT is the only department allowed to use privileged admin APIs. */
export function hasManagementAuthority(
  authenticatedUserId: string | null | undefined,
  staff: LinkedStaffIdentity | null | undefined,
): boolean {
  return (
    resolveLinkedStaffAuthority(authenticatedUserId, staff)
      ?.primary_department === "MANAGEMENT"
  );
}
