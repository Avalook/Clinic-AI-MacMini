// Pure role logic — NO next/headers import, so it is safe to use from both
// Server Components and Client Components (e.g. Nav.tsx).
//
// Roles are derived server-side from the authenticated user's linked staff
// row. These pure helpers only transform/check the already-authoritative role.

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
  | "TRUONG_CA"
  | "PHARMACIST";

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
  "PHARMACIST",
];

// Convert a trusted role value into the closed application enum. Unknown data
// must never inherit a real role (the previous CSKH fallback was fail-open).
export function departmentToRole(
  dept: string | null | undefined,
): ClinicRole | null {
  return isClinicRole(dept ?? "") ? (dept as ClinicRole) : null;
}

export function isClinicRole(v: string | undefined | null): v is ClinicRole {
  return !!v && (ALL_ROLES as string[]).includes(v);
}

// TWO DIFFERENT QUESTIONS, AND CONFLATING THEM BROKE A BUTTON.
//
// "Works at the doctor's desk" includes the medical secretary: TKYK opens the
// same board, types the note for the doctor, moves the same appointment.
//
// "Is a physician" does not. Ordering a test and signing off a lab result are
// acts a secretary must not perform, and the backend has always agreed —
// lab.py gates both on {DOCTOR, ULTRASOUND_DOCTOR}.
//
// For months only the second half of that was true on the server. The browser
// asked isDoctorRole (which includes TKYK) before drawing "Chỉ định XN" and
// "Duyệt kết quả", so a medical secretary saw both buttons, pressed them, and
// got a 403 with no way to tell whether the system was broken or they were.
// The server was right; the screen was lying. Keep the two questions apart.
const DOCTOR_DESK_ROLES = new Set<ClinicRole>([
  "DOCTOR",
  "ULTRASOUND_DOCTOR",
  "TKYK",
]);
const PHYSICIAN_ROLES = new Set<ClinicRole>(["DOCTOR", "ULTRASOUND_DOCTOR"]);

/** Works the doctor's board: doctor, ultrasound doctor, medical secretary. */
export function isDoctorRole(role: ClinicRole | null): boolean {
  return role !== null && DOCTOR_DESK_ROLES.has(role);
}

/** Holds a medical licence: may ORDER tests and SIGN OFF results.
 *
 *  Mirrors `PHYSICIAN_ROLES` in clinicai/api/identity.py, which is what
 *  lab.py's _ORDER_GUARD and _REVIEW_GUARD actually enforce. Any screen that
 *  draws a control those guards protect must ask this, not isDoctorRole. */
