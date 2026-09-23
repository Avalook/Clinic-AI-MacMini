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
  | "PHARMACIST"
  // Màn hình TV phòng chờ — KHÔNG phải người, là cái máy treo tường.
  // Backend từ chối vai này ở mọi endpoint trừ bảng gọi số; ở đây nó chỉ tồn
  // tại để layout biết mà đưa thẳng ra /display thay vì mở bảng điều khiển.
  | "DISPLAY"
  // NGƯỜI NGOÀI PHÒNG KHÁM — lab, phòng chụp. Vào để gửi kết quả họ vừa làm.
  // Backend từ chối vai này ở MỌI endpoint trừ hai đường của riêng nó
  // (identity.py: `get_current_identity` chặn, `get_partner_identity` mở), nên
  // ở đây nó chỉ cần đúng một mục trên thanh bên và không có gì khác.
  | "PARTNER";

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
  "DISPLAY",
  "PARTNER",
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

/** Quyền ghi ở vùng Chăm sóc khách hàng.
 *
 * Backend `cskh_service.INTAKE_ROLES` dùng đúng bốn vai này. Tách tên capability
 * ở UI để một vai chỉ được mở danh bạ (như Thu ngân) không vô tình nhận toàn bộ
 * nút POST chỉ vì nó có quyền đọc `/customers`.
 */
