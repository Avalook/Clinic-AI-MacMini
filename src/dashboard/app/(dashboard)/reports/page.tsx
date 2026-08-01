// Báo cáo vận hành (admin-only, defense-in-depth gate giữ nguyên).
// KPI thật từ Supabase: hôm nay / ngày mai / theo bác sĩ / 30 ngày /
// 7 ngày gần nhất / nguồn đặt lịch. Read-only, KHÔNG hiển thị CCCD.
// Ô số dùng count query (head: true); chỉ fetch rows thật cho bảng theo
// bác sĩ + biểu đồ 7 ngày (giới hạn cột cần thiết).

import { redirect } from "next/navigation";
import StatCard from "../StatCard";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isOpsAdmin } from "../../../lib/roles";
import { vnTodayRangeUtc, fmtDate, VN_TZ } from "../../../lib/datetime";
import PrintReportButton from "./PrintReportButton";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

// "Đã xác nhận" cho lịch ngày mai = CSKH_CONFIRMED trở lên trong workflow
// (CSKH đã gọi hoặc đã đi xa hơn trong quy trình).
const CONFIRMED_PLUS = [
  "CSKH_CONFIRMED",
  "CONFIRMED",
  "CHECKED_IN",
  "COMPLETED",
];

interface DoctorApptRow {
  doctor_id: string | null;
  status: string;
  doctor: { full_name: string } | null;
}

interface SlotRow {
  slot_start: string;
}

interface ChannelRef {
  code: string;
  name: string;
}

function pct(n: number, total: number): string {
  if (total <= 0) return "—";
  return `${Math.round((n / total) * 100)}%`;
}

