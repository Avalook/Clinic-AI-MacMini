import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveActiveMembership,
  resolveManagementClinic,
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

test("admin authority resolves from an active MANAGEMENT membership", () => {
  assert.equal(
    resolveManagementClinic([
      {
        clinic_id: "clinic-a",
        role: "MANAGEMENT",
        is_active: true,
      },
    ]),
    "clinic-a",
  );
  assert.equal(
    resolveManagementClinic([
      { clinic_id: "clinic-a", role: "RECEPTION", is_active: true },
    ]),
    null,
  );
  assert.equal(
    resolveManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: false },
    ]),
    null,
  );
  assert.equal(
    resolveManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
      { clinic_id: "clinic-b", role: "MANAGEMENT", is_active: true },
    ]),
    null,
    "an absent clinic selector must never pick a tenant implicitly",
  );
  assert.equal(
    resolveManagementClinic([
      { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
      { clinic_id: "clinic-a", role: "RECEPTION", is_active: true },
    ]),
    null,
    "multiple active roles are ambiguous even inside one clinic",
  );
});

test("the selector picks the tenant, the role check still decides access", () => {
  const chainOwner = [
    { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
    { clinic_id: "clinic-b", role: "DOCTOR", is_active: true },
  ];
  assert.equal(resolveManagementClinic(chainOwner, "clinic-a"), "clinic-a");
  assert.equal(
    resolveManagementClinic(chainOwner, "clinic-b"),
    null,
    "selecting a clinic they only practise in must not grant admin there",
  );
  assert.equal(
    resolveManagementClinic(chainOwner, "clinic-c"),
    null,
    "a clinic they are not a member of is never selectable",
  );
});

test("frontend authority asks instead of guessing between memberships", () => {
  assert.deepEqual(
    resolveActiveMembership([
      { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
    ]),
    {
      status: "resolved",
      membership: { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
    },
  );

  const twoClinics = [
    { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
    { clinic_id: "clinic-b", role: "MANAGEMENT", is_active: true },
  ];
  assert.equal(
    resolveActiveMembership(twoClinics).status,
    "ambiguous",
    "two clinics is a question to ask, not a reason to deny",
  );
  assert.deepEqual(resolveActiveMembership(twoClinics, "clinic-b"), {
    status: "resolved",
    membership: { clinic_id: "clinic-b", role: "MANAGEMENT", is_active: true },
  });
});

test("a clinic selector is never authority on its own", () => {
  assert.equal(
    resolveActiveMembership([], "clinic-a").status,
    "none",
    "no membership means no access, whatever the cookie says",
  );
  assert.equal(
    resolveActiveMembership(
      [{ clinic_id: "clinic-a", role: "DOCTOR", is_active: false }],
      "clinic-a",
    ).status,
    "none",
    "a revoked membership is not resurrected by selecting it",
  );
  // A stale selection (membership removed while the cookie survived) falls back
  // to the remaining membership rather than locking the account out.
  assert.deepEqual(
    resolveActiveMembership(
      [{ clinic_id: "clinic-a", role: "DOCTOR", is_active: true }],
      "clinic-gone",
    ),
    {
      status: "resolved",
      membership: { clinic_id: "clinic-a", role: "DOCTOR", is_active: true },
    },
  );
  assert.equal(
    resolveActiveMembership(
      [
        { clinic_id: "clinic-a", role: "MANAGEMENT", is_active: true },
        { clinic_id: "clinic-a", role: "RECEPTION", is_active: true },
      ],
      "clinic-a",
    ).status,
    "none",
    "two active roles in one clinic is malformed provisioning, not a choice",
  );
});
