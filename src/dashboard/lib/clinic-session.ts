// Server-only readers for the active clinic identity. Legacy cookies are
// retained for compatibility, but never grant authority. Every
// server-side role/staff decision comes from auth.uid() → staff.auth_user_id.

import { redirect } from "next/navigation";
import { cache } from "react";
import { fetchFromBackend } from "./backend-proxy";
import { docDuocYKhoa } from "./quyen-cua-toi";
import { getCurrentStaff } from "./current-staff";
import {
  departmentToRole,
  canSeeNav,
  quyenMoDuocMan,
  type ClinicRole,
} from "./roles";
import { type ViTriDb } from "./roster";
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
export const getViTriHomNay = cache(() =>
  fetchFromBackend<{
    vi_tri: string[];
    ca: string[];
    vai?: string[];
    /** Phòng của từng vị trí (theo `room_id`, CORE-C 23/09/2026). */
    phong?: Record<string, { room_id: string; ten: string }>;
    /** Danh mục vị trí của phòng khám (`vi_tri_lam_viec`, CORE-C4). */
    danh_muc?: ViTriDb[];
  }>(
    "/api/v1/me/vi-tri-hom-nay",
  ),
);

export const getVaiHomNay = cache(async (): Promise<ClinicRole[]> => {
  const goc = await getClinicRole();
  if (!goc) return [];
  const d = await getViTriHomNay();
  // VAI THEO VỊ TRÍ ĐỨNG TRƯỚC, theo thứ tự máy chủ xếp (Lễ tân → Điều dưỡng →
  // Trưởng ca; có thể gồm cả vai trùng vai tài khoản). Vai tài khoản đứng cuối
  // nếu hôm nay không vị trí nào mang nó — vẫn còn đó cho mọi quyền vốn có.
  const theo = (d?.vai ?? []) as ClinicRole[];
  return theo.includes(goc) ? theo : [...theo, goc];
});

/** VAI CHÍNH HÔM NAY — vai quyết định HIỂN THỊ (trang chủ, nhãn vai, bảng việc).
 *  Có ca: vai của vị trí đầu tiên trong ngày. Không ca: vai tài khoản.
 *  Dùng cho quyết định "vẽ màn nào"; quyết định "được làm không" dùng
 *  `vaiLamViec` (xét MỌI vai hôm nay). */
export async function getVaiChinh(): Promise<ClinicRole | null> {
  return (await getVaiHomNay())[0] ?? null;
}

/** Vai đầu tiên trong vai làm việc hôm nay thoả `dieuKien`, hoặc vai tài khoản. */
export async function vaiLamViec(
  dieuKien: (r: ClinicRole) => boolean,
): Promise<ClinicRole | null> {
  const ds = await getVaiHomNay();
  return ds.find(dieuKien) ?? ds[0] ?? null;
}

/** QUYỀN ĐANG CÓ của người đăng nhập (capability, không phải vai).
 *
 *  Máy chủ tính; ở đây chỉ đọc. Hỏng thì trả rỗng — nghĩa là chỉ còn cửa vai,
 *  y như trước khi có mô hình quyền. Một lần mạng chập không được làm cả phòng
 *  khám mất thanh bên.
 *
 *  `cache()` theo lượt dựng trang: một lần mở /home hỏi đúng một lần. */
export const getQuyenCuaToi = cache(async (): Promise<string[]> => {
  const d = await fetchFromBackend<{ quyen: string[] }>("/api/v1/phan-quyen/toi");
  return d?.quyen ?? [];
});

/** Server-side guard cho 1 trang theo nav href: role không được phép → về /home.
 *  Trước đây các route chỉ ẩn ở sidebar (canSeeNav) → gõ thẳng URL vẫn vào & lộ
 *  PII/kết quả lab. Gọi ĐẦU mỗi page bị giới hạn role để chặn cả truy cập trực tiếp. */
export async function requireNavAccess(href: string): Promise<void> {
  // Vào được nếu MỘT trong các vai hôm nay vào được — vai tài khoản vẫn nằm
  // trong tập này, nên không ai mất lối vào cũ.
  const vai = await getVaiHomNay();
  if (vai.some((r) => canSeeNav(r, href))) return;
  // CỬA THỨ HAI: quản lý cấp khối Siêu âm cho lễ tân thì lễ tân vào được màn
  // siêu âm, dù NAV_ROLES không có vai ấy. Mở thêm, không thay — ai vào được
  // theo vai thì đã về ở dòng trên.
  if (quyenMoDuocMan(await getQuyenCuaToi(), href)) return;
  if (vai.length === 0 && canSeeNav(null, href)) return;
  redirect("/home");
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

/** Guard a surface that renders the medical note, not merely operational PII.
 *  24/09/2026: hỏi QUYỀN (có khối khám / kết quả), không hỏi vai — quản lý có
 *  đủ khối nên mở được (Tuyền chốt). Backend vẫn tự kiểm lại. */
export async function requireClinicalRole(): Promise<ClinicRole> {
  const role = await requireClinicRole();
  if (!(await docDuocYKhoa())) redirect("/home");
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
