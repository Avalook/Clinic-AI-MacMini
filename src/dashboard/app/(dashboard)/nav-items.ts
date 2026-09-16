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
    label: "Tiếp đón khách",
    icon: Users,
  },
  // ĐO SINH HIỆU (Tuyền 16/09/2026): *"điều dưỡng đang ngồi vào đo sinh hiệu
  // thì phải có node là đo sinh hiệu, có danh sách khách theo thứ tự và cứ ấn
  // vào mà điền"*. Trước đó sinh hiệu nhập lẫn trong hàng đợi tiếp nhận.
  { href: "/do-sinh-hieu", label: "Đo sinh hiệu", icon: Activity },
  // BÀN KHÁM THEO PHÒNG (Tuyền chốt 16/09/2026). Thay "Khám bệnh (mọi loại)" và
  // năm màn Khám nội tiết / phụ khoa / sản / hiếm muộn / nam khoa: năm màn ấy
  // đặt tên theo PHIẾU, còn thanh bên đặt tên theo NƠI LÀM VIỆC. Phiếu tự mở
  // theo dịch vụ khách đặt, không do mục thanh bên quyết.
  { href: "/ban-kham", label: "Bàn khám (khách của tôi)", icon: Stethoscope },
  { href: "/ban-kham/KN-NOITIET", label: "Bàn khám · Phòng Nội tiết", icon: Stethoscope },
  { href: "/ban-kham/KN-SANCHAU", label: "Bàn khám · Phòng Sàn chậu", icon: Stethoscope },
  { href: "/ban-kham/KN-SAN-BIO", label: "Bàn khám · Phòng Sản - Biofeedback", icon: Stethoscope },
  { href: "/duyet-ket-qua", label: "Duyệt kết quả", icon: CheckCheck },
  // PHÒNG DỊCH VỤ — mã phòng khớp `clinic_room.code` (migration 20260917000001).
  { href: "/phong/KN-LAYMAU", label: "Lấy mẫu xét nghiệm", icon: FlaskConical },
  { href: "/phong/KN-SA-T1", label: "Phòng siêu âm tầng 1", icon: ScanLine },
  { href: "/phong/KN-SA1", label: "Phòng siêu âm 1 (tầng 4)", icon: ScanLine },
  { href: "/phong/KN-SA2", label: "Phòng siêu âm 2 (tầng 4)", icon: ScanLine },
  { href: "/phong/KN-THUTHUAT", label: "Phòng thủ thuật", icon: Activity },
  { href: "/phong/KN-TTNG", label: "Thủ thuật ngoài giờ", icon: Activity },
  { href: "/phong/KN-SANCHAU", label: "Phòng Sàn chậu (thủ thuật)", icon: Activity },
  { href: "/phong/KN-SAN-BIO", label: "Phòng Sản - Biofeedback (dịch vụ)", icon: Activity },
  // "Luồng khám mới" (lát 1, 11/09) ĐÃ GỠ KHỎI MENU 15/09/2026 — Tuyền: bán
  // bằng luồng thật, không để hai cách làm cùng một việc song song. Mã giữ lại;
  // ý hay của nó đưa vào các màn thật khi làm giao diện.
  // HAI QUẦY, MỘT TÀI KHOẢN (Tuyền 16/09/2026: "thu ngân hiện tại cho thành 1
  // tài khoản tên là thu-ngan thôi để nó có cả node thu ngân dịch vụ và thu
  // ngân thuốc cùng 1 chỗ"). Màn gộp /cashier/board vẫn chạy bằng đường dẫn.
  { href: "/thu-ngan/dich-vu", label: "Thu tiền dịch vụ", icon: Receipt },
  { href: "/thu-ngan/thuoc", label: "Thu tiền thuốc", icon: Receipt },
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
    label: "Điều phối ca",
    icon: LayoutDashboard,
  },
  // ĐỐI TÁC chỉ có đúng mục này, và đây là toàn bộ thanh bên của họ.
  {
    href: "/doi-tac",
    label: "Gửi kết quả",
    icon: FlaskConical,
  },
  {
    href: "/truong-ca/hang-doi",
    label: "Hàng đợi theo trạm",
    icon: Rows3,
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
    label: "Cấp thuốc",
    icon: Pill,
  },
  {
    href: "/pharmacy/inventory",
    label: "Kho thuốc",
    icon: ClipboardList,
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
  // Lễ tân: "Thêm khách hàng" (Tuyền 16/09/2026). Vai này không còn nhánh
  // "vãng lai" riêng — thêm khách xong là đặt lịch ngay trên cùng một màn.
  if (item.href === "/patients/new" && role === "RECEPTION") {
    return "Thêm khách hàng";
  }
  return item.label;
}

