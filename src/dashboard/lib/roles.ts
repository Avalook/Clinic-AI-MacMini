// Pure role logic — NO next/headers import, so it is safe to use from both
// Server Components and Client Components (e.g. Nav.tsx).
//
// Access model (post-refactor): ONE shared Supabase login gates the app, then
// the ACTIVE ROLE is app-state chosen at /role-picker and stored in a cookie.
// These helpers operate on that role string, not on a staff row.

export type ClinicRole =
  | "DOCTOR"
  | "ULTRASOUND_DOCTOR"
  | "NURSE_ULTRASOUND"
  | "TKYK"
  | "CSKH"
  | "MANAGEMENT"
  | "RECEPTION"
  | "CASHIER"
  | "CASHIER_THUOC"
  | "CASHIER_DV"
  | "TRUONG_CA";

export const ALL_ROLES: ClinicRole[] = [
  "DOCTOR",
  "ULTRASOUND_DOCTOR",
  "NURSE_ULTRASOUND",
  "TKYK",
  "CSKH",
  "MANAGEMENT",
  "RECEPTION",
  "CASHIER",
  "CASHIER_THUOC",
  "CASHIER_DV",
  "TRUONG_CA",
];

// staff.primary_department → vai trò ứng dụng. Mỗi người chọn tên mình khi
// đăng nhập; vai trò (và nav) suy ra từ chức danh, không tin client.
export function departmentToRole(dept: string | null | undefined): ClinicRole {
  return isClinicRole(dept ?? "") ? (dept as ClinicRole) : "CSKH";
}

export function isClinicRole(v: string | undefined | null): v is ClinicRole {
  return !!v && (ALL_ROLES as string[]).includes(v);
}

const DOCTOR_ROLES = new Set<ClinicRole>(["DOCTOR", "ULTRASOUND_DOCTOR", "TKYK"]);

/** Doctor / ultrasound doctor — can scope appointments to themselves. */
export function isDoctorRole(role: ClinicRole | null): boolean {
  return role !== null && DOCTOR_ROLES.has(role);
}

/** MANAGEMENT only — sees Reports + Settings + Ca trực. */
export function isAdminRole(role: ClinicRole | null): boolean {
  return role === "MANAGEMENT";
}

/** Bác sĩ Siêu âm — nhập số đo siêu âm thai (CRL/NT/BPD/HC/AC/FL/EFW). */
export function isUltrasoundDoctorRole(role: ClinicRole | null): boolean {
  return role === "ULTRASOUND_DOCTOR";
}

/** Điều dưỡng / phụ siêu âm. */
export function isNurseRole(role: ClinicRole | null): boolean {
  return role === "NURSE_ULTRASOUND";
}

/** Thư ký Y khoa (TKYK) — nhập hộ hồ sơ lâm sàng cho bác sĩ. */
export function isThuKyRole(role: ClinicRole | null): boolean {
  return role === "TKYK";
}

/** Ghi LÂM SÀNG (lý do khám, sinh hiệu, bệnh án, KQ xét nghiệm, log SA) = CHỈ
 *  Bác sĩ + Điều dưỡng + Thư ký Y khoa (recap 17/6). Lễ tân / Quản lý làm hành
 *  chính (check-in, hồ sơ hành chính) — KHÔNG ghi lâm sàng. Tách bạch với
 *  canCheckin (đón khách = hành chính, rộng hơn). */
export function canWriteClinical(role: ClinicRole | null): boolean {
  return isDoctorRole(role) || isNurseRole(role) || isThuKyRole(role);
}

/** Roles allowed to create patients / appointments (data entry) + check-in.
 *  ĐIỀU DƯỠNG ĐÃ BỎ (feedback PM 23/6: ĐD không tạo BN, không check-in — đó là việc
 *  Lễ tân; ĐD lo lâm sàng + 3 hàng đợi. Ghi lâm sàng của ĐD vẫn qua canWriteClinical,
 *  KHÔNG phụ thuộc hàm này). */
export function canWriteIntake(role: ClinicRole | null): boolean {
  return (
    role === "CSKH" ||
    role === "RECEPTION" ||
    role === "MANAGEMENT" ||
    role === "TRUONG_CA"
  );
}

/** Trưởng ca — vai VẬN HÀNH: toàn quyền sửa phần vận hành (lịch hẹn, BN, bảng
 *  giá, ca trực, báo cáo) để xử lý phát sinh. Lâm sàng thì CHỈ XEM (KHÔNG có
 *  trong canWriteClinical). */
export function isTruongCaRole(role: ClinicRole | null): boolean {
  return role === "TRUONG_CA";
}

/** Quản trị VẬN HÀNH = Quản lý + Trưởng ca. Trưởng ca có quyền như Quản lý cho
 *  các màn VẬN HÀNH (báo cáo, tra cứu BN, xếp ca, sửa bảng giá…) NHƯNG THẤP HƠN
 *  quản lý hệ thống: KHÔNG vào /settings (tạo user / cấu hình) — đó vẫn chỉ
 *  isAdminRole (MANAGEMENT). Dùng cho các gate vận hành thay cho isAdminRole. */
