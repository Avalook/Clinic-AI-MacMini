// The service-role key bypasses RLS completely. Every file below can therefore
// read and write any row in any clinic, which is exactly what ADR-0012 says the
// frontend must not be able to do: the backend owns the contract, and the
// frontend has to be replaceable without becoming a security hole.
//
// This list may only ever get SHORTER. Adding a file fails the test, and so does
// leaving a file here after its service-role usage is gone — so the allowlist
// cannot rot into a rubber stamp. Each entry names what has to move to FastAPI
// before it can be deleted.

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

/** Files still allowed to hold the service-role key, and what blocks removal. */
const ALLOWED = new Map<string, string>([
  ["lib/supabase-service.ts", "the factory itself — the last thing to delete"],
  ["app/api/appointments/route.ts", "W5: booking, check-in and episode transitions -> FastAPI scheduling router"],
  ["app/api/appointments/quote/route.ts", "W5: capacity quote reads block_budget (backend-only table) -> scheduling router"],
  ["app/api/appointments/service-history/route.ts", "W5: -> scheduling router"],
  ["app/api/clinical-record/route.ts", "W5: ported to POST /api/v1/clinical-records — delete the legacy branch once CLINICAL_RECORD_VIA_BACKEND is permanent"],
  ["app/api/clinical-form/route.ts", "W5: ported to PUT /api/v1/clinical-forms — awaiting CLINICAL_FORM_VIA_BACKEND"],
  ["app/api/ultrasound/route.ts", "W5: ported to POST /api/v1/ultrasound/measurements — awaiting ULTRASOUND_VIA_BACKEND"],
  ["app/api/lab-result/route.ts", "W5: ported to /api/v1/lab/orders + /api/v1/lab/results — awaiting LAB_VIA_BACKEND"],
  ["app/api/payment/route.ts", "W5: payment router exists; finish the cutover and drop PAYMENT_VIA_BACKEND"],
  ["app/api/patients/route.ts", "W5: create already proxies; PATCH still writes directly"],
  ["app/api/service-log/route.ts", "W5: -> a new service router"],
  ["app/api/sono/route.ts", "W5: -> a new service router"],
  ["app/api/cskh-action/route.ts", "W5: -> a new cskh router"],
  ["app/api/cskh-followup/route.ts", "W5: -> a new cskh router"],
  ["app/api/episodes/route.ts", "W5: episode close -> scheduling router"],
  // These two build a service client inline instead of using the factory. Worth
  // folding into getSupabaseService when they move.
  ["app/api/roster/route.ts", "W5: roster writes -> scheduling router"],
  ["app/api/service-price/route.ts", "W5: price-list writes -> catalog router"],
  // Auth-admin operations (create a login, reset a password, revoke) have no
  // equivalent through the anon key, so this one stays even after W5.
  ["app/api/admin/users/route.ts", "keeps the key: Supabase Auth admin API"],
  // Reads the variable only to warn the operator that the form will 503.
  ["app/(dashboard)/settings/new-user/page.tsx", "presence check only, builds no client"],
]);

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx|mts)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

const sources = [join(ROOT, "app"), join(ROOT, "lib")]
  .flatMap(walk)
  .filter((f) => !f.endsWith(".test.mts") && !f.endsWith(".test.ts"))
  .map((f) => ({ path: relative(ROOT, f), text: readFileSync(f, "utf8") }));

const usesServiceRole = sources.filter((f) =>
  /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/.test(f.text),
);

test("no new file may reach for the service-role key", () => {
  const unexpected = usesServiceRole
    .map((f) => f.path)
    .filter((p) => !ALLOWED.has(p));

  assert.deepEqual(
    unexpected,
    [],
    `These files bypass RLS but are not on the ADR-0012 allowlist. Route the ` +
      `data through FastAPI instead of adding them here:\n  ${unexpected.join("\n  ")}`,
  );
});

test("the allowlist shrinks and never goes stale", () => {
  const present = new Set(usesServiceRole.map((f) => f.path));
  const stale = [...ALLOWED.keys()].filter((p) => !present.has(p));

  assert.deepEqual(
    stale,
    [],
    `These files no longer use the service-role key — delete them from the ` +
      `allowlist so the boundary keeps shrinking:\n  ${stale.join("\n  ")}`,
  );
});

test("the service-role key never crosses into a client component", () => {
  const leaked = usesServiceRole
    .filter((f) => /^["']use client["']/m.test(f.text))
    .map((f) => f.path);

  assert.deepEqual(
    leaked,
    [],
    `A client component reaching for the service-role key would ship it to the ` +
      `browser:\n  ${leaked.join("\n  ")}`,
  );
});

test("the boundary is small enough to finish", () => {
  // A number, not a vibe: W5 is done when this reaches 2 (the factory plus the
  // Auth-admin route). Raising it is not an option — the assertion is an upper
  // bound, so the only way to change this line is downwards.
  assert.ok(
    usesServiceRole.length <= 19,
    `${usesServiceRole.length} files hold the service-role key; the ceiling is 19 ` +
      `and it may only be lowered.`,
  );
});

test("reference data is read through the caller's own session", () => {
  // province/ward carry no patient data and got their SELECT policies in
  // 20260730000002, so nothing may bypass RLS to read them any more.
  const bypassing = usesServiceRole
    .filter((f) => /\.from\(["'](province|ward)["']\)/.test(f.text))
    .map((f) => f.path);

  assert.deepEqual(bypassing, []);
});
