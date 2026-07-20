// "Hàng đợi dịch vụ / thủ thuật" (ĐD/KTV). Đang làm/chờ = finished_at NULL;
// đã hoàn tất = finished_at có giá trị. Đọc qua Supabase RLS.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import ServiceQueueView, { type ServiceRow } from "./ServiceQueueView";

export const dynamic = "force-dynamic";

const SELECT = `
  id, service_name_raw, status, result_text, performer_text,
  started_at, finished_at, created_at,
  patient:patient!clinic_patient_id ( full_name, patient_code )
`;

export default async function ServiceQueuePage() {
  await requireNavAccess("/service-queue");
  const supabase = await getSupabaseServer();

  const [activeRes, doneRes] = await Promise.all([
    supabase
      .from("service_log")
      .select(SELECT)
      .is("finished_at", null)
      .order("created_at", { ascending: true })
      .limit(200),
    supabase
      .from("service_log")
      .select(SELECT)
      .not("finished_at", "is", null)
      .order("finished_at", { ascending: false })
      .limit(50),
  ]);

  const active = (activeRes.data as ServiceRow[] | null) ?? [];
  const done = (doneRes.data as ServiceRow[] | null) ?? [];
  const error = activeRes.error ?? doneRes.error;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">
          Hàng đợi dịch vụ / thủ thuật
        </h1>
        <p className="text-sm text-[#888888]">
          Tạo việc → Bắt đầu (ghi giờ) → Hoàn tất (ghi giờ + kết quả).
        </p>
      </header>

      {error ? (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      ) : (
        <ServiceQueueView active={active} done={done} />
      )}
    </div>
  );
}
