/** Pure identity validation shared by login and server-side authorization. */

export interface LinkedStaffIdentity {
  id: string;
  auth_user_id: string | null;
  primary_department: string;
  is_active: boolean;
}

export interface ClinicMembershipAuthority {
  clinic_id: string;
  role: string;
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

/**
 * Resolve the tenant for an Auth-admin operation. Until the product has an
 * explicit active-clinic selector, multiple management tenants are ambiguous
 * and therefore denied instead of silently choosing one.
 */
export function resolveSingleManagementClinic(
  memberships: readonly ClinicMembershipAuthority[],
): string | null {
  const membership = resolveSingleActiveMembership(memberships);
  return membership?.role === "MANAGEMENT" ? membership.clinic_id : null;
}

/**
 * The dashboard does not yet expose an active-clinic selector. It can safely
 * operate only when the verified staff identity has exactly one active
 * membership; any ambiguity is rejected until the user explicitly chooses.
 */
export function resolveSingleActiveMembership<
  T extends ClinicMembershipAuthority,
>(memberships: readonly T[]): T | null {
  const active = memberships.filter((membership) => membership.is_active);
  return active.length === 1 ? ({ ...active[0] } as T) : null;
}
