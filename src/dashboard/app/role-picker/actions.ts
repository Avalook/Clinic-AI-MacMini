"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../lib/clinic-session";
import { departmentToRole, roleLanding } from "../../lib/roles";
import { getSupabaseServer } from "../../lib/supabase-server";

// Mỗi người chọn ĐÚNG TÊN MÌNH từ danh sách. Vai trò + không gian làm việc suy
// ra từ chức danh (primary_department) đọc THẲNG từ DB — không tin client.
export async function chooseStaffIdentity(formData: FormData): Promise<void> {
  const staffId = String(formData.get("staffId") ?? "").trim();
  if (!staffId) redirect("/role-picker");

  const supabase = await getSupabaseServer();
  const { data: staff } = await supabase
    .from("staff")
    .select("id, primary_department, is_active")
    .eq("id", staffId)
    .maybeSingle();
  if (!staff || staff.is_active === false) redirect("/role-picker");

  const role = departmentToRole(staff.primary_department as string);

  const c = await cookies();
  const opts = {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    maxAge: 60 * 60 * 12, // one clinic workday
  };
  c.set(ROLE_COOKIE, role, opts);
  c.set(STAFF_COOKIE, staffId, opts);
  redirect(roleLanding(role));
}
