// Đặt lịch CSKH — Hub đặt lịch hẹn sử dụng dữ liệu thật từ DB.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import BookingHub, {
  type PatientLite,
  type ApptLite,
} from "./BookingHub";
import type { Option, ProvinceOpt } from "../patients/new/NewPatientForm";
import { listBookableDoctors } from "../../../lib/doctors-server";

export const dynamic = "force-dynamic";

export default async function AppointmentsPage() {
  await requireNavAccess("/appointments");
  const supabase = await getSupabaseServer();
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();

  // Load real locations, services, doctors, provinces, patients, and today's appointments
  const [locRes, svcRes, docRes, provRes, patRes, apptRes] = await Promise.all([
    supabase.from("clinic_location").select("id, name").eq("is_active", true).order("name"),
    supabase.from("service_type").select("id, name").eq("is_active", true).order("name"),
    listBookableDoctors(),
    supabase.from("province").select("code, name, full_name").order("name"),
    supabase
      .from("patient")
      .select("clinic_patient_id, patient_code, full_name, phone_primary, date_of_birth, gender, address, location_id")
      .order("created_at", { ascending: false })
      .limit(200),
    supabase
      .from("appointment")
      .select("id, slot_start, status, doctor_id, service_type_id, clinic_patient_id")
      .gte("slot_start", dayStart)
      .lt("slot_start", dayEnd)
      .not("status", "in", "(CANCELLED,NO_SHOW,DOCTOR_DECLINED)")
      .limit(1000),
  ]);

  const locations: Option[] = (locRes.data ?? []).map((r) => ({
    id: r.id,
    label: r.name,
  }));
  const services: Option[] = (svcRes.data ?? [])
    .filter((r) => (r.name ?? "").trim().toUpperCase() !== "FREE")
    .map((r) => ({
      id: r.id,
      label: (r.name ?? "").replace(/^[\*\#\s]+/, "").trim(),
    }));
  const doctors: Option[] = docRes;
  const provinces: ProvinceOpt[] = (provRes.data ?? []).map((r) => ({
    code: r.code,
    name: r.name,
    fullName: r.full_name,
  }));
  const patients: PatientLite[] = (patRes.data ?? []) as PatientLite[];
  const appts: ApptLite[] = (apptRes.data ?? []) as ApptLite[];

  // docRes không còn là PostgrestResponse: listBookableDoctors đã tự nuốt lỗi
  // và trả mảng rỗng (ô chọn trống nhìn thấy được; một trang lỗi thì che mọi thứ).
  const error = locRes.error ?? svcRes.error ?? patRes.error;

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-2xl bg-danger-bg px-4 py-3 text-sm text-danger">
          Không nạp được dữ liệu: {error.message}
        </div>
      ) : null}

      <BookingHub
        locations={locations}
        services={services}
        doctors={doctors}
        provinces={provinces}
        patients={patients}
        appts={appts}
      />
    </div>
  );
}
