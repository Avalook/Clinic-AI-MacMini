"use server";

// Đăng nhập CÁ NHÂN (email + mật khẩu do quản lý tạo ở Cài đặt) — cổng DUY
// NHẤT vào hệ thống từ 05/08/2026. Vai trò suy từ staff gắn với tài khoản
// (auth_user_id), không cần chọn tên.

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../../lib/clinic-session";
import { laHostGiamSat } from "../../../lib/cong-giam-sat";
import { LOCATION_COOKIE } from "../../../lib/co-so";
import {
  resolveLinkedStaffAuthority,
  resolveSingleActiveMembership,
} from "../../../lib/identity-authority";
import { departmentToRole, roleLanding } from "../../../lib/roles";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { emailTuTenDangNhap } from "../../../lib/ten-dang-nhap";

export async function loginStaff(
  _prev: { error: string } | null,
  formData: FormData,
): Promise<{ error: string } | null> {
  // TÊN TRẦN CŨNG ĐĂNG NHẬP ĐƯỢC. Quản lý nay đặt được nick không có đuôi mail
  // (Quang 09/08/2026), nên chỗ tra cũng phải gắn đuôi bằng ĐÚNG hàm ấy —
  // không thì nick vừa đặt xong gõ vào đây lại bị từ chối. Có sẵn "@" thì giữ
  // nguyên, nên tài khoản đuôi `.local` vẫn vào như cũ.
  const nick = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");
  const email = emailTuTenDangNhap(nick);
  if (!email || !password) return { error: "Nhập tên đăng nhập và mật khẩu." };

  const supabase = await getSupabaseServer();
  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });
  if (error || !data.user)
    return { error: "Tên đăng nhập hoặc mật khẩu không đúng." };

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
  // Mỗi lần đăng nhập chọn lại cơ sở (08/10/2026, hai cơ sở): cơ sở của người
  // trước trên cùng máy không được đi theo người sau. `/chon-co-so` tự đi thẳng
  // khi phòng khám chỉ có một cơ sở.
  c.delete(LOCATION_COOKIE);

  // Đăng nhập ở tên miền giám sát → về thẳng trung tâm giám sát (09/10/2026).
  const dich = laHostGiamSat((await headers()).get("host")) ? "/giam-sat" : roleLanding(role);
  redirect(`/chon-co-so?next=${encodeURIComponent(dich)}`);
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
  c.delete(LOCATION_COOKIE);
  redirect("/login");
}
