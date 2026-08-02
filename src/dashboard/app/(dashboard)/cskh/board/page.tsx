// CSKH Board — Không gian làm việc CSKH (image_1 + image_2 + image_10).
// 2 cột: lịch hẹn cần xác nhận (trái) + follow-up cần gọi (phải).
// Có nút xử lý: Xác nhận lịch, Đã gọi, Đóng case.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { requireNavAccess } from "../../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../../lib/datetime";
import CskhBoard from "./CskhBoard";

export const dynamic = "force-dynamic";

export default async function CskhBoardPage() {
  await requireNavAccess("/cskh/board");
  const supabase = await getSupabaseServer();
  const { startUtc, endUtc } = vnTodayRangeUtc();

  // Lịch hẹn hôm nay cần xác nhận
  const { data: appts, error: apptErr } = await supabase
    .from("appointment")
    .select(
      `id, slot_start, status, queue_number, booking_channel,
       patient:patient!clinic_patient_id(full_name, phone_primary),
       doctor:staff!doctor_id(full_name)`,
    )
    .gte("slot_start", startUtc)
    .lt("slot_start", endUtc)
    .in("status", ["SCHEDULED", "CSKH_CONFIRMED"])
    .order("slot_start", { ascending: true })
    .limit(100);

  // Follow-up cần gọi hôm nay
  const { data: followups, error: fuErr } = await supabase
    .from("cskh_action")
    .select(
      `id, action_type, note, status, created_at,
       patient:clinic_patient_id(full_name, phone_primary)`,
    )
    .gte("created_at", startUtc)
    .lt("created_at", endUtc)
    .order("created_at", { ascending: false })
    .limit(100);

  if (apptErr || fuErr) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được dữ liệu: {apptErr?.message ?? fuErr?.message}
      </div>
    );
  }

  interface PatientRaw {
    full_name: string | null;
    phone_primary: string | null;
  }
  interface DoctorRaw {
    full_name: string | null;
  }
  type ApptRaw = Omit<(typeof appts)[number], "patient" | "doctor"> & {
    patient: PatientRaw[] | null;
    doctor: DoctorRaw[] | null;
  };
  const normAppts = (appts ?? []).map((a: ApptRaw) => ({
    ...a,
    patient: a.patient?.[0] ?? null,
    doctor: a.doctor?.[0] ?? null,
  }));

  type FuRaw = Omit<(typeof followups)[number], "patient"> & {
    patient: PatientRaw[] | null;
  };
  const normFus = (followups ?? []).map((f: FuRaw) => ({
    ...f,
    patient: f.patient?.[0] ?? null,
  }));

  return <CskhBoard appts={normAppts} followups={normFus} />;
}