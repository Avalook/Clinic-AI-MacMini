import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const routeSource = read("../app/api/clinical-record/route.ts");
const getSource = routeSource.split("export async function POST")[0];
const clinicSessionSource = read("../lib/clinic-session.ts");
const currentStaffSource = read("../lib/current-staff.ts");
const patientListSource = read("../app/(dashboard)/patient-list/page.tsx");
const doctorBoardSource = read(
  "../app/(dashboard)/tasks/DoctorWorkBoard.tsx",
);
const homeCheckinSource = read(
  "../app/(dashboard)/home/HomeCheckin.tsx",
);
const weeklyAppointmentsSource = read(
  "../app/(dashboard)/home/WeeklyAppointmentsTable.tsx",
);

test("clinical-record GET authorizes the membership role before sensitive reads", () => {
  const resolveRoleAt = getSource.indexOf("await getClinicRole()");
  const clinicalGateAt = getSource.indexOf("canReadClinical(role)");
  const firstSensitiveReadAt = getSource.indexOf(
    '.from("patient_medical_profile")',
  );

  assert.ok(resolveRoleAt >= 0, "GET must resolve the caller's clinic role");
  assert.ok(clinicalGateAt > resolveRoleAt, "GET must check the resolved role");
  assert.ok(
    firstSensitiveReadAt > clinicalGateAt,
    "profile/pregnancy/lab/SOAP/prescription reads must happen after the role gate",
  );
  assert.match(
    getSource.slice(resolveRoleAt, firstSensitiveReadAt),
    /status:\s*403/,
  );
});

test("the clinical role authority comes from clinic_membership, not department or cookies", () => {
  assert.match(
    clinicSessionSource,
    /getCurrentStaff\(\)[\s\S]*departmentToRole\(staff\.clinic_role\)/,
  );
  assert.match(currentStaffSource, /\.from\(["']clinic_membership["']\)/);
  assert.match(
    currentStaffSource,
    /clinic_role:\s*selection\.membership\.role/,
  );
  // The active-clinic cookie chooses *which* membership, and nothing else: the
  // role still comes from the row that membership query returned.
  assert.match(
    currentStaffSource,
    /resolveActiveMembership\(active, await getActiveClinicId\(\)\)/,
  );
});

test("operational roles cannot open a clinical-record popup", () => {
  assert.match(
    patientListSource,
    /const enablePopup = canReadClinical\(role\)/,
  );
  assert.match(
    doctorBoardSource,
    /const open = readOnly\s*\?\s*null\s*:\s*\(?rows\.find/,
  );
  assert.match(
    homeCheckinSource,
    /const sel = canWriteClinical\s*\?\s*\(?rows\.find/,
  );
  assert.match(
    weeklyAppointmentsSource,
    /\{canWriteClinical && selAppt && \(/,
  );
});
