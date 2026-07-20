"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../lib/clinic-session";
import { getCurrentStaff } from "../../lib/current-staff";
import { departmentToRole, roleLanding } from "../../lib/roles";

// Legacy action retained for already-cached clients. The submitted staffId is
// deliberately ignored: only auth.uid() → staff.auth_user_id may set identity.
export async function chooseStaffIdentity(): Promise<void> {
  const staff = await getCurrentStaff();
  if (!staff) redirect("/login");

  const role = departmentToRole(staff.primary_department);

  const c = await cookies();
  const opts = {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 12, // one clinic workday
  };
  c.set(ROLE_COOKIE, role, opts);
  c.set(STAFF_COOKIE, staff.id, opts);
  redirect(roleLanding(role));
}
