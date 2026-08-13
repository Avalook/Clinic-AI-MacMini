// Appointment booking for CSKH / Lễ tân. Same access model + service-role
// write path as /api/patients.
//
//   POST { clinic_patient_id, doctor_id?, service_type_id, location_id,
//          slot_start, slot_end, booking_channel? }
//     → { ok: true, appointment_id }
//
// Đặt trùng nổi lên thành 409 kèm câu tiếng Việt. Lưới ở database là chỉ mục
// uq_appointment_patient_slot_live (một bệnh nhân, một mốc giờ) và trigger
// enforce_slot_capacity (số chỗ mỗi bác sĩ mỗi khung) — KHÔNG phải một ràng
// buộc exclusion tên appointment_no_doctor_overlap như dòng cũ ở đây khai;
// ràng buộc đó không tồn tại trong schema.
//
//   PATCH { id, action: "confirm" | "decline" }   (DOCTOR only, own appt)
//     → { ok: true, status }
//   Two-step confirmation: CSKH confirms WITH THE PATIENT (cskh_confirm:
//   SCHEDULED→CSKH_CONFIRMED) but the slot still awaits the doctor. Confirm:
//   SCHEDULED|CSKH_CONFIRMED→CONFIRMED. Decline: SCHEDULED|CSKH_CONFIRMED→
//   DOCTOR_DECLINED (keeps doctor_id for history; surfaces to CSKH in the
//   "Đã huỷ / Từ chối" column + the declined-appointments notice in the layout).

import { VN_OFFSET } from "../../../lib/datetime";
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import {
  canWriteIntake,
  isDoctorRole,
  canManageAppt,
  canCheckin,
} from "../../../lib/roles";
import { proxyJsonToBackend } from "../../../lib/backend-proxy";
import { type PatientKind } from "../../../lib/capacity";