// MỘT PHÉP LỌC DUY NHẤT CHO CẢ HAI THANH.
//
// Trước 14/08/2026 thanh bên và thanh dưới tự lọc riêng, và chúng ĐÃ lệch: thanh
// bên bỏ các màn lâm sàng khi phòng khám chạy chế độ CSKH_ONLY, thanh dưới thì
// không — nên trên điện thoại vẫn hiện lối vào những màn mà máy tính đã giấu.
// Gộp về đây để hai chỗ không thể khác nhau nữa.
// ── THANH BÊN THEO VỊ TRÍ (Tuyền chốt 16/09/2026) ─────────────────────────
//
// *"các node bên sidebar phải là theo vị trí chứ không ấn định"*.
//
// Hai tuần lịch Kim Ngưu: một điều dưỡng đứng tới TÁM vị trí ở ba tầng. Thanh
// bên theo VAI cố định thì hôm cô ấy đứng quầy thuốc, menu vẫn mời vào màn siêu
// âm, còn màn quầy thuốc thì phải đi tìm.
//
// Bảng dưới là thứ DUY NHẤT trả lời "đứng chỗ này thì cần màn nào". Nó là
// chuyện trình bày nên nằm ở đây, không ở backend — backend chỉ trả dữ kiện
// "hôm nay bạn đứng đâu" (`GET /me/vi-tri-hom-nay`). Mã khít `vi_tri_lam_viec`.
//
// Thứ tự màn TRONG một vị trí là thứ tự dùng: màn chính trước.
export const MAN_THEO_VI_TRI: Readonly<Record<string, readonly string[]>> = {
  // Không có trong Excel — "bác sĩ trực hôm ấy" không đứng phòng cụ thể.
  LICH_KHAM: ["/ban-kham", "/duyet-ket-qua"],

  // LỄ TÂN KIÊM THU NGÂN + KHO THUỐC (Tuyền 16/09/2026). Bốn vị trí ở quầy tiếp
  // đón và quầy thuốc đều mở trọn bộ việc quầy: người đứng quầy thuốc chiều nay
  // có thể là người đứng tiếp đón sáng nay.
  T1_LETAN: ["/reception/queue", "/thu-ngan/dich-vu", "/reception/checkout", "/patients/new", "/appointments"],
  T1_THUNGAN: ["/thu-ngan/dich-vu", "/reception/checkout"],
  T2_XEPTHUOC: ["/pharmacy", "/thu-ngan/thuoc", "/pharmacy/inventory"],
  T2_TAODON: ["/thu-ngan/thuoc", "/pharmacy", "/pharmacy/inventory"],

  T1_DOCHISO: ["/do-sinh-hieu"],
  T1_LAYMAU: ["/phong/KN-LAYMAU"],

  // Phòng Nội tiết: bác sĩ khám; hỏi bệnh ban đầu và thư ký ngồi cùng phòng.
  T1_BS_NOITIET: ["/ban-kham/KN-NOITIET", "/duyet-ket-qua"],
  T1_HOIBENH: ["/ban-kham/KN-NOITIET"],
  T1_TKYK: ["/ban-kham/KN-NOITIET"],

  // THỦ THUẬT DO BÁC SĨ LÀM (Tuyền 16/09/2026); điều dưỡng cùng phòng hỗ trợ.
  T1_TT_BS: ["/phong/KN-THUTHUAT"],
  T1_TT_DD: ["/phong/KN-THUTHUAT"],
  T1_TTNG_BS: ["/phong/KN-TTNG"],
  T1_TTNG_DD1: ["/phong/KN-TTNG"],
  T1_TTNG_DD2: ["/phong/KN-TTNG"],

  // Siêu âm: bác sĩ và điều dưỡng cùng một phòng, cùng bấm Bắt đầu được.
  T1_SA_BS: ["/phong/KN-SA-T1", "/duyet-ket-qua"],
  T1_SA_DD: ["/phong/KN-SA-T1"],
  T4_SA_BS1: ["/phong/KN-SA1", "/duyet-ket-qua"],
  T4_SA_DD1: ["/phong/KN-SA1"],
  T4_SA_BS2: ["/phong/KN-SA2", "/duyet-ket-qua"],
  T4_SA_DD2: ["/phong/KN-SA2"],

  // Tầng 4: bác sĩ phòng vừa KHÁM (bàn khám) vừa LÀM thủ thuật/dịch vụ (phòng).
  T4_SANCHAU_BS: ["/ban-kham/KN-SANCHAU", "/phong/KN-SANCHAU", "/duyet-ket-qua"],
  T4_SANCHAU_BSTT: ["/phong/KN-SANCHAU"],
  T4_SANCHAU_DD: ["/phong/KN-SANCHAU"],
  T4_SAN_BS: ["/ban-kham/KN-SAN-BIO", "/phong/KN-SAN-BIO", "/duyet-ket-qua"],
  T4_SAN_DD: ["/phong/KN-SAN-BIO"],
  T4_BIO_DD: ["/phong/KN-SAN-BIO"],

  DIEU_PHOI: ["/truong-ca", "/truong-ca/hang-doi", "/customers"],
};

