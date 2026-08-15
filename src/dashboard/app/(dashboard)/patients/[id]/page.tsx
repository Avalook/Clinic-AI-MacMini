// Patient detail: admin info + appointment history + clinical history
// (visits/SOAP, lab results, pregnancy). The clinical history is the
// doctor's "bệnh án / tiền sử khám" view.
// SECURITY: national_id_number (CCCD) is intentionally NOT selected — D-identity.

import { redirect } from "next/navigation";
import PatientDetail from "./PatientDetail";
import PatientHistory from "./PatientHistory";
import PatientBooking from "./PatientBooking";
import PatientCskhLog from "./PatientCskhLog";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getClinicRole, getClinicStaffId } from "../../../../lib/clinic-session";
import {
  canReadClinical,
  canWriteIntake,
  isDoctorRole,
  isPhysicianRole,
  canEditPatient,
} from "../../../../lib/roles";
import type { Option } from "../AppointmentBooking";
import { listBookableDoctors } from "../../../../lib/doctors-server";

export const dynamic = "force-dynamic";

export default async function PatientDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ new?: string; code?: string }>;
}) {
  const { id } = await params;
  const { new: isNew, code } = await searchParams;

  const role = await getClinicRole();

  // Bác sĩ chỉ được mở hồ sơ BN CỦA MÌNH (có lịch hẹn với bác sĩ này). Chặn cả
  // truy cập trực tiếp bằng URL, không chỉ ẩn ở danh sách.
  if (isDoctorRole(role) && role !== "TKYK") {
    const staffId = await getClinicStaffId();
    const supabase = await getSupabaseServer();
    const { data: own } = await supabase
      .from("appointment")
      .select("id")
      .eq("doctor_id", staffId)
      .eq("clinic_patient_id", id)
      .limit(1)
      .maybeSingle();
    if (!own) redirect("/patient-list");
  }

  // Booking is an intake action (CSKH / Lễ tân / Quản lý). Only those roles see
  // the form, so only load its dropdown options when they will be used.
  const canBook = canWriteIntake(role);
  // Sửa thông tin hành chính: intake + bác sĩ (canEditPatient) — vd CSKH mở từ
  // "Danh sách bệnh nhân" sửa tại trang chi tiết.
  const canEdit = canEditPatient(role);
  const canSeeClinicalHistory = canReadClinical(role);

  let services: Option[] = [];
  let doctors: Option[] = [];
  let locations: Option[] = [];
  if (canBook) {
    const supabase = await getSupabaseServer();
    const [locRes, svcRes, docRes] = await Promise.all([
      supabase.from("clinic_location").select("id, name").order("name"),
      supabase.from("service_type").select("id, name").order("name"),
      listBookableDoctors(),
    ]);
    locations = (locRes.data ?? []).map((r) => ({
      id: r.id as string,
      label: r.name as string,
    }));
    // Bỏ dịch vụ rác "FREE" khỏi dropdown đặt lịch (feedback B5#3).
    services = (svcRes.data ?? [])
      .filter((r) => (r.name as string)?.trim().toUpperCase() !== "FREE")
      .map((r) => ({
        id: r.id as string,
        label: r.name as string,
      }));
    doctors = docRes;
  }

  return (
    <div className="mx-auto max-w-[1320px] space-y-5">
      <header className="rounded-card border border-line bg-surface px-4 py-4 shadow-card sm:px-5">
        <p className="text-label font-semibold uppercase tracking-[0.14em] text-brand-700">Hồ sơ & hành trình</p>
        <h1 className="mt-1 text-xl font-semibold text-ink">Hồ sơ bệnh nhân</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Thông tin hành chính và lịch hẹn. CCCD không hiển thị; nội dung lâm sàng
          vẫn được phân quyền riêng theo vai trò.
        </p>
      </header>
      {isNew && (
        <div className="rounded-card border border-success-bg bg-success-bg px-4 py-3 text-sm text-success">
          ✓ Đã tạo hồ sơ bệnh nhân
          {code ? (
            <>
              {" "}
              — Mã BN:{" "}
              <span className="font-mono font-semibold">{code}</span>
            </>
          ) : (
            ""
          )}
          . Thông tin vừa nhập & lịch hẹn hiển thị bên dưới.
        </div>
      )}
      <PatientDetail id={id} canEdit={canEdit} />
      {canBook && (
        <PatientBooking
          clinicPatientId={id}
          services={services}
          doctors={doctors}
          locations={locations}
        />
      )}
      <PatientCskhLog id={id} />
      {canSeeClinicalHistory ? (
        <PatientHistory id={id} canReviewLabs={isPhysicianRole(role)} />
      ) : (
        <section className="rounded-lg border border-line bg-white px-4 py-3 text-sm text-ink-muted">
          Hồ sơ lâm sàng chỉ hiển thị cho bác sĩ, điều dưỡng và thư ký y khoa.
          Thông tin hành chính và nhật ký CSKH vẫn hiển thị ở trên.
        </section>
      )}
    </div>
  );
}