interface Body {
  clinic_patient_id?: string;
  doctor_id?: string;
  service_type_id?: string;
  location_id?: string;
  slot_start?: string;
  slot_end?: string;
  booking_channel?: string;
  queue_number?: string;
  // Capacity Phase 1 (T-20260629-CAP-01) — CSKH nhập tay (DEC-3).
  patient_kind?: string;
  thanh_min?: number;
  sono_min?: number;
  need_sono?: boolean;
  // Ghi chú vận hành của CSKH. BookingHub đã gửi trường này từ đầu; nó không
  // được khai báo ở đây nên rơi ngay tại tầng này, và appointment cũng chưa có
  // cột để nhận. Người dùng gõ, bấm lưu, hệ thống báo thành công, chữ biến mất.
  notes?: string;
  /** Lịch hẹn mà lịch này là tái khám của nó. Xem migration 20260810000007. */
  lich_truoc_id?: string;
}

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date"); // YYYY-MM-DD
  const doctorId = searchParams.get("doctor_id");
  const benhNhan = (searchParams.get("clinic_patient_id") ?? "").trim();

  if (!date && !benhNhan) {
    return NextResponse.json(
      { error: "Missing date or clinic_patient_id parameter" },
      { status: 400 },
    );
  }

  // GATE + BOUND. Trước đây route này chỉ kiểm "đã đăng nhập chưa": dược sĩ,
  // thu ngân, bất kỳ ai có phiên đều đọc được toàn bộ lịch hẹn trong ngày, và
  // không có .limit() nên một ngày bận trả về bao nhiêu dòng cũng phải trả hết.
  // Việc phân tách tenant thì phó mặc hoàn toàn cho RLS.
  //
  // Lịch hẹn là dữ liệu vận hành: những vai nhìn thấy nó trên màn hình là nhóm
  // đặt lịch/tiếp nhận + bàn khám. Cùng ranh giới mà /appointments và /tasks
  // đang dùng, chỉ là ở đây nói thành lời.
  const role = await getClinicRole();
  if (!canWriteIntake(role) && !isDoctorRole(role) && !canCheckin(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // LỊCH SẮP TỚI CỦA MỘT NGƯỜI — để màn Đặt lịch nói được "người này đã có
  // lịch rồi" TRƯỚC khi CSKH bấm đặt thêm.
  //
  // Quang 09/08/2026: *"ấn vào 1 bệnh nhân đã đặt lịch rồi thì trang bên phải
  // phải hiện cái lịch đã đặt ra chứ, để người ta còn biết người này đặt rồi
  // chứ đặt trùng liên tục à"*.
  //
  // KHÔNG lọc theo ngày đang xem: đặt trùng hay xảy ra nhất khi lịch cũ nằm ở
  // một ngày khác — đúng cái mà lưới trước mặt không hiện. Chỉ lấy từ BÂY GIỜ
  // trở đi; lịch đã qua không ngăn ai đặt thêm.
  if (benhNhan) {
    const { data, error } = await caller
      .from("appointment")
      .select("id, slot_start, status, doctor_id, service_type_id")
      .eq("clinic_patient_id", benhNhan)
      .gte("slot_start", new Date().toISOString())
      .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)")
      .order("slot_start")
      .limit(20);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({ appointments: data ?? [] });
  }

  // CỬA SỔ MỘT NGÀY — TÍNH Ở ĐÂY, SAU KHI ĐÃ CHẮC CÓ `date`.
  //
  // LỖI 10/08/2026, và nó là một lỗi 500 CÂM. Hai dòng này vốn nằm ngay dưới
  // khối kiểm tham số, chạy VÔ ĐIỀU KIỆN. Nhưng điều kiện ở trên là
  // `!date && !benhNhan` — nghĩa là hỏi theo BỆNH NHÂN (không kèm ngày) đi qua
  // được, rồi `new Date("nullT00:00:00+07:00")` cho một Invalid Date và
  // `.toISOString()` ném `RangeError: Invalid time value`.
  //
  // Tức là nhánh "khách này đã có lịch gì" — thứ sinh ra để chặn đặt trùng —
  // CHƯA TỪNG chạy được lần nào. Nó luôn 500.
  //
  // Ba triệu chứng tưởng rời nhau, thật ra là một:
  //   · log dashboard rải rác `⨯ RangeError: Invalid time value` (không có
  //     stack component vì lỗi ném trong route handler, không phải trong render)
  //   · panel Đặt lịch rơi vào nhánh `kind: "hong"` của `LichSapToiCuaKhach`
  //   · và bài kiểm `booking-double-check-boundary` cảnh báo đúng chuyện ấy:
  //     hỏi hỏng mà im lặng thì người trực đọc thành "khách chưa có lịch".
  //
  // Nhánh bệnh nhân ở trên đã `return` trước khi tới đây, nên tới dòng này thì
  // `date` chắc chắn có. Ép kiểu bằng một câu kiểm thật thay vì tin vào luồng:
  // luồng đổi được, câu kiểm thì không.
  if (!date) {
    return NextResponse.json(
      { error: "Missing date parameter" },
      { status: 400 },
    );
  }
  // KIỂM TRƯỚC KHI GỌI `toISOString()`, không phải sau: trên một Invalid Date
  // thì chính `toISOString()` là thứ NÉM lỗi, nên mọi câu kiểm đặt sau nó đều
  // không bao giờ chạy tới. Đó đúng là hình dạng của lỗi vừa sửa.
  const dauNgay = new Date(`${date}T00:00:00${VN_OFFSET}`);
  const cuoiNgay = new Date(`${date}T23:59:59${VN_OFFSET}`);
  if (Number.isNaN(dauNgay.getTime()) || Number.isNaN(cuoiNgay.getTime())) {
    return NextResponse.json(
      { error: `Ngày không hợp lệ: ${date}` },
      { status: 400 },
    );
  }
  const startOfDay = dauNgay.toISOString();
  const endOfDay = cuoiNgay.toISOString();

  let query = caller
    .from("appointment")
    .select("id, slot_start, queue_number, status, doctor_id, booking_channel")
    .gte("slot_start", startOfDay)
    .lte("slot_start", endOfDay)
    .not("status", "eq", "CANCELLED")
    .not("status", "eq", "NO_SHOW")
    // Một ngày của Dr4Women vào khoảng 40–60 lượt; 500 là trần an toàn để một
    // ngày bất thường không kéo cả trang xuống mà vẫn không cắt mất dữ liệu thật.
    .order("slot_start")
    .limit(500);

  if (doctorId) {
    query = query.eq("doctor_id", doctorId);
  }

  const { data, error } = await query;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ appointments: data });
}

