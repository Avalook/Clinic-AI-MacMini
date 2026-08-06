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
  // Điều cần canh là NGUỒN quyền, không phải cách viết truy vấn.
  //
  // Bản đầu đòi thấy đúng `.from("clinic_membership")`; bản sau đòi thấy
  // `membership.role` sau khi truy vấn ấy được nhúng vào cùng lượt với `staff`.
  // Cả hai đều ghim vào CÁCH VIẾT, nên cả hai đều đỏ mỗi lần tối ưu dù luật y
  // nguyên. Nguồn quyền nay là backend: getCurrentStaff hỏi GET /api/v1/me,
  // nơi get_current_identity xác thực token rồi tra chính clinic_membership ấy.
  assert.match(
    currentStaffSource,
    /fetchFromBackend<MeResponse>\("\/api\/v1\/me"\)/,
  );
  assert.match(currentStaffSource, /clinic_role:\s*me\.role/);
  // Và bản sao thứ hai KHÔNG được mọc lại: file này không tự đọc bảng nào nữa.
  // Hai bản suy vai từng lệch nhau ở mã vai lạ — backend rơi về CSKH, bản này
  // trả null — nên "chỉ thêm một truy vấn nhỏ cho nhanh" là cách nó quay lại.
  assert.doesNotMatch(currentStaffSource, /\.from\(["']staff["']\)/);
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
