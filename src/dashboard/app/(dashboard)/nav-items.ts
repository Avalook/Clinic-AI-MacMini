// Shared nav model used by both the desktop sidebar (Nav) and the mobile
// bottom tab bar (BottomNav). Visibility is per-role (see canSeeNav).

import {
  Home,
  ClipboardList,
  UserPlus,
  CheckSquare,
  Calendar,
  CalendarRange,
  BarChart3,
  Settings,
  KeyRound,
  Contact,
  Stethoscope,
  FlaskConical,
  Activity,
  Pill,
  Tag,
  ScanLine,
  ClipboardCheck,
  LayoutDashboard,
  Rows3,
  AlertTriangle,
  History,
  Tv,
  ListOrdered,
  CheckCheck,
  Gauge,
  Users,
  Receipt,
  Timer,
  Zap,
  Building2,
  PhoneCall,
  type LucideIcon,
} from "lucide-react";
import { type ClinicRole } from "../../lib/roles";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  // KHÔNG CÓ `shortLabel`. Bỏ ngày 14/08/2026 vì nó cho phép MỘT nút mang HAI
  // tên, và ba nút đã trôi thành tên khác hẳn: "Danh sách bệnh nhân" hiện là
  // "BN đã khám", "Lịch làm việc" thành "Ca trực", "Command Center" thành
  // "Trung tâm". Hai cặp nút khác nhau còn trùng tên nhau ("Hàng đợi" cho cả
  // /reception/queue lẫn /truong-ca/hang-doi; "Lịch sử" cho cả /audit-log lẫn
  // /pharmacy/history) — trên thanh dưới thì không cách nào biết mình đang bấm
  // vào cái nào.
  //
  // Tuyền 14/08/2026: *"nó phải đúng nút chứ không bịa"*. Một tên cho một nút.
  // Thanh dưới cho phép chữ xuống hai dòng thay vì bịa một tên ngắn hơn.
  /** Small tag shown next to the label (e.g. "Đang XD"). */
  badge?: string;
}

