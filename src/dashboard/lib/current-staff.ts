// Resolve the currently-authenticated Supabase user to the staff row
// they're linked to via ``staff.auth_user_id`` (migration 025), and to the
// clinic that session is working in.
//
// Cached per request with React's ``cache()`` — multiple pages/components
// in the same render tree share one query. Returns ``null`` when the
// user is signed out OR when no staff row is linked (CSKH might log in
// with an account that isn't bound to a staff record yet).
//
// SECURITY: this query goes through the server-side Supabase client,
// which itself runs as the authenticated role. The ``staff`` table is
// not yet RLS-gated (P11 RBAC work), so anyone authenticated reads any
// staff row — the linkage check is purely WHERE auth_user_id = uid.

import { cache } from "react";
import { getActiveClinicId } from "./active-clinic";
import {
  resolveActiveMembership,
  resolveLinkedStaffAuthority,
  type ClinicMembershipAuthority,
} from "./identity-authority";
import { getSupabaseServer } from "./supabase-server";

export interface CurrentStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  primary_location_id: string | null;
  auth_user_id: string;
  is_active: boolean;
  clinic_id: string;
  clinic_role: string;
}

/**
 * Who is asking, and from which clinic.
 *
 * ``must_choose_clinic`` is deliberately not ``null``: a staff member with two
 * active memberships is fully authorized and simply has not said where they
 * are working today. Collapsing that into "no identity" is what redirected
 * multi-clinic doctors to /login with no explanation.
 */
export type StaffContext =
  | { status: "anonymous" }
  | {
      status: "resolved";
      staff: CurrentStaff;
      /** Every clinic this login could switch to, including the current one. */
      choices: ClinicMembershipAuthority[];
    }
  | { status: "must_choose_clinic"; choices: ClinicMembershipAuthority[] };

const DOCTOR_DEPTS = new Set(["DOCTOR", "ULTRASOUND_DOCTOR"]);
const ADMIN_DEPTS = new Set(["MANAGEMENT"]);

/** Departments allowed to filter the appointments view by themselves. */
export function isDoctorRole(staff: CurrentStaff | null): boolean {
  return staff !== null && DOCTOR_DEPTS.has(staff.clinic_role);
}

/** MANAGEMENT only — sees Reports + Settings nav items. */
export function isAdminRole(staff: CurrentStaff | null): boolean {
  return staff !== null && ADMIN_DEPTS.has(staff.clinic_role);
}

/** The role-aware default landing path after login. */
export function roleLanding(staff: CurrentStaff | null): string {
  if (isDoctorRole(staff)) return "/appointments?scope=me";
  if (staff?.clinic_role === "CSKH") return "/tasks";
  return "/home";
}

/** Memoised per server-render. */
export const getStaffContext = cache(async (): Promise<StaffContext> => {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { status: "anonymous" };

  const { data, error } = await supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, primary_location_id, auth_user_id, is_active",
    )
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (error || !data) return { status: "anonymous" };
  const linked = resolveLinkedStaffAuthority(
    user.id,
    data as Omit<CurrentStaff, "clinic_id" | "clinic_role">,
  );
  if (!linked) return { status: "anonymous" };

  const { data: memberships, error: membershipError } = await supabase
    .from("clinic_membership")
    .select("clinic_id, role, is_active")
    .eq("staff_id", linked.id)
    .eq("is_active", true);
  if (membershipError) return { status: "anonymous" };

  const active = (memberships ?? []).filter((m) => m.is_active);
  const selection = resolveActiveMembership(active, await getActiveClinicId());
  if (selection.status === "none") return { status: "anonymous" };
  if (selection.status === "ambiguous") {
    return { status: "must_choose_clinic", choices: selection.choices };
  }

  return {
    status: "resolved",
    staff: {
      ...linked,
      clinic_id: selection.membership.clinic_id,
      clinic_role: selection.membership.role,
    },
    choices: active,
  };
});

/**
 * The staff row for a request that can proceed. Still null while the clinic is
 * unchosen — callers that need to tell the two apart read getStaffContext()
 * and send the user to the picker.
 */
export const getCurrentStaff = cache(async (): Promise<CurrentStaff | null> => {
  const context = await getStaffContext();
  return context.status === "resolved" ? context.staff : null;
});
