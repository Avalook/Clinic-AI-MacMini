// Server component: HỒ SƠ KHÁCH HÀNG — thông tin hành chính (mục I) ĐẦY ĐỦ như
// CSKH vừa nhập + lịch sử lịch hẹn. (Khác "Hồ sơ bệnh nhân/TÓM TẮT KHÁM BỆNH" của
// bác sĩ — cái đó ở board "Công việc của tôi".)
// SECURITY: national_id_number (CCCD) is NOT selected — D-identity gate.

import Link from "next/link";
import StatusBadge from "../../StatusBadge";
import PatientAdminEditor from "../../PatientAdminEditor";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { fmtDateTimeOrDate } from "../../../../lib/datetime";
import { doctorName } from "../../../../lib/doctor-name";

interface PatientRow {
  clinic_patient_id: string;
  patient_code: string;
  full_name: string;
  date_of_birth: string | null;
  birth_year?: number | null;
  gender: string | null;
  phone_primary: string | null;
  phone_secondary: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  van_de_di_kham: string | null;
  linh_vuc: string | null;
  created_at: string;
}

interface AppointmentRow {
  id: string;
  slot_start: string;
  status: string;
  booking_channel: string | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}

const PATIENT_COLUMNS_BASE =
  "clinic_patient_id, patient_code, full_name, date_of_birth, gender, " +
  "phone_primary, phone_secondary, ethnicity, nationality, occupation, " +
  "patient_objection, address, guardian_name, van_de_di_kham, linh_vuc, created_at";
// birth_year cần migration 040; nếu chưa apply → fallback PATIENT_COLUMNS_BASE.
const PATIENT_COLUMNS = PATIENT_COLUMNS_BASE + ", birth_year";

// doctor is a LEFT JOIN (doctor_id is nullable).
const APPOINTMENT_COLUMNS = `
  id, slot_start, status, booking_channel,
  doctor:staff!doctor_id ( full_name ),
  service:service_type!service_type_id ( name )
`;

function ageFromDob(dob: string | null, birthYear?: number | null): string {
  if (!dob && birthYear) return String(new Date().getFullYear() - birthYear);
  if (!dob) return "—";
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return "—";
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const m = now.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age -= 1;
  return String(age);
}

// Ngày sinh hiển thị: năm-only (birth_year) → "1990"; else ngày sinh thật.
function dobLabel(p: PatientRow): string {
  if (p.birth_year) return String(p.birth_year);
  return p.date_of_birth ?? "—";
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-meta text-ink-muted">{label}</dt>
      <dd className="mt-0.5 text-emph text-ink">{value}</dd>
    </div>
  );
}

