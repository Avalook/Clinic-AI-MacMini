// Server-only readers for the active clinic identity. Legacy cookies are
// retained for compatibility, but never grant authority. Every
// server-side role/staff decision comes from auth.uid() → staff.auth_user_id.

import { redirect } from "next/navigation";
import { cache } from "react";
import { fetchFromBackend } from "./backend-proxy";
import { getCurrentStaff } from "./current-staff";
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

/** VAI LÀM VIỆC HÔM NAY: vai tài khoản + vai vận hành mà vị trí trong lịch hôm
 *  nay cấp (Tuyền chốt 16/09/2026 — tài khoản Điều dưỡng đứng Lễ tân thì làm
 *  được việc lễ tân). Máy chủ tính (`GET /me/vi-tri-hom-nay` → `vai`); ở đây
 *  chỉ ghép, không tự suy vai từ mã vị trí. Không bao giờ chứa vai bác sĩ mà
 *  tài khoản không có. */
export const getVaiHomNay = cache(async (): Promise<ClinicRole[]> => {
  const goc = await getClinicRole();
  if (!goc) return [];
  const d = await fetchFromBackend<{ vai?: string[] }>("/api/v1/me/vi-tri-hom-nay");
  const them = (d?.vai ?? []).filter((v): v is ClinicRole => v !== goc) as ClinicRole[];
  return [goc, ...them];
});

/** Vai đầu tiên trong vai làm việc hôm nay thoả `dieuKien`, hoặc vai tài khoản. */
export async function vaiLamViec(
  dieuKien: (r: ClinicRole) => boolean,
): Promise<ClinicRole | null> {
  const ds = await getVaiHomNay();
  return ds.find(dieuKien) ?? ds[0] ?? null;
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

/** The tenant this session acts in, from the single active clinic_membership.
 *
 *  Only a *filter hint* for the browser (realtime subscriptions narrow on it so
 *  another tenant's writes are dropped server-side instead of crossing the wire
 *  and being refused by RLS). It grants nothing: every read is still bounded by
 *  RLS and every write by identity.py's own membership lookup. */
export async function getClinicId(): Promise<string | null> {
  return (await getCurrentStaff())?.clinic_id ?? null;
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