export async function POST(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });
  const role = await getClinicRole();
  if (!canWriteIntake(role)) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const clinic_patient_id = (body.clinic_patient_id ?? "").trim();
  const service_type_id = (body.service_type_id ?? "").trim();
  const location_id = (body.location_id ?? "").trim();
  const slot_start = (body.slot_start ?? "").trim();
  const slot_end = (body.slot_end ?? "").trim();
  // location_id KHÔNG còn bắt buộc: bỏ trống thì backend dùng cơ sở của chính
  // người đang đặt (identity.location_id). Trước đây trình duyệt buộc phải nghĩ
  // ra một giá trị, và giá trị nó nghĩ ra là "cơ sở đầu tiên trong danh sách".
  if (!clinic_patient_id || !service_type_id) {
    return NextResponse.json(
      { error: "Thiếu bệnh nhân hoặc dịch vụ." },
      { status: 400 },
    );
  }
  if (!slot_start || !slot_end) {
    return NextResponse.json({ error: "Thiếu giờ hẹn." }, { status: 400 });
  }
  // KIỂM ĐỌC ĐƯỢC TRƯỚC, RỒI MỚI SO SÁNH. `new Date("rác").getTime()` cho `NaN`,
  // và MỌI phép so sánh với `NaN` đều `false` — nên câu kiểm bên dưới IM LẶNG
  // cho qua đúng lúc nó cần chặn nhất. Backend vẫn đỡ được (`slot_start:
  // datetime` của pydantic trả 422), nhưng người trực nhận một lỗi 422 tiếng Anh
  // thay vì một câu tiếng Việt nói rõ sai ở đâu — và một cửa kiểm không làm được
  // việc nó ghi trên biển thì tệ hơn là không có cửa.
  const batDau = new Date(slot_start).getTime();
  const ketThuc = new Date(slot_end).getTime();
  if (Number.isNaN(batDau) || Number.isNaN(ketThuc)) {
    return NextResponse.json(
      { error: "Giờ hẹn không đọc được." },
      { status: 400 },
    );
  }
  if (ketThuc <= batDau) {
    return NextResponse.json(
      { error: "Giờ kết thúc phải sau giờ bắt đầu." },
      { status: 400 },
    );
  }

  const doctor_id = (body.doctor_id ?? "").trim() || null;
  const rawChannel = (body.booking_channel ?? "").trim();
  const queue_number = (body.queue_number ?? "").trim() || null;

  // Capacity Phase 1 — tải/ca. CSKH nhập tay; nếu thiếu thì GỢI Ý theo loại khách (DEC-3).
  const rawKind = (body.patient_kind ?? "").trim().toUpperCase();
  const patient_kind: PatientKind | null =
    rawKind === "NEW" || rawKind === "RETURN" ? (rawKind as PatientKind) : null;
  const need_sono =
    typeof body.need_sono === "boolean" ? body.need_sono : null;
  // KHÔNG suy ra phút từ loại khách nữa (20260803000005). Bảng 15'/5'/+12'/+8'
  // là con số bịa, và nó điều khiển màu của mọi ô lịch. Thời lượng thật đo từ
  // work_item (view v_consultation_duration); ở đây chỉ chuyển tiếp thứ người
  // dùng thật sự gõ vào, hoặc null.
  const thanh_min =
    typeof body.thanh_min === "number" ? body.thanh_min : null;
  const sono_min = typeof body.sono_min === "number" ? body.sono_min : null;

  // KHÁCH TỚI TRỰC TIẾP cho HÔM NAY → tạo lịch là ĐÃ CHECK-IN luôn (PK chốt: walk-in
  // auto check-in — khách đã có mặt ở quầy, không phải chờ "Gọi xác nhận"), tự cấp
  // Booking, the 2+1 pre-check, the episode attach, the audit events and the
  // walk-in auto-check-in all run in ONE transaction in FastAPI. Here they were
  // six sequential calls, so a crash mid-way left half a booking behind.
  // Chuyển tiếp khoá chống-gửi-hai-lần của trình duyệt. Không tự sinh ở đây:
  // mỗi lần bấm lại sẽ ra một khoá mới, tức là không chặn được gì. Khoá phải do
  // BookingHub sinh MỘT LẦN cho MỘT lần đặt và giữ nguyên qua các lần thử lại.
  const idempotencyKey =
    request.headers.get("Idempotency-Key")?.slice(0, 200) || undefined;

  return proxyJsonToBackend(
    "POST",
    "/api/v1/appointments/bookings",
    {
      clinic_patient_id,
      service_type_id,
      location_id: location_id || null,
      slot_start,
      slot_end,
      doctor_id,
      booking_channel: rawChannel || null,
      queue_number,
      patient_kind,
      need_sono,
      thanh_min,
      sono_min,
      notes: (body.notes ?? "").trim() || null,
      // TÁI KHÁM CỦA LỊCH NÀO. Chỉ nút "Tái khám" ở màn Quản lý khách hàng
      // gửi trường này; mọi đường đặt lịch khác để trống, và trống là câu trả
      // lời đúng chứ không phải dữ liệu thiếu. Backend còn kiểm lại lịch ấy có
      // đúng của khách này không — xem BookingService.create.
      lich_truoc_id: (body.lich_truoc_id ?? "").trim() || null,
    },
    idempotencyKey,
  );
}