export function canOperateCustomerCare(role: ClinicRole | null): boolean {
  return canWriteIntake(role);
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

/** Landing path after a role is picked. */
export function roleLanding(role: ClinicRole | null): string {
  // Đối tác không có trang chủ để mà xem — họ vào đúng việc của mình.
  if (role === "PARTNER") return "/doi-tac";
  // Không còn "/tasks" (màn cũ, gộp 18/09/2026 — docs/SITEMAP.md mục C).
  // Bác sĩ siêu âm đứng phòng siêu âm; bác sĩ và thư ký vào bàn khám.
  // Không còn mã phòng viết cứng (CORE-C): vào danh sách phòng, chọn phòng.
  if (isUltrasoundDoctorRole(role)) return "/phong";
  if (isDoctorRole(role)) return "/ban-kham";
  // Trưởng ca có màn làm việc riêng (board "Theo dõi buổi") như bác sĩ vào /tasks.
  if (isTruongCaRole(role)) return "/truong-ca";
  return "/home";
}

export const ROLE_LABEL: Record<ClinicRole, string> = {
  DOCTOR: "Bác sĩ",
  ULTRASOUND_DOCTOR: "Bác sĩ Siêu âm",
  // "Điều dưỡng", không phải "Điều dưỡng / Phụ siêu âm" (Tuyền chốt): họ làm
  // sinh hiệu, lấy mẫu, phụ phòng dịch vụ và nay cả đặt chỉ định. Cái tên ghép
  // kia bó họ vào một phòng.
  NURSE_ULTRASOUND: "Điều dưỡng",
  TKYK: "Thư ký Y khoa",
  CSKH: "CSKH",
  MANAGEMENT: "Quản lý",
  RECEPTION: "Lễ tân",
  CASHIER: "Thu ngân",
  CASHIER_THUOC: "Thu ngân thuốc",
  CASHIER_DV: "Thu ngân dịch vụ",
  TRUONG_CA: "Trưởng ca",
  PHARMACIST: "Dược sĩ",
  DISPLAY: "Màn hình phòng chờ",
  PARTNER: "Đối tác",
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
// Nay giữ đúng phần việc của ca trực: năm màn điều phối + Trang chủ, cộng hai
// ngoại lệ có chủ ý: "Luật đặt lịch" và `/customers`. Ngoại lệ thứ hai khớp
// backend CSKH, nơi TRUONG_CA được phép xử lý phát sinh trong ca.
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
  // TRƯỞNG CA BỎ (Tuyền 16/09/2026): *"không cần check-out hộ lễ tân… trưởng ca
  // chỉ cần nhìn toàn cảnh và điều phối chứ không thay những người khác làm
  // việc"*. Quyền backend giữ nguyên để Quản lý vẫn bấm hộ được khi cần.
  "/reception/checkout": ["RECEPTION", "MANAGEMENT"],
  "/reception/queue": [
    "RECEPTION", "NURSE_ULTRASOUND", "MANAGEMENT",
  ],
  // Đo sinh hiệu — khớp VITALS_ROLES ở luot_kham_service.py (+ Quản lý xem).
  "/do-sinh-hieu": ["NURSE_ULTRASOUND", "RECEPTION", "DOCTOR", "MANAGEMENT"],
  // BÀN KHÁM theo phòng (Tuyền chốt 16/09/2026) — thay /doctor/board và năm
  // màn /kham/*. Bác sĩ khám, thư ký đi kèm nhập hộ + bấm Bắt đầu/Khám xong.
  "/ban-kham": ["DOCTOR", "TKYK", "MANAGEMENT"],
  // BÀN KHÁM TƯ VẤN (24/09/2026): mặc định bác sĩ; ai được cấp khối "Khám tư
  // vấn" cũng vào được qua NAV_QUYEN.
  "/tu-van": ["DOCTOR", "MANAGEMENT"],
  // BẢNG HÀNH TRÌNH CHUNG (nhóm 3, 24/09/2026): mỗi khách hôm nay đang ở đâu /
  // đã xong gì / còn chờ gì — cho MỌI vai nội bộ (khớp GOI_DUOC ở
  // xem_luot_service.py). Nội dung lâm sàng không có trên bảng này.
  "/hanh-trinh": [
    "CSKH", "RECEPTION", "TRUONG_CA", "MANAGEMENT", "DOCTOR", "TKYK",
    "ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND", "CASHIER", "CASHIER_DV",
    "CASHIER_THUOC", "PHARMACIST",
  ],
  // Bàn khám MỘT phòng (`/ban-kham/<room_id>`) dùng chung luật `/ban-kham` —
  // xem `luatNav`. Không còn một dòng cho mỗi mã phòng (CORE-C, 23/09/2026).
  // LỄ TÂN KIÊM THU NGÂN + KHO THUỐC ở Kim Ngưu (Tuyền 16/09/2026: "trong màn
  // của họ chưa có thu ngân, nên tích hợp thu ngân vào lễ tân luôn, kho thuốc
  // cũng ở lễ tân luôn") — vai RECEPTION vào được quầy thu, quầy thuốc, kho.
  "/thu-ngan/dich-vu": ["RECEPTION", "CASHIER", "CASHIER_DV", "MANAGEMENT"],
  "/thu-ngan/thuoc": ["RECEPTION", "CASHIER", "CASHIER_THUOC", "MANAGEMENT"],
  // Hồ sơ nhân sự — cùng ràng buộc với backend: routers/staff.py gác mọi thao
  // tác ghi bằng require_role(MANAGEMENT), nên mở mục này cho vai khác chỉ dẫn
  // tới một trang lưu gì cũng 403.
  "/nhan-su": ["MANAGEMENT"],

  "/home": "all",
  // GỘP 18/09/2026 (Tuyền: "gộp hết" — docs/SITEMAP.md): /cskh-tasks,
  // /episodes, /work-sessions, /tasks, /queue, /cashier/board, /portal,
  // /ops/telemetry chỉ còn chuyển hướng sang màn chuẩn, nên không còn dòng nào
  // ở bảng này. Đo trên prod trước khi gộp: cskh_action 0 dòng, work_session 0
  // dòng, care_episode PENDING_CLOSE 0 dòng và không code nào còn tạo ra nó.
  "/lich-do-ve": ["MANAGEMENT"],
  // Nhắc tái khám — cùng ràng buộc với backend: GET /api/v1/cskh/recalls gác
  // bằng require_role(CSKH, MANAGEMENT, TRUONG_CA), nên mở mục này cho vai khác
  // chỉ dẫn tới một trang trống vì 403. Ghi cuộc gọi đi qua canWriteIntake, đã
  // có đủ ba vai này.
  //
  // CSKH bị gỡ khỏi thanh bên theo chốt trên. LƯU Ý ĐÃ BÁO QUANG: màn này KHÔNG
  // trùng /customers — nó liệt người bác sĩ đã hẹn quay lại mà CHƯA có lịch,
  // tức danh sách "còn thiếu lịch", còn /customers xoay quanh lịch ĐÃ CÓ. Gỡ
  // mục này là CSKH không còn đường vào danh sách ấy từ thanh bên.
  // Trưởng ca bỏ (16/09/2026) — gọi nhắc tái khám là việc CSKH.
  "/nhac-tai-kham": ["MANAGEMENT"],
  // LỄ TÂN ĐƯỢC VÀO MÀN ĐẶT LỊCH (Tuyền 16/09/2026).
  //
  // Trước đó vai này KHÔNG có lối vào nào, trong khi hai nút "Đặt lịch mới" ở
  // Danh sách bệnh nhân và Quản lý khách hàng vẫn trỏ thẳng vào đây — Lễ tân
  // bấm là bị đá về /home, không một dòng báo.
  //
  // Và nay nó là đường CHÍNH: "khách vãng lai" bỏ đi, chỉ còn "đến trực tiếp" —
  // chưa có hồ sơ thì tạo ở tab "Thêm", có rồi thì chọn tên và đặt, kênh đặt
  // ghi "Trực tiếp". Backend đã sẵn luật ấy từ 15/09: kênh Trực tiếp + hôm nay
  // + người đặt thuộc CHECKIN_ROLES ⇒ tự check-in và mở lượt khám.
  "/appointments": ["CSKH", "RECEPTION", "MANAGEMENT"],
  // Thông tin khách hàng — CSKH/Lễ tân/QL/Trưởng ca thao tác; Thu ngân chỉ xem
  // để đối chiếu khi thu tiền (canOperateCustomerCare không gồm CASHIER).
  // LỄ TÂN ĐÃ BỎ KHỎI ĐÂY (Tuyền 16/09/2026: *"bỏ nốt trang công việc của tôi,
  // quản lý khách hàng luôn vì thừa"*). Quầy không gọi điện chăm sóc khách:
  // việc của họ là đón, xếp hàng, đóng lượt. Quyền GHI ở backend giữ nguyên
  // (`cskh_service.INTAKE_ROLES` vẫn có RECEPTION) — bỏ ở đây là bỏ khỏi tầm
  // mắt, không bỏ khả năng; trả lại chỉ là thêm một dòng.
  "/customers": [
    "CSKH",
    "MANAGEMENT",
    "TRUONG_CA",
    "CASHIER",
    "CASHIER_THUOC",
    "CASHIER_DV",
  ],
  // TRƯỞNG CA — năm màn điều phối. Phải liệt kê TỪNG đường: requireNavAccess()
  // tra chính xác href, không so tiền tố, nên thiếu một dòng ở đây là màn đó đá
  // người dùng về /home mà không báo gì.
  // ĐỐI TÁC: đúng MỘT màn, và không vai nào khác cần nó. Quản lý có mặt để xem
  // được đối tác đang nhìn thấy gì — không có đường ấy thì không ai kiểm được
  // lời hứa "họ chỉ thấy việc của họ" ngoài cách mượn tài khoản đối tác.
  "/doi-tac": ["PARTNER", "MANAGEMENT"],
  "/truong-ca": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/hang-doi": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/lich-su": ["TRUONG_CA", "MANAGEMENT"],
  "/truong-ca/tv": ["TRUONG_CA", "MANAGEMENT"],
  // Danh sách bệnh nhân ĐÃ KHÁM (lần đầu / tái khám) — CSKH/Lễ tân/QL + BÁC SĨ.
  // Bác sĩ thấy TOÀN BỘ BN đã khám (như front desk); mở hồ sơ vẫn bị guard
  // patients/[id] (chỉ mở được BN của mình) — đúng mô hình quyền hiện tại.
  // + ĐIỀU DƯỠNG (feedback PM 23/6): nav "Thông tin bệnh nhân" để tra cứu BN +
  // xem lịch sử khám (giống bác sĩ). Sửa lâm sàng/sinh hiệu vẫn theo buổi khám.
  // CSKH BỊ SÓT: dòng ghi chú ngay trên đây nói "CSKH/Lễ tân/QL + BÁC SĨ" từ
  // đầu, nhưng mảng thì không có CSKH — nên người gọi điện chăm sóc khách hàng
  // là vai DUY NHẤT không tra được hồ sơ và lịch sử khám của chính người họ
  // đang gọi. Thêm vào cho khớp với điều đã hứa.
  "/patient-list": ["RECEPTION", "MANAGEMENT", "CSKH", "CASHIER", "CASHIER_THUOC", "CASHIER_DV", "TKYK", "NURSE_ULTRASOUND", ...DOCTOR_ROLES_LIST],
  // ĐIỀU DƯỠNG ĐÃ BỎ (feedback PM 23/6: ĐD không tạo BN).
  // Hàng chờ xếp bác sĩ: quản lý và trưởng ca xếp; CSKH MỞ ĐƯỢC (Tuyền chốt
  // 16/09/2026) — lịch vượt sức chứa về đây cho CSKH gọi khách đổi ca, và
  // thông báo gửi CSKH trỏ thẳng vào trang này. Trước đó CSKH bấm thông báo bị
  // đá về /home. Không bày trên thanh bên của CSKH (xem AN_KHOI_THANH_BEN).
  // Trưởng ca bỏ (16/09/2026) — xếp bác sĩ cho lịch chờ là việc Quản lý/CSKH;
  // trưởng ca đổi bác sĩ ĐANG KHÁM ngay trong màn điều phối.
  "/appointments/cho-xep-bac-si": ["MANAGEMENT", "CSKH"],
  "/patients/new": ["RECEPTION", "MANAGEMENT"],
  // PHÒNG DỊCH VỤ (Tuyền chốt 16/09/2026) — thay /lab-queue, /service-queue,
  // /sono, /sieu-am. Ai BẤM được là do bước của chỉ định quyết ở máy chủ
  // (thủ thuật: chỉ bác sĩ); danh sách dưới đây là ai VÀO được phòng.
  //
  // PHÒNG LÀ TÀI NGUYÊN (CORE-C, 23/09/2026): định danh là room_id, tên đổi tự
  // do. MỘT luật cho mọi `/phong/<room_id>` (xem `luatNav`) = hợp đúng các vai
  // tám dòng mã phòng cũ từng cho vào. Vào được phòng ≠ làm được việc: mọi lệnh
  // vẫn hỏi capability ở máy chủ, và được xếp vào phòng KHÔNG tự cấp quyền.
  // Lễ tân KHÔNG có ở đây: dòng cũ `/phong/KN-LAYMAU` cho lễ tân vào phòng lấy
  // mẫu, nhưng lễ tân đứng Lấy mẫu hôm nay đã mang vai điều dưỡng theo vị trí,
  // và ai được cấp khối "Thực hiện dịch vụ" thì vào qua cửa quyền (NAV_QUYEN).
  "/phong": ["DOCTOR", "ULTRASOUND_DOCTOR", "NURSE_ULTRASOUND", "TKYK", "MANAGEMENT"],
  // Thu ngân: bảng giá tách 2 trang (thuốc / dịch vụ), gate theo VAI tách (mỗi
  // vai chỉ thấy màn của mình). CASHIER = superset (thấy cả hai), Quản lý xem/sửa cả hai.
  "/cashier/thuoc": ["RECEPTION", "CASHIER_THUOC", "CASHIER", "MANAGEMENT"],
  "/cashier/dich-vu": ["RECEPTION", "CASHIER_DV", "CASHIER", "MANAGEMENT"],
  // Nhà thuốc — Dược sĩ (PHARMACIST) + Quản lý/Trưởng ca xem.
  "/pharmacy": ["RECEPTION", "PHARMACIST", "MANAGEMENT"],
  "/pharmacy/history": ["PHARMACIST", "MANAGEMENT"],
  "/pharmacy/consult": ["PHARMACIST", "MANAGEMENT"],
  "/pharmacy/inventory": ["RECEPTION", "PHARMACIST", "MANAGEMENT"],
  // MỌI vai trò tự đăng ký ca của mình (thu ngân, điều dưỡng... cũng cần); Quản
  // lý + Trưởng ca xếp cả bảng. Ca tự đăng ký vào trạng thái chờ duyệt (xem
  // /api/roster).
  //
  // TRỪ CSKH (Quang chốt 09/08/2026): lịch làm việc đã nằm nguyên trên TRANG
  // CHỦ của họ (bảng "Lịch làm việc" cuối trang /home), nên mục thanh bên là
  // đường thứ hai tới cùng một bảng.
  //
  // Viết ra từng vai thay vì "all" — thiếu một dòng ở đây là vai đó mất màn
  // hình mà không báo gì, nên danh sách này phải là ALL_ROLES trừ đúng CSKH,
  // tính bằng code chứ không chép tay.
  // Đối tác (người NGOÀI phòng khám) và màn TV cũng không có lịch làm việc
  // (17/09/2026: thanh bên đối tác hiện "Lịch làm việc").
  "/schedule": ALL_ROLES.filter((r) => r !== "CSKH" && r !== "PARTNER" && r !== "DISPLAY"),
  "/reports": ["MANAGEMENT"],
  // Lịch sử thao tác (audit log) — CSKH + Quản lý + Trưởng ca.
  "/audit-log": ["CSKH", "MANAGEMENT"],
  // Duyệt kết quả theo chỉ định — thay /result-review. Chỉ bác sĩ (duyệt là
  // quyết định chuyên môn; thư ký không có nút Duyệt — Notion v1.0.0).
  "/duyet-ket-qua": ["DOCTOR", "ULTRASOUND_DOCTOR", "MANAGEMENT"],
  // Khớp actor_roles của hai node OPS-* trong danh mục (migration 20260923000007).
  "/viec-can-xu-ly": ["MANAGEMENT", "CASHIER", "TRUONG_CA", "DOCTOR"],
  // Vào được màn không có nghĩa là cấp được quyền: backend đòi capability
  // `permission.manage`, nên người không có nó chỉ xem chứ bấm là bị từ chối.
  "/phan-quyen": ["MANAGEMENT"],
  // Xác nhận tệp kết quả external — phân quyền bằng capability ket_qua.xac_nhan.
  // Không giới hạn role ở đây; backend API và page fail-closed bằng capability.
  "/xac-nhan-ket-qua": ALL_ROLES.filter((r) => r !== "PARTNER" && r !== "DISPLAY"),
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
  // Chỉ Quản lý đặt số khách online/trực tiếp (Tuyền chốt 15/09/2026).
  "/settings/booking-policy": ["MANAGEMENT"],
  // Cấu trúc phòng khám (cơ sở/tầng/phòng, ai làm được bước nào) — CHỈ Quản lý.
  // Đổi sơ đồ phòng là đổi nơi bệnh nhân được gửi tới, và bảng điều phối đọc
  // thẳng từ đó.
  "/settings/clinic-config": ["MANAGEMENT"],
  // Khối chỉnh dây nối nghiệp vụ (nhóm 5, 24/09/2026) — quản lý; ai được cấp
  // quyền `config.wiring.manage` cũng vào được qua NAV_QUYEN.
  "/settings/day-noi": ["MANAGEMENT"],
  // Cài đặt (tạo user / cấu hình hệ thống) = CHỈ Quản lý — ranh giới "thấp hơn
  // quản lý hệ thống" của Trưởng ca.
  "/settings": ["MANAGEMENT"],
  "/settings/tai-khoan": ["MANAGEMENT"],
};

/** ẨN KHỎI THANH BÊN — NHƯNG KHÔNG CHẶN ĐƯỜNG VÀO.
 *
 *  Quang chốt 09/08/2026: *"chỉ cần xem tổng quan thôi, không cần xem màn của
 *  người khác vậy vất vả quá"*. Thanh bên của Quản lý đang có hơn ba mươi mục,
 *  phần lớn là màn thao tác hằng ngày của CSKH / Lễ tân.
 *
 *  VÌ SAO KHÔNG XOÁ THẲNG KHỎI `NAV_ROLES`. Bảng ấy vừa dựng thanh bên VỪA gác
 *  cửa trang (`requireNavAccess` gọi chính `canSeeNav`). Gỡ Quản lý khỏi
 *  `/customers` là gỡ luôn quyền MỞ trang đó — mà nút "Xác nhận lịch trước 7
 *  ngày →" ở màn Chờ xếp bác sĩ vừa dựng xong lại đi thẳng tới đấy. Người dùng
 *  bấm một nút do chính hệ thống bày ra rồi bị đá về /home, không lời giải
 *  thích.
 *
 *  Nên tách hai câu hỏi khác nhau: "có được vào không" (NAV_ROLES) và "có bày
 *  ra trên thanh bên không" (bảng này).
 */
const AN_KHOI_THANH_BEN: Partial<Record<ClinicRole, readonly string[]>> = {
  MANAGEMENT: [
    "/appointments",
    "/customers",
    "/patients/new",
    "/nhac-tai-kham",
    "/reception/checkout",
    "/reception/queue",
  ],
  // PHÒNG CỤ THỂ không bày ra ngày KHÔNG có ca (Tuyền 16/09/2026): ngày có ca,
  // thanh bên mở đúng phòng người ấy đứng (dựng từ lịch trực + room_id, CORE-C
  // 23/09/2026). Ngày không có ca chỉ còn MỘT mục "Phòng dịch vụ" (`/phong`)
  // dẫn tới danh sách phòng — không còn chín mục mã phòng viết cứng.
  // Thanh bên CSKH giữ 5 mục (Tuyền 16/09/2026): việc vượt sức chứa đến qua
  // khung báo + thông báo, không thêm mục.
  CSKH: ["/appointments/cho-xep-bac-si"],
};

/** Mục này có hiện trên thanh bên của vai ấy không. Dùng CHO GIAO DIỆN;
 *  gác cửa trang vẫn là `canSeeNav`. */
export function hienTrenThanhBen(
  role: ClinicRole | null,
  href: string,
  /** Capability người này đang có. Màn nào quyền mở được thì bày ra, dù vai
   *  không có trong `NAV_ROLES` — chốt "sidebar dựng theo quyền của từng
   *  người". Bỏ trống = chỉ xét vai, y như trước. */
  quyen: readonly string[] = [],
): boolean {
  if (quyenMoDuocMan(quyen, href)) return true;
  // MENU theo LUẬT GỐC, không theo công tắc mở quyền.
  //
  // Hai câu hỏi khác nhau: "được VÀO màn này không" (canSeeNav — đang mở tạm
  // cho mọi vai) và "màn này có nên NẰM trong menu của vai này không". Dùng
  // chung một hàm thì từ ngày mở quyền, thanh bên của một điều dưỡng không có
  // ca hôm nay dài gần bốn mươi mục — năm màn khám, hai quầy thu ngân, kho
  // thuốc… — và bốn mục cô ấy thật sự cần chìm ở giữa. Mở quyền là để không bị
  // CHẶN, không phải để bị CHÔN.
  //
  // Ngày có ca, thanh bên đi theo vị trí (mucHienRa) và không qua hàm này.
  if (!canSeeNavGoc(role, href)) return false;
  if (!role) return true;
  return !(AN_KHOI_THANH_BEN[role] ?? []).includes(href);
}

// ── MỞ QUYỀN TẠM THỜI (Tuyền chốt 16/09/2026) ──────────────────────────────
//
// *"tất cả các tài khoản đều có thể thao tác đã, đừng bị phụ thuộc lịch khám
// nữa, trừ bác sĩ ra thui, tại giờ đang rối, trước mắt giải quyết vậy đã"*.
//
// Backend đã nới ở `identity.mo_quyen_tam_thoi`. Nới một mình backend thì chưa
// đủ: thanh bên vẫn ẩn màn, và người dùng không có đường nào bấm tới cái cửa
// vừa mở.
//
// ⚠️ ĐÂY LÀ BIẾN LÚC DỰNG ẢNH, không phải lúc chạy. Next nhét thẳng giá trị
// `NEXT_PUBLIC_*` vào mã trình duyệt khi build, nên đổi nó phải DỰNG LẠI ảnh
// dashboard — khác với backend, chỉ cần khởi động lại container. Khác biệt ấy
// đáng nhớ: tắt một nửa là quyền lệch nhau giữa hai tầng.
const MO_QUYEN_TAM_THOI =
  (process.env.NEXT_PUBLIC_MO_QUYEN_TAM_THOI ?? "1").toLowerCase() !== "0";

//: Màn KHÔNG mở theo công tắc. Không phải vì bí mật — backend vẫn gác chúng —
//: mà vì chúng không phải "thao tác" của ai cả: cổng quản trị, cấu hình hệ
//: thống, báo cáo, vận hành. Mở ra thì thanh bên của điều dưỡng dài 35 mục và
//: bốn mục họ thật sự cần bị đẩy xuống dưới, tức là dựng một bức tường khác.
const KHONG_MO_THEO_CONG_TAC = [
  "/console",
  "/ops",
  "/settings",
  "/reports",
  "/admin",
  // Hai màn của người NGOÀI phòng khám. Chúng đóng theo thiết kế, và công tắc
  // "mở tạm" không được phép chạm vào — xem `test_mo_quyen_tam_thoi.py`.
  "/doi-tac",
  "/display",
];

function moTheoCongTac(href: string): boolean {
  if (!MO_QUYEN_TAM_THOI) return false;
  return !KHONG_MO_THEO_CONG_TAC.some(
    (p) => href === p || href.startsWith(`${p}/`),
  );
}


/** Cửa THỨ HAI: capability mở màn, không cần vai.
 *
 *  Chốt của Tuyền: *"Quản lý cấp được bất kỳ khối nào cho bất kỳ ai, kể cả cho
 *  lễ tân màn siêu âm"* và *"Sidebar dựng theo quyền của từng người"*. Bảng
 *  `NAV_ROLES` ở trên chỉ biết VAI, nên một lễ tân được cấp khối Siêu âm vẫn
 *  không nhìn thấy màn — quyền có mà lối vào thì không.
 *
 *  Bảng này là cửa thứ hai, mở THÊM chứ không thay: ai vào được theo vai thì
 *  vẫn vào, ai có quyền thì cũng vào. Không ai mất lối cũ trong lúc chuyển.
 *
 *  Đây là bước strangler: mỗi lần một màn chuyển hẳn sang quyền thì xoá vai của
 *  nó khỏi `NAV_ROLES`. Danh sách vai chỉ được phép NGẮN ĐI.
 *
 *  VÀO ĐƯỢC MÀN ≠ LÀM ĐƯỢC VIỆC. Mọi lệnh vẫn hỏi capability ở backend; bảng
 *  này chỉ quyết cái màn có hiện trong thanh bên hay không. */
const NAV_QUYEN: Record<string, string[]> = {
  "/reception/queue": ["reception.checkin.perform"],
  "/reception/checkout": ["reception.checkin.perform"],
  "/do-sinh-hieu": ["vitals.measure"],
  "/ban-kham": ["clinical.order.place"],
  "/tu-van": ["clinical.intake.perform"],
  "/settings/day-noi": ["config.wiring.manage"],
  "/truong-ca": ["service.routing.view"],
  "/phong": ["service.execute.start"],
  "/duyet-ket-qua": ["result.form.fill"],
  "/viec-can-xu-ly": ["service.routing.view"],
  "/phan-quyen": ["permission.manage"],
  "/thu-ngan/dich-vu": ["payment.service.collect"],
  "/thu-ngan/thuoc": ["payment.service.collect"],
};

/** Màn theo phòng (`/phong/<room_id>`) dùng chung quyền của `/phong`. */
function quyenCuaMan(href: string): string[] {
  if (NAV_QUYEN[href]) return NAV_QUYEN[href];
  for (const [duong, quyen] of Object.entries(NAV_QUYEN)) {
    if (href.startsWith(`${duong}/`)) return quyen;
  }
  return [];
}

/** Có quyền nào mở được màn này không. `quyen` là danh sách capability đang có. */
export function quyenMoDuocMan(quyen: readonly string[], href: string): boolean {
  const can = quyenCuaMan(href);
  return can.length > 0 && can.some((q) => quyen.includes(q));
}

/** Luật của một đường dẫn. `/phong/<room_id>` và `/ban-kham/<room_id>` dùng luật
 *  gốc của `/phong` / `/ban-kham` — CHỈ hai tiền tố này, không suy rộng: đường
 *  dẫn con của màn khác vẫn giữ nguyên hành vi cũ (CORE-C, 23/09/2026). */
const TIEN_TO_THEO_PHONG = ["/phong", "/ban-kham"] as const;
function luatNav(href: string): (typeof NAV_ROLES)[string] | undefined {
  if (NAV_ROLES[href]) return NAV_ROLES[href];
  const goc = TIEN_TO_THEO_PHONG.find((p) => href.startsWith(`${p}/`));
  return goc ? NAV_ROLES[goc] : undefined;
}

/** Luật gốc của NAV_ROLES, bỏ qua công tắc mở quyền. Chỉ dùng cho MENU. */
export function canSeeNavGoc(role: ClinicRole | null, href: string): boolean {
  const rule = luatNav(href);
  if (!rule || rule === "all") return true;
  return role !== null && rule.includes(role);
}

export function canSeeNav(role: ClinicRole | null, href: string): boolean {
  const rule = luatNav(href);
  if (!rule || rule === "all") return true;
  if (role === null) return false;
  // Vai ngoài phòng khám KHÔNG bao giờ được nới: cái tivi và đối tác chỉ có
  // đúng màn của mình, và đó là chốt chặn chứ không phải cách sắp xếp menu.
  if (role !== "DISPLAY" && role !== "PARTNER" && moTheoCongTac(href)) {
    return true;
  }
  return rule.includes(role);
}