export default async function ReportsPage() {
  // Defense-in-depth: server-side gate even though Nav only renders the
  // link for admins.
  const role = await getClinicRole();
  if (!isOpsAdmin(role)) redirect("/home");

  const supabase = await getSupabaseServer();

  // Mọi mốc ngày tính theo giờ Việt Nam (UTC+7) — cùng cách với các trang khác.
  const { startUtc: dayStart, endUtc: dayEnd } = vnTodayRangeUtc();
  const tomorrowEnd = new Date(new Date(dayEnd).getTime() + DAY_MS).toISOString();
  const start7 = new Date(new Date(dayEnd).getTime() - 7 * DAY_MS).toISOString();
  const start30 = new Date(
    new Date(dayEnd).getTime() - 30 * DAY_MS,
  ).toISOString();

  const apptCount = (start: string, end: string) =>
    supabase
      .from("appointment")
      .select("*", { count: "exact", head: true })
      .gte("slot_start", start)
      .lt("slot_start", end);

  const [
    // Khối 1 — Hôm nay
    todayTotalRes,
    todayDoneRes,
    todayWaitingRes,
    todayUnconfirmedRes,
    todayNoShowRes,
    // Khối 2 — Ngày mai
    tmrTotalRes,
    tmrConfirmedRes,
    // Khối 3 — theo bác sĩ (rows hôm nay, chỉ cột cần thiết)
    byDoctorRes,
    // Khối 4 — 30 ngày
    doneThirtyRes,
    noShowThirtyRes,
    newPatientThirtyRes,
    totalThirtyRes,
    // Khối 5 — 7 ngày gần nhất (chỉ slot_start)
    weekRowsRes,
    // Khối 6 — danh mục kênh đặt lịch
    channelsRes,
  ] = await Promise.all([
    apptCount(dayStart, dayEnd),
    apptCount(dayStart, dayEnd).eq("status", "COMPLETED"),
    apptCount(dayStart, dayEnd).in("status", ["CONFIRMED", "CHECKED_IN"]),
    apptCount(dayStart, dayEnd).eq("status", "SCHEDULED"),
    apptCount(dayStart, dayEnd).eq("status", "NO_SHOW"),
    apptCount(dayEnd, tomorrowEnd),
    apptCount(dayEnd, tomorrowEnd).in("status", CONFIRMED_PLUS),
    supabase
      .from("appointment")
      .select("doctor_id, status, doctor:staff!doctor_id ( full_name )")
      .gte("slot_start", dayStart)
      .lt("slot_start", dayEnd)
      .limit(500),
    apptCount(start30, dayEnd).eq("status", "COMPLETED"),
    apptCount(start30, dayEnd).eq("status", "NO_SHOW"),
    supabase
      .from("patient")
      .select("*", { count: "exact", head: true })
      .gte("created_at", start30),
    apptCount(start30, dayEnd),
    supabase
      .from("appointment")
      .select("slot_start")
      .gte("slot_start", start7)
      .lt("slot_start", dayEnd)
      .limit(2000),
    supabase.from("booking_channel").select("code, name"),
  ]);

  // ---- Khối 1 + 2 ----
  const todayTotal = todayTotalRes.count ?? 0;
  const tmrTotal = tmrTotalRes.count ?? 0;
  const tmrConfirmed = tmrConfirmedRes.count ?? 0;

  // ---- Khối 3: gom theo bác sĩ ----
  const doctorRows = (byDoctorRes.data as unknown as DoctorApptRow[] | null) ?? [];
  const byDoctor = new Map<
    string,
    { name: string; total: number; done: number; waiting: number }
  >();
  for (const r of doctorRows) {
    const key = r.doctor_id ?? "__none__";
    const entry = byDoctor.get(key) ?? {
      name: r.doctor?.full_name ?? "Chưa phân bác sĩ",
      total: 0,
      done: 0,
      waiting: 0,
    };
    entry.total += 1;
    if (r.status === "COMPLETED") entry.done += 1;
    if (r.status === "CONFIRMED" || r.status === "CHECKED_IN")
      entry.waiting += 1;
    byDoctor.set(key, entry);
  }
  const doctorStats = [...byDoctor.values()].sort((a, b) => b.total - a.total);

  // ---- Khối 4: 30 ngày ----
  const done30 = doneThirtyRes.count ?? 0;
  const noShow30 = noShowThirtyRes.count ?? 0;
  const total30 = totalThirtyRes.count ?? 0;

  // ---- Khối 5: đếm lịch hẹn từng ngày (7 ngày gần nhất, theo ngày VN) ----
  const weekRows = (weekRowsRes.data as SlotRow[] | null) ?? [];
  const t7 = new Date(start7).getTime();
  const dayBuckets = Array.from({ length: 7 }, (_, i) => {
    const s = t7 + i * DAY_MS;
    const e = s + DAY_MS;
    const count = weekRows.filter((r) => {
      const t = new Date(r.slot_start).getTime();
      return t >= s && t < e;
    }).length;
    const d = new Date(s + DAY_MS / 2); // giữa ngày VN, an toàn khi format
    return {
      label: d.toLocaleDateString("vi-VN", {
        timeZone: VN_TZ,
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
      }),
      count,
    };
  });
  const maxDay = Math.max(1, ...dayBuckets.map((b) => b.count));

  // ---- Khối 6: nguồn đặt lịch 30 ngày (count theo từng kênh, head-only) ----
  const channels = (channelsRes.data as ChannelRef[] | null) ?? [];
  const channelCounts = await Promise.all([
    ...channels.map((c) =>
      apptCount(start30, dayEnd).eq("booking_channel", c.code),
    ),
    apptCount(start30, dayEnd).is("booking_channel", null),
  ]);
  const channelStats = channels
    .map((c, i) => ({ name: c.name, count: channelCounts[i].count ?? 0 }))
    .filter((c) => c.count > 0)
    .sort((a, b) => b.count - a.count);
  const nullChannel = channelCounts[channels.length]?.count ?? 0;
  const knownSum = channelStats.reduce((s, c) => s + c.count, 0);
  const otherChannel = Math.max(0, total30 - knownSum - nullChannel);
  const maxChannel = Math.max(
    1,
    ...channelStats.map((c) => c.count),
    nullChannel,
    otherChannel,
  );

  const queryError =
    todayTotalRes.error ??
    byDoctorRes.error ??
    weekRowsRes.error ??
    channelsRes.error;

  return (
    <main className="page-in min-w-0 space-y-6 p-4 lg:p-5">
      {/* Print CSS: khi in / lưu PDF ẩn sidebar, nav, nút bấm */}
      <style>{`
        @media print {
          [data-sidebar], nav, aside, [class*="sidebar"],
          #print-report-btn { display: none !important; }
          body { background: var(--color-surface) !important; }
          .space-y-6 > * { page-break-inside: avoid; }
        }
      `}</style>

      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Báo cáo vận hành</h1>
          <p className="mt-1 text-sm text-ink-muted">
            KPI vận hành phòng khám · {fmtDate(new Date())} · chỉ đọc
          </p>
        </div>
        <PrintReportButton />
      </header>

      {queryError && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {queryError.message}
        </div>
      )}

      {/* Khối 1 — Hôm nay */}
      <Section title="Hôm nay">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Tổng lịch hẹn" value={todayTotal} />
          <StatCard label="Đã khám xong" value={todayDoneRes.count ?? 0} />
          <StatCard label="Đang chờ" value={todayWaitingRes.count ?? 0} />
          <StatCard
            label="Chưa xác nhận"
            value={todayUnconfirmedRes.count ?? 0}
          />
          <StatCard label="Không đến" value={todayNoShowRes.count ?? 0} />
        </div>
      </Section>

      {/* Khối 2 — Ngày mai: CSKH đã gọi xác nhận đủ chưa */}
      <Section title="Ngày mai">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard label="Tổng lịch hẹn" value={tmrTotal} />
          <StatCard
            label="Đã xác nhận (CSKH gọi)"
            value={`${tmrConfirmed}/${tmrTotal}`}
          />
          <StatCard
            label="Tỷ lệ xác nhận"
            value={pct(tmrConfirmed, tmrTotal)}
          />
        </div>
      </Section>

      {/* Khối 3 — Theo bác sĩ (hôm nay) */}
      <Section title="Theo bác sĩ (hôm nay)">
        <div className="overflow-x-auto rounded-card border border-line bg-surface shadow-card">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-line bg-surface-muted text-left text-xs text-ink-muted">
                <th className="px-4 py-2 font-medium">Bác sĩ</th>
                <th className="px-4 py-2 text-right font-medium">Số ca</th>
                <th className="px-4 py-2 text-right font-medium">
                  Đã khám xong
                </th>
                <th className="px-4 py-2 text-right font-medium">Đang chờ</th>
              </tr>
            </thead>
            <tbody>
              {doctorStats.length === 0 ? (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-6 text-center text-ink-muted"
                  >
                    Hôm nay chưa có lịch hẹn.
                  </td>
                </tr>
              ) : (
                doctorStats.map((d) => (
                  <tr
                    key={d.name}
                    className="border-b border-surface-sunken last:border-b-0"
                  >
                    <td className="px-4 py-2 text-ink">{d.name}</td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.total}
                    </td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.done}
                    </td>
                    <td className="px-4 py-2 text-right text-ink">
                      {d.waiting}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Section>

      {/* Khối 4 — 30 ngày */}
      <Section title="30 ngày qua">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Lượt khám xong" value={done30} />
          <StatCard label="Không đến (no-show)" value={noShow30} />
          <StatCard
            label="Tỷ lệ no-show"
            value={pct(noShow30, done30 + noShow30)}
          />
          <StatCard
            label="Bệnh nhân mới"
            value={newPatientThirtyRes.count ?? 0}
          />
        </div>
      </Section>

      {/* Khối 5 — 7 ngày gần nhất: bar CSS thuần */}
      <Section title="Lịch hẹn 7 ngày gần nhất">
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          <div className="space-y-2">
            {dayBuckets.map((b) => (
              <div key={b.label} className="flex items-center gap-3 text-sm">
                <span className="w-24 shrink-0 text-xs text-ink-muted">
                  {b.label}
                </span>
                <div className="h-4 flex-1 rounded bg-surface-sunken">
                  <div
                    className="h-4 rounded bg-ink"
                    style={{ width: `${(b.count / maxDay) * 100}%` }}
                  />
                </div>
                <span className="w-8 shrink-0 text-right text-ink">
                  {b.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* Khối 6 — Nguồn đặt lịch (booking_channel, 30 ngày) */}
      <Section title="Nguồn đặt lịch (30 ngày)">
        <div className="rounded-card border border-line bg-surface p-5 shadow-card">
          {channelStats.length === 0 && nullChannel === 0 && otherChannel === 0 ? (
            <p className="text-sm text-ink-muted">
              Chưa có lịch hẹn trong 30 ngày qua.
            </p>
          ) : (
            <div className="space-y-2">
              {[
                ...channelStats,
                ...(otherChannel > 0
                  ? [{ name: "Kênh khác", count: otherChannel }]
                  : []),
                ...(nullChannel > 0
                  ? [{ name: "Không ghi nhận", count: nullChannel }]
                  : []),
              ].map((c) => (
                <div key={c.name} className="flex items-center gap-3 text-sm">
                  <span className="w-44 shrink-0 truncate text-xs text-ink-muted">
                    {c.name}
                  </span>
                  <div className="h-4 flex-1 rounded bg-surface-sunken">
                    <div
                      className="h-4 rounded bg-ink"
                      style={{ width: `${(c.count / maxChannel) * 100}%` }}
                    />
                  </div>
                  <span className="w-8 shrink-0 text-right text-ink">
                    {c.count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </Section>

      <p className="text-xs text-ink-muted">
        Chưa gồm doanh thu — chờ module thu ngân.
      </p>
    </main>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <h2 className="font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}
