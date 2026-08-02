// Duyệt kết quả — Doctor duyệt kết quả XN (image_9 + image_3).
// Hàng đợi kết quả chờ duyệt: xem chi tiết, ký duyệt / trả lại chỉnh sửa.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole, requireNavAccess } from "../../../lib/clinic-session";
import { canReviewLabResult } from "../../../lib/roles";
import ResultReviewBoard from "./ResultReviewBoard";

export const dynamic = "force-dynamic";

export default async function ResultReviewPage() {
  await requireNavAccess("/result-review");
  const supabase = await getSupabaseServer();
  // Quản lý / Trưởng ca mở được màn này để theo dõi hàng đợi, nhưng chữ ký trên
  // kết quả là của bác sĩ — xem canReviewLabResult.
  const canReview = canReviewLabResult(await getClinicRole());

  const { data: results, error } = await supabase
    .from("lab_result")
    .select(
      `lab_result_id, clinic_patient_id, test_code, test_name, result_value,
       result_numeric, result_unit, reference_range_low, reference_range_high,
       flag, triage_group, requires_doctor_review, is_finalized,
       result_received_at,
       patient:clinic_patient_id(full_name, phone_primary)`,
    )
    .eq("requires_doctor_review", true)
    .order("result_received_at", { ascending: false })
    .limit(100);

  if (error) {
    return (
      <div className="p-6 text-sm text-danger">
        Không đọc được kết quả: {error.message}
      </div>
    );
  }

  interface PatientRaw {
    full_name: string | null;
    phone_primary: string | null;
  }
  type Raw = Omit<(typeof results)[number], "patient"> & {
    patient: PatientRaw[] | null;
  };
  const normalized = (results ?? []).map((r: Raw) => ({
    ...r,
    patient: r.patient?.[0] ?? null,
  }));

  // Kết quả đã trả lại vẫn nằm trong hàng đợi (cổng an toàn không mở ra vì bác
  // sĩ từ chối). Không đánh dấu thì người trực sau sẽ trả lại lần thứ hai cho
  // cùng một việc đang mở.
  const { data: openFixes } = await supabase
    .from("staff_task")
    .select("source_id")
    .eq("task_type", "LAB_RESULT_FIX")
    .eq("source_type", "LAB_RESULT")
    .in("status", ["PENDING", "IN_PROGRESS"])
    .limit(200);

  const sentBackIds = (openFixes ?? [])
    .map((t: { source_id: string | null }) => t.source_id)
    .filter((id): id is string => Boolean(id));

  return (
    <ResultReviewBoard
      results={normalized}
      sentBackIds={sentBackIds}
      canReview={canReview}
    />
  );
}