export function isOpsAdmin(role: ClinicRole | null): boolean {
  return isAdminRole(role) || isTruongCaRole(role);
}

/** Roles lo check-in (đón khách đã đến) = FRONT DESK: Lễ tân + Quản lý.
 *  ĐIỀU DƯỠNG ĐÃ BỎ (feedback PM 23/6: check-in là việc Lễ tân). */
export function canCheckin(role: ClinicRole | null): boolean {
  return role === "RECEPTION" || role === "MANAGEMENT";
}

/** Roles quản trị vòng đời lịch hẹn: HỦY lịch + PHÂN LẠI bác sĩ (CSKH + Quản lý
 *  + Trưởng ca — vận hành, xử lý phát sinh). */
export function canManageAppt(role: ClinicRole | null): boolean {
  return role === "CSKH" || role === "MANAGEMENT" || role === "TRUONG_CA";
}

/** Roles được SỬA thông tin hành chính BN (mục I): nhóm intake (CSKH/Lễ tân/QL/ĐD)
 *  + BÁC SĨ. Bác sĩ KHÔNG tạo BN (canWriteIntake) nhưng được sửa hồ sơ hành chính
 *  (vd trong "Danh sách bệnh nhân"). KHÔNG đụng CCCD/định danh. */
export function canEditPatient(role: ClinicRole | null): boolean {
  return canWriteIntake(role) || isDoctorRole(role);
}

/** Họ thu ngân: CASHIER (superset) + 2 vai tách CASHIER_THUOC / CASHIER_DV.
 *  Dùng cho các quyền/nav chung của thu ngân (xem khách, board read-only…). */
export function isCashierRole(role: ClinicRole | null): boolean {
  return role === "CASHIER" || role === "CASHIER_THUOC" || role === "CASHIER_DV";
}

/** Lễ tân xem "Công việc của tôi" (board bác sĩ) nhưng CHỈ ĐỌC — mọi nút
 *  Nhận/Từ chối/Lưu hồ sơ/Chỉ định XN đều bị khóa. Dùng để clone giao diện
 *  bác sĩ cho front desk mà không cấp quyền ghi. */
export function isTasksReadOnly(role: ClinicRole | null): boolean {
  // Lễ tân + Thu ngân (cả 2 vai tách): xem board "Công việc của tôi" để nắm tình
  // trạng buổi khám, nhưng CHỈ ĐỌC — tránh rơi xuống ConfirmBoard (quản lý lịch).
  return role === "RECEPTION" || isCashierRole(role);
}

/** Landing path after a role is picked. */
export function roleLanding(role: ClinicRole | null): string {
  if (isDoctorRole(role)) return "/tasks";
  // Trưởng ca có màn làm việc riêng (board "Theo dõi buổi") như bác sĩ vào /tasks.
  if (isTruongCaRole(role)) return "/truong-ca";
  return "/home";
}

export const ROLE_LABEL: Record<ClinicRole, string> = {
  DOCTOR: "Bác sĩ",
  ULTRASOUND_DOCTOR: "Bác sĩ Siêu âm",
  NURSE_ULTRASOUND: "Điều dưỡng / Phụ siêu âm",
  TKYK: "Thư ký Y khoa",
  CSKH: "CSKH",
  MANAGEMENT: "Quản lý",
  RECEPTION: "Lễ tân",
  CASHIER: "Thu ngân",
  CASHIER_THUOC: "Thu ngân thuốc",
  CASHIER_DV: "Thu ngân dịch vụ",
  TRUONG_CA: "Trưởng ca",
};

// Which roles may see each sidebar destination. Anything not listed = everyone.
// RECEPTION (Lễ tân) is a front-desk role with a deliberately small menu:
// only Trang chủ + Nhập khách hàng + Check-in. So the broader destinations
// are scoped to everyone-except-reception.
// Lịch làm việc: bác sĩ/điều dưỡng xem ca trực của mình + quản lý xem cả bảng.
// CSKH & Lễ tân KHÔNG xem (sidebar gọn theo đầu việc của họ).
// Bác sĩ (DOCTOR + Bác sĩ siêu âm): việc chính gom ở "Công việc của tôi"
// (/tasks). Thêm "Lịch làm việc" (/schedule) để TỰ đăng ký ca của mình (feedback
// C4). /appointments + /patients/new vẫn KHÔNG cho bác sĩ (chỉ Quản lý / front
// desk). /patients: nav chỉ Quản lý; bác sĩ vào được qua URL (scope BN của
// mình, gate trong page) — CSKH/Lễ tân tra cứu bằng /customers.
const DOCTOR_ROLES_LIST: ClinicRole[] = ["DOCTOR", "ULTRASOUND_DOCTOR", "TKYK"];