export default async function PatientDetail({
  id,
  canEdit = false,
}: {
  id: string;
  /** CSKH/Lễ tân/QL/Bác sĩ: sửa thông tin hành chính ngay tại đây. */
  canEdit?: boolean;
}) {
  const supabase = await getSupabaseServer();

  const [patientRes, apptRes] = await Promise.all([
    supabase
      .from("patient")
      .select(PATIENT_COLUMNS)
      .eq("clinic_patient_id", id)
      .maybeSingle(),
    supabase
      .from("appointment")
      .select(APPOINTMENT_COLUMNS)
      .eq("clinic_patient_id", id)
      .order("slot_start", { ascending: false })
      .limit(20),
  ]);

  let patient = patientRes.data as PatientRow | null;
  let perr = patientRes.error;
  // birth_year chưa migrate → query lỗi cột thiếu → đọc lại không có birth_year.
  if (perr && /birth_year|column/i.test(perr.message ?? "")) {
    const retry = await supabase
      .from("patient")
      .select(PATIENT_COLUMNS_BASE)
      .eq("clinic_patient_id", id)
      .maybeSingle();
    patient = retry.data as PatientRow | null;
    perr = retry.error;
  }
  const error = perr ?? apptRes.error;
  const appointments = (apptRes.data as AppointmentRow[] | null) ?? [];

  if (error) {
    return (
      <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
        {error.message}
      </div>
    );
  }

  if (!patient) {
    return (
      <div className="space-y-3">
        <div className="rounded-lg border border-line bg-white px-3 py-6 text-center text-ink-muted">
          Không tìm thấy bệnh nhân.
        </div>
        <Link
          href="/patient-list"
          className="text-sm text-brand-600 hover:underline"
        >
          ← Về danh sách BN
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <section
        aria-label="Thông tin hành chính bệnh nhân"
        className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <div className="flex items-center gap-4 border-b border-surface-sunken bg-gradient-to-r from-brand-50 to-white p-4 sm:p-6">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xl font-semibold text-white">
            {patient.full_name.trim().charAt(0).toUpperCase() || "?"}
          </span>
          <div className="min-w-0">
            <h2 className="truncate text-lg font-semibold text-ink">
              {patient.full_name}
            </h2>
            <p className="mt-0.5 font-mono text-sm text-ink-muted">
              {patient.patient_code}
            </p>
          </div>
        </div>
        {canEdit ? (
          // CSKH/Lễ tân/QL/Bác sĩ: sửa hành chính tại chỗ (PATCH /api/patients).
          <div className="p-4 sm:p-6">
            <PatientAdminEditor
              patient={{
                clinic_patient_id: patient.clinic_patient_id,
                full_name: patient.full_name,
                date_of_birth: patient.date_of_birth,
                phone_primary: patient.phone_primary,
                phone_secondary: patient.phone_secondary,
                gender: patient.gender,
                ethnicity: patient.ethnicity,
                nationality: patient.nationality,
                occupation: patient.occupation,
                patient_objection: patient.patient_objection,
                address: patient.address,
                guardian_name: patient.guardian_name,
                van_de_di_kham: patient.van_de_di_kham,
                linh_vuc: patient.linh_vuc,
              }}
            />
          </div>
        ) : (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 p-4 sm:grid-cols-4 sm:gap-x-6 sm:p-6">
            <Field label="Ngày sinh" value={dobLabel(patient)} />
            <Field label="Tuổi" value={ageFromDob(patient.date_of_birth, patient.birth_year)} />
            <Field label="Giới tính" value={patient.gender ?? "—"} />
            <Field label="SĐT" value={patient.phone_primary ?? "—"} />
            <Field label="SĐT người nhà" value={patient.phone_secondary ?? "—"} />
            <Field label="Dân tộc" value={patient.ethnicity ?? "—"} />
            <Field label="Quốc tịch" value={patient.nationality ?? "—"} />
            <Field label="Nghề nghiệp" value={patient.occupation ?? "—"} />
            <Field label="Đối tượng" value={patient.patient_objection ?? "—"} />
            <Field
              label="Số lịch hẹn"
              value={appointments.length >= 20 ? "20+" : String(appointments.length)}
            />
            <div className="col-span-2 sm:col-span-4">
              <dt className="text-meta text-ink-muted">Địa chỉ</dt>
              <dd className="mt-0.5 text-emph text-ink">
                {patient.address ?? "—"}
              </dd>
            </div>
          </dl>
        )}
      </section>

      <section aria-label="Lịch sử lịch hẹn" className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
        <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
          <div>
            <h3 className="text-base font-semibold text-ink">Lịch sử lịch hẹn</h3>
            <p className="mt-0.5 text-xs text-ink-muted">{appointments.length >= 20 ? "20+" : appointments.length} lượt hẹn gần đây</p>
          </div>
          <span className="rounded-chip bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-800">{appointments.length}</span>
        </header>

        {/* Mobile: card list (<md). */}
        <div className="space-y-2 p-3 md:hidden">
          {appointments.map((a) => (
            <div
              key={a.id}
              className="rounded-control border border-line bg-white p-3 shadow-card"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-mono text-xs text-ink-soft">
                  {fmtDateTimeOrDate(a.slot_start)}
                </span>
                <StatusBadge status={a.status} />
              </div>
              <p className="mt-1 text-sm text-ink">
                {a.service?.name ?? "—"}
              </p>
              <p className="text-xs text-ink-soft">
                {a.doctor?.full_name ? doctorName(a.doctor.full_name) : "—"} ·{" "}
                {a.booking_channel ?? "—"}
              </p>
            </div>
          ))}
          {appointments.length === 0 && (
            <div className="rounded-lg border border-line bg-white px-4 py-6 text-center text-sm text-ink-muted">
              Chưa có lịch hẹn.
            </div>
          )}
        </div>

        {/* Desktop: table (≥md). */}
        <div className="hidden max-h-[88vh] min-h-[180px] overflow-auto md:block">
          <table className="min-w-full divide-y divide-brand-100 text-sm">
            <thead className="sticky top-0 z-10 bg-brand-100 text-left text-label uppercase tracking-wide text-brand-800">
              <tr>
                <th className="px-4 py-2.5 font-semibold">Ngày giờ</th>
                <th className="px-4 py-2.5 font-semibold">Dịch vụ</th>
                <th className="px-4 py-2.5 font-semibold">Bác sĩ</th>
                <th className="px-4 py-2.5 font-semibold">Trạng thái</th>
                <th className="px-4 py-2.5 font-semibold">Kênh đặt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-100">
              {appointments.map((a) => (
                <tr
                  key={a.id}
                  className="transition-colors duration-150 hover:bg-brand-50"
                >
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-soft">
                    {fmtDateTimeOrDate(a.slot_start)}
                  </td>
                  <td className="px-4 py-2.5 text-ink">
                    {a.service?.name ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-ink-soft">
                    {a.doctor?.full_name ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge status={a.status} />
                  </td>
                  <td className="px-4 py-2.5 text-ink-soft">
                    {a.booking_channel ?? "—"}
                  </td>
                </tr>
              ))}
              {appointments.length === 0 && (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-6 text-center text-ink-muted"
                  >
                    Chưa có lịch hẹn.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
