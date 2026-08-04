// "Công việc của tôi" (CSKH) = Tình trạng lịch hẹn (kanban theo dõi hồ sơ).
// Chờ xác nhận → Đã xác nhận. Click tên KH để xem/sửa thông tin + xác nhận.
// (Trang "staff_task" cũ giữ ở TasksRealtime.tsx — chưa dùng, chưa xoá.)
// CCCD KHÔNG select (D-identity).

import { getSupabaseServer } from "../../../lib/supabase-server";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import {
  vnTodayRangeUtc,
  vnLocalToUtcISO,
  vnMonthStartUtc,
} from "../../../lib/datetime";
import { currentWeekStartVn } from "../../../lib/roster";
import {
  getClinicRole,
  getClinicStaffId,
  requireNavAccess,
} from "../../../lib/clinic-session";
import {
  isDoctorRole,
  canManageAppt,
  isTasksReadOnly,
  isCashierRole,
  isUltrasoundDoctorRole,
  isNurseRole,
} from "../../../lib/roles";
import ConfirmBoard, { type ApptRow, type Opt } from "./ConfirmBoard";
import CskhActionBoard, { type CskhActionRow } from "./CskhActionBoard";
import DoctorWorkBoard, { type DoctorApptRow } from "./DoctorWorkBoard";
import CashierWorkBoard, {
  type CashierMode,
  type CashierRow,
  type CashierServiceItem,
  type CashierDrugItem,
} from "./CashierWorkBoard";
import type { ClinicRole } from "../../../lib/roles";
import { paidCashierPaymentSeeds } from "../../../lib/clinical-workspace-policy";
import { listBookableDoctors } from "../../../lib/doctors-server";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

// Chuẩn hoá tên để khớp bảng giá (service_price): bỏ URL trong ngoặc, gộp khoảng trắng.
const normName = (s: string): string =>
  (s ?? "")
    .toLowerCase()
    .replace(/\(https?:\/\/[^)]*\)?/g, "")
    .replace(/[()]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
// Bỏ link Notion "(https://…)" khỏi tên dịch vụ/xét nghiệm cho gọn.
const cleanName = (s: string | null): string =>
  (s ?? "").replace(/\s*\(https?:\/\/[^)]*\)?/gi, "").trim();

const oneOf = <T,>(x: T | T[] | null): T | null =>
  !x ? null : Array.isArray(x) ? (x[0] ?? null) : x;

// Mode thu ngân theo vai: CASHIER_THUOC=[thuoc], CASHIER_DV=[dich_vu], CASHIER=cả hai.
function cashierModes(role: ClinicRole | null): CashierMode[] {
  if (role === "CASHIER_THUOC") return ["thuoc"];
  if (role === "CASHIER_DV") return ["dich_vu"];
  return ["thuoc", "dich_vu"];
}

