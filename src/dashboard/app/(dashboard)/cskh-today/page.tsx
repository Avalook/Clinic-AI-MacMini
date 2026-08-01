// "Cần làm hôm nay" (CSKH/Quản lý) — danh sách tự sinh từ dữ liệu vận hành.
// Màn chỉ trình bày các dữ liệu CSKH đã được phép thấy; xử lý xác nhận/phân lại
// lịch vẫn thuộc /tasks, còn ghi nhật ký cuộc gọi giữ nguyên API hiện có.

import { fetchFromBackend } from "../../../lib/backend-proxy";
import { requireNavAccess } from "../../../lib/clinic-session";
import { fmtDate, nowMs, VN_TZ, vnTodayRangeUtc } from "../../../lib/datetime";
import { labReleaseDecision } from "../../../lib/lab-release";
import { getSupabaseServer } from "../../../lib/supabase-server";
import type { FollowupBucket } from "./CskhFollowupList";
import CskhTodayWorkspace from "./CskhTodayWorkspace";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;
const FOLLOWUP_TIERS = [2, 10, 20, 30] as const;

interface PatientLite {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
}

interface ApptRow {
  id: string;
  slot_start: string;
  patient: PatientLite | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}

interface LabRow {
  lab_result_id: string;
  test_name: string | null;
  triage_group: string | null;
  is_finalized: boolean;
  result_received_at: string | null;
  patient: PatientLite | null;
}

interface TaiKham {
  ngay: string;
  xn: string[];
  ghi_chu: string;
}

interface RecallRow {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  tai_kham: TaiKham;
}

interface RecallProjection {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  due_date: string;
  repeat_tests: string[];
  instruction: string;
}

const XN_LABEL: Record<string, string> = {
  HM: "Hormone",
  SH: "Sinh hóa",
  SA: "Siêu âm",
  DXA: "DXA",
  PS: "Pap smear",
};

function vnYmd(): string {
  return new Date(nowMs()).toLocaleDateString("en-CA", { timeZone: VN_TZ });
}

function buildFollowupBuckets(
  recalls: RecallRow[],
  todayYmd: string,
): FollowupBucket[] {
  const tiersDesc = [...FOLLOWUP_TIERS].sort((a, b) => b - a);
  const buckets: FollowupBucket[] = tiersDesc.map((tier) => ({
    tier,
    label: `Quá hạn ≥ ${tier} ngày`,
    rows: [],
  }));

  for (const recall of recalls) {
    const overdueDays = Math.floor(
      (Date.parse(todayYmd) - Date.parse(recall.tai_kham.ngay)) / DAY_MS,
    );
    if (overdueDays < FOLLOWUP_TIERS[0]) continue;
    const bucket = buckets.find((entry) => overdueDays >= entry.tier);
    if (bucket) {
      bucket.rows.push({
        clinic_patient_id: recall.clinic_patient_id,
        full_name: recall.full_name,
        phone_primary: recall.phone_primary,
        ngay: recall.tai_kham.ngay,
        overdue_days: overdueDays,
      });
    }
  }
  return buckets;
}