export const NAV: NavItem[] = [
  { href: "/home", label: "Trang chủ", icon: Home },
  // Bảng chạy trên workflow kernel. Đặt cạnh màn cũ (chưa thay thế) và gắn
  // badge để nhân viên biết đây là bản mới đang chạy song song — bỏ badge khi
  // staff_task được gỡ.
  {
    href: "/reception/queue",
    label: "Hàng đợi tiếp nhận",
    icon: Users,
  },
  {
    href: "/doctor/board",
    label: "Bàn khám",
    icon: Stethoscope,
    badge: "Mới",
  },
  {
    href: "/cashier/board",
    label: "Bàn thu ngân",
    icon: Receipt,
    badge: "Mới",
  },
  {
    href: "/reception/checkout",
    label: "Check-out lượt khám",
    icon: CheckCheck,
  },
  {
    href: "/cskh-tasks",
    label: "Nhiệm vụ chăm sóc",
    icon: ClipboardCheck,
  },
  // Nhắc tái khám — người bác sĩ đã hẹn quay lại mà chưa đặt lịch. Đứng cạnh
  // "Nhiệm vụ chăm sóc" vì cùng người làm, nhưng là danh sách khác: màn kia
  // xoay quanh lịch ĐÃ CÓ, màn này xoay quanh lịch CÒN THIẾU.
  {
    href: "/nhac-tai-kham",
    label: "Nhắc tái khám",
    icon: PhoneCall,
  },
  {
    href: "/appointments/cho-xep-bac-si",
    label: "Chờ xếp bác sĩ",
    icon: UserPlus,
  },
  {
    href: "/appointments",
    label: "Đặt lịch",
    icon: ClipboardList,
  },
  {
    href: "/customers",
    label: "Quản lý khách hàng",
    icon: Contact,
  },
  {
    href: "/patient-list",
    label: "Danh sách bệnh nhân",
    icon: Stethoscope,
  },
  {
    href: "/patients/new",
    label: "Tạo bệnh nhân",
    icon: UserPlus,
  },
  // Check-in ĐÃ chuyển lên TRANG CHỦ (HomeCheckin) — không còn ở sidebar.
  {
    href: "/tasks",
    label: "Công việc của tôi",
    icon: CheckSquare,
  },
  // Số thứ tự GỌI khám — ưu tiên người có hẹn, gọi theo tên (xem chung).
  {
    href: "/queue",
    label: "Số thứ tự gọi khám",
    icon: ListOrdered,
  },
  // CSKH xác nhận đóng "đợt khám" BS đã khám xong không hẹn lần sau (EPI-01).
  {
    href: "/episodes",
    label: "Đóng đợt khám",
    icon: CheckCheck,
  },
  // TRƯỞNG CA — năm màn điều phối, mỗi màn một mục trên thanh bên.
  //
  // Trước đây là MỘT mục dẫn vào một trang có cột tab riêng — tức là một thanh
  // bên thứ hai nằm ngay cạnh thanh bên thật, và người dùng phải học hai chỗ
  // điều hướng cho cùng một khu vực. Nay mỗi màn là một URL: mở thẳng được, gửi
  // link được, nút Quay lại chạy đúng.
  {
    href: "/truong-ca",
    label: "Toàn cảnh điều phối",
    icon: LayoutDashboard,
  },
  {
    href: "/truong-ca/hang-doi",
    label: "Hàng đợi theo trạm",
    icon: Rows3,
  },
  {
    href: "/truong-ca/canh-bao",
    label: "Cảnh báo & ngưỡng",
    icon: AlertTriangle,
  },
  {
    href: "/truong-ca/lich-su",
    label: "Lịch sử điều phối",
    icon: History,
  },
  {
    href: "/truong-ca/tv",
    label: "TV phòng chờ",
    icon: Tv,
  },
  // Bảng giá tách 2 trang, đặt NGAY DƯỚI "Công việc của tôi" (sidebar Thu ngân).
  { href: "/cashier/thuoc", label: "Bảng giá thuốc", icon: Pill },
  { href: "/cashier/dich-vu", label: "Bảng giá dịch vụ", icon: Tag },
  // Nhà thuốc — Dược sĩ (PHARMACIST). Đơn chờ cấp + Chuẩn bị + Kho.
  {
    href: "/pharmacy",
    label: "Đơn thuốc chờ cấp",
    icon: Pill,
    badge: "Mới",
  },
  {
    href: "/pharmacy/inventory",
    label: "Kho & tồn kho",
    icon: ClipboardList,
    badge: "Mới",
  },
  {
    href: "/pharmacy/history",
    label: "Lịch sử bàn giao",
    icon: ClipboardCheck,
    badge: "Mới",
  },
  {
    href: "/pharmacy/consult",
    label: "Tư vấn dùng thuốc",
    icon: CheckCheck,
    badge: "Mới",
  },
  {
    href: "/lab-queue",
    label: "Hàng đợi xét nghiệm",
    icon: FlaskConical,
  },
  {
    href: "/service-queue",
    label: "Hàng đợi dịch vụ",
    icon: Activity,
  },
  { href: "/sono", label: "ĐD siêu âm", icon: ScanLine },
  {
    href: "/sieu-am",
    label: "Bộ phận Siêu âm",
    icon: ScanLine,
  },
  { href: "/schedule", label: "Lịch làm việc", icon: Calendar },
  // Có trong NAV_ROLES (Quản lý + Trưởng ca) nhưng CHƯA TỪNG có mục ở đây, nên
  // trang chỉ vào được bằng cách gõ URL — quyền đã cấp mà không có đường đi.
  {
    href: "/work-sessions",
    label: "Buổi làm việc",
    icon: Timer,
  },
  // "Lịch đổ về" — Quản lý xem toàn bộ lịch một tuần + thống kê theo khung giờ.
  // Đứng NGAY TRÊN Báo cáo vì cùng một loại việc: đọc số của cả phòng khám,
  // không thao tác lên lịch của ai.
  {
    href: "/lich-do-ve",
    label: "Lịch đổ về",
    icon: CalendarRange,
  },
  { href: "/reports", label: "Báo cáo", icon: BarChart3 },
  {
    href: "/audit-log",
    label: "Lịch sử thao tác",
    icon: ClipboardCheck,
    // KHÔNG còn badge "Mới". Màn này không chạy song song với một màn cũ nào —
    // nó là màn duy nhất cho việc của nó, nên nhãn "Mới" chỉ làm sidebar ồn.
    //
    // Mười badge còn lại vẫn giữ: chúng đánh dấu những màn ĐANG chạy song song
    // với bản cũ (xem ghi chú đầu danh sách), và bỏ chúng là mất đúng thông tin
    // mà nhân viên cần để biết mình đang ở bản nào.
  },
  {
    href: "/result-review",
    label: "Duyệt kết quả",
    icon: CheckCheck,
    badge: "Mới",
  },
  {
    href: "/ops/telemetry",
    label: "Sức khoẻ API",
    icon: Timer,
  },
  { href: "/ops", label: "Vận hành hệ thống", icon: Gauge },
  {
    href: "/settings/booking-policy",
    label: "Luật đặt lịch",
    icon: Calendar,
  },
  {
    href: "/settings/clinic-config",
    label: "Cấu trúc phòng khám",
    icon: Building2,
  },
  // Hồ sơ CON NGƯỜI, tách khỏi "Cấu trúc phòng khám" ở trên — màn kia gán nhân
  // viên vào trạm công việc, màn này là tên/vai/cơ sở/hợp đồng của từng người.
  {
    href: "/nhan-su",
    label: "Quản lý nhân sự",
    icon: Users,
  },
  // Tài khoản ĐĂNG NHẬP, tách khỏi "Cài đặt" — bên kia là cấu hình phòng khám,
  // đây là quản trị người dùng: tạo login, đặt lại mật khẩu, gỡ tài khoản.
  {
    href: "/settings/tai-khoan",
    label: "Thiết lập tài khoản cho nhân viên",
    icon: KeyRound,
  },
  { href: "/settings", label: "Cài đặt", icon: Settings },
  {
    href: "/portal",
    label: "Command Center",
    icon: Zap,
    badge: "Mới",
  },
];