// Màn THU TIỀN của thu ngân: BN đang khám hôm nay + khoản thu lấy THẬT từ hồ sơ.
//   Dịch vụ = dịch vụ khám (appointment.service_type) + CLS bác sĩ chỉ định
//   (lab_result) + dịch vụ điều dưỡng làm (service_log hôm nay).
//   Thuốc   = đơn thuốc bác sĩ kê (prescription của lượt khám).
// Giá best-effort khớp tên với service_price; chưa có → để trống. Khu QR + xác
// nhận thanh toán là khung demo (chưa có bảng billing — KHÔNG bịa trạng thái đã thu).
async function CashierTasks(modes: CashierMode[]) {
  const supabase = await getSupabaseServer();
  const { startUtc, endUtc } = vnTodayRangeUtc();

  interface VisitRaw {
    visit_id: string;
    clinic_patient_id: string;
    appointment_id: string | null;
    patient:
      | { full_name: string | null; patient_code: string | null; phone_primary: string | null }
      | { full_name: string | null; patient_code: string | null; phone_primary: string | null }[]
      | null;
    appointment:
      | { status: string | null; service: { name: string | null } | { name: string | null }[] | null }
      | { status: string | null; service: { name: string | null } | { name: string | null }[] | null }[]
      | null;
  }

  const { data: visitsRaw, error } = await supabase
    .from("visit")
    .select(
      `visit_id, clinic_patient_id, appointment_id,
       patient:patient!clinic_patient_id ( full_name, patient_code, phone_primary ),
       appointment:appointment!appointment_id ( status, service:service_type!service_type_id ( name ) )`,
    )
    .gte("created_at", startUtc)
    .lt("created_at", endUtc)
    .order("created_at", { ascending: false })
    .limit(300);

  // CHỈ hiện BN cho thu ngân khi BÁC SĨ ĐÃ KHÁM XONG (appointment.status =
  // COMPLETED). Trước đây lấy MỌI visit tạo hôm nay (kể cả CHECKED_IN/IN_PROGRESS
  // = đang khám) → thu ngân thu tiền được khi bác sĩ chưa khám xong. "Khám xong"
  // = COMPLETED (khớp /patient-list + VisitStatusBoard; dashboard KHÔNG tự set
  // visit.FINALIZED nên lọc theo appointment.status, không theo visit.status).
  const visits = ((visitsRaw as VisitRaw[] | null) ?? []).filter(
    (v) => oneOf(v.appointment)?.status === "COMPLETED",
  );
  const patientIds = [
    ...new Set(visits.map((v) => v.clinic_patient_id).filter((x): x is string => !!x)),
  ];
  const apptIds = [
    ...new Set(visits.map((v) => v.appointment_id).filter((x): x is string => !!x)),
  ];
  const visitIds = visits.map((v) => v.visit_id);
  const wantSvc = modes.includes("dich_vu");
  const wantRx = modes.includes("thuoc");

  const [labRes, svcRes, rxRes, priceRes, payRes] = await Promise.all([
    wantSvc && apptIds.length
      ? supabase
          .from("lab_result")
          .select("id, appointment_id, test_name")
          .in("appointment_id", apptIds)
          .limit(2000)
      : Promise.resolve({ data: [] }),
    wantSvc && patientIds.length
      ? supabase
          .from("service_log")
          .select("id, clinic_patient_id, service_name_raw, service:service_type!service_type_id ( name )")
          .in("clinic_patient_id", patientIds)
          .gte("ordered_at", startUtc)
          .lt("ordered_at", endUtc)
          .limit(1000)
      : Promise.resolve({ data: [] }),
    wantRx && visitIds.length
      ? supabase
          .from("prescription")
          .select("id, visit_id, drug_name_raw, quantity, dosage_instructions")
          .in("visit_id", visitIds)
          .limit(2000)
      : Promise.resolve({ data: [] }),
    supabase.from("service_price").select("name, group, unit_price").eq("active", true),
    // Khâu ĐÃ THU (bảng payment) — seed trạng thái "Đã thanh toán". Bảng có thể
    // chưa tồn tại (migration 056 chưa apply) → error → coi như rỗng (graceful).
    visitIds.length
      ? supabase
          .from("payment")
          .select("visit_id, kind, status")
          .eq("status", "PAID")
          .in("visit_id", visitIds)
      : Promise.resolve({ data: [] }),
  ]);

  const paidInit = paidCashierPaymentSeeds(
    (payRes.data as { visit_id: string; kind: string; status: string | null }[] | null) ?? [],
  );

  // Bảng giá theo tên đã chuẩn hoá (chỉ dòng có đơn giá).
  const priceThuoc = new Map<string, number>();
  const priceDV = new Map<string, number>();
  for (const p of (priceRes.data as { name: string; group: string; unit_price: number | null }[] | null) ?? []) {
    if (p.unit_price == null) continue;
    (p.group === "thuoc" ? priceThuoc : priceDV).set(normName(p.name), p.unit_price);
  }
  const dvPrice = (name: string): number | null => priceDV.get(normName(name)) ?? null;

  // CLS theo appointment.
  const labByAppt = new Map<string, { id: string; test_name: string }[]>();
  for (const l of (labRes.data as { id: string; appointment_id: string | null; test_name: string }[] | null) ?? []) {
    if (!l.appointment_id) continue;
    const arr = labByAppt.get(l.appointment_id) ?? [];
    arr.push({ id: l.id, test_name: l.test_name });
    labByAppt.set(l.appointment_id, arr);
  }
  // service_log theo BN.
  interface SvcRaw {
    id: string;
    clinic_patient_id: string;
    service_name_raw: string | null;
    service: { name: string | null } | { name: string | null }[] | null;
  }
  const svcByPatient = new Map<string, CashierServiceItem[]>();
  for (const s of (svcRes.data as SvcRaw[] | null) ?? []) {
    const name = oneOf(s.service)?.name ?? cleanName(s.service_name_raw);
    if (!name) continue;
    const arr = svcByPatient.get(s.clinic_patient_id) ?? [];
    arr.push({ id: s.id, name, price: dvPrice(name) });
    svcByPatient.set(s.clinic_patient_id, arr);
  }
  // Đơn thuốc theo lượt khám.
  interface RxRaw {
    id: string;
    visit_id: string;
    drug_name_raw: string | null;
    quantity: string | null;
    dosage_instructions: string | null;
  }
  const rxByVisit = new Map<string, CashierDrugItem[]>();
  for (const d of (rxRes.data as RxRaw[] | null) ?? []) {
    const name = (d.drug_name_raw ?? "").trim();
    if (!name) continue;
    const arr = rxByVisit.get(d.visit_id) ?? [];
    arr.push({
      id: d.id,
      name,
      quantity: d.quantity,
      dosage: d.dosage_instructions,
      price: priceThuoc.get(normName(name)) ?? null,
    });
    rxByVisit.set(d.visit_id, arr);
  }

  const rows: CashierRow[] = visits.map((v) => {
    const p = oneOf(v.patient);
    const appt = oneOf(v.appointment);
    const services: CashierServiceItem[] = [];
    if (wantSvc) {
      const examName = oneOf(appt?.service ?? null)?.name ?? null;
      if (examName)
        services.push({ id: `exam-${v.visit_id}`, name: examName, price: dvPrice(examName) });
      for (const l of v.appointment_id ? (labByAppt.get(v.appointment_id) ?? []) : []) {
        const nm = cleanName(l.test_name);
        if (nm) services.push({ id: l.id, name: nm, price: dvPrice(nm) });
      }
      services.push(...(svcByPatient.get(v.clinic_patient_id) ?? []));
    }
    return {
      visit_id: v.visit_id,
      clinic_patient_id: v.clinic_patient_id,
      full_name: p?.full_name ?? null,
      patient_code: p?.patient_code ?? null,
      phone: p?.phone_primary ?? null,
      appt_status: appt?.status ?? null,
      services,
      drugs: wantRx ? (rxByVisit.get(v.visit_id) ?? []) : [],
    };
  });

  if (error) {
    return (
      <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
        {error.message}
      </div>
    );
  }
  return <CashierWorkBoard rows={rows} modes={modes} paidInit={paidInit} />;
}

