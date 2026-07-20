// "Hàng đợi xét nghiệm" (ĐD/KTV). Chờ kết quả = lab_result chưa có
// result_value lẫn external_ref. Đã trả = đã có 1 trong 2. Đọc qua RLS.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import LabQueueView, { type LabRow } from "./LabQueueView";

export const dynamic = "force-dynamic";

const SELECT = `
  lab_result_id, test_name, result_value, external_ref, lab_provider,
  result_received_at, created_at,
  patient:patient!clinic_patient_id ( full_name, patient_code, phone_primary )
`;

export default async function LabQueuePage() {
  await requireNavAccess("/lab-queue");
  const supabase = await getSupabaseServer();

  const [pendingRes, doneRes] = await Promise.all([
    supabase
      .from("lab_result")
      .select(SELECT)
      .is("result_value", null)
      .is("external_ref", null)
      .order("created_at", { ascending: true })
      .limit(200),
    supabase
      .from("lab_result")
      .select(SELECT)
      .or("result_value.not.is.null,external_ref.not.is.null")
      .order("result_received_at", { ascending: false })
      .limit(50),
  ]);

  const pending = (pendingRes.data as LabRow[] | null) ?? [];
  const done = (doneRes.data as LabRow[] | null) ?? [];
  const error = pendingRes.error ?? doneRes.error;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">
          Hàng đợi xét nghiệm
        </h1>
        <p className="text-sm text-[#888888]">
          Bác sĩ chỉ định → đính tóm tắt + link phiếu (PDF/Drive) + nhà cung cấp
          lab. Bác sĩ xem lại ở mục VI hồ sơ khám.
        </p>
      </header>

      {error ? (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      ) : (
        <LabQueueView pending={pending} done={done} />
      )}
    </div>
  );
}
