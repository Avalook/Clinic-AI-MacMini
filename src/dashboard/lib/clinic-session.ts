// Server-only readers for the active clinic identity. Legacy cookies are
// retained for compatibility, but never grant authority. Every
// server-side role/staff decision comes from auth.uid() → staff.auth_user_id.

import { redirect } from "next/navigation";
import { getCurrentStaff, getStaffContext } from "./current-staff";
import {
  departmentToRole,
  canReadClinical,
  canSeeNav,
  type ClinicRole,
} from "./roles";
import { getSupabaseServer } from "./supabase-server";

export const ROLE_COOKIE = "clinic_role";
export const STAFF_COOKIE = "clinic_staff_id";

export async function getClinicRole(): Promise<ClinicRole | null> {
  const staff = await getCurrentStaff();
  return staff ? departmentToRole(staff.clinic_role) : null;
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
 *  vai lâm sàng. Thiếu phiên hoặc staff liên kết → /login. Trước đây các
 *  trang in đọc PII + hồ sơ khám mà KHÔNG kiểm tra gì (chỉ dựa RLS) — gõ URL là
 *  xem được. Trả về role để caller dùng tiếp nếu cần. */
export async function requireClinicRole(): Promise<ClinicRole> {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");
  // Trang in nằm ngoài (dashboard), nên layout không hỏi hộ được: người làm ở
  // nhiều phòng khám phải được hỏi ở đây, thay vì bị coi như chưa đăng nhập.
  const context = await getStaffContext();
  if (context.status === "must_choose_clinic") redirect("/choose-clinic");
  const role = await getClinicRole();
  if (!role) redirect("/login");
  return role;
}

/** Guard a surface that renders the medical note, not merely operational PII. */
export async function requireClinicalRole(): Promise<ClinicRole> {
  const role = await requireClinicRole();
  if (!canReadClinical(role)) redirect("/home");
  return role;
}

/** Authoritative staff.id linked to the authenticated user. */
export async function getClinicStaffId(): Promise<string | null> {
  return (await getCurrentStaff())?.id ?? null;
}

export interface ActiveStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
}

/** The staff row linked to the authenticated user. */
export async function getActiveStaff(): Promise<ActiveStaff | null> {
  const staff = await getCurrentStaff();
  if (!staff) return null;
  return {
    id: staff.id,
    full_name: staff.full_name,
    short_name: staff.short_name,
    primary_department: staff.primary_department,
  };
}
