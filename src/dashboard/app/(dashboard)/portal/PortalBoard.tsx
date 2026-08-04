"use client";

// Command Center — Cổng trung tâm điều khiển toàn hệ thống.
// Tổng hợp mọi thứ: trạng thái hệ thống, vai trò, màn hình, hạ tầng, nhân viên.

import Link from "next/link";
import { VN_TZ } from "../../../lib/datetime";
import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  ExternalLink,
  FileClock,
  Gauge,
  HardDrive,
  LayoutDashboard,
  RefreshCw,
  ScrollText,
  Settings,
  ShieldCheck,
  Users,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";

import {
  emptyOpsSummary,
  normalizeOpsPayload,
  safeHttpUrl,
  type OpsLinks,
  type OpsSummary,
  type ServiceState,
} from "../../../lib/ops-summary";
import {
  ALL_ROLES,
  ROLE_LABEL,
  canSeeNav,
  type ClinicRole,
} from "../../../lib/roles";
import { NAV } from "../nav-items";

// ─── Types ────────────────────────────────────────────────────────────────────

interface StaffRow {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  employment_type: string;
  is_active: boolean;
  auth_user_id: string | null;
}

interface RecentEvent {
  event_id: string;
  event_type: string;
  aggregate_type: string;
  source: string;
  occurred_at: string;
}

