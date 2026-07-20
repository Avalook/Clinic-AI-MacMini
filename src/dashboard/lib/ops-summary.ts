export type OverallState = "healthy" | "degraded" | "critical";
export type ServiceState = "healthy" | "down" | "disabled" | "unknown";
export type FindingState = "good" | "warning" | "critical" | "unknown";

export interface OpsService {
  id: string;
  state: ServiceState;
  restartCount: number;
  cpuPercent: number | null;
  memoryPercent: number | null;
}

export interface OpsSummary {
  generatedAt: string;
  environment: "production" | "staging" | "unknown";
  overall: OverallState;
  snapshotState: "fresh" | "stale" | "expired" | "unknown" | "invalid";
  snapshotAgeSeconds: number | null;
  database: { state: "healthy" | "down"; latencyMs: number | null };
  services: OpsService[];
  host: { diskUsedPercent: number } | null;
  backup: {
    state: "fresh" | "stale" | "critical" | "unknown";
    completedAt: string | null;
    ageHours: number | null;
    verified: boolean | null;
    archiveBytes: number | null;
    offsiteUploaded: boolean | null;
    scope: "public-schema-only" | null;
  };
  security: Array<{
    id: string;
    label: string;
    state: FindingState;
    detail: string;
  }>;
  logCounts: { windowMinutes: number; warnings: number; errors: number } | null;
}

export interface OpsLinks {
  logs: string | null;
  uptime: string | null;
  sentry: string | null;
}

const SERVICE_IDS = new Set([
  "api",
  "dashboard",
  "caddy",
  "worker",
  "notification-relay",
  "rabbitmq",
  "dozzle",
  "uptime-kuma",
]);
const SERVICE_STATES = new Set<ServiceState>([
  "healthy",
  "down",
  "disabled",
  "unknown",
]);
const FINDING_STATES = new Set<FindingState>([
  "good",
  "warning",
  "critical",
  "unknown",
]);

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0
    ? value
    : null;
}

function text(value: unknown, max = 240): string | null {
  return typeof value === "string" && value.length > 0 && value.length <= max
    ? value
    : null;
}

export function safeHttpUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  try {
    const url = new URL(raw);
    if (!['http:', 'https:'].includes(url.protocol)) return null;
    if (url.username || url.password) return null;
    return url.toString();
  } catch {
    return null;
  }
}

export function buildOpsLinks(
  env: Record<string, string | undefined>,
): OpsLinks {
  return {
    logs: safeHttpUrl(env.OPS_DOZZLE_PUBLIC_URL),
    uptime: safeHttpUrl(env.OPS_KUMA_PUBLIC_URL),
    sentry: safeHttpUrl(env.OPS_SENTRY_PUBLIC_URL),
  };
}

export function emptyOpsSummary(): OpsSummary {
  return {
    generatedAt: new Date(0).toISOString(),
    environment: "unknown",
    overall: "degraded",
    snapshotState: "unknown",
    snapshotAgeSeconds: null,
    database: { state: "down", latencyMs: null },
    services: [],
    host: null,
    backup: {
      state: "unknown",
      completedAt: null,
      ageHours: null,
      verified: null,
      archiveBytes: null,
      offsiteUploaded: null,
      scope: null,
    },
    security: [],
    logCounts: null,
  };
}

export function normalizeOpsPayload(payload: unknown): OpsSummary {
  const root = record(payload);
  const generatedAt = text(root?.generated_at ?? root?.generatedAt);
  const overall = root?.overall;
  const snapshotState = root?.snapshot_state ?? root?.snapshotState;
  const database = record(root?.database);
  if (
    !root ||
    !generatedAt ||
    !["healthy", "degraded", "critical"].includes(String(overall)) ||
    !["fresh", "stale", "expired", "unknown", "invalid"].includes(
      String(snapshotState),
    ) ||
    !database ||
    !["healthy", "down"].includes(String(database.state))
  ) {
    return emptyOpsSummary();
  }

  const environment = ["production", "staging"].includes(
    String(root.environment),
  )
    ? (root.environment as "production" | "staging")
    : "unknown";

  const services = Array.isArray(root.services)
    ? root.services.flatMap((value): OpsService[] => {
        const item = record(value);
        const id = text(item?.id, 64);
        const state = item?.state as ServiceState;
        if (!item || !id || !SERVICE_IDS.has(id) || !SERVICE_STATES.has(state)) {
          return [];
        }
        return [
          {
            id,
            state,
            restartCount: finiteNumber(item.restart_count ?? item.restartCount) ?? 0,
            cpuPercent: finiteNumber(item.cpu_percent ?? item.cpuPercent),
            memoryPercent: finiteNumber(item.memory_percent ?? item.memoryPercent),
          },
        ];
      })
    : [];

  const backupRaw = record(root.backup);
  const backupState = backupRaw?.state;
  const backup = {
    state: ["fresh", "stale", "critical"].includes(String(backupState))
      ? (backupState as "fresh" | "stale" | "critical")
      : ("unknown" as const),
    completedAt: text(backupRaw?.completed_at ?? backupRaw?.completedAt),
    ageHours: finiteNumber(backupRaw?.age_hours ?? backupRaw?.ageHours),
    verified:
      typeof backupRaw?.verified === "boolean" ? backupRaw.verified : null,
    archiveBytes: finiteNumber(backupRaw?.archive_bytes ?? backupRaw?.archiveBytes),
    offsiteUploaded:
      typeof (backupRaw?.offsite_uploaded ?? backupRaw?.offsiteUploaded) === "boolean"
        ? (backupRaw?.offsite_uploaded ?? backupRaw?.offsiteUploaded) as boolean
        : null,
    scope:
      backupRaw?.scope === "public-schema-only"
        ? ("public-schema-only" as const)
        : null,
  };

  const security = Array.isArray(root.security)
    ? root.security.flatMap((value) => {
        const item = record(value);
        const id = text(item?.id, 64);
        const label = text(item?.label, 120);
        const detail = text(item?.detail, 240);
        const state = item?.state as FindingState;
        return item && id && label && detail && FINDING_STATES.has(state)
          ? [{ id, label, detail, state }]
          : [];
      })
    : [];

  const hostRaw = record(root.host);
  const diskUsedPercent = finiteNumber(hostRaw?.disk_used_percent ?? hostRaw?.diskUsedPercent);
  const logsRaw = record(root.log_counts ?? root.logCounts);
  const windowMinutes = finiteNumber(logsRaw?.window_minutes ?? logsRaw?.windowMinutes);
  const warnings = finiteNumber(logsRaw?.warnings);
  const errors = finiteNumber(logsRaw?.errors);

  return {
    generatedAt,
    environment,
    overall: overall as OverallState,
    snapshotState: snapshotState as OpsSummary["snapshotState"],
    snapshotAgeSeconds: finiteNumber(root.snapshot_age_seconds ?? root.snapshotAgeSeconds),
    database: {
      state: database.state as "healthy" | "down",
      latencyMs: finiteNumber(database.latency_ms ?? database.latencyMs),
    },
    services,
    host: diskUsedPercent === null ? null : { diskUsedPercent },
    backup,
    security,
    logCounts:
      windowMinutes === null || warnings === null || errors === null
        ? null
        : { windowMinutes, warnings, errors },
  };
}
