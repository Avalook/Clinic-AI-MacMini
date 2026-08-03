// Shared nav model used by both the desktop sidebar (Nav) and the mobile
// bottom tab bar (BottomNav). Visibility is per-role (see canSeeNav).

import {
  Home,
  ClipboardList,
  UserPlus,
  CheckSquare,
  Calendar,
  BarChart3,
  Settings,
  Contact,
  Stethoscope,
  FlaskConical,
  Activity,
  Pill,
  Tag,
  ScanLine,
  ClipboardCheck,
  ListOrdered,
  CheckCheck,
  Gauge,
  Users,
  Receipt,
  Timer,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { type ClinicRole } from "../../lib/roles";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Shorter label for the cramped bottom bar (falls back to label). */
  shortLabel?: string;
  /** Small tag shown next to the label (e.g. "Đang XD"). */
  badge?: string;
}

export const NAV: NavItem[] = [
  { href: "/home", label: "Trang chủ", shortLabel: "Trang chủ", icon: Home },
  // Bảng chạy trên workflow kernel. Đặt cạnh màn cũ (chưa thay thế) và gắn
  // badge để nhân viên biết đây là bản mới đang chạy song song — bỏ badge khi
  // staff_task được gỡ.
  {
    href: "/reception/queue",
    label: "Hàng đợi tiếp nhận",
    shortLabel: "Hàng đợi",
    icon: Users,
    badge: "Mới",
  },
  {
    href: "/doctor/board",
    label: "Bàn khám",
    shortLabel: "Bàn khám",
    icon: Stethoscope,
    badge: "Mới",
  },
  {
    href: "/cashier/board",
    label: "Bàn thu ngân",
    shortLabel: "Thu ngân",
    icon: Receipt,
    badge: "Mới",
  },
  {
    href: "/cskh-tasks",
    label: "Nhiệm vụ chăm sóc",
    shortLabel: "Chăm sóc",
    icon: ClipboardCheck,
  },
  {
    href: "/appointments",
    label: "Đặt lịch",
    shortLabel: "Đặt lịch",
    icon: ClipboardList,
  },
  {
    href: "/customers",
    label: "Quản lý khách hàng",
    shortLabel: "Khách hàng",
    icon: Contact,
  },
  {
    href: "/patient-list",
    label: "Danh sách bệnh nhân",
    shortLabel: "BN đã khám",
    icon: Stethoscope,
  },
  {
    href: "/patients/new",
    label: "Tạo bệnh nhân",
    shortLabel: "Tạo BN",
    icon: UserPlus,
  },
  // Check-in ĐÃ chuyển lên TRANG CHỦ (HomeCheckin) — không còn ở sidebar.
  {
    href: "/tasks",
    label: "Công việc của tôi",
    shortLabel: "Việc",
    icon: CheckSquare,
  },
  // Số thứ tự GỌI khám — ưu tiên người có hẹn, gọi theo tên (xem chung).
  {
    href: "/queue",
    label: "Số thứ tự gọi khám",
    shortLabel: "Gọi khám",
    icon: ListOrdered,
  },
  // CSKH xác nhận đóng "đợt khám" BS đã khám xong không hẹn lần sau (EPI-01).
  {
    href: "/episodes",
    label: "Đóng đợt khám",
    shortLabel: "Đóng đợt",
    icon: CheckCheck,
  },
  // Trưởng ca (hành chính): theo dõi buổi (read-only).
  {
    href: "/truong-ca",
    label: "Theo dõi buổi",
    shortLabel: "Theo dõi",
    icon: ClipboardCheck,
  },
  // Bảng giá tách 2 trang, đặt NGAY DƯỚI "Công việc của tôi" (sidebar Thu ngân).
  { href: "/cashier/thuoc", label: "Bảng giá thuốc", shortLabel: "Giá thuốc", icon: Pill },
  { href: "/cashier/dich-vu", label: "Bảng giá dịch vụ", shortLabel: "Giá DV", icon: Tag },
  // Nhà thuốc — Dược sĩ (PHARMACIST). Đơn chờ cấp + Chuẩn bị + Kho.
  {
    href: "/pharmacy",
    label: "Đơn thuốc chờ cấp",
    shortLabel: "Đơn thuốc",
    icon: Pill,
    badge: "Mới",
  },
  {
    href: "/pharmacy/inventory",
    label: "Kho & tồn kho",
    shortLabel: "Kho",
    icon: ClipboardList,
    badge: "Mới",
  },
  {
    href: "/pharmacy/history",
    label: "Lịch sử bàn giao",
    shortLabel: "Lịch sử",
    icon: ClipboardCheck,
    badge: "Mới",
  },
  {
    href: "/pharmacy/consult",
    label: "Tư vấn dùng thuốc",
    shortLabel: "Tư vấn",
    icon: CheckCheck,
    badge: "Mới",
  },
  {
    href: "/lab-queue",
    label: "Hàng đợi xét nghiệm",
    shortLabel: "Xét nghiệm",
    icon: FlaskConical,
  },
  {
    href: "/service-queue",
    label: "Hàng đợi dịch vụ",
    shortLabel: "Dịch vụ",
    icon: Activity,
  },
  { href: "/sono", label: "ĐD siêu âm", shortLabel: "Siêu âm", icon: ScanLine },
  { href: "/schedule", label: "Lịch làm việc", shortLabel: "Ca trực", icon: Calendar },
  // Có trong NAV_ROLES (Quản lý + Trưởng ca) nhưng CHƯA TỪNG có mục ở đây, nên
  // trang chỉ vào được bằng cách gõ URL — quyền đã cấp mà không có đường đi.
  {
    href: "/work-sessions",
    label: "Buổi làm việc",
    shortLabel: "Buổi",
    icon: Timer,
  },
  { href: "/reports", label: "Báo cáo", icon: BarChart3 },
  {
    href: "/audit-log",
    label: "Lịch sử thao tác",
    shortLabel: "Lịch sử",
    icon: ClipboardCheck,
    badge: "Mới",
  },
  {
    href: "/result-review",
    label: "Duyệt kết quả",
    shortLabel: "Duyệt KQ",
    icon: CheckCheck,
    badge: "Mới",
  },
  {
    href: "/ops/telemetry",
    label: "Sức khoẻ API",
    shortLabel: "Sức khoẻ",
    icon: Timer,
  },
  { href: "/ops", label: "Vận hành hệ thống", shortLabel: "Hệ thống", icon: Gauge },
  {
    href: "/settings/booking-policy",
    label: "Luật đặt lịch",
    shortLabel: "Luật đặt lịch",
    icon: Calendar,
  },
  { href: "/settings", label: "Cài đặt", icon: Settings },
  {
    href: "/portal",
    label: "Command Center",
    shortLabel: "Trung tâm",
    icon: Zap,
    badge: "Mới",
  },
];

// Nhãn nav theo vai. Wording ĐỒNG BỘ: mọi vai (kể cả điều dưỡng) đều "Tạo bệnh
// nhân" — bỏ khái niệm "khách vãng lai"/"khách hàng".
export function navLabelFor(
  item: NavItem,
  role: ClinicRole | null,
  short = false,
): string {
  if (item.href === "/patients/new" && role === "CSKH") {
    return short ? "Nhập thông tin" : "Nhập thông tin khách hàng mới";
  }
  return short ? (item.shortLabel ?? item.label) : item.label;
}

// Active = exact match, or a nested path with no more-specific nav item also
// matching (so /patients/new highlights itself, not /patients).
export function isActiveNav(
  href: string,
  pathname: string,
  hrefs: string[],
): boolean {
  if (pathname === href) return true;
  if (!pathname.startsWith(href + "/")) return false;
  return !hrefs.some(
    (h) =>
      h !== href &&
      h.startsWith(href + "/") &&
      (pathname === h || pathname.startsWith(h + "/")),
  );
}
