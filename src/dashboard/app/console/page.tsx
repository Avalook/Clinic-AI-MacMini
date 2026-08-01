/**
 * Bảng điều khiển của chủ sản phẩm.
 *
 * Một trang trả lời "tôi làm được gì với hệ này, và nó đang ra sao" — thay cho
 * việc mở docker ps, đọc log, gõ psql, rồi tự ghép lại trong đầu.
 *
 * KHÔNG tồn tại ở production, và bị chặn ở HAI tầng: trang này notFound(), và
 * API tự trả 404 khi APP_ENV=production. Trang liệt kê mọi tài khoản đăng nhập
 * được — trên hệ đang phục vụ bệnh nhân thì đó là một bản đồ tấn công. Một tầng
 * chặn là một tầng có thể quên.
 */

import { notFound } from "next/navigation";
import Link from "next/link";

import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip from "@/components/ui/StatusChip";
import { getSupabaseServer } from "@/lib/supabase-server";

import FeedbackBox from "./FeedbackBox";

export const metadata = { title: "Bảng điều khiển · ClinicAI" };
export const dynamic = "force-dynamic";

const API = (process.env.CLINIC_API_URL ?? "").trim().replace(/\/$/, "");

interface Overview {
  workload: { workspace: string; pending: number; in_progress: number; blocked: number }[] | null;
  accounts: { email: string; full_name: string | null; role: string | null; is_gate: boolean }[] | null;
  totals: Record<string, number> | null;
  feedback:
    | {
        id: string;
        created_at: string;
        page_url: string | null;
        role_at_time: string | null;
        comment: string;
        severity: string;
        status: string;
        image_path: string | null;
      }[]
    | null;
}

const WORKSPACE_VI: Record<string, { ten: string; man: string | null }> = {
  bang_dieu_phoi: { ten: "Tiếp nhận", man: "/reception/queue" },
  khu_bac_si: { ten: "Bàn khám", man: "/doctor/board" },
  thu_ngan_dong_luot: { ten: "Thu ngân", man: "/cashier/board" },
  khu_dieu_duong: { ten: "Điều dưỡng", man: null },
  khu_sieu_am: { ten: "Siêu âm", man: null },
  khu_xet_nghiem: { ten: "Xét nghiệm", man: null },
  khu_dat_lich: { ten: "Đặt lịch", man: null },
  bang_theo_doi_sau_kham: { ten: "Theo dõi sau khám", man: null },
  khu_lich_nhan_su: { ten: "Lịch nhân sự", man: null },
};

const SEVERITY_VI: Record<string, { label: string; tone: "blocked" | "overdue" | "assigned" | "ready" }> = {
  chan_dung: { label: "Chặn đứng", tone: "blocked" },
  lam_sai: { label: "Làm sai", tone: "overdue" },
  kho_hieu: { label: "Khó hiểu", tone: "assigned" },
  nhan_xet: { label: "Góp ý", tone: "ready" },
};

async function fetchOverview(): Promise<Overview | { error: string }> {
  if (!API) return { error: "CLINIC_API_URL chưa cấu hình" };
  const supabase = await getSupabaseServer();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) return { error: "Chưa đăng nhập" };
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  if (process.env.BACKEND_API_KEY) headers["X-API-Key"] = process.env.BACKEND_API_KEY;
  try {
    const res = await fetch(`${API}/api/v1/console/overview`, { headers, cache: "no-store" });
    if (res.status === 403) return { error: "Trang này chỉ dành cho vai Quản lý." };
    if (res.status === 404) return { error: "Bảng điều khiển bị tắt ở môi trường này." };
    if (!res.ok) return { error: `Máy chủ trả HTTP ${res.status}` };
    return (await res.json()) as Overview;
  } catch {
    return { error: "Không kết nối được máy chủ API." };
  }
}

