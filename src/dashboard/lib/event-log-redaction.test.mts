import assert from "node:assert/strict";
import test from "node:test";

import { redactAuditData } from "./event-log-redaction.ts";

test("redacts patient PII recursively while retaining the audit shape", () => {
  const input = {
    clinic_patient_id: "32a95e2e-489f-48b3-b31b-62bcbcaef457",
    full_name: "Nguyen Thi A",
    changes: {
      phone_primary: { from: "0900000000", to: "0911111111" },
      address: { from: "Old address", to: "New address" },
      location_id: { from: "clinic-a", to: "clinic-b" },
    },
  };

  assert.deepEqual(redactAuditData(input), {
    clinic_patient_id: "32a95e2e-489f-48b3-b31b-62bcbcaef457",
    full_name: "[REDACTED]",
    changes: {
      phone_primary: "[REDACTED]",
      address: "[REDACTED]",
      location_id: { from: "clinic-a", to: "clinic-b" },
    },
  });

  // The helper must never mutate data that may still be used by the request.
  assert.equal(input.full_name, "Nguyen Thi A");
  assert.deepEqual(input.changes.phone_primary, {
    from: "0900000000",
    to: "0911111111",
  });
});

test("redacts identity and secret aliases case-insensitively inside arrays", () => {
  const input = {
    records: [
      {
        patient_name: "Patient A",
        DateOfBirth: "1990-01-01",
        national_id_number: "001234567890",
        ethnicity: "Sensitive ethnicity",
        occupation: "Sensitive occupation",
        guardian_name: "Guardian A",
        access_token: "secret-token",
        status: "CONFIRMED",
      },
    ],
  };

  assert.deepEqual(redactAuditData(input), {
    records: [
      {
        patient_name: "[REDACTED]",
        DateOfBirth: "[REDACTED]",
        national_id_number: "[REDACTED]",
        ethnicity: "[REDACTED]",
        occupation: "[REDACTED]",
        guardian_name: "[REDACTED]",
        access_token: "[REDACTED]",
        status: "CONFIRMED",
      },
    ],
  });
});

test("preserves dates and identifiers needed to investigate an event", () => {
  const occurredAt = new Date("2026-07-17T08:00:00.000Z");
  const input = {
    appointment_id: "appt-1",
    clinic_patient_id: "patient-1",
    slot_start: "2026-07-18T08:00:00+07:00",
    occurred_at: occurredAt,
    status: "CHECKED_IN",
  };

  const output = redactAuditData(input);

  assert.deepEqual(output, input);
  assert.notEqual(output, input);
  assert.equal(output.occurred_at, occurredAt);
});
