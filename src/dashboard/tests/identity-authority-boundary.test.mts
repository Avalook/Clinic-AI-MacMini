import assert from "node:assert/strict";
import test from "node:test";

import {
  resolveLinkedStaffAuthority,
} from "../lib/identity-authority.ts";

const managementStaff = {
  id: "staff-management",
  auth_user_id: "auth-management",
  primary_department: "MANAGEMENT",
  is_active: true,
};

test("derives role only from the staff row linked to the authenticated user", () => {
  assert.deepEqual(
    resolveLinkedStaffAuthority("auth-management", managementStaff),
    managementStaff,
  );
});

test("rejects a forged staff selection belonging to another auth user", () => {
  assert.equal(
    resolveLinkedStaffAuthority("auth-reception", managementStaff),
    null,
  );
});

test("rejects inactive and unlinked staff identities", () => {
  assert.equal(
    resolveLinkedStaffAuthority("auth-management", {
      ...managementStaff,
      is_active: false,
    }),
    null,
  );
  assert.equal(
    resolveLinkedStaffAuthority("auth-management", {
      ...managementStaff,
      auth_user_id: null,
    }),
    null,
  );
});