interface PortalProps {
  staff: StaffRow[];
  counts: {
    appointmentsToday: number;
    patientsToday: number;
    visitsToday: number;
    pendingTasks: number;
  };
  recentEvents: RecentEvent[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

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

const STATE_STYLE: Record<string, string> = {
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
};

// Mô tả ngắn cho từng vai trò
const ROLE_DESC: Record<ClinicRole, string> = {
  DOCTOR: "Khám, chẩn đoán, kê đơn",
  ULTRASOUND_DOCTOR: "Siêu âm, đo chỉ số thai",
  NURSE_ULTRASOUND: "Hỗ trợ siêu âm, xét nghiệm",
  TKYK: "Nhập hồ sơ lâm sàng hộ bác sĩ",
  CSKH: "Chăm sóc khách hàng, đặt lịch",
  MANAGEMENT: "Quản lý toàn hệ thống",
  RECEPTION: "Đón tiếp, check-in, hành chính",
  CASHIER: "Thu ngân tổng hợp",
  CASHIER_THUOC: "Thu ngân bán thuốc",
  CASHIER_DV: "Thu ngân dịch vụ",
  TRUONG_CA: "Điều phối ca, vận hành",
  PHARMACIST: "Dược sĩ, cấp phát thuốc",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function StateIcon({ state }: { state: string }) {
  if (["healthy", "fresh", "good"].includes(state)) {
    return <CheckCircle2 size={16} aria-hidden />;
  }
  if (["critical", "down", "expired", "invalid"].includes(state)) {
    return <XCircle size={16} aria-hidden />;
  }
  return <AlertTriangle size={16} aria-hidden />;
}

function Badge({ state, text }: { state: string; text: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-chip border px-2.5 py-1 text-xs font-medium ${STATE_STYLE[state] ?? STATE_STYLE.unknown}`}
    >
      <StateIcon state={state} />
      {text}
    </span>
  );
}

function fmtNumber(value: number | null, suffix = "") {
  return value === null
    ? "—"
    : `${new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(value)}${suffix}`;
}

function fmtBytes(value: number | null) {
  if (value === null) return "—";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function fmtDateTime(iso: string) {
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: VN_TZ,
  });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function SectionCard({
  title,
  icon: Icon,
  children,
  className = "",
}: {
  title: string;
  icon: LucideIcon;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-card border border-line bg-surface p-4 shadow-card ${className}`}
    >
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
        <Icon size={17} className="text-brand-600" />
        {title}
      </h2>
      {children}
    </section>
  );
}

function StatTile({
  label,
  value,
  icon: Icon,
  accent = "text-brand-600",
}: {
  label: string;
  value: number;
  icon: LucideIcon;
  accent?: string;
}) {
  return (
    <div className="rounded-card border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-muted">{label}</p>
        <Icon size={18} className={accent} aria-hidden />
      </div>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </div>
  );
}

function ServiceCard({
  label,
  state,
  latency,
  restarts,
}: {
  label: string;
  state: ServiceState;
  latency?: number | null;
  restarts?: number;
}) {
  const stateText =
    state === "healthy"
      ? "Ổn định"
      : state === "disabled"
        ? "Đang tắt"
        : state === "down"
          ? "Mất kết nối"
          : "Chưa rõ";
  return (
    <div className="flex items-center justify-between rounded-control border border-line bg-surface-muted px-3 py-2.5">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink">{label}</p>
        <p className="text-xs text-ink-muted">
          {latency !== undefined
            ? `Độ trễ ${fmtNumber(latency, " ms")}`
            : `Restart ${restarts ?? 0}`}
        </p>
      </div>
      <Badge state={state} text={stateText} />
    </div>
  );
}

function ToolLink({
  href,
  title,
  detail,
  icon,
}: {
  href: string | null;
  title: string;
  detail: string;
  icon: React.ReactNode;
}) {
  if (!href) {
    return (
      <div className="flex items-center gap-3 rounded-card border border-dashed border-line bg-surface-muted p-4 text-ink-muted">
        {icon}
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs">Chưa cấu hình đường dẫn an toàn.</p>
        </div>
      </div>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
    >
      <span className="rounded-control bg-brand-50 p-2 text-brand-600">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-ink">{title}</p>
        <p className="text-xs text-ink-muted">{detail}</p>
      </div>
      <ExternalLink
        size={16}
        className="text-ink-faint group-hover:text-brand-600"
        aria-hidden
      />
    </a>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function PortalBoard({
  staff,
  counts,
  recentEvents,
}: PortalProps) {
  const [summary, setSummary] = useState<OpsSummary>(emptyOpsSummary());
  const [links, setLinks] = useState<OpsLinks>({
    logs: null,
    uptime: null,
    sentry: null,
  });
  const [loading, setLoading] = useState(true);
  const [sourceUnavailable, setSourceUnavailable] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/ops/summary", { cache: "no-store" });
      if (!response.ok) throw new Error("ops unavailable");
      const payload = (await response.json()) as Record<string, unknown>;
      setSummary(normalizeOpsPayload(payload));
      const rawLinks =
        payload.links && typeof payload.links === "object"
          ? (payload.links as Record<string, unknown>)
          : {};
      setLinks({
        logs: safeHttpUrl(
          typeof rawLinks.logs === "string" ? rawLinks.logs : null,
        ),
        uptime: safeHttpUrl(
          typeof rawLinks.uptime === "string" ? rawLinks.uptime : null,
        ),
        sentry: safeHttpUrl(
          typeof rawLinks.sentry === "string" ? rawLinks.sentry : null,
        ),
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

  const overallText =
    summary.overall === "healthy"
      ? "Hệ thống ổn định"
      : summary.overall === "critical"
        ? "Cần xử lý ngay"
        : "Có hạng mục cần kiểm tra";
  const overallStyle = STATE_STYLE[summary.overall] ?? STATE_STYLE.unknown;

  // Nhóm màn hình theo vai trò
  const roleScreens = ALL_ROLES.map((r) => {
    const screens = NAV.filter((item) => {
      // /portal không hiển thị trong grid vai trò
      if (item.href === "/portal") return false;
      return canSeeNav(r, item.href);
    });
    return { role: r, screens };
  });

  // Số nhân viên active / đã link
  const activeStaff = staff.filter((s) => s.is_active).length;
  const linkedStaff = staff.filter((s) => s.auth_user_id !== null).length;

  return (
    <main className="page-in min-w-0 space-y-6 p-4 lg:p-5">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Zap size={22} className="text-brand-600" />
            <h1 className="text-xl font-semibold text-ink lg:text-2xl">
              Command Center
            </h1>
          </div>
          <p className="mt-1 text-sm text-ink-muted">
            Cổng trung tâm điều khiển toàn hệ thống · vai trò, màn hình, hạ
            tầng, vận hành
          </p>
        </div>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-sm font-medium text-ink-soft shadow-card hover:bg-surface-muted disabled:opacity-60"
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          Làm mới
        </button>
      </header>

      {/* ── Tổng quan hệ thống ─────────────────────────────────────────── */}
      <section
        className={`flex flex-wrap items-center justify-between gap-4 rounded-card border p-4 shadow-card ${overallStyle}`}
      >
        <div className="flex items-center gap-3">
          <StateIcon state={summary.overall} />
          <div>
            <p className="font-semibold">{overallText}</p>
            <p className="text-xs opacity-80">
              {sourceUnavailable
                ? "Nguồn trạng thái tạm thời chưa phản hồi."
                : `Snapshot ${summary.snapshotState} · ${summary.environment}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <Clock3 size={15} />
          Cập nhật{" "}
          {summary.generatedAt === new Date(0).toISOString()
            ? "—"
            : new Date(summary.generatedAt).toLocaleTimeString("vi-VN")}
        </div>
      </section>

      {/* ── Số liệu hôm nay ────────────────────────────────────────────── */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Lịch hẹn hôm nay"
          value={counts.appointmentsToday}
          icon={BarChart3}
        />
        <StatTile
          label="BN mới hôm nay"
          value={counts.patientsToday}
          icon={Users}
        />
        <StatTile
          label="Lượt khám hôm nay"
          value={counts.visitsToday}
          icon={Activity}
        />
        <StatTile
          label="Việc đang chờ"
          value={counts.pendingTasks}
          icon={Clock3}
          accent="text-warning"
        />
      </section>

      {/* ── Dịch vụ & hiệu năng ────────────────────────────────────────── */}
      <SectionCard title="Dịch vụ & hiệu năng" icon={Activity}>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <ServiceCard
            label="Database"
            state={summary.database.state}
            latency={summary.database.latencyMs}
          />
          {summary.services.map((service) => (
            <ServiceCard
              key={service.id}
              label={SERVICE_LABELS[service.id] ?? service.id}
              state={service.state}
              restarts={service.restartCount}
            />
          ))}
          {summary.services.length === 0 && (
            <ServiceCard label="Host collector" state="unknown" restarts={0} />
          )}
        </div>
      </SectionCard>

      {/* ── Backup & tài nguyên ────────────────────────────────────────── */}
      <div className="grid gap-5 xl:grid-cols-2">
        <SectionCard title="Backup & tài nguyên" icon={FileClock}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Backup gần nhất</p>
              <p className="mt-1 text-lg font-semibold text-ink">
                {summary.backup.ageHours === null
                  ? "Chưa rõ"
                  : `${fmtNumber(summary.backup.ageHours)} giờ trước`}
              </p>
              <div className="mt-2">
                <Badge
                  state={summary.backup.state}
                  text={
                    summary.backup.state === "fresh"
                      ? "Còn mới"
                      : summary.backup.state === "stale"
                        ? "Sắp quá hạn"
                        : summary.backup.state === "critical"
                          ? "Quá hạn/lỗi"
                          : "Chưa có dữ liệu"
                  }
                />
              </div>
            </div>
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Dung lượng backup</p>
              <p className="mt-1 text-lg font-semibold text-ink">
                {fmtBytes(summary.backup.archiveBytes)}
              </p>
              <p className="mt-2 text-xs text-ink-muted">
                Public schema · cần Supabase PITR/Auth riêng
              </p>
            </div>
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="flex items-center gap-1.5 text-xs text-ink-muted">
                <HardDrive size={14} /> SSD đã dùng
              </p>
              <p className="mt-1 text-lg font-semibold text-ink">
                {fmtNumber(summary.host?.diskUsedPercent ?? null, "%")}
              </p>
            </div>
            <div className="rounded-control border border-line bg-surface-muted p-3">
              <p className="text-xs text-ink-muted">Log 15 phút</p>
              <p className="mt-1 text-lg font-semibold text-ink">
                {summary.logCounts
                  ? `${summary.logCounts.errors} lỗi · ${summary.logCounts.warnings} cảnh báo`
                  : "Chưa rõ"}
              </p>
              <p className="mt-2 text-xs text-ink-muted">
                Chỉ đếm mức độ, không đọc nội dung log.
              </p>
            </div>
          </div>
        </SectionCard>

        {/* ── Bảo mật ──────────────────────────────────────────────────── */}
        <SectionCard title="Bảo mật" icon={ShieldCheck}>
          <ul className="space-y-2">
            {summary.security.length > 0 ? (
              summary.security.map((item) => (
                <li
                  key={item.id}
                  className="flex items-start gap-3 rounded-control border border-line bg-surface-muted p-3"
                >
                  <span
                    className={`mt-0.5 rounded-chip border p-1.5 ${STATE_STYLE[item.state] ?? STATE_STYLE.unknown}`}
                  >
                    <StateIcon state={item.state} />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-ink">
                      {item.label}
                    </p>
                    <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                      {item.detail}
                    </p>
                  </div>
                </li>
              ))
            ) : (
              <li className="flex items-start gap-3 rounded-control border border-line bg-surface-muted p-3">
                <span
                  className={`mt-0.5 rounded-chip border p-1.5 ${STATE_STYLE.unknown}`}
                >
                  <StateIcon state="unknown" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">
                    Kiểm tra host
                  </p>
                  <p className="mt-0.5 text-xs leading-5 text-ink-muted">
                    Chưa có snapshot host hợp lệ; không tự giả định trạng thái
                    an toàn.
                  </p>
                </div>
              </li>
            )}
          </ul>
        </SectionCard>
      </div>

      {/* ── Vai trò & Màn hình ─────────────────────────────────────────── */}
      <SectionCard title="Vai trò & Màn hình" icon={LayoutDashboard}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {roleScreens.map(({ role: r, screens }) => (
            <div
              key={r}
              className="rounded-card border border-line bg-surface-muted p-4"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">
                    {ROLE_LABEL[r]}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {ROLE_DESC[r]}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                  {screens.length} màn
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {screens.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="inline-flex items-center gap-1 rounded-chip border border-line bg-surface px-2 py-1 text-xs text-ink-soft transition hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                  >
                    <item.icon size={12} aria-hidden />
                    {item.shortLabel ?? item.label}
                  </Link>
                ))}
                {screens.length === 0 && (
                  <span className="text-xs text-ink-faint">
                    Không có màn hình riêng
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </SectionCard>

      {/* ── Nhân viên ──────────────────────────────────────────────────── */}
      <SectionCard title="Nhân viên" icon={Users}>
        <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
          <span className="rounded-chip border border-line bg-surface-muted px-3 py-1.5">
            <span className="font-semibold text-ink">{staff.length}</span>{" "}
            <span className="text-ink-muted">tổng</span>
          </span>
          <span className="rounded-chip border border-success bg-success-bg px-3 py-1.5 text-success">
            <span className="font-semibold">{activeStaff}</span> active
          </span>
          <span className="rounded-chip border border-warning bg-warning-bg px-3 py-1.5 text-warning">
            <span className="font-semibold">{linkedStaff}</span> đã link login
          </span>
        </div>
        <div className="max-h-80 overflow-y-auto rounded-control border border-line">
          <table className="min-w-full divide-y divide-brand-100 text-sm">
            <thead className="sticky top-0 z-10 bg-brand-100 text-left text-[11px] font-semibold uppercase tracking-wide text-brand-800">
              <tr>
                <th className="px-4 py-2.5 font-medium">Họ tên</th>
                <th className="px-4 py-2.5 font-medium">Vai trò</th>
                <th className="px-4 py-2.5 font-medium">Hợp đồng</th>
                <th className="px-4 py-2.5 font-medium">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-brand-100">
              {staff.map((s) => (
                <tr
                  key={s.id}
                  className="transition-colors duration-150 hover:bg-brand-50"
                >
                  <td className="px-4 py-2.5 text-ink">
                    {s.full_name}
                    {s.short_name && s.short_name !== s.full_name && (
                      <span className="ml-2 text-xs text-ink-muted">
                        {s.short_name}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-ink-soft">
                    {ROLE_LABEL[s.primary_department as ClinicRole] ??
                      s.primary_department}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-ink-muted">
                    {s.employment_type}
                  </td>
                  <td className="px-4 py-2.5">
                    {s.is_active ? (
                      <span className="inline-flex items-center gap-1 text-xs text-success">
                        <span className="h-1.5 w-1.5 rounded-full bg-success" />
                        Active
                      </span>
                    ) : (
                      <span className="text-xs text-ink-muted">Inactive</span>
                    )}
                    {s.auth_user_id ? (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs text-success">
                        <span className="h-1.5 w-1.5 rounded-full bg-success" />
                        Đã link
                      </span>
                    ) : (
                      <span className="ml-2 inline-flex items-center gap-1 text-xs text-warning">
                        <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                        Chưa link
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {staff.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-4 py-6 text-center text-ink-muted"
                  >
                    Chưa có nhân viên.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </SectionCard>

      {/* ── Sự kiện gần đây ────────────────────────────────────────────── */}
      <SectionCard title="Sự kiện gần đây" icon={ScrollText}>
        {recentEvents.length === 0 ? (
          <p className="py-6 text-center text-sm text-ink-muted">
            Chưa có sự kiện nào.
          </p>
        ) : (
          <ul className="space-y-1.5">
            {recentEvents.map((e) => (
              <li
                key={e.event_id}
                className="flex items-start gap-3 rounded-control border border-line bg-surface-muted px-3 py-2"
              >
                <span className="mt-0.5 shrink-0 text-xs tabular-nums text-ink-faint">
                  {fmtDateTime(e.occurred_at)}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
                      {e.event_type}
                    </span>
                    <span className="text-xs text-ink-muted">
                      {e.aggregate_type} · {e.source}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* ── Công cụ chuyên sâu ─────────────────────────────────────────── */}
      <SectionCard title="Công cụ chuyên sâu" icon={Settings}>
        <div className="grid gap-3 md:grid-cols-3">
          <ToolLink
            href={links.logs}
            title="Log realtime · Dozzle"
            detail="Mở ở tab riêng, không đưa log bệnh nhân vào dashboard."
            icon={<ScrollText size={18} />}
          />
          <ToolLink
            href={links.uptime}
            title="Uptime Kuma"
            detail="Theo dõi uptime và cấu hình cảnh báo."
            icon={<Activity size={18} />}
          />
          <ToolLink
            href={links.sentry}
            title="Sentry"
            detail="Điều tra exception theo request ID."
            icon={<Database size={18} />}
          />
        </div>
      </SectionCard>

      {/* ── Lối tắt quản trị ───────────────────────────────────────────── */}
      <SectionCard title="Lối tắt quản trị" icon={Gauge}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            href="/ops"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <Gauge size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Vận hành hệ thống</p>
              <p className="text-xs text-ink-muted">Ops Center</p>
            </div>
          </Link>
          <Link
            href="/settings"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <Settings size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Cài đặt tài khoản</p>
              <p className="text-xs text-ink-muted">Nhân viên & login</p>
            </div>
          </Link>
          <Link
            href="/audit-log"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <ScrollText size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Lịch sử thao tác</p>
              <p className="text-xs text-ink-muted">Audit log</p>
            </div>
          </Link>
          <Link
            href="/reports"
            className="group flex items-center gap-3 rounded-card border border-line bg-surface p-4 shadow-card transition hover:border-brand-300 hover:bg-brand-50"
          >
            <span className="rounded-control bg-brand-50 p-2 text-brand-600">
              <BarChart3 size={18} />
            </span>
            <div>
              <p className="text-sm font-medium text-ink">Báo cáo</p>
              <p className="text-xs text-ink-muted">Số liệu vận hành</p>
            </div>
          </Link>
        </div>
      </SectionCard>
    </main>
  );
}