// Bác sĩ: lịch của MÌNH (đủ trường hành chính để dựng hồ sơ lâm sàng).

// readOnly = vai vận hành xem clone giao diện board bác sĩ nhưng KHÔNG được mở
// hồ sơ lâm sàng. Họ vẫn có staff id liên kết nhưng KHÔNG phải bác sĩ →
// khi readOnly ta BỎ lọc doctor_id để thấy lịch của MỌI bác sĩ (góc nhìn front
// desk). Nếu lọc theo staffId của lễ tân thì board sẽ rỗng (không lịch nào của họ).
// allDoctors = TKYK: KHÔNG lọc theo doctor_id (TKYK không phải BS trên lịch) → thấy
// hàng đợi của MỌI bác sĩ để nhập hộ bệnh án, NHƯNG vẫn GHI được (readOnly=false).
async function DoctorTasks(
  readOnly = false,
  showPreVisitBrief = false,
  allDoctors = false,
  showSono = false,
  vitalsOnly = false,
) {
  const staffId = await getClinicStaffId();
  const { startUtc } = vnTodayRangeUtc();
  // Cửa sổ 31 ngày tới: đủ cho bộ lọc Tuần này / Tuần sau / Tháng này ở board bác sĩ.
  const N = 31;
  const endUtc = new Date(new Date(startUtc).getTime() + N * DAY_MS).toISOString();
  // Mốc ĐỌC lùi về sớm nhất board có thể lọc (đầu TUẦN hoặc đầu THÁNG hiện tại) —
  // nếu chỉ đọc từ HÔM NAY thì "Tuần này"/"Tháng này" mất phần đầu kỳ đã qua (vd vào
  // Thứ Năm không thấy lịch T2–T4 của chính tuần đó). So sánh chuỗi ISO-UTC = so giờ.
  const readStartUtc = [
    startUtc,
    vnLocalToUtcISO(currentWeekStartVn(), "00:00"),
    vnMonthStartUtc(),
  ].sort()[0];

  // MỘT LƯỢT GỌI THAY CHO BA.
  //
  // Trước đây: đọc lịch hẹn → gom id → đọc lab_result (luật "chờ đọc KQ") →
  // gom bệnh nhân → đọc TOÀN BỘ lịch sử hẹn (luật "Tái khám / Khám lần đầu").
  // Ba vòng mạng NỐI TIẾP, và vòng cuối không có `limit` nên lớn theo lịch sử
  // phòng khám. Hai luật ấy đều là luật nghiệp vụ, và luật "Tái khám" còn là
  // bản sao của chính nó ở trang chủ.
  //
  // Nay cả hai tính trong SQL và về cùng dòng dữ liệu. Đã đối chiếu với đường
  // cũ trên prod trước khi đổi: 266 dòng qua 6 cửa sổ × 7 bác sĩ khớp từng
  // trường, và 7 tình huống của luật B3 dựng riêng cũng khớp
  // (xem doctor_board_service.py).
  const board = await fetchFromBackend<{ items: DoctorApptRow[] }>(
    `/api/v1/appointments/doctor-board?start=${encodeURIComponent(readStartUtc)}` +
      `&end=${encodeURIComponent(endUtc)}` +
      // Bác sĩ: chỉ lịch của MÌNH. Lễ tân (readOnly) + TKYK (allDoctors) không
      // lọc → thấy mọi bác sĩ. Giữ nguyên luật cũ, chỉ đổi nơi thực hiện.
      (staffId && !readOnly && !allDoctors ? `&doctor_id=${staffId}` : ""),
  );
  const withPhanLoai: DoctorApptRow[] = board?.items ?? [];
  // `null` = backend không trả lời. Giữ nguyên khối báo lỗi sẵn có của trang
  // thay vì hiện một bảng trống — trông y hệt "hôm nay không có ai".
  const error = board === null ? { message: "Không đọc được danh sách khám." } : null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">
          {showSono ? "Bàn khám & siêu âm" : "Danh sách khám bệnh"}
        </h1>
        {readOnly && (
          <p className="mt-0.5 text-sm text-ink-muted">
            Xem lịch khám của tất cả bác sĩ. Vai trò hiện tại không mở hồ sơ lâm sàng.
          </p>
        )}
        {allDoctors && !readOnly && (
          <p className="mt-0.5 inline-flex items-center gap-1.5 text-sm text-brand-800">
            <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[11px] font-medium">
              ✍ Nhập hộ bệnh án
            </span>
            <span className="text-ink-muted">
              Xem hàng đợi của tất cả bác sĩ & nhập hồ sơ — bác sĩ chốt khám xong.
            </span>
          </p>
        )}
      </header>
      {error ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      ) : (
        <DoctorWorkBoard
          rows={withPhanLoai}
          staffId={staffId}
          readOnly={readOnly}
          canEditAdmin={false}
          /* Nút tóm tắt trước khám: chỉ board của BÁC SĨ (DoctorTasks() — nhánh
             isDoctorRole), vai vận hành (DoctorTasks(true)) không bật. */
          showPreVisitBrief={showPreVisitBrief}
          /* Form số đo siêu âm: chỉ Bác sĩ Siêu âm (ULTRASOUND_DOCTOR). */
          showSono={showSono}
          vitalsOnly={vitalsOnly}
        />
      )}
    </div>
  );
}

