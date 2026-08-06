// Ai đang đăng nhập — HỎI BACKEND, không tự suy ra lần thứ hai.
//
// Bản trước tự truy vấn Supabase: đọc `staff` theo auth_user_id, nhúng
// `clinic_membership` đang hoạt động, lấy vai từ đó. Đúng bằng luật của
// `get_current_identity` bên FastAPI — viết hai lần, bằng hai ngôn ngữ. Và hai
// bản ấy ĐÃ lệch đúng ở chỗ quan trọng nhất: một mã vai lạ thì backend rơi về
// CSKH (quyền thấp nhất, nhưng vẫn là một phiên làm việc được), còn bản này trả
// null — người dùng bị đá về /login mà không hiểu vì sao. Cùng một dòng dữ
// liệu, hai câu trả lời khác nhau cho câu hỏi "tôi là ai".
//
// Nay chỉ còn một câu trả lời: GET /api/v1/me. Nó xác THỰC token (chữ ký, hạn),
// tra staff → clinic_membership, và có cache 30 giây trong tiến trình api nên
// mỗi lần chuyển trang không phải đi Seoul một vòng.
//
// KHÔNG CÓ ĐƯỜNG LÙI VỀ SUPABASE, CÓ CHỦ Ý. Một đường lùi chính là bản sao thứ
// hai mọc lại — và nó vô ích: mọi route nghiệp vụ của dashboard đã proxy thẳng
// xuống FastAPI không điều kiện (xem backend-proxy.ts), nên khi api chết thì
// mọi nút bấm đã hỏng rồi. Giữ được danh tính trên một ứng dụng không bấm được
// gì chỉ khiến hỏng hóc trông giống bình thường.

import { cache } from "react";
import { fetchFromBackend } from "./backend-proxy";

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

/** Hình dạng GET /api/v1/me trả về (routers/identity.py). */
interface MeResponse {
  staff_id: string;
  auth_user_id: string;
  full_name: string;
  short_name: string;
  department: string;
  role: string;
  clinic_id: string;
  clinic_name: string;
  location_id: string;
  location_name: string;
  can_write_clinical: boolean;
  is_doctor: boolean;
  is_cashier: boolean;
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
  const me = await fetchFromBackend<MeResponse>("/api/v1/me");
  if (!me) return null;

  return {
    id: me.staff_id,
    full_name: me.full_name,
    // Backend trả chuỗi rỗng khi cột trống; kiểu ở đây là `string | null` từ
    // trước và các chỗ gọi dùng `?? full_name`, nên giữ nguyên quy ước null.
    short_name: me.short_name || null,
    primary_department: me.department,
    primary_location_id: me.location_id || null,
    auth_user_id: me.auth_user_id,
    // /me chỉ trả lời cho nhân viên còn hoạt động — truy vấn của nó có
    // `s.is_active IS NOT FALSE`, và không có tư cách thành viên đang hoạt động
    // thì nó 403. Đến được đây tức là còn hoạt động.
    is_active: true,
    clinic_id: me.clinic_id,
    // VAI THEO PHÒNG KHÁM (clinic_membership.role), không phải
    // staff.primary_department. Một bác sĩ có thể là MANAGEMENT ở cơ sở A và
    // DOCTOR ở cơ sở B; chỉ vai của tư cách thành viên đang dùng mới đúng.
    clinic_role: me.role,
    clinic_name: me.clinic_name,
    location_name: me.location_name,
  };
});
