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
  {
    href: "/appointments",
    label: "Lịch hẹn (check đặt lịch)",
    shortLabel: "Lịch hẹn",
    icon: ClipboardList,
  },
  {
    href: "/customers",
    label: "Thông tin khách hàng",
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
  { href: "/reports", label: "Báo cáo", icon: BarChart3 },
  { href: "/settings", label: "Cài đặt", icon: Settings },
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