// ── NHÓM VAI TRÊN THANH BÊN (Tuyền chốt 16/09/2026) ─────────────────────────
//
// *"sidebar sẽ là: điều dưỡng rồi các node điều dưỡng, dưới là lễ tân rồi các
// node của lễ tân"*. Người đứng hai vai trong ngày thấy hai nhóm, mỗi nhóm một
// tiêu đề — nhìn là biết mục nào là việc của vai nào.
export type NhomVai =
  | "LE_TAN"
  | "DIEU_DUONG"
  | "BAC_SI"
  | "THU_KY"
  | "BS_SIEU_AM"
  | "TRUONG_CA";

export const TEN_NHOM: Record<NhomVai, string> = {
  LE_TAN: "Lễ tân",
  DIEU_DUONG: "Điều dưỡng",
  BAC_SI: "Bác sĩ",
  THU_KY: "Thư ký y khoa",
  BS_SIEU_AM: "Bác sĩ siêu âm",
  TRUONG_CA: "Trưởng ca",
};

/** Vị trí thuộc nhóm nào. Hỏi bệnh ban đầu: bác sĩ đứng thì là việc bác sĩ. */
export const NHOM_THEO_VI_TRI: Readonly<Record<string, NhomVai>> = {
  LICH_KHAM: "BAC_SI",
  T1_LETAN: "LE_TAN",
  T1_THUNGAN: "LE_TAN",
  T2_XEPTHUOC: "LE_TAN",
  T2_TAODON: "LE_TAN",
  T1_DOCHISO: "DIEU_DUONG",
  T1_LAYMAU: "DIEU_DUONG",
  T1_TT_DD: "DIEU_DUONG",
  T1_TTNG_DD1: "DIEU_DUONG",
  T1_TTNG_DD2: "DIEU_DUONG",
  T1_SA_DD: "DIEU_DUONG",
  T4_SA_DD1: "DIEU_DUONG",
  T4_SA_DD2: "DIEU_DUONG",
  T4_SANCHAU_DD: "DIEU_DUONG",
  T4_SAN_DD: "DIEU_DUONG",
  T4_BIO_DD: "DIEU_DUONG",
  T1_BS_NOITIET: "BAC_SI",
  T1_TT_BS: "BAC_SI",
  T1_TTNG_BS: "BAC_SI",
  T4_SANCHAU_BS: "BAC_SI",
  T4_SANCHAU_BSTT: "BAC_SI",
  T4_SAN_BS: "BAC_SI",
  T1_HOIBENH: "THU_KY",
  T1_TKYK: "THU_KY",
  T1_SA_BS: "BS_SIEU_AM",
  T4_SA_BS1: "BS_SIEU_AM",
  T4_SA_BS2: "BS_SIEU_AM",
  DIEU_PHOI: "TRUONG_CA",
};