export function isPhysicianRole(role: ClinicRole | null): boolean {
  return role !== null && PHYSICIAN_ROLES.has(role);
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

/** Reading the medical note has the same boundary as writing it (ROLE-02). */
export function canReadClinical(role: ClinicRole | null): boolean {
  return canWriteClinical(role);
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

/** Họ thu ngân.
 *
 *  MỘT VAI, KHÔNG PHẢI BA (Quang chốt 2026-08-03: "thu ngân giờ ghép thành 1
 *  thu ngân duy nhất"). Phòng khám có một quầy; tách làm ba chỉ tạo ra ba chỗ
 *  phải nhớ liệt kê trong NAV_ROLES — quên một chỗ là một vai mất màn hình mà
 *  không ai biết — và ba giá trị khác nhau trong audit log cho cùng một việc.
 *
 *  20260803000007 gộp mọi membership về CASHIER. CASHIER_THUOC / CASHIER_DV
 *  được GIỮ trong kiểu và trong hàm này vì event_log cũ có chứa chúng: một bản
 *  ghi kiểm toán không đọc lại được là một bản ghi kiểm toán vô dụng. Đừng gán
 *  chúng cho người mới. */
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
  PHARMACIST: "Dược sĩ",
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

// ─────────────────────────────────────────────────────────────────────────────
// TRƯỞNG CA CHỈ THẤY VIỆC ĐIỀU PHỐI (Quang, 2026-08-04).
//
// Trước đây vai này thấy 28/36 mục — gồm cả kho thuốc, bảng giá, duyệt kết quả,
// Command Center. Không phải vì ai đó quyết định thế, mà vì mỗi lần thêm một
// màn người ta thêm TRUONG_CA vào cho chắc. Một thanh bên 28 mục thì mục quan
// trọng nhất cũng chỉ là một dòng trong hai mươi tám dòng.
//
// Nay giữ đúng phần việc của ca trực: năm màn điều phối + Trang chủ, cộng
// "Luật đặt lịch" (xem ghi chú tại chính dòng đó — đó là một ngoại lệ có chủ ý,
// không phải sót).
//
// Các màn bị bỏ KHÔNG mất đi: Quản lý hệ thống vẫn vào được tất cả, và mỗi bộ
// phận vẫn giữ màn của mình. Bỏ ở đây chỉ là bỏ khỏi TẦM MẮT của Trưởng ca.
const NAV_ROLES: Record<string, "all" | ClinicRole[]> = {
  // --- bảng chạy trên workflow kernel -------------------------------------
  // Vai được thấy bảng nào là theo actor_roles của node trong danh mục, không
  // phải theo cảm tính: hàng đợi tiếp nhận là workspace bang_dieu_phoi
  // (RECEPTION + NURSE_ULTRASOUND cho bước xác minh), bàn khám là khu_bac_si,
  // bàn thu ngân là thu_ngan_dong_luot. Lễ tân chỉ có actor ở node đóng lượt,
  // không được mở board đối soát vì nó còn chứa hàng thanh toán/đối soát.
  // Trưởng ca và quản lý xem được tất cả để điều phối.
  // Check-out lượt khám — Lễ tân là người bấm; Trưởng ca/Quản lý bấm hộ được.
  "/reception/checkout": ["RECEPTION", "TRUONG_CA", "MANAGEMENT"],
  "/reception/queue": [
    "RECEPTION", "NURSE_ULTRASOUND", "MANAGEMENT",
  ],
  "/doctor/board": [
    "DOCTOR", "ULTRASOUND_DOCTOR", "TKYK", "MANAGEMENT",
  ],
  "/cashier/board": [
    "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "MANAGEMENT",
  ],
  // Số liệu vận hành: cùng ràng buộc như /ops — endpoint phía sau chỉ cho
  // MANAGEMENT, nên hiện mục này cho vai khác chỉ dẫn tới một trang 403.
  "/ops/telemetry": ["MANAGEMENT"],
  // Hồ sơ nhân sự — cùng ràng buộc với backend: routers/staff.py gác mọi thao
  // tác ghi bằng require_role(MANAGEMENT), nên mở mục này cho vai khác chỉ dẫn
  // tới một trang lưu gì cũng 403.
  "/nhan-su": ["MANAGEMENT"],

  "/home": "all",
  // Nhiệm vụ chăm sóc — thay thế cũ /cskh-today + /cskh/board.
  "/cskh-tasks": ["CSKH", "MANAGEMENT"],
  // Nhắc tái khám — cùng ràng buộc với backend: GET /api/v1/cskh/recalls gác
  // bằng require_role(CSKH, MANAGEMENT, TRUONG_CA), nên mở mục này cho vai khác
  // chỉ dẫn tới một trang trống vì 403. Ghi cuộc gọi đi qua canWriteIntake, đã
  // có đủ ba vai này.
  "/nhac-tai-kham": ["CSKH", "MANAGEMENT", "TRUONG_CA"],
  "/appointments": ["CSKH", "MANAGEMENT"],
  // Thông tin khách hàng (danh bạ + chi tiết + tra cứu tên/mã/SĐT) — CSKH/Lễ tân/QL
  // + Thu ngân (xem để đối chiếu khi thu tiền; canWriteIntake KHÔNG gồm CASHIER → chỉ xem).
  "/customers": ["CSKH", "RECEPTION", "MANAGEMENT", "CASHIER", "CASHIER_THUOC", "CASHIER_DV"],
  // TRƯỞNG CA — năm màn điều phối. Phải liệt kê TỪNG đường: requireNavAccess()
  // tra chính xác href, không so tiền tố, nên thiếu một dòng ở đây là màn đó đá
  // người dùng về /home mà không báo gì.
  "/truong-ca": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/hang-doi": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/canh-bao": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/lich-su": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/tv": ["TRUONG_CA", "MANAGEMENT"],
  // Danh sách bệnh nhân ĐÃ KHÁM (lần đầu / tái khám) — CSKH/Lễ tân/QL + BÁC SĨ.
  // Bác sĩ thấy TOÀN BỘ BN đã khám (như front desk); mở hồ sơ vẫn bị guard
  // patients/[id] (chỉ mở được BN của mình) — đúng mô hình quyền hiện tại.
  // + ĐIỀU DƯỠNG (feedback PM 23/6): nav "Thông tin bệnh nhân" để tra cứu BN +
  // xem lịch sử khám (giống bác sĩ). Sửa lâm sàng/sinh hiệu vẫn theo buổi khám.
  "/patient-list": ["RECEPTION", "MANAGEMENT", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST],
  // ĐIỀU DƯỠNG ĐÃ BỎ (feedback PM 23/6: ĐD không tạo BN).
  "/patients/new": ["RECEPTION", "MANAGEMENT"],
  // /checkin đã chuyển hẳn lên Trang chủ (HomeCheckin) — route cũ đã xóa.
  // Lễ tân được THÊM vào: thấy "Công việc của tôi" nhưng ở chế độ CHỈ XEM
  // (clone giao diện board bác sĩ, khóa mọi nút sửa — xem isTasksReadOnly).
  // TKYK (Thư ký Y khoa): vào hàng đợi khám của MỌI bác sĩ để NHẬP HỘ bệnh án
  // (canWriteClinical đã =true). Routing → DoctorWorkBoard (xem tasks/page.tsx).
  "/tasks": ["MANAGEMENT", "RECEPTION", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST],
  // Hàng đợi XN + Dịch vụ: điều dưỡng/KTV thực hiện (+ Quản lý xem).
  "/lab-queue": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  "/service-queue": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  // ĐD siêu âm: hàng đợi BN sắp khám SA + hàng đợi XN 3 trạng thái + in phiếu.
  "/sono": ["NURSE_ULTRASOUND", "MANAGEMENT"],
  // Bộ phận Siêu âm (4 màn). Khác /sono: đó là hàng đợi điều dưỡng chạy trên
  // service_log; đây là màn của cả bộ phận — hàng chờ, phòng SA1–SA3, soạn kết
  // quả, tra cứu phiếu đã ký. Danh sách vai phải khớp ULTRASOUND_ROLES ở
  // ultrasound_board_service.py; lệch nhau thì có người thấy nút mà bấm vào bị
  // 403, hoặc tệ hơn: vào được màn mà backend mới là nơi từ chối.
  "/sieu-am": [
    "ULTRASOUND_DOCTOR",
    "NURSE_ULTRASOUND",
    "TKYK",
    "TRUONG_CA",
    "MANAGEMENT",
  ],
  // Bảng số thứ tự GỌI KHÁM (ưu tiên người có hẹn). Gọi theo tên — xem chung như /tasks.
  // TẠM ẨN (Quang 2026-07-03): [] = không vai nào thấy sidebar + gõ URL bị redirect
  // /home (requireNavAccess). Mở lại: khôi phục danh sách vai dưới đây.
  // ["CSKH", "MANAGEMENT", "RECEPTION", "TRUONG_CA", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST]
  "/queue": [],
  // Đóng "đợt khám" chờ xác nhận (BS khám xong không hẹn lần sau) — việc CSKH/vận hành.
  "/episodes": ["MANAGEMENT"],
  // Thu ngân: bảng giá tách 2 trang (thuốc / dịch vụ), gate theo VAI tách (mỗi
  // vai chỉ thấy màn của mình). CASHIER = superset (thấy cả hai), Quản lý xem/sửa cả hai.
  // ("Công việc của tôi" thu ngân nằm ở /tasks, gate bằng entry /tasks bên dưới.)
  "/cashier/thuoc": ["CASHIER_THUOC", "CASHIER", "MANAGEMENT"],
  "/cashier/dich-vu": ["CASHIER_DV", "CASHIER", "MANAGEMENT"],
  // Nhà thuốc — Dược sĩ (PHARMACIST) + Quản lý/Trưởng ca xem.
  "/pharmacy": ["PHARMACIST", "MANAGEMENT"],
  "/pharmacy/history": ["PHARMACIST", "MANAGEMENT"],
  "/pharmacy/consult": ["PHARMACIST", "MANAGEMENT"],
  "/pharmacy/inventory": ["PHARMACIST", "MANAGEMENT"],
  // MỌI vai trò tự đăng ký ca của mình (CSKH, thu ngân... cũng cần); Quản lý +
  // Trưởng ca xếp cả bảng. Ca tự đăng ký vào trạng thái chờ duyệt (xem /api/roster).
  "/schedule": "all",
  "/work-sessions": ["MANAGEMENT"],
  "/reports": ["MANAGEMENT"],
  // Lịch sử thao tác (audit log) — CSKH + Quản lý + Trưởng ca.
  "/audit-log": ["CSKH", "MANAGEMENT"],
  // Duyệt kết quả — Bác sĩ + TKYK + Quản lý/Trưởng ca xem.
  "/result-review": ["DOCTOR", "ULTRASOUND_DOCTOR", "TKYK", "MANAGEMENT"],
  "/ops": ["MANAGEMENT"],
  // Luật đặt lịch (khung giờ / số chỗ) — Trưởng ca + Quản lý sửa được.
  // Trang riêng vì /settings (tạo user) vẫn chỉ MANAGEMENT.
  // GIỮ CHO TRƯỞNG CA — ngoại lệ có chủ ý giữa đợt dọn thanh bên.
  //
  // Quang chốt (2026-08-03): *"trưởng ca và quản lý hệ thống của phòng khám
  // Dr4women có thể điều chỉnh số lượng slot trong khung giờ nhất định"*. Backend
  // đã theo đúng quyết định đó (_BOOKING_POLICY_GUARD = TRUONG_CA + MANAGEMENT),
  // nên bỏ mục này khỏi thanh bên sẽ để lại một quyền mà không có đường đi tới.
  //
  // Lưu ý: Notion §CSKH tiêu chí 7 viết "chỉ quản lý hệ thống được thay đổi quy
  // tắc và sức chứa" — mâu thuẫn với quyết định trên. Quyết định trực tiếp của
  // Quang thắng; ghi lại ở đây để lần sau không ai "sửa lại cho khớp Notion".
  "/settings/booking-policy": ["TRUONG_CA", "MANAGEMENT"],
  // Cấu trúc phòng khám (cơ sở/tầng/phòng, ai làm được bước nào) — CHỈ Quản lý.
  // Khác /settings/booking-policy (Trưởng ca sửa được số chỗ): đổi sơ đồ phòng
  // là đổi nơi bệnh nhân được gửi tới, và bảng điều phối đọc thẳng từ đó.
  "/settings/clinic-config": ["MANAGEMENT"],
  // Cài đặt (tạo user / cấu hình hệ thống) = CHỈ Quản lý — ranh giới "thấp hơn
  // quản lý hệ thống" của Trưởng ca.
  "/settings": ["MANAGEMENT"],
  // Command Center — Cổng trung tâm điều khiển toàn hệ thống.
  // Chỉ Quản lý + Trưởng ca (isOpsAdmin) mới được vào.
  "/portal": ["MANAGEMENT"],
};

export function canSeeNav(role: ClinicRole | null, href: string): boolean {
  const rule = NAV_ROLES[href];
  if (!rule || rule === "all") return true;
  return role !== null && rule.includes(role);
}
