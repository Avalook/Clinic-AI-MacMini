// Nhiệm vụ chăm sóc — thay thế /cskh-today + /cskh/board.
// Server component: query cskh_action + appointment data, pass to client view.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess, getClinicRole } from "../../../lib/clinic-session";
import { vnTodayRangeUtc } from "../../../lib/datetime";
import CskhTasksView, { type CskhTaskRow } from "./CskhTasksView";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Supabase join trả object HOẶC array — lấy phần tử đầu. */
function pick1<T>(v: T | T[] | null | undefined): T | null {
  if (!v) return null;
  return Array.isArray(v) ? (v[0] ?? null) : v;
}

export default async function CskhTasksPage() {
  await requireNavAccess("/cskh-tasks");
  const supabase = await getSupabaseServer();
  const { startUtc: todayStart, endUtc: todayEnd } = vnTodayRangeUtc();
  const tomorrowEnd = new Date(
    new Date(todayEnd).getTime() + DAY_MS,
  ).toISOString();
  const weekEnd = new Date(
    new Date(todayEnd).getTime() + 7 * DAY_MS,
  ).toISOString();

  // 1. CSKH Actions (công việc chăm sóc) — active tasks
  const { data: actions, error: actErr } = await supabase
    .from("cskh_action")
    .select(
      `id, source_ref, category, step, status, description, result_text,
       deadline_at, source_created_at, created_at, created_by_text, last_edited_by_text,
       clinic_patient_id,
       patient:patient!clinic_patient_id(full_name, phone_primary, patient_code)`,
    )
    .not("status", "in", "(CLOSED,CANCELLED)")
    .order("deadline_at", { ascending: true, nullsFirst: false })
    .order("source_created_at", { ascending: false })
    .limit(200);

  // 2. Lịch hẹn ngày mai cần gọi xác nhận
  const { data: tomorrowAppts, error: tmrErr } = await supabase
    .from("appointment")
    .select(
      `id, slot_start, status, booking_channel,
       patient:patient!clinic_patient_id(clinic_patient_id, full_name, phone_primary, patient_code),
       doctor:staff!doctor_id(full_name)`,
    )
    .eq("status", "SCHEDULED")
    .gte("slot_start", todayEnd)
    .lt("slot_start", tomorrowEnd)
    .order("slot_start", { ascending: true })
    .limit(200);

  // 3. Lịch hẹn tuần tới chờ xác nhận (>7 ngày trước)
  const { data: weekAppts, error: wkErr } = await supabase
    .from("appointment")
    .select(
      `id, slot_start, status, booking_channel,
       patient:patient!clinic_patient_id(clinic_patient_id, full_name, phone_primary, patient_code),
       doctor:staff!doctor_id(full_name)`,
    )
    .eq("status", "SCHEDULED")
    .gte("slot_start", tomorrowEnd)
    .lt("slot_start", weekEnd)
    .order("slot_start", { ascending: true })
    .limit(200);

  // 4. Lịch bị bác sĩ từ chối
  const { data: declinedAppts, error: decErr } = await supabase
    .from("appointment")
    .select(
      `id, slot_start, status, booking_channel,
       patient:patient!clinic_patient_id(clinic_patient_id, full_name, phone_primary, patient_code),
       doctor:staff!doctor_id(full_name)`,
    )
    .eq("status", "DOCTOR_DECLINED")
    .gte("slot_start", todayStart)
    .order("slot_start", { ascending: true })
    .limit(100);

  const error = actErr ?? tmrErr ?? wkErr ?? decErr;

  // Transform appointment data into task rows
  type ApptRaw = NonNullable<typeof tomorrowAppts>[number];
  function apptToTask(
    a: ApptRaw,
    category: string,
    step: string,
  ): CskhTaskRow {
    const pat = pick1(a.patient as Record<string, unknown> | Record<string, unknown>[] | null);
    const doc = pick1(a.doctor as Record<string, string | null> | Record<string, string | null>[] | null);
    return {
      id: `appt:${a.id}`,
      sourceType: "appointment",
      sourceId: a.id,
      category,
      step,
      status: a.status,
      description: doc?.full_name ? `BS ${doc.full_name}` : "Chưa phân bác sĩ",
      deadlineAt: a.slot_start,
      createdAt: a.slot_start,
      assignee: null,
      patientId: (pat?.clinic_patient_id as string) ?? null,
      patientName: (pat?.full_name as string) ?? "Chưa có tên",
      patientPhone: (pat?.phone_primary as string) ?? null,
      patientCode: (pat?.patient_code as string) ?? null,
      resultText: null,
    };
  }

  // Transform cskh_action data
  type ActionRaw = NonNullable<typeof actions>[number];
  function actionToTask(a: ActionRaw): CskhTaskRow {
    const pat = pick1(a.patient as Record<string, unknown> | Record<string, unknown>[] | null);
    return {
      id: a.id,
      sourceType: "cskh_action",
      sourceId: a.id,
      category: a.category ?? "CHAM_SOC",
      step: a.step ?? "PENDING",
      status: a.status ?? "OPEN",
      description: a.description ?? "",
      deadlineAt: a.deadline_at,
      createdAt: a.source_created_at ?? a.created_at,
      assignee: a.last_edited_by_text ?? a.created_by_text ?? null,
      patientId: a.clinic_patient_id,
      patientName: (pat?.full_name as string) ?? "Chưa có tên",
      patientPhone: (pat?.phone_primary as string) ?? null,
      patientCode: (pat?.patient_code as string) ?? null,
      resultText: a.result_text ?? null,
    };
  }

  const tasks: CskhTaskRow[] = [
    ...(tomorrowAppts ?? []).map((a) =>
      apptToTask(a, "NHAC_HEN", "GỌI_XÁC_NHẬN"),
    ),
    ...(weekAppts ?? []).map((a) =>
      apptToTask(a, "XAC_NHAN_LICH", "CHỜ_XÁC_NHẬN"),
    ),
    ...(declinedAppts ?? []).map((a) =>
      apptToTask(a, "PHAN_LAI_LICH", "BS_TỪ_CHỐI"),
    ),
    ...(actions ?? []).map(actionToTask),
  ];

  // Stats
  const todayDeadline = tasks.filter((t) => {
    if (!t.deadlineAt) return false;
    return t.deadlineAt >= todayStart && t.deadlineAt < todayEnd;
  }).length;
  const overSla = tasks.filter((t) => {
    if (!t.deadlineAt) return false;
    return t.deadlineAt < todayStart && t.status !== "DONE";
  }).length;
  const waitingResponse = tasks.filter(
    (t) => t.step === "CHỜ_PHẢN_HỒI" || t.status === "WAITING",
  ).length;
  const done = tasks.filter(
    (t) => t.status === "DONE" || t.status === "CLOSED",
  ).length;

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          Không đọc được dữ liệu: {error.message}
        </div>
      ) : null}
      <CskhTasksView
        tasks={tasks}
        stats={{
          todayDeadline,
          overSla,
          waitingResponse,
          done,
        }}
      />
    </div>
  );
}