const THU_TU_NHOM: readonly NhomVai[] = [
  "BAC_SI",
  "BS_SIEU_AM",
  "THU_KY",
  "DIEU_DUONG",
  "LE_TAN",
  "TRUONG_CA",
];

function nhomCua(viTri: string, role: ClinicRole | null): NhomVai | null {
  if (viTri === "T1_HOIBENH" && role === "DOCTOR") return "BAC_SI";
  return NHOM_THEO_VI_TRI[viTri] ?? null;
}

export interface NhomThanhBen {
  nhom: NhomVai;
  ten: string;
  muc: NavItem[];
}

/** Các nhóm hôm nay, mỗi nhóm các màn theo thứ tự vị trí rồi thứ tự dùng. */
export function nhomTheoViTri(
  viTri: readonly string[],
  role: ClinicRole | null,
): { nhom: NhomVai; hrefs: string[] }[] {
  const theo = new Map<NhomVai, string[]>();
  for (const v of viTri) {
    const n = nhomCua(v, role);
    if (!n) continue;
    const ds = theo.get(n) ?? [];
    for (const h of MAN_THEO_VI_TRI[v] ?? []) if (!ds.includes(h)) ds.push(h);
    theo.set(n, ds);
  }
  return THU_TU_NHOM.filter((n) => theo.has(n)).map((n) => ({
    nhom: n,
    hrefs: theo.get(n)!,
  }));
}

/** Màn cần cho các vị trí hôm nay, theo thứ tự vị trí rồi thứ tự dùng, không lặp. */
export function hrefTheoViTri(viTri: readonly string[]): string[] {
  const ra: string[] = [];
  for (const v of viTri) {
    for (const h of MAN_THEO_VI_TRI[v] ?? []) if (!ra.includes(h)) ra.push(h);
  }
  return ra;
}

export function mucHienRa(
  role: ClinicRole | null,
  hienTrenThanhBen: (r: ClinicRole | null, href: string) => boolean,
  featureMode: string,
  clinicalHrefs: ReadonlySet<string>,
  /** Mã vị trí người này đứng HÔM NAY. Rỗng = không có ca → menu theo vai. */
  viTriHomNay: readonly string[] = [],
): NavItem[] {
  const conLai = (item: NavItem) =>
    !(featureMode === "CSKH_ONLY" && clinicalHrefs.has(item.href));

  // CÓ CA HÔM NAY → thanh bên là việc của hôm nay: Trang chủ, màn của từng vị
  // trí, rồi Lịch làm việc để xem mai đứng đâu.
  //
  // QUẢN LÝ KHÔNG ÁP DỤNG. Quản lý không đứng vị trí; menu của họ là báo cáo,
  // cấu hình, nhân sự — thu về theo vị trí là giấu mất đúng những màn ấy trong
  // ngày họ lỡ được xếp một ca.
  //
  // RỖNG → rơi về menu theo vai như trước, chứ không để thanh bên trống trơn:
  // người không có ca hôm nay vẫn phải vào được hệ thống để làm việc gì đó.
  const theoViTri = role !== "MANAGEMENT" ? hrefTheoViTri(viTriHomNay) : [];
  if (theoViTri.length > 0) {
    const thuTu = ["/home", ...theoViTri, "/schedule"];
    return thuTu
      .map((h) => NAV.find((item) => item.href === h))
      .filter((item): item is NavItem => item !== undefined && conLai(item));
  }

  return NAV.filter((item) => hienTrenThanhBen(role, item.href) && conLai(item));
}

