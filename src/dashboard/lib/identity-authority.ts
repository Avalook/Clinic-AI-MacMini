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

const CLINIC_ID_SHAPE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Is this string even shaped like a clinic id?
 *
 * Nothing security-relevant — resolveActiveMembership() decides that. It keeps
 * a junk cookie from travelling to the backend as an X-Clinic-ID that its UUID
 * parser rejects with a 400, which reads to the user as "the app is broken"
 * rather than "nothing is selected".
 */
export function isClinicSelector(value: string | null | undefined): boolean {
  return typeof value === "string" && CLINIC_ID_SHAPE.test(value.trim());
}

/**
 * Outcome of picking the clinic a request acts in.
 *
 * ``ambiguous`` exists because "cannot decide" and "not allowed" used to be the
 * same value here — both were ``null``. A doctor working at two clinics was
 * therefore treated exactly like someone with no membership at all: signed out
 * at login, redirected to /login by the layout, with nothing on screen saying
 * why. The two answers now have different shapes so callers cannot conflate
 * them again.
 */
export type ClinicSelection<T extends ClinicMembershipAuthority> =
  | { status: "none" }
  | { status: "resolved"; membership: T }
  | { status: "ambiguous"; choices: T[] };

/**
 * Resolve which clinic a staff member is acting in.
 *
 * ``requestedClinicId`` is a *selector*, never authority (ADR-0009): it can
 * only pick among memberships this staff row already holds, so a forged cookie
 * buys nothing that a second login would not. The same rule the backend
 * applies in ``identity.py`` — hence the identical treatment of two active
 * roles inside one clinic, which is malformed provisioning rather than a
 * choice anyone can make.
 */
export function resolveActiveMembership<T extends ClinicMembershipAuthority>(
  memberships: readonly T[],
  requestedClinicId?: string | null,
): ClinicSelection<T> {
  const active = memberships.filter((membership) => membership.is_active);
  if (active.length === 0) return { status: "none" };

  if (requestedClinicId) {
    const selected = active.filter(
      (membership) => membership.clinic_id === requestedClinicId,
    );
    if (selected.length === 1) {
      return { status: "resolved", membership: { ...selected[0] } as T };
    }
    if (selected.length > 1) return { status: "none" };
    // A selection matching no membership is stale — revoked access, or a
    // cookie carried over from another deployment. Fall through and ask again
    // rather than lock the account out over a cookie.
  }

  if (active.length === 1) {
    return { status: "resolved", membership: { ...active[0] } as T };
  }
  return {
    status: "ambiguous",
    choices: active.map((membership) => ({ ...membership }) as T),
  };
}

/**
 * Resolve the tenant for an Auth-admin operation: the caller's active clinic,
 * and only when they manage it. Chain owners hold MANAGEMENT in more than one
 * clinic, so requiring exactly one membership would have locked the operation
 * to single-clinic managers — the selector decides, the role check still bites.
 */
export function resolveManagementClinic(
  memberships: readonly ClinicMembershipAuthority[],
  requestedClinicId?: string | null,
): string | null {
  const selection = resolveActiveMembership(memberships, requestedClinicId);
  if (selection.status !== "resolved") return null;
  return selection.membership.role === "MANAGEMENT"
    ? selection.membership.clinic_id
    : null;
}
