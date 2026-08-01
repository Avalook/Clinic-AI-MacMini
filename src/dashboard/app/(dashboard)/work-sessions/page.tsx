// Server Component — reads from Supabase via the SSR client, RLS-gated by
// the authenticated user's session.

import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";

interface WorkSessionRow {
  id: string;
  location_id: string;
  session_date: string;
  session_type: string;
  start_time: string;
  end_time: string;
  max_patients: number | null;
  clinic_location: { name: string | null } | null;
  work_session_staff: { count: number }[];
}

export const dynamic = "force-dynamic";

export default async function WorkSessionsPage() {
  // Chỉ Quản lý (NAV_ROLES) — chặn gõ thẳng URL; trang này bị sót trong đợt
  // vá requireNavAccess 05/06.
  await requireNavAccess("/work-sessions");
  const supabase = await getSupabaseServer();

  const { data, error } = await supabase
    .from("work_session")
    .select(
      // Field names verified against migration 009/010/001 (Step 1).
      "id, location_id, session_date, session_type, start_time, end_time, max_patients, " +
        "clinic_location:clinic_location ( name ), " +
        "work_session_staff ( count )",
    )
    .order("session_date", { ascending: false })
    .limit(100);

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">Ca trực</h1>
        <p className="mt-1 text-sm text-ink-muted">
          100 ca làm gần nhất, sắp theo ngày giảm dần · chỉ đọc.
        </p>
      </header>

      {error && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {/* Mobile: card list (<md). */}
      <ul className="space-y-2 md:hidden">
        {(data as WorkSessionRow[] | null)?.map((s) => (
          <li
            key={s.id}
            className="rounded-card border border-line bg-surface p-4 shadow-card"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="font-mono text-xs text-ink-soft">
                {s.session_date}
              </span>
              <span className="text-xs text-ink">{s.session_type}</span>
            </div>
            <p className="mt-1 font-mono text-xs text-ink-soft">
              {s.start_time} – {s.end_time}
            </p>
            <p className="text-xs text-ink-soft">
              {s.clinic_location?.name ?? "—"}
              {" · "}Nhân sự: {s.work_session_staff?.[0]?.count ?? 0}
              {" · "}Tối đa BN: {s.max_patients ?? "—"}
            </p>
          </li>
        ))}
        {(!data || data.length === 0) && (
          <li className="rounded-card border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted shadow-card">
            Chưa có ca làm nào.
          </li>
        )}
      </ul>

      {/* Desktop: table (≥md). */}
      <div className="hidden min-h-[180px] max-h-[88vh] overflow-x-auto overflow-y-auto rounded-card border border-line bg-surface shadow-card md:block">
        <table className="min-w-full divide-y divide-brand-100 text-sm">
          <thead className="sticky top-0 z-10 bg-brand-100 text-left text-[11px] font-semibold uppercase tracking-wide text-brand-800">
            <tr>
              <th className="px-4 py-2.5 font-semibold">Ngày</th>
              <th className="px-4 py-2.5 font-semibold">Loại ca</th>
              <th className="px-4 py-2.5 font-semibold">Giờ</th>
              <th className="px-4 py-2.5 font-semibold">Địa điểm</th>
              <th className="px-4 py-2.5 font-semibold">Nhân sự</th>
              <th className="px-4 py-2.5 font-semibold">Tối đa BN</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-100">
            {(data as WorkSessionRow[] | null)?.map((s) => (
              <tr
                key={s.id}
                className="transition-colors duration-150 hover:bg-brand-50"
              >
                <td className="px-4 py-2.5 font-mono text-xs text-ink-soft">
                  {s.session_date}
                </td>
                <td className="px-4 py-2.5 text-ink">{s.session_type}</td>
                <td className="px-4 py-2.5 font-mono text-xs text-ink-soft">
                  {s.start_time} – {s.end_time}
                </td>
                <td className="px-4 py-2.5 text-ink-soft">
                  {s.clinic_location?.name ?? "—"}
                </td>
                <td className="px-4 py-2.5 text-ink-soft">
                  {s.work_session_staff?.[0]?.count ?? 0}
                </td>
                <td className="px-4 py-2.5 text-ink-soft">
                  {s.max_patients ?? "—"}
                </td>
              </tr>
            ))}
            {(!data || data.length === 0) && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-ink-muted">
                  Chưa có ca làm nào.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