// THANH BÊN: các NHÓM VAI hôm nay + "Việc khác" (gập sẵn).
//
// Chỉ ẩn thì hỏng đúng chuyện thường ngày trong lịch Kim Ngưu: đứng thay nhau
// giữa ca. Người đứng Đo sinh hiệu được gọi sang lấy mẫu vẫn phải có lối vào,
// chỉ là không bày ra chen với việc chính.
//
// Không có ca (hoặc là Quản lý) → `nhom` rỗng, `khac` là menu theo vai, và
// thanh bên vẽ một danh sách phẳng như trước.
export function nhomThanhBen(
  role: ClinicRole | null,
  hienTrenThanhBen: (r: ClinicRole | null, href: string) => boolean,
  featureMode: string,
  clinicalHrefs: ReadonlySet<string>,
  viTriHomNay: readonly string[] = [],
): { dau: NavItem[]; nhom: NhomThanhBen[]; khac: NavItem[] } {
  // Cùng một phép lọc với thanh dưới — `mucHienRa` — để hai thanh không lệch.
  const theoVai = mucHienRa(role, hienTrenThanhBen, featureMode, clinicalHrefs, []);
  const homNay = mucHienRa(role, hienTrenThanhBen, featureMode, clinicalHrefs, viTriHomNay);
  const coCa = role !== "MANAGEMENT" && hrefTheoViTri(viTriHomNay).length > 0;
  if (!coCa) {
    return { dau: [], nhom: [], khac: theoVai };
  }
  const choPhep = new Map(homNay.map((i) => [i.href, i]));
  const nhom: NhomThanhBen[] = nhomTheoViTri(viTriHomNay, role)
    .map((g) => ({
      nhom: g.nhom,
      ten: TEN_NHOM[g.nhom],
      muc: g.hrefs
        .map((h) => choPhep.get(h))
        .filter((i): i is NavItem => i !== undefined),
    }))
    .filter((g) => g.muc.length > 0);
  const daCo = new Set(nhom.flatMap((g) => g.muc.map((i) => i.href)));
  const dau = homNay.filter((i) => i.href === "/home");
  daCo.add("/home");
  const khac = theoVai.filter((i) => !daCo.has(i.href));
  if (!khac.some((i) => i.href === "/schedule")) {
    const lich = NAV.find((i) => i.href === "/schedule");
    if (lich) khac.push(lich);
  }
  return { dau, nhom, khac };
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
  // Trưởng ca: toàn cảnh trước, rồi hàng đợi, rồi khách hàng — đúng thứ tự họ
  // nhìn khi phòng chờ đông.
  TRUONG_CA: ["/home", "/truong-ca", "/truong-ca/hang-doi", "/customers"],
  // Điều dưỡng, ngày không có ca: ba việc hay đứng nhất.
  NURSE_ULTRASOUND: ["/home", "/do-sinh-hieu", "/phong/KN-LAYMAU", "/phong/KN-SA-T1"],
  // Bác sĩ và thư ký: bàn khám là màn chính. Ngày có ca, thanh dưới đi theo
  // vị trí và bảng này không được dùng tới.
  DOCTOR: ["/home", "/ban-kham", "/duyet-ket-qua", "/patient-list"],
  TKYK: ["/home", "/ban-kham", "/tasks", "/patient-list"],
  ULTRASOUND_DOCTOR: ["/home", "/phong/KN-SA-T1", "/duyet-ket-qua", "/patient-list"],
  // Lễ tân kiêm thu ngân (Tuyền 16/09/2026).
  RECEPTION: ["/home", "/reception/queue", "/thu-ngan/dich-vu", "/appointments"],
  // Dược sĩ: đơn chờ cấp → kho → tư vấn.
  PHARMACIST: ["/home", "/pharmacy", "/pharmacy/inventory", "/pharmacy/consult"],
  CASHIER: ["/home", "/thu-ngan/dich-vu", "/thu-ngan/thuoc", "/cashier/dich-vu"],
  CASHIER_THUOC: ["/home", "/thu-ngan/thuoc", "/cashier/thuoc", "/customers"],
  CASHIER_DV: ["/home", "/thu-ngan/dich-vu", "/cashier/dich-vu", "/customers"],
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