const NAV_ROLES: Record<string, "all" | ClinicRole[]> = {
  "/home": "all",
  // "Cần làm hôm nay" — danh sách việc CSKH tự sinh từ dữ liệu (gọi xác nhận,
  // phân lại lịch bị từ chối, tái khám đến hạn, KQ XN mới về).
  "/cskh-today": ["CSKH", "MANAGEMENT", "TRUONG_CA"],
  "/appointments": ["MANAGEMENT", "TRUONG_CA"],
  // Thông tin khách hàng (danh bạ + chi tiết + tra cứu tên/mã/SĐT) — CSKH/Lễ tân/QL
  // + Thu ngân (xem để đối chiếu khi thu tiền; canWriteIntake KHÔNG gồm CASHIER → chỉ xem).
  "/customers": ["CSKH", "RECEPTION", "MANAGEMENT", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TRUONG_CA"],
  // Trưởng ca: theo dõi buổi (read-only). Vai HÀNH CHÍNH, KHÔNG lâm sàng.
  "/truong-ca": ["TRUONG_CA", "MANAGEMENT"],
  // Danh sách bệnh nhân ĐÃ KHÁM (lần đầu / tái khám) — CSKH/Lễ tân/QL + BÁC SĨ.
  // Bác sĩ thấy TOÀN BỘ BN đã khám (như front desk); mở hồ sơ vẫn bị guard
  // patients/[id] (chỉ mở được BN của mình) — đúng mô hình quyền hiện tại.
  // + ĐIỀU DƯỠNG (feedback PM 23/6): nav "Thông tin bệnh nhân" để tra cứu BN +
  // xem lịch sử khám (giống bác sĩ). Sửa lâm sàng/sinh hiệu vẫn theo buổi khám.
  "/patient-list": ["CSKH", "RECEPTION", "MANAGEMENT", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TRUONG_CA", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST],
  // ĐIỀU DƯỠNG ĐÃ BỎ (feedback PM 23/6: ĐD không tạo BN).
  "/patients/new": ["CSKH", "RECEPTION", "MANAGEMENT", "TRUONG_CA"],
  // /checkin đã chuyển hẳn lên Trang chủ (HomeCheckin) — route cũ đã xóa.
  // Lễ tân được THÊM vào: thấy "Công việc của tôi" nhưng ở chế độ CHỈ XEM
  // (clone giao diện board bác sĩ, khóa mọi nút sửa — xem isTasksReadOnly).
  // TKYK (Thư ký Y khoa): vào hàng đợi khám của MỌI bác sĩ để NHẬP HỘ bệnh án
  // (canWriteClinical đã =true). Routing → DoctorWorkBoard (xem tasks/page.tsx).
  "/tasks": ["CSKH", "MANAGEMENT", "RECEPTION", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST],
  // Hàng đợi XN + Dịch vụ: điều dưỡng/KTV thực hiện (+ Quản lý xem).
  "/lab-queue": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  "/service-queue": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  // ĐD siêu âm: hàng đợi BN sắp khám SA + hàng đợi XN 3 trạng thái + in phiếu.
  "/sono": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  // Bảng số thứ tự GỌI KHÁM (ưu tiên người có hẹn). Gọi theo tên — xem chung như /tasks.
  // TẠM ẨN (Quang 2026-07-03): [] = không vai nào thấy sidebar + gõ URL bị redirect
  // /home (requireNavAccess). Mở lại: khôi phục danh sách vai dưới đây.
  // ["CSKH", "MANAGEMENT", "RECEPTION", "TRUONG_CA", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST]
  "/queue": [],
  // Đóng "đợt khám" chờ xác nhận (BS khám xong không hẹn lần sau) — việc CSKH/vận hành.
  "/episodes": ["CSKH", "MANAGEMENT", "TRUONG_CA"],
  // Thu ngân: bảng giá tách 2 trang (thuốc / dịch vụ), gate theo VAI tách (mỗi
  // vai chỉ thấy màn của mình). CASHIER = superset (thấy cả hai), Quản lý xem/sửa cả hai.
  // ("Công việc của tôi" thu ngân nằm ở /tasks, gate bằng entry /tasks bên dưới.)
  "/cashier/thuoc": ["CASHIER_THUOC", "CASHIER", "MANAGEMENT", "TRUONG_CA"],
  "/cashier/dich-vu": ["CASHIER_DV", "CASHIER", "MANAGEMENT", "TRUONG_CA"],
  // MỌI vai trò tự đăng ký ca của mình (CSKH, thu ngân... cũng cần); Quản lý +
  // Trưởng ca xếp cả bảng. Ca tự đăng ký vào trạng thái chờ duyệt (xem /api/roster).
  "/schedule": "all",
  "/work-sessions": ["MANAGEMENT", "TRUONG_CA"],
  "/reports": ["MANAGEMENT", "TRUONG_CA"],
  // Cài đặt (tạo user / cấu hình hệ thống) = CHỈ Quản lý — ranh giới "thấp hơn
  // quản lý hệ thống" của Trưởng ca.
  "/settings": ["MANAGEMENT"],
};

export function canSeeNav(role: ClinicRole | null, href: string): boolean {
  const rule = NAV_ROLES[href];
  if (!rule || rule === "all") return true;
  return role !== null && rule.includes(role);
}
