"use server";

// Đăng nhập CÁ NHÂN (email + mật khẩu do quản lý tạo ở Cài đặt) — cổng DUY
// NHẤT vào hệ thống từ 05/08/2026. Vai trò suy từ staff gắn với tài khoản
// (auth_user_id), không cần chọn tên.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../../lib/clinic-session";
import {
  resolveLinkedStaffAuthority,
  resolveSingleActiveMembership,
} from "../../../lib/identity-authority";
import { departmentToRole, roleLanding } from "../../../lib/roles";
import { getSupabaseServer } from "../../../lib/supabase-server";

export async function loginStaff(
  _prev: { error: string } | null,
  formData: FormData,
): Promise<{ error: string } | null> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) return { error: "Nhập email và mật khẩu." };

  const supabase = await getSupabaseServer();
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  if (error || !data.user) return { error: "Email hoặc mật khẩu không đúng." };

  // Tài khoản phải gắn với 1 nhân viên (staff.auth_user_id).
  const { data: staff } = await supabase
    .from("staff")
    .select("id, primary_department, is_active, auth_user_id")
    .eq("auth_user_id", data.user.id)
    .maybeSingle();

  const identity = resolveLinkedStaffAuthority(data.user.id, staff);
  if (!identity) {
    await supabase.auth.signOut();
    return { error: "Tài khoản chưa gắn với nhân viên. Liên hệ quản lý." };
  }

  const { data: memberships, error: membershipError } = await supabase
    .from("clinic_membership")
    .select("clinic_id, role, is_active")
    .eq("staff_id", identity.id)
    .eq("is_active", true);
  const membership = resolveSingleActiveMembership(memberships ?? []);
  if (membershipError || !membership) {
    await supabase.auth.signOut();
    return {
      error:
        "Tài khoản phải có đúng một phòng khám đang hoạt động. Liên hệ quản lý.",
    };
  }

  const role = departmentToRole(membership.role);
  if (!role) {
    await supabase.auth.signOut();
    return { error: "Vai trò nhân viên không hợp lệ. Liên hệ quản lý." };
  }
  const opts = {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 12,
  };
  const c = await cookies();
  c.set(ROLE_COOKIE, role, opts);
  c.set(STAFF_COOKIE, identity.id, opts);

  redirect(roleLanding(role));
}

// Đăng xuất. Trước đây nằm ở `enter/actions.ts` cùng cổng phòng khám dùng
// chung; cổng đã bỏ (05/08/2026) nên nó về ở cạnh đường đăng nhập duy nhất.
export async function logout(): Promise<void> {
  const supabase = await getSupabaseServer();
  await supabase.auth.signOut();
  // Xoá cả hai cookie: người sau ngồi vào máy phải đăng nhập lại từ đầu, chứ
  // không thừa hưởng vai của người trước.
  const c = await cookies();
  c.delete(ROLE_COOKIE);
  c.delete(STAFF_COOKIE);
  redirect("/login");
}
