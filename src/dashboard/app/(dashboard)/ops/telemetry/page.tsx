/**
 * Sức khoẻ API — response times and recent failures.
 *
 * /ops already answers "are the containers up". This answers "is it working",
 * which is a different question: a front desk waiting eight seconds for a queue
 * has a perfectly healthy container.
 *
 * Numbers come from a ring buffer in the API process, so they reset on restart
 * and describe one process. That limit is printed on the screen rather than
 * left for someone to discover after trusting a graph.
 */

import StatCard, { StatRow } from "@/components/ui/StatCard";
import { fetchTelemetry } from "@/lib/telemetry-server";

export const metadata = { title: "Sức khoẻ API · ClinicAI" };
export const dynamic = "force-dynamic";

const WINDOW_MINUTES = 15;

function ms(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(2)}s` : `${v.toFixed(0)}ms`;
}

/** Slow enough to be felt, slow enough to be a bug. */
function timingTone(p95: number, threshold: number): string {
  if (p95 >= threshold) return "text-danger";
  if (p95 >= threshold / 2) return "text-warning";
  return "text-ink";
}

export default async function TelemetryPage() {
  const result = await fetchTelemetry(WINDOW_MINUTES * 60);

  return (
    <main className="page-in flex flex-col gap-5 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Sức khoẻ API</h1>
        <p className="text-sm text-ink-muted">
          Thời gian phản hồi và lỗi gần đây — {WINDOW_MINUTES} phút vừa qua.
        </p>
      </header>

      {!result.ok ? (
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không đọc được số liệu</p>
          <p className="mt-1 text-sm text-danger">
            {result.reason === "forbidden"
              ? "Màn này chỉ dành cho vai trò Quản lý."
              : result.reason === "no-session"
                ? "Phiên đăng nhập đã hết hạn."
                : "Không kết nối được máy chủ API. Số 0 ở đây KHÔNG có nghĩa là hệ thống khoẻ."}
            {result.detail ? ` (${result.detail})` : ""}
          </p>
        </div>
      ) : (
        <>
          <StatRow>
            <StatCard label="Số request" value={result.data.total} tone="brand" />
            <StatCard label="p50" value={ms(result.data.p50_ms)} tone="neutral" />
            <StatCard
              label="p95"
              value={ms(result.data.p95_ms)}
              tone={result.data.p95_ms >= result.data.slow_threshold_ms ? "danger" : "neutral"}
            />
            <StatCard
              label="Lỗi 5xx"
              value={result.data.statuses["5xx"] ?? 0}
              tone={(result.data.statuses["5xx"] ?? 0) > 0 ? "danger" : "success"}
            />
          </StatRow>

          <section className="rounded-card border border-line bg-surface shadow-card">
            <header className="flex items-baseline justify-between border-b border-line px-5 py-3">
              <h2 className="font-medium text-ink">Chậm nhất theo p95</h2>
              <span className="text-xs text-ink-muted">
                Sắp theo đuôi, không theo trung bình — đuôi mới là cái người dùng
                cảm thấy.
              </span>
            </header>
            {result.data.routes.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-ink-muted">
                Chưa có request nào trong {WINDOW_MINUTES} phút qua.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-[13px] text-ink-muted">
                    <th className="px-5 py-2 font-medium">Route</th>
                    <th className="px-3 py-2 font-medium">Số lần</th>
                    <th className="px-3 py-2 font-medium">p50</th>
                    <th className="px-3 py-2 font-medium">p95</th>
                    <th className="px-5 py-2 font-medium">Chậm nhất</th>
                  </tr>
                </thead>
                <tbody className="tabular-nums">
                  {result.data.routes.map((r) => (
                    <tr
                      key={`${r.method} ${r.route}`}
                      className="border-b border-line last:border-0"
                    >
                      <td className="px-5 py-2">
                        <span className="mr-2 text-xs font-medium text-ink-muted">
                          {r.method}
                        </span>
                        <span className="text-ink">{r.route}</span>
                      </td>
                      <td className="px-3 py-2 text-ink-muted">{r.count}</td>
                      <td className="px-3 py-2 text-ink-soft">{ms(r.p50_ms)}</td>
                      <td
                        className={`px-3 py-2 font-medium ${timingTone(r.p95_ms, result.data.slow_threshold_ms)}`}
                      >
                        {ms(r.p95_ms)}
                      </td>
                      <td className="px-5 py-2 text-ink-muted">{ms(r.max_ms)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="rounded-card border border-line bg-surface shadow-card">
            <header className="border-b border-line px-5 py-3">
              <h2 className="font-medium text-ink">Lỗi 5xx gần đây</h2>
              <p className="text-xs text-ink-muted">
                Chỉ 5xx. Lỗi 4xx là hệ thống từ chối đúng luật — đưa vào đây thì
                danh sách đầy những lần từ chối hợp lệ và không ai đọc nữa.
              </p>
            </header>
            {result.data.errors.length === 0 ? (
              <p className="px-5 py-8 text-center text-sm text-ink-muted">
                Không có lỗi máy chủ nào trong bộ đệm.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {result.data.errors.map((e, i) => (
                  <li key={`${e.at}-${i}`} className="px-5 py-3">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <span className="font-medium text-danger">{e.status}</span>
                      <span className="text-xs text-ink-muted">{e.method}</span>
                      <span className="text-sm text-ink">{e.route}</span>
                      <span className="ml-auto text-xs text-ink-faint tabular-nums">
                        {new Date(e.at * 1000).toLocaleTimeString("vi-VN")}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      <span className="font-medium">{e.kind}</span>
                      {e.detail ? ` — ${e.detail}` : ""}
                    </p>
                    {e.request_id ? (
                      <p className="text-xs text-ink-faint">
                        request_id {e.request_id} — dùng mã này để tra trong log
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* The limit belongs on the screen, not in a doc nobody opens. */}
          <p className="text-xs text-ink-faint">
            Số liệu nằm trong bộ nhớ tiến trình API: mất khi khởi động lại, và
            chỉ mô tả một tiến trình. Không thay thế hệ giám sát thật khi chạy
            nhiều bản sao. Ngưỡng &ldquo;chậm&rdquo; ={" "}
            {ms(result.data.slow_threshold_ms)}.
          </p>
        </>
      )}
    </main>
  );
}
