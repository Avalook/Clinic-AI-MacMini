// Server-only readers for the active clinic role (cookie-based app-state).
// The shared Supabase session gates the app (RLS); the role cookie decides
// which UI/scope to show. Identity for doctor scope = clinic_staff_id, which
// replaces the old staff.auth_user_id linkage.

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { isClinicRole, canSeeNav, type ClinicRole } from "./roles";
import { getSupabaseServer } from "./supabase-server";

export const ROLE_COOKIE = "clinic_role";
export const STAFF_COOKIE = "clinic_staff_id";

export async function getClinicRole(): Promise<ClinicRole | null> {
  const v = (await cookies()).get(ROLE_COOKIE)?.value;
  return isClinicRole(v) ? v : null;
}

/** Server-side guard cho 1 trang theo nav href: role không được phép → về /home.
 *  Trước đây các route chỉ ẩn ở sidebar (canSeeNav) → gõ thẳng URL vẫn vào & lộ
 *  PII/kết quả lab. Gọi ĐẦU mỗi page bị giới hạn role để chặn cả truy cập trực tiếp. */
export async function requireNavAccess(href: string): Promise<void> {
  const role = await getClinicRole();
  if (!canSeeNav(role, href)) redirect("/home");
}

/** Guard cho trang NGOÀI nhóm (dashboard) (vd /print/*) — nơi layout gác quyền
 *  KHÔNG chạy. Bắt buộc: (1) có phiên Supabase thật (auth.getUser), (2) đã chọn
 *  vai lâm sàng. Thiếu phiên → /login; thiếu vai → /role-picker. Trước đây các
 *  trang in đọc PII + hồ sơ khám mà KHÔNG kiểm tra gì (chỉ dựa RLS) — gõ URL là
 *  xem được. Trả về role để caller dùng tiếp nếu cần. */
export async function requireClinicRole(): Promise<ClinicRole> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  const role = await getClinicRole();
  if (!role) redirect("/role-picker");
  return role;
}

/** Selected doctor's staff.id (only set when a doctor role was picked). */
export async function getClinicStaffId(): Promise<string | null> {
  return (await cookies()).get(STAFF_COOKIE)?.value ?? null;
}

export interface ActiveStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
}

/** The staff row for the picked doctor identity, or null (non-doctor roles). */
export async function getActiveStaff(): Promise<ActiveStaff | null> {
  const staffId = await getClinicStaffId();
  if (!staffId) return null;
  const supabase = await getSupabaseServer();
  const { data } = await supabase
    .from("staff")
    .select("id, full_name, short_name, primary_department")
    .eq("id", staffId)
    .maybeSingle();
  return (data as ActiveStaff | null) ?? null;
}
