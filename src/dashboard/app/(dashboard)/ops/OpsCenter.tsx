"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  FileClock,
  Gauge,
  HardDrive,
  RefreshCw,
  ScrollText,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  emptyOpsSummary,
  normalizeOpsPayload,
  safeHttpUrl,
  type FindingState,
  type OpsLinks,
  type OpsSummary,
  type ServiceState,
} from "../../../lib/ops-summary";

const SERVICE_LABELS: Record<string, string> = {
  api: "FastAPI",
  dashboard: "Dashboard",
  caddy: "Caddy ingress",
  worker: "Worker",
  "notification-relay": "Notification relay",
  rabbitmq: "RabbitMQ",
  dozzle: "Dozzle",
  "uptime-kuma": "Uptime Kuma",
};

const STATE_STYLE = {
  healthy: "border-success bg-success-bg text-success",
  degraded: "border-warning bg-warning-bg text-warning",
  critical: "border-danger bg-danger-bg text-danger",
  down: "border-danger bg-danger-bg text-danger",
  unknown: "border-line bg-surface-muted text-ink-muted",
  disabled: "border-line bg-surface-sunken text-ink-faint",
  fresh: "border-success bg-success-bg text-success",
  stale: "border-warning bg-warning-bg text-warning",
  expired: "border-danger bg-danger-bg text-danger",
  invalid: "border-danger bg-danger-bg text-danger",
  good: "border-success bg-success-bg text-success",
  warning: "border-warning bg-warning-bg text-warning",
} as const;

function StateIcon({ state }: { state: string }) {
  if (["healthy", "fresh", "good"].includes(state)) {
    return <CheckCircle2 size={17} aria-hidden />;
  }
  if (["critical", "down", "expired", "invalid"].includes(state)) {
    return <XCircle size={17} aria-hidden />;
  }
  return <AlertTriangle size={17} aria-hidden />;
}

