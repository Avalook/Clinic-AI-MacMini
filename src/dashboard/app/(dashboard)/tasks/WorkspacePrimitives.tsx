import type { ReactNode } from "react";

type MetricTone = "brand" | "warning" | "danger" | "success" | "neutral";

const METRIC_TONE: Record<MetricTone, string> = {
  brand: "bg-brand-50 text-brand-700",
  warning: "bg-warning-bg text-warning",
  danger: "bg-danger-bg text-danger",
  success: "bg-success-bg text-success",
  neutral: "bg-surface-sunken text-ink-muted",
};

export function initials(value: string | null | undefined, fallback = "BN"): string {
  if (!value?.trim()) return fallback;
  return value
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
}

export function Monogram({
  value,
  fallback,
  className = "",
}: {
  value: string | null | undefined;
  fallback?: string;
  className?: string;
}) {
  return (
    <span
      className={`grid size-9 shrink-0 place-items-center rounded-full border border-line bg-surface-sunken text-xs font-semibold text-ink-soft ${className}`}
      aria-hidden="true"
    >
      {initials(value, fallback)}
    </span>
  );
}

export function WorkspaceMetric({
  label,
  value,
  icon,
  tone = "neutral",
  detail,
}: {
  label: string;
  value: number | string;
  icon: ReactNode;
  tone?: MetricTone;
  detail?: string;
}) {
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3.5">
      <span
        className={`grid size-10 shrink-0 place-items-center rounded-full ${METRIC_TONE[tone]}`}
        aria-hidden="true"
      >
        {icon}
      </span>
      <span className="min-w-0">
        <span className="block truncate text-xs text-ink-muted">{label}</span>
        <span className="mt-0.5 block text-2xl font-semibold leading-none text-ink">
          {value}
        </span>
        {detail ? <span className="mt-1 block truncate text-label text-ink-faint">{detail}</span> : null}
      </span>
    </div>
  );
}

export function WorkspaceMetricRow({ children }: { children: ReactNode }) {
  return (
    <section className="grid overflow-hidden rounded-card border border-line bg-surface shadow-card sm:grid-cols-2 xl:grid-cols-4 xl:divide-x xl:divide-line">
      {children}
    </section>
  );
}

export function EmptyWorkspace({
  title,
  detail,
  icon,
}: {
  title: string;
  detail: string;
  icon?: ReactNode;
}) {
  return (
    <div className="grid min-h-44 place-items-center rounded-control border border-dashed border-line-strong bg-surface-muted px-5 py-8 text-center">
      <div>
        {icon ? <span className="mx-auto block text-brand-600">{icon}</span> : null}
        <p className="mt-2 text-sm font-medium text-ink">{title}</p>
        <p className="mt-1 max-w-sm text-xs leading-5 text-ink-muted">{detail}</p>
      </div>
    </div>
  );
}

export function PanelHeading({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line px-3.5 py-3">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {detail ? <p className="mt-0.5 text-xs text-ink-muted">{detail}</p> : null}
      </div>
      {action}
    </div>
  );
}
