// Shared nav model used by both the desktop sidebar (Nav) and the mobile
// bottom tab bar (BottomNav). Visibility is per-role (see canSeeNav).

import {
  Home,
  ClipboardList,
  UserPlus,
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
  Rows3,
  History,
  Tv,
  CheckCheck,
  Gauge,
  Users,
  Receipt,
  Building2,
  PhoneCall,
  Route,
  FileSpreadsheet,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import {
  laManLego,
  legoChoHien,
  quyenMoDuocMan,
  type ClinicRole,
} from "../../lib/roles";

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
  /** NODE CON (Tuyền 27/09/2026): href của node cha — thanh bên vẽ mục này
   *  thụt vào, ngay dưới node cha. Cùng lego với cha (`catalogue.MAN`). */
  cha?: string;
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
  { href: "/tu-van", label: "Bàn khám tư vấn", icon: Stethoscope },
  { href: "/ban-kham", label: "Bàn khám", icon: Stethoscope },
  // "Xác nhận kết quả" OFF (Tuyền 23/09/2026 khuya: "không cần nút xác nhận kết
  // quả… cho vào luôn trong phiếu khám của bác sĩ"). Tệp đối tác HỢP LỆ ngay khi
  // tải lên (cờ XAC_NHAN_TEP_DOI_TAC). Route còn giữ, chỉ gỡ khỏi thanh bên.
  // "Duyệt kết quả" OFF (Tuyền 23/09/2026 tối: "không cần cái duyệt kết quả nữa,
  // duyệt làm gì khi ta có thể tự điền vào đây") — bác sĩ đọc/điền kết quả ngay
  // trong phiếu khám (mục C). Route /duyet-ket-qua còn giữ, chỉ gỡ khỏi thanh bên.
  // Việc sinh ra từ sự kiện: khách đã trả tiền mà không làm được dịch vụ, và
  // dịch vụ bị dừng giữa chừng. Mở việc mà không màn nào hiện thì vẫn là rơi.
  { href: "/viec-can-xu-ly", label: "Việc cần xử lý", icon: ClipboardCheck },
  // Quản lý tự bật/tắt khối công việc cho từng người — không cần ai sửa code.
  { href: "/phan-quyen", label: "Phân quyền", icon: KeyRound },
  // PHÒNG DỊCH VỤ — PHÒNG LÀ TÀI NGUYÊN (CORE-C, 23/09/2026). Trước đây chín
  // mục viết cứng theo mã phòng (`/phong/KN-SA1`…): quản lý thêm hay đổi tên
  // phòng thì thanh bên không đổi theo. Nay MỘT mục dẫn tới danh sách phòng
  // (đọc từ database); ngày có ca, thanh bên tự dựng mục cho đúng phòng người
  // ấy đứng, tên lấy từ `clinic_room.name` (xem `mucPhong`).
  { href: "/phong", label: "Phòng dịch vụ", icon: ScanLine },
  // "Luồng khám mới" (lát 1, 11/09) ĐÃ GỠ KHỎI MENU 15/09/2026 — Tuyền: bán
  // bằng luồng thật, không để hai cách làm cùng một việc song song. Mã giữ lại;
  // ý hay của nó đưa vào các màn thật khi làm giao diện.
  // HAI QUẦY, MỘT TÀI KHOẢN (Tuyền 16/09/2026: "thu ngân hiện tại cho thành 1
  // tài khoản tên là thu-ngan thôi để nó có cả node thu ngân dịch vụ và thu
  // ngân thuốc cùng 1 chỗ"). /cashier/board cũ nay chuyển hướng về đây.
  { href: "/thu-ngan/dich-vu", label: "Thu tiền dịch vụ", icon: Receipt },
  { href: "/thu-ngan/thuoc", label: "Thu tiền thuốc", icon: Receipt },
  {
    href: "/reception/checkout",
    label: "Check-out lượt khám",
    icon: CheckCheck,
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
  // THÊM KHÁCH TRƯỚC DANH SÁCH (đợt 3, 27/09/2026 — C6): CSKH / lễ tân mở máy
  // là để thêm khách đang gọi / đang đứng quầy; mục ấy từng nằm DƯỚI hai danh
  // sách, người trực phải dò mới thấy.
  {
    href: "/patients/new",
    label: "Tạo bệnh nhân",
    icon: UserPlus,
  },
  {
    href: "/customers",
    label: "Quản lý khách hàng",
    icon: Contact,
  },
  // Nhắc tái khám — người bác sĩ đã hẹn quay lại mà chưa đặt lịch. Node CON của
  // Quản lý khách hàng (Tuyền 27/09/2026): cùng lego "Chăm sóc khách hàng".
  {
    href: "/nhac-tai-kham",
    label: "Nhắc tái khám",
    icon: PhoneCall,
    cha: "/customers",
  },
  {
    href: "/patient-list",
    label: "Danh sách bệnh nhân",
    icon: Stethoscope,
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
    icon: Rows3,
  },
  // BẢNG HÀNH TRÌNH CHUNG (nhóm 3, 24/09/2026) — mọi vai nội bộ.
  {
    href: "/hanh-trinh",
    label: "Hành trình khách hôm nay",
    icon: Route,
  },
  // ĐỐI TÁC chỉ có đúng mục này, và đây là toàn bộ thanh bên của họ.
  {
    href: "/doi-tac",
    label: "Việc của đối tác",
    icon: FlaskConical,
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
  // Bảng giá tách 2 trang (thuốc / dịch vụ).
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
  // Dây nối nghiệp vụ (nhóm 5, 24/09/2026): qua tư vấn / đi thẳng phòng, tự
  // xếp phòng, thời hạn nhắc, người nhận chuông, vị trí trực.
  {
    href: "/settings/day-noi",
    label: "Dây nối nghiệp vụ",
    icon: Route,
  },
  // Mẫu kết quả (27/09/2026): gắn mẫu cho dịch vụ, sửa / tạo mẫu kết quả.
  {
    href: "/settings/mau-ket-qua",
    label: "Mẫu kết quả",
    icon: FileSpreadsheet,
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
  // Dọn dữ liệu khách thử (30/09/2026): quản trị viên tick khách theo ngày để
  // xoá hẳn — chỉ `permission.manage`, máy chủ hỏi lại ở mọi lệnh.
  {
    href: "/settings/don-du-lieu-thu",
    label: "Dọn dữ liệu thử",
    icon: Trash2,
  },
  { href: "/settings", label: "Cài đặt", icon: Settings },
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
/** MÃ VỊ TRÍ ĐỜI CŨ còn trong lịch (mẫu lịch trước Kim Ngưu, 14–27/09/2026):
 *  đọc như mã mới tương ứng, để thanh bên ĐI THEO ĐÚNG LỊCH quản lý đã xếp (Tuyền
 *  17/09/2026). Mã cũ không ghi phòng siêu âm cụ thể → mở cả ba phòng. */
export const MA_VI_TRI_CU: Readonly<Record<string, readonly string[]>> = {
  LE_TAN: ["T1_LETAN"],
  LAY_MAU: ["T1_LAYMAU"],
  TLYK: ["T1_TKYK"],
  PHU_BS_SA: ["T1_SA_DD", "T4_SA_DD1", "T4_SA_DD2"],
  MAY_TRONG: ["T1_SA_BS", "T4_SA_BS1", "T4_SA_BS2"],
  MAY_NGOAI: ["T1_SA_BS", "T4_SA_BS1", "T4_SA_BS2"],
  PHONG_NGOAI_MOR: ["T1_SA_BS", "T4_SA_BS1", "T4_SA_BS2"],
};

/** Đổi mã cũ sang mã mới, giữ thứ tự, không lặp. */
export function chuanHoaViTri(viTri: readonly string[]): string[] {
  const ra: string[] = [];
  for (const v of viTri) {
    for (const m of MA_VI_TRI_CU[v] ?? [v]) if (!ra.includes(m)) ra.push(m);
  }
  return ra;
}

// ── PHÒNG CỦA VỊ TRÍ (CORE-C, 23/09/2026) ───────────────────────────────────
//
// Vị trí trực biết mình thuộc phòng nào qua `vi_tri_lam_viec.room_id` — máy chủ
// trả về trong `GET /me/vi-tri-hom-nay` → `phong`. Bảng dưới chỉ ghi "vị trí này
// làm ở PHÒNG của nó" (`PHONG`) hay "khám ở bàn khám của phòng nó" (`BAN_KHAM`),
// không ghi phòng nào. Đổi tên phòng, thêm phòng: không ai phải sửa file này.
export const PHONG = "@phong";
export const BAN_KHAM = "@ban-kham";

/** Phòng của từng vị trí trực, theo mã vị trí. Máy chủ tính. */
export type PhongTheoViTri = Readonly<
  Record<string, { room_id: string; ten: string }>
>;

/** Đổi ký hiệu thành đường dẫn thật. Vị trí chưa gắn phòng → danh sách phòng
 *  (`/phong`) hoặc bàn khám chung (`/ban-kham`), không bao giờ là một mã đoán. */
function giaiMan(h: string, viTri: string, phong: PhongTheoViTri): string {
  if (h !== PHONG && h !== BAN_KHAM) return h;
  const goc = h === PHONG ? "/phong" : "/ban-kham";
  const p = phong[viTri];
  return p ? `${goc}/${p.room_id}` : goc;
}

export const MAN_THEO_VI_TRI: Readonly<Record<string, readonly string[]>> = {
  // Không có trong Excel — "bác sĩ trực hôm ấy" không đứng phòng cụ thể.
  LICH_KHAM: ["/ban-kham"],

  // LỄ TÂN KIÊM THU NGÂN + KHO THUỐC (Tuyền 16/09/2026). Bốn vị trí ở quầy tiếp
  // đón và quầy thuốc đều mở trọn bộ việc quầy: người đứng quầy thuốc chiều nay
  // có thể là người đứng tiếp đón sáng nay.
  // "Thêm khách hàng" ĐẦU nhóm (đợt 3, 27/09/2026 — C6).
  T1_LETAN: [
    "/patients/new",
    "/reception/queue",
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
    "/reception/checkout",
    "/appointments",
  ],
  T1_THUNGAN: [
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
    "/reception/checkout",
  ],
  T2_XEPTHUOC: ["/thu-ngan/thuoc"],
  T2_TAODON: ["/thu-ngan/thuoc"],

  T1_DOCHISO: ["/do-sinh-hieu"],
  T1_LAYMAU: [PHONG],

  // Phòng Nội tiết: bác sĩ khám; hỏi bệnh ban đầu và thư ký ngồi cùng phòng.
  T1_BS_NOITIET: [BAN_KHAM],
  // Hỏi bệnh ban đầu = BÀN KHÁM TƯ VẤN (24/09/2026): hàng tư vấn chung.
  T1_HOIBENH: ["/tu-van"],
  T1_TKYK: [BAN_KHAM],

  // THỦ THUẬT DO BÁC SĨ LÀM (Tuyền 16/09/2026); điều dưỡng cùng phòng hỗ trợ.
  T1_TT_BS: [PHONG],
  T1_TT_DD: [PHONG],
  T1_TTNG_BS: [PHONG],
  T1_TTNG_DD1: [PHONG],
  T1_TTNG_DD2: [PHONG],

  // Siêu âm: bác sĩ và điều dưỡng cùng một phòng, cùng bấm Bắt đầu được.
  T1_SA_BS: [PHONG],
  T1_SA_DD: [PHONG],
  T4_SA_BS1: [PHONG],
  T4_SA_DD1: [PHONG],
  T4_SA_BS2: [PHONG],
  T4_SA_DD2: [PHONG],

  // Tầng 4: bác sĩ phòng vừa KHÁM (bàn khám) vừa LÀM thủ thuật/dịch vụ (phòng).
  T4_SANCHAU_BS: [BAN_KHAM, PHONG],
  T4_SANCHAU_BSTT: [PHONG],
  T4_SANCHAU_DD: [PHONG],
  T4_SAN_BS: [BAN_KHAM, PHONG],
  T4_SAN_DD: [PHONG],
  T4_BIO_DD: [PHONG],

  DIEU_PHOI: ["/truong-ca", "/customers"],

  // Thư ký đi kèm từng bác sĩ (17/09/2026).
  T1_TT_TK: [PHONG],
  T1_SA_TK: [PHONG],
  T1_TTNG_TK: [PHONG],
  T4_SANCHAU_TK: [BAN_KHAM, PHONG],
  T4_SANCHAU_TKTT: [PHONG],
  T4_SAN_TK: [BAN_KHAM, PHONG],
  T4_SA_TK1: [PHONG],
  T4_SA_TK2: [PHONG],
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
  T1_TT_TK: "THU_KY",
  T1_SA_TK: "THU_KY",
  T1_TTNG_TK: "THU_KY",
  T4_SANCHAU_TK: "THU_KY",
  T4_SANCHAU_TKTT: "THU_KY",
  T4_SAN_TK: "THU_KY",
  T4_SA_TK1: "THU_KY",
  T4_SA_TK2: "THU_KY",
};

// Một người hai vai trong ngày: LỄ TÂN Ở TRÊN, ĐIỀU DƯỠNG Ở DƯỚI (Tuyền 17/09/2026).
const THU_TU_NHOM: readonly NhomVai[] = [
  "BAC_SI",
  "BS_SIEU_AM",
  "THU_KY",
  "LE_TAN",
  "DIEU_DUONG",
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
  phong: PhongTheoViTri = {},
): { nhom: NhomVai; hrefs: string[] }[] {
  const theo = new Map<NhomVai, string[]>();
  for (const v of chuanHoaViTri(viTri)) {
    const n = nhomCua(v, role);
    if (!n) continue;
    const ds = theo.get(n) ?? [];
    for (const m of MAN_THEO_VI_TRI[v] ?? []) {
      const h = giaiMan(m, v, phong);
      if (!ds.includes(h)) ds.push(h);
    }
    theo.set(n, ds);
  }
  return THU_TU_NHOM.filter((n) => theo.has(n)).map((n) => ({
    nhom: n,
    hrefs: theo.get(n)!,
  }));
}

/** Màn cần cho các vị trí hôm nay, theo thứ tự vị trí rồi thứ tự dùng, không lặp. */
export function hrefTheoViTri(
  viTri: readonly string[],
  phong: PhongTheoViTri = {},
): string[] {
  const ra: string[] = [];
  for (const v of chuanHoaViTri(viTri)) {
    for (const m of MAN_THEO_VI_TRI[v] ?? []) {
      const h = giaiMan(m, v, phong);
      if (!ra.includes(h)) ra.push(h);
    }
  }
  return ra;
}

/** Mục thanh bên của một đường dẫn: mục cố định trong NAV, hoặc mục dựng từ
 *  phòng (`/phong/<room_id>`, `/ban-kham/<room_id>`) — tên là tên phòng hiện
 *  tại, nên đổi tên phòng là thanh bên đổi theo ở lần mở trang kế tiếp. */
export function mucPhong(
  href: string,
  phong: PhongTheoViTri = {},
): NavItem | undefined {
  const co = NAV.find((item) => item.href === href);
  if (co) return co;
  const [, goc, id] = href.split("/");
  const p = Object.values(phong).find((x) => x.room_id === id);
  if (!p) return undefined;
  if (goc === "phong") return { href, label: p.ten, icon: ScanLine };
  if (goc === "ban-kham") {
    return { href, label: `Bàn khám · ${p.ten}`, icon: Stethoscope };
  }
  return undefined;
}

/** Màn lâm sàng (ẩn khi CSKH_ONLY) — kể cả mọi màn theo phòng. */
function laManLamSang(href: string, clinicalHrefs: ReadonlySet<string>): boolean {
  return (
    clinicalHrefs.has(href) ||
    href.startsWith("/phong/") ||
    href.startsWith("/ban-kham/")
  );
}

export function mucHienRa(
  role: ClinicRole | null,
  hienTrenThanhBen: (r: ClinicRole | null, href: string) => boolean,
  featureMode: string,
  clinicalHrefs: ReadonlySet<string>,
  /** Mã vị trí người này đứng HÔM NAY. Rỗng = không có ca → menu theo vai. */
  viTriHomNay: readonly string[] = [],
  /** Phòng của từng vị trí hôm nay (máy chủ tính từ `room_id`). */
  phong: PhongTheoViTri = {},
  /** Quyền (capability) của tài khoản. `null` = máy chủ chưa trả lời. */
  quyen: readonly string[] | null = null,
): NavItem[] {
  const conLai = (item: NavItem) =>
    !(featureMode === "CSKH_ONLY" && laManLamSang(item.href, clinicalHrefs));

  // CÓ CA HÔM NAY → thanh bên là việc của hôm nay: Trang chủ, màn của từng vị
  // trí, rồi Lịch làm việc để xem mai đứng đâu.
  //
  // QUẢN LÝ KHÔNG ÁP DỤNG. Quản lý không đứng vị trí; menu của họ là báo cáo,
  // cấu hình, nhân sự — thu về theo vị trí là giấu mất đúng những màn ấy trong
  // ngày họ lỡ được xếp một ca.
  //
  // RỖNG → rơi về menu theo vai như trước, chứ không để thanh bên trống trơn:
  // người không có ca hôm nay vẫn phải vào được hệ thống để làm việc gì đó.
  const theoViTri = role !== "MANAGEMENT" ? hrefTheoViTri(viTriHomNay, phong) : [];
  if (theoViTri.length > 0) {
    const thuTu = ["/home", ...theoViTri, "/schedule"];
    // VỊ TRÍ quyết màn nào bày hôm nay, LEGO quyết màn nào được bày (kiểm toán
    // 27/09/2026): đứng Lễ tân mà lego Tiếp đón đang tắt thì không hiện mục
    // Tiếp đón — trước đây nhánh này trả thẳng, bỏ qua lego.
    return thuTu
      .filter((h) => legoChoHien(quyen, h))
      .map((h) => mucPhong(h, phong))
      .filter((item): item is NavItem => item !== undefined && conLai(item));
  }

  return NAV.filter((item) => hienTrenThanhBen(role, item.href) && conLai(item));
}

// THANH BÊN: các NHÓM VAI hôm nay + "Lego đang bật" + "Việc khác" (gập sẵn).
//
// Chỉ ẩn thì hỏng đúng chuyện thường ngày trong lịch Kim Ngưu: đứng thay nhau
// giữa ca. Người đứng Đo sinh hiệu được gọi sang lấy mẫu vẫn phải có lối vào,
// chỉ là không bày ra chen với việc chính.
//
// Đợt 3 (27/09/2026): Trang chủ + Hành trình (luôn bật) đứng đầu (`dau`); lego
// ĐANG BẬT của chính tài khoản không gập (`lego`) — lễ tân và thu ngân hỗ trợ
// nhau bằng cách BẬT THÊM LEGO ở /phan-quyen, không dùng chung tài khoản. "Việc
// khác" chỉ còn những màn ngoài lego.
//
// Không có ca (hoặc là Quản lý) → `nhom`, `lego` rỗng, `khac` là menu theo vai,
// và thanh bên vẽ một danh sách phẳng như trước.
export function nhomThanhBen(
  role: ClinicRole | null,
  hienTrenThanhBen: (r: ClinicRole | null, href: string) => boolean,
  featureMode: string,
  clinicalHrefs: ReadonlySet<string>,
  viTriHomNay: readonly string[] = [],
  phong: PhongTheoViTri = {},
  quyen: readonly string[] | null = null,
): { dau: NavItem[]; nhom: NhomThanhBen[]; lego: NavItem[]; khac: NavItem[] } {
  // Cùng một phép lọc với thanh dưới — `mucHienRa` — để hai thanh không lệch.
  const theoVai = mucHienRa(role, hienTrenThanhBen, featureMode, clinicalHrefs, []);
  const homNay = mucHienRa(
    role, hienTrenThanhBen, featureMode, clinicalHrefs, viTriHomNay, phong, quyen,
  );
  const coCa = role !== "MANAGEMENT" && hrefTheoViTri(viTriHomNay).length > 0;
  if (!coCa) {
    return { dau: [], nhom: [], lego: [], khac: theoVai };
  }
  const choPhep = new Map(homNay.map((i) => [i.href, i]));
  const nhom: NhomThanhBen[] = nhomTheoViTri(viTriHomNay, role, phong)
    .map((g) => ({
      nhom: g.nhom,
      ten: TEN_NHOM[g.nhom],
      muc: g.hrefs
        .map((h) => choPhep.get(h))
        .filter((i): i is NavItem => i !== undefined),
    }))
    .filter((g) => g.muc.length > 0);
  const daCo = new Set(nhom.flatMap((g) => g.muc.map((i) => i.href)));
  const dau = [
    ...homNay.filter((i) => i.href === "/home"),
    ...theoVai.filter((i) => i.href === "/hanh-trinh" && !daCo.has(i.href)),
  ];
  for (const i of dau) daCo.add(i.href);
  daCo.add("/home");
  const conLai = theoVai.filter((i) => !daCo.has(i.href));
  if (!conLai.some((i) => i.href === "/schedule") && legoChoHien(quyen, "/schedule")) {
    const lich = NAV.find((i) => i.href === "/schedule");
    if (lich) conLai.push(lich);
  }
  const dangBat = (i: NavItem) =>
    quyen !== null && laManLego(i.href) && quyenMoDuocMan(quyen, i.href);
  return { dau, nhom, lego: conLai.filter(dangBat), khac: conLai.filter((i) => !dangBat(i)) };
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
  TRUONG_CA: ["/home", "/truong-ca", "/truong-ca/lich-su", "/customers"],
  // Điều dưỡng, ngày không có ca: ba việc hay đứng nhất.
  NURSE_ULTRASOUND: ["/home", "/do-sinh-hieu", "/phong", "/schedule"],
  // Bác sĩ và thư ký: bàn khám là màn chính. Ngày có ca, thanh dưới đi theo
  // vị trí và bảng này không được dùng tới.
  DOCTOR: ["/home", "/ban-kham", "/patient-list", "/hanh-trinh"],
  TKYK: ["/home", "/ban-kham", "/patient-list", "/schedule"],
  ULTRASOUND_DOCTOR: ["/home", "/phong", "/patient-list", "/hanh-trinh"],
  // Lễ tân kiêm thu ngân (Tuyền 16/09/2026, cập nhật 20/09/2026).
  RECEPTION: [
    "/home",
    "/reception/queue",
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
  ],
  // Dược sĩ: đơn chờ cấp → kho → tư vấn.
  PHARMACIST: ["/home", "/pharmacy", "/pharmacy/inventory", "/pharmacy/consult"],
  CASHIER: ["/home", "/thu-ngan/dich-vu", "/thu-ngan/thuoc", "/cashier/dich-vu"],
  // 25/09: Bảng giá thuốc OFF khỏi thanh bên (giá thuốc sửa ở Kho thuốc).
  CASHIER_THUOC: ["/home", "/thu-ngan/thuoc", "/patient-list", "/customers"],
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

/** Đưa node con về NGAY DƯỚI node cha (27/09/2026). Thanh bên xếp theo nhóm
 *  việc nên con có thể rơi vào nhóm khác cha; cha không hiện thì con đứng chỗ
 *  cũ như mục thường. Thuần — nhận các danh sách, trả danh sách mới. */
export function xepNodeCon<T extends { href: string; cha?: string }>(ds: T[][]): T[][] {
  const coCha = new Set(ds.flat().map((m) => m.href));
  const con = ds.flat().filter((m) => m.cha && coCha.has(m.cha));
  const conHref = new Set(con.map((m) => m.href));
  return ds.map((list) =>
    list
      .filter((m) => !conHref.has(m.href))
      .flatMap((m) => [m, ...con.filter((c) => c.cha === m.href)]),
  );
}

// ── NHÓM THEO CÔNG VIỆC (Tuyền 27/09/2026: sidebar kiểu A — Linear / Vercel) ──
// Ngày KHÔNG có nhóm theo vị trí hôm nay, thanh bên chia mục theo dòng đi của
// khách thay vì một danh sách phẳng 17 mục. Chỉ là TRÌNH BÀY: mục nào hiện vẫn
// do `mucHienRa` / lego quyết; mục không thuộc nhóm nào rơi vào "Khác".
export const NHOM_CONG_VIEC: readonly { ma: string; ten: string; hrefs: readonly string[] }[] = [
  { ma: "hom-nay", ten: "Hôm nay", hrefs: ["/home", "/viec-can-xu-ly", "/hanh-trinh"] },
  {
    ma: "tiep-don",
    ten: "Tiếp đón & thu",
    hrefs: ["/reception/queue", "/thu-ngan/dich-vu", "/thu-ngan/thuoc", "/reception/checkout"],
  },
  { ma: "kham", ten: "Khám & dịch vụ", hrefs: ["/do-sinh-hieu", "/tu-van", "/ban-kham", "/phong", "/doi-tac"] },
  {
    ma: "khach",
    ten: "Khách hàng",
    hrefs: ["/appointments", "/appointments/cho-xep-bac-si", "/customers", "/nhac-tai-kham", "/patient-list", "/patients/new"],
  },
  { ma: "thuoc", ten: "Nhà thuốc", hrefs: ["/pharmacy", "/pharmacy/inventory", "/pharmacy/history", "/pharmacy/consult"] },
  { ma: "dieu-hanh", ten: "Điều hành", hrefs: ["/truong-ca", "/truong-ca/tv", "/truong-ca/lich-su", "/schedule"] },
  {
    ma: "quan-tri",
    ten: "Quản trị",
    hrefs: [
      "/phan-quyen",
      "/nhan-su",
      "/settings/tai-khoan",
      "/settings/don-du-lieu-thu",
      "/settings",
      "/settings/clinic-config",
      "/settings/day-noi",
      "/settings/booking-policy",
      "/settings/mau-ket-qua",
      "/cashier/dich-vu",
      "/cashier/thuoc",
      "/reports",
      "/lich-do-ve",
      "/ops",
      "/audit-log",
    ],
  },
];

/** Chia các mục đang hiện vào nhóm công việc, giữ thứ tự khai trong nhóm; mục
 *  phòng theo vị trí (`/phong/…`) vào "Khám & dịch vụ"; còn lại vào "Khác".
 *  Thuần — nhóm rỗng bị bỏ. */
export function nhomTheoCongViec<T extends { href: string }>(
  ds: readonly T[],
): { ma: string; ten: string; muc: T[] }[] {
  const cuaNhom = (href: string) =>
    NHOM_CONG_VIEC.find((g) => g.hrefs.includes(href))?.ma ??
    (href.startsWith("/phong/") ? "kham" : "khac");
  const out = [...NHOM_CONG_VIEC, { ma: "khac", ten: "Khác", hrefs: [] as readonly string[] }].map(
    (g) => {
      const muc = ds.filter((m) => cuaNhom(m.href) === g.ma);
      const thuTu = (m: T) => {
        const i = g.hrefs.indexOf(m.href);
        return i === -1 ? g.hrefs.length + ds.indexOf(m) : i;
      };
      return { ma: g.ma, ten: g.ten, muc: [...muc].sort((a, b) => thuTu(a) - thuTu(b)) };
    },
  );
  return out.filter((g) => g.muc.length > 0);
}