export default async function ConsolePage() {
  if (process.env.APP_ENV === "production") notFound();

  const data = await fetchOverview();
  const failed = "error" in data;

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-5 p-6">
      <header>
        <h1 className="text-2xl font-semibold text-ink">Bảng điều khiển</h1>
        <p className="text-sm text-ink-muted">
          Toàn cảnh hệ thống, tài khoản, và chỗ báo lỗi cho tôi. Chỉ có ở môi
          trường thử — không tồn tại ở production.
        </p>
      </header>

      {failed ? (
        <div className="rounded-card border border-danger bg-danger-bg p-5">
          <p className="font-medium text-danger">Không đọc được số liệu</p>
          <p className="mt-1 text-sm text-danger">{(data as { error: string }).error}</p>
          <p className="mt-2 text-xs text-danger">
            Khung báo lỗi bên dưới vẫn dùng được.
          </p>
        </div>
      ) : null}

      {!failed && data.totals ? (
        <StatRow>
          <StatCard label="Bệnh nhân" value={data.totals.benh_nhan ?? 0} tone="brand" />
          <StatCard label="Lịch hôm nay" value={data.totals.lich_hom_nay ?? 0} tone="neutral" />
          <StatCard label="Lượt đang mở" value={data.totals.luot_dang_mo ?? 0} tone="neutral" />
          <StatCard label="Việc đang mở" value={data.totals.viec_dang_mo ?? 0} tone="warning" />
        </StatRow>
      ) : null}

      {/* Giá là thứ chặn cả mảng tiền — nói ngay ở đầu, không giấu trong bảng. */}
      {!failed && data.totals && data.totals.dich_vu_co_gia === 0 ? (
        <div className="rounded-card border border-warning bg-warning-bg px-4 py-3 text-sm text-warning">
          <strong>Bảng giá trống:</strong> {data.totals.dich_vu_co_gia}/
          {data.totals.dich_vu_tong} dịch vụ có giá. Chưa thu tiền được, báo cáo
          doanh thu sẽ bằng 0. Cần nhập bảng giá của phòng khám.
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {/* --- việc đang chờ ở từng khu --- */}
        <section className="rounded-card border border-line bg-surface shadow-card">
          <header className="border-b border-line px-5 py-3">
            <h2 className="font-medium text-ink">Việc đang chờ, theo khu</h2>
            <p className="text-xs text-ink-muted">Bấm vào tên khu để mở bảng của khu đó.</p>
          </header>
          {!failed && data.workload?.length ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-[13px] text-ink-muted">
                  <th className="px-5 py-2 font-medium">Khu</th>
                  <th className="px-3 py-2 font-medium">Chờ</th>
                  <th className="px-3 py-2 font-medium">Đang làm</th>
                  <th className="px-5 py-2 font-medium">Bị chặn</th>
                </tr>
              </thead>
              <tbody className="tabular-nums">
                {data.workload.map((w) => {
                  const meta = WORKSPACE_VI[w.workspace] ?? { ten: w.workspace, man: null };
                  return (
                    <tr key={w.workspace} className="border-b border-line last:border-0">
                      <td className="px-5 py-2">
                        {meta.man ? (
                          <Link href={meta.man} className="text-brand-700 underline">
                            {meta.ten}
                          </Link>
                        ) : (
                          <span className="text-ink">{meta.ten}</span>
                        )}
                        <span className="ml-2 text-xs text-ink-faint">{w.workspace}</span>
                      </td>
                      <td className="px-3 py-2 text-ink">{w.pending}</td>
                      <td className="px-3 py-2 text-ink-soft">{w.in_progress}</td>
                      <td className="px-5 py-2 text-ink-muted">{w.blocked}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="px-5 py-6 text-sm text-ink-muted">Chưa có số liệu.</p>
          )}
        </section>

        {/* --- tài khoản --- */}
        <section className="rounded-card border border-line bg-surface shadow-card">
          <header className="border-b border-line px-5 py-3">
            <h2 className="font-medium text-ink">Tài khoản đăng nhập được</h2>
            <p className="text-xs text-ink-muted">
              Mật khẩu chung: <code className="text-ink-soft">clinic-test-pw-123</code>.
              Mở mỗi vai ở một cửa sổ ẩn danh riêng.
            </p>
          </header>
          {!failed && data.accounts?.length ? (
            <ul className="divide-y divide-line text-sm">
              {data.accounts.map((a) => (
                <li key={a.email} className="flex items-center gap-3 px-5 py-2">
                  <span className="flex-1">
                    <span className="block text-ink">{a.full_name ?? "— cổng phòng khám —"}</span>
                    <span className="block text-xs text-ink-faint">{a.email}</span>
                  </span>
                  {a.is_gate ? (
                    <StatusChip tone="cancelled" label="cổng chung" />
                  ) : (
                    <StatusChip tone="assigned" label={a.role ?? "chưa gán vai"} />
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-5 py-6 text-sm text-ink-muted">Chưa có số liệu.</p>
          )}
        </section>
      </div>

      {/* --- công cụ vận hành --- */}
      <section className="rounded-card border border-line bg-surface p-5 shadow-card">
        <h2 className="font-medium text-ink">Theo dõi & xử lý sự cố</h2>
        <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { t: "Sức khoẻ API", d: "p50/p95, lỗi 5xx", href: "/ops/telemetry", ext: false },
            { t: "Vận hành", d: "trạng thái container", href: "/ops", ext: false },
            { t: "Uptime Kuma", d: "monitor + lịch sử", href: "http://127.0.0.1:3002", ext: true },
            { t: "Dozzle", d: "log trực tiếp", href: "http://127.0.0.1:8889", ext: true },
          ].map((x) =>
            x.ext ? (
              <a
                key={x.t}
                href={x.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-control border border-line px-4 py-3 hover:bg-surface-sunken"
              >
                <span className="block text-sm font-medium text-ink">{x.t} ↗</span>
                <span className="block text-xs text-ink-muted">{x.d}</span>
              </a>
            ) : (
              <Link
                key={x.t}
                href={x.href}
                className="rounded-control border border-line px-4 py-3 hover:bg-surface-sunken"
              >
                <span className="block text-sm font-medium text-ink">{x.t}</span>
                <span className="block text-xs text-ink-muted">{x.d}</span>
              </Link>
            ),
          )}
        </div>
      </section>

      <FeedbackBox role={null} />

      {/* --- phản hồi đã gửi --- */}
      <section className="rounded-card border border-line bg-surface shadow-card">
        <header className="border-b border-line px-5 py-3">
          <h2 className="font-medium text-ink">Đã báo</h2>
          <p className="text-xs text-ink-muted">
            Đọc lại bằng <code className="text-ink-soft">scripts/read-feedback.sh</code>
          </p>
        </header>
        {!failed && data.feedback?.length ? (
          <ul className="divide-y divide-line">
            {data.feedback.map((f) => {
              const sev = SEVERITY_VI[f.severity] ?? { label: f.severity, tone: "ready" as const };
              return (
                <li key={f.id} className="px-5 py-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusChip tone={sev.tone} label={sev.label} />
                    {f.status === "moi" ? (
                      <StatusChip tone="ready" label="chưa xử lý" />
                    ) : (
                      <StatusChip tone="completed" label={f.status} />
                    )}
                    <span className="text-xs text-ink-faint">
                      {new Date(f.created_at).toLocaleString("vi-VN")}
                      {f.page_url ? ` · ${f.page_url}` : ""}
                      {f.role_at_time ? ` · ${f.role_at_time}` : ""}
                    </span>
                  </div>
                  <p className="mt-1 text-ink">{f.comment}</p>
                  {f.image_path ? (
                    <p className="text-xs text-ink-faint">📎 {f.image_path}</p>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="px-5 py-6 text-sm text-ink-muted">
            Chưa có phản hồi nào. Dùng khung bên trên khi thấy gì đó sai.
          </p>
        )}
      </section>
    </main>
  );
}
