import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const apiSource = readFileSync(
  new URL("../app/api/ops/summary/route.ts", import.meta.url),
  "utf8",
);
const pageSource = readFileSync(
  new URL("../app/(dashboard)/ops/page.tsx", import.meta.url),
  "utf8",
);

test("Ops API authenticates the real Supabase user and requires MANAGEMENT", () => {
  assert.match(apiSource, /auth\.getUser\(\)/);
  assert.match(apiSource, /isAdminRole/);
  assert.match(apiSource, /json\([^\n]+,\s*401\)/);
  assert.match(apiSource, /json\([^\n]+,\s*403\)/);
  assert.doesNotMatch(apiSource, /clinic_role|clinic_staff_id|cookies\(\)/);
});

test("Ops page has a server-side navigation authorization gate", () => {
  assert.match(pageSource, /requireNavAccess\(["']\/ops["']\)/);
});

test("Ops implementation never mounts or reads docker.sock in the dashboard", () => {
  assert.doesNotMatch(apiSource + pageSource, /docker\.sock|Dockerode|\/containers\/json/);
});
