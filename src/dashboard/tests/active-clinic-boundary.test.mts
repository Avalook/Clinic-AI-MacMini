// A doctor who works at two clinics could not use this product at all: the
// frontend resolved "more than one membership" to null, which every caller
// read as "not signed in", and the backend refused every proxied request
// because nothing ever sent it the X-Clinic-ID it has asked for since W3.
//
// These assertions are about the two halves staying joined. The pure decision
// itself lives in clinical-access-boundary.test.mts.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { isClinicSelector } from "../lib/identity-authority.ts";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const proxySource = read("../lib/backend-proxy.ts");
const layoutSource = read("../app/(dashboard)/layout.tsx");
const loginSource = read("../app/(auth)/login/actions.ts");
const pickerActionSource = read("../app/(auth)/choose-clinic/actions.ts");
const activeClinicSource = read("../lib/active-clinic.ts");
const clinicSessionSource = read("../lib/clinic-session.ts");

test("every proxied request tells the backend which clinic it means", () => {
  // Both directions: route handlers (proxyJsonToBackend) and server components
  // (fetchFromBackend). Missing it on either side is a 403 the user cannot act
  // on, on exactly the screens a multi-clinic doctor needs.
  const sends = proxySource.match(/headers\["X-Clinic-ID"\]/g) ?? [];
  assert.equal(
    sends.length,
    2,
    "both proxyJsonToBackend and fetchFromBackend must send X-Clinic-ID",
  );
  assert.match(proxySource, /headers\["X-Clinic-ID"\] = context\.staff\.clinic_id/);
});

test("the header carries the resolved membership, not the raw cookie", () => {
  // Sending the cookie straight through would let this side and identity.py
  // disagree the moment a membership is revoked: the page renders for clinic
  // A while every write goes to clinic B and comes back 403.
  assert.doesNotMatch(proxySource, /getActiveClinicId/);
  assert.match(proxySource, /getStaffContext/);
});

test("an unchosen clinic is reported as unchosen, not as forbidden", () => {
  assert.match(
    proxySource,
    /must_choose_clinic[\s\S]{0,400}status:\s*409/,
    "a stale tab must be told to pick a clinic, not that it lacks permission",
  );
});

test("the dashboard sends multi-clinic staff to the picker, not to /login", () => {
  const guardAt = layoutSource.indexOf('redirect("/choose-clinic")');
  const loginRedirectAt = layoutSource.indexOf('redirect("/login")');
  assert.ok(guardAt >= 0, "the layout must handle must_choose_clinic");
  assert.ok(
    guardAt < loginRedirectAt,
    "the ambiguous case must be caught before the signed-out case swallows it",
  );
});

test("routes outside (dashboard) ask the same question the layout does", () => {
  // /print/* renders the medical note and does not go through the dashboard
  // layout, so it needs its own copy of the guard — otherwise the lockout
  // survives on exactly the pages that leak the most if it is got wrong.
  const guard = clinicSessionSource
    .split("export async function requireClinicRole")[1]
    ?.split("\n}")[0];
  assert.ok(guard, "requireClinicRole must exist");
  assert.match(guard, /must_choose_clinic[\s\S]{0,80}redirect\("\/choose-clinic"\)/);
});

test("logging in with two clinics asks a question instead of signing you out", () => {
  const ambiguousBranch = loginSource
    .split('=== "ambiguous"')[1]
    ?.split("\n  }")[0];
  assert.ok(ambiguousBranch, "login must handle the ambiguous case explicitly");
  assert.match(ambiguousBranch, /redirect\("\/choose-clinic"\)/);
  assert.doesNotMatch(
    ambiguousBranch,
    /signOut/,
    "multiple memberships must not end the session",
  );
  // The single-clinic path still pins the selection, so the backend gets the
  // same tenant the page was rendered for.
  assert.match(loginSource, /setActiveClinicId\(membership\.clinic_id\)/);
});

test("the picker validates the posted clinic against real memberships", () => {
  // The form value is a selector. If it were written to the cookie unchecked,
  // a typed URL would still be harmless at the database (RLS derives the
  // tenant from auth.uid()), but the UI would claim a clinic the user has no
  // business seeing — and claiming is how trust is lost.
  const readAt = pickerActionSource.indexOf('.from("clinic_membership")');
  const setAt = pickerActionSource.indexOf("setActiveClinicId(");
  assert.ok(readAt >= 0, "the action must re-read memberships");
  assert.ok(setAt > readAt, "nothing is written before the membership is proven");
  assert.match(
    pickerActionSource,
    /setActiveClinicId\(selection\.membership\.clinic_id\)/,
    "write back the resolved membership, never the posted string",
  );
});

test("the selection is scoped to a shift and to this server", () => {
  assert.match(activeClinicSource, /httpOnly: true/);
  assert.match(activeClinicSource, /sameSite: "lax"/);
  assert.match(activeClinicSource, /maxAge: 60 \* 60 \* 12/);
});

test("a junk selector reads as nothing selected", () => {
  assert.equal(isClinicSelector("a0000000-0000-4000-8000-000000000001"), true);
  assert.equal(isClinicSelector(" a0000000-0000-4000-8000-000000000001 "), true);
  for (const junk of [
    "",
    "   ",
    "clinic-a",
    "a0000000-0000-4000-8000-00000000000",
    "a0000000-0000-4000-8000-000000000001'; DROP TABLE clinic;--",
    null,
    undefined,
  ]) {
    assert.equal(isClinicSelector(junk), false, `${String(junk)} must not pass`);
  }
});
