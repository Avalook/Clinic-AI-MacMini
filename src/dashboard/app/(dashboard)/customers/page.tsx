// "Thông tin khách hàng" — danh bạ khách (master-detail) KÈM lịch hẹn sắp tới.
// Server đọc patient qua Supabase RLS; lọc theo NGÀY TẠO (created_at) hoặc NGÀY
// HẸN (slot_start) để biết khách thuộc ngày/tuần nào (feedback 05/06). client
// (CustomersView) lo chọn + bôi hồng.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import {
  canWriteIntake,
  canManageAppt,
  canOperateCustomerCare,
} from "../../../lib/roles";
import { unaccentVi } from "../../../lib/validation";
import type { EditableAppt } from "./AppointmentEditModal";
import {
  vnTodayRangeUtc,
  vnMonthStartUtc,
  vnLocalToUtcISO,
  nowMs,
  mocMs,
  conToi,
  daQua,
  VN_OFFSET,
  VN_TZ,
  ngayVN,
} from "../../../lib/datetime";
import { currentWeekStartVn, shiftWeek } from "../../../lib/roster";
import type { DongLichSu } from "./so-tuong-tac";
import type { DongPhanHoi } from "./PhanHoiKhach";
import type { TepKetQuaRow } from "./TepKetQua";
import type { MocTaiKham } from "./NhacTaiKham";
import CustomersView, {
  type CustomerRow,
  type ApptInfo,
  type Opt,
  type Period,
  type ByDim,
  type ChuoiKham,
  type LuotKham,
  type HenGoiLai,
} from "./CustomersView";

/** Một mốc gọi nhắc tái khám, đúng hình dạng RecallJobService trả về. */
type RecallRaw = MocTaiKham & { clinic_patient_id: string };
import { listBookableDoctors } from "../../../lib/doctors-server";
import { fetchFromBackend } from "../../../lib/backend-proxy";

export const dynamic = "force-dynamic";

/** Đầu tháng SAU theo giờ VN, dạng UTC ISO (chặn cuối cửa sổ "Tháng này"). */
function vnNextMonthStartUtc(): string {
  const ymd = new Date().toLocaleDateString("en-CA", {
    timeZone: VN_TZ,
  });
  const [y, m] = ymd.split("-").map(Number);
  const ny = m === 12 ? y + 1 : y;
  const nm = m === 12 ? 1 : m + 1;
  return new Date(
    `${ny}-${String(nm).padStart(2, "0")}-01T00:00:00${VN_OFFSET}`,
  ).toISOString();
}

/** [start,end) UTC cho kỳ lọc theo giờ VN; null = "Tất cả". */
function windowFor(period: Period): { start: string; end: string } | null {
  if (period === "today") {
    const { startUtc, endUtc } = vnTodayRangeUtc();
    return { start: startUtc, end: endUtc };
  }
  if (period === "week") {
    const ws = currentWeekStartVn();
    return {
      start: vnLocalToUtcISO(ws, "00:00"),
      end: vnLocalToUtcISO(shiftWeek(ws, 1), "00:00"),
    };
  }
  if (period === "month") {
    return { start: vnMonthStartUtc(), end: vnNextMonthStartUtc() };
  }
  return null;
}

/** Supabase join trả object HOẶC array (tuỳ quan hệ) — lấy phần tử đầu. */
function pick1<T>(v: T | T[] | null | undefined): T | null {
  if (!v) return null;
  return Array.isArray(v) ? (v[0] ?? null) : v;
}