export default async function CskhTodayPage() {
  await requireNavAccess("/cskh-today");
  const supabase = await getSupabaseServer();
  const { startUtc: todayStart, endUtc: todayEnd } = vnTodayRangeUtc();
  const tomorrowEnd = new Date(
    new Date(todayEnd).getTime() + DAY_MS,
  ).toISOString();
  const appointmentSelect = `
    id, slot_start,
    patient:patient!clinic_patient_id ( clinic_patient_id, full_name, phone_primary ),
    doctor:staff!doctor_id ( full_name ),
    service:service_type!service_type_id ( name )
  `;

  const [tomorrowRes, declinedRes, recallProjection, labRes] = await Promise.all([
    supabase
      .from("appointment")
      .select(appointmentSelect)
      .eq("status", "SCHEDULED")
      .gte("slot_start", todayEnd)
      .lt("slot_start", tomorrowEnd)
      .order("slot_start", { ascending: true })
      .limit(200),
    supabase
      .from("appointment")
      .select(appointmentSelect)
      .eq("status", "DOCTOR_DECLINED")
      .gte("slot_start", todayStart)
      .order("slot_start", { ascending: true })
      .limit(200),
    // FastAPI projects only the instruction CSKH needs; the SOAP source stays
    // behind the backend boundary.
    fetchFromBackend<RecallProjection[]>("/api/v1/cskh/recalls"),
    supabase
      .from("lab_result")
      .select(
        `lab_result_id, test_name, triage_group, is_finalized, result_received_at,
         patient:patient!clinic_patient_id ( clinic_patient_id, full_name, phone_primary )`,
      )
      .gte("result_received_at", todayStart)
      .lt("result_received_at", todayEnd)
      .order("result_received_at", { ascending: false })
      .limit(200),
  ]);

  const error = tomorrowRes.error ?? declinedRes.error ?? labRes.error;
  const tomorrow = (tomorrowRes.data as ApptRow[] | null) ?? [];
  const declined = (declinedRes.data as ApptRow[] | null) ?? [];
  const labs = (labRes.data as LabRow[] | null) ?? [];
  const recalls: RecallRow[] = (recallProjection ?? []).map((row) => ({
    clinic_patient_id: row.clinic_patient_id,
    full_name: row.full_name,
    phone_primary: row.phone_primary,
    tai_kham: {
      ngay: row.due_date,
      xn: row.repeat_tests,
      ghi_chu: row.instruction,
    },
  }));
  const followupBuckets = buildFollowupBuckets(recalls, vnYmd());

  return (
    <div className="space-y-3">
      {error ? (
        <div className="rounded-control bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      ) : null}
      {recallProjection === null ? (
        <div className="rounded-control bg-warning-bg px-3 py-2 text-sm text-warning">
          Không tải được danh sách tái khám từ máy chủ. Các phần khác vẫn hoạt động;
          vui lòng báo quản trị viên nếu cảnh báo này còn xuất hiện.
        </div>
      ) : null}
      <CskhTodayWorkspace
        todayLabel={fmtDate(new Date())}
        tomorrow={tomorrow.map((appointment) => ({
          id: appointment.id,
          slotStart: appointment.slot_start,
          patient: appointment.patient
            ? {
                id: appointment.patient.clinic_patient_id,
                fullName: appointment.patient.full_name,
                phone: appointment.patient.phone_primary,
              }
            : null,
          doctorName: appointment.doctor?.full_name ?? null,
          serviceName: appointment.service?.name ?? null,
        }))}
        declined={declined.map((appointment) => ({
          id: appointment.id,
          slotStart: appointment.slot_start,
          patient: appointment.patient
            ? {
                id: appointment.patient.clinic_patient_id,
                fullName: appointment.patient.full_name,
                phone: appointment.patient.phone_primary,
              }
            : null,
          doctorName: appointment.doctor?.full_name ?? null,
          serviceName: appointment.service?.name ?? null,
        }))}
        recalls={recalls.map((recall) => ({
          patientId: recall.clinic_patient_id,
          fullName: recall.full_name,
          phone: recall.phone_primary,
          dueDate: recall.tai_kham.ngay,
          repeatTests: recall.tai_kham.xn.map((code) => XN_LABEL[code] ?? code),
          instruction: recall.tai_kham.ghi_chu,
        }))}
        followups={followupBuckets.flatMap((bucket) =>
          bucket.rows.map((row) => ({
            patientId: row.clinic_patient_id,
            fullName: row.full_name,
            phone: row.phone_primary,
            dueDate: row.ngay,
            overdueDays: row.overdue_days,
            tierLabel: bucket.label,
          })),
        )}
        labs={labs.map((lab) => {
          const release = labReleaseDecision(lab.triage_group, lab.is_finalized);
          return {
            id: lab.lab_result_id,
            testName: lab.test_name,
            receivedAt: lab.result_received_at,
            patient: lab.patient
              ? {
                  id: lab.patient.clinic_patient_id,
                  fullName: lab.patient.full_name,
                  phone: lab.patient.phone_primary,
                }
              : null,
            releaseAllowed: release.allowed,
            releaseLabel: release.label,
          };
        })}
      />
    </div>
  );
}