function Badge({ state, text }: { state: keyof typeof STATE_STYLE; text: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-xs font-medium ${STATE_STYLE[state]}`}>
      <StateIcon state={state} />
      {text}
    </span>
  );
}

function fmtNumber(value: number | null, suffix = "") {
  return value === null ? "—" : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function fmtBytes(value: number | null) {
  if (value === null) return "—";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function ServiceCard({ label, state, latency, restarts }: { label: string; state: ServiceState; latency?: number | null; restarts?: number }) {
  return (
    <article className="rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-ink">{label}</p>
          <p className="mt-1 text-xs text-ink-muted">
            {latency !== undefined ? `Độ trễ ${fmtNumber(latency, " ms")}` : `Restart ${restarts ?? 0}`}
          </p>
        </div>
        <Badge state={state} text={state === "healthy" ? "Ổn định" : state === "disabled" ? "Đang tắt" : state === "down" ? "Mất kết nối" : "Chưa rõ"} />
      </div>
    </article>
  );
}

function FindingCard({ item }: { item: { label: string; detail: string; state: FindingState } }) {
  return (
    <li className="flex items-start gap-3 rounded-control border border-line bg-surface p-3">
      <span className={`mt-0.5 rounded-chip border p-1.5 ${STATE_STYLE[item.state]}`}>
        <StateIcon state={item.state} />
      </span>
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink">{item.label}</p>
        <p className="mt-0.5 text-xs leading-5 text-ink-muted">{item.detail}</p>
      </div>
    </li>
  );
}

function ToolLink({ href, title, detail, icon }: { href: string | null; title: string; detail: string; icon: React.ReactNode }) {
  if (!href) {
    return (
      <div className="flex items-center gap-3 rounded-card border border-dashed border-line bg-surface-muted p-4 text-ink-muted">
        {icon}<div><p className="text-sm font-medium">{title}</p><p className="text-xs">Chưa cấu hình đường dẫn an toàn.</p></div>
      </div>
    );
  }
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50">
      <span className="rounded-control bg-brand-50 p-2 text-brand-600">{icon}</span>
      <div className="min-w-0 flex-1"><p className="text-sm font-medium text-ink">{title}</p><p className="text-xs text-ink-muted">{detail}</p></div>
      <ExternalLink size={16} className="text-ink-faint group-hover:text-brand-600" aria-hidden />
    </a>
  );
}

export default function OpsCenter() {
  const [summary, setSummary] = useState<OpsSummary>(emptyOpsSummary());
  const [links, setLinks] = useState<OpsLinks>({ logs: null, uptime: null, sentry: null });
  const [loading, setLoading] = useState(true);
  const [sourceUnavailable, setSourceUnavailable] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/ops/summary", { cache: "no-store" });
      if (!response.ok) throw new Error("ops unavailable");
      const payload = (await response.json()) as Record<string, unknown>;
      setSummary(normalizeOpsPayload(payload));
      const rawLinks = payload.links && typeof payload.links === "object" ? payload.links as Record<string, unknown> : {};
      setLinks({
        logs: safeHttpUrl(typeof rawLinks.logs === "string" ? rawLinks.logs : null),
        uptime: safeHttpUrl(typeof rawLinks.uptime === "string" ? rawLinks.uptime : null),
        sentry: safeHttpUrl(typeof rawLinks.sentry === "string" ? rawLinks.sentry : null),
      });
      setSourceUnavailable(payload.sourceUnavailable === true);
    } catch {
      setSummary(emptyOpsSummary());
      setSourceUnavailable(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initial = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 30_000);
    const onVisible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearTimeout(initial);
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  const overallText = summary.overall === "healthy" ? "Hệ thống ổn định" : summary.overall === "critical" ? "Cần xử lý ngay" : "Có hạng mục cần kiểm tra";
  const overallStyle = STATE_STYLE[summary.overall];

  return (
    <main className="page-in min-w-0 space-y-6 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><Gauge size={22} className="text-brand-600" /><h1 className="text-xl font-semibold text-ink lg:text-2xl">Vận hành hệ thống</h1></div>
          <p className="mt-1 text-sm text-ink-muted">Một cửa theo dõi hiệu năng, backup và bảo mật · chỉ dành cho Quản lý</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading} className="inline-flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-sm font-medium text-ink-soft shadow-card hover:bg-surface-muted disabled:opacity-60">
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} /> Làm mới
        </button>
      </header>

      <section className={`flex flex-wrap items-center justify-between gap-4 rounded-card border p-4 shadow-card ${overallStyle}`}>
        <div className="flex items-center gap-3"><StateIcon state={summary.overall} /><div><p className="font-semibold">{overallText}</p><p className="text-xs opacity-80">{sourceUnavailable ? "Nguồn trạng thái tạm thời chưa phản hồi." : `Snapshot ${summary.snapshotState} · ${summary.environment}`}</p></div></div>
        <div className="flex items-center gap-2 text-xs"><Clock3 size={15} /> Cập nhật {summary.generatedAt === new Date(0).toISOString() ? "—" : new Date(summary.generatedAt).toLocaleTimeString("vi-VN")}</div>
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"><Activity size={17} /> Dịch vụ & hiệu năng</h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <ServiceCard label="Database" state={summary.database.state} latency={summary.database.latencyMs} />
          {summary.services.map((service) => <ServiceCard key={service.id} label={SERVICE_LABELS[service.id] ?? service.id} state={service.state} restarts={service.restartCount} />)}
          {summary.services.length === 0 && <ServiceCard label="Host collector" state="unknown" restarts={0} />}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="rounded-card border border-line bg-surface-muted p-4 shadow-card">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"><FileClock size={17} /> Backup & tài nguyên</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-control border border-line bg-surface p-3"><p className="text-xs text-ink-muted">Backup gần nhất</p><p className="mt-1 text-lg font-semibold text-ink">{summary.backup.ageHours === null ? "Chưa rõ" : `${fmtNumber(summary.backup.ageHours)} giờ trước`}</p><div className="mt-2"><Badge state={summary.backup.state} text={summary.backup.state === "fresh" ? "Còn mới" : summary.backup.state === "stale" ? "Sắp quá hạn" : summary.backup.state === "critical" ? "Quá hạn/lỗi" : "Chưa có dữ liệu"} /></div></div>
            <div className="rounded-control border border-line bg-surface p-3"><p className="text-xs text-ink-muted">Dung lượng backup</p><p className="mt-1 text-lg font-semibold text-ink">{fmtBytes(summary.backup.archiveBytes)}</p><p className="mt-2 text-xs text-ink-muted">Public schema · cần Supabase PITR/Auth riêng</p></div>
            <div className="rounded-control border border-line bg-surface p-3"><p className="flex items-center gap-1.5 text-xs text-ink-muted"><HardDrive size={14} /> SSD đã dùng</p><p className="mt-1 text-lg font-semibold text-ink">{fmtNumber(summary.host?.diskUsedPercent ?? null, "%")}</p></div>
            <div className="rounded-control border border-line bg-surface p-3"><p className="text-xs text-ink-muted">Log 15 phút</p><p className="mt-1 text-lg font-semibold text-ink">{summary.logCounts ? `${summary.logCounts.errors} lỗi · ${summary.logCounts.warnings} cảnh báo` : "Chưa rõ"}</p><p className="mt-2 text-xs text-ink-muted">Chỉ đếm mức độ, không đọc nội dung log.</p></div>
          </div>
        </section>

        <section className="rounded-card border border-line bg-surface-muted p-4 shadow-card">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"><ShieldCheck size={17} /> Bảo mật</h2>
          <ul className="space-y-2">{summary.security.length > 0 ? summary.security.map((item) => <FindingCard key={item.id} item={item} />) : <FindingCard item={{ label: "Kiểm tra host", detail: "Chưa có snapshot host hợp lệ; không tự giả định trạng thái an toàn.", state: "unknown" }} />}</ul>
        </section>
      </div>

      <section>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink"><ScrollText size={17} /> Công cụ chuyên sâu</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <ToolLink href={links.logs} title="Log realtime · Dozzle" detail="Mở ở tab riêng, không đưa log bệnh nhân vào dashboard." icon={<ScrollText size={18} />} />
          <ToolLink href={links.uptime} title="Uptime Kuma" detail="Theo dõi uptime và cấu hình cảnh báo." icon={<Activity size={18} />} />
          <ToolLink href={links.sentry} title="Sentry" detail="Điều tra exception theo request ID." icon={<Database size={18} />} />
        </div>
      </section>
    </main>
  );
}