// Nhãn nav theo vai. Wording ĐỒNG BỘ: mọi vai (kể cả điều dưỡng) đều "Tạo bệnh
// nhân" — bỏ khái niệm "khách vãng lai"/"khách hàng".
export function navLabelFor(item: NavItem, role: ClinicRole | null): string {
  if (item.href === "/patients/new" && role === "CSKH") {
    return "Nhập thông tin khách hàng mới";
  }
  return item.label;
}

// MỘT PHÉP LỌC DUY NHẤT CHO CẢ HAI THANH.
//
// Trước 14/08/2026 thanh bên và thanh dưới tự lọc riêng, và chúng ĐÃ lệch: thanh
// bên bỏ các màn lâm sàng khi phòng khám chạy chế độ CSKH_ONLY, thanh dưới thì
// không — nên trên điện thoại vẫn hiện lối vào những màn mà máy tính đã giấu.
// Gộp về đây để hai chỗ không thể khác nhau nữa.
export function mucHienRa(
  role: ClinicRole | null,
  hienTrenThanhBen: (r: ClinicRole | null, href: string) => boolean,
  featureMode: string,
  clinicalHrefs: ReadonlySet<string>,
): NavItem[] {
  return NAV.filter((item) => {
    if (!hienTrenThanhBen(role, item.href)) return false;
    if (featureMode === "CSKH_ONLY" && clinicalHrefs.has(item.href)) return false;
    return true;
  });
}

