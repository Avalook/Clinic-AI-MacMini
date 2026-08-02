"use server";

// Clinic access gate. The "shared clinic password" is the password of ONE
// shared Supabase Auth account (email kept server-side in CLINIC_SHARED_EMAIL).
// Signing in establishes the clinic-gate session; each staff member must then
// authenticate personally and be linked through staff.auth_user_id.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../../lib/clinic-session";
import { ACTIVE_CLINIC_COOKIE } from "../../../lib/active-clinic";

export async function enterClinic(
  _prev: { error: string } | null,
  formData: FormData,
): Promise<{ error: string } | null> {
  const password = String(formData.get("password") ?? "");
  const email = process.env.CLINIC_SHARED_EMAIL;
  if (!email) {
    return {
      error:
        "Server chưa cấu hình CLINIC_SHARED_EMAIL. Thêm vào .env.local rồi khởi động lại.",
    };
  }
  if (!password) return { error: "Nhập mật khẩu phòng khám." };

  const supabase = await getSupabaseServer();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { error: "Mật khẩu không đúng." };

  // Cổng phòng khám đã mở (session chung). Giờ mỗi người đăng nhập cá nhân.
  redirect("/login");
}

// Sign out + forget the picked role so the next person starts clean.
export async function leaveClinic(): Promise<void> {
  const supabase = await getSupabaseServer();
  await supabase.auth.signOut();
  const c = await cookies();
  c.delete(ROLE_COOKIE);
  c.delete(STAFF_COOKIE);
  // Người tiếp theo trên cùng máy này phải chọn lại nơi làm việc của họ.
  c.delete(ACTIVE_CLINIC_COOKIE);
  redirect("/enter");
}
