import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const source = readFileSync(
  new URL("../app/api/brief/[id]/route.ts", import.meta.url),
  "utf8",
);

test("the brief proxy forwards the verified caller bearer token", () => {
  const sessionAt = source.indexOf("auth.getSession()");
  const tokenAt = source.indexOf("session?.access_token");
  const bearerAt = source.indexOf("Authorization: `Bearer ${token}`");
  const fetchAt = source.indexOf("await fetch(");

  assert.ok(sessionAt >= 0, "the proxy must resolve the caller session");
  assert.ok(tokenAt > sessionAt, "the proxy must obtain the access token");
  assert.ok(bearerAt > tokenAt, "the backend request must carry Bearer auth");
  assert.ok(fetchAt > bearerAt, "authorization must be prepared before fetch");
});

test("the brief proxy fails closed when the backend URL is absent", () => {
  assert.doesNotMatch(
    source,
    /process\.env\.CLINIC_API_URL\s*\?\?\s*["']http:\/\/localhost/,
  );
  assert.match(source, /CLINIC_API_URL chưa được cấu hình/);
});
