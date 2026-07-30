// "Danh sách bệnh nhân" — BN đã khám (lịch hẹn COMPLETED). Gom theo BN để suy
// "Khám lần đầu" (1 lần) / "Tái khám" (>=2 lần). Đọc qua Supabase RLS.
//
// Bấm tên BN: chỉ vai LÂM SÀNG được bật hồ sơ lâm sàng ở panel phải. Vai vận
// hành đi tới trang thông tin hành chính; route /api/clinical-record còn chặn
// độc lập để không thể bypass bằng cách gọi API trực tiếp.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import {
  canEditPatient,
  canReadClinical,
  canWriteIntake,
  isDoctorRole,
} from "../../../lib/roles";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import PatientListView, { type ExaminedRow } from "./PatientListView";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";
import type { Option } from "../patients/AppointmentBooking";

export const dynamic = "force-dynamic";

// Đủ trường để dựng hồ sơ lâm sàng (mục I Hành chính) trong popup.
type PatientFull = NonNullable<DoctorApptRow["patient"]>;
interface ApptJoin {
  id: string;
  status: string;
  queue_number: string | null;
  slot_start: string;
  patient: PatientFull | PatientFull[] | null;
  service: { name: string } | { name: string }[] | null;
}

const SELECT = `
  id, status, queue_number, slot_start,
  patient:patient!clinic_patient_id (
    clinic_patient_id, patient_code, full_name, date_of_birth,
    phone_primary, phone_secondary, gender, ethnicity, nationality,
    occupation, patient_objection, address, guardian_name
  ),
  service:service_type!service_type_id ( name )
`;

const one = <T,>(x: T | T[] | null): T | null =>
  !x ? null : Array.isArray(x) ? (x[0] ?? null) : x;

export default async function PatientListPage() {
  await requireNavAccess("/patient-list");
  const role = await getClinicRole();
  // Membership role is authoritative. Operational roles keep the administrative
  // patient page but never mount ClinicalRecordForm.
  const enablePopup = canReadClinical(role);
  // Nút tái khám chỉ tồn tại bên trong popup; vai vận hành đặt lại lịch từ trang
  // hành chính /patients/[id], nên không cần nạp option khi popup bị chặn.
  const showRebook = enablePopup && canWriteIntake(role);
  // Bác sĩ: pager ◀ ▶ xem lượt khám trước/sau ngay trong phiếu.
  const showPager = isDoctorRole(role);
  const supabase = await getSupabaseServer();

  // Dữ liệu cho MODAL đặt lịch nhanh ("Tái khám" trong popup). Chỉ nạp khi nút hiện
  // (CSKH/Lễ tân/Quản lý — đều canWriteIntake nên POST /api/appointments cho phép).
  // Giống cách trang chi tiết BN nạp options; bỏ dịch vụ rác "FREE".
  let services: Option[] = [];
  let doctors: Option[] = [];
  let locations: Option[] = [];
  if (showRebook) {
    const [locRes, svcRes, docRes] = await Promise.all([
      supabase.from("clinic_location").select("id, name").order("name"),
      supabase.from("service_type").select("id, name").order("name"),
      supabase
        .from("staff")
        .select("id, full_name")
        .in("primary_department", ["DOCTOR", "ULTRASOUND_DOCTOR"])
        .eq("is_active", true)
        .order("full_name"),
    ]);
    locations = (locRes.data ?? []).map((r) => ({
      id: r.id as string,
      label: r.name as string,
    }));
    services = (svcRes.data ?? [])
      .filter((r) => (r.name as string)?.trim().toUpperCase() !== "FREE")
      .map((r) => ({ id: r.id as string, label: r.name as string }));
    doctors = (docRes.data ?? []).map((r) => ({
      id: r.id as string,
      label: r.full_name as string,
    }));
  }

  // BN xuất hiện ở "Danh sách bệnh nhân" khi: (a) đã khám xong (COMPLETED) — lịch
  // sử; HOẶC (b) ĐANG khám HÔM NAY (CHECKED_IN/IN_PROGRESS) — walk-in vừa tiếp
  // nhận hiện ngay, không phải chờ đóng lượt khám. Trước đây chỉ lọc COMPLETED nên
  // khách đến trực tiếp (auto CHECKED_IN) nằm ở "khách hàng" mà không lọt danh sách
  // này. Active giới hạn TRONG NGÀY để không kéo về mọi lượt CHECKED_IN cũ bị bỏ dở.
  // Sắp xếp mới→cũ để lần xuất hiện ĐẦU của mỗi BN chính là lượt gần nhất. Cap 2000.
  const { startUtc: todayStartUtc, endUtc: todayEndUtc } = vnTodayRangeUtc();
  const { data, error } = await supabase
    .from("appointment")
    .select(SELECT)
    .or(
      `status.eq.COMPLETED,and(status.in.(CHECKED_IN,IN_PROGRESS),slot_start.gte.${todayStartUtc},slot_start.lt.${todayEndUtc})`,
    )
    .order("slot_start", { ascending: false })
    .limit(2000);

  const raw = (data as ApptJoin[] | null) ?? [];
  const map = new Map<string, ExaminedRow>();
  for (const a of raw) {
    const p = one(a.patient);
    if (!p) continue;
    const cur = map.get(p.clinic_patient_id);
    if (cur) {
      cur.visit_count += 1;
    } else {
      map.set(p.clinic_patient_id, {
        clinic_patient_id: p.clinic_patient_id,
        patient_code: p.patient_code,
        full_name: p.full_name,
        phone_primary: p.phone_primary,
        date_of_birth: p.date_of_birth,
        gender: p.gender,
        visit_count: 1,
        latest: a.slot_start, // lần xuất hiện đầu = gần nhất (đã order desc)
        phan_loai: "Khám lần đầu",
        // Lượt khám GẦN NHẤT — mở trong popup hồ sơ lâm sàng (chỉ đọc).
        appt: {
          id: a.id,
          slot_start: a.slot_start,
          status: a.status,
          queue_number: a.queue_number,
          patient: p,
          service: one(a.service),
        },
      });
    }
  }
  const rows: ExaminedRow[] = [...map.values()]
    .map(
      (r): ExaminedRow => ({
        ...r,
        phan_loai: r.visit_count >= 2 ? "Tái khám" : "Khám lần đầu",
      }),
    )
    .sort((a, b) => (a.latest < b.latest ? 1 : -1));

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">
          Danh sách bệnh nhân
        </h1>
      </header>

      {error ? (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      ) : (
        // Chỉ vai lâm sàng có popup; quyền sửa hành chính vẫn được gate riêng ở
        // trang /patients/[id] và PATCH /api/patients.
        <PatientListView
          rows={rows}
          enablePopup={enablePopup}
          canEditAdmin={canEditPatient(role)}
          /* Nút tóm tắt trước khám chỉ cho BÁC SĨ. */
          showPreVisitBrief={isDoctorRole(role)}
          /* Nút Tái khám: CSKH/Lễ tân. Pager lượt khám: Bác sĩ. */
          showRebook={showRebook}
          /* Lễ tân xếp BN tái khám VÃNG LAI vào chỗ Ưu tiên (ô xanh), không phải ô hồng. */
          walkinRebook={role === "RECEPTION"}
          enableVisitPager={showPager}
          services={services}
          doctors={doctors}
          locations={locations}
        />
      )}
    </div>
  );
}
