// The service-role key bypasses RLS completely. Every file below can therefore
// read and write any row in any clinic, which is exactly what ADR-0012 says the
// frontend must not be able to do: the backend owns the contract, and the
// frontend has to be replaceable without becoming a security hole.
//
// The legacy branches are gone: every business route is now a thin proxy to
// FastAPI, and reads go through the caller's own session under RLS. What is
// left is the Auth-admin route, which needs a capability the anon key does not
// have, and the factory it calls.
//
// This list may only ever get SHORTER. Adding a file fails the test, and so does
// leaving a file here after its service-role usage is gone — so the allowlist
// cannot rot into a rubber stamp.

import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

/** Files still allowed to hold the service-role key, and why. */
const ALLOWED = new Map<string, string>([
  ["lib/supabase-service.ts", "the factory, and the presence check the settings page asks it for"],
  // Creating a login, resetting a password and revoking one go through the
  // Supabase Auth admin API, which has no anon-key equivalent. This is the one
  // capability the backend cannot take over, so this entry is the floor.
  ["app/api/admin/users/route.ts", "keeps the key: Supabase Auth admin API"],
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

const sources = [
  ...[join(ROOT, "app"), join(ROOT, "lib")].flatMap(walk),
  join(ROOT, "proxy.ts"),
]
  .filter((f) => !f.endsWith(".test.mts") && !f.endsWith(".test.ts"))
  .map((f) => ({ path: relative(ROOT, f), text: readFileSync(f, "utf8") }));

const usesServiceRole = sources.filter((f) =>
  /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/.test(f.text),
);
const adminRoute = sources.find(
  (source) => source.path === "app/api/admin/users/route.ts",
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

test("the boundary is as small as it goes", () => {
  // A number, not a vibe. This started at 17 and is now at its floor: the
  // factory and the Auth-admin route that needs it. There is no third file to
  // justify, so anything above 2 is a regression, not a work item.
  assert.ok(
    usesServiceRole.length <= 2,
    `${usesServiceRole.length} files hold the service-role key; the ceiling is 2 ` +
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

test("the Auth-admin exception remains tenant- and membership-scoped", () => {
  assert.ok(adminRoute);
  assert.match(adminRoute.text, /\.from\(["']clinic_membership["']\)/);
  assert.match(adminRoute.text, /\.eq\(["']clinic_id["'], clinicId\)/);
  assert.match(adminRoute.text, /resolveManagementClinic/);
  // The selector must come from the session, never from the request body — an
  // Auth-admin route that trusted a posted clinic_id would hand a manager of
  // one clinic the user list of every other one.
  assert.match(adminRoute.text, /getActiveClinicId\(\)/);
  assert.match(adminRoute.text, /\.eq\(["']auth_user_id["'], target\.auth_user_id\)/);
});
