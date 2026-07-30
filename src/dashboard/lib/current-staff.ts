// Resolve the currently-authenticated Supabase user to the staff row
// they're linked to via ``staff.auth_user_id`` (migration 025).
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
import {
  resolveLinkedStaffAuthority,
  resolveSingleActiveMembership,
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
export const getCurrentStaff = cache(async (): Promise<CurrentStaff | null> => {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data, error } = await supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, primary_location_id, auth_user_id, is_active",
    )
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (error || !data) return null;
  const linked = resolveLinkedStaffAuthority(
    user.id,
    data as Omit<CurrentStaff, "clinic_id" | "clinic_role">,
  );
  if (!linked) return null;

  const { data: memberships, error: membershipError } = await supabase
    .from("clinic_membership")
    .select("clinic_id, role, is_active")
    .eq("staff_id", linked.id)
    .eq("is_active", true);
  const membership = resolveSingleActiveMembership(memberships ?? []);
  if (membershipError || !membership) return null;

  return {
    ...linked,
    clinic_id: membership.clinic_id,
    clinic_role: membership.role,
  };
});