const SELECT = `
  id, slot_start, status, booking_channel, cancellation_reason, cancelled_at,
  patient:patient!clinic_patient_id (
    clinic_patient_id, full_name, patient_code, phone_primary,
    phone_secondary, date_of_birth, location_id, gender, ethnicity,
    nationality, occupation, patient_objection, address, guardian_name
  ),
  doctor:staff!doctor_id ( full_name ),
  service:service_type!service_type_id ( name )
`;

export default async function TasksPage() {
  // Chặn gõ thẳng URL ngoài quyền (vd Điều dưỡng): nav ẩn là chưa đủ — không
  // có dòng này, role ngoài danh sách rơi xuống nhánh ConfirmBoard (lộ toàn
  // bộ lịch + nhật ký CSKH).
  await requireNavAccess("/tasks");
  // Bác sĩ thấy board lâm sàng riêng; CSKH/Quản lý thấy board lịch hẹn cũ.
  const role = await getClinicRole();
  // Thu ngân (CASHIER + 2 vai tách CASHIER_THUOC/CASHIER_DV): màn LÀM VIỆC thu ngân
  // riêng (2 mode thuốc/dịch vụ) — KHÔNG dùng board bác sĩ. Đặt TRƯỚC isTasksReadOnly
  // để mọi vai thu ngân không rơi vào nhánh read-only board (tránh lộ lịch/BN của BS).
  if (isCashierRole(role)) return CashierTasks(cashierModes(role));
  // Bác sĩ: board lâm sàng. Bác sĩ Siêu âm thêm form số đo siêu âm thai (showSono).
  if (role === "TKYK") {
    // TKYK: nhập HỘ bệnh án cho BS → cùng board bác sĩ, GHI được, thấy MỌI bác sĩ
    // (allDoctors), complete được lịch trực tiếp, hiển thị cả siêu âm.
    return DoctorTasks(false, true, true, true);
  }
  if (isDoctorRole(role))
    return DoctorTasks(false, true, false, isUltrasoundDoctorRole(role));
  // Điều dưỡng (NURSE_ULTRASOUND): hỗ trợ BS nhập bệnh án (sinh hiệu + lý do khám)
  // → cùng board bác sĩ, GHI được (readOnly=false), thấy MỌI bác sĩ (allDoctors),
  // không siêu âm, không xem tóm tắt trước khám.
  // Điều dưỡng được điền hồ sơ như bác sĩ (mở quyền 29/6): bỏ vitalsOnly.
  if (isNurseRole(role)) return DoctorTasks(false, false, true, false, false);
  // Vai vận hành: chỉ xem lịch bác sĩ, không mở popup hồ sơ lâm sàng.
  if (isTasksReadOnly(role)) {
    const isReception = role === "RECEPTION";
    return DoctorTasks(true, false, false, false, isReception);
  }

  const supabase = await getSupabaseServer();
  const { startUtc } = vnTodayRangeUtc();
  // Hàng đợi CSKH: hôm nay → 31 ngày tới (mở rộng từ 7) để lịch CSKH vừa đặt cho
  // tuần/tháng sau VẪN hiện ở "Tình trạng lịch hẹn" (feedback B5#6).
  const endUtc = new Date(new Date(startUtc).getTime() + 31 * DAY_MS).toISOString();

  // Bảng 2 (Nhật ký CSKH) — đọc 200 việc gần nhất từ cskh_action.
  const CSKH_SELECT = `
    id, category, status, description, action_data, source_created_at, created_by_text,
    patient:patient!clinic_patient_id (
      clinic_patient_id, full_name, patient_code, phone_primary
    )
  `;

  const [apptRes, locRes, cskhRes, docRes] = await Promise.all([
    supabase
      .from("appointment")
      .select(SELECT)
      // Board 4 cột: Chờ xác nhận → Đã xác nhận → Đã khám xong → Đã huỷ / Từ chối.
      // Cột cuối để CSKH THẤY lịch bác sĩ từ chối (DOCTOR_DECLINED) + hủy + không đến.
      .in("status", [
        "SCHEDULED",
        "CSKH_CONFIRMED",
        "CONFIRMED",
        "CHECKED_IN",
        "COMPLETED",
        "CANCELLED",
        "DOCTOR_DECLINED",
        "NO_SHOW",
      ])
      .gte("slot_start", startUtc)
      .lt("slot_start", endUtc)
      .order("slot_start", { ascending: true })
      .limit(300),
    supabase.from("clinic_location").select("id, name").order("name"),
    supabase
      .from("cskh_action")
      .select(CSKH_SELECT)
      .order("source_created_at", { ascending: false, nullsFirst: false })
      .limit(200),
    // Bác sĩ để PHÂN LẠI lịch bị từ chối.
    listBookableDoctors(),
  ]);

  const rows = (apptRes.data as ApptRow[] | null) ?? [];
  const cskhRows = (cskhRes.data as CskhActionRow[] | null) ?? [];
  const locations: Opt[] = (locRes.data ?? []).map((r) => ({
    id: r.id as string,
    label: r.name as string,
  }));
  const doctors: Opt[] = docRes;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-ink">
          Tình trạng lịch hẹn
        </h1>
        <p className="text-sm text-ink-muted">
          Theo dõi hồ sơ · click tên khách hàng để xem thông tin & xác nhận lịch.
        </p>
      </header>

      {apptRes.error ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {apptRes.error.message}
        </div>
      ) : (
        <>
          <ConfirmBoard
            rows={rows}
            locations={locations}
            doctors={doctors}
            canManage={canManageAppt(role)}
          />

          {/* Ý nghĩa từng trạng thái — để phòng khám đọc hiểu (PM yêu cầu) */}
          <dl className="grid gap-2.5 rounded-lg border border-line bg-surface-muted px-4 py-3 text-xs text-ink-soft sm:grid-cols-2 lg:grid-cols-4">
            {[
              {
                dotClass: "bg-status-assigned",
                term: "Chờ xác nhận",
                desc: "Lịch mới đặt, CSKH chưa gọi xác nhận với khách.",
              },
              {
                dotClass: "bg-success",
                term: "Đã xác nhận",
                desc: "CSKH đã gọi xác nhận với khách (chờ bác sĩ nhận ca), hoặc bác sĩ đã nhận / khách đã đến.",
              },
              {
                dotClass: "bg-ink-muted",
                term: "Đã khám xong",
                desc: "Khách đã khám xong lượt này.",
              },
              {
                dotClass: "bg-danger",
                term: "Đã huỷ / Từ chối",
                desc: "Lịch bị hủy, bác sĩ từ chối, hoặc khách không đến.",
              },
            ].map((s) => (
              <div key={s.term} className="flex gap-2">
                <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${s.dotClass}`} />
                <div>
                  <dt className="font-semibold text-ink">{s.term}</dt>
                  <dd>{s.desc}</dd>
                </div>
              </div>
            ))}
          </dl>

          {/* Bảng 2 — Nhật ký CSKH (CSKH-Action). ĐANG XÂY DỰNG: data sẽ tự ghi
              khi nối Zalo/Pancake; hiện CSKH có thể ghi tay 1 việc qua nút "+". */}
          <section className="space-y-2">
            <div>
              <h2 className="text-base font-semibold text-ink">
                Nhật ký chăm sóc khách hàng (CSKH)
              </h2>
              <p className="text-sm text-ink-muted">
                Các việc CSKH theo loại (từ bảng CSKH-Action) · mỗi thẻ = 1 lần
                thao tác với khách. Bấm “+ Thêm việc” trên mỗi cột để ghi tay.
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1 rounded-md bg-warning-bg px-2 py-0.5 text-xs font-medium text-warning">
                  🚧 Đang xây dựng
                </span>
                <span className="inline-flex items-center gap-1 rounded-chip bg-status-assigned-bg px-2 py-0.5 text-xs text-status-assigned">
                  🤖 Tự ghi khi CSKH thao tác (xác nhận lịch → vào “Đặt hẹn”
                  ngay) + về sau khi nối Zalo / Pancake.
                </span>
              </div>
            </div>
            {cskhRes.error ? (
              <div className="rounded-md bg-warning-bg px-3 py-2 text-sm text-warning">
                Chưa đọc được CSKH-Action: {cskhRes.error.message}
              </div>
            ) : (
              <CskhActionBoard rows={cskhRows} />
            )}
          </section>
        </>
      )}
    </div>
  );
}
