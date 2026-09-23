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
const weeklyAppointmentsSource = read(
  "../app/(dashboard)/home/WeeklyAppointmentsTable.tsx",
);

test("clinical-record GET: backend quyết ai đọc được, trang không tự đọc bảng nhạy cảm", () => {
  // 24/09/2026: cửa đọc (quyền đọc hồ sơ + thư ký chỉ khách của bác sĩ mình)
  // và mọi câu đọc nằm ở backend (`GET /api/v1/clinical-records/doc`,
  // services/ho_so_lam_sang_doc.py). Trang không còn câu `.from(` nào ở GET —
  // nó quay lại là quay lại quyết định ở frontend.
  assert.match(getSource, /\/api\/v1\/clinical-records\/doc/);
  assert.doesNotMatch(getSource, /\.from\(["']/);
  assert.doesNotMatch(getSource, /\.rpc\(["']/);
  const py = read("../../clinicai/api/v1/routers/clinical_records.py");
  assert.match(py, /_DOC_HO_SO_GUARD = require_role\(\*CLINICAL_WRITE_ROLES\)/);
  const svc = read("../../clinicai/services/ho_so_lam_sang_doc.py");
  assert.match(svc, /khach_duoc_xem/);
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
    /const enablePopup = vaiHomNay\.some\(canReadClinical\)/,
  );
  // DoctorWorkBoard (/tasks) và HomeCheckin đã gỡ 18/09/2026 — hai lối mở
  // bệnh án ấy không còn tồn tại (xem man-da-gop-boundary.test.mts).
  assert.match(
    weeklyAppointmentsSource,
    /\{canWriteClinical && selAppt && \(/,
  );
});
