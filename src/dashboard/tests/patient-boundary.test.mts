import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const routeSource = readFileSync(
  new URL("../app/api/patients/route.ts", import.meta.url),
  "utf8",
);
const postSource = routeSource.split("export async function PATCH")[0];

test("patient creation is fail-closed through the authoritative backend", () => {
  assert.match(postSource, /Authorization:\s*`Bearer \$\{token\}`/);
  assert.doesNotMatch(postSource, /\.from\(["']patient["']\)\s*\n\s*\.insert\(/);
  assert.doesNotMatch(postSource, /generatePatientCode/);
});
