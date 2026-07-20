"use server";

// Đăng nhập CÁ NHÂN (email + mật khẩu do quản lý tạo ở Cài đặt). Sau khi vào
// "cổng" phòng khám (/enter), mỗi nhân viên đăng nhập tài khoản của mình → vào
// thẳng phần việc. Vai trò suy từ staff gắn với tài khoản (auth_user_id),
// không cần chọn tên.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../../lib/clinic-session";
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
    .select("id, primary_department, is_active")
    .eq("auth_user_id", data.user.id)
    .maybeSingle();

  if (!staff) {
    await supabase.auth.signOut();
    return { error: "Tài khoản chưa gắn với nhân viên. Liên hệ quản lý." };
  }
  if (staff.is_active === false) {
    await supabase.auth.signOut();
    return { error: "Tài khoản đã bị khoá." };
  }

  const role = departmentToRole(staff.primary_department as string);
  const opts = {
    path: "/",
    httpOnly: true,
    sameSite: "lax" as const,
    maxAge: 60 * 60 * 12,
  };
  const c = await cookies();
  c.set(ROLE_COOKIE, role, opts);
  c.set(STAFF_COOKIE, staff.id as string, opts);

  redirect(roleLanding(role));
}
