// Server-only readers for the active clinic identity. Legacy cookies are
// retained for compatibility, but never grant authority. Every
// server-side role/staff decision comes from auth.uid() → staff.auth_user_id.

import { redirect } from "next/navigation";
import { cache } from "react";
import { fetchFromBackend } from "./backend-proxy";
import { docDuocYKhoa, inDuocPhieu } from "./quyen-cua-toi";
import { getCurrentStaff } from "./current-staff";
import { departmentToRole, vaoDuocMan, type ClinicRole } from "./roles";
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
    /** Mọi vai hiệu lực, đã tính lego đang bật (26/09/2026). */
    vai_hieu_luc?: string[];
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
  const hieuLuc = d?.vai_hieu_luc as ClinicRole[] | undefined;
  // Máy chủ cũ chưa trả vai hiệu lực: giữ luật cũ.
  if (!hieuLuc) return theo.includes(goc) ? theo : [...theo, goc];
  // VAI THEO LEGO (Tuyền chốt 26/09/2026 — "chỉ cần lego"): thứ tự = vị trí
  // hôm nay, rồi vai tài khoản (nếu lego còn giữ nó), rồi vai lego mang lại.
  // Vai tài khoản mà lego đã tắt KHÔNG còn ở đây — cùng luật cửa gác máy chủ.
  const ra = theo.filter((v) => hieuLuc.includes(v));
  if (hieuLuc.includes(goc) && !ra.includes(goc)) ra.push(goc);
  for (const v of hieuLuc) if (!ra.includes(v)) ra.push(v);
  return ra;
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

/** "Vai" cho nút bấm ở Bàn khám / Bàn khám tư vấn — theo QUYỀN (Tuyền 28/09/2026:
 *  thư ký, bác sĩ, điều dưỡng xếp cùng phòng "bản chất node giống nhau, thao
 *  tác như nhau, song song"). Có quyền chỉ định → dùng như bác sĩ; chỉ có quyền
 *  khám → như thư ký; không có → vai tài khoản như trước. Máy chủ vẫn tự kiểm
 *  quyền ở mọi lệnh — đây chỉ là để không khoá nút của người có quyền. */
export async function vaiBanKham(): Promise<ClinicRole | null> {
  const quyen = await getQuyenCuaToi();
  if (quyen?.includes("clinical.order.place")) return "DOCTOR";
  if (quyen?.includes("clinical.consult.perform")) return "TKYK";
  return vaiLamViec((r) => r === "DOCTOR" || r === "TKYK");
}

/** QUYỀN ĐANG CÓ của người đăng nhập (capability, không phải vai).
 *
 *  Máy chủ tính; ở đây chỉ đọc. Hỏng thì trả rỗng — nghĩa là chỉ còn cửa vai,
 *  y như trước khi có mô hình quyền. Một lần mạng chập không được làm cả phòng
 *  khám mất thanh bên.
 *
 *  `cache()` theo lượt dựng trang: một lần mở /home hỏi đúng một lần. */
/** Quyền của người đang đăng nhập. `null` = máy chủ không trả lời (khác với
 *  `[]` = biết chắc không có quyền nào) — thanh bên dựng theo lego cần phân biệt. */
export const getQuyenCuaToi = cache(async (): Promise<string[] | null> => {
  const d = await fetchFromBackend<{ quyen: string[] }>("/api/v1/phan-quyen/toi");
  return d?.quyen ?? null;
});

/** Server-side guard cho 1 trang theo nav href: không được vào → về /home.
 *  Trước đây các route chỉ ẩn ở sidebar (canSeeNav) → gõ thẳng URL vẫn vào & lộ
 *  PII/kết quả lab. Gọi ĐẦU mỗi page bị giới hạn để chặn cả truy cập trực tiếp.
 *
 *  Luật nằm ở `vaoDuocMan` (lib/roles.ts, hàm thuần — có bài kiểm): màn thuộc
 *  lego CHỈ hỏi lego của tài khoản (27/09/2026), màn ngoài lego giữ luật vai. */
export async function requireNavAccess(href: string): Promise<void> {
  if (await moDuocMan(href)) return;
  redirect("/home");
}

/** Người đang đăng nhập mở được màn này không — cùng luật với `requireNavAccess`,
 *  cho chỗ cần HỎI (vd ô số ở trang chủ chỉ gắn link khi đích mở được). */
export async function moDuocMan(href: string): Promise<boolean> {
  const [vai, quyen] = await Promise.all([getVaiHomNay(), getQuyenCuaToi()]);
  return vaoDuocMan(href, vai, quyen);
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

/** Cửa trang IN PHIẾU KHÁM: đọc được y khoa, hoặc làm một khâu quầy (tiếp đón /
 *  thu tiền / nhà thuốc) — in cho khách ở mọi khâu (Tuyền 27/09/2026). */
export async function requireInPhieu(): Promise<ClinicRole> {
  const role = await requireClinicRole();
  if (!(await inDuocPhieu())) redirect("/home");
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
