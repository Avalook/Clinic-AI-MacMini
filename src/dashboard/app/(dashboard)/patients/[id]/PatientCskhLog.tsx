// Nhật ký CSKH của 1 bệnh nhân (từ cskh_log, khớp theo SĐT). Timeline theo
// ngày: trạng thái đến/XN, phân loại KQ, tình trạng chăm sóc, hẹn tiếp, ghi chú.
// An toàn khi bảng chưa tồn tại (migration chưa áp) → ẩn section.

import { getSupabaseServer } from "../../../../lib/supabase-server";
import { fmtDate } from "../../../../lib/datetime";

interface CskhRow {
  id: string;
  work_date: string | null;
  slot_time: string | null;
  visit_type: string | null;
  arrived: boolean | null;
  has_test: boolean | null;
  tests: string | null;
  result_group: string | null;
  cskh_status: string | null;
  cskh_followup: string | null;
  last_cskh_date: string | null;
  cskh_by: string | null;
  note: string | null;
}

function groupColor(g: string | null): string {
  const s = (g ?? "").toLowerCase();
  if (s.includes("nhóm a")) return "bg-success-bg text-success";
  if (s.includes("nhóm b")) return "bg-warning-bg text-warning";
  if (s.includes("nhóm c")) return "bg-danger-bg text-danger";
  return "bg-surface-sunken text-ink-muted";
}

export default async function PatientCskhLog({ id }: { id: string }) {
  const supabase = await getSupabaseServer();
  const { data, error } = await supabase
    .from("cskh_log")
    .select(
      "id, work_date, slot_time, visit_type, arrived, has_test, tests, result_group, cskh_status, cskh_followup, last_cskh_date, cskh_by, note",
    )
    .eq("clinic_patient_id", id)
    .order("work_date", { ascending: false })
    .limit(30);

  // Bảng chưa tồn tại / chưa có log cho BN này → ẩn hẳn (không làm rối hồ sơ).
  if (error) return null;
  const rows = (data as CskhRow[] | null) ?? [];
  if (rows.length === 0) return null;

  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold text-ink">
        Chăm sóc khách hàng (CSKH)
        <span className="ml-2 text-sm font-normal text-ink-muted">
          ({rows.length})
        </span>
      </h3>

      <ol className="space-y-2">
        {rows.map((r) => (
          <li
            key={r.id}
            className="rounded-card border border-line bg-surface p-3 shadow-card"
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-ink">
                {r.work_date ? fmtDate(r.work_date) : "—"}
                {r.slot_time ? ` · ${r.slot_time}` : ""}
              </span>
              {r.visit_type && (
                <span className="rounded-full bg-surface-sunken px-2 py-0.5 text-xs text-ink-soft">
                  {r.visit_type}
                </span>
              )}
              <span
                className={
                  "rounded-full px-2 py-0.5 text-xs font-medium " +
                  (r.arrived
                    ? "bg-success-bg text-success"
                    : "bg-danger-bg text-danger")
                }
              >
                {r.arrived ? "Đã đến" : "Không đến"}
              </span>
              {r.result_group && (
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${groupColor(r.result_group)}`}
                >
                  {r.result_group}
                </span>
              )}
            </div>

            {(r.tests || r.has_test) && (
              <p className="mt-1.5 text-sm text-ink-soft">
                <span className="text-ink-muted">Xét nghiệm: </span>
                {r.tests ?? (r.has_test ? "Có" : "—")}
              </p>
            )}
            {r.cskh_status && (
              <p className="mt-1 text-sm text-ink-soft">
                <span className="text-ink-muted">Tình trạng CSKH: </span>
                {r.cskh_status}
              </p>
            )}
            {r.cskh_followup && (
              <p className="mt-1 text-sm text-ink-soft">
                <span className="text-ink-muted">Hẹn chăm sóc: </span>
                {r.cskh_followup}
              </p>
            )}
            {r.note && (
              <p className="mt-1 text-xs italic text-ink-muted">“{r.note}”</p>
            )}
            {(r.cskh_by || r.last_cskh_date) && (
              <p className="mt-1.5 text-xs text-ink-faint">
                {r.cskh_by ? `Người CSKH: ${r.cskh_by}` : ""}
                {r.cskh_by && r.last_cskh_date ? " · " : ""}
                {r.last_cskh_date ? `Gần nhất: ${fmtDate(r.last_cskh_date)}` : ""}
              </p>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
