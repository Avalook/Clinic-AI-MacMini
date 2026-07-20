import assert from "node:assert/strict";
import test from "node:test";

import {
  buildOpsLinks,
  normalizeOpsPayload,
  safeHttpUrl,
} from "./ops-summary.ts";

test("safeHttpUrl accepts only credential-free http(s) URLs", () => {
  assert.equal(safeHttpUrl("http://127.0.0.1:8888"), "http://127.0.0.1:8888/");
  assert.equal(safeHttpUrl("https://status.example.test/path"), "https://status.example.test/path");
  assert.equal(safeHttpUrl("https://user:pass@example.test"), null);
  assert.equal(safeHttpUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("file:///etc/passwd"), null);
});

test("buildOpsLinks rejects unsafe configuration", () => {
  assert.deepEqual(
    buildOpsLinks({
      OPS_DOZZLE_PUBLIC_URL: "http://127.0.0.1:8888",
      OPS_KUMA_PUBLIC_URL: "javascript:alert(1)",
      OPS_SENTRY_PUBLIC_URL: "https://sentry.example.test/issues/",
    }),
    {
      logs: "http://127.0.0.1:8888/",
      uptime: null,
      sentry: "https://sentry.example.test/issues/",
    },
  );
});

test("normalizer allowlists fields and fails closed on malformed payload", () => {
  const normalized = normalizeOpsPayload({
    generated_at: "2026-07-17T12:00:00.000Z",
    environment: "production",
    overall: "healthy",
    snapshot_state: "fresh",
    snapshot_age_seconds: 12,
    database: { state: "healthy", latency_ms: 42.5, database_url: "secret" },
    services: [
      { id: "api", state: "healthy", restart_count: 0, command: "secret" },
    ],
    host: { disk_used_percent: 44 },
    backup: {
      state: "fresh",
      completed_at: "2026-07-17T02:00:00.000Z",
      age_hours: 10,
      verified: true,
      archive_bytes: 123617,
      offsite_uploaded: false,
      scope: "public-schema-only",
      archive_path: "/private/patient.sql.gz",
    },
    security: [
      { id: "ingress", label: "Ingress", state: "good", detail: "An toàn" },
    ],
    log_counts: { window_minutes: 15, warnings: 1, errors: 0 },
    raw_logs: "patient secret",
  });

  assert.equal(normalized.overall, "healthy");
  assert.equal(normalized.database.latencyMs, 42.5);
  assert.equal(normalized.services[0]?.id, "api");
  assert.equal(normalized.backup.archiveBytes, 123617);
  assert.doesNotMatch(JSON.stringify(normalized), /secret|private|patient|command/);

  const fallback = normalizeOpsPayload({ nope: true });
  assert.equal(fallback.overall, "degraded");
  assert.equal(fallback.snapshotState, "unknown");
  assert.equal(fallback.database.state, "down");
});

