// There used to be two doors: a shared clinic password (/enter, signing in as
// the one account named by CLINIC_SHARED_EMAIL), and then the personal login.
// The first one is gone. These assertions are about it staying gone, and about
// the second one still opening.
//
// Two failure modes, opposite in shape:
//   - the gate comes back — a route, a redirect, or anything reading that env
//     var. One env var means one clinic, which is the end of a pooled product,
//     and one password everybody knows means the audit trail names a building
//     instead of a person.
//   - the gate leaves a hole behind — /login stops being public, so the only
//     door left is behind the check that sends you to it. Nobody can sign in at
//     all, and the redirect loop looks like an outage rather than a config bug.
//
// The comments in proxy.ts and login/actions.ts deliberately name /enter and
// CLINIC_SHARED_EMAIL to explain why they went away. The scans below therefore
// match *uses* (a quoted path, a process.env read), never a mention.

import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const ROOT = fileURLToPath(new URL("..", import.meta.url));

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    if (entry === "node_modules" || entry === ".next") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.(ts|tsx|mts|mjs)$/.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

const sources = [
  ...[join(ROOT, "app"), join(ROOT, "lib"), join(ROOT, "e2e")].flatMap(walk),
  join(ROOT, "proxy.ts"),
]
  .filter((f) => !/\.test\.(mts|ts)$/.test(f))
  .map((f) => ({ path: relative(ROOT, f), text: readFileSync(f, "utf8") }));

const proxySource = readFileSync(join(ROOT, "proxy.ts"), "utf8");
const loginSource = readFileSync(
  join(ROOT, "app/(auth)/login/actions.ts"),
  "utf8",
);

test("the shared-password route does not exist", () => {
  assert.equal(
    existsSync(join(ROOT, "app/(auth)/enter")),
    false,
    "app/(auth)/enter is the gate itself",
  );
  const linking = sources.filter((f) => /["'`]\/enter\b/.test(f.text));
  assert.deepEqual(
    linking.map((f) => f.path),
    [],
    "nothing may redirect or link to /enter — it 404s now",
  );
});

test("nothing reads the shared clinic account out of the environment", () => {
  // Deleting the page but leaving the lookup is the worst of both: a clinic
  // whose deployment still only fits one tenant, with no screen admitting it.
  const readers = sources.filter((f) =>
    /process\.env\.CLINIC_SHARED_EMAIL|env\[["'`]CLINIC_SHARED_EMAIL/.test(
      f.text,
    ),
  );
  assert.deepEqual(readers.map((f) => f.path), []);
});

test("/login is public, or nobody can reach the only door left", () => {
  const declared = proxySource.match(/const PUBLIC_PATHS = \[([^\]]*)\]/);
  assert.ok(declared, "PUBLIC_PATHS must stay a literal we can read");
  const paths = [...declared[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert.ok(
    paths.includes("/login"),
    `/login must be public; PUBLIC_PATHS is ${JSON.stringify(paths)}`,
  );
  // And the signed-out branch must send people there, not to a route that is
  // now a 404.
  assert.match(proxySource, /if \(!user\) \{[\s\S]{0,120}redirectTo\("\/login"\)/);
});

test("signing out empties the desk for the next person", () => {
  // Reception shares one machine. A logout that ends the Supabase session but
  // keeps the role, staff and clinic cookies hands the next person the previous
  // person's identity — the exact confusion the shared account used to cause.
  const body = loginSource.split("export async function signOutStaff")[1];
  assert.ok(body, "signOutStaff must exist");
  assert.match(body, /auth\.signOut\(\)/);
  for (const cookie of ["ROLE_COOKIE", "STAFF_COOKIE", "ACTIVE_CLINIC_COOKIE"]) {
    assert.match(body, new RegExp(`delete\\(${cookie}\\)`), `must clear ${cookie}`);
  }
  assert.match(body, /redirect\("\/login"\)/);

  // And the button in the sidebar must be wired to it. A "Thoát" that runs an
  // empty action is worse than no button: the person believes they left.
  const layoutSource = readFileSync(
    join(ROOT, "app/(dashboard)/layout.tsx"),
    "utf8",
  );
  assert.match(layoutSource, /leaveAction=\{signOutStaff\}/);
  assert.match(layoutSource, /import \{ signOutStaff \} from "\.\.\/\(auth\)\/login\/actions"/);
});
