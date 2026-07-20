"use server";

// Clinic access gate. The "shared clinic password" is the password of ONE
// shared Supabase Auth account (email kept server-side in CLINIC_SHARED_EMAIL).
// Signing in establishes the authenticated session that RLS requires; the
// per-person role is then chosen at /role-picker.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { ROLE_COOKIE, STAFF_COOKIE } from "../../../lib/clinic-session";

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
  redirect("/enter");
}
