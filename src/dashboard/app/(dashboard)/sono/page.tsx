// Màn ĐD siêu âm (T-DASH-DDSA-A01):
//   (a) Hàng đợi BN sắp khám SA — tích bắt đầu → hoàn tất → hủy (đổi status dòng SA).
//   (b) Hàng đợi XN 3 trạng thái — lấy mẫu / gửi lab / có KQ, mỗi ô nút có/chưa.
// Đọc qua getSupabaseServer() (RLS SELECT service_log_select_authenticated); ghi tiến
// trình qua route service-role /api/sono. KHÔNG đụng lab_result, KHÔNG ghi visit.status.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import SonoView, { type SonoRow } from "./SonoView";

export const dynamic = "force-dynamic";

const SELECT = `
  id, kind, service_name_raw, status, result_text,
  started_at, sent_to_lab_at, finished_at, created_at,
  patient:patient!clinic_patient_id ( full_name, patient_code )
`;

export default async function SonoPage() {
  await requireNavAccess("/sono");
  const supabase = await getSupabaseServer();

  const [saRes, xnRes] = await Promise.all([
    supabase
      .from("service_log")
      .select(SELECT)
      .eq("kind", "SA")
      .order("created_at", { ascending: true })
      .limit(200),
    supabase
      .from("service_log")
      .select(SELECT)
      .eq("kind", "XN")
      .order("created_at", { ascending: true })
      .limit(200),
  ]);

  const sa = (saRes.data as SonoRow[] | null) ?? [];
  const xn = (xnRes.data as SonoRow[] | null) ?? [];
  const error = saRes.error ?? xnRes.error;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-ink">ĐD siêu âm</h1>
        <p className="text-sm text-ink-muted">
          Hàng đợi BN siêu âm (bắt đầu → hoàn tất → hủy) và hàng đợi xét nghiệm 3
          trạng thái (lấy mẫu → gửi lab → có KQ). In phiếu kết quả từ từng dòng.
        </p>
      </header>

      {error ? (
        <div className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {error.message}
        </div>
      ) : (
        <SonoView sa={sa} xn={xn} />
      )}
    </div>
  );
}
