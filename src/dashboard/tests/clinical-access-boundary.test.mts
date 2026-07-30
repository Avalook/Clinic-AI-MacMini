import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveSingleActiveMembership,
  resolveSingleManagementClinic,
} from "../lib/identity-authority.ts";
import { labReleaseDecision } from "../lib/lab-release.ts";
import {
  canReadClinical,
  departmentToRole,
} from "../lib/roles.ts";

test("unknown or missing departments never inherit a real clinic role", () => {
  assert.equal(departmentToRole("NOT_A_ROLE"), null);
  assert.equal(departmentToRole(""), null);
  assert.equal(departmentToRole(null), null);
});

test("only finalized GROUP_A laboratory results may be reported to a patient", () => {
  assert.equal(labReleaseDecision("GROUP_A", true).allowed, true);

  for (const group of ["GROUP_B", "GROUP_C", "PENDING", null, undefined]) {
    assert.equal(
      labReleaseDecision(group, true).allowed,
      false,
      `${String(group)} must fail closed`,
    );
  }
  assert.equal(labReleaseDecision("GROUP_A", false).allowed, false);
});

test("medical notes are readable only by the four clinical roles", () => {
  for (const role of [
    "DOCTOR",
    "ULTRASOUND_DOCTOR",
    "NURSE_ULTRASOUND",
    "TKYK",
  ] as const) {
    assert.equal(canReadClinical(role), true);
  }
  for (const role of [
    "MANAGEMENT",
    "RECEPTION",
    "CSKH",
    "CASHIER",
    null,
  ] as const) {
    assert.equal(canReadClinical(role), false);
  }
});

test("admin authority resolves from exactly one active MANAGEMENT membership", () => {
  assert.equal(
    resolveSingleManagementClinic([
      {
        clinic_id: "clinic-a",
        role: "MANAGEMENT",
        is_active: true,
      },
    ]),
    "clinic-a",
  );
  assert.equal(
    resolveSingleManagementClinic([
      { clinic_id: "clinic-a", role: "RECEPTION", is_active: true },
    ]),
    null,
  );
  assert.equal(
    resolveSingleManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: false },
    ]),
    null,
  );
  assert.equal(
    resolveSingleManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
      { clinic_id: "clinic-b", role: "MANAGEMENT", is_active: true },
    ]),
    null,
    "an absent clinic selector must never pick a tenant implicitly",
  );
  assert.equal(
    resolveSingleManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
      { clinic_id: "clinic-a", role: "RECEPTION", is_active: true },
    ]),
    null,
    "multiple active roles are ambiguous even inside one clinic",
  );
});

test("frontend authority refuses to guess between memberships", () => {
  assert.deepEqual(
    resolveSingleActiveMembership([
      { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
    ]),
    { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
  );
  assert.equal(
    resolveSingleActiveMembership([
      { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
      { clinic_id: "clinic-b", role: "MANAGEMENT", is_active: true },
    ]),
    null,
  );
});
