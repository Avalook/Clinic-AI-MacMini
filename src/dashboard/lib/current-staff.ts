// Resolve the currently-authenticated Supabase user to the staff row
// they're linked to via ``staff.auth_user_id`` (migration 025).
//
// Cached per request with React's ``cache()`` — multiple pages/components
// in the same render tree share one query. Returns ``null`` when the
// user is signed out OR when no staff row is linked (CSKH might log in
// with an account that isn't bound to a staff record yet).
//
// SECURITY: this query goes through the server-side Supabase client,
// which itself runs as the authenticated role. The ``staff`` table is
// not yet RLS-gated (P11 RBAC work), so anyone authenticated reads any
// staff row — the linkage check is purely WHERE auth_user_id = uid.

import { cache } from "react";
import {
  resolveLinkedStaffAuthority,
  resolveSingleActiveMembership,
} from "./identity-authority";
import { getSupabaseServer } from "./supabase-server";

export interface CurrentStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  primary_location_id: string | null;
  auth_user_id: string;
  is_active: boolean;
  clinic_id: string;
  clinic_role: string;
  /** Tên phòng khám + cơ sở, để hiện lên đầu màn hình. */
  clinic_name: string;
  location_name: string;
}

// THREE HELPERS USED TO LIVE HERE AND ALL THREE ARE GONE (audit, 2026-08-03).
//
// isDoctorRole, isAdminRole and roleLanding were duplicated from lib/roles.ts
// with DIFFERENT bodies — this file's isDoctorRole excluded TKYK, roles.ts's
// included it, and roleLanding sent doctors to /appointments?scope=me while
// roles.ts sent them to /tasks. Two exported functions with the same name and
// different answers, distinguished only by which path you happened to import.
// TypeScript cannot catch that; it type-checks either import perfectly.
//
// Nothing imported them (only getCurrentStaff was ever pulled from this file),
// so they were dead code lying in wait for the first person to autocomplete the
// wrong one. lib/roles.ts is the single home for role logic — it is pure, has no
// next/headers dependency, and both server and client components can use it.

/** Memoised per server-render. */
export const getCurrentStaff = cache(async (): Promise<CurrentStaff | null> => {
  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  // Nhúng luôn tên cơ sở: yêu cầu "tài khoản nào cũng phải có phòng khám, cơ sở"
  // chỉ có tác dụng nếu người dùng NHÌN THẤY mình đang ở đâu. Một dòng chữ trên
  // đầu màn hình là thứ ngăn lễ tân đặt lịch cho cơ sở khác mà không biết.
  //
  // MỘT LƯỢT GỌI, KHÔNG PHẢI HAI. Bản trước đọc `staff` rồi mới đọc
  // `clinic_membership` bằng staff.id — hai lượt NỐI TIẾP, vì lượt sau cần kết
  // quả lượt trước. Mỗi lượt tới Supabase (Seoul) mất ~80ms đo từ máy ở Việt
  // Nam, và hàm này chạy trên MỌI trang, MỌI lần điều hướng.
  //
  // clinic_membership.staff_id là khoá ngoại trỏ về staff.id, nên PostgREST
  // nhúng được nó vào cùng truy vấn. Cùng dữ liệu, cùng RLS, cùng phép kiểm
  // `resolveSingleActiveMembership` bên dưới — chỉ bớt một vòng mạng.
  const { data, error } = await supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, primary_location_id," +
        " auth_user_id, is_active," +
        " clinic_location:clinic_location!staff_primary_location_id_fkey ( name )," +
        " clinic_membership:clinic_membership!clinic_membership_staff_id_fkey" +
        " ( clinic_id, role, is_active, clinic:clinic!clinic_membership_clinic_id_fkey ( name ) )",
    )
    .eq("auth_user_id", user.id)
    .eq("clinic_membership.is_active", true)
    .maybeSingle();

  if (error || !data) return null;
  // resolveLinkedStaffAuthority chỉ kiểm quan hệ auth_user_id ↔ staff; hai tên
  // hiển thị được ghép vào sau khi nó đã xác nhận danh tính, nên ép kiểu ở đây
  // bỏ qua chúng có chủ ý.
  const linked = resolveLinkedStaffAuthority(
    user.id,
    data as unknown as Omit<
      CurrentStaff,
      "clinic_id" | "clinic_role" | "clinic_name" | "location_name"
    >,
  );
  if (!linked) return null;

  // Phép kiểm KHÔNG đổi: vẫn đúng hàm ấy, vẫn từ chối khi có 0 hoặc >1 tư cách
  // thành viên đang hoạt động. Chỉ khác chỗ dữ liệu đến từ đâu.
  const memberships = (
    data as unknown as {
      clinic_membership?: {
        clinic_id: string;
        role: string;
        is_active: boolean;
        clinic?: { name?: string } | { name?: string }[];
      }[];
    }
  ).clinic_membership;
  const membership = resolveSingleActiveMembership(memberships ?? []);
  if (!membership) return null;

  const locationRel = (data as { clinic_location?: { name?: string } | { name?: string }[] })
    .clinic_location;
  const location = Array.isArray(locationRel) ? locationRel[0] : locationRel;
  const clinicRel = (
    membership as unknown as { clinic?: { name?: string } | { name?: string }[] }
  ).clinic;
  const clinic = Array.isArray(clinicRel) ? clinicRel[0] : clinicRel;

  return {
    ...linked,
    clinic_id: membership.clinic_id,
    clinic_role: membership.role,
    clinic_name: clinic?.name ?? "",
    location_name: location?.name ?? "",
  };
});