// THANH DƯỚI TRÊN ĐIỆN THOẠI — bốn nút cho mỗi vai, chọn theo VIỆC CỦA VAI ẤY.
//
// Trước đây thanh dưới lấy "bốn mục đầu tiên" của NAV. Nhưng NAV xếp theo luồng
// khám bệnh để thanh bên đọc xuôi, không xếp theo mức hay dùng — nên với vai
// nhiều màn thì bốn mục đầu là bốn màn CỦA NGƯỜI KHÁC:
//
//   Quản lý (35 mục)  → Bàn khám · Thu ngân · Chăm sóc, còn Báo cáo/Nhân sự/
//                       Cấu trúc/Vận hành đều nằm sau nút Menu.
//   Trưởng ca (13)    → thiếu chính "Toàn cảnh điều phối", màn chính của họ.
//   ĐD siêu âm (9)    → hiện "Hàng đợi tiếp nhận", giấu "ĐD siêu âm".
//
// Danh sách dưới đây là thứ tự CÓ CHỦ Ý. Vai nào không khai thì rơi về bốn mục
// đầu như cũ — với vai ít màn (CSKH có 5, Bác sĩ có 6) thứ tự ấy vốn đã đúng.
//
// Mỗi href ở đây vẫn phải qua `mucHienRa`: khai một màn mà vai ấy không được
// xem thì nó bị bỏ, không phải hiện ra một nút bấm vào là 403.
export const THANH_DUOI: Partial<Record<ClinicRole, readonly string[]>> = {
  // Quản lý không đứng quầy. Trên điện thoại họ xem SỐ và xem PHÒNG KHÁM ĐANG
  // CHẠY RA SAO, không thao tác bàn khám hay thu ngân.
  MANAGEMENT: ["/home", "/lich-do-ve", "/reports", "/truong-ca"],
  // Trưởng ca: toàn cảnh trước, rồi hàng đợi, rồi cảnh báo — đúng thứ tự họ
  // nhìn khi phòng chờ đông.
  TRUONG_CA: ["/home", "/truong-ca", "/truong-ca/hang-doi", "/truong-ca/canh-bao"],
  // Điều dưỡng siêu âm: trạm của họ là /sono.
  NURSE_ULTRASOUND: ["/home", "/sono", "/service-queue", "/tasks"],
  // Bác sĩ siêu âm: bàn khám + bộ phận siêu âm.
  ULTRASOUND_DOCTOR: ["/home", "/doctor/board", "/sieu-am", "/patient-list"],
  // Tiếp nhận: hàng đợi, check-out, và tạo bệnh nhân — ba việc ở quầy.
  RECEPTION: ["/home", "/reception/queue", "/reception/checkout", "/patients/new"],
  // Dược sĩ: đơn chờ cấp → kho → tư vấn. "Lịch sử bàn giao" là màn tra cứu,
  // để trong Menu.
  PHARMACIST: ["/home", "/pharmacy", "/pharmacy/inventory", "/pharmacy/consult"],
  // Thu ngân: bàn thu ngân là màn chính; bảng giá là thứ tra khi khách hỏi.
  CASHIER: ["/home", "/cashier/board", "/cashier/dich-vu", "/cashier/thuoc"],
  CASHIER_THUOC: ["/home", "/cashier/board", "/cashier/thuoc", "/customers"],
  CASHIER_DV: ["/home", "/cashier/board", "/cashier/dich-vu", "/customers"],
};

/** Bốn nút của thanh dưới cho vai này, luôn là TẬP CON của thanh bên. */
export function mucThanhDuoi(
  role: ClinicRole | null,
  hienRa: NavItem[],
  toiDa: number,
): NavItem[] {
  const khai = role ? THANH_DUOI[role] : undefined;
  if (!khai) return hienRa.slice(0, toiDa);
  const theoHref = new Map(hienRa.map((i) => [i.href, i]));
  const chon = khai
    .map((h) => theoHref.get(h))
    .filter((i): i is NavItem => i !== undefined);
  // Khai thiếu, hoặc một màn bị ẩn vì chế độ CSKH_ONLY → bù bằng mục kế tiếp
  // của thanh bên, để thanh dưới không bị hụt nút.
  for (const i of hienRa) {
    if (chon.length >= toiDa) break;
    if (!chon.includes(i)) chon.push(i);
  }
  return chon.slice(0, toiDa);
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
