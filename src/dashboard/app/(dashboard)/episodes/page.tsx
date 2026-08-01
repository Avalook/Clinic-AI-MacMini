// Trang "ĐÓNG ĐỢT KHÁM" (T-20260629-EPI-01) — danh sách đợt khám đang CHỜ XÁC NHẬN
// (PENDING_CLOSE): bác sĩ khám xong mà KHÔNG hẹn lần sau. CSKH xác nhận đã kết thúc
// (đóng) hoặc còn theo dõi tiếp (mở lại). Lưới an toàn chống BS quên hẹn → lượt sau bị
// tính nhẹ tải → overbook. Chỉ CSKH/Quản lý/Trưởng ca (NAV_ROLES + gate API canManageAppt).
import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import EpisodesBoard, { type EpisodeRow } from "./EpisodesBoard";

export const dynamic = "force-dynamic";

const SELECT = `
  id, opened_at, last_visit_at,
  patient:patient!clinic_patient_id ( full_name, patient_code ),
  service:service_type!service_type_id ( name )
`;

type RawRow = {
  id: string;
  opened_at: string;
  last_visit_at: string | null;
  patient: { full_name: string | null; patient_code: string | null } | null;
  service: { name: string | null } | null;
};

export default async function EpisodesPage() {
  await requireNavAccess("/episodes");
  const supabase = await getSupabaseServer();

  const { data, error } = await supabase
    .from("care_episode")
    .select(SELECT)
    .eq("status", "PENDING_CLOSE")
    .order("last_visit_at", { ascending: true, nullsFirst: true })
    .limit(300);

  const rows: EpisodeRow[] = ((data as RawRow[] | null) ?? []).map((r) => ({
    id: r.id,
    opened_at: r.opened_at,
    last_visit_at: r.last_visit_at,
    patient_name: r.patient?.full_name ?? "(không tên)",
    patient_code: r.patient?.patient_code ?? null,
    service_name: r.service?.name ?? "(dịch vụ?)",
  }));

  return (
    <div className="space-y-3">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-brand-700">
          CSKH · kết thúc theo dõi
        </p>
        <h1 className="mt-1 text-xl font-semibold text-ink">Đóng đợt khám</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Bác sĩ đã khám xong mà chưa hẹn lần sau. Xác nhận giúp: đợt đã{" "}
          <b>kết thúc</b> (đóng) hay bệnh nhân còn <b>theo dõi tiếp</b> (để mở).
        </p>
      </div>
      {error ? (
        <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">
          Lỗi tải danh sách: {error.message}
        </p>
      ) : (
        <EpisodesBoard rows={rows} />
      )}
    </div>
  );
}
