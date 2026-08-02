// Which clinic the current session is working in.
//
// Server-only. This cookie is a *selector*, not authority: everything it can
// express is "pick this one of my memberships". Authority still comes from
// auth.uid() → staff.auth_user_id → clinic_membership, on both sides of the
// wire — resolveActiveMembership() here, identity.py there. A forged value
// therefore buys nothing: it either names a clinic the caller is already a
// member of, or it resolves to nothing and the request fails closed.
//
// It exists because the alternative is worse. Deriving the clinic silently
// works only while every staff member has exactly one, and the first doctor
// who works Tuesdays at another branch turns a silent derivation into a
// silent lockout.
//
// LIMIT, stated rather than hidden: this selects the tenant for everything
// that goes through FastAPI (X-Clinic-ID) and for every role decision here.
// It does NOT narrow the direct Supabase reads in app/ — RLS scopes those with
// current_clinic_ids(), which returns *all* of a staff member's clinics. So a
// multi-clinic doctor can work, but their list screens still mix both clinics
// until those queries filter on clinic_id explicitly (Phase C).

import { cookies } from "next/headers";
import { isClinicSelector } from "./identity-authority";

export const ACTIVE_CLINIC_COOKIE = "clinic_active_id";

/** 12h, matching the login cookies: a shift, not a device. */
export const ACTIVE_CLINIC_COOKIE_OPTIONS = {
  path: "/",
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  maxAge: 60 * 60 * 12,
};

/**
 * The selected clinic, or null. Shape-checked here so a junk cookie becomes
 * "nothing selected" instead of a 400 from the backend's UUID parser.
 */
export async function getActiveClinicId(): Promise<string | null> {
  const value = (await cookies()).get(ACTIVE_CLINIC_COOKIE)?.value?.trim();
  return isClinicSelector(value) ? (value as string) : null;
}

/** Server actions and route handlers only — Next forbids writing elsewhere. */
export async function setActiveClinicId(clinicId: string): Promise<void> {
  (await cookies()).set(
    ACTIVE_CLINIC_COOKIE,
    clinicId,
    ACTIVE_CLINIC_COOKIE_OPTIONS,
  );
}

export async function clearActiveClinicId(): Promise<void> {
  (await cookies()).delete(ACTIVE_CLINIC_COOKIE);
}