// KHÔNG ĐƯỢC ĐẶT CHÚ THÍCH BÊN TRONG CHUỖI NÀY.
//
// Nó trông như SQL nhưng KHÔNG PHẢI SQL: đây là tham số `select` của PostgREST,
// một danh sách cột phân cách bằng dấu phẩy. `--` không phải chú thích ở đây; nó
// là ký tự trong tên cột.
//
// Tôi đặt hai dòng `-- …` vào đây ngày 11/08/2026 để giải thích cột `updated_at`.
// Kết quả: PostgREST trả
//     failed to parse select parameter (…,--Thẻkhoálạcquancho…)
// và CẢ MÀN Quản lý khách hàng trắng. Câu giải thích cho người đọc đã giết chính
// thứ nó giải thích.
//
// Nó lọt qua vì tôi nghiệm thu tính năng ấy bằng đường API (PATCH /api/patients)
// mà không mở lại chính trang tiêu thụ dữ liệu này. Bài học: sửa truy vấn của
// trang nào thì phải MỞ trang đó, không chỉ gọi API của nó.
//
// `updated_at` = thẻ khoá lạc quan cho form sửa hồ sơ (mốc màn hình đã đọc).
// Xem PatientAdminEditor.save() và patient_service.update_patient().
const SELECT = `
  clinic_patient_id, patient_code, full_name, date_of_birth, birth_year,
  phone_primary, phone_secondary, gender, ethnicity, nationality,
  occupation, patient_objection, address, guardian_name, location_id, created_at,
  van_de_di_kham, linh_vuc, updated_at
`;

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    period?: string;
    by?: string;
    selected?: string;
    /** Trạng thái CSKH cần mở sẵn ở cột phải — chuông thông báo gửi kèm. */
    viec?: string;
    /** LƯỢT KHÁM đang xem (`appointment.id`). Thiếu = để màn tự chọn. */
    luot?: string;
  }>;
}) {
  await requireNavAccess("/customers");
  const role = await getClinicRole();
  // CSKH / Lễ tân / Quản lý: được SỬA thông tin hành chính ngay trong panel.
  const canEdit = canWriteIntake(role);
  const canOperateCskh = canOperateCustomerCare(role);
  // CSKH / Quản lý / Trưởng ca: được ĐỔI / HỦY lịch hẹn (bấm ô "Lịch hẹn sắp tới").
  const canManage = canManageAppt(role);
  const sp = await searchParams;
  const q = (sp.q ?? "").trim();
  const period: Period = (["today", "week", "month", "all"].includes(
    sp.period ?? "",
  )
    ? sp.period
    : "all") as Period;
  const by: ByDim = sp.by === "appt" ? "appt" : "created";
  const selected = (sp.selected ?? "").trim() || null;
  // VIỆC VÀ LƯỢT ĐI TỪ URL VÀO MÀN.
  //
  // Chuông thông báo gửi người trực tới đây kèm sẵn "khách nào" — nhưng cho tới
  // 10/08/2026 nó KHÔNG nói được "việc gì" và "lượt nào", nên bấm vào một thông
  // báo "hẹn gọi lại 23:30" chỉ mở đúng hồ sơ rồi buông tay: cột phải vẫn chạy
  // theo việc gấp nhất do view suy ra, thường là một việc khác hẳn.
  //
  // Hai tham số này cũng là thứ giữ được lượt đang xem qua F5 và qua một đường
  // dẫn gửi cho ca sau.
  const viec = (sp.viec ?? "").trim() || null;
  const luot = (sp.luot ?? "").trim() || null;
  const win = windowFor(period);

  const supabase = await getSupabaseServer();

  // Lọc THEO NGÀY HẸN: tìm khách có lịch trong cửa sổ trước → lấy danh sách id.
  // BỎ lịch đã hủy/không đến/BS từ chối — hủy lịch xong khách không còn "có hẹn".
  const DEAD_STATUSES = "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)";
  let apptFilterIds: string[] | null = null;
  if (by === "appt" && win) {
    const { data: inWin } = await supabase
      .from("appointment")
      .select("clinic_patient_id")
      .gte("slot_start", win.start)
      .lt("slot_start", win.end)
      .not("clinic_patient_id", "is", null)
      .not("status", "in", DEAD_STATUSES)
      .limit(3000);
    apptFilterIds = [
      ...new Set((inWin ?? []).map((a) => a.clinic_patient_id as string)),
    ];
  }

  // Tìm tên KHÔNG phân biệt dấu (D11): cộng thêm điều kiện trên cột
  // full_name_unaccent (migration 039 — bỏ dấu + thường). useUnaccent=false để
  // fallback nếu cột chưa migrate (KHÔNG đổi DB, chỉ tái dùng cột sẵn có).
  const t = q ? q.replace(/[,()%*]/g, " ").trim() : "";
  const buildPatientQuery = (useUnaccent: boolean) => {
    let query = supabase
      .from("patient")
      .select(SELECT)
      .order("created_at", { ascending: false })
      .limit(300);
    if (by === "created" && win) query = query.gte("created_at", win.start);
    if (by === "appt" && apptFilterIds) {
      // Rỗng → sentinel để .in() không lỗi và trả 0 dòng.
      query = query.in(
        "clinic_patient_id",
        apptFilterIds.length
          ? apptFilterIds
          : ["00000000-0000-0000-0000-000000000000"],
      );
    }
    if (t) {
      const ors = [
        `full_name.ilike.%${t}%`,
        `patient_code.ilike.%${t}%`,
        `phone_primary.ilike.%${t}%`,
      ];
      if (useUnaccent) {
        ors.push(`full_name_unaccent.ilike.%${unaccentVi(t)}%`);
      }
      query = query.or(ors.join(","));
    }
    return query;
  };

  const [patRes, locRes, svcRes, docRes] = await Promise.all([
    buildPatientQuery(true),
    supabase.from("clinic_location").select("id, name").order("name"),
    // Nạp dịch vụ + bác sĩ khi vai INTAKE (đặt/đổi/hủy lịch) — cho cả modal đổi
    // lịch (canManage) lẫn nút "Đặt lịch" (canEdit gồm Lễ tân).
    canEdit
      ? supabase.from("service_type").select("id, name").order("name")
      : Promise.resolve({ data: [] as { id: string; name: string }[] }),
    canEdit ? listBookableDoctors() : Promise.resolve([]),
  ]);

  let { data, error } = patRes;
  // Thiếu cột full_name_unaccent (chưa migrate) → tìm lại không bỏ dấu.
  if (error && /full_name_unaccent|column/i.test(error.message ?? "")) {
    ({ data, error } = await buildPatientQuery(false));
  }

  const rows = (data as CustomerRow[] | null) ?? [];
  const locations: Opt[] = (locRes.data ?? []).map((r) => ({
    id: r.id as string,
    label: r.name as string,
  }));
  // Dropdown cho modal ĐỔI lịch — bỏ dịch vụ rác "FREE" (khớp trang đặt lịch).
  const services: Opt[] = ((svcRes.data ?? []) as { id: string; name: string }[])
    .filter((r) => (r.name ?? "").trim().toUpperCase() !== "FREE")
    .map((r) => ({ id: r.id, label: r.name }));
  const doctors: Opt[] = docRes;

  const shownIds = rows.map((r) => r.clinic_patient_id);
  // canManage: nạp thêm field để ĐIỀN SẴN modal đổi lịch (dịch vụ/bác sĩ/
  // cơ sở/kênh). Vai khác chỉ cần tóm tắt (nhẹ hơn).
  //
  // NHƯNG `id` THÌ MỌI VAI ĐỀU CẦN, và trước 10/08/2026 nó chỉ có ở nhánh
  // canManage. Bốn vai vào được màn này mà không có quyền đổi lịch — Lễ tân và
  // ba vai Thu ngân (`roles.ts`: "/customers" mở cho 7 vai, `canManageAppt`
  // chỉ 3) — do đó KHÔNG có id lịch nào, nên với họ:
  //   · sổ chăm sóc không gắn được vào lượt nào,
  //   · nút "Tái khám" mờ vĩnh viễn kể cả khi khách vừa khám xong,
  //   · và mọi thao tác thuộc `CAN_LICH_HEN` trả lỗi "phải gắn với một lịch hẹn".
  //
  // `id` không phải dữ liệu nhạy cảm và không phải quyền: RLS mới là chốt, chứ
  // không phải danh sách cột. Giấu nó chỉ làm màn hình nói dối về khách.
  // LÝ DO HUỶ PHẢI ĐI CÙNG GIỜ HUỶ. Trước 10/08/2026 câu này lấy `cancelled_at`
  // mà bỏ `ly_do_huy_ma` + `cancellation_reason` — hai cột `booking_service`
  // vẫn ghi đầy đủ mỗi lần huỷ. Nên màn nói được "huỷ lúc 14:20" và không nói
  // được vì sao, trong khi màn /tasks cùng dữ liệu ấy thì hiện ra bình thường.
  // Lưu mà không hiện thì người trực gọi lại hỏi đúng câu khách vừa trả lời.
  //
  // Sửa CẢ HAI nhánh: nhánh không-canManage là màn của Thu ngân / Điều dưỡng,
  // và một màn nói ít hơn cũng là một màn nói sai.
  const apptSelectAll = canManage
    ? `clinic_patient_id, id, slot_start, status, created_at, cancelled_at,
       ly_do_huy_ma, cancellation_reason,
       service_type_id, doctor_id, bac_si_da_go_id, location_id, booking_channel, lich_truoc_id,
       service:service_type!service_type_id ( name ),
       doctor:staff!doctor_id ( full_name )`
    : `clinic_patient_id, id, slot_start, status, created_at, cancelled_at,
       ly_do_huy_ma, cancellation_reason, service_type_id, bac_si_da_go_id, lich_truoc_id,
       service:service_type!service_type_id ( name ),
       doctor:staff!doctor_id ( full_name )`;
  const apptsPromise = shownIds.length
    ? supabase
        .from("appointment")
        .select(apptSelectAll)
        .in("clinic_patient_id", shownIds)
        .order("slot_start", { ascending: true })
        .limit(3000)
    : Promise.resolve({ data: [] as unknown[], error: null });
  // CA TRỰC CỦA BÁC SĨ — để biết lịch nào vừa MẤT bác sĩ.
  //
  // TÌNH HUỐNG SỐ 9 trong bảng "tình huống phát sinh" của khách: *"Lịch bác sĩ
  // thay đổi sau khi khách đã đặt → hệ thống giúp nhận biết các lịch khách bị
  // ảnh hưởng để CSKH chủ động xử lý"*. Trước hôm nay không có gì làm việc ấy:
  // quản lý gỡ một ca trực, và lịch của khách vẫn nằm im dưới tên một bác sĩ
  // hôm đó không đi làm. Đường duy nhất để biết là khách tới quầy rồi mới vỡ lẽ.
  //
  // MỘT TRUY VẤN CHO CẢ MÀN, không hỏi từng lịch một: lấy toàn bộ ca trực trong
  // khoảng ngày mà các lịch đang hiện chạm tới, rồi tra trong bộ nhớ. Hỏi theo
  // từng lịch là 30–40 vòng mạng để vẽ một cột.
  // CHỈ ĐẾM CA KHÁM (`LICH_KHAM`), không đếm mọi trạm.
  //
  // Bản đầu hỏi "bác sĩ này có dòng ca trực nào ngày ấy không". Nhưng một bác
  // sĩ còn có thể được xếp vào `THU_THUAT_NGOAI_GIO`, `PHU_BS_KHAM`, `TLYK`…
  // — mười mã trạm đang dùng trên prod. Quản lý gỡ đúng ca KHÁM mà người ấy
  // còn một ca trạm khác thì phép kiểm vẫn đọc ra "có đi làm", và cảnh báo
  // không bao giờ nổ. Đó chính là ca Tuyền báo còn nợ 14/08/2026.
  //
  // Câu hỏi thật không phải "hôm ấy có mặt ở phòng khám không" mà "hôm ấy có
  // ngồi bàn khám không" — lịch hẹn của khách đặt vào bàn khám.
  const caTrucPromise = shownIds.length
    ? supabase
        .from("work_roster")
        .select("staff_id, work_date")
        .eq("station", "LICH_KHAM")
        .not("staff_id", "is", null)
        .gte("work_date", new Date(nowMs() - 86_400_000).toISOString().slice(0, 10))
        .limit(5000)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // TRẠNG THÁI — suy lại từ dữ liệu mỗi lần đọc (view 20260809000005).
  //
  // Trước đây cột này đọc `cskh_action.status`, rơi về `appointment.status`,
  // rồi rơi tiếp về chuỗi cứng "Khách mới" — nên gần như mọi khách hiện "Đã
  // đặt lịch", một câu đúng mà vô dụng: nó không nói CSKH phải làm gì tiếp.
  const trangThaiPromise = shownIds.length
    ? supabase
        .from("v_trang_thai_cskh")
        .select(
          "clinic_patient_id, trang_thai, nhan, han_xu_ly, qua_han, so_viec_mo, co_viec_qua_han, appointment_id, da_xac_nhan",
        )
        .in("clinic_patient_id", shownIds)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // MỌI VIỆC ĐANG MỞ, KHÔNG CHỈ VIỆC THẮNG (view 20260810000008).
  //
  // `v_trang_thai_cskh` là `DISTINCT ON (clinic_patient_id)` — một dòng cho một
  // KHÁCH. Danh sách bên trái cần đúng như vậy: một người, một chip. Nhưng cột
  // giữa và cột phải làm việc trên MỘT LƯỢT, và một khách có nhiều lượt.
  //
  // Ca Cường 10/08/2026: lượt hôm qua đang CHECKED_IN nên việc thắng là
  // `DA_CHECKIN` (ưu tiên 0); người trực mở lượt tái khám ngày mai thì cột giữa
  // vẫn sáng "Đã check-in — đang ở đây" và cột phải mời "Check-in cho khách" —
  // cả hai đang nói về một lượt khác. Việc đúng của lượt ấy (`CHO_XAC_NHAN`)
  // bị `DISTINCT ON` ném đi trước khi tới được màn hình.
  const viecMoPromise = shownIds.length
    ? supabase
        .from("v_viec_cskh")
        .select(
          "clinic_patient_id, trang_thai, nhan, uu_tien, han_xu_ly, qua_han, appointment_id",
        )
        .in("clinic_patient_id", shownIds)
        .limit(3000)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // NHẮC TÁI KHÁM — gộp về đây, không còn là một màn rời.
  //
  // HAI VIỆC TRONG MỘT LỜI GỌI, và cái thứ hai mới là cái quan trọng:
  //
  //  1. Đọc các mốc gọi đang mở, để vùng làm việc của từng khách hiện đúng
  //     "còn N ngày nữa phải gọi mời đặt lịch".
  //  2. SINH việc của hôm nay. Endpoint này chạy `sinh_viec_nhac_tai_kham()`
  //     trước khi trả về, và dự án CHƯA CÓ BỘ HẸN GIỜ NÀO — nên việc chỉ ra
  //     đời khi có người mở một màn gọi đường này. Trước đây đường ấy là
  //     /nhac-tai-kham; ngày 09/08/2026 màn đó bị gỡ khỏi thanh bên của CSKH,
  //     và cùng lúc bộ sinh việc mất luôn người kích hoạt. Không ai báo lỗi —
  //     hàng đợi chỉ đơn giản là không bao giờ có gì trong đó.
  //
  // Trả về null khi vai không được đọc (Lễ tân, Thu ngân) hoặc backend im —
  // khối nhắc tái khám ẩn đi, phần còn lại của màn vẫn chạy.
  const recallPromise = fetchFromBackend<{
    luot1: RecallRaw[];
    luot2: RecallRaw[];
  }>("/api/v1/cskh/recall-jobs");

  // KHÔNG CÒN HỎI TRẠNG THÁI ZALO. Hai nút gửi ZNS nằm trong khối "Ghi một
  // tương tác khác" đã bỏ ngày 09/08. Giữ lời gọi này là mỗi lần mở màn lại tốn
  // một lượt sang backend cho một thứ không còn hiện ra ở đâu.

  // TỆP KẾT QUẢ — ảnh/video siêu âm, phiếu xét nghiệm CSKH đã tải lên.
  const tepPromise = shownIds.length
    ? supabase
        .from("tep_ket_qua")
        .select(
          "id, clinic_patient_id, appointment_id, ten_hien_thi, loai_tep, mime, so_byte, tai_len_luc, gui_luc, gui_kenh, staff:tai_len_boi_staff_id ( full_name )",
        )
        .in("clinic_patient_id", shownIds)
        .order("tai_len_luc", { ascending: false })
        .limit(300)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // PHẢN HỒI / KHIẾU NẠI — vòng đời xử lý hiện ngay trong vùng làm việc.
  const phanHoiPromise = shownIds.length
    ? supabase
        .from("phan_hoi_khach")
        .select(
          "id, clinic_patient_id, loai, noi_dung, trang_thai, huong_xu_ly, created_at, staff:nguoi_tiep_nhan_staff_id ( full_name )",
        )
        .in("clinic_patient_id", shownIds)
        .order("created_at", { ascending: false })
        .limit(300)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // VIỆC CSKH TỰ HẸN CHO MÌNH — "gọi lại ngày…".
  //
  // Bảng này sinh ra trạng thái `HEN_GOI_LAI` của view và sinh cả một thông báo
  // trong chuông, NHƯNG cho tới 10/08/2026 màn hình chưa từng ĐỌC nó: ngày hẹn,
  // giờ hẹn và lý do người trực gõ vào đều nằm trong database mà không hiện ở
  // đâu. Bấm "Bấm để xử lý" trong chuông thì mở đúng hồ sơ rồi hết — không có
  // node nào nói "hẹn gọi lại 23:30 ngày 10/08 vì việc gì", và cũng không có
  // nút nào đóng được việc, nên `dong_luc` vĩnh viễn NULL và khách kẹt ở trạng
  // thái ấy mãi mãi.
  const henGoiLaiPromise = shownIds.length
    ? supabase
        .from("hen_goi_lai")
        .select(
          "id, clinic_patient_id, ngay_goi, gio_goi, ly_do, created_at, staff:tao_boi_staff_id ( full_name )",
        )
        .in("clinic_patient_id", shownIds)
        .is("dong_luc", null)
        .order("ngay_goi", { ascending: true })
        .limit(300)
    : Promise.resolve({ data: [] as unknown[], error: null });

  // SỔ TƯƠNG TÁC — nguồn thật của cột "Tương tác gần nhất".
  //
  // `cskh_action` bên dưới là hàng nhập khẩu từ Notion và có 0 dòng trên bản
  // thật; hai câu INSERT duy nhất ghi vào nó còn không có cột `step` lẫn
  // `deadline_at`. Bảng mới ghi từ chính màn này (20260809000003).
  const tuongTacPromise = shownIds.length
    ? supabase
        .from("tuong_tac_cskh")
        .select(
          // `appointment_id` để gom được từng lượt khám thành một chuỗi —
          // cột đã có từ 20260809000003 nhưng chưa từng được mang xuống UI.
          // GỌI TÊN CỘT KHOÁ NGOẠI, đừng để PostgREST tự đoán.
          //
          // `staff(full_name)` chạy được suốt vì `tuong_tac_cskh` chỉ có MỘT
          // khoá ngoại sang `staff`. Migration 20260810000009 thêm cái thứ hai
          // (`huy_boi_staff_id`, cho hoàn tác) và PostgREST lập tức từ chối cả
          // câu: *"Could not embed because more than one relationship was found
          // for 'tuong_tac_cskh' and 'staff'"* — không phải một cột null, mà là
          // 400 cho toàn bộ truy vấn, tức TRẮNG CẢ MÀN Quản lý khách hàng.
          //
          // Thêm một khoá ngoại thứ hai sang cùng một bảng là đủ để làm hỏng
          // một câu select viết đúng từ trước. Ba chỗ khác trong màn này đã gọi
          // tên cột sẵn (`staff:tao_boi_staff_id`, `staff:nguoi_tiep_nhan_staff_id`,
          // `staff:tai_len_boi_staff_id`) — chỗ này là chỗ duy nhất còn đoán.
          "id, clinic_patient_id, appointment_id, xay_ra_luc, loai, kenh, ket_qua, khach_xac_nhan, noi_dung, trang_thai_ma, huy_luc, staff:nhan_vien_staff_id ( full_name )",
        )
        .in("clinic_patient_id", shownIds)
        .order("xay_ra_luc", { ascending: false })
        .limit(1000)
    : Promise.resolve({ data: [] as unknown[], error: null });
  const cskhPromise = shownIds.length
    ? supabase
        .from("cskh_action")
        .select(
          "id, clinic_patient_id, category, step, status, description, deadline_at, source_created_at, created_by_text, last_edited_by_text",
        )
        .in("clinic_patient_id", shownIds)
        .order("source_created_at", { ascending: false })
        .limit(1000)
    : Promise.resolve({ data: [] as unknown[], error: null });

/** Ngày theo giờ PHÒNG KHÁM, dạng yyyy-mm-dd.
 *
 *  Cắt chuỗi ISO thì sai: PostgREST trả `"2026-08-10T23:30:00+07:00"` và cắt 10
 *  ký tự đầu ra đúng ngày, nhưng `toISOString()` lại đổi sang UTC thành ngày
 *  hôm trước. Đi qua `Intl` với múi giờ phòng khám là cách duy nhất đúng cho cả
 *  hai dạng chuỗi. */
function ngayVn(iso: string): string {
  return new Date(iso).toLocaleDateString("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

/** Một dòng lịch hẹn như PostgREST trả về (theo `apptSelectAll`). */
/** Một dòng ca trực: bác sĩ này có đi làm ngày này không. */
type CaTrucRaw = {
  staff_id: string | null;
  work_date: string | null;
};

type LichHenRaw = {
  clinic_patient_id: string;
  slot_start: string;
  status: string;
  id?: string;
  service_type_id?: string | null;
  doctor_id?: string | null;
  /** Bác sĩ đã bị gỡ khỏi lịch khi ca trực của họ bị xoá (14/08/2026). */
  bac_si_da_go_id?: string | null;
  location_id?: string | null;
  booking_channel?: string | null;
  created_at?: string | null;
  cancelled_at?: string | null;
  ly_do_huy_ma?: string | null;
  cancellation_reason?: string | null;
  lich_truoc_id?: string | null;
  service?: { name: string } | { name: string }[] | null;
  doctor?: { full_name: string } | { full_name: string }[] | null;
};

  // Lịch hẹn của các khách đang hiển thị → "lịch đại diện": SẮP TỚI gần nhất,
  // nếu không có thì lịch GẦN NHẤT trong quá khứ. Kèm tổng số lịch.
  const apptByPatient: Record<string, ApptInfo> = {};
  /** Toàn bộ lịch hẹn theo khách. Khai NGOÀI khối dưới vì khối "lịch sử các
   *  lần khám" ở cuối file cũng đọc nó — gom lại một lần rồi dùng hai chỗ, thay
   *  vì bắn thêm một truy vấn cho cùng dữ liệu. */
  const grouped: Record<string, LichHenRaw[]> = {};
  // TẬP CA TRỰC DÙNG CHO CẢ HAI CHỖ: cờ "mất bác sĩ" của lịch đại diện (ngay
  // dưới) và của TỪNG LƯỢT trong lịch sử khám (cuối tệp). Khai ở ngoài khối để
  // không phải hỏi database lần thứ hai cho cùng một câu hỏi.
  const coCaTruc = new Set<string>();
  let doCaTruc = false;
  if (rows.length) {
    // Bắn CÙNG LÚC với truy vấn cskh_action bên dưới: cả hai chỉ cần `ids`, và
    // xếp hàng chúng là cộng thêm một lượt ~180ms sang Seoul mà không đổi kết
    // quả. `await` ở đây chỉ chờ đúng cái đã bay từ trước.
    // HỨNG LỖI, ĐỪNG NUỐT. PostgREST select một cột không tồn tại hoặc chưa
    // được GRANT thì trả 400 cho CẢ CÂU: `appts` về null, `grouped` rỗng, và
    // mọi khách mất sạch lịch hẹn — mất luôn "Lịch hẹn sắp tới", nhãn trạng
    // thái theo lịch, và ô Lịch sử các lần khám. Không một dòng đỏ nào.
    //
    // Đúng cái bẫy vừa gặp khi thêm `ly_do_huy_ma`: một tên cột gõ sai không
    // làm hỏng một ô, nó làm trắng cả màn. TypeScript không canh được — client
    // Supabase ở đây không gắn generic nên chuỗi select là chữ tự do.
    const { data: appts, error: apptErr } = await apptsPromise;
    if (apptErr) {
      console.error("customers: không nạp được lịch hẹn", apptErr);
    }
    // Ca trực: "bác sĩ X có đi làm ngày Y không". Hỏng thì tập rỗng — và tập
    // rỗng KHÔNG được hiểu là "mọi bác sĩ đều nghỉ", xem `matBacSi` bên dưới.
    const { data: caTruc, error: caTrucErr } = await caTrucPromise;
    if (caTrucErr) {
      console.error("customers: không nạp được ca trực", caTrucErr);
    }
    for (const r of (caTruc as unknown as CaTrucRaw[] | null) ?? []) {
      if (r.staff_id && r.work_date) coCaTruc.add(`${r.staff_id}|${r.work_date}`);
    }
    doCaTruc = coCaTruc.size > 0;
    // SO GIỜ BẰNG MỐC THỜI GIAN, KHÔNG BẰNG CHUỖI.
    //
    // Chỗ này từng là `a.slot_start >= new Date().toISOString()`. Database chạy
    // ở múi Asia/Ho_Chi_Minh nên PostgREST trả `"2026-08-09T08:15:00+07:00"`,
    // còn `toISOString()` cho `"2026-08-09T05:48:00.000Z"`. So hai chuỗi ấy là
    // so ký tự: "08" > "05" ⇒ một lịch ĐÃ QUA bốn tiếng vẫn được coi là SẮP TỚI.
    //
    // Thấy được trên prod 09/08: Nguyễn Bình có lịch 08:15 (đã khám xong) và
    // 21:00 (sắp tới); lúc 12:37 panel vẫn hiện "Lịch hẹn sắp tới 08:15" — bắt
    // đúng lịch cũ, và giấu mất lịch thật sự sắp tới.
    const bayGio = nowMs();
    for (const a of (appts as unknown as LichHenRaw[] | null) ?? []) {
      (grouped[a.clinic_patient_id] ??= []).push(a);
    }
    const DEAD = ["CANCELLED", "NO_SHOW", "DOCTOR_DECLINED"];
    // LƯỢT CHƯA ĐÓNG — tập trạng thái mà lượt khám vẫn còn đang diễn ra.
    //
    // Dùng cho HAI câu hỏi khác nhau nhưng cùng một tập hợp, nên khai một lần:
    //   · "lịch nào là lịch sắp tới"  — một lượt ĐÃ checkout không còn sắp tới
    //   · "lịch nào còn đổi/huỷ được" — cũng đúng các trạng thái ấy
    //
    // LỖI NÓ CHỮA (Quang 10/08/2026). `DEAD` không chứa `COMPLETED` — cố ý, vì
    // `count` và bộ lọc "theo ngày hẹn" vẫn phải đếm lượt đã khám xong. Nhưng
    // `upcoming` cũng đọc `live`, nên một lượt checkout lúc 12:25 mà giờ hẹn là
    // 18:15 vẫn thắng vai "lịch sắp tới" — và thắng luôn cả lượt tái khám vừa
    // đặt. Từ đó cột giữa đứng yên ở lượt cũ: đặt tái khám xong màn không đổi,
    // đọc thành "nút không ấn được".
    const CHUA_DONG = ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"];
    for (const [pid, list] of Object.entries(grouped)) {
      // Lịch "sống" (bỏ đã hủy/không đến/BS từ chối) để chọn LỊCH ĐẠI DIỆN + đếm:
      // hủy lịch xong thì KHÔNG còn hiện là "Lịch hẹn sắp tới".
      // Sắp xếp TẠI ĐÂY thay vì tin vào thứ tự truy vấn: "lịch sống gần nhất"
      // và "lịch sắp tới đầu tiên" đều đọc theo thứ tự này.
      const live = list
        .filter((a) => !DEAD.includes(a.status))
        .sort((x, y) => mocMs(x.slot_start) - mocMs(y.slot_start));
      const upcoming = live.find(
        (a) => conToi(a.slot_start, bayGio) && CHUA_DONG.includes(a.status),
      );
      // Lịch đại diện: sắp tới → lịch sống gần nhất → CUỐI CÙNG mới tới lịch đã
      // huỷ. Nhánh thứ ba là mới: trước đây khách chỉ còn lịch huỷ thì bị bỏ
      // qua hẳn (`continue`), nên vùng làm việc của họ trống trơn — đúng lúc
      // CSKH cần gọi hỏi vì sao huỷ.
      const repr = upcoming ?? live[live.length - 1] ?? list[list.length - 1];
      if (!repr) continue;
      // Chỉ cho ĐỔI/HỦY lịch còn "sống" & SẮP TỚI (repr là lịch upcoming) —
      // CỘNG THÊM lịch khách đang check-in, dù giờ hẹn đã trôi qua.
      //
      // LỖI CŨ, VÀ NÓ IM LẶNG. `upcoming` dựng từ `conToi()`, mà `conToi` là
      // `slot_start >= now` tính theo MILI-GIÂY, không phải "trong ngày". Khách
      // hẹn 9h00, check-in 8h55: nút chạy. 9h01: `upcoming` thành undefined →
      // `appt` không dựng → `appointmentId` xuống HanhDongTrangThai là null →
      // backend chặn ("Việc này phải gắn với một lịch hẹn cụ thể", CAN_LICH_HEN
      // ở tuong_tac_cskh_service) → hai nút của bước "Đã check-in" trả lỗi đỏ.
      //
      // Tức là chúng chết đúng vào lúc chúng sinh ra để phục vụ: khách đang
      // ngồi trong phòng khám. Mà cột trạng thái vẫn sáng bình thường, vì nhánh
      // DA_CHECKIN của view chạy theo `status = 'CHECKED_IN'` và không quan tâm
      // giờ — nên nhìn màn hình không thấy gì sai, chỉ thấy bấm là lỗi.
      //
      // Check-in rồi thì giờ hẹn hết ý nghĩa: người ta đã tới. Lấy chính `repr`
      // làm mốc thay vì đòi có một lịch còn ở tương lai.
      let appt: EditableAppt | undefined;
      const dangCoMatTaiPhongKham = repr.status === "CHECKED_IN";
      if (
        canManage &&
        (upcoming || dangCoMatTaiPhongKham) &&
        repr.id &&
        CHUA_DONG.includes(repr.status)
      ) {
        appt = {
          id: repr.id,
          slot_start: repr.slot_start,
          service_type_id: repr.service_type_id ?? null,
          service_name: pick1(repr.service)?.name ?? null,
          doctor_id: repr.doctor_id ?? null,
          doctor_name: pick1(repr.doctor)?.full_name ?? null,
          location_id: repr.location_id ?? null,
          booking_channel: repr.booking_channel ?? null,
        };
      }
      apptByPatient[pid] = {
        // ĐỊNH DANH LƯỢT, TÁCH KHỎI QUYỀN SỬA LƯỢT.
        //
        // Trước 10/08/2026 id của lịch đại diện chỉ tồn tại BÊN TRONG `appt`,
        // mà `appt` là đối tượng "được đổi/huỷ không". Lượt đã COMPLETED thì
        // `appt` không được dựng ⇒ `lich.id` xuống client là null, trong khi
        // `lich.status` vẫn lấy từ `repr`. Prop `lich` thành một vật lai: trạng
        // thái của lượt này, id của không lượt nào.
        //
        // Hệ quả nặng nhất nằm ở `VungLamViecKhach`: `lich.id` null làm bộ lọc
        // sổ chăm sóc theo lượt tự huỷ và quay về sổ của CẢ KHÁCH — nên một
        // lượt vừa sinh ra đã tích xanh đủ tám bước bằng dữ liệu của lượt
        // trước. "Lượt nào" và "sửa được không" là hai câu hỏi khác nhau.
        id: repr.id ?? null,
        slot_start: repr.slot_start,
        status: repr.status,
        upcoming: Boolean(upcoming),
        // QUÁ GIỜ HẸN MÀ KHÁCH CHƯA ĐẾN. Quang 09/08/2026: *"thời gian trôi rồi
        // mà sao vẫn còn nhắc khám, phải cảnh báo đỏ"*.
        //
        // Chỉ tính khi lịch đại diện đã qua giờ VÀ vẫn đang ở trạng thái "chưa
        // tới nơi". Đã check-in / đã khám xong thì giờ trôi qua là bình thường,
        // tô đỏ ở đó là dạy người dùng bỏ qua màu đỏ.
        qua_gio_hen:
          daQua(repr.slot_start, bayGio) &&
          ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(repr.status),
        // LỊCH NÀY VỪA MẤT BÁC SĨ: có người phụ trách, nhưng người ấy không còn
        // ca trực vào đúng ngày khám.
        //
        // CHỈ TÍNH CHO LỊCH CÒN CỨU ĐƯỢC — chưa tới giờ và chưa check-in. Một
        // lịch đã qua mà mất bác sĩ thì không đổi lại được nữa; tô đỏ ở đó chỉ
        // làm ngập màn hình và dạy người trực bỏ qua màu đỏ.
        //
        // `doCaTruc` là chốt an toàn: truy vấn ca trực hỏng hoặc tuần chưa xếp
        // thì tập rỗng, và tập rỗng KHÔNG được đọc thành "mọi bác sĩ đều nghỉ".
        // Báo nhầm hàng loạt còn tệ hơn không báo: người trực sẽ gọi cho hàng
        // chục khách để nói một chuyện không xảy ra.
        mat_bac_si:
          doCaTruc &&
          !!repr.doctor_id &&
          !daQua(repr.slot_start, bayGio) &&
          ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(repr.status) &&
          !coCaTruc.has(`${repr.doctor_id}|${ngayVN(repr.slot_start)}`),
        count: live.length,
        // LƯỢT KHÁM GẦN NHẤT ĐÃ XONG — nguồn cho nút "Tái khám".
        //
        // Dữ liệu này KHÔNG phải thêm truy vấn: `list` đã chứa toàn bộ lịch của
        // khách kể cả COMPLETED (dòng `examined` bên dưới đọc chính nó), và
        // `apptSelectAll` đã lấy sẵn service_type_id + tên dịch vụ. Nó chỉ chưa
        // từng được mang xuống client.
        //
        // Lấy cái MỚI NHẤT chứ không phải cái đầu: tái khám là nối tiếp lượt
        // vừa rồi, không phải lượt năm ngoái.
        lanKhamGanNhat: (() => {
          const xong = list
            .filter((a) => a.status === "COMPLETED" && a.id)
            .sort((x, y) => mocMs(y.slot_start) - mocMs(x.slot_start))[0];
          if (!xong) return null;
          return {
            id: xong.id as string,
            slot_start: xong.slot_start,
            service_type_id: xong.service_type_id ?? null,
            service_name: pick1(xong.service)?.name ?? null,
          };
        })(),
        // LẦN KHÁM THỨ MẤY. Đếm lượt ĐÃ KHÁM XONG, không đếm lịch đã đặt: khách
        // đặt năm lịch rồi huỷ bốn thì họ vẫn mới khám một lần.
        soLanKham: list.filter((a) => a.status === "COMPLETED").length,
        // Lịch đại diện có nối vào một lượt trước không.
        laTaiKham: Boolean(repr.lich_truoc_id),
        // Lọc lại `conToi` chứ không dùng cả `live`: lịch hôm qua chưa đóng
        // trạng thái vẫn nằm trong `live`, mà bỏ một lịch đã trôi qua thì không
        // giải quyết được chuyện đặt trùng.
        //
        // Cột `id` chỉ có khi `canManage` (xem lựa chọn cột ở trên) — không có
        // id thì không huỷ được, nên bỏ luôn khỏi danh sách thay vì vẽ ra một
        // dòng bấm vào không làm gì.
        //
        // TRÙNG = CÙNG DỊCH VỤ, CÙNG NGÀY. Không phải "có từ hai lịch trở lên".
        //
        // Quang 10/08/2026: khám xong cho Huyền rồi đặt lịch khám mới thì màn
        // báo "2 lịch trùng" — *"trước thì đúng nhưng giờ bỏ hoặc vô hiệu hoá
        // đi, để nó sẽ là đợt khám mới"*. Đúng: một lịch Nội tiết đã khám xong
        // và một lịch Phụ khoa sắp tới là HAI ĐỢT KHÁC NHAU, không phải đặt
        // nhầm hai lần.
        //
        // Cảnh báo sai còn tệ hơn không cảnh báo: nó xuất hiện ở mọi khách có
        // hai dịch vụ, nên người trực học cách bỏ qua — rồi bỏ qua luôn lần
        // trùng thật. Ca sinh ra cảnh báo này (Lan đặt ba lần liên tiếp cùng
        // Phụ khoa trong một buổi) vẫn bị bắt, vì nó cùng dịch vụ cùng ngày.
        //
        // Lịch nối chuỗi tái khám cũng không tính: `lich_truoc_id` nói rõ nó là
        // lượt tiếp theo có chủ ý, không phải bản sao.
        sapToi: (() => {
          const sapToi = live.filter(
            (a) => conToi(a.slot_start, bayGio) && a.id,
          );
          const dem = new Map<string, number>();
          for (const a of sapToi) {
            if (a.lich_truoc_id) continue;
            const khoa = `${a.service_type_id ?? "?"}|${ngayVn(a.slot_start)}`;
            dem.set(khoa, (dem.get(khoa) ?? 0) + 1);
          }
          return sapToi
            .filter((a) => {
              if (a.lich_truoc_id) return false;
              const khoa = `${a.service_type_id ?? "?"}|${ngayVn(a.slot_start)}`;
              return (dem.get(khoa) ?? 0) > 1;
            })
            .map((a) => ({
              id: a.id as string,
              slot_start: a.slot_start,
              status: a.status,
              service_name: pick1(a.service)?.name ?? null,
              doctor_name: pick1(a.doctor)?.full_name ?? null,
            }));
        })(),
        // "Đã khám" = có ≥1 lịch COMPLETED (cùng định nghĩa "bệnh nhân" ở
        // /patient-list). Đang khám (CHECKED_IN/IN_PROGRESS) hay mới đặt/check-in
        // thì CHƯA tính — nút "Hồ sơ & lịch sử khám" sẽ ẩn.
        examined: list.some((a) => a.status === "COMPLETED"),
        created_at: repr.created_at ?? null,
        cancelled_at: repr.cancelled_at ?? null,
        ly_do_huy_ma: repr.ly_do_huy_ma ?? null,
        cancellation_reason: repr.cancellation_reason ?? null,
        appt,
      };
    }
  }

  // Lịch hẹn + CSKH actions (trạng thái, tương tác, hạn xử lý, phụ trách)
  type CskhRaw = {
    id: string;
    clinic_patient_id: string;
    category: string | null;
    step: string | null;
    status: string | null;
    description: string | null;
    deadline_at: string | null;
    source_created_at: string | null;
    created_by_text: string | null;
    last_edited_by_text: string | null;
  };
  const cskhByPatient: Record<
    string,
    {
      status: string;
      lastInteraction: string | null;
      nextStep: string | null;
      deadline: string | null;
      assignee: string | null;
    }
  > = {};
  let cskhError: { message: string } | null = null;

  if (rows.length) {
    // ĐỌC CẢ `error`. Bản trước chỉ lấy `data`, nên khi RLS chặn (nhân viên
    // chưa nối clinic_membership) truy vấn trả 0 dòng và bốn cột giữa hiện "—"
    // y hệt lúc chưa có dữ liệu. Không phân biệt được "chưa có việc nào" với
    // "anh không có quyền đọc" là kiểu hỏng tệ nhất: không ai đi tìm.
    const { data: cskhActions, error } = await cskhPromise;
    cskhError = error;

    // Group by patient, pick latest action
    const grouped: Record<string, CskhRaw[]> = {};
    for (const a of (cskhActions as CskhRaw[] | null) ?? []) {
      if (a.clinic_patient_id) {
        (grouped[a.clinic_patient_id] ??= []).push(a);
      }
    }
    for (const [pid, actionList] of Object.entries(grouped)) {
      const latest = actionList[0]; // already sorted DESC
      if (!latest) continue;
      cskhByPatient[pid] = {
        status: latest.status ?? "OPEN",
        lastInteraction: latest.description ?? null,
        nextStep: latest.step ?? null,
        deadline: latest.deadline_at ?? null,
        assignee:
          latest.last_edited_by_text ?? latest.created_by_text ?? null,
      };
    }
  }

  // Gom sổ tương tác theo khách. Dòng đầu mỗi nhóm là lần gần nhất (đã sắp xếp
  // giảm dần ở truy vấn).
  type TuongTacRaw = {
    id: string;
    huy_luc: string | null;
    clinic_patient_id: string;
    xay_ra_luc: string;
    loai: string;
    kenh: string;
    ket_qua: string | null;
    khach_xac_nhan: boolean | null;
    noi_dung: string | null;
    trang_thai_ma: string | null;
    appointment_id: string | null;
    staff?: { full_name: string } | { full_name: string }[] | null;
  };
  type ViecCskh = {
    clinic_patient_id: string;
    trang_thai: string;
    nhan: string;
    uu_tien: number;
    han_xu_ly: string | null;
    qua_han: boolean;
    appointment_id: string | null;
  };
  type TrangThaiRaw = {
    clinic_patient_id: string;
    trang_thai: string;
    nhan: string;
    han_xu_ly: string | null;
    qua_han: boolean;
    so_viec_mo: number;
    co_viec_qua_han: boolean;
    appointment_id: string | null;
    da_xac_nhan: boolean;
  };
  const trangThaiByPatient: Record<string, TrangThaiRaw> = {};
  const viecMoByPatient: Record<string, ViecCskh[]> = {};
  let trangThaiError: { message: string } | null = null;
  type PhanHoiRaw = {
    id: string;
    clinic_patient_id: string;
    loai: string;
    noi_dung: string;
    trang_thai: string;
    huong_xu_ly: string | null;
    created_at: string;
    staff?: { full_name: string } | { full_name: string }[] | null;
  };
  type TepRaw = {
    id: string;
    clinic_patient_id: string;
    appointment_id: string | null;
    ten_hien_thi: string | null;
    loai_tep: string;
    mime: string;
    so_byte: number;
    tai_len_luc: string;
    gui_luc: string | null;
    gui_kenh: string | null;
    staff?: { full_name: string } | { full_name: string }[] | null;
  };
  type HenGoiLaiRaw = {
    id: string;
    clinic_patient_id: string;
    ngay_goi: string;
    gio_goi: string | null;
    ly_do: string;
    created_at: string | null;
    staff?: { full_name: string } | { full_name: string }[] | null;
  };
  const tepByPatient: Record<string, TepKetQuaRow[]> = {};
  const henGoiLaiByPatient: Record<string, HenGoiLai[]> = {};
  const phanHoiByPatient: Record<string, DongPhanHoi[]> = {};
  const tuongTacByPatient: Record<string, DongLichSu[]> = {};
  let tuongTacError: { message: string } | null = null;
  if (rows.length) {
    const { data: tep } = await tepPromise;
    for (const r of (tep as TepRaw[] | null) ?? []) {
      const nv = Array.isArray(r.staff) ? r.staff[0] : r.staff;
      (tepByPatient[r.clinic_patient_id] ??= []).push({
        id: r.id,
        appointment_id: r.appointment_id,
        ten_hien_thi: r.ten_hien_thi,
        loai_tep: r.loai_tep,
        mime: r.mime,
        so_byte: r.so_byte,
        tai_len_luc: r.tai_len_luc,
        tai_len_boi: nv?.full_name ?? null,
        gui_luc: r.gui_luc,
        gui_kenh: r.gui_kenh,
        gui_boi: null,
      });
    }
    const { data: hgl } = await henGoiLaiPromise;
    for (const r of (hgl as HenGoiLaiRaw[] | null) ?? []) {
      const nv = Array.isArray(r.staff) ? r.staff[0] : r.staff;
      (henGoiLaiByPatient[r.clinic_patient_id] ??= []).push({
        id: r.id,
        ngay_goi: r.ngay_goi,
        gio_goi: r.gio_goi ?? null,
        ly_do: r.ly_do,
        tao_boi: nv?.full_name ?? null,
        created_at: r.created_at ?? null,
      });
    }
    const { data: ph } = await phanHoiPromise;
    for (const r of (ph as PhanHoiRaw[] | null) ?? []) {
      const nv = Array.isArray(r.staff) ? r.staff[0] : r.staff;
      (phanHoiByPatient[r.clinic_patient_id] ??= []).push({
        id: r.id,
        loai: r.loai,
        noi_dung: r.noi_dung,
        trang_thai: r.trang_thai,
        huong_xu_ly: r.huong_xu_ly,
        created_at: r.created_at,
        nguoi_tiep_nhan: nv?.full_name ?? null,
      });
    }
    const { data: tt2, error: ttErr2 } = await trangThaiPromise;
    trangThaiError = ttErr2;
    for (const t of (tt2 as TrangThaiRaw[] | null) ?? []) {
      trangThaiByPatient[t.clinic_patient_id] = t;
    }
    const { data: vm, error: vmErr } = await viecMoPromise;
    // Nuốt lỗi CÓ CHỦ Ý, và chỉ ở đây: `v_viec_cskh` là view mới
    // (20260810000008). Máy chủ nào chưa áp migration ấy sẽ trả 404, và khi ấy
    // màn phải lùi về hành vi cũ — một trạng thái cho cả khách — chứ không
    // được sập. Ghi log để không ai tưởng là "hôm nay không có việc nào".
    if (vmErr) {
      console.error("customers: không đọc được v_viec_cskh", vmErr);
    }
    for (const v of (vm as ViecCskh[] | null) ?? []) {
      (viecMoByPatient[v.clinic_patient_id] ??= []).push(v);
    }
    const { data: tt, error: ttErr } = await tuongTacPromise;
    tuongTacError = ttErr;
    for (const t of (tt as TuongTacRaw[] | null) ?? []) {
      const nv = Array.isArray(t.staff) ? t.staff[0] : t.staff;
      (tuongTacByPatient[t.clinic_patient_id] ??= []).push({
        id: t.id,
        huy_luc: t.huy_luc,
        xay_ra_luc: t.xay_ra_luc,
        loai: t.loai,
        kenh: t.kenh,
        ket_qua: t.ket_qua,
        khach_xac_nhan: t.khach_xac_nhan,
        noi_dung: t.noi_dung,
        trang_thai_ma: t.trang_thai_ma,
        appointment_id: t.appointment_id,
        nhan_vien: nv?.full_name ?? null,
        nguon: "tuong_tac",
      });
    }
  }

  // ───────────────────────────────────────────────────────────────────────
  // LỊCH SỬ CÁC LẦN KHÁM — dựng chuỗi, không dựng danh sách phẳng
  // ───────────────────────────────────────────────────────────────────────
  //
  // Quang 10/08/2026: timeline dọc, có giờ bắt đầu và kết thúc; TÁI KHÁM nối
  // tiếp lượt trước thành MỘT chuỗi, còn khám mới là chuỗi RIÊNG.
  //
  // GOM THEO `appointment`, RỒI MỚI GHÉP `visit` — không gom theo visit.
  // Lịch chưa check-in KHÔNG có dòng `visit` (nó chỉ ra đời lúc check-in), nên
  // dựng theo visit_id sẽ làm mọi lịch đã huỷ, khách không đến, và lịch còn ở
  // tương lai BIẾN MẤT khỏi lịch sử — đúng những lượt CSKH cần nhìn lại nhất.
  const lichSuKhamByPatient: Record<string, ChuoiKham[]> = {};
  if (rows.length) {
    const { data: visitRows } = await supabase
      .from("visit")
      .select("appointment_id, checked_in_at, closed_at, finalized_at")
      .in("clinic_patient_id", shownIds)
      .limit(3000);
    const visitTheoLich: Record<
      string,
      { batDau: string | null; ketThuc: string | null }
    > = {};
    for (const v of (visitRows ?? []) as {
      appointment_id: string | null;
      checked_in_at: string | null;
      closed_at: string | null;
      finalized_at: string | null;
    }[]) {
      if (!v.appointment_id) continue;
      visitTheoLich[v.appointment_id] = {
        batDau: v.checked_in_at,
        // BA MỐC KẾT THÚC, ưu tiên theo độ chắc chắn: quầy đóng lượt >
        // bác sĩ ký bệnh án > CSKH bấm checkout (ghép ở dưới). Không có mốc
        // nào thì để null và nói ra là "chưa đóng" — đừng bịa giờ.
        ketThuc: v.closed_at ?? v.finalized_at ?? null,
      };
    }

    for (const [pid, list] of Object.entries(grouped)) {
      const cacLuot: LuotKham[] = list
        .filter((a) => a.id)
        .sort((x, y) => mocMs(x.slot_start) - mocMs(y.slot_start))
        .map((a) => {
          const v = visitTheoLich[a.id as string];
          const buoc = (tuongTacByPatient[pid] ?? [])
            .filter((d) => d.appointment_id === a.id)
            .sort((x, y) => mocMs(x.xay_ra_luc) - mocMs(y.xay_ra_luc));
          // CSKH bấm "Checkout" ghi một dòng CHECK_OUT — đó là mốc kết thúc
          // theo góc nhìn của người trực, dùng khi quầy chưa đóng lượt.
          const checkout = buoc.find((d) => d.loai === "CHECK_OUT");
          return {
            id: a.id as string,
            slot_start: a.slot_start,
            status: a.status,
            // DỊCH VỤ THEO MÃ, không chỉ theo tên. Nút "Tái khám" khoá dịch vụ
            // của lượt đang xem, và nó cần `service_type_id` chứ không cần chữ.
            service_type_id: a.service_type_id ?? null,
            service_name: pick1(a.service)?.name ?? null,
            doctor_name: pick1(a.doctor)?.full_name ?? null,
            lich_truoc_id: a.lich_truoc_id ?? null,
            // MẤT BÁC SĨ — TÍNH CHO CHÍNH LƯỢT NÀY.
            //
            // Cùng phép tính với `mat_bac_si` của lịch đại diện bên trên, chỉ
            // khác là gắn vào từng lượt. Bản trước chỉ có ở lịch đại diện, và
            // màn hình vẽ khi `luotDangXem.id === selectedAppt.id` — một phép
            // so giữa hai nguồn dữ liệu khác nhau, im lặng khi chúng không trỏ
            // cùng một lịch.
            //
            // `doCaTruc` vẫn là chốt an toàn: tập ca trực rỗng (truy vấn hỏng,
            // tuần chưa xếp) KHÔNG được đọc thành "mọi bác sĩ đều nghỉ" — báo
            // nhầm hàng loạt tệ hơn không báo.
            // Bật cả khi bác sĩ ĐÃ BỊ GỠ (doctor_id về NULL): lúc ấy điều kiện
            // "có bác sĩ mà không có ca" không còn đúng, nhưng lịch vẫn đang
            // chờ xếp lại và khách vẫn cần được gọi.
            mat_bac_si:
              !!a.bac_si_da_go_id ||
              (doCaTruc &&
              !!a.doctor_id &&
              !daQua(a.slot_start, nowMs()) &&
              ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"].includes(a.status) &&
              !coCaTruc.has(`${a.doctor_id}|${ngayVN(a.slot_start)}`)),
            // Lý do huỷ đi theo TỪNG LƯỢT, không theo khách: một đợt có thể có
            // ba lượt mà chỉ một lượt bị huỷ. Đặt ở cấp đợt là gán sai lượt.
            ly_do_huy_ma: a.ly_do_huy_ma ?? null,
            cancellation_reason: a.cancellation_reason ?? null,
            created_at: a.created_at ?? null,
            cancelled_at: a.cancelled_at ?? null,
            bat_dau: v?.batDau ?? null,
            ket_thuc: v?.ketThuc ?? checkout?.xay_ra_luc ?? null,
            buoc: buoc.map((d) => ({
              luc: d.xay_ra_luc,
              huy_luc: d.huy_luc ?? null,
              trang_thai_ma: d.trang_thai_ma ?? null,
              loai: d.loai,
              ket_qua: d.ket_qua,
              nhan_vien: d.nhan_vien,
            })),
          };
        });
      if (!cacLuot.length) continue;

      // GHÉP CHUỖI. Một lượt có `lich_truoc_id` thì nối vào chuỗi chứa lượt ấy;
      // không có thì mở chuỗi mới. Duyệt theo thứ tự thời gian nên lượt trước
      // luôn đã được xếp chỗ khi tới lượt sau.
      const chuoiCuaLuot: Record<string, number> = {};
      const chuoi: ChuoiKham[] = [];
      for (const luot of cacLuot) {
        const chiSo =
          luot.lich_truoc_id !== null
            ? chuoiCuaLuot[luot.lich_truoc_id]
            : undefined;
        if (chiSo !== undefined) {
          chuoi[chiSo]!.luot.push(luot);
          chuoiCuaLuot[luot.id] = chiSo;
        } else {
          // `lich_truoc_id` trỏ tới một lượt KHÔNG có trong danh sách (lịch đã
          // bị dọn, hoặc ngoài phạm vi truy vấn) cũng rơi vào đây. Mở chuỗi mới
          // còn hơn ném lượt ấy đi.
          chuoiCuaLuot[luot.id] = chuoi.length;
          chuoi.push({ luot: [luot] });
        }
      }
      // Chuỗi mới nhất lên đầu — người trực quan tâm lần gần đây trước.
      chuoi.sort(
        (a, b) =>
          mocMs(b.luot[b.luot.length - 1]!.slot_start) -
          mocMs(a.luot[a.luot.length - 1]!.slot_start),
      );
      lichSuKhamByPatient[pid] = chuoi;
    }
  }

  // VÒNG GOM MỐC GỌI ĐÃ BỎ cùng khối Nhắc tái khám (Quang chốt 09/08/2026) —
  // không còn ai đọc `taiKhamByPatient` nữa.
  //
  // NHƯNG LỜI GỌI THÌ Ở LẠI, VÀ PHẢI Ở LẠI. Xem điểm 2 trong ghi chú của
  // `recallPromise` bên trên: endpoint này chạy `sinh_viec_nhac_tai_kham()`
  // TRƯỚC khi trả về, và dự án chưa có bộ hẹn giờ nào. Nó là thứ duy nhất còn
  // sinh việc nhắc của hôm nay. Bỏ nó đi vì "không ai đọc kết quả" thì hàng đợi
  // nhắc sẽ vĩnh viễn rỗng — và đúng như lần trước, KHÔNG AI BÁO LỖI: nhãn
  // "Nhắc đi khám hôm nay" chỉ đơn giản là không bao giờ xuất hiện nữa.
  //
  // VÀ NAY KẾT QUẢ ĐƯỢC DÙNG LẠI. Từ 09/08 lời gọi này chỉ còn chạy để sinh
  // việc rồi ném kết quả đi, vì khối "Nhắc tái khám" đã gỡ khỏi màn. Hệ quả:
  // hai trạng thái `MOI_TAI_KHAM` và `NHAC_DI_KHAM` vẫn hiện chip đỏ "quá giờ
  // hẹn" ở danh sách mà CSKH KHÔNG có chỗ nào đóng chúng — đường ghi
  // (`/api/recall-jobs/{id}/ket-qua`) vẫn mở cho vai CSKH suốt thời gian ấy,
  // chỉ là không nút nào gọi tới.
  const taiKhamByPatient: Record<string, MocTaiKham[]> = {};
  const recall = await recallPromise;
  for (const r of [...(recall?.luot1 ?? []), ...(recall?.luot2 ?? [])]) {
    (taiKhamByPatient[r.clinic_patient_id] ??= []).push(r);
  }

  return (
    <div className="space-y-3">
      {/* Tiêu đề nằm ở THANH TRÊN CÙNG (GlobalHeader) — nó đã hiện đúng
          "Quản lý khách hàng" kèm chính câu mô tả này. */}

      {error || cskhError || tuongTacError || trangThaiError ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {(error ?? cskhError ?? tuongTacError ?? trangThaiError)?.message}
        </div>
      ) : (
        <CustomersView
          rows={rows}
          apptByPatient={apptByPatient}
          cskhByPatient={cskhByPatient}
          tuongTacByPatient={tuongTacByPatient}
          trangThaiByPatient={trangThaiByPatient}
          viecMoByPatient={viecMoByPatient}
          phanHoiByPatient={phanHoiByPatient}
          lichSuKhamByPatient={lichSuKhamByPatient}
          henGoiLaiByPatient={henGoiLaiByPatient}
          taiKhamByPatient={taiKhamByPatient}
          tepByPatient={tepByPatient}
          locations={locations}
          q={q}
          period={period}
          by={by}
          initialSelected={selected}
          initialViec={viec}
          initialLuot={luot}
          canEdit={canEdit}
          canManage={canManage}
          canOperateCskh={canOperateCskh}
          services={services}
          doctors={doctors}
        />
      )}
    </div>
  );
}
