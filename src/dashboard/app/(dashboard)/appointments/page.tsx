// Đặt lịch CSKH — Hub đặt lịch hẹn sử dụng dữ liệu thật từ DB.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole, requireNavAccess } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import BookingHub, {
  type PatientLite,
  type ApptLite,
} from "./BookingHub";
import type { Option, ProvinceOpt } from "../patients/new/NewPatientForm";

export const dynamic = "force-dynamic";

export default async function AppointmentsPage() {
  await requireNavAccess("/appointments");
  const role = await getClinicRole();
  const supabase = await getSupabaseServer();
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();

  // Load real locations, services, doctors, provinces, patients, and today's appointments
  const [locRes, svcRes, docRes, provRes, patRes, apptRes] = await Promise.all([
    supabase.from("clinic_location").select("id, name").order("name"),
    supabase.from("service_type").select("id, name").order("name"),
    supabase
      .from("staff")
      .select("id, full_name")
      .in("primary_department", ["DOCTOR", "ULTRASOUND_DOCTOR"])
      .eq("is_active", true)
      .order("full_name"),
    supabase.from("province").select("code, name, full_name").order("name"),
    supabase
      .from("patient")
      .select("clinic_patient_id, patient_code, full_name, phone_primary, date_of_birth, gender, address")
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
  const doctors: Option[] = (docRes.data ?? []).map((r) => ({
    id: r.id,
    label: r.full_name,
  }));
  const provinces: ProvinceOpt[] = (provRes.data ?? []).map((r) => ({
    code: r.code,
    name: r.name,
    fullName: r.full_name,
  }));
  const patients: PatientLite[] = (patRes.data ?? []) as PatientLite[];
  const appts: ApptLite[] = (apptRes.data ?? []) as ApptLite[];

  const error = locRes.error ?? svcRes.error ?? docRes.error ?? patRes.error;

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