type PatchAction =
  | "confirm"
  | "decline"
  | "complete"
  | "checkin"
  | "undo_checkin"
  | "cskh_confirm"
  | "cancel"
  | "no_show"
  | "reassign"
  | "assign_doctor"
  | "reschedule";

interface PatchBody {
  id?: string;
  action?: PatchAction;
  cancellation_reason?: string; // cho action "cancel"
  ly_do_huy_ma?: string; // mã lý do huỷ — BẮT BUỘC khi action = "cancel"
  doctor_id?: string; // "reassign"/"assign_doctor"/"reschedule"; rỗng = bỏ phân
  slot_start?: string; // cho action "reschedule" (ISO UTC)
  slot_end?: string; // cho action "reschedule" (ISO UTC)
}

// "complete" = bác sĩ chốt KHÁM XONG (lịch → COMPLETED). KHÔNG đụng visit
// (FINALIZED là khóa pháp lý riêng, không tự quyết ở đây).
const DOCTOR_ACTIONS = new Set<PatchAction>(["confirm", "decline", "complete"]);
// Front-desk (Lễ tân/CSKH/Quản lý) actions.
const CHECKIN_ACTIONS = new Set<PatchAction>([
  "checkin",
  "undo_checkin",
  "cskh_confirm",
]);
// Quản trị vòng đời lịch: hủy + phân lại + ĐỔI LỊCH (CSKH/Quản lý).
const MANAGE_ACTIONS = new Set<PatchAction>([
  "cancel",
  "reassign",
  // Xếp bác sĩ cho một lịch đã đặt mà chưa có ai. Khác "reassign" (chỉ nhận
  // lịch bị bác sĩ từ chối) và khác "reschedule" (bắt buộc đổi giờ).
  "assign_doctor",
  "reschedule",
]);
// no_show: front-desk đánh "không đến" (canCheckin).
const ALL_ACTIONS = new Set<PatchAction>([
  ...DOCTOR_ACTIONS,
  ...CHECKIN_ACTIONS,
  ...MANAGE_ACTIONS,
  "no_show",
]);

export async function PATCH(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  const action = body.action;
  if (!id || !action || !ALL_ACTIONS.has(action)) {
    return NextResponse.json(
      { error: "Thiếu id lịch hẹn hoặc action không hợp lệ." },
      { status: 400 },
    );
  }

  const role = await getClinicRole();
  const staffId = await getClinicStaffId();

  // Gate theo nhóm: bác sĩ (own appt) · hủy/phân-lại (CSKH/QL) · không-đến
  // (front-desk) · check-in/cskh_confirm (intake).
  if (DOCTOR_ACTIONS.has(action)) {
    if (!isDoctorRole(role)) {
      return NextResponse.json(
        { error: "Chỉ bác sĩ mới xác nhận/từ chối/khám-xong lịch hẹn." },
        { status: 403 },
      );
    }
    if (!staffId) {
      return NextResponse.json(
        { error: "Chưa chọn danh tính bác sĩ." },
        { status: 403 },
      );
    }
  } else if (MANAGE_ACTIONS.has(action)) {
    if (!canManageAppt(role)) {
      return NextResponse.json(
        { error: "Chỉ CSKH / Quản lý mới hủy hoặc phân lại bác sĩ." },
        { status: 403 },
      );
    }
  } else if (action === "no_show") {
    if (!canCheckin(role)) {
      return NextResponse.json(
        { error: "Chỉ Lễ tân / Quản lý mới đánh không đến." },
        { status: 403 },
      );
    }
  } else if (!canWriteIntake(role)) {
    return NextResponse.json(
      { error: "Chỉ Lễ tân / CSKH / Quản lý mới check-in bệnh nhân." },
      { status: 403 },
    );
  }

  return proxyJsonToBackend("PATCH", `/api/v1/appointments/${id}`, {
    action,
    cancellation_reason: body.cancellation_reason ?? null,
    ly_do_huy_ma: body.ly_do_huy_ma ?? null,
    ...(body.doctor_id !== undefined ? { doctor_id: body.doctor_id || null } : {}),
    slot_start: body.slot_start ?? null,
    slot_end: body.slot_end ?? null,
  });
}
